// --- services/banditService.js ---
// Bandit parameter read/write (Redis + PostgreSQL) and Thompson Sampling.

const jStat = require('jstat');
const { pool, getRedis } = require('../config/db');

/** The 6 interval arms in seconds. */
const ARMS = [180, 210, 240, 270, 300, 330];

/** Redis key TTL in seconds (1 hour). */
const CACHE_TTL = 3600;

/** Population cache TTL in seconds (30 minutes). */
const POPULATION_CACHE_TTL = 1800;

/**
 * Build default bandit params for all 12 contexts.
 * @returns {Object} Default params with alpha=1, beta=1 for every arm in every context.
 */
function defaultParams() {
  const timeSlots = ['morning', 'afternoon', 'evening', 'night'];
  const depths = ['early', 'mid', 'deep'];
  const params = {};
  for (const t of timeSlots) {
    for (const d of depths) {
      const ctx = `${t}_${d}`;
      params[ctx] = {};
      for (const arm of ARMS) {
        params[ctx][String(arm)] = { alpha: 1, beta: 1 };
      }
    }
  }
  return params;
}

/**
 * Load bandit params from Redis cache.
 * @param {string} userId
 * @returns {Promise<Object|null>} Parsed params or null.
 */
async function loadFromCache(userId) {
  const { client, available } = getRedis();
  if (!available || !client) return null;
  try {
    const data = await client.get(`bandit:${userId}`);
    if (data) {
      console.log(`Cache HIT: bandit:${userId}`);
      return JSON.parse(data);
    }
    console.log(`Cache MISS: bandit:${userId}`);
    return null;
  } catch (err) {
    console.warn(`Cache Warning: failed to load bandit:${userId}: ${err.message}`);
    return null;
  }
}

/**
 * Save bandit params to Redis cache with TTL.
 * @param {string} userId
 * @param {Object} params
 * @param {number} [ttl=3600] TTL in seconds.
 * @returns {Promise<void>}
 */
async function saveToCache(userId, params, ttl = CACHE_TTL) {
  const { client, available } = getRedis();
  if (!available || !client) return;
  try {
    await client.setEx(`bandit:${userId}`, ttl, JSON.stringify(params));
  } catch (err) {
    console.warn(`Cache Warning: failed to save bandit:${userId}: ${err.message}`);
  }
}

/**
 * Load bandit params from PostgreSQL.
 * @param {string} userId
 * @returns {Promise<Object|null>} Params object or null if no rows found.
 */
async function loadFromDB(userId) {
  const { rows } = await pool.query(
    'SELECT context_key, arm, alpha, beta FROM bandit_params WHERE user_id = $1',
    [userId]
  );
  if (rows.length === 0) return null;

  const params = {};
  for (const row of rows) {
    if (!params[row.context_key]) {
      params[row.context_key] = {};
    }
    params[row.context_key][String(row.arm)] = {
      alpha: row.alpha,
      beta: row.beta,
    };
  }
  return params;
}

/**
 * Save bandit params to PostgreSQL using upsert.
 * @param {string} userId
 * @param {Object} params - Full bandit params object.
 * @returns {Promise<void>}
 */
async function saveToDB(userId, params) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    for (const [contextKey, arms] of Object.entries(params)) {
      for (const [armStr, values] of Object.entries(arms)) {
        await client.query(
          `INSERT INTO bandit_params (user_id, context_key, arm, alpha, beta, updated_at)
           VALUES ($1, $2, $3, $4, $5, NOW())
           ON CONFLICT (user_id, context_key, arm) DO UPDATE
           SET alpha = EXCLUDED.alpha, beta = EXCLUDED.beta, updated_at = EXCLUDED.updated_at`,
          [userId, contextKey, parseInt(armStr, 10), values.alpha, values.beta]
        );
      }
    }
    await client.query('COMMIT');
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

/**
 * Load bandit params with Redis → PostgreSQL → defaults fallback chain.
 * @param {string} userId
 * @returns {Promise<Object>} Bandit params object.
 */
