// --- index.js ---
// ADHDLockIn Express API server entry point.

require('dotenv').config();

const express = require('express');
const cors = require('cors');
const { initRedis } = require('./config/db');
const sessionRoutes = require('./routes/sessions');
const recommendationRoutes = require('./routes/recommendations');
const errorHandler = require('./middleware/errorHandler');

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());

// Routes
app.use('/api/sessions', sessionRoutes);
app.use('/api/recommendations', recommendationRoutes);

/**
 * GET /api/health
 * Health check endpoint.
 */
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Error handling
app.use(errorHandler);

/**
 * Start the server after initializing Redis.
 */
async function start() {
  await initRedis();
  app.listen(PORT, () => {
    console.log(`ADHDLockIn API server running on port ${PORT}`);
  });
}

start();
