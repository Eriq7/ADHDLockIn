# --- api_client.py ---
# HTTP client for ADHDLockIn Express API.
# Used by the desktop app to read/write data through the API
# instead of directly connecting to PostgreSQL/Redis.

import requests
from datetime import datetime

API_BASE_URL = "https://1ltnq33e02.execute-api.us-east-1.amazonaws.com/api"
API_TIMEOUT = 5  # seconds


class APIClient:
    def __init__(self, user_id="local_user"):
        self.user_id = user_id

    def get_recommendation(self, time_of_day, session_depth):
        """
        Call GET /api/recommendations/:userId to get the recommended interval.
        Returns the recommended seconds (int), e.g. 240.
        Returns None if the API call fails.
        """
        try:
            response = requests.get(
                f"{API_BASE_URL}/recommendations/{self.user_id}",
                params={"timeOfDay": time_of_day, "sessionDepth": session_depth},
                timeout=API_TIMEOUT
            )
            data = response.json()
            if data.get("success"):
                return data["data"]["recommended"]
            return None
        except Exception as e:
            print(f"API Error (get_recommendation): {e}")
            return None

    def post_session(self, start_time, end_time, duration, completed,
                     interval_selected, context_key, time_of_day,
                     session_depth, round_number):
        """
        Call POST /api/sessions to log a session.
        The backend automatically updates bandit params (alpha/beta),
        so there's no need to call update_reward() separately.
        Returns True on success, False on failure.
        """
        try:
            payload = {
                "userId": self.user_id,
                "startTime": start_time.isoformat() if isinstance(start_time, datetime) else start_time,
                "endTime": end_time.isoformat() if isinstance(end_time, datetime) else end_time,
                "duration": duration,
                "completed": completed,
                "intervalSelected": interval_selected,
                "contextKey": context_key,
                "timeOfDay": time_of_day,
                "sessionDepth": session_depth,
                "roundNumber": round_number
            }
            response = requests.post(
                f"{API_BASE_URL}/sessions",
                json=payload,
                timeout=API_TIMEOUT
            )
            data = response.json()
            return data.get("success", False)
        except Exception as e:
            print(f"API Error (post_session): {e}")
            return False
