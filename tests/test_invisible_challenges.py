import pytest
from app.models.invisible_challenge_engine import get_challenge_engine

def test_invisible_challenge_integration(client, logged_in_user):
    """
    Test that challenge features are passed from the API layer down 
    to the InvisibleChallengeEngine and back to the response.
    """
    # 1. Create a payload simulating the JS collector
    payload = {
        "session_id": logged_in_user["session_id"],
        "type": "extended",
        "event_count": 50,
        "extended_features": {
            "ch_challenge_count": 5,
            "ch_response_count": 5,
            "ch_bot_challenge_score": 0.85,  # High bot score
            "ch_correction_time_mean": 30,   # Superhuman < 50ms
            "ch_correction_accuracy_mean": 0.99,
            "ch_subconscious_ratio": 0.8
        }
    }

    # 2. Post to the behavioral endpoint
    response = client.post(
        "/api/v1/behavioral/data",
        json=payload,
        headers={"Authorization": f"Bearer {logged_in_user['access_token']}"}
    )
    
    assert response.status_code == 200
    data = response.json
    
    # 3. Verify the ensemble response contains challenge_risk and flags
    # Since we made it async, wait, if we made it async, ensemble_result will not be in the response immediately!
    # Let's check the score directly through the engine or ensure we wait.
    
    engine = get_challenge_engine()
    result = engine.score_responses(payload["extended_features"])
    assert result["challenge_risk"] > 0
    assert "challenge:bot_score(0.85)" in result["flags"]
    assert "challenge:superhuman_correction(30ms)" in result["flags"]
