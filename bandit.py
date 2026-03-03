# --- bandit.py ---
# Contextual Thompson Sampling Bandit for adaptive study interval selection.
#
# Algorithm overview:
# - 6 discrete arms represent possible focus interval lengths (180s to 330s).
# - Context is derived from time-of-day and session depth (round number).
# - Each (context, arm) pair maintains alpha/beta parameters for a Beta distribution.
# - To select an arm: sample from Beta(alpha, beta) for each arm, pick the highest.
# - On session complete: alpha += 1 (reward). On incomplete: beta += 1 (penalty).
# - Parameters are persisted to bandit_params.json between sessions.

import json
import os
import sys
import random
from datetime import datetime

try:
    from db import load_bandit_params_from_db, save_bandit_params_to_db
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

try:
    from cache import load_bandit_params_from_cache, save_bandit_params_to_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

ARMS = [180, 210, 240, 270, 300, 330]
PARAMS_FILE = "bandit_params.json"


def _user_data_path(filename):
    home = os.path.expanduser("~")
    app_dir = os.path.join(home, ".adhdlockin")
    os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, filename)


def _get_params_path():
    return _user_data_path(PARAMS_FILE)


def _get_time_of_day():
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "afternoon"
    elif 18 <= hour < 24:
        return "evening"
    else:
        return "night"


def _get_session_depth(round_number):
    if round_number <= 2:
        return "early"
    elif round_number <= 4:
        return "mid"
    else:
        return "deep"


def _get_context_key(round_number):
    return f"{_get_time_of_day()}_{_get_session_depth(round_number)}"


def _default_params():
    """Create default parameters with alpha=1, beta=1 for all context-arm pairs."""
    contexts = []
    for tod in ["morning", "afternoon", "evening", "night"]:
        for depth in ["early", "mid", "deep"]:
            contexts.append(f"{tod}_{depth}")

    params = {}
    for ctx in contexts:
        params[ctx] = {}
        for arm in ARMS:
            params[ctx][str(arm)] = {"alpha": 1, "beta": 1}
    return params


def _load_params():
    # 1. Try Redis cache first
    if CACHE_AVAILABLE:
        try:
            params = load_bandit_params_from_cache()
            if params is not None:
                return params
        except Exception as e:
            print(f"Warning: Failed to load bandit params from cache: {e}")

    # 2. Try PostgreSQL
    if DB_AVAILABLE:
        try:
            params = load_bandit_params_from_db()
            if params is not None:
                if CACHE_AVAILABLE:
                    save_bandit_params_to_cache(params)
                return params
        except Exception as e:
            print(f"Warning: Failed to load bandit params from DB: {e}")

    # 3. Fall back to JSON file
    path = _get_params_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                params = json.load(f)
                if CACHE_AVAILABLE:
                    save_bandit_params_to_cache(params)
                return params
        except (json.JSONDecodeError, IOError):
            pass
    return _default_params()


def _save_params(params):
    # 1. Save to Redis cache
    if CACHE_AVAILABLE:
        try:
            save_bandit_params_to_cache(params)
        except Exception as e:
            print(f"Warning: Failed to save bandit params to cache: {e}")
    # 2. Save to PostgreSQL
    if DB_AVAILABLE:
        try:
            save_bandit_params_to_db(params)
        except Exception as e:
            print(f"Warning: Failed to save bandit params to DB: {e}")
    # 3. Save to JSON as backup
    path = _get_params_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(params, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Error: Failed to save bandit params to JSON: {e}")


def _ensure_context(params, context_key):
    """Ensure the context key exists in params (handles new contexts gracefully)."""
    if context_key not in params:
        params[context_key] = {}
        for arm in ARMS:
            params[context_key][str(arm)] = {"alpha": 1, "beta": 1}


def select_interval(round_number: int) -> int:
    """
    Given the current round number, determine context (time_of_day + session_depth),
    run Thompson Sampling, and return the selected interval in seconds.
    """
    params = _load_params()
    context_key = _get_context_key(round_number)
    _ensure_context(params, context_key)

    best_arm = ARMS[0]
    best_sample = -1.0

    for arm in ARMS:
        arm_params = params[context_key][str(arm)]
        sample = random.betavariate(arm_params["alpha"], arm_params["beta"])
        if sample > best_sample:
            best_sample = sample
            best_arm = arm

    return best_arm


def update_reward(round_number: int, interval: int, completed: bool) -> None:
    """
    After a session ends, update the bandit params for the arm that was chosen.
    completed=True means user finished the session, False means they quit/reset.
    """
    params = _load_params()
    context_key = _get_context_key(round_number)
    _ensure_context(params, context_key)

    arm_key = str(interval)
    if arm_key not in params[context_key]:
        return

    if completed:
        params[context_key][arm_key]["alpha"] += 1
    else:
        params[context_key][arm_key]["beta"] += 1

    _save_params(params)


def get_bandit_stats() -> dict:
    """
    Return the full bandit_params dict for debugging or future API use.
    """
    return _load_params()
