"""
list_live_models.py
List available models that support Live API
"""

import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

def list_models():
    """List all available models"""
    
    print("\n" + "="*70)
    print("Listing Available Gemini Models")
    print("="*70)
    
    client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
    
    print("\nAll available models:\n")
    try:
        models = list(client.models.list())
        print(f"Total models: {len(models)}\n")
        
        for model in models:
            # Check the model name
            print(f"📦 {model.name}")
            
            # Check if it's a live/multimodal model
            if hasattr(model, 'supported_generation_methods'):
                methods = model.supported_generation_methods
                if 'generateContent' in methods or 'streamGenerateContent' in methods:
                    print(f"   Methods: {methods}")
            
            # Look for keywords
            name_lower = model.name.lower()
            if any(keyword in name_lower for keyword in ['live', '2.0', 'multimodal', 'flash']):
                print(f"   ⭐ POSSIBLE LIVE MODEL")
            
            print()
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    list_models()
