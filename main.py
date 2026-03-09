"""
main.py
FastAPI application entry point for Kineo
Handles HTTP endpoints and WebSocket connections for live agent sessions
"""

import os
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Import Kineo modules
from agent import (
    client, MODEL_ID, create_agent_config,
    tool_get_customer, tool_score_and_respond
)
from tools.firestore_client import get_customer, list_all_customers
from tools.churn_scorer import score_churn

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Kineo",
    description="Real-time voice + vision return agent for e-commerce churn prevention",
    version="1.0.0"
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════
# HTTP ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/")
async def serve_frontend():
    """
    Serves the frontend HTML file.
    """
    frontend_path = Path(__file__).parent / "frontend" / "index.html"
    if not frontend_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(frontend_path)


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    Returns status and model information.
    """
    return JSONResponse(content={
        "status": "ok",
        "model": MODEL_ID,
        "timestamp": datetime.utcnow().isoformat(),
        "service": "Kineo Voice Agent"
    })


@app.get("/customer/{customer_id}")
async def get_customer_profile(customer_id: str):
    """
    Fetches customer profile from Firestore.
    
    Args:
        customer_id: Unique customer identifier
        
    Returns:
        Customer profile data
    """
    try:
        customer = get_customer(customer_id)
        return JSONResponse(content={
            "success": True,
            "customer": customer
        })
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving customer: {str(e)}")


@app.get("/customers")
async def list_customers():
    """
    Lists all customers in the database.
    Useful for debugging and testing.
    """
    try:
        customers = list_all_customers()
        return JSONResponse(content={
            "success": True,
            "count": len(customers),
            "customers": customers
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing customers: {str(e)}")


# ═══════════════════════════════════════════════════════════
# WEBSOCKET - LIVE SESSION
# ═══════════════════════════════════════════════════════════

class SessionManager:
    """
    Manages active WebSocket sessions with Gemini Live API.
    """
    
    def __init__(self):
        self.active_sessions: Dict[str, dict] = {}
    
    async def create_session(self, websocket: WebSocket, customer_id: str):
        """
        Creates a new live session with Gemini.
        
        Args:
            websocket: Client WebSocket connection
            customer_id: Customer ID for this session
        """
        session_id = f"session_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        # Get customer profile
        try:
            customer = get_customer(customer_id)
            
            self.active_sessions[session_id] = {
                "customer_id": customer_id,
                "customer": customer,
                "websocket": websocket,
                "started_at": datetime.utcnow().isoformat(),
                "messages": []
            }
            
            return session_id
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Session creation failed: {str(e)}")
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """Gets session data."""
        return self.active_sessions.get(session_id)
    
    def close_session(self, session_id: str):
        """Closes and removes a session."""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]


# Global session manager
session_manager = SessionManager()


@app.websocket("/session")
async def websocket_session(websocket: WebSocket):
    """
    WebSocket endpoint for live voice + vision sessions.
    
    Flow:
    1. Client connects with customer_id
    2. Server creates Gemini Live session
    3. Audio/video streams bidirectionally
    4. Server calls tools (get_customer, score_and_respond) when needed
    5. Agent speaks personalized offer
    6. Session ends, data logged to Firestore
    """
    await websocket.accept()
    session_id = None
    
    try:
        # Wait for initial customer_id message
        init_message = await websocket.receive_json()
        customer_id = init_message.get("customer_id")
        
        if not customer_id:
            await websocket.send_json({
                "type": "error",
                "message": "customer_id required"
            })
            await websocket.close()
            return
        
        # Create session
        session_id = await session_manager.create_session(websocket, customer_id)
        session = session_manager.get_session(session_id)
        
        # Send session started confirmation
        await websocket.send_json({
            "type": "session_started",
            "session_id": session_id,
            "customer": session["customer"]
        })
        
        print(f"\n✅ Session started: {session_id} (Customer: {customer_id})")
        
        # Main session loop - handle incoming messages
        while True:
            try:
                message = await websocket.receive_json()
                message_type = message.get("type")
                
                # Handle different message types
                if message_type == "audio_chunk":
                    # In full implementation, this would stream to Gemini Live API
                    # For now, log that we received audio
                    print(f"📢 Received audio chunk from {customer_id}")
                    
                elif message_type == "video_frame":
                    # In full implementation, this would stream to Gemini Live API
                    print(f"📹 Received video frame from {customer_id}")
                    
                elif message_type == "transcript":
                    # Store user transcript
                    transcript = message.get("text", "")
                    session["messages"].append({
                        "role": "user",
                        "content": transcript,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                    # Echo back (in full implementation, Gemini would respond)
                    await websocket.send_json({
                        "type": "transcript",
                        "text": transcript,
                        "role": "user"
                    })
                    
                elif message_type == "request_offer":
                    # Client requesting churn scoring and offer
                    damage_label = message.get("damage_label", "quality_issue")
                    frustration_score = message.get("frustration_score", 5.0)
                    
                    # Call churn scoring tool
                    result = tool_score_and_respond(
                        customer_id=customer_id,
                        damage_label=damage_label,
                        frustration_score=frustration_score
                    )
                    
                    if result["success"]:
                        # Send offer to client
                        await websocket.send_json({
                            "type": "offer",
                            "text": result["offer"],
                            "session_id": result["session_id"]
                        })
                        
                        print(f"✅ Offer generated for {customer_id}: {result['offer'][:80]}...")
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": result.get("error", "Unknown error")
                        })
                
                elif message_type == "end_session":
                    print(f"👋 Session ending: {session_id}")
                    break
                    
            except WebSocketDisconnect:
                print(f"🔌 WebSocket disconnected: {session_id}")
                break
            except Exception as e:
                print(f"❌ Error in session {session_id}: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
    
    except Exception as e:
        print(f"❌ Session error: {str(e)}")
        if websocket.client_state.name == "CONNECTED":
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
    
    finally:
        # Cleanup
        if session_id:
            session_manager.close_session(session_id)
        
        # Close websocket if still open
        if websocket.client_state.name == "CONNECTED":
            await websocket.close()


# ═══════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    """
    Runs on application startup.
    """
    print("\n" + "="*70)
    print("🚀 KINEO SERVER STARTING")
    print("="*70)
    print(f"Model: {MODEL_ID}")
    print(f"Project: {os.getenv('GCP_PROJECT_ID')}")
    print(f"Endpoints:")
    print(f"  GET  /health")
    print(f"  GET  /customer/{{customer_id}}")
    print(f"  GET  /customers")
    print(f"  GET  /")
    print(f"  WS   /session")
    print("="*70 + "\n")


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8080))
    
    print(f"\n🌐 Starting Kineo on http://localhost:{port}")
    print(f"📱 Frontend: http://localhost:{port}")
    print(f"🔍 Health check: http://localhost:{port}/health\n")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )

