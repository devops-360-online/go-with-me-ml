#!/usr/bin/env python3
"""
Step 2: SSE Client
Shows how to consume the SSE endpoints we created
"""

import requests
import json
import sys
import time
from typing import Optional

# Install with: pip install sseclient-py
try:
    import sseclient
except ImportError:
    print("❌ sseclient-py not installed. Install with: pip3 install sseclient-py")
    sys.exit(1)

class SSEMLClient:
    def __init__(self, api_url: str = "http://localhost:8080", sse_url: str = "http://localhost:8081"):
        """
        api_url: Your API Gateway (submits requests)
        sse_url: Your ML Service with SSE (receives notifications) - usually same as API in production
        """
        self.api_url = api_url
        self.sse_url = sse_url
        self.session = requests.Session()
    
    def submit_request(self, prompt: str, user_id: str = "test-user") -> dict:
        """
        Step 1: Submit request to API Gateway
        This would normally go to your /api/gateway endpoint
        """
        url = f"{self.api_url}/api/gateway"
        
        payload = {
            "prompt": prompt,
            "user_id": "5",
            "max_length": 100,
            "temperature": 0.7
        }
        
        print(f"🚀 Submitting request: {prompt[:30]}...")
        
        try:
            response = self.session.post(url, json=payload, timeout=30)
            
            # Handle new API Gateway response format
            if response.status_code == 200:
                result = response.json()
                
                # Check if request was successful
                if result.get("success", False):
                    request_id = result.get("request_id")
                    print(f"✅ Request submitted! ID: {request_id}")
                    print(f"📡 SSE endpoint: {result.get('sse_endpoint', 'unknown')}")
                    return result
                else:
                    # Handle quota exceeded or other errors
                    error_msg = result.get("message", "Unknown error")
                    print(f"❌ Request failed: {error_msg}")
                    return {"error": "request_failed", "message": error_msg}
                    
            elif response.status_code == 429:
                # Quota exceeded
                result = response.json()
                print(f"❌ Quota exceeded: {result.get('message', 'Rate limit reached')}")
                return {"error": "quota_exceeded", "message": result.get('message')}
                
            else:
                print(f"❌ Request failed: {response.status_code}")
                try:
                    error_detail = response.json()
                    return {"error": "request_failed", "status_code": response.status_code, "detail": error_detail}
                except:
                    return {"error": "request_failed", "status_code": response.status_code}
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error: {e}")
            return {"error": "network_error"}
    
    def wait_for_result_sse(self, request_id: str, timeout: int = 300) -> dict:
        """
        Step 2: Connect to SSE endpoint and wait for results
        This connects to /events/{request_id}
        """
        sse_endpoint = f"{self.sse_url}/events/{request_id}"
        print(f"📡 Connecting to SSE: {sse_endpoint}")
        
        try:
            # Connect to SSE stream
            response = self.session.get(
                sse_endpoint,
                headers={"Accept": "text/event-stream", "Cache-Control": "no-cache"},
                stream=True,
                timeout=timeout
            )
            
            if response.status_code != 200:
                print(f"❌ SSE connection failed: {response.status_code}")
                return {"error": "sse_connection_failed"}
            
            print("🔗 SSE connected, waiting for result...")
            
            # Process SSE events
            client = sseclient.SSEClient(response)
            
            for event in client.events():
                try:
                    event_data = json.loads(event.data)
                    print(event_data.get("result"))
                    event_type = event_data.get("type", "unknown")
                    
                    print(f"📨 Received: {event_type}")
                    
                    if event_type == "connected":
                        print("✅ SSE connection confirmed")
                        continue
                        
                    elif event_type == "ping":
                        print("💓 Keepalive ping")
                        continue
                        
                    elif event_type == "completed":
                        print("🎉 Result received!")
                        return {
                            "status": "completed",
                            "result": event_data.get("result"),
                            "token_usage": event_data.get("token_usage", {}),
                            "request_id": event_data.get("request_id")
                        }
                        
                    elif event_type == "failed":
                        print("❌ Request failed")
                        return {
                            "status": "failed",
                            "error": event_data.get("error"),
                            "request_id": event_data.get("request_id")
                        }
                        
                except json.JSONDecodeError as e:
                    print(f"⚠️ Invalid JSON in event: {e}")
                    continue
                except Exception as e:
                    print(f"⚠️ Error processing event: {e}")
                    continue
            
            return {"error": "sse_stream_ended"}
            
        except requests.exceptions.Timeout:
            return {"error": "timeout", "message": f"Timeout after {timeout} seconds"}
        except requests.exceptions.RequestException as e:
            return {"error": "sse_connection_error", "message": str(e)}
    
    def submit_and_wait(self, prompt: str, user_id: str = "test-user") -> dict:
        """
        Complete flow: Submit request + wait for result via SSE
        """
        # Step 1: Submit request
        submit_result = self.submit_request(prompt, user_id)
        
        if "error" in submit_result:
            return submit_result
        
        request_id = submit_result.get("request_id")
        if not request_id:
            return {"error": "no_request_id"}
        
        # Step 2: Wait for result via SSE
        return self.wait_for_result_sse(request_id)

def test_with_simulation():
    """
    Test the SSE client using the simulation endpoint
    (when your full ML pipeline isn't ready yet)
    """
    print("🧪 Testing SSE Client with Simulation")
    print("=" * 40)
    
    client = SSEMLClient(
        api_url="http://localhost:8080",    # API Gateway (not ready yet)
        sse_url="http://localhost:8081"     # SSE Service (ready!)
    )
    
    # Simulate a request ID (normally comes from API Gateway)
    fake_request_id = f"test_{int(time.time())}"
    print(f"🔮 Using simulated request ID: {fake_request_id}")
    
    # Step 1: Start SSE connection (in background)
    import threading
    result_container = {}
    
    def wait_for_result():
        result = client.wait_for_result_sse(fake_request_id, timeout=60)
        result_container['result'] = result
    
    sse_thread = threading.Thread(target=wait_for_result)
    sse_thread.start()
    
    # Give SSE time to connect
    time.sleep(2)
    
    # Step 2: Simulate notification (like Results Collector would do)
    simulate_url = f"{client.sse_url}/simulate"
    simulate_params = {
        "request_id": fake_request_id,
        "result": "Hello from SSE! This would be your ML result."
    }
    
    print(f"📤 Sending simulated notification...")
    response = requests.post(simulate_url, params=simulate_params)
    print(f"Simulation response: {response.json()}")
    
    # Wait for SSE to receive the result
    sse_thread.join(timeout=10)
    
    if 'result' in result_container:
        result = result_container['result']
        if "error" not in result:
            print(f"🎉 SUCCESS! Received: {result['result']}")
            print(f"📊 Token usage: {result.get('token_usage', {})}")
        else:
            print(f"❌ Error: {result['error']}")
    else:
        print("⏰ Timeout - no result received")

def main():
    """Main function - shows different usage patterns"""
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Test mode - use simulation
        test_with_simulation()
        return
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 sse_client.py test                    # Test with simulation")
        print("  python3 sse_client.py \"Your prompt here\"     # Real request (when ready)")
        return
    
    prompt = " ".join(sys.argv[1:])
    
    print("🎯 SSE ML Client")
    print("=" * 30)
    
    # Real usage (when your API Gateway is ready)
    client = SSEMLClient()
    result = client.submit_and_wait(prompt)
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
    else:
        print(f"📄 Result: {result.get('result', 'No result')}")
        token_usage = result.get('token_usage', {})
        if token_usage:
            print(f"🔢 Tokens: {token_usage.get('total_tokens', 0)}")

if __name__ == "__main__":
    main() 