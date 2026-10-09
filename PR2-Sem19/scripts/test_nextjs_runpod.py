"""Test script to call Next.js API which calls Runpod directly"""
import requests
import json
import time

# Test URL
AUDIO_URL = "https://www.oxford-hypnotherapy.co.uk/wp-content/uploads/2020/07/Relaxation_without_music.mp3"

print("="*60)
print("Testing Next.js -> Runpod Direct")
print("="*60)

# Submit job to Next.js API (v1/transcriptions endpoint for direct URLs)
print("\n[1] Submitting job to Next.js API...")
response = requests.post(
    "http://localhost:3000/api/v1/transcriptions",
    json={"url": AUDIO_URL}
)

print(f"Status: {response.status_code}")
data = response.json()
print(f"Response: {json.dumps(data, indent=2)}")

if "jobId" in data:
    job_id = data["jobId"]
    print(f"\n[2] Polling job {job_id}...")
    
    for i in range(30):
        time.sleep(2)
        status_resp = requests.get(f"http://localhost:3000/api/v1/jobs/{job_id}")
        status_data = status_resp.json()
        
        if status_data.get("status") == "completed":
            print(f"\nJob completed!")
            print(f"Result: {json.dumps(status_data.get('result', {}), indent=2)[:500]}")
            break
        elif status_data.get("status") == "failed":
            print(f"\nJob failed: {status_data.get('error')}")
            break
        else:
            print(f"  Status: {status_data.get('status')} (attempt {i+1})")
else:
    print("No jobId returned")
