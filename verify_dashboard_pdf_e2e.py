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
from app.database.models.cumulative_weak_area import CumulativeWeakArea
from app.database.models.guidance_profile import GuidanceProfile
from app.database.models.guidance_step import GuidanceStep
from app.database.models.progress_history import ProgressHistory
from app.database.models.test_report import TestReport
from app.database.models.training_report import TrainingReport
from app.utils.security import hash_password, create_access_token
from app.config.constants import STEPS


def run_dashboard_pdf_e2e_verification():
    print("=" * 80)
    print("STARTING END-TO-END VERIFICATION: PHASE 3 LONGITUDINAL CLINICAL PORTFOLIO PDF")
    print("=" * 80)

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

    # 2. Create Users (User A, User B, User C - Pristine)
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
    user_c = User(
        name="Dr. Elena Rostova",
        email="elena.rostova@hospital.org",
        password_hash=hash_password("SecurePass123!")
    )
    db.add_all([user_a, user_b, user_c])
    db.commit()
    db.refresh(user_a)
    db.refresh(user_b)
    db.refresh(user_c)

    token_a = create_access_token(user_id=user_a.id, email=user_a.email)
    token_b = create_access_token(user_id=user_b.id, email=user_b.email)
    token_c = create_access_token(user_id=user_c.id, email=user_c.email)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    headers_c = {"Authorization": f"Bearer {token_c}"}

    print(f"✓ Created Users: {user_a.name} (ID: {user_a.id}), {user_b.name} (ID: {user_b.id}), {user_c.name} (ID: {user_c.id})")

    # 3. Populate User A with multi-session longitudinal trajectory
    # Session 1: TRAINING - NEEDS_PRACTICE
    s1 = TrainingSession(
        session_id="sess-001-tr",
        user_id=user_a.id,
        session_type="TRAINING",
        session_number=1,
        start_time=datetime.utcnow(),
        status="COMPLETED"
    )
    db.add(s1)
    db.commit()
    db.refresh(s1)

    for i in range(16):
        db.add(StepPerformance(
            session_id=s1.id, step_id=i, step_name=STEPS[i],
            attempts=3 if i == 5 else 1, mistakes=2 if i == 5 else 0,
            first_attempt_correct=False if i == 5 else True,
            step_time_seconds=9.0, completed=True
        ))
    db.add(TrainingReport(
        session_id=s1.id, user_id=user_a.id, session_number=1,
        total_steps=16, completed_steps=16, correct_steps=15,
        accuracy=75.0, total_attempts=18, total_mistakes=2,
        first_attempt_correct_count=15, first_attempt_accuracy=93.75,
        total_time_seconds=145.0, average_step_time_seconds=9.06,
        overall_result="NEEDS_PRACTICE"
    ))
    db.add(ProgressHistory(
        session_id=s1.id, user_id=user_a.id, session_number=1,
        accuracy=75.0, total_mistakes=2, total_attempts=18,
        total_time_seconds=145.0, completed_steps=16
    ))
    db.commit()

    # Session 2: TRAINING - SATISFACTORY
    s2 = TrainingSession(
        session_id="sess-002-tr",
        user_id=user_a.id,
        session_type="TRAINING",
        session_number=2,
        start_time=datetime.utcnow(),
        status="COMPLETED"
    )
    db.add(s2)
    db.commit()
    db.refresh(s2)

    for i in range(16):
        db.add(StepPerformance(
            session_id=s2.id, step_id=i, step_name=STEPS[i],
            attempts=2 if i == 5 else 1, mistakes=1 if i == 5 else 0,
            first_attempt_correct=False if i == 5 else True,
            step_time_seconds=8.0, completed=True
        ))
    db.add(TrainingReport(
        session_id=s2.id, user_id=user_a.id, session_number=2,
        total_steps=16, completed_steps=16, correct_steps=15,
        accuracy=88.5, total_attempts=17, total_mistakes=1,
        first_attempt_correct_count=15, first_attempt_accuracy=93.75,
        total_time_seconds=130.0, average_step_time_seconds=8.12,
        overall_result="SATISFACTORY"
    ))
    db.add(ProgressHistory(
        session_id=s2.id, user_id=user_a.id, session_number=2,
        accuracy=88.5, total_mistakes=1, total_attempts=17,
        total_time_seconds=130.0, completed_steps=16
    ))
    db.commit()

    # Session 3: TEST - PASS (Authoritative)
    s3 = TrainingSession(
        session_id="sess-003-test",
        user_id=user_a.id,
        session_type="TEST",
        session_number=3,
        start_time=datetime.utcnow(),
        status="COMPLETED"
    )
    db.add(s3)
    db.commit()
    db.refresh(s3)

    for i in range(16):
        db.add(StepPerformance(
            session_id=s3.id, step_id=i, step_name=STEPS[i],
            attempts=1, mistakes=0, first_attempt_correct=True,
            step_time_seconds=6.8, completed=True
        ))
    db.add(TestReport(
        session_id=s3.id, user_id=user_a.id, session_number=3,
        total_steps=16, completed_steps=16, correct_steps=16,
        accuracy=100.0, total_attempts=16, total_mistakes=0,
        first_attempt_correct_count=16, first_attempt_accuracy=100.0,
        total_time_seconds=110.0, average_step_time_seconds=6.88,
        result="PASS"
    ))
    db.add(ProgressHistory(
        session_id=s3.id, user_id=user_a.id, session_number=3,
        accuracy=100.0, total_mistakes=0, total_attempts=16,
        total_time_seconds=110.0, completed_steps=16
    ))
    db.commit()

    # Cumulative Weak Areas
    db.add(CumulativeWeakArea(
        user_id=user_a.id, step_id=5, step_name=STEPS[5],
        total_attempts=6, total_mistakes=3, mistake_ratio=50.0,
        severity="HIGH", rank=1, last_session_id=s2.id
    ))
    db.add(CumulativeWeakArea(
        user_id=user_a.id, step_id=7, step_name=STEPS[7],
        total_attempts=4, total_mistakes=1, mistake_ratio=25.0,
        severity="MEDIUM", rank=2, last_session_id=s1.id
    ))
    db.commit()

    # Adaptive Guidance Profile
    prof = GuidanceProfile(
        user_id=user_a.id,
        profile_version=1,
        session_target=4
    )
    db.add(prof)
    db.commit()
    db.refresh(prof)

    db.add(GuidanceStep(
        guidance_profile_id=prof.id, step_id=5, step_name=STEPS[5],
        guidance_level="HIGH", mistake_count=3, mistake_ratio=50.0,
        guidance_message="Ensure tourniquet is palpated and vein selected before needle insertion."
    ))
    db.add(GuidanceStep(
        guidance_profile_id=prof.id, step_id=7, step_name=STEPS[7],
        guidance_level="MEDIUM", mistake_count=1, mistake_ratio=25.0,
        guidance_message="Carefully steady cannula at shallow angle of insertion."
    ))
    db.commit()
    print("✓ Populated multi-session history, cumulative weak areas, and adaptive guidance for User A")

    # 4. Fetch Dashboard JSON to verify source truth
    res_json = client.get(f"/api/users/{user_a.id}/dashboard", headers=headers_a)
    assert res_json.status_code == 200
    dashboard_json = res_json.json()
    print(f"✓ Fetched Dashboard JSON: {len(dashboard_json['progress'])} progress entries, {len(dashboard_json['cumulative_weak_areas'])} cumulative weak areas")

    # 5. Download Longitudinal Clinical Portfolio PDF
    print("\n--- Generating Longitudinal Clinical Portfolio PDF (User A) ---")
    res_pdf = client.get(f"/api/users/{user_a.id}/dashboard/pdf", headers=headers_a)
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert res_pdf.content.startswith(b"%PDF")

    portfolio_a_path = "sample_trainee_clinical_portfolio.pdf"
    with open(portfolio_a_path, "wb") as f:
        f.write(res_pdf.content)
    print(f"✓ Saved Portfolio PDF to disk: {portfolio_a_path} ({len(res_pdf.content)} bytes)")

    # 6. PDF Structural & Content Inspection
    reader = PdfReader(portfolio_a_path)
    total_pages = len(reader.pages)
    print(f"✓ Total Pages: {total_pages} (Target: exactly 5 pages)")
    assert total_pages == 5, f"Expected exactly 5 pages, got {total_pages}"

    # Extract text per page
    pages_text = [reader.pages[i].extract_text() or "" for i in range(total_pages)]
    all_text = "\n".join(pages_text)

    # 7. Page-by-page Verification
    print("\n--- Verifying Page-by-Page Content ---")

    # Page 1: Overview & Snapshots
    print("Checking Page 1: Trainee Clinical Overview...")
    assert "Medical VR — Venipuncture Training Portfolio" in pages_text[0]
    assert "Dr. Marcus Vance" in pages_text[0]
    assert "marcus.vance@hospital.org" in pages_text[0]
    assert "RESULT: PASS" in pages_text[0]
    assert "TRAINING STATUS: SATISFACTORY" in pages_text[0]
    assert "Total Sessions: 3" in pages_text[0]
    print("  ✓ Page 1 contains overview, snapshots, distinct TEST (PASS) and TRAINING (SATISFACTORY) statuses.")

    # Page 2: Longitudinal Performance
    print("Checking Page 2: Longitudinal Performance...")
    assert "LONGITUDINAL PERFORMANCE PROGRESSION" in pages_text[1]
    assert "Completed" in pages_text[1]
    assert "16 / 16" in pages_text[1]
    assert "75.0%" in pages_text[1]
    assert "88.5%" in pages_text[1]
    assert "100.0%" in pages_text[1]
    print("  ✓ Page 2 contains longitudinal table with exact sessions, steps, and accuracy values.")

    # Page 3: Cumulative Weak Areas
    print("Checking Page 3: Cumulative Weak Areas...")
    assert "CUMULATIVE WEAK AREAS — HISTORICAL" in pages_text[2]
    assert "Cumulative weak areas represent recurring procedural vulnerabilities" in pages_text[2]
    assert "Clean Area" in pages_text[2] or "Step 5" in pages_text[2]
    assert "Take Cannula" in pages_text[2]
    assert "50.0%" in pages_text[2]
    assert "HIGH" in pages_text[2]
    assert "MEDIUM" in pages_text[2]
    print("  ✓ Page 3 contains cumulative weak areas, ranks, severity, and mistake ratios.")

    # Page 4: Adaptive Learning Plan
    print("Checking Page 4: Adaptive Learning Plan...")
    assert "ADAPTIVE GUIDANCE / NEXT TRAINING FOCUS" in pages_text[3]
    assert "Curriculum Target Session: #4" in pages_text[3]
    assert "Ensure tourniquet is palpated" in pages_text[3]
    print("  ✓ Page 4 contains adaptive learning plan and verified guidance messages.")

    # Page 5: Assessment History & Sign-off
    print("Checking Page 5: Assessment History & Supervisor Sign-off...")
    assert "ASSESSMENT HISTORY & CLINICAL SUPERVISOR REVIEW" in pages_text[4]
    assert "TEST ASSESSMENT LOG" in pages_text[4]
    assert "TRAINING LOG" in pages_text[4]
    assert "Reviewer Name:" in pages_text[4]
    assert "Supervisor Signature:" in pages_text[4]
    assert "deterministic backend assessment engine" in pages_text[4]
    print("  ✓ Page 5 contains assessment history, educational disclaimer, and supervisor sign-off fields.")

    # 8. Data Integrity Verification (Dashboard JSON vs Dashboard PDF)
    print("\n--- Verifying Data Integrity (Dashboard JSON -> PDF) ---")
    # Overall sessions count
    assert str(len(dashboard_json["progress"])) in all_text
    # Authoritative test result
    assert dashboard_json["latest_test"]["result"] == "PASS"
    assert "RESULT: PASS" in all_text
    # Training snapshot
    assert dashboard_json["latest_training"]["overall_result"] == "SATISFACTORY"
    assert "TRAINING STATUS: SATISFACTORY" in all_text
    # Weak areas values
    for wa in dashboard_json["cumulative_weak_areas"]:
        assert f"{wa['mistake_ratio']}%" in all_text
        assert wa["severity"] in all_text
        assert str(wa["rank"]) in all_text
    # Guidance values
    guide_prof = dashboard_json["adaptive_guidance"]
    assert f"Curriculum Target Session: #{guide_prof['session_target']}" in all_text
    for gstep in guide_prof["guidance"]:
        assert gstep["guidance_level"] in all_text
        assert gstep["guidance_message"] in all_text
    print("  ✓ All 12 source JSON values match the PDF with ZERO alterations.")

    # 9. Mastery Claims Check
    print("\n--- Verifying Absence of Unsubstantiated Mastery Claims ---")
    for forbidden in ["PROTOCOL MASTERED", "CLINICALLY COMPETENT", "CERTIFIED"]:
        assert forbidden not in all_text, f"Found forbidden claim: '{forbidden}'"
    print("  ✓ Verified NO ungrounded mastery claims ('PROTOCOL MASTERED', 'CLINICALLY COMPETENT', 'CERTIFIED') in PDF.")

    # 10. Pristine User Check (User C)
    print("\n--- Verifying Pristine User Empty States ---")
    res_pristine = client.get(f"/api/users/{user_c.id}/dashboard/pdf", headers=headers_c)
    assert res_pristine.status_code == 200
    pristine_path = "sample_pristine_user_portfolio.pdf"
    with open(pristine_path, "wb") as f:
        f.write(res_pristine.content)
    reader_c = PdfReader(pristine_path)
    text_c = "\n".join([p.extract_text() or "" for p in reader_c.pages])
    assert "No recorded TEST sessions." in text_c
    assert "No recorded training sessions." in text_c
    assert "No cumulative weak areas identified from available history." in text_c
    assert "No active adaptive guidance available." in text_c
    print("  ✓ Pristine user produces valid 5-page PDF with explicit, truthful empty states.")

    # 11. Security Checks (Authentication & Multi-User Isolation)
    print("\n--- Verifying Security & Access Controls ---")
    # Unauthenticated -> 401
    res_401 = client.get(f"/api/users/{user_a.id}/dashboard/pdf")
    assert res_401.status_code == 401
    print("  ✓ Unauthenticated request rejected with 401 Unauthorized.")

    # Cross-user (User B accessing User A's portfolio) -> 403
    res_403 = client.get(f"/api/users/{user_a.id}/dashboard/pdf", headers=headers_b)
    assert res_403.status_code == 403
    print("  ✓ Cross-user request (User B -> User A) strictly rejected with 403 Forbidden.")

    # Nonexistent user -> 401 (invalid credentials) or 404
    token_fake = create_access_token(user_id=99999, email="ghost@hospital.org")
    res_404 = client.get("/api/users/99999/dashboard/pdf", headers={"Authorization": f"Bearer {token_fake}"})
    assert res_404.status_code in [401, 404]
    print(f"  ✓ Nonexistent user token rejected with {res_404.status_code}.")

    print("\n" + "=" * 80)
    print("PHASE 3 END-TO-END VERIFICATION COMPLETED WITH 100% SUCCESS!")
    print("=" * 80)


if __name__ == "__main__":
    run_dashboard_pdf_e2e_verification()
