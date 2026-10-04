import io
import json
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

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def get_test_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

fastapi_app.dependency_overrides[get_db] = get_test_db

client = TestClient(fastapi_app)
db = TestingSessionLocal()

# 1. Create Trainee User
user = User(
    name="Dr. Alex Rivera",
    email="alex.rivera@medvr.org",
    password_hash=hash_password("Pass1234!")
)
db.add(user)
db.commit()
db.refresh(user)

token = create_access_token(user_id=user.id, email=user.email)
auth_headers = {"Authorization": f"Bearer {token}"}

print("\n=======================================================")
print("[1] HEALTH CHECK")
print("=======================================================")
res_health = client.get("/health")
print("GET /health ->", res_health.status_code, res_health.json())

print("\n=======================================================")
print("[2] TEST PASS REPORT GENERATION WITH AI FEEDBACK")
print("=======================================================")
sess_pass = TrainingSession(
    session_id="session-demo-pass",
    user_id=user.id,
    session_type="TEST",
    session_number=1,
    start_time=datetime.utcnow(),
    end_time=datetime.utcnow(),
    total_time_seconds=120.0,
    status="COMPLETED"
)
db.add(sess_pass)
db.commit()
db.refresh(sess_pass)

for i in range(16):
    sp = StepPerformance(
        session_id=sess_pass.id,
        step_id=i,
        step_name=STEPS[i],
        attempts=1,
        mistakes=0,
        first_attempt_correct=True,
        step_time_seconds=7.5,
        completed=True
    )
    db.add(sp)
db.commit()

res_ai_pass = client.post(f"/api/reports/{sess_pass.id}/ai", headers=auth_headers)
print(f"POST /api/reports/{sess_pass.id}/ai -> Status: {res_ai_pass.status_code}")
print(json.dumps(res_ai_pass.json(), indent=2))

print("\n=======================================================")
print("[3] TEST FAIL REPORT GENERATION WITH AI FEEDBACK")
print("=======================================================")
sess_fail = TrainingSession(
    session_id="session-demo-fail",
    user_id=user.id,
    session_type="TEST",
    session_number=2,
    start_time=datetime.utcnow(),
    end_time=datetime.utcnow(),
    total_time_seconds=150.0,
    status="COMPLETED"
)
db.add(sess_fail)
db.commit()
db.refresh(sess_fail)

for i in range(16):
    sp = StepPerformance(
        session_id=sess_fail.id,
        step_id=i,
        step_name=STEPS[i],
        attempts=2 if i == 7 else 1,
        mistakes=1 if i == 7 else 0,
        first_attempt_correct=False if i == 7 else True,
        step_time_seconds=9.0,
        completed=True
    )
    db.add(sp)

m_fail = Mistake(
    session_id=sess_fail.id,
    step_id=7,
    mistake_type="WRONG_OBJECT",
    attempt_number=1
)
db.add(m_fail)
db.commit()

res_ai_fail = client.post(f"/api/reports/{sess_fail.id}/ai", headers=auth_headers)
print(f"POST /api/reports/{sess_fail.id}/ai -> Status: {res_ai_fail.status_code}")
print(json.dumps(res_ai_fail.json(), indent=2))

print("\n=======================================================")
print("[4] TRAINING REPORT GENERATION WITH AI FEEDBACK")
print("=======================================================")
sess_train = TrainingSession(
    session_id="session-demo-training",
    user_id=user.id,
    session_type="TRAINING",
    session_number=3,
    start_time=datetime.utcnow(),
    end_time=datetime.utcnow(),
    total_time_seconds=45.0,
    status="COMPLETED"
)
db.add(sess_train)
db.commit()
db.refresh(sess_train)

for i in range(5):
    sp = StepPerformance(
        session_id=sess_train.id,
        step_id=i,
        step_name=STEPS[i],
        attempts=1,
        mistakes=0,
        first_attempt_correct=True,
        step_time_seconds=9.0,
        completed=True
    )
    db.add(sp)
db.commit()

res_ai_train = client.post(f"/api/reports/{sess_train.id}/ai", headers=auth_headers)
print(f"POST /api/reports/{sess_train.id}/ai -> Status: {res_ai_train.status_code}")
print(json.dumps(res_ai_train.json(), indent=2))

print("\n=======================================================")
print("[5] PDF DOWNLOAD VERIFICATION")
print("=======================================================")
res_pdf = client.get(f"/api/reports/{sess_pass.id}/pdf", headers=auth_headers)
print(f"GET /api/reports/{sess_pass.id}/pdf -> Status: {res_pdf.status_code}")
print(f"Content-Type: {res_pdf.headers.get('content-type')}")
print(f"Content-Disposition: {res_pdf.headers.get('content-disposition')}")
print(f"PDF Header: {res_pdf.content[:10]}")
assert res_pdf.content.startswith(b"%PDF")
print("PDF successfully generated and verified!")
print("=======================================================\n")
