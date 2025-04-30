# Standard Library
import logging
import os
import time
import json
from typing import Dict, List, Optional, Union, AsyncGenerator

# Third-Party Libraries
from fastapi import FastAPI, HTTPException, Request, Query, Body
from fastapi.responses import StreamingResponse
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
    stream: bool = Field(False, description="Whether to stream the response token by token")

class InferenceResponse(BaseModel):
    output_text: str
    token_usage: TokenCount
    model: str
    processing_time: float

class StreamingChunk(BaseModel):
    token: str
    is_finished: bool = False
    token_count: Optional[TokenCount] = None
    model: Optional[str] = None
    processing_time: Optional[float] = None

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

async def _generate_next_token(model, tokenizer, generated, attention_mask, past_key_values, request):
    """Helper function to generate the next token."""
    # Prepare model inputs with proper attention mask and past key values
    model_inputs = {
        "input_ids": generated[:, -1:] if past_key_values is not None else generated,
        "attention_mask": attention_mask,
    }
    
    if past_key_values is not None:
        model_inputs["past_key_values"] = past_key_values
    
    # Generate next token logits
    outputs = model(**model_inputs, use_cache=True)
    past_key_values = outputs.past_key_values
    
    # Apply temperature scaling and top-k filtering
    next_token_logits = outputs.logits[:, -1, :] / request.temperature
    
    if request.top_k > 0:
        indices_to_remove = next_token_logits < torch.topk(next_token_logits, request.top_k)[0][..., -1, None]
        next_token_logits[indices_to_remove] = -float("Inf")
    
    # Sample next token from probability distribution
    probs = torch.nn.functional.softmax(next_token_logits, dim=-1)
    next_token = torch.multinomial(probs, num_samples=1).squeeze(1)
    
    return next_token, past_key_values

async def stream_inference(request: InferenceRequest) -> AsyncGenerator[str, None]:
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
    
    # Initialize generation state
    generated = inputs["input_ids"].clone()
    past_key_values = None
    attention_mask = inputs["attention_mask"]
    completion_tokens = 0
    max_length = min(request.max_length + prompt_tokens, prompt_tokens + 100)
    
    # Generate tokens one by one to enable streaming
    with PROCESSING_TIME.labels(model=MODEL_NAME).time():
        with torch.inference_mode():
            for _ in range(max_length - prompt_tokens):
                # Generate next token using helper function
                next_token, past_key_values = await _generate_next_token(
                    model, tokenizer, generated, attention_mask, past_key_values, request
                )
                
                # Update generation state
                generated = torch.cat([generated, next_token.unsqueeze(-1)], dim=-1)
                attention_mask = torch.cat([attention_mask, attention_mask.new_ones((attention_mask.shape[0], 1))], dim=-1)
                
                # Decode and process the generated token
                token_text = tokenizer.decode([next_token[0].item()], skip_special_tokens=True)
                completion_tokens += 1
                
                # Skip empty tokens but don't stop generation
                if token_text.strip():
                    # Check if generation should stop
                    is_finished = next_token.item() == tokenizer.eos_token_id or completion_tokens >= (max_length - prompt_tokens)
                    chunk = {"token": token_text, "is_finished": is_finished}
                    
                    # Add final metadata when generation is complete
                    if is_finished:
                        total_tokens = prompt_tokens + completion_tokens
                        processing_time = time.time() - start_time
                        
                        # Update metrics
                        REQUESTS.labels(model=MODEL_NAME).inc()
                        TOKENS_PROCESSED.labels(type="prompt", model=MODEL_NAME).inc(prompt_tokens)
                        TOKENS_PROCESSED.labels(type="completion", model=MODEL_NAME).inc(completion_tokens)
                        
                        # Add final metadata to the chunk
                        chunk.update({
                            "token_count": {
                                "prompt_tokens": prompt_tokens,
                                "completion_tokens": completion_tokens,
                                "total_tokens": total_tokens
                            },
                            "model": MODEL_NAME,
                            "processing_time": processing_time
                        })
                        
                        logger.info(f"Streaming inference completed in {processing_time:.2f}s | Tokens: {total_tokens}")
                    
                    # Yield the chunk and break if generation is complete
                    yield json.dumps(chunk) + "\n"
                    
                    if is_finished:
                        break

@app.post("/inference")
async def inference(request: InferenceRequest):
    global processing_request
    start_time = time.time()
    logger.info(f"Received inference request: {request.prompt[:50]}...")
    processing_request = True
    
    try:
        # Check if streaming is requested
        if request.stream:
            logger.info("Streaming response requested")
            # Return a streaming response
            return StreamingResponse(
                stream_inference(request),
                media_type="application/x-ndjson"
            )
        else:
            # Return a regular response
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
    