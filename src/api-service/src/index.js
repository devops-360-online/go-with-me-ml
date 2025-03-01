const express = require('express');
const { v4: uuidv4 } = require('uuid');
const amqp = require('amqplib');
const pool = require('./db');
const redis = require('redis');
const winston = require('winston');
const { estimateTokens } = require('./utils/tokenizer');
const rateLimit = require('express-rate-limit');
require('dotenv').config();

// Configure logger
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: 'api-service.log' })
  ]
});

// Initialize Redis client
const redisClient = redis.createClient({
  url: process.env.REDIS_URL || 'redis://localhost:6379'
});

(async () => {
  await redisClient.connect();
  logger.info('Connected to Redis');
})().catch(err => {
  logger.error('Redis connection error:', err);
  process.exit(1);
});

const app = express();
app.use(express.json());

// Basic rate limiter to prevent abuse
const apiLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
  standardHeaders: true,
  message: { error: 'Too many requests, please try again later.' }
});

app.use(apiLimiter);

// Middleware to extract user ID from request
const extractUserId = (req, res, next) => {
  const apiKey = req.headers['x-api-key'];
  if (!apiKey) {
    return res.status(401).json({ error: 'API key is required' });
  }
  
  // In a real app, you would validate the API key against a database
  // For now, we'll use the API key as the user ID
  req.userId = apiKey;
  next();
};

// Check user quota middleware
const checkQuota = async (req, res, next) => {
  const { userId } = req;
  
  try {
    // Check request quota
    const requestsUsed = await redisClient.get(`user:${userId}:quota:daily:requests:used`);
    const requestsLimit = await redisClient.get(`user:${userId}:quota:daily:requests:limit`) || 100;
    
    if (requestsUsed && parseInt(requestsUsed) >= parseInt(requestsLimit)) {
      return res.status(429).json({ 
        error: 'Request quota exceeded',
        limit: requestsLimit,
        used: requestsUsed
      });
    }
    
    // Check token quota
    const tokensUsed = await redisClient.get(`user:${userId}:quota:daily:tokens:used`);
    const tokensLimit = await redisClient.get(`user:${userId}:quota:daily:tokens:limit`) || 10000;
    
    // Estimate tokens for this request
    const { prompt } = req.body;
    const estimatedTokens = estimateTokens(prompt);
    
    if (tokensUsed && parseInt(tokensUsed) + estimatedTokens > parseInt(tokensLimit)) {
      return res.status(429).json({ 
        error: 'Token quota exceeded',
        limit: tokensLimit,
        used: tokensUsed,
        estimated: estimatedTokens
      });
    }
    
    // Store estimated tokens for this request
    req.estimatedTokens = estimatedTokens;
    next();
  } catch (error) {
    logger.error('Error checking quota:', error);
    next(); // Continue even if quota check fails
  }
};

// Update quota after request is processed
const updateQuota = async (userId, estimatedTokens) => {
  try {
    // Increment request count
    await redisClient.incr(`user:${userId}:quota:daily:requests:used`);
    
    // Reserve estimated tokens
    await redisClient.incrBy(`user:${userId}:quota:daily:tokens:used`, estimatedTokens);
    
    logger.info(`Updated quota for user ${userId}: +1 request, +${estimatedTokens} tokens`);
  } catch (error) {
    logger.error('Error updating quota:', error);
  }
};

app.post('/generate', extractUserId, checkQuota, async (req, res) => {
  const { prompt } = req.body;
  const { userId, estimatedTokens } = req;
  
  if (!prompt) return res.status(400).json({ error: "Missing prompt" });

  try {
    const requestId = uuidv4();
    
    // Store request in database
    await pool.query(
      'INSERT INTO requests (request_id, user_id, prompt, status, estimated_tokens) VALUES ($1, $2, $3, $4, $5)', 
      [requestId, userId, prompt, 'queued', estimatedTokens]
    );

    // Update quota
    await updateQuota(userId, estimatedTokens);

    // Send to RabbitMQ
    const conn = await amqp.connect(process.env.RABBITMQ_URL || 'amqp://localhost');
    const channel = await conn.createChannel();
    await channel.assertQueue('inference_requests', { durable: true });
    
    channel.sendToQueue('inference_requests', Buffer.from(JSON.stringify({ 
      requestId, 
      userId,
      prompt,
      estimatedTokens,
      timestamp: new Date().toISOString()
    })));
    
    await channel.close();
    await conn.close();

    logger.info(`Request ${requestId} queued for user ${userId}`);
    res.json({ requestId, status: 'queued', estimatedTokens });
  } catch (error) {
    logger.error('Error processing request:', error);
    res.status(500).json({ error: "Internal server error" });
  }
});

app.get('/status', extractUserId, async (req, res) => {
  const { requestId } = req.query;
  const { userId } = req;
  
  if (!requestId) return res.status(400).json({ error: "Missing requestId" });
  
  try {
    const result = await pool.query(
      'SELECT result, status, prompt_tokens, completion_tokens, total_tokens FROM requests WHERE request_id = $1 AND user_id = $2', 
      [requestId, userId]
    );
    
    if (result.rowCount === 0) return res.status(404).json({ status: 'not_found' });

    const row = result.rows[0];
    if (row.status === 'queued' || row.result === null) {
      return res.json({ status: 'processing' });
    }

    return res.json({ 
      status: 'done', 
      output: row.result,
      tokens: {
        prompt: row.prompt_tokens,
        completion: row.completion_tokens,
        total: row.total_tokens
      }
    });
  } catch (error) {
    logger.error('Error checking status:', error);
    res.status(500).json({ error: "Internal server error" });
  }
});

// Endpoint to check quota
app.get('/quota', extractUserId, async (req, res) => {
  const { userId } = req;
  
  try {
    const requestsUsed = await redisClient.get(`user:${userId}:quota:daily:requests:used`) || 0;
    const requestsLimit = await redisClient.get(`user:${userId}:quota:daily:requests:limit`) || 100;
    const tokensUsed = await redisClient.get(`user:${userId}:quota:daily:tokens:used`) || 0;
    const tokensLimit = await redisClient.get(`user:${userId}:quota:daily:tokens:limit`) || 10000;
    
    res.json({
      requests: {
        used: parseInt(requestsUsed),
        limit: parseInt(requestsLimit),
        remaining: Math.max(0, parseInt(requestsLimit) - parseInt(requestsUsed))
      },
      tokens: {
        used: parseInt(tokensUsed),
        limit: parseInt(tokensLimit),
        remaining: Math.max(0, parseInt(tokensLimit) - parseInt(tokensUsed))
      }
    });
  } catch (error) {
    logger.error('Error checking quota:', error);
    res.status(500).json({ error: "Internal server error" });
  }
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

const port = process.env.PORT || 8080;
app.listen(port, () => {
  logger.info(`API service running on port ${port}`);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  logger.info('SIGTERM signal received: closing HTTP server');
  await redisClient.quit();
  process.exit(0);
});
