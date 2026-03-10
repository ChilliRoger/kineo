# test_gemini_live.py
# Test script to explore Gemini Live API capabilities

import asyncio
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

async def test_gemini_live():
    """Test Gemini Live API connection"""
    
    client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
    model_id = 'gemini-2.0-flash-live-001'
    
    print("\n" + "="*70)
    print("Testing Gemini Live API Connection")
    print("="*70)
    
    # Check available methods
    print("\n1. Client methods:")
    client_methods = [m for m in dir(client) if not m.startswith('_')]
    print(f"   Available: {', '.join(client_methods[:10])}...")
    
    # Check if we have aio (async) support
    print("\n2. Async support:")
    if hasattr(client, 'aio'):
        print(f"   ✓ client.aio available")
        aio_methods = [m for m in dir(client.aio) if not m.startswith('_')]
        print(f"   Methods: {', '.join(aio_methods[:10])}...")
    
    # Check models
    print("\n3. Available models:")
    try:
        models = list(client.models.list())
        live_models = [m for m in models if 'live' in m.name.lower() or 'multimodal' in m.name.lower()]
        if live_models:
            for model in live_models[:3]:
                print(f"   - {model.name}")
        else:
            print(f"   Total models: {len(models)}")
    except Exception as e:
        print(f"   Error listing models: {e}")
    
    # Try to create a live session
    print("\n4. Testing Live Session Creation:")
    try:
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO", "TEXT"],
        )
        print(f"   ✓ Config created: {config}")
        
        # Check if we can connect
        if hasattr(client.aio, 'live'):
            print("   ✓ client.aio.live exists")
        else:
            print("   ⚠ client.aio.live not found - checking alternatives")
            
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    asyncio.run(test_gemini_live())
