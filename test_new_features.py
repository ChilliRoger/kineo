"""
test_new_features.py
Test script for new backend features: webhooks, orders, and multi-language support
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_order_endpoints():
    """Test order management endpoints"""
    print("\n" + "="*70)
    print("TESTING ORDER ENDPOINTS")
    print("="*70)
    
    # Test 1: Get customer orders
    print("\n1. Get orders for customer cust_sarah_001:")
    response = requests.get(f"{BASE_URL}/orders/customer/cust_sarah_001")
    data = response.json()
    print(f"   Status: {response.status_code}")
    print(f"   Found {data['count']} orders")
    if data['orders']:
        for order in data['orders'][:2]:  # Show first 2
            print(f"   - {order.get('order_id', 'N/A')}: {order.get('product_name', 'N/A')} ({order.get('status', 'N/A')})")
    
    # Test 2: Get specific order
    if data['orders']:
        order_id = data['orders'][0]['id']
        print(f"\n2. Get specific order {order_id}:")
        response = requests.get(f"{BASE_URL}/orders/{order_id}")
        order_data = response.json()
        print(f"   Status: {response.status_code}")
        if order_data['success']:
            print(f"   Product: {order_data['order']['product_name']}")
            print(f"   Status: {order_data['order']['status']}")
            print(f"   Price: ${order_data['order']['price']}")


def test_webhook():
    """Test webhook endpoint"""
    print("\n" + "="*70)
    print("TESTING WEBHOOK ENDPOINT")
    print("="*70)
    
    # Test webhook for order shipped
    print("\n1. Testing 'order.shipped' webhook:")
    webhook_payload = {
        "event_type": "order.shipped",
        "order_id": "ORD-2024-001",
        "tracking_number": "1Z999AA10123456789",
        "notes": "Your order has been shipped!"
    }
    
    response = requests.post(f"{BASE_URL}/webhook/order-update", json=webhook_payload)
    data = response.json()
    print(f"   Status: {response.status_code}")
    print(f"   Success: {data.get('success', False)}")
    print(f"   Message: {data.get('message', 'N/A')}")
    
    # Test webhook for replacement shipped
    print("\n2. Testing 'replacement.shipped' webhook:")
    webhook_payload = {
        "event_type": "replacement.shipped",
        "order_id": "ORD-2024-001",
        "tracking_number": "1Z999AA10123456790",
        "notes": "Your replacement is on the way!"
    }
    
    response = requests.post(f"{BASE_URL}/webhook/order-update", json=webhook_payload)
    data = response.json()
    print(f"   Status: {response.status_code}")
    print(f"   Success: {data.get('success', False)}")
    print(f"   Message: {data.get('message', 'N/A')}")


def test_language_detection():
    """Test multi-language support (manual test instructions)"""
    print("\n" + "="*70)
    print("TESTING MULTI-LANGUAGE SUPPORT")
    print("="*70)
    
    print("\nLanguage detection is now enabled in the agent!")
    print("To test, open http://localhost:8000 and try these messages:")
    print()
    print("🇺🇸 ENGLISH:")
    print("   'My product is broken'")
    print()
    print("🇪🇸 SPANISH:")
    print("   'Mi producto está roto'")
    print("   'Hola, necesito ayuda con mi pedido'")
    print()
    print("🇫🇷 FRENCH:")
    print("   'Mon produit est cassé'")
    print("   'Bonjour, j'ai un problème avec ma commande'")
    print()
    print("🇩🇪 GERMAN:")
    print("   'Mein Produkt ist kaputt'")
    print("   'Hallo, ich habe ein Problem mit meiner Bestellung'")
    print()
    print("🇵🇹 PORTUGUESE:")
    print("   'Meu produto está quebrado'")
    print("   'Olá, preciso de ajuda com meu pedido'")
    print()
    print("The agent will detect the language and respond accordingly!")


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("KINEO BACKEND FEATURES TEST SUITE")
    print("="*70)
    
    try:
        # Check if server is running
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            print("\n❌ Server is not running on http://localhost:8000")
            print("Please start the server with: python main.py")
            return
        
        print(f"\n✅ Server is running (Model: {response.json()['model']})")
        
        # Run tests
        test_order_endpoints()
        test_webhook()
        test_language_detection()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS COMPLETED")
        print("="*70)
        print()
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to server")
        print("Please start the server with: python main.py")
    except Exception as e:
        print(f"\n❌ Test error: {e}")


if __name__ == "__main__":
    main()
