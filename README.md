# Kalpit AI Agent Document Q&A

Retro-styled document question answering workspace completed for the **Kalpit Private Limited (UK) – AI Agent Development Internship** assignment. The project couples a FastAPI backend, LangChain-powered Retrieval-Augmented Generation (RAG) pipeline, and a lightweight static frontend that streams answers with cited snippets.

<video width="100%" controls>
  <source src="https://github.com/Hiteshydv001/Docs-Agentic-AI/blob/main/Kalpit%20Private%20Limited%2C%20UK.mp4" type="video/mp4">
  Your browser does not support the video tag.
</video>


## Table of Contents
1. [Features](#features)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Project Layout](#project-layout)
5. [Running Locally](#running-locally)
6. [API Endpoints](#api-endpoints)
7. [Docker Image](#docker-image)
8. [Deploying](#deploying)
9. [Configuration](#configuration)
10. [Troubleshooting](#troubleshooting)

## Features
- **Multi-format ingestion** – accepts `.txt`, `.pdf`, and `.docx` documents, chunked with LangChain text splitters.
- **BGE embeddings + Chroma** – stores contextual vectors for fast similarity search and persistent retrieval.
- **Local LLM via Ollama** – streams answers token-by-token while enforcing a context-grounded prompt.
- **Cited evidence** – most-relevant chunks are surfaced after every answer for reviewers.
- **Retro UI** – responsive single page built with vanilla HTML/CSS/JS, tuned to the assignment brand.
- **Deployment-ready** – Dockerfile for Render (backend) and static assets for Vercel (frontend).

## Architecture
```
+--------------------+       +-------------------+       +--------------------+
|  Static Frontend   | <---> |  FastAPI Backend  | <---> | LangChain RAG Stack |
| (Vercel / static)  | SSE   | (Render / Docker) |       | Embeddings + LLM    |
+--------------------+       +-------------------+       +--------------------+
          |                              |                          |
          |----> /api/upload ------------> loads -> splits -> stores
          |<--- stream /api/ask <--------- retrieves -> streams LLM output
```
- `app.py` exposes upload + ask endpoints, streams responses via Server-Sent Events, and mounts `/static` for local development.
- `rag_pipeline.py` builds the RAGSystem: HuggingFace BGE embeddings, Chroma DB, LangChain RetrievalQA chain, and Ollama LLM client.
- `static/` holds the UI (`index.html`, `styles.css`, `app.js`). JavaScript manages uploads, SSE parsing, answer rendering, and source listing.

## Tech Stack
- **Python 3.11**, **FastAPI**, **Uvicorn**
- **LangChain**, **langchain-community**, **langchain-text-splitters**
- **ChromaDB** for vector persistence
- **HuggingFace Embeddings** (`BAAI/bge-large-en-v1.5`)
- **Ollama** client targeting `mistral:latest`
- **Vanilla HTML/CSS/JS** frontend

## Project Layout
```
.
├── app.py                 # FastAPI application & routes
├── rag_pipeline.py        # RAGSystem definition
├── static/                # Frontend (index.html, styles.css, app.js)
├── uploads/               # Runtime uploads (ignored by git)
├── chroma_db/             # Embedded vector store (ignored by git)
├── requirements.txt
├── Dockerfile
└── README.md
```

## Running Locally
Prerequisites: Python 3.11+, Ollama daemon running (or adjust `rag_pipeline.py` to hit a remote Ollama host), and ideally a virtual environment.

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```
Visit `http://localhost:8000` to load the UI, upload a document, then ask questions once processing completes. The first upload downloads the BGE embedding model, so expect a longer warm-up.

### Connecting to a remote Ollama host
If Render (or another service) cannot run the Ollama daemon, set the environment variable `OLLAMA_HOST=https://your-ollama-endpoint` before launching the app. LangChain’s `Ollama` client will route through that base URL.

## API Endpoints
- `GET /` – serves `static/index.html` for local preview.
- `POST /api/upload` – multipart form upload of a single document. Triggers ingestion and returns a status JSON: `{ "message": "Document processed successfully." }`.
- `POST /api/ask` – `{ "question": "..." }` body. Streams SSE payloads containing tokens, sources, and completion markers.

## Docker Image
The repo ships with a production-ready Dockerfile optimized for Render.

```bash
docker build -t kalpit-docqa .
docker run -p 8000:8000 kalpit-docqa
```
Directories `uploads/` and `chroma_db/` are created in the container at `/app`. Mount volumes if you need persistence.

## Deploying
### Backend on Render
1. Push the repository to GitHub and create a Render **Web Service** using the Docker option.
2. Ensure environment variables include `PORT=8000` and any LLM configuration (e.g., `OLLAMA_HOST`).
3. Attach a Render Disk if uploads / vector store persistence is required.
4. Render respects the Docker `CMD`, so no start command override is necessary.

### Frontend on Vercel
1. Either point Vercel at the same repo with root `static/` or copy the folder into a dedicated frontend repo.
2. Configure the build as “Other”, leave the build command empty, and set output directory to `static`.
3. Update `static/app.js` to use an absolute API base when hitting the Render backend (e.g., `const API_BASE = 'https://your-service.onrender.com';`).
4. Expose `NEXT_PUBLIC_API_BASE` (or similar) in Vercel if you want environment-dependent endpoints.

## Configuration
| Variable | Description |
| --- | --- |
| `PORT` | Port FastAPI listens on (default `8000`). Required by Render. |
| `OLLAMA_HOST` | Optional base URL for a remote Ollama server. Leave unset to use local defaults. |
| `VECTORSTORE_DIR`, `UPLOADS_DIR` | Paths inside `rag_pipeline.py`; override if mounting volumes elsewhere. |

Dependencies are pinned via `requirements.txt`; keep them in sync with the Docker image to avoid mismatch between local and hosted builds.

## Troubleshooting
- **Upload stuck / slow**: first run downloads embedding weights and can take a few minutes. Subsequent uploads reuse the cached model.
- **"Document not processed" when asking**: ensure the upload succeeded (green status) before hitting “Get Answer”.
- **No Ollama server**: either install Ollama locally (`https://ollama.com`) or swap `RAGSystem` to call an API-based LLM (OpenAI, Azure OpenAI, etc.).
- **Render build fails**: confirm the Render service uses Docker and that `requirements.txt` matches the Python version (3.11).
- **Large uploads**: raise the chunk size / timeout in `app.py` as needed and consider S3/offloaded storage for production.

---
Feel free to reach out if you need a walkthrough, further optimizations, or alternative deployment targets.
