"""
test_live_session.py
Test Gemini Live API with actual audio interaction
"""

import asyncio
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

async def test_live_session():
    """Test a real live session"""
    
    print("\n" + "="*70)
    print("Testing Real Gemini Live Session")
    print("="*70)
    
    client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
    model_id = 'gemini-2.5-flash-native-audio-preview-12-2025'  # Native audio model for Live API
    
    try:
        # Create config with both audio and text
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO", "TEXT"],
            system_instruction="You are a helpful assistant. Respond briefly to what the user says."
        )
        
        print("\n1. Connecting to Gemini Live API...")
        async with client.aio.live.connect(model=model_id, config=config) as session:
            print("✅ Connected!")
            
            # Send a text message first (simpler than audio)
            print("\n2. Sending text message...")
            await session.send(
                types.LiveClientContent(
                    turns=[types.Turn(
                        parts=[types.Part(text="Hello, can you hear me?")],
                        role="user"
                    )],
                    turn_complete=True
                )
            )
            print("✅ Message sent")
            
            # Receive response
            print("\n3. Waiting for response...")
            timeout = 10
            received_response = False
            
            try:
                async with asyncio.timeout(timeout):
                    async for response in session.receive():
                        print(f"\n📨 Received response: {type(response).__name__}")
                        print(f"   Response attributes: {dir(response)}")
                        
                        # Try to extract content
                        if hasattr(response, 'server_content'):
                            print(f"   ✓ Has server_content")
                            server_content = response.server_content
                            print(f"   Server content: {server_content}")
                            
                            if hasattr(server_content, 'model_turn'):
                                print(f"   ✓ Has model_turn")
                                for part in server_content.model_turn.parts:
                                    if hasattr(part, 'text'):
                                        print(f"   📝 Text: {part.text}")
                                    if hasattr(part, 'inline_data'):
                                        print(f"   🔊 Audio data: {len(part.inline_data.data)} bytes")
                            
                            if server_content.turn_complete:
                                print("   ✓ Turn complete")
                                received_response = True
                                break
                        
                        elif hasattr(response, 'tool_call'):
                            print(f"   🔧 Tool call received")
                        
                        else:
                            print(f"   ❓ Unknown response type")
                            print(f"   Content: {response}")
                            
            except asyncio.TimeoutError:
                print(f"\n⏱️ Timeout after {timeout} seconds")
            
            if received_response:
                print("\n✅ SUCCESS: Received response from Gemini!")
            else:
                print("\n❌ FAIL: No response received")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_live_session())
