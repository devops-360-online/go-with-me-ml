/**
 * Utility for estimating token counts for different models
 */

// For simplicity, we're using a rough estimation based on characters
// In production, you would use a proper tokenizer like tiktoken
function estimateTokensSimple(text) {
  if (!text) return 0;
  // Rough estimate: 1 token ≈ 4 characters for English text
  return Math.ceil(text.length / 4);
}

// More accurate estimation using tiktoken (if available)
let tiktoken;
try {
  tiktoken = require('tiktoken');
} catch (error) {
  console.warn('tiktoken not available, using simple token estimation');
}

/**
 * Estimate the number of tokens in a text string
 * @param {string} text - The text to estimate tokens for
 * @param {string} model - The model to use for estimation (default: gpt-3.5-turbo)
 * @returns {number} - Estimated token count
 */
function estimateTokens(text, model = 'gpt-3.5-turbo') {
  if (!text) return 0;
  
  // If tiktoken is available, use it for more accurate estimation
  if (tiktoken) {
    try {
      const encoding = tiktoken.encoding_for_model(model);
      return encoding.encode(text).length;
    } catch (error) {
      console.warn(`Error using tiktoken: ${error.message}`);
      // Fall back to simple estimation
      return estimateTokensSimple(text);
    }
  }
  
  // Fall back to simple estimation
  return estimateTokensSimple(text);
}

module.exports = {
  estimateTokens,
  estimateTokensSimple
}; 