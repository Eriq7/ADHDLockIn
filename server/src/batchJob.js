const { pool } = require('./config/db');

// Beta distribution sampling via Gamma distribution
function gammaSample(alpha) {
  if (alpha < 1) {
    return gammaSample(alpha + 1) * Math.pow(Math.random(), 1 / alpha);
  }
  const d = alpha - 1 / 3;
  const c = 1 / Math.sqrt(9 * d);
  while (true) {
    let x, v;
    do {
      x = randn();
      v = 1 + c * x;
    } while (v <= 0);
    v = v * v * v;
    const u = Math.random();
    if (u < 1 - 0.0331 * (x * x) * (x * x)) return d * v;
    if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v;
  }
}

function randn() {
  const u1 = Math.random();
  const u2 = Math.random();
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}

function betaSample(alpha, beta) {
  const x = gammaSample(alpha);
  const y = gammaSample(beta);
  return x / (x + y);
}

const ARMS = [180, 210, 240, 270, 300, 330];
const CONTEXTS = [];
for (const tod of ['morning', 'afternoon', 'evening', 'night']) {
  for (const depth of ['early', 'mid', 'deep']) {
    CONTEXTS.push(`${tod}_${depth}`);
  }
}

async function runBatchJob() {
  const client = await pool.connect();
  try {
    console.log(`[Batch] Starting population recommendation computation at ${new Date().toISOString()}`);

    // 1. Aggregate all users' bandit parameters
    const aggregateResult = await client.query(`
      SELECT context_key, arm,
             SUM(alpha) as total_alpha,
             SUM(beta) as total_beta,
             COUNT(DISTINCT user_id) as user_count
      FROM bandit_params
      GROUP BY context_key, arm
      ORDER BY context_key, arm
    `);

    // 2. Group by context_key
    const contextData = {};
    for (const row of aggregateResult.rows) {
      if (!contextData[row.context_key]) {
        contextData[row.context_key] = { arms: [], userCount: 0 };
      }
      contextData[row.context_key].arms.push({
        arm: row.arm,
        totalAlpha: parseFloat(row.total_alpha),
        totalBeta: parseFloat(row.total_beta)
      });
      contextData[row.context_key].userCount = Math.max(
        contextData[row.context_key].userCount,
        parseInt(row.user_count)
      );
    }

    // 3. Thompson Sampling for each context
    let upsertCount = 0;

    for (const contextKey of CONTEXTS) {
      let allScores;
      let recommendedArm;
      let totalUsers;

      if (contextData[contextKey] && contextData[contextKey].arms.length > 0) {
        const data = contextData[contextKey];
        totalUsers = data.userCount;

        allScores = data.arms.map(a => ({
          arm: a.arm,
          score: betaSample(a.totalAlpha, a.totalBeta),
          totalAlpha: a.totalAlpha,
          totalBeta: a.totalBeta
        }));

        // Fill missing arms with uninformative prior
        for (const arm of ARMS) {
          if (!allScores.find(s => s.arm === arm)) {
            allScores.push({
              arm: arm,
              score: betaSample(1, 1),
              totalAlpha: 1,
              totalBeta: 1
            });
          }
        }
      } else {
        totalUsers = 0;
        allScores = ARMS.map(arm => ({
          arm: arm,
          score: betaSample(1, 1),
          totalAlpha: 1,
          totalBeta: 1
        }));
      }

      allScores.sort((a, b) => b.score - a.score);
      recommendedArm = allScores[0].arm;

      // 4. UPSERT into population_recommendations
      await client.query(`
        INSERT INTO population_recommendations (context_key, recommended_arm, all_scores, total_users, computed_at)
        VALUES ($1, $2, $3, $4, NOW())
        ON CONFLICT (context_key)
        DO UPDATE SET
          recommended_arm = $2,
          all_scores = $3,
          total_users = $4,
          computed_at = NOW()
      `, [
        contextKey,
        recommendedArm,
        JSON.stringify(allScores),
        totalUsers
      ]);

      upsertCount++;
      console.log(`[Batch] ${contextKey}: recommended ${recommendedArm}s (${totalUsers} users)`);
    }

    console.log(`[Batch] Completed. Updated ${upsertCount} context recommendations.`);
    return { success: true, updatedContexts: upsertCount };

  } finally {
    client.release();
  }
}

if (require.main === module) {
  runBatchJob()
    .then((result) => { console.log('Batch job result:', result); process.exit(0); })
    .catch((err) => { console.error('Batch job failed:', err); process.exit(1); });
}

module.exports = { runBatchJob };
