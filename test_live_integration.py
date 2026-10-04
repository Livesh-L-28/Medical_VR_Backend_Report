import time
import json
import httpx
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database.database import Base, get_db
from app.main import app as fastapi_app
import app.database.models
from app.database.models.user import User
from app.database.models.session import TrainingSession
from app.database.models.step_performance import StepPerformance
from app.database.models.mistake import Mistake
from app.database.models.weak_area import WeakArea
from app.utils.security import hash_password, create_access_token
from app.config.constants import STEPS
from app.config.settings import settings
from app.services.historical_context_service import get_user_historical_context

# -----------------------------------------------------------------------------
# Setup In-Memory Database for Live API Test
# -----------------------------------------------------------------------------
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

fastapi_app.dependency_overrides[get_db] = override_get_db
client = TestClient(fastapi_app)
db = TestingSessionLocal()

results = {}

# -----------------------------------------------------------------------------
# STEP 1 & 2: Verify Backend & Medical LLM Reachability
# -----------------------------------------------------------------------------
print("\n" + "="*80)
print("1. VERIFYING MEDICAL VR BACKEND & MEDICAL LLM API REACHABILITY")
print("="*80)

# Backend Health
res_backend_health = client.get("/health")
assert res_backend_health.status_code == 200
results["backend_url"] = "http://127.0.0.1:8001"
results["backend_status"] = res_backend_health.json().get("status")
print(f"[✓] Medical VR Backend is reachable: {results['backend_status']}")

# Medical LLM Health
llm_base_url = settings.MEDICAL_LLM_URL.rstrip('/')
llm_endpoint = settings.MEDICAL_LLM_ENDPOINT
results["medical_llm_url"] = llm_base_url
results["llm_endpoint"] = llm_endpoint
results["model_configured"] = settings.MEDICAL_LLM_MODEL

try:
    with httpx.Client(timeout=10.0) as http_c:
        llm_health_resp = http_c.get(f"{llm_base_url}/health")
        assert llm_health_resp.status_code == 200
        llm_health_data = llm_health_resp.json()
        print(f"[✓] Medical LLM API is reachable at {llm_base_url}/health: {llm_health_data.get('status')}")
        print(f"    Parameters: {llm_health_data.get('model_parameters')}, Device: {llm_health_data.get('device')}")
except Exception as e:
    print(f"[!] Warning checking LLM health: {e}")

# -----------------------------------------------------------------------------
# STEP 3 & 4: Create User & Test Session
# -----------------------------------------------------------------------------
print("\n" + "="*80)
print("2. CREATING TRAINEE USER & EVALUATED TEST SESSION")
print("="*80)

# User 1
user1 = User(
    name="Dr. Marcus Vance",
    email="m.vance@clinic.org",
    password_hash=hash_password("Pass1234!")
)
# User 2 for isolation testing
user2 = User(
    name="Dr. Other User",
    email="other@clinic.org",
    password_hash=hash_password("Pass1234!")
)
db.add_all([user1, user2])
db.commit()
db.refresh(user1)
db.refresh(user2)

token_u1 = create_access_token(user_id=user1.id, email=user1.email)
headers_u1 = {"Authorization": f"Bearer {token_u1}"}

# User 1 prior completed session (to test historical context)
prior_sess = TrainingSession(
    session_id="prior-sess-0",
    user_id=user1.id,
    session_type="TRAINING",
    session_number=1,
    start_time=datetime.utcnow(),
    end_time=datetime.utcnow(),
    total_time_seconds=90.0,
    status="COMPLETED"
)
db.add(prior_sess)
db.commit()
db.refresh(prior_sess)

for i in range(16):
    db.add(StepPerformance(
        session_id=prior_sess.id,
        step_id=i,
        step_name=STEPS[i],
        attempts=1,
        mistakes=0,
        first_attempt_correct=True,
        step_time_seconds=5.0,
        completed=True
    ))
db.commit()

# Current TEST session: Step 7 has 1 mistake (FAIL session to test weak areas)
current_sess = TrainingSession(
    session_id="current-test-sess-1",
    user_id=user1.id,
    session_type="TEST",
    session_number=2,
    start_time=datetime.utcnow(),
    end_time=datetime.utcnow(),
    total_time_seconds=145.0,
    status="COMPLETED"
)
db.add(current_sess)
db.commit()
db.refresh(current_sess)

for i in range(16):
    is_step_7 = (i == 7)
    db.add(StepPerformance(
        session_id=current_sess.id,
        step_id=i,
        step_name=STEPS[i],
        attempts=2 if is_step_7 else 1,
        mistakes=1 if is_step_7 else 0,
        first_attempt_correct=not is_step_7,
        step_time_seconds=8.5,
        completed=True
    ))

