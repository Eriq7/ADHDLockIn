// --- services/recommendationService.js ---
// Personal and population-level recommendation logic.

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
 * Falls back to population-level recommendation if the user has no data.
 * @param {string} userId
 * @param {Object} [options]
 * @param {string} [options.timeOfDay] - Override time-of-day (auto-detected if omitted).
 * @param {string} [options.sessionDepth="early"] - "early" | "mid" | "deep"
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

  // Ensure the context exists in params
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
 * Get population-level recommendation by aggregating all users' bandit params.
 * @param {Object} [options]
 * @param {string} [options.timeOfDay] - Filter by time-of-day.
 * @param {string} [options.sessionDepth] - Filter by session depth.
 * @returns {Promise<Object>} Population recommendation result.
 */
async function getPopulationRecommendation(options = {}) {
  const timeOfDay = options.timeOfDay || getTimeOfDay();
  const sessionDepth = options.sessionDepth || 'early';
  const contextKey = `${timeOfDay}_${sessionDepth}`;

  const { params, totalUsers } = await banditService.loadPopulationParams();

  const contextParams = params[contextKey];
  if (!contextParams) {
    // No data at all — return defaults
    const defaults = banditService.defaultParams()[contextKey];
    const allScores = banditService.thompsonSample(defaults).map((s) => ({
      arm: s.arm,
      score: s.score,
      totalAlpha: s.alpha,
      totalBeta: s.beta,
    }));
    return {
      contextKey,
      recommended: allScores[0].arm,
      allScores,
      totalUsers: 0,
      source: 'population',
    };
  }

  const sampled = banditService.thompsonSample(contextParams);
  const allScores = sampled.map((s) => ({
    arm: s.arm,
    score: s.score,
    totalAlpha: s.alpha,
    totalBeta: s.beta,
  }));

  console.log(`Population recommendation: ctx=${contextKey}, recommended=${allScores[0].arm}s, users=${totalUsers}`);

  return {
    contextKey,
    recommended: allScores[0].arm,
    allScores,
    totalUsers,
    source: 'population',
  };
}

module.exports = { getPersonalRecommendation, getPopulationRecommendation };
