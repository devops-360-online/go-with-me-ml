const { Pool } = require('pg');
const logger = require('./logger');

/**
 * PostgreSQL connection pool for database access
 */
class Database {
  constructor() {
    this.pool = new Pool({
      connectionString: process.env.POSTGRES_DSN || 'postgresql://postgres:postgres@localhost:5432/mlservice',
      max: 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
    });

    this.pool.on('error', (err) => {
      logger.error('Unexpected error on idle database client', err);
    });

    logger.info('Database connection pool initialized');
  }

  /**
   * Get a client from the pool for transaction usage
   * @returns {Promise<import('pg').PoolClient>} A client from the connection pool
   */
  async getClient() {
    return this.pool.connect();
  }

  /**
   * Query the database
   * @param {string} text - SQL query text
   * @param {Array} params - Query parameters
   * @returns {Promise<import('pg').QueryResult>} Query result
   */
  async query(text, params) {
    const start = Date.now();
    try {
      const res = await this.pool.query(text, params);
      const duration = Date.now() - start;
      logger.debug('Executed query', { text, duration, rows: res.rowCount });
      return res;
    } catch (err) {
      logger.error('Error executing query', { text, error: err.message });
      throw err;
    }
  }

  /**
   * Get a request by ID
   * @param {string} requestId - The request ID to retrieve
   * @returns {Promise<Object>} The request data
   */
  async getRequest(requestId) {
    const query = `
      SELECT id, user_id, status, prompt, result, model, max_tokens, tokens_used, 
             created_at, completed_at
      FROM requests
      WHERE id = $1
    `;
    const { rows } = await this.query(query, [requestId]);
    return rows[0];
  }

  /**
   * Get all requests for a user
   * @param {string} userId - The user ID
   * @param {number} limit - Maximum number of requests to return
   * @param {number} offset - Number of requests to skip
   * @returns {Promise<Array>} Array of request objects
   */
  async getUserRequests(userId, limit = 10, offset = 0) {
    const query = `
      SELECT id, status, prompt, model, tokens_used, created_at, completed_at
      FROM requests
      WHERE user_id = $1
      ORDER BY created_at DESC
      LIMIT $2 OFFSET $3
    `;
    const { rows } = await this.query(query, [userId, limit, offset]);
    return rows;
  }

  /**
   * Get quota usage for a user
   * @param {string} userId - The user ID
   * @returns {Promise<Object>} Quota usage information
   */
  async getQuotaUsage(userId) {
    const query = `
      SELECT 
        user_id,
        request_count,
        token_count,
        period_start,
        period_end
      FROM quota_usage
      WHERE user_id = $1
        AND period_start <= NOW()
        AND period_end >= NOW()
    `;
    const { rows } = await this.query(query, [userId]);
    return rows[0] || { user_id: userId, request_count: 0, token_count: 0 };
  }

  /**
   * Get token usage for a user within a specific time period
   * @param {string} userId - The user ID
   * @param {Date} startDate - Start date for the query
   * @param {Date} endDate - End date for the query
   * @returns {Promise<Object>} Token usage information
   */
  async getTokenUsage(userId, startDate, endDate) {
    const query = `
      SELECT 
        user_id,
        SUM(tokens_used) as total_tokens
      FROM token_logs
      WHERE user_id = $1
        AND created_at >= $2
        AND created_at <= $3
      GROUP BY user_id
    `;
    const { rows } = await this.query(query, [userId, startDate, endDate]);
    return rows[0] || { user_id: userId, total_tokens: 0 };
  }
}

module.exports = new Database();
