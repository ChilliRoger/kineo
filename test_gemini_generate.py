"""
test_gemini_generate.py
Test if standard Gemini generate_content works
"""

import asyncio
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

async def test_generate():
    """Test basic content generation"""
    
    print("\n" + "="*70)
    print("Testing Gemini generate_content")
    print("="*70)
    
    client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
    model_id = 'gemini-2.5-flash'
    
    try:
        print(f"\n1. Using model: {model_id}")
        
        prompt = """You are a friendly customer service agent. A customer says: 
"I received the wrong item in my order and I'm very frustrated."

Respond empathetically in 1-2 sentences."""
        
        print(f"\n2. Sending prompt...")
        response = await client.aio.models.generate_content(
            model=model_id,
            contents=prompt
        )
        
        print(f"\n3. ✅ Response received!")
        print(f"\n{response.text}\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_generate())
    if success:
        print("="*70)
        print("✅ SUCCESS: Gemini API is working!")
        print("="*70)
    else:
        print("="*70)
        print("❌ FAIL: Gemini API not working")
        print("="*70)
