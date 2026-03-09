"""
tools/churn_scorer.py
Dynamic rule-based churn scoring logic
Calculates churn risk based on customer profile, damage type, and frustration level
Generates personalized win-back offers based on churn tier
"""

from typing import Dict


def score_churn(
    customer: Dict,
    damage_label: str,
    frustration_score: float
) -> Dict:
    """
    Calculate churn risk score using rule-based scoring logic.
    Generates personalized win-back offers based on risk tier.
    
    Args:
        customer: Customer profile dictionary with keys:
            - name (str)
            - return_count (int)
            - loyalty_tier (str): bronze/silver/gold
            - last_order_days_ago (int)
            - total_orders (int)
            - lifetime_value (float)
        damage_label: Type of issue reported (wrong_item, broken, quality_issue, etc.)
        frustration_score: Detected frustration level from 0-10
        
    Returns:
        Dictionary with:
            - score (int): Churn risk score 0-100
            - tier (str): low/medium/high/critical
            - offer (str): Personalized win-back offer message
            
    Scoring Logic:
        - Base: 30 points
        - Damage type: +25 (wrong_item), +20 (broken), +10 (quality_issue)
        - Frustration: +15 (>7.0), +10 (>5.0)
        - Return history: +10 (>1 returns), +15 (>3 returns)
        - Loyalty: -10 (gold), -5 (silver)
        - Recency: +10 if last order >30 days ago
        - Cap at 100
    """
    # Start with base score
    score = 30
    
    # ═══════════════════════════════════════════════════════════
    # DAMAGE TYPE SCORING
    # ═══════════════════════════════════════════════════════════
    damage_scores = {
        'wrong_item': 25,
        'broken': 20,
        'quality_issue': 10,
        'defective': 15,
        'damaged': 18,
        'not_as_described': 12
    }
    score += damage_scores.get(damage_label.lower(), 5)
    
    # ═══════════════════════════════════════════════════════════
    # FRUSTRATION LEVEL SCORING
    # ═══════════════════════════════════════════════════════════
    if frustration_score > 7.0:
        score += 15
    elif frustration_score > 5.0:
        score += 10
    
    # ═══════════════════════════════════════════════════════════
    # RETURN HISTORY SCORING
    # ═══════════════════════════════════════════════════════════
    return_count = customer.get('return_count', 0)
    if return_count > 3:
        score += 15
    elif return_count > 1:
        score += 10
    
    # ═══════════════════════════════════════════════════════════
    # LOYALTY TIER ADJUSTMENT (reduces churn risk)
    # ═══════════════════════════════════════════════════════════
    loyalty_tier = customer.get('loyalty_tier', 'bronze').lower()
    if loyalty_tier == 'gold':
        score -= 10
    elif loyalty_tier == 'silver':
        score -= 5
    
    # ═══════════════════════════════════════════════════════════
    # RECENCY SCORING (dormant customers = higher risk)
    # ═══════════════════════════════════════════════════════════
    last_order_days = customer.get('last_order_days_ago', 0)
    if last_order_days > 30:
        score += 10
    
    # Cap score at 100
    score = min(100, max(0, score))
    
    # ═══════════════════════════════════════════════════════════
    # DETERMINE CHURN TIER
    # ═══════════════════════════════════════════════════════════
    if score >= 80:
        tier = 'critical'
    elif score >= 60:
        tier = 'high'
    elif score >= 40:
        tier = 'medium'
    else:
        tier = 'low'
    
    # ═══════════════════════════════════════════════════════════
    # GENERATE PERSONALIZED OFFER (fully dynamic)
    # ═══════════════════════════════════════════════════════════
    offer = _generate_offer(customer, damage_label, tier, score)
    
    return {
        'score': score,
        'tier': tier,
        'offer': offer
    }


