// --- config/db.js ---
// PostgreSQL connection pool and Redis client configuration.

const { Pool } = require('pg');
const redis = require('redis');

// PostgreSQL connection pool
const pool = new Pool({
  host: process.env.DB_HOST,
  port: parseInt(process.env.DB_PORT, 10),
  database: process.env.DB_NAME,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

pool.on('error', (err) => {
  console.error('PostgreSQL pool error:', err.message);
});

// Redis client
let redisClient = null;
let redisAvailable = false;

/**
 * Initialize the Redis client connection.
 * If Redis is unavailable, the app continues without cache.
 * @returns {Promise<void>}
 */
async function initRedis() {
  try {
    redisClient = redis.createClient({
      socket: {
        host: process.env.REDIS_HOST || 'localhost',
        port: parseInt(process.env.REDIS_PORT, 10) || 6379,
      },
    });

    redisClient.on('error', (err) => {
      console.error('Redis client error:', err.message);
      redisAvailable = false;
    });

    await redisClient.connect();
    redisAvailable = true;
    console.log('Redis: connected successfully.');
  } catch (err) {
    console.warn(`Redis Warning: unavailable (${err.message}). Continuing without cache.`);
    redisAvailable = false;
  }
}

/**
 * Get the Redis client instance.
 * @returns {{ client: object|null, available: boolean }}
 */
function getRedis() {
  return { client: redisClient, available: redisAvailable };
}

module.exports = { pool, initRedis, getRedis };
