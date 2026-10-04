import io
import pytest
from datetime import datetime, timedelta
from pypdf import PdfReader
from fastapi.testclient import TestClient

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
from app.utils.security import create_access_token
from app.config.constants import STEPS


@pytest.fixture
def populated_portfolio_user(db_session, test_user_1):
    """
    Setup a user with realistic multi-session history:
    - Session 1: TRAINING (with mistake on step 7)
    - Session 2: TRAINING (clean 16/16)
    - Session 3: TEST (clean 16/16 - PASS)
    - Cumulative Weak Areas: Step 7
    - Adaptive Guidance Profile & Steps
    """
    u_id = test_user_1.id

    # 1. Session 1 (TRAINING)
    t1 = datetime.utcnow() - timedelta(days=2)
    s1 = TrainingSession(
        session_id="port-s1",
        user_id=u_id,
        session_type="TRAINING",
        session_number=1,
        start_time=t1,
        end_time=t1 + timedelta(minutes=4),
        total_time_seconds=145.0,
        status="COMPLETED"
    )
    db_session.add(s1)
    db_session.commit()
    db_session.refresh(s1)

    for i in range(16):
        db_session.add(StepPerformance(
            session_id=s1.id,
            step_id=i,
            step_name=STEPS[i],
            attempts=2 if i == 7 else 1,
            mistakes=1 if i == 7 else 0,
            first_attempt_correct=False if i == 7 else True,
            step_time_seconds=9.0,
            completed=True
        ))
    db_session.add(Mistake(session_id=s1.id, step_id=7, mistake_type="WRONG_OBJECT", attempt_number=1))
    db_session.add(TrainingReport(
        session_id=s1.id,
        user_id=u_id,
        session_number=1,
        total_steps=16,
        completed_steps=16,
        correct_steps=15,
        accuracy=93.75,
        total_attempts=17,
        total_mistakes=1,
        first_attempt_correct_count=15,
        first_attempt_accuracy=93.75,
        total_time_seconds=145.0,
        average_step_time_seconds=9.06,
        overall_result="SATISFACTORY"
    ))
    db_session.add(ProgressHistory(
        session_id=s1.id,
        user_id=u_id,
        session_number=1,
        accuracy=93.75,
        total_mistakes=1,
        total_attempts=17,
        total_time_seconds=145.0,
        completed_steps=16
    ))
    db_session.commit()

    # 2. Session 2 (TRAINING - Clean)
    t2 = datetime.utcnow() - timedelta(days=1)
    s2 = TrainingSession(
        session_id="port-s2",
        user_id=u_id,
        session_type="TRAINING",
        session_number=2,
        start_time=t2,
        end_time=t2 + timedelta(minutes=3),
        total_time_seconds=120.0,
        status="COMPLETED"
    )
    db_session.add(s2)
    db_session.commit()
    db_session.refresh(s2)

    for i in range(16):
        db_session.add(StepPerformance(
            session_id=s2.id,
            step_id=i,
            step_name=STEPS[i],
            attempts=1,
            mistakes=0,
            first_attempt_correct=True,
            step_time_seconds=7.5,
            completed=True
        ))
    db_session.add(TrainingReport(
        session_id=s2.id,
        user_id=u_id,
        session_number=2,
        total_steps=16,
        completed_steps=16,
        correct_steps=16,
        accuracy=100.0,
        total_attempts=16,
        total_mistakes=0,
        first_attempt_correct_count=16,
        first_attempt_accuracy=100.0,
        total_time_seconds=120.0,
        average_step_time_seconds=7.5,
        overall_result="EXCELLENT"
    ))
    db_session.add(ProgressHistory(
        session_id=s2.id,
        user_id=u_id,
        session_number=2,
        accuracy=100.0,
        total_mistakes=0,
        total_attempts=16,
        total_time_seconds=120.0,
        completed_steps=16
    ))
    db_session.commit()

    # 3. Session 3 (TEST - Clean PASS)
    t3 = datetime.utcnow() - timedelta(hours=2)
    s3 = TrainingSession(
        session_id="port-s3",
        user_id=u_id,
        session_type="TEST",
        session_number=3,
        start_time=t3,
        end_time=t3 + timedelta(minutes=3),
        total_time_seconds=110.0,
        status="COMPLETED"
    )
    db_session.add(s3)
    db_session.commit()
    db_session.refresh(s3)

    for i in range(16):
        db_session.add(StepPerformance(
            session_id=s3.id,
            step_id=i,
            step_name=STEPS[i],
            attempts=1,
            mistakes=0,
            first_attempt_correct=True,
            step_time_seconds=6.8,
            completed=True
        ))
    db_session.add(TestReport(
        session_id=s3.id,
        user_id=u_id,
        session_number=3,
        total_steps=16,
        completed_steps=16,
        correct_steps=16,
        accuracy=100.0,
        total_attempts=16,
        total_mistakes=0,
        first_attempt_correct_count=16,
        first_attempt_accuracy=100.0,
        total_time_seconds=110.0,
        average_step_time_seconds=6.88,
        result="PASS"
    ))
    db_session.add(ProgressHistory(
        session_id=s3.id,
        user_id=u_id,
        session_number=3,
        accuracy=100.0,
        total_mistakes=0,
        total_attempts=16,
        total_time_seconds=110.0,
        completed_steps=16
    ))
    db_session.commit()

    # 4. Cumulative Weak Area
    db_session.add(CumulativeWeakArea(
        user_id=u_id,
        step_id=7,
        step_name=STEPS[7],
        total_attempts=4,
        total_mistakes=1,
        mistake_ratio=25.0,
        severity="MEDIUM",
        rank=1,
        last_session_id=s1.id
    ))
    db_session.commit()

    # 5. Adaptive Guidance Profile & Steps
    prof = GuidanceProfile(
        user_id=u_id,
        profile_version=1,
        session_target=4
    )
    db_session.add(prof)
    db_session.commit()
    db_session.refresh(prof)

    for i in range(16):
        lev = "MEDIUM" if i == 7 else "LOW"
        msg = f"Be careful during {STEPS[i]}." if i == 7 else f"Perform {STEPS[i]} according to standard procedure."
        db_session.add(GuidanceStep(
            guidance_profile_id=prof.id,
            step_id=i,
            step_name=STEPS[i],
            guidance_level=lev,
            mistake_count=1 if i == 7 else 0,
            mistake_ratio=25.0 if i == 7 else 0.0,
            guidance_message=msg
        ))
    db_session.commit()

    return test_user_1


