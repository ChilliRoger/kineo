"""
gemini_audio_session.py
Alternative implementation using Gemini's standard audio API
Since Live API is not available, this uses generate_content with audio input/output
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

class GeminiAudioSession:
    """
    Manages audio interaction with Gemini using standard API.
    Simulates bidirectional audio conversation.
    """
    
    def __init__(self, customer_id: str, session_id: str):
        """Initialize Gemini audio session"""
        self.customer_id = customer_id
        self.session_id = session_id
        self.client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
        self.model_id = 'gemini-2.0-flash'  # Try 2.0 flash - might have separate quota
        
        # Session state
        self.is_active = False
        self.customer_data = None
        self.conversation_history = []
        self.audio_buffer = []
        
        # Callbacks
        self.on_audio_response: Optional[Callable] = None
        self.on_text_response: Optional[Callable] = None
        self.on_tool_call: Optional[Callable] = None
        
        # System prompt
        self.system_prompt = self._create_system_prompt()
        
        print(f"✅ GeminiAudioSession created: {session_id} for customer {customer_id}")
    
    def _create_system_prompt(self) -> str:
        """Create system prompt"""
        return """You are Kineo, a warm customer support agent for e-commerce returns.

Listen to customer complaints, assess damage type (wrong_item, broken, quality_issue, etc.) 
and frustration level (0-10), then offer a personalized win-back deal.

Be empathetic, concise, and solution-oriented. Use the customer's first name."""
    
    async def start(self):
        """Start the session"""
        try:
            print(f"\n🔄 Starting Gemini audio session for {self.customer_id}...")
            
            # Get customer data
            self.customer_data = get_customer(self.customer_id)
            self.is_active = True
            
            print(f"✅ Session started")
            print(f"   Customer: {self.customer_data['name']}")
            
            # Keep session alive
            while self.is_active:
                await asyncio.sleep(0.1)
                
        except Exception as e:
            print(f"❌ Error starting session: {e}")
            raise
    
    async def send_audio(self, audio_data: str):
        """Buffer audio data (disabled - no speech-to-text available)"""
        if not self.is_active:
            return
        
        # Just buffer audio, don't process automatically
        # In production, you'd use Google Speech-to-Text API here
        self.audio_buffer.append(audio_data)
    
    async def send_video(self, video_frame: str):
        """Process video frame (optional, for context)"""
        # Store latest frame for context
        self.latest_video_frame = video_frame
    
    async def send_text(self, text: str):
        """Send text message"""
        if not self.is_active:
            print(f"⚠️ Session not active, ignoring text: {text}")
            return
        
        try:
            print(f"\n📨 Received user text: {text}")
            
            # Generate response
            response_text = await self._generate_response(text)
            print(f"🤖 Generated response: {response_text}")
            
            # Send text back
            if self.on_text_response:
                await self.on_text_response(response_text)
                print(f"✅ Sent response via callback")
            else:
                print(f"⚠️ No on_text_response callback set!")
            
            # Check if we should score churn
            if any(keyword in text.lower() for keyword in ['wrong', 'broken', 'defective', 'damaged', 'unhappy', 'frustrated']):
                print(f"🎯 Triggering churn scoring...")
                await self._trigger_churn_scoring(text, response_text)
                
        except Exception as e:
            print(f"❌ Error sending text: {e}")
            import traceback
            traceback.print_exc()
    
    async def _process_audio_buffer(self):
        """Process buffered audio and generate response"""
        if not self.audio_buffer:
            return
        
        try:
            # For now, simulate audio processing by converting to text
            # In production, you'd use speech-to-text
            text = "[Audio captured - simulated transcription]"
            
            # Generate response using text
            response_text = await self._generate_response(text)
            
            # Send response
            if self.on_text_response:
                await self.on_text_response(response_text)
            
            # Generate audio response (text-to-speech)
            # For now, just send text - browser can use Web Speech API
            if self.on_audio_response:
                # Simulate audio by sending text that browser will speak
                await self.on_audio_response(f"TEXT_TO_SPEAK:{response_text}")
            
            # Clear buffer
            self.audio_buffer = []
            
        except Exception as e:
            print(f"❌ Error processing audio: {e}")
    
    async def _generate_response(self, user_input: str) -> str:
        """Generate response using Gemini"""
        try:
            # Build conversation context
            customer_info = json.dumps(self.customer_data, indent=2)
            prompt = f"""{self.system_prompt}

CUSTOMER PROFILE:
{customer_info}

CONVERSATION:
User: {user_input}

Respond naturally and empathetically (1-2 sentences):"""
            
            print(f"🔄 Calling Gemini API with model: {self.model_id}")
            
            # Generate with Gemini
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt
            )
            
            response_text = response.text
            print(f"✅ Gemini API returned: {response_text}")
            
            # Add to history
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "agent", "content": response_text})
            
            return response_text
            
        except Exception as e:
            print(f"❌ Error generating response: {e}")
            import traceback
            traceback.print_exc()
            return "I apologize, I'm having trouble processing that. Could you please repeat?"
    
    async def _trigger_churn_scoring(self, user_input: str, agent_response: str):
        """Trigger churn scoring based on conversation"""
        try:
            # Analyze the conversation to determine damage type and frustration
            damage_label = self._detect_damage_type(user_input)
            frustration_score = self._detect_frustration(user_input)
            
            # Score churn
            result = score_churn(
                customer=self.customer_data,
                damage_label=damage_label,
                frustration_score=frustration_score
            )
            
            print(f"🎯 Churn Score: {result['score']} ({result['tier']})")
            
            # Save to Firestore
            save_session_log(
                session_id=self.session_id,
                customer_id=self.customer_id,
                transcript=[{
                    "user": user_input,
                    "agent": agent_response
                }],
                churn_score=result['score'],
                offer_text=result['offer']
            )
            
            # Send offer
            if self.on_text_response:
                await self.on_text_response(f"\n💡 {result['offer']}")
            
            if self.on_tool_call:
                await self.on_tool_call({
                    "tool": "score_and_respond",
                    "result": result
                })
                
        except Exception as e:
            print(f"❌ Error in churn scoring: {e}")
    
    def _detect_damage_type(self, text: str) -> str:
        """Detect damage type from text"""
        text_lower = text.lower()
        
        if 'wrong' in text_lower or 'incorrect' in text_lower:
            return 'wrong_item'
        elif 'broken' in text_lower or 'shattered' in text_lower:
            return 'broken'
        elif 'defective' in text_lower or 'not working' in text_lower:
            return 'defective'
        elif 'damaged' in text_lower:
            return 'damaged'
        elif 'quality' in text_lower or 'cheap' in text_lower:
            return 'quality_issue'
        else:
            return 'not_as_described'
    
    def _detect_frustration(self, text: str) -> float:
        """Detect frustration level from text"""
        text_lower = text.lower()
        
        frustration_keywords = {
            'very frustrated': 9.0,
            'extremely upset': 9.0,
            'angry': 8.0,
            'frustrated': 7.0,
            'disappointed': 5.0,
            'unhappy': 5.0,
            'annoyed': 6.0
        }
        
        for keyword, score in frustration_keywords.items():
            if keyword in text_lower:
                return score
        
        return 4.0  # Default moderate frustration
    
    async def stop(self):
        """Stop the session"""
        self.is_active = False
        print(f"🛑 Session stopped: {self.session_id}")
