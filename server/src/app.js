require('dotenv').config();
const express = require('express');
const cors = require('cors');
const sessionRoutes = require('./routes/sessions');
const recommendationRoutes = require('./routes/recommendations');
const userRoutes = require('./routes/users');
const errorHandler = require('./middleware/errorHandler');

const app = express();

app.use(cors());
app.use(express.json());

app.use('/api/sessions', sessionRoutes);
app.use('/api/recommendations', recommendationRoutes);
app.use('/api/users', userRoutes);

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.use(errorHandler);

module.exports = app;
