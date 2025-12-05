"""Tiny FastAPI app exposing health and manual sync endpoints."""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import threading
from main import main as run_sync

app = FastAPI(title="Airtable-ClickUp Sync API")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/sync")
def sync():
    # run sync in background thread to avoid blocking
    thread = threading.Thread(target=run_sync, daemon=True)
    thread.start()
    return JSONResponse({"status": "sync_started"})
