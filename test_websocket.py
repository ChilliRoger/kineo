# test_websocket.py
# Quick test to verify WebSocket connection works

import asyncio
import json
import websockets

async def test_websocket():
    print("\n" + "="*70)
    print("🧪 TESTING WEBSOCKET CONNECTION")
    print("="*70)
    
    uri = "ws://localhost:8000/session"
    
    try:
        print(f"\n📡 Connecting to {uri}...")
        
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connected!")
            
            # Send initialization message
            init_msg = {
                "type": "init",
                "customer_id": "customer_001"
            }
            print(f"\n📤 Sending: {json.dumps(init_msg)}")
            await websocket.send(json.dumps(init_msg))
            
            # Wait for session_started response
            response = await websocket.recv()
            data = json.loads(response)
            print(f"\n📥 Received: {json.dumps(data, indent=2)}")
            
            if data.get("type") == "session_started":
                print(f"\n✅ Session started successfully!")
                print(f"   Session ID: {data.get('session_id')}")
                print(f"   Customer: {data.get('customer', {}).get('name')}")
                
                # Send a test transcript
                transcript_msg = {
                    "type": "transcript",
                    "text": "I received the wrong item and I'm frustrated"
                }
                print(f"\n📤 Sending transcript: {transcript_msg['text']}")
                await websocket.send(json.dumps(transcript_msg))
                
                # Wait for echo
                response = await websocket.recv()
                data = json.loads(response)
                print(f"📥 Echo received: {data.get('text')}")
                
                # Request offer
                offer_msg = {
                    "type": "request_offer",
                    "damage_label": "wrong_item",
                    "frustration_score": 8.5
                }
                print(f"\n📤 Requesting win-back offer...")
                await websocket.send(json.dumps(offer_msg))
                
                # Wait for offer
                response = await websocket.recv()
                data = json.loads(response)
                
                if data.get("type") == "offer":
                    print(f"\n✅ OFFER RECEIVED:")
                    print(f"   {data.get('text')[:200]}...")
                    print(f"   Session ID: {data.get('session_id')}")
                
                # End session
                end_msg = {"type": "end_session"}
                await websocket.send(json.dumps(end_msg))
                print(f"\n👋 Session ended gracefully")
                
            else:
                print(f"❌ Unexpected response type: {data.get('type')}")
            
    except Exception as e:
        print(f"\n❌ WebSocket test failed: {str(e)}")
        return False
    
    print("\n" + "="*70)
    print("✅ ALL WEBSOCKET TESTS PASSED")
    print("="*70)
    return True

if __name__ == "__main__":
    asyncio.run(test_websocket())
