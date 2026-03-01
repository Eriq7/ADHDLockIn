// --- services/sessionService.js ---
// Session CRUD operations against PostgreSQL.

const { pool } = require('../config/db');

/**
 * Insert a new session record into the sessions table.
 * @param {Object} session - Session data.
 * @param {string} session.userId
 * @param {string} session.startTime - ISO 8601 timestamp.
 * @param {string} session.endTime - ISO 8601 timestamp.
 * @param {number} session.duration - Duration in seconds.
 * @param {boolean} session.completed
 * @param {number} session.intervalSelected - The arm chosen (e.g. 210).
 * @param {string} [session.contextKey]
 * @param {string} [session.timeOfDay]
 * @param {string} [session.sessionDepth]
 * @param {number} [session.roundNumber]
 * @returns {Promise<Object>} The inserted session row.
 */
async function createSession(session) {
  const {
    userId,
    startTime,
    endTime,
    duration,
    completed,
    intervalSelected,
    contextKey,
    timeOfDay,
    sessionDepth,
    roundNumber,
  } = session;

  const durationMinutes = Math.round((duration / 60) * 100) / 100;
  const startDate = new Date(startTime);
  const date = startDate.toISOString().split('T')[0];
  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const dayOfWeek = days[startDate.getUTCDay()];

  const { rows } = await pool.query(
    `INSERT INTO sessions
       (user_id, start_time, end_time, duration_seconds, duration_minutes,
        completed, interval_selected, context_key, time_of_day,
        session_depth, round_number, date, day_of_week)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
     RETURNING id, user_id, start_time, end_time, duration_seconds,
               completed, interval_selected, context_key, created_at`,
    [
      userId, startTime, endTime, duration, durationMinutes,
      completed, intervalSelected, contextKey, timeOfDay,
      sessionDepth, roundNumber, date, dayOfWeek,
    ]
  );

  console.log(`Session created: id=${rows[0].id}, user=${userId}, duration=${duration}s, completed=${completed}`);
  return rows[0];
}

/**
 * Get sessions for a user with optional pagination and date filtering.
 * @param {string} userId
 * @param {Object} [options]
 * @param {number} [options.limit=100]
 * @param {number} [options.offset=0]
 * @param {string} [options.startDate] - ISO date string (YYYY-MM-DD).
 * @param {string} [options.endDate] - ISO date string (YYYY-MM-DD).
 * @returns {Promise<{sessions: Array, total: number}>}
 */
async function getSessionsByUser(userId, options = {}) {
  const { limit = 100, offset = 0, startDate, endDate } = options;

  let whereClause = 'WHERE user_id = $1';
  const queryParams = [userId];
  let paramIndex = 2;

  if (startDate) {
    whereClause += ` AND date >= $${paramIndex}`;
    queryParams.push(startDate);
    paramIndex++;
  }
  if (endDate) {
    whereClause += ` AND date <= $${paramIndex}`;
    queryParams.push(endDate);
    paramIndex++;
  }

  // Get total count
  const countResult = await pool.query(
    `SELECT COUNT(*) AS total FROM sessions ${whereClause}`,
    queryParams
  );
  const total = parseInt(countResult.rows[0].total, 10);

  // Get paginated results
  const dataParams = [...queryParams, limit, offset];
  const { rows } = await pool.query(
    `SELECT id, user_id, start_time, end_time, duration_seconds AS duration,
            completed, interval_selected, context_key, time_of_day,
            session_depth, round_number, created_at
     FROM sessions
     ${whereClause}
     ORDER BY start_time DESC
     LIMIT $${paramIndex} OFFSET $${paramIndex + 1}`,
    dataParams
  );

  return { sessions: rows, total };
}

module.exports = { createSession, getSessionsByUser };