def _generate_offer(customer: Dict, damage_label: str, tier: str, score: int) -> str:
    """
    Generate a fully personalized win-back offer based on churn tier.
    References customer name and specific damage issue dynamically.
    
    Args:
        customer: Customer profile dictionary
        damage_label: Type of damage reported
        tier: Churn risk tier (critical/high/medium/low)
        score: Calculated churn score
        
    Returns:
        Personalized offer message string
    """
    name = customer.get('name', 'valued customer').split()[0]  # First name only
    loyalty = customer.get('loyalty_tier', 'bronze').title()
    total_orders = customer.get('total_orders', 0)
    ltv = customer.get('lifetime_value', 0)
    
    # Format damage label for natural speech
    damage_descriptions = {
        'wrong_item': 'received the wrong item',
        'broken': 'received a broken product',
        'quality_issue': 'are experiencing quality issues',
        'defective': 'received a defective item',
        'damaged': 'received a damaged product',
        'not_as_described': 'product didn\'t match the description'
    }
    damage_text = damage_descriptions.get(damage_label.lower(), 'are having an issue')
    
    # ═══════════════════════════════════════════════════════════
    # CRITICAL TIER (>=80): Maximum retention effort
    # ═══════════════════════════════════════════════════════════
    if tier == 'critical':
        offer = (
            f"{name}, I'm truly sorry you {damage_text}. As a {loyalty} member "
            f"with {total_orders} orders, you're incredibly important to us. "
            f"Here's what I'd like to do immediately: I'm sending you a free replacement "
            f"with express shipping at no charge, upgrading your loyalty status for the next "
            f"6 months, and adding ${min(100, int(ltv * 0.15))} in store credit to your account. "
            f"Plus, you'll have my personal number for any future concerns. Does that work for you?"
        )
    
    # ═══════════════════════════════════════════════════════════
    # HIGH TIER (>=60): Strong retention offer
    # ═══════════════════════════════════════════════════════════
    elif tier == 'high':
        discount = 25 if loyalty == 'Gold' else 20
        offer = (
            f"{name}, I really apologize that you {damage_text}. "
            f"Let me make this right: I'm arranging priority reshipment with 2-day delivery, "
            f"completely free. I'm also adding a {discount}% discount code for your next order, "
            f"and waiving any return shipping costs. Your satisfaction means everything to us."
        )
    
    # ═══════════════════════════════════════════════════════════
    # MEDIUM TIER (>=40): Standard retention offer
    # ═══════════════════════════════════════════════════════════
    elif tier == 'medium':
        discount = 15
        offer = (
            f"{name}, I'm sorry to hear you {damage_text}. "
            f"I'd like to offer you a {discount}% discount on your next purchase, "
            f"and we'll process your return with free return shipping. "
            f"I've also flagged your account for priority handling on future orders."
        )
    
    # ═══════════════════════════════════════════════════════════
    # LOW TIER (<40): Standard resolution
    # ═══════════════════════════════════════════════════════════
    else:
        offer = (
            f"{name}, thank you for letting us know you {damage_text}. "
            f"I'll get your return processed right away with a full refund. "
            f"We'll email you a prepaid return label within the next hour. "
            f"We appreciate your business and hope to serve you better next time."
        )
    
    return offer


def test_all_scenarios():
    """
    Test churn scoring with all 3 customers and all 3 damage types.
    Displays a comprehensive matrix of results.
    """
    # Test customers (matching seeded data)
    customers = [
        {
            'customer_id': 'customer_001',
            'name': 'Sarah Chen',
            'total_orders': 24,
            'return_count': 0,
            'tenure_months': 18,
            'loyalty_tier': 'gold',
            'last_order_days_ago': 5,
            'lifetime_value': 3200.50
        },
        {
            'customer_id': 'customer_002',
            'name': 'Marcus Rodriguez',
            'total_orders': 12,
            'return_count': 2,
            'tenure_months': 8,
            'loyalty_tier': 'silver',
            'last_order_days_ago': 15,
            'lifetime_value': 890.25
        },
        {
            'customer_id': 'customer_003',
            'name': 'Emma Thompson',
            'total_orders': 1,
            'return_count': 0,
            'tenure_months': 0,
            'loyalty_tier': 'bronze',
            'last_order_days_ago': 3,
            'lifetime_value': 45.99
        }
    ]
    
    damage_types = ['wrong_item', 'broken', 'quality_issue']
    frustration_levels = [4.0, 6.5, 8.5]  # Low, medium, high
    
    print("\n" + "="*80)
    print("CHURN SCORING TEST — ALL SCENARIOS")
    print("="*80)
    
    for customer in customers:
        print(f"\n{'='*80}")
        print(f"CUSTOMER: {customer['name']} ({customer['customer_id']})")
        print(f"Profile: {customer['loyalty_tier'].upper()} | {customer['total_orders']} orders | "
              f"{customer['return_count']} returns | LTV: ${customer['lifetime_value']:.2f}")
        print(f"{'='*80}")
        
        for damage_label in damage_types:
            for frustration in frustration_levels:
                result = score_churn(customer, damage_label, frustration)
                
                print(f"\n📊 Scenario: {damage_label.upper()} | Frustration: {frustration}/10")
                print(f"   ├─ Churn Score: {result['score']}/100")
                print(f"   ├─ Risk Tier: {result['tier'].upper()}")
                print(f"   └─ Offer: {result['offer'][:120]}...")
                print()


if __name__ == "__main__":
    """
    Run this file directly to test all churn scoring scenarios:
    python tools/churn_scorer.py
    """
    test_all_scenarios()

