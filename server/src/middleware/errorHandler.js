// --- middleware/errorHandler.js ---
// Centralized error handling middleware.

/**
 * Express error-handling middleware.
 * Catches all errors thrown in route handlers and returns a consistent JSON response.
 * @param {Error} err
 * @param {import('express').Request} req
 * @param {import('express').Response} res
 * @param {import('express').NextFunction} next
 */
function errorHandler(err, req, res, next) {
  console.error(`Error [${req.method} ${req.originalUrl}]:`, err.message);

  // PostgreSQL unique constraint violation
  if (err.code === '23505') {
    return res.status(409).json({
      success: false,
      error: 'Duplicate entry: record already exists.',
    });
  }

  // PostgreSQL foreign key / check constraint violation
  if (err.code === '23503' || err.code === '23514') {
    return res.status(400).json({
      success: false,
      error: 'Invalid data: constraint violation.',
    });
  }

  res.status(500).json({
    success: false,
    error: 'Internal server error.',
  });
}

module.exports = errorHandler;
