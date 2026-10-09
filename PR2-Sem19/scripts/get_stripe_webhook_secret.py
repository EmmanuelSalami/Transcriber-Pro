#!/usr/bin/env python3
"""
Run stripe listen briefly to capture the webhook signing secret.
Updates PR2-Sem19/.env with the new STRIPE_WEBHOOK_SECRET.

NOTE: For Stripe LIVE mode, the CLI only accepts restricted keys from `stripe login`.
Run `stripe listen --live --forward-to localhost:8000/v1/credits/webhook` manually
and copy the whsec_... from the output. This script works for TEST mode only.
"""
import os
import re
import subprocess
import sys

try:
    from dotenv import load_dotenv
    from pathlib import Path
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path, override=True)
except ImportError:
    pass

def main():
    api_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not api_key or len(api_key) < 20:
        print("ERROR: STRIPE_SECRET_KEY not set or invalid in .env")
        sys.exit(1)

    proc = subprocess.Popen(
        [
            "stripe", "listen",
            "--api-key", api_key,
            "--forward-to", "localhost:8000/v1/credits/webhook",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )

    secret = None
    for line in proc.stdout:
        line = line.strip()
        m = re.search(r"whsec_[a-zA-Z0-9]+", line)
        if m:
            secret = m.group(0)
            break

    proc.terminate()
    proc.wait(timeout=5)

    if not secret:
        print("ERROR: Could not capture webhook secret from stripe listen output")
        sys.exit(1)

    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()

    if re.search(r"STRIPE_WEBHOOK_SECRET=whsec_", content):
        content = re.sub(r"STRIPE_WEBHOOK_SECRET=whsec_[a-zA-Z0-9]+", f"STRIPE_WEBHOOK_SECRET={secret}", content)
    else:
        content = content.rstrip() + f"\nSTRIPE_WEBHOOK_SECRET={secret}\n"

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Updated .env with STRIPE_WEBHOOK_SECRET={secret[:20]}...")
    print("Run 'stripe listen --api-key $STRIPE_SECRET_KEY --forward-to localhost:8000/v1/credits/webhook' in a separate terminal for live testing.")

if __name__ == "__main__":
    main()
