import pytest
from fastapi.testclient import TestClient
from datetime import datetime

from app.main import app
from app.database.models.user import User
from app.database.models.session import TrainingSession
from app.utils.security import hash_password, create_access_token


@pytest.fixture
def test_user(db_session):
    u = User(
        name="Dr. Test User",
        email="test.user.enhancements@medvr.org",
        password_hash=hash_password("Pass1234!")
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(user_id=test_user.id, email=test_user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def active_session(test_user, db_session):
    sess = TrainingSession(
        session_id="session-enhancement-test",
        user_id=test_user.id,
        session_type="TEST",
        session_number=99,
        start_time=datetime.utcnow(),
        status="IN_PROGRESS"
    )
    db_session.add(sess)
    db_session.commit()
    db_session.refresh(sess)
    return sess


def test_auth_register_and_refresh(client: TestClient):
    # 1. Register new user
    reg_payload = {
        "name": "Nurse Sarah Jenkins",
        "email": "sarah.jenkins@hospital.org",
        "password": "SecurePassword123!"
    }
    res_reg = client.post("/api/auth/register", json=reg_payload)
    assert res_reg.status_code == 201
    data = res_reg.json()
    assert "access_token" in data
    assert data["email"] == "sarah.jenkins@hospital.org"

    # Also test /api/v1 alias
    v1_headers = {"Authorization": f"Bearer {data['access_token']}"}
    res_me = client.get("/api/v1/auth/me", headers=v1_headers)
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "sarah.jenkins@hospital.org"

    # 2. Refresh token
    res_ref = client.post("/api/auth/refresh", headers=v1_headers)
    assert res_ref.status_code == 200
    assert "access_token" in res_ref.json()


def test_batch_step_performance_ingestion(client: TestClient, active_session, auth_headers):
    # Prepare batch of 5 steps
    batch_payload = [
        {
            "session_id": active_session.id,
            "step_id": i,
            "attempts": 1,
            "mistakes": 0,
            "first_attempt_correct": True,
            "step_time_seconds": 6.5,
            "completed": True
        }
        for i in range(5)
    ]

    # Test /api/step-performance/batch
    res_batch = client.post("/api/step-performance/batch", json=batch_payload, headers=auth_headers)
    assert res_batch.status_code == 200
    data = res_batch.json()
    assert len(data) == 5
    assert data[0]["step_name"] == "Wash Hands"
    assert data[4]["step_name"] == "Dip Cotton in Spirit"

    # Test duplicate batch rejection
    res_dup = client.post("/api/step-performance/batch", json=batch_payload, headers=auth_headers)
    assert res_dup.status_code == 400


def test_dynamic_model_name_in_ai_report(client: TestClient, active_session, auth_headers):
    # Insert all 16 steps
    all_steps_batch = [
        {
            "session_id": active_session.id,
            "step_id": i,
            "attempts": 1,
            "mistakes": 0,
            "first_attempt_correct": True,
            "step_time_seconds": 7.0,
            "completed": True
        }
        for i in range(16)
    ]
    client.post("/api/step-performance/batch", json=all_steps_batch, headers=auth_headers)

    # Request AI report with custom model override
    res_ai = client.post(
        f"/api/reports/{active_session.id}/ai?model_name=llama-3.2-3b",
        headers=auth_headers
    )
    assert res_ai.status_code == 200
    data = res_ai.json()
    assert data["model_name"] == "llama-3.2-3b"
    assert data["deterministic_assessment"]["result"] == "PASS"
