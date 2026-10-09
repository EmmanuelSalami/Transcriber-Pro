#!/usr/bin/env python3
"""
Create Stripe product, price, coupon, and FREETEST promotion code.
Uses STRIPE_SECRET_KEY from environment. Run from project root with .env loaded.

  cd PR2-Sem19 && python scripts/setup_stripe.py

Or: set STRIPE_SECRET_KEY=sk_test_... and run.
"""
import os
import sys

# Load .env if python-dotenv available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def main():
    api_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not api_key:
        print("ERROR: STRIPE_SECRET_KEY not set.")
        print("Get your key from https://dashboard.stripe.com/test/apikeys")
        print("Add to .env: STRIPE_SECRET_KEY=sk_test_...")
        sys.exit(1)

    import stripe
    stripe.api_key = api_key

    # 1. Create product
    product = stripe.Product.create(
        name="Transcription Credits",
        description="250 minutes of transcription",
    )
    print(f"Product: {product.id}")

    # 2. Create price (£5 = 500 pence)
    price = stripe.Price.create(
        product=product.id,
        currency="gbp",
        unit_amount=500,
    )
    print(f"Price: {price.id}")

    # 3. Create 100% off coupon
    coupon = stripe.Coupon.create(
        percent_off=100,
        duration="once",
    )
    print(f"Coupon: {coupon.id}")

    # 4. Create FREETEST promotion code
    promo = stripe.PromotionCode.create(
        coupon=coupon.id,
        code="FREETEST",
    )
    print(f"Promo: {promo.id} (code=FREETEST)")

    print("\n--- Add to .env ---")
    print(f"STRIPE_PRICE_ID={price.id}")
    print("\nDone. Use FREETEST at checkout for 100% off (250 min credited).")

if __name__ == "__main__":
    main()
