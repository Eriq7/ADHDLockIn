# --- db.py ---
# PostgreSQL database module for ADHDLockIn.
# Provides session logging and bandit parameter storage.

import psycopg2
from datetime import datetime

DB_CONFIG = {
    "dbname": "adhdlockin",
    "user": "postgres",
    "password": "Awaqq1314",
    "host": "localhost",
    "port": "5432"
}

_conn = None


def _get_conn():
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(
            dbname=DB_CONFIG["dbname"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"]
        )
        _conn.autocommit = True
    return _conn


def init_db():
    """Connect to PostgreSQL and create tables if they don't exist."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(50) DEFAULT 'local_user',
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                duration_seconds INTEGER NOT NULL,
                duration_minutes NUMERIC(10,2) NOT NULL,
                completed BOOLEAN DEFAULT TRUE,
                interval_selected INTEGER,
                context_key VARCHAR(50),
                time_of_day VARCHAR(20),
                session_depth VARCHAR(20),
                round_number INTEGER,
                date DATE NOT NULL,
                day_of_week VARCHAR(20) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bandit_params (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(50) DEFAULT 'local_user',
                context_key VARCHAR(50) NOT NULL,
                arm INTEGER NOT NULL,
                alpha INTEGER DEFAULT 1,
                beta INTEGER DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, context_key, arm)
            );
        """)
        cur.close()
        print("DB: PostgreSQL initialized successfully.")
    except Exception as e:
        print(f"DB Warning: Could not initialize PostgreSQL: {e}")


def log_session_to_db(start_time, end_time, duration_seconds, completed=True,
                       interval_selected=None, context_key=None, time_of_day=None,
                       session_depth=None, round_number=None):
    """Insert a session record into the sessions table."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        duration_minutes = round(duration_seconds / 60, 2)
        date = start_time.date()
        day_of_week = start_time.strftime('%A')
        cur.execute("""
            INSERT INTO sessions
                (start_time, end_time, duration_seconds, duration_minutes, completed,
                 interval_selected, context_key, time_of_day, session_depth,
                 round_number, date, day_of_week)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (start_time, end_time, duration_seconds, duration_minutes, completed,
              interval_selected, context_key, time_of_day, session_depth,
              round_number, date, day_of_week))
        cur.close()
    except Exception as e:
        print(f"DB Warning: Failed to log session: {e}")


def get_all_sessions(user_id='local_user'):
    """Return all sessions for a user as a list of dicts."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM sessions WHERE user_id = %s ORDER BY start_time",
            (user_id,)
        )
        columns = [desc[0] for desc in (cur.description or [])]
        rows = cur.fetchall()
        cur.close()
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        print(f"DB Warning: Failed to get sessions: {e}")
        return []


def load_bandit_params_from_db(user_id='local_user'):
    """
    Load bandit params from PostgreSQL and return in the same format as bandit.py uses.
    Returns None if no data exists in DB yet.
    """
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT context_key, arm, alpha, beta FROM bandit_params WHERE user_id = %s",
            (user_id,)
        )
        rows = cur.fetchall()
        cur.close()
        if not rows:
            return None
        params = {}
        for context_key, arm, alpha, beta in rows:
            if context_key not in params:
                params[context_key] = {}
            params[context_key][str(arm)] = {"alpha": alpha, "beta": beta}
        return params
    except Exception as e:
        print(f"DB Warning: Failed to load bandit params: {e}")
        return None


def save_bandit_params_to_db(params, user_id='local_user'):
    """
    Save the full bandit params dict to PostgreSQL.
    Uses INSERT ... ON CONFLICT to upsert each (context_key, arm) pair.
    """
    try:
        conn = _get_conn()
        cur = conn.cursor()
        for context_key, arms in params.items():
            for arm_str, values in arms.items():
                cur.execute("""
                    INSERT INTO bandit_params (user_id, context_key, arm, alpha, beta, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, context_key, arm) DO UPDATE
                    SET alpha = EXCLUDED.alpha, beta = EXCLUDED.beta, updated_at = EXCLUDED.updated_at
                """, (user_id, context_key, int(arm_str), values["alpha"], values["beta"], datetime.now()))
        cur.close()
    except Exception as e:
        print(f"DB Warning: Failed to save bandit params: {e}")


def close_db():
    """Close the database connection."""
    global _conn
    if _conn and not _conn.closed:
        try:
            _conn.close()
            print("DB: Connection closed.")
        except Exception as e:
            print(f"DB Warning: Error closing connection: {e}")
    _conn = None