async function loadParams(userId) {
  // 1. Try Redis
  let params = await loadFromCache(userId);
  if (params) return params;

  // 2. Try PostgreSQL
  params = await loadFromDB(userId);
  if (params) {
    await saveToCache(userId, params);
    return params;
  }

  // 3. Defaults
  return defaultParams();
}

/**
 * Update bandit params after a session: alpha+1 if completed, beta+1 if not.
 * Writes to both PostgreSQL and Redis.
 * @param {string} userId
 * @param {string} contextKey - e.g. "morning_early"
 * @param {number} arm - The interval arm (e.g. 210)
 * @param {boolean} completed - Whether the session was completed.
 * @returns {Promise<Object>} Updated params for the context.
 */
async function updateReward(userId, contextKey, arm, completed) {
  const params = await loadParams(userId);

  // Ensure context exists
  if (!params[contextKey]) {
    params[contextKey] = {};
    for (const a of ARMS) {
      params[contextKey][String(a)] = { alpha: 1, beta: 1 };
    }
  }

  const armKey = String(arm);
  if (!params[contextKey][armKey]) {
    params[contextKey][armKey] = { alpha: 1, beta: 1 };
  }

  if (completed) {
    params[contextKey][armKey].alpha += 1;
  } else {
    params[contextKey][armKey].beta += 1;
  }

  // Write back to PostgreSQL and Redis
  await saveToDB(userId, params);
  await saveToCache(userId, params);

  console.log(
    `Bandit update: user=${userId}, ctx=${contextKey}, arm=${arm}, ` +
    `completed=${completed}, alpha=${params[contextKey][armKey].alpha}, beta=${params[contextKey][armKey].beta}`
  );

  return params;
}

/**
 * Perform Thompson Sampling on a set of arms.
 * Each arm has alpha/beta parameters for a Beta distribution.
 * @param {Object} armsParams - { "180": {alpha, beta}, "210": {alpha, beta}, ... }
 * @returns {Array<{arm: number, score: number, alpha: number, beta: number}>} Sorted by score descending.
 */
function thompsonSample(armsParams) {
  const results = [];
  for (const [armStr, { alpha, beta }] of Object.entries(armsParams)) {
    const score = jStat.beta.sample(alpha, beta);
    results.push({
      arm: parseInt(armStr, 10),
      score: Math.round(score * 100) / 100,
      alpha,
      beta,
    });
  }
  results.sort((a, b) => b.score - a.score);
  return results;
}

/**
 * Load aggregated population-level bandit params across all users.
 * Sums alpha and beta for each (context_key, arm) pair.
 * @returns {Promise<{params: Object, totalUsers: number}>}
 */
async function loadPopulationParams() {
  // Check cache first
  const cached = await loadFromCache('population');
  if (cached) {
    return { params: cached.params, totalUsers: cached.totalUsers };
  }

  // Query aggregated data from PostgreSQL
  const { rows } = await pool.query(
    `SELECT context_key, arm, SUM(alpha) AS total_alpha, SUM(beta) AS total_beta
     FROM bandit_params
     GROUP BY context_key, arm
     ORDER BY context_key, arm`
  );

  // Count distinct users
  const countResult = await pool.query(
    'SELECT COUNT(DISTINCT user_id) AS total FROM bandit_params'
  );
  const totalUsers = parseInt(countResult.rows[0].total, 10) || 0;

  if (rows.length === 0) {
    return { params: defaultParams(), totalUsers: 0 };
  }

  const params = {};
  for (const row of rows) {
    if (!params[row.context_key]) {
      params[row.context_key] = {};
    }
    params[row.context_key][String(row.arm)] = {
      alpha: parseInt(row.total_alpha, 10),
      beta: parseInt(row.total_beta, 10),
    };
  }

  // Cache for 30 minutes
  await saveToCache('population', { params, totalUsers }, POPULATION_CACHE_TTL);

  return { params, totalUsers };
}

module.exports = {
  ARMS,
  loadParams,
  updateReward,
  thompsonSample,
  loadPopulationParams,
  defaultParams,
};
