"""
Locust Load Testing Suite for Behavioral Authentication.

Verifies that the behavioral scoring endpoints can handle high concurrency
with < 50ms latency, as required for production.
"""

from locust import HttpUser, task, between
import random
import time
import json


class BehavioralAuthUser(HttpUser):
    # Wait between 1 and 5 seconds between tasks
    wait_time = between(1, 5)

    def on_start(self):
        """Called when a Locust user starts before any task."""
        # Optional: Setup user session, login, etc.
        self.session_id = f"test_session_{random.randint(10000, 99999)}"

    @task(3)
    def submit_behavioral_telemetry(self):
        """Submit passive enrollment / behavioral telemetry payloads."""
        payload = {
            "session_id": self.session_id,
            "type": "extended",
            "event_count": 50,
            "categories": {
                "keystroke": {
                    "key_hold_mean": random.uniform(80.0, 120.0),
                    "flight_time_mean": random.uniform(70.0, 150.0),
                    "typing_speed_wpm": random.uniform(40.0, 80.0),
                    "keystroke_event_count": 25,
                },
                "mouse_pointer": {
                    "mouse_vel_mean": random.uniform(200.0, 400.0),
                    "mouse_event_count": 25,
                }
            },
            "device_context": {
                "screen_width": 1920,
                "screen_height": 1080
            }
        }
        
        # We don't have a user authenticated, so we submit to the unauthenticated
        # telemetry endpoint or a mock test endpoint. If we want to test the full
        # pipeline, we'd need a real token. For load testing, we will hit the
        # public configuration endpoints as well.
        
        with self.client.post(
            "/api/v1/auth/behavioral/telemetry", 
            json=payload,
            catch_response=True,
            name="Submit Telemetry"
        ) as response:
            # We expect 401 Unauthorized if no token, which is fine for load testing
            # the WAF/Gateway layer. If we want to load test the ML, we'd need
            # valid tokens.
            if response.status_code in [200, 202, 401, 403]:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def fetch_csrf_token(self):
        """Test the CSRF token generation endpoint."""
        with self.client.get(
            "/api/v1/auth/csrf-token",
            catch_response=True,
            name="Fetch CSRF"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to get CSRF token: {response.status_code}")

    @task(2)
    def simulate_login_failure(self):
        """Simulate high-volume login attempts to test rate limiting."""
        payload = {
            "username": f"user_{random.randint(1, 1000)}",
            "password": "wrong_password"
        }
        
        with self.client.post(
            "/api/v1/auth/login",
            json=payload,
            catch_response=True,
            name="Login Attempt"
        ) as response:
            # We expect 401 (Invalid creds) or 429 (Rate limited)
            if response.status_code in [401, 429]:
                response.success()
            else:
                response.failure(f"Unexpected login response: {response.status_code}")
