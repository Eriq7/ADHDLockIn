// --- services/recommendationService.js ---
// Personal and population-level recommendation logic.

const { pool } = require('../config/db');
const banditService = require('./banditService');

/**
 * Determine the current time-of-day slot based on server local time.
 * @returns {string} "morning" | "afternoon" | "evening" | "night"
 */
function getTimeOfDay() {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return 'morning';
  if (hour >= 12 && hour < 17) return 'afternoon';
  if (hour >= 17 && hour < 21) return 'evening';
  return 'night';
}

/**
 * Get a personalized interval recommendation for a user.
 * Falls back to pre-computed population recommendation if the user has no data.
 * @param {string} userId
 * @param {Object} [options]
 * @param {string} [options.timeOfDay]
 * @param {string} [options.sessionDepth="early"]
 * @returns {Promise<Object>} Recommendation result.
 */
async function getPersonalRecommendation(userId, options = {}) {
  const timeOfDay = options.timeOfDay || getTimeOfDay();
  const sessionDepth = options.sessionDepth || 'early';
  const contextKey = `${timeOfDay}_${sessionDepth}`;

  const params = await banditService.loadParams(userId);

  // Check if user has real data (any alpha or beta > 1)
  const hasPersonalData = Object.values(params).some((arms) =>
    Object.values(arms).some((v) => v.alpha > 1 || v.beta > 1)
  );

  if (!hasPersonalData) {
    console.log(`Recommendation: user=${userId} has no personal data, falling back to population.`);
    const popResult = await getPopulationRecommendation({ timeOfDay, sessionDepth });
    return { ...popResult, userId, source: 'population' };
  }

  const contextParams = params[contextKey];
  if (!contextParams) {
    console.log(`Recommendation: context=${contextKey} not found for user=${userId}, falling back to population.`);
    const popResult = await getPopulationRecommendation({ timeOfDay, sessionDepth });
    return { ...popResult, userId, source: 'population' };
  }

  const allScores = banditService.thompsonSample(contextParams);
  const recommended = allScores[0].arm;

  console.log(`Recommendation: user=${userId}, ctx=${contextKey}, recommended=${recommended}s`);

  return {
    userId,
    contextKey,
    recommended,
    allScores,
    source: 'personal',
  };
}

/**
 * Get population-level recommendation from pre-computed population_recommendations table.
 * Falls back to default 240s if no pre-computed data exists.
 * @param {Object} [options]
 * @param {string} [options.timeOfDay]
 * @param {string} [options.sessionDepth]
 * @returns {Promise<Object>} Population recommendation result.
 */
async function getPopulationRecommendation(options = {}) {
  const timeOfDay = options.timeOfDay || getTimeOfDay();
  const sessionDepth = options.sessionDepth || 'early';
  const contextKey = `${timeOfDay}_${sessionDepth}`;

  const result = await pool.query(
    'SELECT * FROM population_recommendations WHERE context_key = $1',
    [contextKey]
  );

  if (result.rows.length > 0) {
    const row = result.rows[0];
    return {
      contextKey: row.context_key,
      recommended: row.recommended_arm,
      allScores: row.all_scores,
      totalUsers: row.total_users,
      computedAt: row.computed_at,
      source: 'population',
    };
  }

  // Table empty (batch job hasn't run yet): return default 240
  return {
    contextKey: contextKey,
    recommended: 240,
    allScores: [180, 210, 240, 270, 300, 330].map(arm => ({
      arm: arm,
      score: 0,
      totalAlpha: 1,
      totalBeta: 1
    })),
    totalUsers: 0,
    computedAt: null,
    source: 'default',
  };
}

module.exports = { getPersonalRecommendation, getPopulationRecommendation };
