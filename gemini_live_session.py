"""
gemini_live_session.py
Handles bidirectional streaming with Gemini Live API
Manages audio/video input and output, tool calling, and session state
"""

import asyncio
import base64
import json
import os
from typing import Optional, Callable
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Import tools
from tools.firestore_client import get_customer, save_session_log
from tools.churn_scorer import score_churn

load_dotenv()

class GeminiLiveSession:
    """
    Manages a live session with Gemini multimodal API.
    Handles bidirectional streaming of audio/video and tool calling.
    """
    
    def __init__(self, customer_id: str, session_id: str):
        """
        Initialize a new Gemini Live session.
        
        Args:
            customer_id: Customer ID for this session
            session_id: Unique session identifier
        """
        self.customer_id = customer_id
        self.session_id = session_id
        self.client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
        self.model_id = 'gemini-2.0-flash-exp'  # Using the experimental live model
        
        # Session state
        self.live_session = None
        self.is_active = False
        self.customer_data = None
        self.conversation_history = []
        
        # Callbacks for sending data back to frontend
        self.on_audio_response: Optional[Callable] = None
        self.on_text_response: Optional[Callable] = None
        self.on_tool_call: Optional[Callable] = None
        
        # System prompt
        self.system_prompt = self._create_system_prompt()
        
        print(f"✅ GeminiLiveSession created: {session_id} for customer {customer_id}")
    
    def _create_system_prompt(self) -> str:
        """Create the system prompt for Kineo agent"""
        return """You are Kineo, a warm and empathetic customer support agent for an e-commerce platform.

Your job is to help customers who want to return a product. Listen to what went wrong, ask them to show the product if they can, and understand their frustration.

IMPORTANT WORKFLOW:
1. When a session starts, you'll see the customer profile information automatically
2. Ask the customer what went wrong with their order
3. Listen carefully and observe any product issues they show on camera
4. Assess the damage type (wrong_item, broken, quality_issue, defective, damaged, not_as_described)
5. Gauge their frustration level from their tone (0-10 scale)
6. Call the score_and_respond tool with your assessment
7. Deliver the win-back offer naturally and warmly in your voice

PERSONALITY:
- Be warm, empathetic, and genuinely caring
- Speak naturally, not robotically
- Use the customer's first name
- Acknowledge their frustration
- Be solution-oriented
- Never mention internal scores or tiers
- Keep responses concise (2-3 sentences usually)

TOOL USAGE:
- get_customer: Already called, customer info provided at start
- score_and_respond: Call this after understanding the issue, providing damage_label and frustration_score

Remember: You're here to turn a negative experience into a positive one!"""
    
    async def start(self):
        """Start the Gemini Live session"""
        try:
            print(f"\n🔄 Starting Gemini Live session for {self.customer_id}...")
            
            # Get customer data first
            self.customer_data = get_customer(self.customer_id)
            customer_context = f"\n\nCUSTOMER PROFILE:\n{json.dumps(self.customer_data, indent=2)}"
            
            # Create live config
            config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],  # Agent responds with voice
                system_instruction=self.system_prompt + customer_context,
                tools=[
                    self._get_score_and_respond_tool()
                ]
            )
            
            # Connect to Gemini Live API
            async with self.client.aio.live.connect(
                model=self.model_id,
                config=config
            ) as session:
                self.live_session = session
                self.is_active = True
                
                print(f"✅ Connected to Gemini Live API")
                print(f"   Model: {self.model_id}")
                print(f"   Customer: {self.customer_data['name']}")
                
                # Start receiving responses
                receive_task = asyncio.create_task(self._receive_loop())
                
                # Wait for session to be manually stopped
                while self.is_active:
                    await asyncio.sleep(0.1)
                
                # Cancel receive task
                receive_task.cancel()
                
        except Exception as e:
            print(f"❌ Error starting Gemini Live session: {e}")
            raise
    
    async def send_audio(self, audio_data: str):
        """
        Send audio data to Gemini.
        
        Args:
            audio_data: Base64 encoded audio (PCM16, 16kHz)
        """
        if not self.live_session or not self.is_active:
            return
        
        try:
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_data)
            
            # Send to Gemini
            await self.live_session.send(
                types.LiveClientContent(
                    turns=[types.Turn(
                        parts=[types.Part(
                            inline_data=types.Blob(
                                mime_type="audio/pcm",
                                data=audio_bytes
                            )
                        )],
                        role="user"
                    )],
                    turn_complete=False  # Audio is streaming
                )
            )
            
        except Exception as e:
            print(f"❌ Error sending audio: {e}")
    
    async def send_video(self, video_frame: str):
        """
        Send video frame to Gemini.
        
        Args:
            video_frame: Base64 encoded image (JPEG)
        """
        if not self.live_session or not self.is_active:
            return
        
        try:
            # Decode base64 image
            image_bytes = base64.b64decode(video_frame)
            
            # Send to Gemini
            await self.live_session.send(
                types.LiveClientContent(
                    turns=[types.Turn(
                        parts=[types.Part(
                            inline_data=types.Blob(
                                mime_type="image/jpeg",
                                data=image_bytes
                            )
                        )],
                        role="user"
                    )],
                    turn_complete=False
                )
            )
            
        except Exception as e:
            print(f"❌ Error sending video: {e}")
    
    async def send_text(self, text: str):
        """
        Send text message to Gemini.
        
        Args:
            text: Text message from user
        """
        if not self.live_session or not self.is_active:
            return
        
        try:
            await self.live_session.send(
                types.LiveClientContent(
                    turns=[types.Turn(
                        parts=[types.Part(text=text)],
                        role="user"
                    )],
                    turn_complete=True
                )
            )
            
            # Record in conversation
            self.conversation_history.append({
                "role": "user",
                "content": text
            })
            
        except Exception as e:
            print(f"❌ Error sending text: {e}")
    
    async def _receive_loop(self):
        """Continuously receive responses from Gemini"""
        try:
            async for response in self.live_session.receive():
                await self._handle_response(response)
                
        except asyncio.CancelledError:
            print("🛑 Receive loop cancelled")
        except Exception as e:
            print(f"❌ Error in receive loop: {e}")
    
    async def _handle_response(self, response):
        """Handle a response from Gemini"""
        try:
            # Handle server content (agent responses)
            if hasattr(response, 'server_content'):
                server_content = response.server_content
                
                # Check if this is a turn complete
                if server_content.turn_complete:
                    # Extract audio if present
                    for part in server_content.model_turn.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            # Audio response
                            audio_data = base64.b64encode(part.inline_data.data).decode()
                            if self.on_audio_response:
                                await self.on_audio_response(audio_data)
                        
                        elif hasattr(part, 'text') and part.text:
                            # Text response (for logging/transcript)
                            if self.on_text_response:
                                await self.on_text_response(part.text)
                            
                            self.conversation_history.append({
                                "role": "agent",
                                "content": part.text
                            })
            
            # Handle tool calls
            if hasattr(response, 'tool_call'):
                tool_call = response.tool_call
                await self._handle_tool_call(tool_call)
            
        except Exception as e:
            print(f"❌ Error handling response: {e}")
    
    async def _handle_tool_call(self, tool_call):
        """Handle a tool call from Gemini"""
        try:
            function_name = tool_call.function_calls[0].name
            function_args = tool_call.function_calls[0].args
            
            print(f"🔧 Tool call: {function_name}({function_args})")
            
            if function_name == "score_and_respond":
                # Call the churn scoring tool
                damage_label = function_args.get('damage_label', 'quality_issue')
                frustration_score = function_args.get('frustration_score', 5.0)
                
                # Calculate churn score
                churn_result = score_churn(
                    self.customer_data,
                    damage_label,
                    frustration_score
                )
                
                # Save session log
                save_session_log(
                    session_id=self.session_id,
                    customer_id=self.customer_id,
                    damage_label=damage_label,
                    frustration_score=frustration_score,
                    churn_score=churn_result['score'],
                    offer_given=churn_result['offer']
                )
                
                # Send result back to Gemini
                tool_response = types.LiveClientToolResponse(
                    function_responses=[types.FunctionResponse(
                        name=function_name,
                        response={
                            "offer": churn_result['offer'],
                            "churn_tier": churn_result['tier']
                        },
                        id=tool_call.function_calls[0].id
                    )]
                )
                
                await self.live_session.send(tool_response)
                
                # Notify callback
                if self.on_tool_call:
                    await self.on_tool_call({
                        "function": function_name,
                        "result": churn_result
                    })
                
        except Exception as e:
            print(f"❌ Error handling tool call: {e}")
    
    def _get_score_and_respond_tool(self):
        """Get the score_and_respond tool declaration"""
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="score_and_respond",
                    description="Calculates churn risk and generates personalized win-back offer. Call this after understanding the customer's issue and frustration level.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "damage_label": types.Schema(
                                type=types.Type.STRING,
                                description="Type of damage: wrong_item, broken, quality_issue, defective, damaged, not_as_described"
                            ),
                            "frustration_score": types.Schema(
                                type=types.Type.NUMBER,
                                description="Customer frustration level from 0-10 based on tone (0=calm, 5=annoyed, 10=very angry)"
                            )
                        },
                        required=["damage_label", "frustration_score"]
                    )
                )
            ]
        )
    
    async def stop(self):
        """Stop the live session"""
        self.is_active = False
        print(f"👋 Stopping Gemini Live session: {self.session_id}")
