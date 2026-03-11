"""
order_service.py
Order management and webhook handling for Kineo
Tracks order status, shipments, and sends real-time updates
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from google.cloud import firestore

# Handle imports for both module and script execution
try:
    from tools.firestore_client import db
except ModuleNotFoundError:
    from firestore_client import db

# Firestore collections
ORDERS_COLLECTION = "kineo_orders"
ORDER_UPDATES_COLLECTION = "kineo_order_updates"


class OrderStatus:
    """Order status constants"""
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    RETURN_REQUESTED = "return_requested"
    RETURN_APPROVED = "return_approved"
    REPLACEMENT_SHIPPED = "replacement_shipped"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class OrderService:
    """Service for managing orders and updates"""
    
    def __init__(self):
        self.db = db
        self.orders_ref = db.collection(ORDERS_COLLECTION)
        self.updates_ref = db.collection(ORDER_UPDATES_COLLECTION)
    
    def get_order(self, order_id: str) -> Optional[Dict]:
        """
        Retrieve order by ID
        
        Args:
            order_id: Order identifier
            
        Returns:
            Order data or None if not found
        """
        try:
            doc = self.orders_ref.document(order_id).get()
            if doc.exists:
                return {"id": doc.id, **doc.to_dict()}
            return None
        except Exception as e:
            print(f"❌ Error fetching order {order_id}: {e}")
            return None
    
    def get_customer_orders(self, customer_id: str, limit: int = 10) -> List[Dict]:
        """
        Get all orders for a customer
        
        Args:
            customer_id: Customer identifier
            limit: Maximum number of orders to return
            
        Returns:
            List of order dictionaries
        """
        try:
            # Simple query without ordering to avoid index requirement
            docs = (self.orders_ref
                   .where("customer_id", "==", customer_id)
                   .limit(limit)
                   .stream())
            
            orders = []
            for doc in docs:
                orders.append({"id": doc.id, **doc.to_dict()})
            
            # Sort in Python instead of Firestore
            orders.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
            return orders
        except Exception as e:
            print(f"❌ Error fetching orders for customer {customer_id}: {e}")
            return []
    
    def create_order(self, order_data: Dict) -> Optional[str]:
        """
        Create a new order
        
        Args:
            order_data: Order information
            
        Returns:
            Order ID or None if failed
        """
        try:
            # Add timestamp
            order_data["created_at"] = datetime.now(timezone.utc).isoformat()
            order_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            # Set default status
            if "status" not in order_data:
                order_data["status"] = OrderStatus.PENDING
            
            # Create document
            doc_ref = self.orders_ref.document()
            doc_ref.set(order_data)
            
            print(f"✅ Created order: {doc_ref.id}")
            return doc_ref.id
            
        except Exception as e:
            print(f"❌ Error creating order: {e}")
            return None
    
    def update_order_status(
        self, 
        order_id: str, 
        new_status: str, 
        notes: Optional[str] = None,
        tracking_number: Optional[str] = None
    ) -> bool:
        """
        Update order status and create update record
        
        Args:
            order_id: Order identifier
            new_status: New order status
            notes: Optional notes about the update
            tracking_number: Optional tracking number for shipments
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update order document
            update_data = {
                "status": new_status,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            if tracking_number:
                update_data["tracking_number"] = tracking_number
            
            self.orders_ref.document(order_id).update(update_data)
            
            # Create update record
            update_record = {
                "order_id": order_id,
                "status": new_status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "notes": notes or "",
                "tracking_number": tracking_number or ""
            }
            
            self.updates_ref.add(update_record)
            
            print(f"✅ Updated order {order_id} to status: {new_status}")
            return True
            
        except Exception as e:
            print(f"❌ Error updating order {order_id}: {e}")
            return False
    
    def process_webhook(self, webhook_data: Dict) -> Dict:
        """
        Process incoming webhook from order management system
        
        Args:
            webhook_data: Webhook payload
            
        Returns:
            Processing result with status
        """
        try:
            event_type = webhook_data.get("event_type")
            order_id = webhook_data.get("order_id")
            
            if not order_id:
                return {"success": False, "message": "Missing order_id"}
            
            # Handle different webhook event types
            if event_type == "order.shipped":
                success = self.update_order_status(
                    order_id,
                    OrderStatus.SHIPPED,
                    notes=webhook_data.get("notes", "Order shipped"),
                    tracking_number=webhook_data.get("tracking_number")
                )
                
            elif event_type == "order.delivered":
                success = self.update_order_status(
                    order_id,
                    OrderStatus.DELIVERED,
                    notes=webhook_data.get("notes", "Order delivered")
                )
                
            elif event_type == "replacement.shipped":
                success = self.update_order_status(
                    order_id,
                    OrderStatus.REPLACEMENT_SHIPPED,
                    notes=webhook_data.get("notes", "Replacement shipped"),
                    tracking_number=webhook_data.get("tracking_number")
                )
                
            elif event_type == "return.approved":
                success = self.update_order_status(
                    order_id,
                    OrderStatus.RETURN_APPROVED,
                    notes=webhook_data.get("notes", "Return approved")
                )
                
            else:
                return {"success": False, "message": f"Unknown event type: {event_type}"}
            
            if success:
                # Get order details to return customer_id for notification
                order = self.get_order(order_id)
                return {
                    "success": True,
                    "message": f"Processed {event_type}",
                    "order_id": order_id,
                    "customer_id": order.get("customer_id") if order else None,
                    "new_status": webhook_data.get("status", "unknown")
                }
            else:
                return {"success": False, "message": "Failed to update order"}
                
        except Exception as e:
            print(f"❌ Error processing webhook: {e}")
            return {"success": False, "message": str(e)}
    
    def get_order_updates(self, order_id: str) -> List[Dict]:
        """
        Get all status updates for an order
        
        Args:
            order_id: Order identifier
            
        Returns:
            List of update records
        """
        try:
            # Simple query without ordering to avoid index requirement
            docs = (self.updates_ref
                   .where("order_id", "==", order_id)
                   .stream())
            
            updates = []
            for doc in docs:
                updates.append({"id": doc.id, **doc.to_dict()})
            
            # Sort in Python instead of Firestore
            updates.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            return updates
            
        except Exception as e:
            print(f"❌ Error fetching updates for order {order_id}: {e}")
            return []


# Global service instance
order_service = OrderService()


def seed_test_orders():
    """Seed test orders for demo purposes"""
    
    test_orders = [
        {
            "order_id": "ORD-2024-001",
            "customer_id": "cust_sarah_001",
            "product_name": "Premium Wireless Headphones",
            "product_sku": "WH-XB910N",
            "quantity": 1,
            "price": 149.99,
            "status": OrderStatus.RETURN_REQUESTED,
            "order_date": "2024-02-15T10:30:00Z",
            "tracking_number": "1Z999AA10123456784",
            "return_reason": "Product arrived damaged"
        },
        {
            "order_id": "ORD-2024-002",
            "customer_id": "cust_sarah_001",
            "product_name": "Smart Watch Series 5",
            "product_sku": "SW-SERIES5-BLK",
            "quantity": 1,
            "price": 399.99,
            "status": OrderStatus.DELIVERED,
            "order_date": "2024-01-10T14:20:00Z",
            "tracking_number": "1Z999AA10123456785"
        },
        {
            "order_id": "ORD-2024-003",
            "customer_id": "cust_marcus_002",
            "product_name": "Portable Bluetooth Speaker",
            "product_sku": "SPK-FLIP6-RED",
            "quantity": 2,
            "price": 129.99,
            "status": OrderStatus.SHIPPED,
            "order_date": "2024-03-05T09:15:00Z",
            "tracking_number": "1Z999AA10123456786"
        },
        {
            "order_id": "ORD-2024-004",
            "customer_id": "cust_emma_003",
            "product_name": "4K Webcam",
            "product_sku": "CAM-4K-PRO",
            "quantity": 1,
            "price": 89.99,
            "status": OrderStatus.RETURN_APPROVED,
            "order_date": "2024-02-28T16:45:00Z",
            "return_reason": "Received wrong item"
        }
    ]
    
    print("\n🌱 Seeding test orders...")
    for order in test_orders:
        order_id = order_service.create_order(order)
        if order_id:
            print(f"   ✅ Created order: {order['order_id']} for {order['customer_id']}")
    
    print("✅ Order seeding complete!\n")


if __name__ == "__main__":
    # Test the service
    print("Testing Order Service...")
    seed_test_orders()
    
    # Test retrieval
    print("\n📦 Testing order retrieval...")
    orders = order_service.get_customer_orders("cust_sarah_001")
    print(f"Found {len(orders)} orders for Sarah")
    for order in orders:
        print(f"   - {order['order_id']}: {order['product_name']} ({order['status']})")
