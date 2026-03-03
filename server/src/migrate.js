const { pool } = require('./config/db');

const migrations = [
  {
    name: 'create_users_table',
    sql: `
      CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        secret_key VARCHAR(10) NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
      );
    `
  },
  {
    name: 'create_sessions_table',
    sql: `
      CREATE TABLE IF NOT EXISTS sessions (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        start_time TIMESTAMP NOT NULL,
        end_time TIMESTAMP NOT NULL,
        duration INTEGER NOT NULL,
        completed BOOLEAN NOT NULL DEFAULT false,
        interval_selected INTEGER NOT NULL,
        context_key VARCHAR(30),
        time_of_day VARCHAR(10),
        session_depth VARCHAR(10),
        round_number INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT NOW()
      );
    `
  },
  {
    name: 'create_bandit_params_table',
    sql: `
      CREATE TABLE IF NOT EXISTS bandit_params (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        context_key VARCHAR(30) NOT NULL,
        arm INTEGER NOT NULL,
        alpha FLOAT DEFAULT 1.0,
        beta FLOAT DEFAULT 1.0,
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(user_id, context_key, arm)
      );
    `
  },
  {
    name: 'create_population_recommendations_table',
    sql: `
      CREATE TABLE IF NOT EXISTS population_recommendations (
        id SERIAL PRIMARY KEY,
        context_key VARCHAR(30) NOT NULL UNIQUE,
        recommended_arm INTEGER NOT NULL,
        all_scores JSONB NOT NULL,
        total_users INTEGER NOT NULL DEFAULT 0,
        computed_at TIMESTAMP DEFAULT NOW()
      );
    `
  },
  {
    name: 'create_sessions_user_id_index',
    sql: `CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);`
  },
  {
    name: 'create_bandit_params_user_context_index',
    sql: `CREATE INDEX IF NOT EXISTS idx_bandit_user_context ON bandit_params(user_id, context_key);`
  }
];

async function runMigration() {
  const client = await pool.connect();
  try {
    for (const migration of migrations) {
      console.log(`Running migration: ${migration.name}`);
      await client.query(migration.sql);
      console.log(`Completed: ${migration.name}`);
    }
    console.log('All migrations completed');
  } finally {
    client.release();
  }
}

if (require.main === module) {
  runMigration()
    .then(() => { console.log('Migration finished'); process.exit(0); })
    .catch((err) => { console.error('Migration failed:', err); process.exit(1); });
}

module.exports = { runMigration };
