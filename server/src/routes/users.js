// --- routes/users.js ---
// Routes for /api/users endpoints.

const express = require('express');
const router = express.Router();
const userService = require('../services/userService');

/**
 * POST /api/users/register
 * Register a new user. System generates a 6-char secret key.
 */
router.post('/register', async (req, res, next) => {
  try {
    const { username } = req.body;

    if (!username) {
      return res.status(400).json({ success: false, error: 'Missing required field: username' });
    }

    const result = await userService.register(username);

    res.status(201).json({
      success: true,
      data: {
        username: result.username,
        secretKey: result.secretKey,
        message: 'Registration successful. Please save your username and secret key. This is the only time they will be shown.',
      },
    });
  } catch (err) {
    if (err.code === 'INVALID_USERNAME') {
      return res.status(400).json({ success: false, error: err.message });
    }
    if (err.code === 'USERNAME_TAKEN') {
      return res.status(409).json({ success: false, error: err.message });
    }
    next(err);
  }
});

/**
 * POST /api/users/login
 * Login with username and secret key.
 */
router.post('/login', async (req, res, next) => {
  try {
    const { username, secretKey } = req.body;

    if (!username) {
      return res.status(400).json({ success: false, error: 'Missing required field: username' });
    }
    if (!secretKey) {
      return res.status(400).json({ success: false, error: 'Missing required field: secretKey' });
    }

    const result = await userService.login(username, secretKey);

    res.json({
      success: true,
      data: {
        userId: result.userId,
        username: result.username,
        createdAt: result.createdAt,
        message: 'Login successful.',
      },
    });
  } catch (err) {
    if (err.code === 'USER_NOT_FOUND') {
      return res.status(404).json({ success: false, error: err.message });
    }
    if (err.code === 'INVALID_KEY') {
      return res.status(401).json({ success: false, error: err.message });
    }
    next(err);
  }
});

module.exports = router;
