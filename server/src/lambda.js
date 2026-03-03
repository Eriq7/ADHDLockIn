const serverless = require('serverless-http');
const app = require('./app');
const { runMigration } = require('./migrate');

let migrationDone = false;
const handler = serverless(app);

module.exports.handler = async (event, context) => {
  if (!migrationDone) {
    try {
      await runMigration();
      migrationDone = true;
      console.log('Migration completed successfully');
    } catch (err) {
      console.error('Migration failed:', err);
      migrationDone = true;
    }
  }
  return handler(event, context);
};
