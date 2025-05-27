import requests
import json

def stream_inference(prompt, max_length=50):
    url = "http://localhost:8080/api/gateway"  # Change to your service URL
    payload = {
        "prompt": prompt,
        "stream": False,
        "user_id":"7"
    }
    
    # Make a streaming request
    response = requests.post(url, json=payload, stream=True)
    

    
    # Process the streaming response
    for line in response.iter_lines():
        if line:
            chunk = json.loads(line)
            token = chunk.get("token", "")
            is_finished = chunk.get("is_finished", False)
            
            # Print token as it arrives
            print(token, end="", flush=True)
            
            # If this is the final token, print stats
            if is_finished and "token_count" in chunk:
                print("\n\n--- Stats ---")
                print(f"Tokens: {chunk['token_count']}")
                print(f"Time: {chunk['processing_time']:.2f}s")
                break

if __name__ == "__main__":
    prompt = input("Enter your prompt: ")
    stream_inference(prompt)