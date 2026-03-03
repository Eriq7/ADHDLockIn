const { runBatchJob } = require('./batchJob');
const { runMigration } = require('./migrate');

let migrationDone = false;

module.exports.handler = async (event, context) => {
  if (!migrationDone) {
    try {
      await runMigration();
      migrationDone = true;
    } catch (err) {
      console.error('Migration failed:', err);
      migrationDone = true;
    }
  }

  try {
    const result = await runBatchJob();
    console.log('Batch job completed:', result);
    return {
      statusCode: 200,
      body: JSON.stringify(result)
    };
  } catch (err) {
    console.error('Batch job error:', err);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: err.message })
    };
  }
};
