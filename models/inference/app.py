# Standard Library
import logging
import os
import time
import json
from typing import Dict, List, Optional, Union

# Third-Party Libraries
from fastapi import FastAPI, HTTPException, Request, Query, Body
from pydantic import BaseModel, Field
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
from prometheus_client import Counter, Histogram, start_http_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="ML Inference Service", description="API for ML model inference")

# Start Prometheus metrics server
start_http_server(8000)

# Define Prometheus metrics
REQUESTS = Counter('ml_requests_total', 'Total number of requests processed', ['model'])
TOKENS_PROCESSED = Counter('ml_tokens_processed_total', 'Total number of tokens processed', ['type', 'model'])
PROCESSING_TIME = Histogram('ml_processing_seconds', 'Time spent processing requests', ['model'])

# Global state trackers
model_loaded = False
processing_request = False

# Load model based on environment variable
MODEL_NAME = os.environ.get("MODEL_NAME", "distilgpt2")
logger.info(f"Loading model: {MODEL_NAME}")

# Determine the best available device for Mac optimization
# MPS (Metal Performance Shaders) is Apple's GPU acceleration framework
if torch.backends.mps.is_available():
    device = torch.device("mps")
    logger.info("Using MPS (Metal) for Mac acceleration")
elif torch.cuda.is_available():
    device = torch.device("cuda")
    logger.info("Using CUDA GPU acceleration")
else:
    device = torch.device("cpu")
    logger.info("Using CPU for inference")

try:
    # Load tokenizer with proper configuration
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    
    # Configure tokenizer for generation - required for proper text generation
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"

    # Model loading configuration optimized for Mac M-series
    # Different settings for different device types
    load_kwargs = {
        "low_cpu_mem_usage": True,  # Reduces memory usage during model loading
    }
    
    # Choose appropriate precision based on device
    # Lower precision (fp16) uses less memory but may reduce accuracy slightly
    if device.type != "cpu":
        load_kwargs["torch_dtype"] = torch.float16  # Half precision for GPU/MPS
    else:
        load_kwargs["torch_dtype"] = torch.float32  # Full precision for CPU
    
    # Load the model without device_map="auto" which can cause issues on Mac
    logger.info(f"Loading model with settings: {load_kwargs}")
    model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, **load_kwargs)
    
    # Explicitly move model to the detected device
    model = model.to(device)
    
    # Set model to evaluation mode for inference
    model.eval()
    logger.info(f"Model {MODEL_NAME} loaded successfully on {device}")
    model_loaded = True

except Exception as e:
    logger.error(f"Error loading model: {e}")
    import traceback
    logger.error(traceback.format_exc())
    raise HTTPException(status_code=500, detail=f"Model loading failed: {e}")

# Pydantic models for request/response validation
class TokenCount(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class InferenceRequest(BaseModel):
    prompt: str
    max_length: int = Field(100, ge=10, le=500, description="Maximum length of generated text")
    temperature: float = Field(0.7, ge=0.1, le=2.0, description="Controls randomness")
    top_p: float = Field(0.9, ge=0.1, le=1.0, description="Nucleus sampling parameter")
    top_k: int = Field(50, ge=0, le=1000, description="Top-k sampling parameter")
    repetition_penalty: float = Field(1.2, ge=0.5, le=2.0, description="Penalty for repeating tokens")
    num_return_sequences: int = Field(1, ge=1, le=5, description="Number of sequences to generate")

class InferenceResponse(BaseModel):
    output_text: str
    token_usage: TokenCount
    model: str
    processing_time: float

# API Endpoints
@app.get("/health")
async def health_check():
    # Fast health check that doesn't depend on model processing
    # This always responds quickly for Kubernetes probes
    return {
        "status": "healthy", 
        "model": MODEL_NAME, 
        "device": str(device),
        "model_loaded": model_loaded,
        "processing_request": processing_request
    }

# Separate function to do the actual inference
async def run_inference(request: InferenceRequest):
    start_time = time.time()
    
    # Tokenize input with proper attention mask
    inputs = tokenizer(
        request.prompt,
        return_tensors="pt",
        return_attention_mask=True,
        padding=True
    )
    
    # Move inputs to the device where the model is
    inputs = {k: v.to(device) for k, v in inputs.items()}

    prompt_tokens = inputs["input_ids"].shape[-1]
    
    # Generation parameters - optimized for speed
    gen_kwargs = {
        "input_ids": inputs["input_ids"],
        "attention_mask": inputs["attention_mask"],
        "max_length": min(request.max_length, 100),  # Reduced for speed
        "temperature": request.temperature,
        "top_p": request.top_p,
        "top_k": request.top_k,
        "repetition_penalty": request.repetition_penalty,
        "num_return_sequences": 1,  # Stick to 1 sequence
        "do_sample": True,
        "pad_token_id": tokenizer.eos_token_id,
        "eos_token_id": tokenizer.eos_token_id
    }

    # Generate text with timing
    with PROCESSING_TIME.labels(model=MODEL_NAME).time():
        # inference_mode is more memory efficient than no_grad for PyTorch inference
        with torch.inference_mode():
            outputs = model.generate(**gen_kwargs)

    # Decode generated text, skipping the input tokens
    output_text = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[-1]:], 
        skip_special_tokens=True
    )

    # Calculate token usage
    completion_tokens = len(outputs[0]) - prompt_tokens
    total_tokens = prompt_tokens + completion_tokens

    # Update metrics
    REQUESTS.labels(model=MODEL_NAME).inc()
    TOKENS_PROCESSED.labels(type="prompt", model=MODEL_NAME).inc(prompt_tokens)
    TOKENS_PROCESSED.labels(type="completion", model=MODEL_NAME).inc(completion_tokens)

    # Calculate processing time
    processing_time = time.time() - start_time
    logger.info(f"Inference completed in {processing_time:.2f}s | Tokens: {total_tokens}")

    return InferenceResponse(
        output_text=output_text,
        token_usage=TokenCount(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens
        ),
        model=MODEL_NAME,
        processing_time=processing_time
    )

@app.post("/inference", response_model=InferenceResponse)
async def inference(request: InferenceRequest):
    global processing_request
    start_time = time.time()
    logger.info(f"Received inference request: {request.prompt[:50]}...")
    processing_request = True
    
    try:
        # Run the actual inference in a separate function
        return await run_inference(request)
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        processing_request = False

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - {response.status_code} ({process_time:.2f}s)")
    return response

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server on port 8080...")
    uvicorn.run(app, host="0.0.0.0", port=8080)
    