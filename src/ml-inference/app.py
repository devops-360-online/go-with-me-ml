from fastapi import FastAPI, HTTPException, Request
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from pydantic import BaseModel
import os
import logging
import time
from prometheus_client import Counter, Histogram, start_http_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Start Prometheus metrics server
start_http_server(8000)

# Define Prometheus metrics
REQUESTS = Counter('ml_requests_total', 'Total number of requests processed', ['model'])
TOKENS_PROCESSED = Counter('ml_tokens_processed_total', 'Total number of tokens processed', ['type', 'model'])
PROCESSING_TIME = Histogram('ml_processing_seconds', 'Time spent processing requests', ['model'])

app = FastAPI(title="ML Inference Service")

# Load model based on environment variable or use default
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt2")
logger.info(f"Loading model: {MODEL_NAME}")

try:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)
    logger.info(f"Model {MODEL_NAME} loaded successfully")
except Exception as e:
    logger.error(f"Error loading model: {e}")
    raise

class InferenceRequest(BaseModel):
    prompt: str
    max_length: int = 100
    temperature: float = 0.7
    top_p: float = 0.9
    requestId: str = None
    userId: str = None

class TokenCount(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class InferenceResponse(BaseModel):
    output_text: str
    token_usage: TokenCount
    model: str
    processing_time: float

@app.get("/health")
async def health_check():
    return {"status": "healthy", "model": MODEL_NAME}

@app.post("/run")
async def run_inference(request: InferenceRequest):
    start_time = time.time()
    
    try:
        logger.info(f"Processing request: {request.requestId} for user: {request.userId}")
        
        # Encode the prompt to get token count
        input_ids = tokenizer.encode(request.prompt, return_tensors='pt')
        prompt_tokens = len(input_ids[0])
        
        # Generate text
        with PROCESSING_TIME.labels(model=MODEL_NAME).time():
            outputs = model.generate(
                input_ids,
                max_length=request.max_length,
                temperature=request.temperature,
                top_p=request.top_p,
                do_sample=True
            )
        
        # Decode the generated text
        generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Calculate completion tokens (total - prompt)
        completion_tokens = len(outputs[0]) - prompt_tokens
        total_tokens = prompt_tokens + completion_tokens
        
        # Update metrics
        REQUESTS.labels(model=MODEL_NAME).inc()
        TOKENS_PROCESSED.labels(type="prompt", model=MODEL_NAME).inc(prompt_tokens)
        TOKENS_PROCESSED.labels(type="completion", model=MODEL_NAME).inc(completion_tokens)
        
        processing_time = time.time() - start_time
        logger.info(f"Request {request.requestId} processed in {processing_time:.2f}s, {total_tokens} tokens")
        
        return InferenceResponse(
            output_text=generated_text,
            token_usage=TokenCount(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            ),
            model=MODEL_NAME,
            processing_time=processing_time
        )
    
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"Request processed in {process_time:.2f}s")
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