# =============================================================================
# 1. UNAUTHENTICATED REQUEST (401)
# =============================================================================
def test_dashboard_pdf_unauthenticated_401(client, test_user_1):
    res = client.get(f"/api/users/{test_user_1.id}/dashboard/pdf")
    assert res.status_code == 401


# =============================================================================
# 2. CROSS-USER FORBIDDEN (403)
# =============================================================================
def test_dashboard_pdf_cross_user_forbidden_403(client, test_user_1, auth_headers_user_2):
    res = client.get(f"/api/users/{test_user_1.id}/dashboard/pdf", headers=auth_headers_user_2)
    assert res.status_code == 403
    assert "You are not allowed to access this user's data" in res.json()["detail"]


# =============================================================================
# 3. NONEXISTENT USER (404)
# =============================================================================
def test_dashboard_pdf_nonexistent_user_404(client, db_session):
    nonexistent_id = 99999
    token = create_access_token(user_id=nonexistent_id, email="fake@medvr.org")
    # Even if token is signed with nonexistent_id, get_current_user rejects if not in DB
    res = client.get(f"/api/users/{nonexistent_id}/dashboard/pdf", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code in [401, 404]


# =============================================================================
# 4. PRISTINE USER WITH ZERO SESSIONS
# =============================================================================
def test_dashboard_pdf_empty_history_pristine_user(client, test_user_1, auth_headers_user_1):
    res = client.get(f"/api/users/{test_user_1.id}/dashboard/pdf", headers=auth_headers_user_1)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")

    reader = PdfReader(io.BytesIO(res.content))
    assert len(reader.pages) == 5
    text = "\n".join([p.extract_text() for p in reader.pages])
    assert "No recorded training sessions." in text
    assert "No recorded TEST sessions." in text
    assert "No cumulative weak areas identified from available history." in text
    assert "No active adaptive guidance available." in text


# =============================================================================
# 5. VALID POPULATED PORTFOLIO PDF
# =============================================================================
def test_dashboard_pdf_success_valid_pdf_structure(client, populated_portfolio_user, auth_headers_user_1):
    res = client.get(f"/api/users/{populated_portfolio_user.id}/dashboard/pdf", headers=auth_headers_user_1)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "attachment; filename=\"trainee_portfolio_1.pdf\"" in res.headers["content-disposition"]
    assert res.content.startswith(b"%PDF")
    assert len(res.content) > 2000

    reader = PdfReader(io.BytesIO(res.content))
    assert len(reader.pages) == 5
    text = "\n".join([p.extract_text() for p in reader.pages])

    # Header & Trainee Info
    assert "Medical VR — Venipuncture Training Portfolio" in text
    assert "Trainee One" in text
    assert "trainee1@example.com" in text


# =============================================================================
# 6. TEST VS TRAINING SEPARATION
# =============================================================================
def test_dashboard_pdf_test_training_separation(client, populated_portfolio_user, auth_headers_user_1):
    res = client.get(f"/api/users/{populated_portfolio_user.id}/dashboard/pdf", headers=auth_headers_user_1)
    assert res.status_code == 200
    reader = PdfReader(io.BytesIO(res.content))

    # Page 1 contains both snapshots visibly distinct
    page1_text = reader.pages[0].extract_text()
    assert "LATEST TEST RESULT: PASS" in page1_text
    assert "TRAINING STATUS: EXCELLENT" in page1_text
    assert "Authoritative deterministic test assessment result." in page1_text
    assert "Formative training evaluation status." in page1_text


# =============================================================================
# 7. CUMULATIVE WEAK AREAS RENDERED
# =============================================================================
def test_dashboard_pdf_cumulative_weak_areas_rendered(client, populated_portfolio_user, auth_headers_user_1):
    res = client.get(f"/api/users/{populated_portfolio_user.id}/dashboard/pdf", headers=auth_headers_user_1)
    assert res.status_code == 200
    reader = PdfReader(io.BytesIO(res.content))

    # Page 3 is Cumulative Weak Areas
    page3_text = reader.pages[2].extract_text()
    assert "CUMULATIVE WEAK AREAS — HISTORICAL" in page3_text
    assert "Take Cannula" in page3_text
    assert "25.0%" in page3_text
    assert "MEDIUM" in page3_text


# =============================================================================
# 8. ADAPTIVE GUIDANCE RENDERED
# =============================================================================
def test_dashboard_pdf_adaptive_guidance_rendered(client, populated_portfolio_user, auth_headers_user_1):
    res = client.get(f"/api/users/{populated_portfolio_user.id}/dashboard/pdf", headers=auth_headers_user_1)
    assert res.status_code == 200
    reader = PdfReader(io.BytesIO(res.content))

    # Page 4 is Adaptive Guidance
    page4_text = reader.pages[3].extract_text()
    assert "ADAPTIVE GUIDANCE / NEXT TRAINING FOCUS" in page4_text
    assert "Active Profile Version: 1" in page4_text
    assert "Curriculum Target Session: #4" in page4_text
    assert "Take Cannula" in page4_text
    assert "Be careful during Take Cannula." in page4_text


# =============================================================================
# 9. PARTIAL SESSION HANDLING
# =============================================================================
def test_dashboard_pdf_partial_session_handling(client, db_session, test_user_2, auth_headers_user_2):
    # Add a partial session: 2 of 16 completed
    sess_part = TrainingSession(
        session_id="port-part",
        user_id=test_user_2.id,
        session_type="TEST",
        session_number=1,
        start_time=datetime.utcnow(),
        status="COMPLETED"
    )
    db_session.add(sess_part)
    db_session.commit()

    db_session.add(StepPerformance(
        session_id=sess_part.id, step_id=0, step_name=STEPS[0],
        attempts=1, mistakes=0, first_attempt_correct=True,
        step_time_seconds=8.0, completed=True
    ))
    db_session.add(StepPerformance(
        session_id=sess_part.id, step_id=1, step_name=STEPS[1],
        attempts=1, mistakes=0, first_attempt_correct=True,
        step_time_seconds=8.0, completed=True
    ))
    db_session.add(TestReport(
        session_id=sess_part.id, user_id=test_user_2.id,
        session_number=1,
        total_steps=16, completed_steps=2, correct_steps=2,
        accuracy=12.5, total_attempts=2, total_mistakes=0,
        first_attempt_correct_count=2, first_attempt_accuracy=100.0,
        total_time_seconds=16.0, average_step_time_seconds=8.0,
        result="FAIL"
    ))
    db_session.add(ProgressHistory(
        session_id=sess_part.id, user_id=test_user_2.id,
        session_number=1, accuracy=12.5, total_mistakes=0,
        total_attempts=2, total_time_seconds=16.0, completed_steps=2
    ))
    db_session.commit()

    res = client.get(f"/api/users/{test_user_2.id}/dashboard/pdf", headers=auth_headers_user_2)
    assert res.status_code == 200
    reader = PdfReader(io.BytesIO(res.content))
    text = "\n".join([p.extract_text() for p in reader.pages])
    assert "2 / 16" in text
    assert "RESULT: FAIL" in text
    assert "16 / 16" not in text.split("Completed Steps:")[1].split()[0]  # Ensure not converted to 16/16


# =============================================================================
# 10. DETERMINISTIC IMMUTABILITY
# =============================================================================
def test_dashboard_pdf_deterministic_immutability(client, populated_portfolio_user, auth_headers_user_1, db_session):
    # Verify DB has PASS before PDF call
    tr = db_session.query(TestReport).filter(TestReport.user_id == populated_portfolio_user.id).first()
    assert tr.result == "PASS"
    assert tr.accuracy == 100.0

    res = client.get(f"/api/users/{populated_portfolio_user.id}/dashboard/pdf", headers=auth_headers_user_1)
    assert res.status_code == 200

    # Verify DB has PASS unchanged after PDF call
    tr_after = db_session.query(TestReport).filter(TestReport.user_id == populated_portfolio_user.id).first()
    assert tr_after.result == "PASS"
    assert tr_after.accuracy == 100.0
    assert tr_after.total_mistakes == 0


# =============================================================================
# 11. SUPERVISOR SIGN-OFF FIELDS
# =============================================================================
def test_dashboard_pdf_supervisor_signoff_fields(client, populated_portfolio_user, auth_headers_user_1):
    res = client.get(f"/api/users/{populated_portfolio_user.id}/dashboard/pdf", headers=auth_headers_user_1)
    assert res.status_code == 200
    reader = PdfReader(io.BytesIO(res.content))

    # Page 5 is Assessment History & Sign-off
    page5_text = reader.pages[4].extract_text()
    assert "CLINICAL SUPERVISOR / FACULTY MANUAL REVIEW" in page5_text
    assert "Reviewer Name:" in page5_text
    assert "Review Date:" in page5_text
    assert "Supervisor Signature:" in page5_text
    assert "Recommended for Clinical Observation" in page5_text


# =============================================================================
# 12. EXACT FIVE PAGES
# =============================================================================
def test_dashboard_pdf_exact_five_pages(client, populated_portfolio_user, auth_headers_user_1):
    res = client.get(f"/api/users/{populated_portfolio_user.id}/dashboard/pdf", headers=auth_headers_user_1)
    assert res.status_code == 200
    reader = PdfReader(io.BytesIO(res.content))
    assert len(reader.pages) == 5, f"Expected exactly 5 pages, got {len(reader.pages)}"


# =============================================================================
# 13. NO UNGROUNDED MASTERY CLAIMS
# =============================================================================
def test_dashboard_pdf_no_mastery_claims(client, populated_portfolio_user, auth_headers_user_1):
    res = client.get(f"/api/users/{populated_portfolio_user.id}/dashboard/pdf", headers=auth_headers_user_1)
    assert res.status_code == 200
    reader = PdfReader(io.BytesIO(res.content))
    text = "\n".join([p.extract_text() for p in reader.pages])
    assert "PROTOCOL MASTERED" not in text
    assert "CLINICALLY COMPETENT" not in text


# =============================================================================
# 14. EXISTING SESSION PDF REGRESSION UNAFFECTED
# =============================================================================
def test_existing_session_pdf_regression_unaffected(client, populated_portfolio_user, auth_headers_user_1, db_session):
    # Retrieve session 3 (TEST) and call individual session report endpoint
    sess3 = db_session.query(TrainingSession).filter(
        TrainingSession.user_id == populated_portfolio_user.id,
        TrainingSession.session_type == "TEST"
    ).first()
    assert sess3 is not None

    res = client.get(f"/api/reports/{sess3.id}/pdf", headers=auth_headers_user_1)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(res.content))
    assert len(reader.pages) >= 2
    text = "\n".join([p.extract_text() for p in reader.pages])
    assert "RESULT: PASS" in text
    assert "SECTION 5 — STEP PERFORMANCE" in text
    assert "SECTION 10 — FINAL SUMMARY" in text
