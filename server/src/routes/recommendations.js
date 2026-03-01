// --- routes/recommendations.js ---
// Routes for /api/recommendations endpoints.

const express = require('express');
const router = express.Router();
const recommendationService = require('../services/recommendationService');

/**
 * GET /api/recommendations/population
 * Get population-level recommendation aggregated across all users.
 * Must be defined BEFORE /:userId to avoid route conflict.
 */
router.get('/population', async (req, res, next) => {
  try {
    const { timeOfDay, sessionDepth } = req.query;

    const result = await recommendationService.getPopulationRecommendation({
      timeOfDay,
      sessionDepth,
    });

    res.json({ success: true, data: result });
  } catch (err) {
    next(err);
  }
});

/**
 * GET /api/recommendations/:userId
 * Get a personalized interval recommendation for a specific user.
 * Falls back to population recommendation if user has no data.
 */
router.get('/:userId', async (req, res, next) => {
  try {
    const { userId } = req.params;
    const { timeOfDay, sessionDepth } = req.query;

    const result = await recommendationService.getPersonalRecommendation(userId, {
      timeOfDay,
      sessionDepth,
    });

    res.json({ success: true, data: result });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
