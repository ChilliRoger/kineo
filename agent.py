"""
agent.py
Google ADK agent definition with Gemini Live API configuration
Defines the Kineo agent with system prompt, tools, and voice/vision streaming setup
"""

import os
import uuid
from datetime import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Import our custom tools
from tools.firestore_client import get_customer, save_session_log
from tools.churn_scorer import score_churn

# Load environment variables
load_dotenv()

# Initialize Gemini client
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

# Model configuration
MODEL_ID = 'gemini-2.0-flash-live-001'

# System prompt for Kineo agent
SYSTEM_PROMPT = """You are Kineo, a warm and empathetic customer support agent for an e-commerce platform.

Your job is to help customers who want to return a product. Ask them what went wrong, ask them to show the product if they can, and understand their frustration.

You have two tools available: get_customer and score_and_respond.

IMPORTANT WORKFLOW:
1. Always use get_customer first to load the customer profile
2. Listen to their issue and understand the damage type and frustration level
3. Then use score_and_respond once you understand the issue
4. Deliver the win-back offer naturally in conversation

Be concise, warm, and empathetic. Always end with the personalized win-back offer.
Never sound robotic. Never mention churn scores or tiers to the customer.
Speak naturally as if you're a real person who genuinely cares."""


# ═══════════════════════════════════════════════════════════
# TOOL DEFINITIONS FOR ADK
# ═══════════════════════════════════════════════════════════

def tool_get_customer(customer_id: str) -> dict:
    """
    Retrieves customer profile from Firestore.
    Call this first when starting a session to understand the customer's history.
    
    Args:
        customer_id: The unique customer identifier
        
    Returns:
        Customer profile with order history, loyalty tier, and return count
    """
    try:
        customer = get_customer(customer_id)
        return {
            "success": True,
            "customer": customer
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def tool_score_and_respond(
    customer_id: str,
    damage_label: str,
    frustration_score: float
) -> dict:
    """
    Calculates churn risk and generates personalized win-back offer.
    Call this after understanding the customer's issue.
    
    Args:
        customer_id: The unique customer identifier
        damage_label: Type of damage (wrong_item, broken, quality_issue, defective, damaged, not_as_described)
        frustration_score: Detected frustration level from 0-10 based on conversation tone
        
    Returns:
        Personalized win-back offer to present to the customer
    """
    try:
        # Get customer profile
        customer = get_customer(customer_id)
        
        # Score churn risk
        churn_result = score_churn(customer, damage_label, frustration_score)
        
        # Generate session ID
        session_id = f"session_{uuid.uuid4().hex[:12]}"
        
        # Log to Firestore
        save_session_log(
            session_id=session_id,
            customer_id=customer_id,
            damage_label=damage_label,
            frustration_score=frustration_score,
            churn_score=churn_result['score'],
            offer_given=churn_result['offer']
        )
        
        return {
            "success": True,
            "offer": churn_result['offer'],
            "session_id": session_id
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ═══════════════════════════════════════════════════════════
# TOOL DECLARATIONS FOR GEMINI
# ═══════════════════════════════════════════════════════════

get_customer_declaration = {
    "name": "get_customer",
    "description": "Retrieves customer profile from the database. Use this first when starting a session to understand the customer's order history, loyalty tier, and return behavior.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "customer_id": {
                "type": "STRING",
                "description": "The unique customer identifier (e.g., customer_001)"
            }
        },
        "required": ["customer_id"]
    }
}

score_and_respond_declaration = {
    "name": "score_and_respond",
    "description": "Calculates churn risk and generates a personalized win-back offer based on the customer's issue and frustration level. Use this after understanding what went wrong.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "customer_id": {
                "type": "STRING",
                "description": "The unique customer identifier"
            },
            "damage_label": {
                "type": "STRING",
                "description": "Type of damage or issue: wrong_item, broken, quality_issue, defective, damaged, not_as_described"
            },
            "frustration_score": {
                "type": "NUMBER",
                "description": "Customer frustration level from 0-10 based on their tone (0=calm, 5=annoyed, 10=very angry)"
            }
        },
        "required": ["customer_id", "damage_label", "frustration_score"]
    }
}


# ═══════════════════════════════════════════════════════════
# AGENT CONFIGURATION
# ═══════════════════════════════════════════════════════════

def create_agent_config():
    """
    Creates the Gemini Live API configuration for Kineo agent.
    
    Returns:
        Configuration dictionary with model and system instructions
        Note: Tools will be called manually in the FastAPI backend
    """
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],  # Agent responds with voice
        system_instruction=SYSTEM_PROMPT
    )
    
    return config


# Store tool declarations for manual calling in FastAPI
TOOL_DECLARATIONS = {
    "get_customer": get_customer_declaration,
    "score_and_respond": score_and_respond_declaration
}


def handle_tool_call(function_call):
    """
    Routes function calls from Gemini to the appropriate tool handler.
    
    Args:
        function_call: Function call object from Gemini
        
    Returns:
        Tool execution result
    """
    tool_name = function_call.name
    tool_args = function_call.args
    
    if tool_name == "get_customer":
        return tool_get_customer(**tool_args)
    elif tool_name == "score_and_respond":
        return tool_score_and_respond(**tool_args)
    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}


def initialize_agent():
    """
    Initializes the Kineo agent with Gemini Live API.
    Tests that configuration is valid and credentials are working.
    
    Returns:
        True if successful, raises exception otherwise
    """
    try:
        print("\n" + "="*70)
        print("🤖 INITIALIZING KINEO AGENT")
        print("="*70)
        
        print(f"\n✓ Model: {MODEL_ID}")
        print(f"✓ API Key: {'*' * 20}{os.getenv('GEMINI_API_KEY')[-8:]}")
        print(f"✓ Tools registered: get_customer, score_and_respond")
        
        # Test Gemini client connection
        print(f"\n🔄 Testing Gemini API connection...")
        
        # List available models to verify API key works
        models = client.models.list()
        print(f"✓ Gemini API connected successfully")
        print(f"✓ Available models: {len(list(models))} models found")
        
        # Create agent config
        config = create_agent_config()
        print(f"✓ Agent config created")
        
        print("\n" + "="*70)
        print("✅ KINEO AGENT INITIALIZED SUCCESSFULLY")
        print("="*70)
        print("\nAgent ready for live voice + vision sessions!")
        print("System: Warm, empathetic customer support")
        print("Capabilities: Voice input, video input, tool calling")
        print("\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Agent initialization failed: {str(e)}")
        raise


if __name__ == "__main__":
    """
    Run this file directly to test agent initialization:
    python agent.py
    """
    initialize_agent()

