# app.py

import os
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import json
import asyncio
import uvicorn
from pydantic import BaseModel
from rag_pipeline import RAGSystem, UPLOADS_DIR

app = FastAPI(title="Document Q&A System")
app.mount("/static", StaticFiles(directory="static"), name="static")
rag_system = RAGSystem()


class QuestionRequest(BaseModel):
    question: str


@app.get("/")
async def index():
    return FileResponse(os.path.join("static", "index.html"))


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    file_path = os.path.join(UPLOADS_DIR, filename)

    with open(file_path, "wb") as dest:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            dest.write(chunk)

    try:
        await run_in_threadpool(rag_system.process_document, file_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        import traceback
        traceback.print_exc()  # Print full error to console for debugging
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(exc)}") from exc

    return JSONResponse({"message": "Document processed successfully."})


@app.post("/api/ask")
async def ask_question(payload: QuestionRequest):
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    async def generate():
        try:
            # Get source documents first
            docs = await run_in_threadpool(
                rag_system.vectorstore.similarity_search, question, k=5
            )
            
            # Stream the answer
            answer_buffer = []
            async for chunk in rag_system.ask_question_stream(question):
                answer_buffer.append(chunk)
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
            
            # Send sources at the end
            sources = []
            for doc in docs:
                sources.append({
                    "source": os.path.basename(doc.metadata.get("source", "Unknown")),
                    "content": doc.page_content,
                })
            
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
            yield "data: {\"type\": \"done\"}\n\n"
            
        except Exception as exc:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)