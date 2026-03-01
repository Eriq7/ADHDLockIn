// --- services/userService.js ---
// User registration and login logic.

const { pool } = require('../config/db');

/** Characters for secret key generation (excludes confusable chars: 0/O, 1/I/L). */
const KEY_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';

/**
 * Generate a random 6-character secret key.
 * @returns {string} e.g. "A3K9M2"
 */
function generateSecretKey() {
  let key = '';
  for (let i = 0; i < 6; i++) {
    key += KEY_CHARS.charAt(Math.floor(Math.random() * KEY_CHARS.length));
  }
  return key;
}

/**
 * Validate username format: 3-50 chars, letters/numbers/underscores only.
 * @param {string} username
 * @returns {boolean}
 */
function isValidUsername(username) {
  return /^[A-Za-z0-9_]{3,50}$/.test(username);
}

/**
 * Register a new user. Generates a secret key automatically.
 * @param {string} username
 * @returns {Promise<{username: string, secretKey: string}>}
 * @throws Error with code 'USERNAME_TAKEN' or 'INVALID_USERNAME'.
 */
async function register(username) {
  if (!username || !isValidUsername(username)) {
    const err = new Error('Username must be 3-50 characters, only letters, numbers, and underscores allowed.');
    err.code = 'INVALID_USERNAME';
    throw err;
  }

  // Check if username already exists
  const existing = await pool.query(
    'SELECT id FROM users WHERE username = $1',
    [username]
  );
  if (existing.rows.length > 0) {
    const err = new Error('Username already taken. Please choose a different username.');
    err.code = 'USERNAME_TAKEN';
    throw err;
  }

  const secretKey = generateSecretKey();

  const { rows } = await pool.query(
    'INSERT INTO users (username, secret_key) VALUES ($1, $2) RETURNING username, secret_key, created_at',
    [username, secretKey]
  );

  console.log(`User registered: ${username}`);
  return { username: rows[0].username, secretKey: rows[0].secret_key };
}

/**
 * Login a user by verifying username and secret key.
 * @param {string} username
 * @param {string} secretKey
 * @returns {Promise<{userId: string, username: string, createdAt: string}>}
 * @throws Error with code 'USER_NOT_FOUND' or 'INVALID_KEY'.
 */
async function login(username, secretKey) {
  const { rows } = await pool.query(
    'SELECT username, secret_key, created_at FROM users WHERE username = $1',
    [username]
  );

  if (rows.length === 0) {
    const err = new Error('User not found. Please register first.');
    err.code = 'USER_NOT_FOUND';
    throw err;
  }

  if (rows[0].secret_key !== secretKey) {
    const err = new Error('Invalid secret key.');
    err.code = 'INVALID_KEY';
    throw err;
  }

  console.log(`User logged in: ${username}`);
  return {
    userId: rows[0].username,
    username: rows[0].username,
    createdAt: rows[0].created_at,
  };
}

/**
 * Create the users table if it doesn't exist.
 * Called on server startup.
 * @returns {Promise<void>}
 */
async function ensureUsersTable() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS users (
      id SERIAL PRIMARY KEY,
      username VARCHAR(50) UNIQUE NOT NULL,
      secret_key VARCHAR(10) NOT NULL,
      created_at TIMESTAMP DEFAULT NOW()
    );
  `);
  console.log('DB: users table ready.');
}

module.exports = { register, login, ensureUsersTable };