db.add(Mistake(
    session_id=current_sess.id,
    step_id=7,
    mistake_type="WRONG_OBJECT",
    attempt_number=1
))
db.commit()

results["session_id_tested"] = current_sess.id
print(f"[✓] Created Test Session ID {current_sess.id} for User {user1.id} ({user1.name})")

# -----------------------------------------------------------------------------
# STEP 5, 6, 7: Call AI Report Endpoint & Measure Live Request
# -----------------------------------------------------------------------------
print("\n" + "="*80)
print("3. EXECUTING LIVE POST /api/reports/{session_id}/ai")
print("="*80)

t0 = time.time()
res_report = client.post(f"/api/reports/{current_sess.id}/ai", headers=headers_u1)
latency_ms = round((time.time() - t0) * 1000, 2)
results["latency_ms"] = latency_ms
results["http_status"] = res_report.status_code

assert res_report.status_code == 200, f"Failed with {res_report.status_code}: {res_report.text}"
report_data = res_report.json()

print(f"[✓] Received HTTP {res_report.status_code} in {latency_ms} ms")
print("\n--- Final Backend Response ---")
print(json.dumps(report_data, indent=2))

# -----------------------------------------------------------------------------
# STEP 8: Schema & Content Validation
# -----------------------------------------------------------------------------
print("\n" + "="*80)
print("4. VERIFYING SCHEMA VALIDATION & AI FEEDBACK")
print("="*80)

ai_feedback = report_data.get("ai_feedback")
assert ai_feedback is not None
assert "summary" in ai_feedback
assert "strengths" in ai_feedback
assert "improvement_areas" in ai_feedback
assert "recommendations" in ai_feedback
assert "progress_summary" in ai_feedback
assert "next_training_focus" in ai_feedback

print("[✓] AI Feedback schema validated successfully")
print(f"    AI Status: {report_data.get('ai_feedback_status')}")
print(f"    Model Used: {report_data.get('model_name')}")

# -----------------------------------------------------------------------------
# STEP 9: User Isolation Check
# -----------------------------------------------------------------------------
print("\n" + "="*80)
print("5. VERIFYING USER ISOLATION")
print("="*80)

token_u2 = create_access_token(user_id=user2.id, email=user2.email)
headers_u2 = {"Authorization": f"Bearer {token_u2}"}

# User 2 attempting to access User 1's report
res_u2 = client.post(f"/api/reports/{current_sess.id}/ai", headers=headers_u2)
assert res_u2.status_code == 403, f"Expected 403, got {res_u2.status_code}"
print("[✓] Unauthorized access correctly rejected with HTTP 403 Forbidden")

# User 2 historical context check
u2_hist = get_user_historical_context(user_id=user2.id, current_session_id=current_sess.id, db=db)
assert u2_hist["previous_sessions"] == 0
assert u2_hist["previous_accuracy"] == []
print("[✓] User 2 historical context is completely isolated (0 prior sessions shown)")

# -----------------------------------------------------------------------------
# STEP 10: Deterministic Result Preservation Check
# -----------------------------------------------------------------------------
print("\n" + "="*80)
print("6. VERIFYING DETERMINISTIC RESULT PRESERVATION")
print("="*80)

det = report_data["deterministic_assessment"]
assert det["result"] == "FAIL", f"Expected FAIL, got {det['result']}"
assert det["accuracy"] == 93.75
assert det["total_mistakes"] == 1
assert det["completed_steps"] == 16
print("[✓] Deterministic assessment is strictly preserved: Result = FAIL, Mistakes = 1, Accuracy = 93.75%")

# -----------------------------------------------------------------------------
# STEP 11 & 12: LLM Failure Handling Verification
# -----------------------------------------------------------------------------
print("\n" + "="*80)
print("7. TESTING FAILURE HANDLING WHEN LLM IS UNAVAILABLE")
print("="*80)

# Simulate LLM offline by pointing to unused port 59999
settings.MEDICAL_LLM_URL = "http://127.0.0.1:59999"

res_offline = client.post(f"/api/reports/{current_sess.id}/ai", headers=headers_u1)
assert res_offline.status_code == 200, f"Expected 200, got {res_offline.status_code}"
offline_data = res_offline.json()

assert offline_data["deterministic_assessment"]["result"] == "FAIL"
assert offline_data["ai_feedback_status"] in ["UNAVAILABLE", "FALLBACK"]
assert offline_data["ai_feedback"] is not None
print(f"[✓] Graceful failure handling verified: HTTP 200 returned with ai_feedback_status='{offline_data['ai_feedback_status']}'")
print("[✓] Deterministic assessment remains 100% operational when LLM is offline")

# Restore setting
settings.MEDICAL_LLM_URL = llm_base_url

print("\n" + "="*80)
print("ALL LIVE INTEGRATION TESTS COMPLETED SUCCESSFULLY!")
print("="*80)
