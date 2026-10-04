import io
import json
import os
from datetime import datetime
from pypdf import PdfReader
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
from app.database.models.test_report import TestReport
from app.database.models.training_report import TrainingReport
from app.utils.security import hash_password, create_access_token
from app.config.constants import STEPS


def run_e2e_verification():
    print("=" * 70)
    print("STARTING END-TO-END VERIFICATION OF PDF REPORT GENERATION")
    print("=" * 70)

    # 1. Setup isolated in-memory DB and test client
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

    # 2. Create Users (User A and User B)
    user_a = User(
        name="Dr. Marcus Vance",
        email="marcus.vance@hospital.org",
        password_hash=hash_password("SecurePass123!")
    )
    user_b = User(
        name="Nurse Clara Oswald",
        email="clara.oswald@hospital.org",
        password_hash=hash_password("SecurePass123!")
    )
    db.add_all([user_a, user_b])
    db.commit()
    db.refresh(user_a)
    db.refresh(user_b)

    token_a = create_access_token(user_id=user_a.id, email=user_a.email)
    token_b = create_access_token(user_id=user_b.id, email=user_b.email)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    print(f"✓ Created Users: {user_a.name} (ID: {user_a.id}) & {user_b.name} (ID: {user_b.id})")

    # 3. Create Historical Session 1 (User A: TEST - FAIL with mistake on Step 7)
    s1 = TrainingSession(
        session_id="session-001-fail",
        user_id=user_a.id,
        session_type="TEST",
        session_number=1,
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        total_time_seconds=160.0,
        status="COMPLETED"
    )
    db.add(s1)
    db.commit()
    db.refresh(s1)

    for i in range(16):
        db.add(StepPerformance(
            session_id=s1.id,
            step_id=i,
            step_name=STEPS[i],
            attempts=2 if i == 7 else 1,
            mistakes=1 if i == 7 else 0,
            first_attempt_correct=False if i == 7 else True,
            step_time_seconds=10.0,
            completed=True
        ))
    db.add(Mistake(session_id=s1.id, step_id=7, mistake_type="WRONG_OBJECT", attempt_number=1))
    db.add(WeakArea(session_id=s1.id, step_id=7, step_name=STEPS[7], attempts=2, mistakes=1, mistake_ratio=50.0, severity="HIGH", rank=1))
    db.commit()

    # Pre-generate assessment for Session 1 so it appears in history
    from app.services.test_assessment_service import assess_test_session
    rep1 = assess_test_session(s1.id, db)
    print(f"✓ Created Session 1 (TEST): Result={rep1['result']}, Accuracy={rep1['accuracy']}%")

    # 4. Create Historical Session 2 (User A: TRAINING)
    s2 = TrainingSession(
        session_id="session-002-training",
        user_id=user_a.id,
        session_type="TRAINING",
        session_number=2,
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        total_time_seconds=140.0,
        status="COMPLETED"
    )
    db.add(s2)
    db.commit()
    db.refresh(s2)

    for i in range(16):
        db.add(StepPerformance(
            session_id=s2.id,
            step_id=i,
            step_name=STEPS[i],
            attempts=1,
            mistakes=0,
            first_attempt_correct=True,
            step_time_seconds=8.5,
            completed=True
        ))
    db.commit()
    from app.services.training_report_service import generate_training_report
    rep2 = generate_training_report(s2.id, db)
    print(f"✓ Created Session 2 (TRAINING): Status={rep2.overall_result}, Accuracy={rep2.accuracy}%")

    # 5. Create Current Session 3 (User A: TEST - PASS, perfect 16/16)
    s3 = TrainingSession(
        session_id="session-003-pass",
        user_id=user_a.id,
        session_type="TEST",
        session_number=3,
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        total_time_seconds=115.0,
        status="COMPLETED"
    )
    db.add(s3)
    db.commit()
    db.refresh(s3)

    for i in range(16):
        db.add(StepPerformance(
            session_id=s3.id,
            step_id=i,
            step_name=STEPS[i],
            attempts=1,
            mistakes=0,
            first_attempt_correct=True,
            step_time_seconds=7.1,
            completed=True
        ))
    db.commit()

    # 6. Call AI feedback endpoint for Session 3 with live Medical LLM
    print("\n--- Calling Live Medical LLM API for Session 3 ---")
    res_ai = client.post(f"/api/reports/{s3.id}/ai", headers=headers_a)
    assert res_ai.status_code == 200, f"AI generation failed: {res_ai.text}"
    ai_data = res_ai.json()
    print(f"✓ AI Report API Response Status: {res_ai.status_code}")
    print(f"✓ AI Feedback Status: {ai_data['ai_status']}")
    print(f"✓ Deterministic Result: {ai_data['deterministic_assessment']['result']}")
    print(f"✓ AI Summary: {ai_data['ai_feedback']['summary']}")
    assert ai_data['deterministic_assessment']['result'] == "PASS"

    # 7. Generate & Download PDF for Session 3
    print("\n--- Generating PDF Report for Session 3 (TEST - PASS) ---")
    res_pdf_3 = client.get(f"/api/reports/{s3.id}/pdf", headers=headers_a)
    assert res_pdf_3.status_code == 200
    assert res_pdf_3.headers["content-type"] == "application/pdf"
    assert res_pdf_3.content.startswith(b"%PDF")

    pdf_pass_path = "sample_test_pass_report.pdf"
    with open(pdf_pass_path, "wb") as f:
        f.write(res_pdf_3.content)
    print(f"✓ Saved PDF to disk: {pdf_pass_path} ({len(res_pdf_3.content)} bytes)")

    # Read and inspect PDF with pypdf
    reader_pass = PdfReader(pdf_pass_path)
    assert len(reader_pass.pages) >= 1
    extracted_text_pass = "\n".join([page.extract_text() or "" for page in reader_pass.pages])
    print(f"✓ Extracted {len(reader_pass.pages)} page(s) of content")

    # Verify all 10 sections exist in text
    sections_checked = [
        "Medical VR — Venipuncture Training",
        "Performance / Assessment Report",
        "SECTION 2 — TRAINEE INFORMATION",
        "Dr. Marcus Vance",
        "SECTION 3 — PERFORMANCE SUMMARY",
        "Total Steps: 16",
        "SECTION 4 — DETERMINISTIC RESULT",
        "RESULT: PASS",
        "SECTION 5 — STEP PERFORMANCE",
        "Wash Hands",
        "Dispose Cannula",
        "SECTION 6 — MISTAKES",
        "No mistakes recorded.",
        "SECTION 7 — WEAK AREAS",
        "Take Cannula",
        "SECTION 8 — HISTORICAL PROGRESS",
        "Previous Completed Sessions: 2",
        "AI-GENERATED TRAINING FEEDBACK",
        "AI-generated feedback is supplementary and does not determine assessment results.",
        "SECTION 10 — FINAL SUMMARY",
        "Deterministic Assessment Result: PASS"
    ]
    for sec in sections_checked:
        assert sec in extracted_text_pass, f"Expected '{sec}' in PDF, but was missing!"
        print(f"  ✓ Verified in PDF: {sec}")

    # 7b. Create pristine User C with zero mistakes ever to verify "No weak areas identified."
    user_c = User(
        name="Dr. Elena Rostova",
        email="elena.rostova@hospital.org",
        password_hash=hash_password("SecurePass123!")
    )
    db.add(user_c)
    db.commit()
    db.refresh(user_c)
    token_c = create_access_token(user_id=user_c.id, email=user_c.email)
    headers_c = {"Authorization": f"Bearer {token_c}"}

    s_c = TrainingSession(
        session_id="session-user-c-pass",
        user_id=user_c.id,
        session_type="TEST",
        session_number=1,
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        total_time_seconds=105.0,
        status="COMPLETED"
    )
    db.add(s_c)
    db.commit()
    db.refresh(s_c)
    for i in range(16):
        db.add(StepPerformance(
            session_id=s_c.id,
            step_id=i,
            step_name=STEPS[i],
            attempts=1,
            mistakes=0,
            first_attempt_correct=True,
            step_time_seconds=6.5,
            completed=True
        ))
    db.commit()

    res_pdf_c = client.get(f"/api/reports/{s_c.id}/pdf", headers=headers_c)
    assert res_pdf_c.status_code == 200
    pdf_c_path = "sample_pristine_user_pass_report.pdf"
    with open(pdf_c_path, "wb") as f:
        f.write(res_pdf_c.content)
    reader_c = PdfReader(pdf_c_path)
    extracted_text_c = "\n".join([page.extract_text() or "" for page in reader_c.pages])
    assert "No mistakes recorded." in extracted_text_c
    assert "No weak areas identified." in extracted_text_c
    assert "No previous historical session data recorded." in extracted_text_c
    print("  ✓ Verified 'No mistakes recorded.', 'No weak areas identified.', and 'No previous historical session data recorded.' for pristine user report.")


    # 8. Generate & Download PDF for Session 1 (TEST - FAIL)
    print("\n--- Generating PDF Report for Session 1 (TEST - FAIL) ---")
    res_pdf_1 = client.get(f"/api/reports/{s1.id}/pdf", headers=headers_a)
    assert res_pdf_1.status_code == 200
    pdf_fail_path = "sample_test_fail_report.pdf"
    with open(pdf_fail_path, "wb") as f:
        f.write(res_pdf_1.content)
    print(f"✓ Saved PDF to disk: {pdf_fail_path} ({len(res_pdf_1.content)} bytes)")

    reader_fail = PdfReader(pdf_fail_path)
    extracted_text_fail = "\n".join([page.extract_text() or "" for page in reader_fail.pages])
    assert "RESULT: FAIL" in extracted_text_fail
    assert "WRONG_OBJECT" in extracted_text_fail
    assert "Take Cannula" in extracted_text_fail
    print("  ✓ Verified FAIL result, WRONG_OBJECT mistake, and Take Cannula weak area in FAIL report.")

    # 9. Generate & Download PDF for Session 2 (TRAINING)
    print("\n--- Generating PDF Report for Session 2 (TRAINING) ---")
    res_pdf_2 = client.get(f"/api/reports/{s2.id}/pdf", headers=headers_a)
    assert res_pdf_2.status_code == 200
    pdf_train_path = "sample_training_report.pdf"
    with open(pdf_train_path, "wb") as f:
        f.write(res_pdf_2.content)
    print(f"✓ Saved PDF to disk: {pdf_train_path} ({len(res_pdf_2.content)} bytes)")

    reader_train = PdfReader(pdf_train_path)
    extracted_text_train = "\n".join([page.extract_text() or "" for page in reader_train.pages])
    assert "TRAINING STATUS: EXCELLENT" in extracted_text_train or "TRAINING STATUS: SATISFACTORY" in extracted_text_train
    assert "Session Type: TRAINING" in extracted_text_train
    print("  ✓ Verified TRAINING session type and evaluation status (no PASS/FAIL).")

    # 10. Security Checks (Authentication & Authorization)
    print("\n--- Testing Security Controls ---")
    # 10a. Unauthenticated request
    res_unauth = client.get(f"/api/reports/{s3.id}/pdf")
    assert res_unauth.status_code == 401, f"Expected 401, got {res_unauth.status_code}"
    print("  ✓ Unauthenticated access correctly rejected (401)")

    # 10b. Cross-user access (User B requesting User A's session report)
    res_cross = client.get(f"/api/reports/{s3.id}/pdf", headers=headers_b)
    assert res_cross.status_code == 403, f"Expected 403, got {res_cross.status_code}"
    print("  ✓ Cross-user access correctly rejected (403 Forbidden)")

    # 11. Deterministic Assessment Immutability Check
    print("\n--- Checking Deterministic Immutability ---")
    db_rep3 = db.query(TestReport).filter(TestReport.session_id == s3.id).first()
    assert db_rep3.result == "PASS"
    assert db_rep3.accuracy == 100.0
    assert db_rep3.total_mistakes == 0
    assert db_rep3.completed_steps == 16
    print("  ✓ Database TestReport record for Session 3 is strictly PASS, 100% accuracy, 0 mistakes.")

    db_rep1 = db.query(TestReport).filter(TestReport.session_id == s1.id).first()
    assert db_rep1.result == "FAIL"
    assert db_rep1.total_mistakes == 1
    print("  ✓ Database TestReport record for Session 1 is strictly FAIL, 1 mistake.")

    print("\n" + "=" * 70)
    print("ALL END-TO-END PDF VERIFICATION CHECKS PASSED PERFECTLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_e2e_verification()
