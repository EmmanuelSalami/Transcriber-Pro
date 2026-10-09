import httpx
import json
import sys
import time

# Get API key from environment
API_KEY = "transcription-api-key-2024"

print("=" * 60)
print("Testing Oxford Hypnotherapy MP3 URL")
print("=" * 60)

headers = {"Authorization": f"Bearer {API_KEY}"}

# First test health
print("\n[1] Testing health endpoint...")
try:
    r = httpx.get("http://localhost:8000/health", headers=headers, timeout=10.0)
    print(f"    Status: {r.status_code}")
    if r.status_code == 200:
        health_data = r.json()
        print(f"    Response: {json.dumps(health_data, indent=4)}")
    else:
        print(f"    Error: {r.text}")
except Exception as e:
    print(f"    ERROR: {e}")
    import traceback
    traceback.print_exc()

# Now test media transcription with form data
print("\n[2] Testing media transcription (multipart/form-data)...")
url = "http://localhost:8000/v1/transcriptions/media"
media_url = "https://www.oxford-hypnotherapy.co.uk/wp-content/uploads/2020/07/Relaxation_without_music.mp3"

# Use multipart/form-data instead of JSON
form_data = {
    "url": media_url,
    "language": "en"
}

print(f"    Endpoint: {url}")
print(f"    Media URL: {media_url}")

try:
    response = httpx.post(url, data=form_data, headers=headers, timeout=300.0)
    print(f"\n    Response Status: {response.status_code}")
    
    try:
        data = response.json()
        print(f"    Response Body:")
        print(json.dumps(data, indent=4))
        
        # Check if job was created
        if "jobId" in data:
            job_id = data["jobId"]
            print(f"\n    ✓ Job created: {job_id}")
            
            # Poll job status until completed or failed
            print(f"\n[3] Polling job status (this may take 1-2 minutes)...")
            status_url = f"http://localhost:8000/v1/jobs/{job_id}"
            
            for i in range(60):  # Poll for up to 2 minutes
                time.sleep(2)
                status_response = httpx.get(status_url, headers=headers, timeout=10.0)
                status_data = status_response.json()
                current_status = status_data.get('status')
                
                if i % 5 == 0:  # Print every 10 seconds
                    print(f"    [{i*2}s] Status: {current_status}")
                
                if current_status in ['completed', 'failed']:
                    print(f"\n    Final Status: {current_status}")
                    print(f"    Full Response: {json.dumps(status_data, indent=4)}")
                    break
            else:
                print("\n    Timeout waiting for job completion")
            
    except Exception as e:
        print(f"    Raw Response: {response.text}")
        print(f"    Error parsing JSON: {e}")
        
except Exception as e:
    print(f"    ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)
