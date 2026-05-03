"""
FastAPI Backend for Multi-Agent Research Assistant
Endpoints:
  POST /research       — start a new research job
  GET  /status/{id}    — check job status
  GET  /report/{id}    — retrieve final report
  WS   /ws/{id}        — stream real-time agent progress
"""
import os
import uuid
import asyncio
import json
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# In-memory job store (replace with Redis for production)
jobs: dict[str, dict] = {}
# WebSocket connections per job_id
ws_connections: dict[str, list[WebSocket]] = {}


# ─── Models ──────────────────────────────────────────────────────────────────

class ResearchRequest(BaseModel):
    topic: str
    depth: str = "quick"  # "quick" | "deep"


class ResearchResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobStatus(BaseModel):
    job_id: str
    status: str          # "pending" | "running" | "completed" | "failed"
    topic: str
    depth: str
    created_at: str
    completed_at: Optional[str] = None
    progress_log: list[str] = []
    error: Optional[str] = None


# ─── App Setup ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Multi-Agent Research Assistant API starting...")
    yield
    print("🛑 API shutting down...")


app = FastAPI(
    title="Multi-Agent Research Assistant",
    description="Autonomous research pipeline with LangGraph + CrewAI agents",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── WebSocket Manager ───────────────────────────────────────────────────────

async def broadcast_progress(job_id: str, agent: str, message: str):
    """Send progress update to all WebSocket clients watching this job."""
    payload = json.dumps({
        "type": "progress",
        "agent": agent,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    })
    
    # Store in job log
    if job_id in jobs:
        jobs[job_id]["progress_log"].append(f"[{agent}] {message}")
    
    # Broadcast to WebSocket clients
    if job_id in ws_connections:
        dead = []
        for ws in ws_connections[job_id]:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            ws_connections[job_id].remove(ws)


# ─── Background Task ─────────────────────────────────────────────────────────

async def run_research_job(job_id: str, topic: str, depth: str):
    """Execute the research pipeline in the background."""
    
    # Import here to avoid circular imports
    from graph.workflow import run_research
    
    jobs[job_id]["status"] = "running"
    
    # Create async-safe progress callback
    loop = asyncio.get_event_loop()
    
    def progress_callback(agent: str, message: str):
        asyncio.run_coroutine_threadsafe(
            broadcast_progress(job_id, agent, message),
            loop
        )
    
    try:
        # Run in thread pool to not block event loop
        final_state = await asyncio.to_thread(
            run_research,
            topic=topic,
            depth=depth,
            progress_callback=progress_callback,
        )
        
        jobs[job_id].update({
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "final_report": final_state.get("final_report", ""),
            "draft_report": final_state.get("draft_report", ""),
            "sources": final_state.get("sources", []),
            "fact_check_results": final_state.get("fact_check_results", []),
            "iteration_count": final_state.get("iteration_count", 0),
        })
        
        await broadcast_progress(job_id, "system", "✅ Research complete! Report is ready.")
        
    except Exception as e:
        jobs[job_id].update({
            "status": "failed",
            "completed_at": datetime.now().isoformat(),
            "error": str(e),
        })
        await broadcast_progress(job_id, "system", f"❌ Error: {str(e)}")


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name": "Multi-Agent Research Assistant",
        "version": "1.0.0",
        "endpoints": {
            "POST /research": "Start research job",
            "GET /status/{job_id}": "Check job status",
            "GET /report/{job_id}": "Get final report",
            "WS /ws/{job_id}": "Stream progress",
        }
    }


@app.post("/research", response_model=ResearchResponse)
async def start_research(request: ResearchRequest, background_tasks: BackgroundTasks):
    """Start a new research job."""
    
    if not request.topic.strip():
        raise HTTPException(status_code=400, detail="Topic cannot be empty")
    
    if request.depth not in ("quick", "deep"):
        raise HTTPException(status_code=400, detail="depth must be 'quick' or 'deep'")
    
    job_id = str(uuid.uuid4())[:8]
    
    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "topic": request.topic,
        "depth": request.depth,
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
        "progress_log": [],
        "final_report": None,
        "error": None,
    }
    
    ws_connections[job_id] = []
    
    background_tasks.add_task(run_research_job, job_id, request.topic, request.depth)
    
    return ResearchResponse(
        job_id=job_id,
        status="pending",
        message=f"Research job started. Connect to /ws/{job_id} for live updates.",
    )


@app.get("/status/{job_id}", response_model=JobStatus)
async def get_status(job_id: str):
    """Check the status of a research job."""
    
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    job = jobs[job_id]
    return JobStatus(
        job_id=job["job_id"],
        status=job["status"],
        topic=job["topic"],
        depth=job["depth"],
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
        progress_log=job.get("progress_log", []),
        error=job.get("error"),
    )


@app.get("/report/{job_id}")
async def get_report(job_id: str):
    """Retrieve the final research report."""
    
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    job = jobs[job_id]
    
    if job["status"] != "completed":
        raise HTTPException(
            status_code=202,
            detail=f"Report not ready yet. Current status: {job['status']}"
        )
    
    return {
        "job_id": job_id,
        "topic": job["topic"],
        "status": "completed",
        "final_report": job.get("final_report", ""),
        "sources_count": len(job.get("sources", [])),
        "fact_checks_count": len(job.get("fact_check_results", [])),
        "iterations": job.get("iteration_count", 0),
        "completed_at": job.get("completed_at"),
    }


@app.get("/jobs")
async def list_jobs():
    """List all jobs (for debugging)."""
    return [
        {
            "job_id": j["job_id"],
            "topic": j["topic"],
            "status": j["status"],
            "created_at": j["created_at"],
        }
        for j in jobs.values()
    ]


@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time progress streaming."""
    await websocket.accept()
    
    if job_id not in ws_connections:
        ws_connections[job_id] = []
    ws_connections[job_id].append(websocket)
    
    try:
        # Send current log history immediately on connect
        if job_id in jobs:
            log = jobs[job_id].get("progress_log", [])
            for entry in log:
                await websocket.send_text(json.dumps({
                    "type": "history",
                    "message": entry,
                }))
            
            # If already complete, send final status
            if jobs[job_id]["status"] == "completed":
                await websocket.send_text(json.dumps({
                    "type": "complete",
                    "message": "Research complete!",
                }))
        
        # Keep connection alive
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
            
    except WebSocketDisconnect:
        if job_id in ws_connections and websocket in ws_connections[job_id]:
            ws_connections[job_id].remove(websocket)


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("BACKEND_PORT", 8000)),
        reload=False,
    )
