import io
import json
import pytest
from unittest.mock import patch, AsyncMock
import httpx

from app.services.pdf_report_service import generate_assessment_pdf
from app.database.models.test_report import TestReport
from app.database.models.training_report import TrainingReport
from app.database.models.mistake import Mistake
from app.database.models.weak_area import WeakArea
from app.database.models.progress_history import ProgressHistory
from app.config.constants import STEPS


def test_1_pdf_generated_successfully(client, completed_test_session_pass, auth_headers_user_1):
    """1. Test that a PDF report is generated successfully with valid %PDF header and content."""
    res = client.get(
        f"/api/reports/{completed_test_session_pass.id}/pdf",
        headers=auth_headers_user_1
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "attachment; filename=" in res.headers["content-disposition"]
    assert res.content.startswith(b"%PDF")
    assert len(res.content) > 1000


def test_2_valid_test_report(client, completed_test_session_pass, auth_headers_user_1, db_session):
    """2. Test valid TEST report with deterministic PASS/FAIL result."""
    res = client.get(
        f"/api/reports/{completed_test_session_pass.id}/pdf",
        headers=auth_headers_user_1
    )
    assert res.status_code == 200
    assert res.content.startswith(b"%PDF")

    # Verify underlying test report has PASS
    test_rep = db_session.query(TestReport).filter(TestReport.session_id == completed_test_session_pass.id).first()
    assert test_rep is not None
    assert test_rep.result == "PASS"
    assert test_rep.accuracy == 100.0


def test_3_valid_training_report(client, completed_training_session, auth_headers_user_1, db_session):
    """3. Test valid TRAINING report with training evaluation status (EXCELLENT/SATISFACTORY)."""
    res = client.get(
        f"/api/reports/{completed_training_session.id}/pdf",
        headers=auth_headers_user_1
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")

    # Verify underlying training report has training status, not PASS/FAIL
    tr_rep = db_session.query(TrainingReport).filter(TrainingReport.session_id == completed_training_session.id).first()
    assert tr_rep is not None
    assert tr_rep.overall_result in ["EXCELLENT", "SATISFACTORY", "NEEDS_PRACTICE", "INCOMPLETE"]
    assert tr_rep.overall_result not in ["PASS", "FAIL"]


def test_4_report_with_mistakes():
    """4. Test PDF rendering when session contains deterministic mistakes."""
    user_info = {"id": 1, "name": "Trainee One"}
    session_info = {"session_id": 201, "session_number": 1, "session_type": "TEST", "user_id": 1}
    assessment_data = {
        "result": "FAIL",
        "accuracy": 87.5,
        "completed_steps": 16,
        "total_steps": 16,
        "total_mistakes": 2,
        "first_attempt_accuracy": 87.5,
        "total_time_seconds": 160.0,
        "average_step_time_seconds": 10.0
    }
    mistakes = [
        {"step_id": 7, "mistake_type": "WRONG_OBJECT", "attempt_number": 1},
        {"step_id": 11, "mistake_type": "WRONG_ZONE", "attempt_number": 2}
    ]

    pdf_buffer = generate_assessment_pdf(
        user_info=user_info,
        session_info=session_info,
        assessment_data=assessment_data,
        step_performance=[],
        mistakes=mistakes,
        weak_areas=[],
        historical_context={},
        ai_feedback=None,
        ai_status="NONE"
    )
    content = pdf_buffer.getvalue()
    assert content.startswith(b"%PDF")
    assert len(content) > 1000


def test_5_report_with_weak_areas():
    """5. Test PDF rendering when session contains identified weak areas."""
    user_info = {"id": 1, "name": "Trainee One"}
    session_info = {"session_id": 202, "session_number": 1, "session_type": "TEST", "user_id": 1}
    assessment_data = {
        "result": "FAIL",
        "accuracy": 81.25,
        "completed_steps": 15,
        "total_steps": 16,
        "total_mistakes": 3,
        "first_attempt_accuracy": 75.0,
        "total_time_seconds": 190.0,
        "average_step_time_seconds": 11.8
    }
    weak_areas = [
        {"step_id": 7, "step_name": "Take Cannula", "severity": "HIGH", "mistakes": 2, "attempts": 3, "mistake_ratio": 66.7},
        {"step_id": 8, "step_name": "Insert Cannula", "severity": "MEDIUM", "mistakes": 1, "attempts": 2, "mistake_ratio": 50.0}
    ]

    pdf_buffer = generate_assessment_pdf(
        user_info=user_info,
        session_info=session_info,
        assessment_data=assessment_data,
        step_performance=[],
        mistakes=[],
        weak_areas=weak_areas,
        historical_context={},
        ai_feedback=None,
        ai_status="NONE"
    )
    content = pdf_buffer.getvalue()
    assert content.startswith(b"%PDF")
    assert len(content) > 1000


def test_6_report_with_no_mistakes():
    """6. Test PDF rendering when session has 0 mistakes and 0 weak areas."""
    user_info = {"id": 1, "name": "Trainee One"}
    session_info = {"session_id": 203, "session_number": 1, "session_type": "TEST", "user_id": 1}
    assessment_data = {
        "result": "PASS",
        "accuracy": 100.0,
        "completed_steps": 16,
        "total_steps": 16,
        "total_mistakes": 0,
        "first_attempt_accuracy": 100.0,
        "total_time_seconds": 110.0,
        "average_step_time_seconds": 6.8
    }

    pdf_buffer = generate_assessment_pdf(
        user_info=user_info,
        session_info=session_info,
        assessment_data=assessment_data,
        step_performance=[],
        mistakes=[],
        weak_areas=[],
        historical_context={},
        ai_feedback=None,
        ai_status="NONE"
    )
    content = pdf_buffer.getvalue()
    assert content.startswith(b"%PDF")
    assert len(content) > 1000


def test_7_report_with_historical_data():
    """7. Test PDF rendering with rich user historical data and trend."""
    user_info = {"id": 1, "name": "Trainee One"}
    session_info = {"session_id": 204, "session_number": 4, "session_type": "TEST", "user_id": 1}
    assessment_data = {
        "result": "PASS",
        "accuracy": 93.75,
        "completed_steps": 16,
        "total_steps": 16,
        "total_mistakes": 1,
        "first_attempt_accuracy": 93.75,
        "total_time_seconds": 130.0,
        "average_step_time_seconds": 8.1
    }
    historical_context = {
        "previous_sessions": 3,
        "previous_accuracy": [55.0, 63.0, 71.0, 82.0],
        "previous_results": ["FAIL", "FAIL", "FAIL", "PASS"],
        "average_historical_accuracy": 67.75,
        "recurring_weak_areas": [
            {"step_id": 7, "step_name": "Take Cannula", "occurrences": 3}
        ]
    }

    pdf_buffer = generate_assessment_pdf(
        user_info=user_info,
        session_info=session_info,
        assessment_data=assessment_data,
        step_performance=[],
        mistakes=[],
        weak_areas=[],
        historical_context=historical_context,
        ai_feedback=None,
        ai_status="NONE"
    )
    content = pdf_buffer.getvalue()
    assert content.startswith(b"%PDF")
    assert len(content) > 1000


def test_8_report_without_historical_data():
    """8. Test PDF rendering when session is the first session with no history."""
    user_info = {"id": 1, "name": "Trainee One"}
    session_info = {"session_id": 205, "session_number": 1, "session_type": "TEST", "user_id": 1}
    assessment_data = {
        "result": "PASS",
        "accuracy": 100.0,
        "completed_steps": 16,
        "total_steps": 16,
        "total_mistakes": 0,
        "first_attempt_accuracy": 100.0,
        "total_time_seconds": 120.0,
        "average_step_time_seconds": 7.5
    }
    historical_context = {
        "previous_sessions": 0,
        "previous_accuracy": [],
        "previous_results": [],
        "recurring_weak_areas": []
    }

    pdf_buffer = generate_assessment_pdf(
        user_info=user_info,
        session_info=session_info,
        assessment_data=assessment_data,
        step_performance=[],
        mistakes=[],
        weak_areas=[],
        historical_context=historical_context,
        ai_feedback=None,
        ai_status="NONE"
    )
    content = pdf_buffer.getvalue()
    assert content.startswith(b"%PDF")


def test_9_report_with_ai_feedback():
    """9. Test PDF rendering with validated AI feedback and disclaimer banner."""
    user_info = {"id": 1, "name": "Trainee One"}
    session_info = {"session_id": 206, "session_number": 1, "session_type": "TEST", "user_id": 1}
    assessment_data = {
        "result": "PASS",
        "accuracy": 100.0,
        "completed_steps": 16,
        "total_steps": 16,
        "total_mistakes": 0,
        "first_attempt_accuracy": 100.0,
        "total_time_seconds": 120.0,
        "average_step_time_seconds": 7.5
    }
    ai_feedback = {
        "summary": "Trainee exhibited outstanding procedural compliance and sterile discipline.",
        "strengths": ["Completed 16/16 steps correctly", "Clean aseptic workflow"],
        "improvement_areas": [],
        "recommendations": ["Ready for clinical deployment"],
        "progress_summary": "Passed assessment with 100% accuracy on first attempt.",
        "next_training_focus": ["Pediatric and geriatric venipuncture simulations"]
    }

    pdf_buffer = generate_assessment_pdf(
        user_info=user_info,
        session_info=session_info,
        assessment_data=assessment_data,
        step_performance=[],
        mistakes=[],
        weak_areas=[],
        historical_context={},
        ai_feedback=ai_feedback,
        ai_status="SUCCESS",
        model_name="openbiollm"
    )
    content = pdf_buffer.getvalue()
    assert content.startswith(b"%PDF")
    assert len(content) > 1000


def test_10_report_when_llm_feedback_unavailable(client, completed_test_session_fail, auth_headers_user_1):
    """10. Test that PDF still generates when LLM is unavailable without modifying deterministic assessment."""
    # When no prior AI feedback is stored and LLM is offline, download_pdf_report generates a fallback
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        res = client.get(
            f"/api/reports/{completed_test_session_fail.id}/pdf",
            headers=auth_headers_user_1
        )
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/pdf"
        assert res.content.startswith(b"%PDF")


def test_11_unauthorized_report_access(client, completed_test_session_pass):
    """11. Test unauthorized report access without JWT token returns 401."""
    res = client.get(f"/api/reports/{completed_test_session_pass.id}/pdf")
    assert res.status_code == 401


def test_12_cross_user_report_access(client, completed_test_session_pass, auth_headers_user_2):
    """12. Test cross-user report access: User 2 cannot access User 1's report (403 Forbidden)."""
    res = client.get(
        f"/api/reports/{completed_test_session_pass.id}/pdf",
        headers=auth_headers_user_2
    )
    assert res.status_code == 403
    assert "Unauthorized" in res.json()["detail"]


def test_13_deterministic_pass_fail_unchanged(client, completed_test_session_fail, auth_headers_user_1, db_session):
    """13. Test that generating the PDF report leaves deterministic PASS/FAIL and mistakes unaltered."""
    # Read initial assessment
    initial_report = db_session.query(TestReport).filter(TestReport.session_id == completed_test_session_fail.id).first()
    assert initial_report is None  # not assessed yet

    # Request PDF download
    res = client.get(
        f"/api/reports/{completed_test_session_fail.id}/pdf",
        headers=auth_headers_user_1
    )
    assert res.status_code == 200

    # Verify deterministic report in database is strictly FAIL with 1 mistake
    final_report = db_session.query(TestReport).filter(TestReport.session_id == completed_test_session_fail.id).first()
    assert final_report is not None
    assert final_report.result == "FAIL"
    assert final_report.total_mistakes == 1
    assert final_report.completed_steps == 16
    assert final_report.accuracy == 93.75
