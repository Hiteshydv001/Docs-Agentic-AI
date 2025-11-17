# rag_pipeline.py

import os

# Disable ChromaDB telemetry BEFORE importing Chroma
os.environ["ANONYMIZED_TELEMETRY"] = "False"

import shutil

from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.llms import Ollama
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

# --- Constants ---
VECTORSTORE_DIR = "chroma_db"
UPLOADS_DIR = "uploads"
# Use a top-tier embedding model for better accuracy
EMBEDDING_MODEL_NAME = "BAAI/bge-large-en-v1.5" 
LLM_MODEL_NAME = "mistral:latest"

# Ensure necessary directories exist
os.makedirs(UPLOADS_DIR, exist_ok=True)

class RAGSystem:
    def __init__(self):
        """Initializes the RAG system components."""
        # 1. Initialize the powerful embedding model
        # BAAI's BGE models are top-performers on the MTEB leaderboard.
        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL_NAME,
            model_kwargs={'device': 'cpu'},  # Use 'cuda' for GPU
            encode_kwargs={'normalize_embeddings': True}  # Crucial for BGE models
        )
        
        # 2. Initialize the local LLM
        self.llm = Ollama(
            model=LLM_MODEL_NAME,
            temperature=0.3,
            num_predict=512,
            num_ctx=4096,
        )
        
        # 3. Define the QA prompt template for high accuracy
        # This prompt strictly guides the LLM to use only the provided context.
        self.prompt_template = """You are an expert Q&A assistant. Your task is to answer the user's question based *only* on the provided text context.

Follow these rules STRICTLY:
1. Read the context carefully.
2. Formulate a concise answer to the question using ONLY the information from the context.
3. Do NOT copy-paste the context. Summarize and rephrase the information in your own words.
4. If the answer cannot be found in the context, you MUST reply with "I'm sorry, the answer to that question is not in the provided document."

CONTEXT:
---
{context}
---

QUESTION: {question}

ANSWER:"""
        self.qa_prompt = PromptTemplate(
            template=self.prompt_template, input_variables=["context", "question"]
        )

        self.vectorstore = None
        self.qa_chain = None

    def process_document(self, file_path):
        """
        Loads, splits, and embeds a document to create a queryable vector store.
        """
        print(f"Processing document: {file_path}")
        
        # --- 1. Load the document ---
        # Select the appropriate loader based on the file extension.
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".txt":
            loader = TextLoader(file_path)
        elif ext == ".pdf":
            loader = PyPDFLoader(file_path)
        elif ext == ".docx":
            loader = Docx2txtLoader(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
        documents = loader.load()

        # --- 2. Split the document into chunks (Advanced Technique) ---
        # RecursiveCharacterTextSplitter is context-aware. It tries to split on
        # paragraphs, then sentences, ensuring chunks are semantically coherent.
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        chunks = text_splitter.split_documents(documents)
        print(f"Document split into {len(chunks)} chunks.")

        # --- 3. Create and persist the vector store ---
        # Clean any old database files to ensure data from previous sessions is cleared.
        # Delete old vectorstore client reference first to release file locks
        if self.vectorstore is not None:
            try:
                del self.vectorstore
            except Exception:
                pass
        
        # Now attempt to remove the directory
        if os.path.exists(VECTORSTORE_DIR):
            try:
                shutil.rmtree(VECTORSTORE_DIR)
            except (PermissionError, OSError) as e:
                print(f"Warning: Could not delete old vector store: {e}")
                # Force cleanup by trying again after a short delay
                import time
                time.sleep(0.5)
                try:
                    shutil.rmtree(VECTORSTORE_DIR)
                except Exception:
                    # If still failing, try to work with existing directory
                    pass
        
        self.vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=VECTORSTORE_DIR
        )
        print(f"Vector store created in {VECTORSTORE_DIR}.")

        # --- 4. Create the RetrievalQA chain ---
        # This chain combines the retriever and the LLM.
        # We use 'Maximal Marginal Relevance' (MMR) for retrieval. MMR fetches
        # chunks that are both relevant to the query AND diverse, which provides a
        # richer, less redundant context to the LLM.
        retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={'k': 5}
        )

        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=retriever,
            chain_type_kwargs={"prompt": self.qa_prompt},
            return_source_documents=True
        )
        print("QA Chain is ready.")

    def ask_question(self, question):
        """
        Asks a question to the loaded document and returns the result.
        """
        if not self.qa_chain:
            return {"error": "Document not processed. Please upload and process a document first."}
        
        print(f"Asking question: {question}")
        result = self.qa_chain.invoke({"query": question})
        
        # Fallback if result is empty
        if not result.get("result") or result.get("result").strip() == "":
            # Try direct retrieval
            docs = self.vectorstore.similarity_search(question, k=3)
            context = "\n\n".join([doc.page_content for doc in docs])
            result["result"] = f"Based on the document: {context[:500]}..."
        
        return result
    
    async def ask_question_stream(self, question):
        """
        Stream the answer token by token for real-time display.
        """
        if not self.qa_chain:
            yield "Error: Document not processed."
            return
        
        print(f"Asking question (streaming): {question}")
        
        # Get relevant context
        docs = self.vectorstore.similarity_search(question, k=5)
        context = "\n\n".join([doc.page_content for doc in docs])
        
        # Format the prompt
        prompt = self.prompt_template.format(context=context, question=question)
        
        # Stream from Ollama
        try:
            for chunk in self.llm.stream(prompt):
                if chunk:
                    yield chunk
        except Exception as e:
            print(f"Streaming error: {e}")
            # Fallback to non-streaming
            result = self.qa_chain.invoke({"query": question})
            answer = result.get("result", "No answer generated.")
            for char in answer:
                yield char
                import time
                time.sleep(0.01)  # Simulate streaming