// --- routes/sessions.js ---
// Routes for /api/sessions endpoints.

const express = require('express');
const router = express.Router();
const sessionService = require('../services/sessionService');
const banditService = require('../services/banditService');

/**
 * POST /api/sessions
 * Create a new session record and update bandit params.
 */
router.post('/', async (req, res, next) => {
  try {
    const {
      userId, startTime, endTime, duration, completed,
      intervalSelected, contextKey, timeOfDay, sessionDepth, roundNumber,
    } = req.body;

    // Validate required fields
    if (!userId) {
      return res.status(400).json({ success: false, error: 'Missing required field: userId' });
    }
    if (duration == null) {
      return res.status(400).json({ success: false, error: 'Missing required field: duration' });
    }
    if (intervalSelected == null) {
      return res.status(400).json({ success: false, error: 'Missing required field: intervalSelected' });
    }

    // Insert session into PostgreSQL
    const session = await sessionService.createSession({
      userId,
      startTime: startTime || new Date().toISOString(),
      endTime: endTime || new Date().toISOString(),
      duration,
      completed: completed != null ? completed : true,
      intervalSelected,
      contextKey,
      timeOfDay,
      sessionDepth,
      roundNumber,
    });

    // Update bandit params (alpha+1 or beta+1)
    if (contextKey && intervalSelected) {
      await banditService.updateReward(
        userId,
        contextKey,
        intervalSelected,
        completed != null ? completed : true
      );
    }

    res.status(201).json({
      success: true,
      data: {
        id: session.id,
        userId: session.user_id,
        duration: session.duration_seconds,
        completed: session.completed,
        contextKey: session.context_key,
        createdAt: session.created_at,
      },
    });
  } catch (err) {
    next(err);
  }
});

/**
 * GET /api/sessions/:userId
 * Get session history for a user with pagination and date filtering.
 */
router.get('/:userId', async (req, res, next) => {
  try {
    const { userId } = req.params;
    const {
      limit = '100',
      offset = '0',
      startDate,
      endDate,
    } = req.query;

    const result = await sessionService.getSessionsByUser(userId, {
      limit: parseInt(limit, 10),
      offset: parseInt(offset, 10),
      startDate,
      endDate,
    });

    // Map snake_case DB columns to camelCase for API response
    const sessions = result.sessions.map((s) => ({
      id: s.id,
      startTime: s.start_time,
      endTime: s.end_time,
      duration: s.duration,
      completed: s.completed,
      intervalSelected: s.interval_selected,
      contextKey: s.context_key,
      timeOfDay: s.time_of_day,
      sessionDepth: s.session_depth,
      roundNumber: s.round_number,
      createdAt: s.created_at,
    }));

    res.json({
      success: true,
      data: {
        sessions,
        total: result.total,
        limit: parseInt(limit, 10),
        offset: parseInt(offset, 10),
      },
    });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
