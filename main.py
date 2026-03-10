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
from gemini_live_session import GeminiLiveSession

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
# WEBSOCKET - LIVE SESSION WITH GEMINI
# ═══════════════════════════════════════════════════════════

class SessionManager:
    """
    Manages active WebSocket sessions with Gemini Live API.
    Each session has a GeminiLiveSession that handles bidirectional streaming.
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
        
        try:
            # Get customer profile first
            customer = get_customer(customer_id)
            
            # Create Gemini Live session
            gemini_session = GeminiLiveSession(customer_id, session_id)
            
            # Set up callbacks to send Gemini responses to frontend
            async def on_audio_response(audio_data: str):
                """Send Gemini's audio response to frontend"""
                await websocket.send_json({
                    "type": "audio_response",
                    "data": audio_data
                })
            
            async def on_text_response(text: str):
                """Send Gemini's text (transcript) to frontend"""
                await websocket.send_json({
                    "type": "transcript",
                    "text": text,
                    "role": "agent"
                })
            
            async def on_tool_call(tool_result: dict):
                """Send churn scoring results to frontend"""
                await websocket.send_json({
                    "type": "offer",
                    "text": tool_result['result']['offer'],
                    "churn_score": tool_result['result']['score'],
                    "churn_tier": tool_result['result']['tier'],
                    "session_id": session_id
                })
            
            # Attach callbacks
            gemini_session.on_audio_response = on_audio_response
            gemini_session.on_text_response = on_text_response
            gemini_session.on_tool_call = on_tool_call
            
            # Store session
            self.active_sessions[session_id] = {
                "customer_id": customer_id,
                "customer": customer,
                "websocket": websocket,
                "gemini_session": gemini_session,
                "started_at": datetime.utcnow().isoformat(),
                "messages": []
            }
            
            # Start Gemini session in background
            asyncio.create_task(gemini_session.start())
            
            return session_id
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Session creation failed: {str(e)}")
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """Gets session data."""
        return self.active_sessions.get(session_id)
    
    async def close_session(self, session_id: str):
        """Closes and removes a session."""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            # Stop Gemini session
            if 'gemini_session' in session:
                await session['gemini_session'].stop()
            del self.active_sessions[session_id]


# Global session manager
session_manager = SessionManager()


@app.websocket("/session")
async def websocket_session(websocket: WebSocket):
    """
    WebSocket endpoint for live voice + vision sessions with Gemini.
    
    Flow:
    1. Client connects with customer_id
    2. Server creates Gemini Live session
    3. Audio/video streams bidirectionally in real-time
    4. Gemini calls tools (score_and_respond) automatically
    5. Agent speaks personalized offer
    6. Session ends, data already logged to Firestore
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
        
        # Create session with Gemini Live
        session_id = await session_manager.create_session(websocket, customer_id)
        session = session_manager.get_session(session_id)
        gemini_session = session['gemini_session']
        
        # Send session started confirmation
        await websocket.send_json({
            "type": "session_started",
            "session_id": session_id,
            "customer": session["customer"]
        })
        
        print(f"\n✅ Gemini Live session started: {session_id} (Customer: {customer_id})")
        
        # Give Gemini session a moment to connect
        await asyncio.sleep(1)
        
        # Main session loop - handle incoming messages
        while True:
            try:
                message = await websocket.receive_json()
                message_type = message.get("type")
                
                # Handle different message types
                if message_type == "audio_chunk":
                    # Stream audio to Gemini Live API
                    audio_data = message.get("data")
                    await gemini_session.send_audio(audio_data)
                    
                elif message_type == "video_frame":
                    # Stream video frame to Gemini Live API
                    frame_data = message.get("data")
                    await gemini_session.send_video(frame_data)
                    
                elif message_type == "transcript":
                    # Send text to Gemini
                    transcript = message.get("text", "")
                    session["messages"].append({
                        "role": "user",
                        "content": transcript,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                    await gemini_session.send_text(transcript)
                    
                    # Echo back to frontend
                    await websocket.send_json({
                        "type": "transcript",
                        "text": transcript,
                        "role": "user"
                    })
                    
                elif message_type == "request_offer":
                    # Manual trigger for testing (in real use, Gemini calls tool automatically)
                    damage_label = message.get("damage_label", "quality_issue")
                    frustration_score = message.get("frustration_score", 5.0)
                    
                    # Call churn scoring directly
                    result = tool_score_and_respond(
                        customer_id=customer_id,
                        damage_label=damage_label,
                        frustration_score=frustration_score
                    )
                    
                    if result["success"]:
                        await websocket.send_json({
                            "type": "offer",
                            "text": result["offer"],
                            "session_id": result["session_id"]
                        })
                        print(f"✅ Manual offer generated for {customer_id}")
                
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
            await session_manager.close_session(session_id)
        
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

