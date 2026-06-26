#def main():
#    print("Hello from adkagents!")


import os
import uvicorn
from google.adk.cli.fast_api import get_fast_api_app

# 1. Grab the dynamic port assigned by Google Cloud Run
port = int(os.environ.get("PORT", 8080))

# 2. Wrap your ADK agent in a production-ready FastAPI web server
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
app = get_fast_api_app(
    agents_dir=AGENT_DIR,
    allow_origins=["*"],
    web=True,
    trace_to_cloud=os.environ.get("TRACE_TO_CLOUD", "false").lower() == "true",
)

import httpx
from pydantic import BaseModel
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from bank_agent.observability import store, CostGranularity


class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    message: str


class ChatResponse(BaseModel):
    response: str
    session_id: str


@app.post("/api/chat", response_model=ChatResponse)
async def api_chat(req: ChatRequest):
    """Simple chat endpoint for external integration (e.g. Flutter app)."""
    session_url = f"http://127.0.0.1:{port}/apps/bank_agent/users/{req.user_id}/sessions/{req.session_id}"
    run_url = f"http://127.0.0.1:{port}/run"
    
    async with httpx.AsyncClient() as client:
        try:
            # Check if session exists; if not, create it
            session_resp = await client.get(session_url)
            if session_resp.status_code == 404:
                create_session_url = f"http://127.0.0.1:{port}/apps/bank_agent/users/{req.user_id}/sessions"
                create_payload = {
                    "session_id": req.session_id,
                    "state": {}
                }
                create_resp = await client.post(create_session_url, json=create_payload)
                if create_resp.status_code not in (200, 201):
                    raise HTTPException(status_code=create_resp.status_code, detail=f"Failed to auto-create session: {create_resp.text}")

            payload = {
                "app_name": "bank_agent",
                "user_id": req.user_id,
                "session_id": req.session_id,
                "new_message": {
                    "parts": [{"text": req.message}]
                }
            }
            
            response = await client.post(run_url, json=payload, timeout=60.0)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=f"ADK runner error: {response.text}")
            
            events = response.json()
            text_response = ""
            for event in events:
                if event.get("type") == "content" or "content" in event:
                    content_data = event.get("content", {})
                    parts = content_data.get("parts", [])
                    for part in parts:
                        if "text" in part:
                            text_response += part["text"]
            
            if not text_response:
                text_response = "I did not receive a text response from the agent. Please try again."
                
            return ChatResponse(
                response=text_response.strip(),
                session_id=req.session_id
            )
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=f"Failed to communicate with ADK agent: {str(e)}")



@app.get("/obs", response_class=HTMLResponse)
async def obs_dashboard():
    """Serves the frontend dashboard for agent observability."""
    html_path = os.path.join(AGENT_DIR, "bank_agent", "observability", "dashboard.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="Dashboard file not found.", status_code=404)


@app.get("/obs/summary")
async def obs_summary(granularity: str | None = None):
    """Aggregated stats: sessions, total tokens, cost, avg latency.

    Optional ``?granularity=session|turn|cumulative`` query param overrides
    the default (env ``COST_GRANULARITY``).
    """
    gran = None
    if granularity:
        try:
            gran = CostGranularity(granularity.strip().lower())
        except ValueError:
            pass
    return store.get_summary(granularity=gran)


@app.get("/obs/traces")
async def obs_traces(limit: int = 100):
    """Individual LLM call records (newest first).

    Optional ``?limit=N`` query param controls the number of records returned
    (default 100).
    """
    return store.get_traces(limit=limit)


@app.get("/obs/tools")
async def obs_tools():
    """Per-tool call counts, success rates, and duration percentiles."""
    return store.get_tool_stats()


@app.post("/obs/reset")
async def obs_reset():
    """Clear all recorded observability data."""
    store.reset()
    return {"status": "ok", "message": "Observability data cleared"}


if __name__ == "__main__":
    # 3. Start the server!
    uvicorn.run(app, host="0.0.0.0", port=port)