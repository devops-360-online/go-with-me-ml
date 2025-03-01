const { Pool } = require('pg');
const winston = require('winston');
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
    new winston.transports.File({ filename: 'db.log' })
  ]
});

// Create a PostgreSQL connection pool
const pool = new Pool({
  connectionString: process.env.POSTGRES_DSN || 'postgresql://postgres:postgres@localhost:5432/mlservice',
  max: 20, // Maximum number of clients in the pool
  idleTimeoutMillis: 30000, // How long a client is allowed to remain idle before being closed
  connectionTimeoutMillis: 2000, // How long to wait for a connection
});

// Test the connection
pool.query('SELECT NOW()', (err, res) => {
  if (err) {
    logger.error('Error connecting to PostgreSQL:', err);
  } else {
    logger.info('Connected to PostgreSQL at:', res.rows[0].now);
  }
});

// Handle pool errors
pool.on('error', (err) => {
  logger.error('Unexpected error on idle client', err);
  process.exit(-1);
});

module.exports = pool;
