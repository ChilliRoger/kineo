"""
tools/firestore_client.py
All Firestore database operations for Kineo
Handles customer profile reads, session logging, and test data seeding
"""

import os
from datetime import datetime
from typing import Dict, Optional
from google.cloud import firestore
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Firestore client
db = firestore.Client(
    project=os.getenv("GCP_PROJECT_ID"),
    database="(default)"
)

# Collection names from environment
CUSTOMERS_COLLECTION = os.getenv("FIRESTORE_COLLECTION_CUSTOMERS", "kineo_customers")
SESSIONS_COLLECTION = os.getenv("FIRESTORE_COLLECTION_SESSIONS", "kineo_sessions")


def get_customer(customer_id: str) -> Dict:
    """
    Reads a customer document from Firestore.
    
    Args:
        customer_id: Unique customer identifier
        
    Returns:
        Dictionary containing customer profile data:
        - customer_id: str
        - name: str
        - total_orders: int
        - return_count: int
        - tenure_months: int
        - loyalty_tier: str (bronze/silver/gold)
        - last_order_days_ago: int
        
    Raises:
        ValueError: If customer not found
    """
    try:
        doc_ref = db.collection(CUSTOMERS_COLLECTION).document(customer_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise ValueError(f"Customer {customer_id} not found in Firestore")
        
        customer_data = doc.to_dict()
        customer_data['customer_id'] = customer_id
        
        print(f"✅ Retrieved customer: {customer_data['name']} ({customer_id})")
        return customer_data
        
    except Exception as e:
        print(f"❌ Error retrieving customer {customer_id}: {str(e)}")
        raise


def save_session_log(
    session_id: str,
    customer_id: str,
    damage_label: str = "unknown", 
    frustration_score: float = 0.0, 
    churn_score: float = 0.0, 
    offer_given: str = "", 
    transcript: list = None, 
    **kwargs
) -> None:
    """
    Writes a complete session record to Firestore after each interaction ends.
    
    Args:
        session_id: Unique session identifier
        customer_id: Customer who had the interaction
        damage_label: Type of damage (wrong_item, broken, quality_issue, etc.)
        frustration_score: Detected frustration level (0-10)
        churn_score: Calculated churn risk score (0-100)
        offer_given: The win-back offer that was presented
        transcript: List of message objects
    """
    try:
        session_data = {
            'session_id': session_id,
            'customer_id': customer_id,
            'damage_label': damage_label,
            'frustration_score': frustration_score,
            'churn_score': churn_score,
            'offer_given': offer_given,
            'transcript': transcript or [],
            'timestamp': firestore.SERVER_TIMESTAMP,
            'created_at': datetime.utcnow().isoformat()
        }
        
        # Merge any extra kwargs
        session_data.update(kwargs)
        
        doc_ref = db.collection(SESSIONS_COLLECTION).document(session_id)
        doc_ref.set(session_data)
        
        print(f"✅ Session log saved: {session_id} (Customer: {customer_id}, Churn: {churn_score})")
        
    except Exception as e:
        print(f"❌ Error saving session log {session_id}: {str(e)}")
        raise


def seed_test_customers() -> None:
    """
    Seeds 3 realistic test customer profiles into Firestore.
    Creates diverse customer scenarios for testing churn scoring:
    - Customer A: Loyal, high LTV, first return (should get best offers)
    - Customer B: Mid-tier, 2 previous returns (moderate risk)
    - Customer C: New customer, first order, first return (high churn risk)
    """
    test_customers = [
        {
            'customer_id': 'customer_001',
            'name': 'Sarah Chen',
            'email': 'sarah.chen@example.com',
            'total_orders': 24,
            'return_count': 0,  # First return ever
            'tenure_months': 18,
            'loyalty_tier': 'gold',
            'last_order_days_ago': 5,
            'lifetime_value': 3200.50,
            'description': 'Loyal customer, high LTV, first return - should receive premium retention offer'
        },
        {
            'customer_id': 'customer_002',
            'name': 'Marcus Rodriguez',
            'email': 'marcus.rodriguez@example.com',
            'total_orders': 12,
            'return_count': 2,  # Has returned before
            'tenure_months': 8,
            'loyalty_tier': 'silver',
            'last_order_days_ago': 15,
            'lifetime_value': 890.25,
            'description': 'Mid-tier customer, 2 previous returns - moderate churn risk'
        },
        {
            'customer_id': 'customer_003',
            'name': 'Emma Thompson',
            'email': 'emma.thompson@example.com',
            'total_orders': 1,
            'return_count': 0,  # First order and first return
            'tenure_months': 0,  # Brand new
            'loyalty_tier': 'bronze',
            'last_order_days_ago': 3,
            'lifetime_value': 45.99,
            'description': 'New customer, first order, first return - critical churn risk'
        }
    ]
    
    print("\n" + "="*60)
    print("SEEDING TEST CUSTOMERS TO FIRESTORE")
    print("="*60)
    
    for customer in test_customers:
        try:
            customer_id = customer['customer_id']
            doc_ref = db.collection(CUSTOMERS_COLLECTION).document(customer_id)
            doc_ref.set(customer)
            
            print(f"\n✅ Created: {customer['name']} ({customer_id})")
            print(f"   Loyalty: {customer['loyalty_tier'].upper()}")
            print(f"   Orders: {customer['total_orders']} | Returns: {customer['return_count']}")
            print(f"   Tenure: {customer['tenure_months']} months | LTV: ${customer['lifetime_value']:.2f}")
            print(f"   Scenario: {customer['description']}")
            
        except Exception as e:
            print(f"\n❌ Error creating customer {customer['customer_id']}: {str(e)}")
            raise
    
    print("\n" + "="*60)
    print("✅ ALL TEST CUSTOMERS SEEDED SUCCESSFULLY")
    print("="*60)
    
    # Verify by reading back
    print("\n🔍 VERIFICATION - Reading back from Firestore:")
    for customer in test_customers:
        retrieved = get_customer(customer['customer_id'])
        assert retrieved['name'] == customer['name'], f"Mismatch for {customer['customer_id']}"
    
    print("\n✅ Verification complete - all customers readable from Firestore\n")


def list_all_customers() -> list:
    """
    Lists all customers in the database.
    Useful for debugging and verification.
    
    Returns:
        List of customer dictionaries
    """
    try:
        docs = db.collection(CUSTOMERS_COLLECTION).stream()
        customers = []
        
        for doc in docs:
            customer = doc.to_dict()
            customer['customer_id'] = doc.id
            customers.append(customer)
        
        return customers
        
    except Exception as e:
        print(f"❌ Error listing customers: {str(e)}")
        return []


if __name__ == "__main__":
    """
    Run this file directly to seed test customers:
    python tools/firestore_client.py
    """
    print("\n🚀 Kineo Firestore Client - Test Data Seeder\n")
    seed_test_customers()

