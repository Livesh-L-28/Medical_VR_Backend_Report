"""
tests/test_simulation_console.py
=================================
End-to-End and Integration tests for Phase 5A: Temporary Web Clinical Simulation Console.

Verifies the entire HTTP workflow required by Section 26 & Section 27:
- GET /ui route availability and HTML elements
- Scenario 1: Login -> Create TRAINING -> 16 steps -> Complete -> AI -> Download PDF
- Scenario 2: Login -> Create TEST -> 16 steps + mistake on Step 7 -> Complete -> Deterministic FAIL -> Download PDF
- Scenario 3: Login -> Create TEST -> 16 steps 0 mistakes -> Complete -> Deterministic PASS -> Download PDF
- Scenario 4: Login -> Create partial session (2/16) -> Complete -> Verify 2/16 and unreached steps -> Download PDF
- Scenario 5: LLM offline fallback -> Complete -> AI fallback used -> Download PDF
- Scenario 6: Multi-user isolation (User B forbidden from User A session, report, and portfolio PDF)
- Longitudinal portfolio PDF download via GET /api/users/{user_id}/dashboard/pdf
"""

import io
import pytest
from unittest.mock import patch
from pypdf import PdfReader


def test_ui_route_serves_simulation_console(client):
    """Verify GET /ui serves the Temporary Web Clinical Simulation Console HTML."""
    response = client.get("/ui")
    assert response.status_code == 200
    html = response.text
    assert "Medical VR Clinical Simulation Console" in html
    assert "Canonical Venipuncture Steps (0–15)" in html
    assert "POST /api/auth/login" in html or "handleLoginSubmit" in html
    assert "POST /api/mistakes/" in html or "submitRecordedMistake" in html
    assert "WRONG_OBJECT" in html
    assert "WRONG_ZONE" in html
    assert "INCORRECT_PLACEMENT" in html
    assert "downloadSessionPDF" in html
    assert "downloadPortfolioPDF" in html


def test_scenario_1_training_session_workflow(client, test_user_1):
    """
    Scenario 1:
    Login -> Create TRAINING -> Complete 16 steps -> Complete session -> Generate AI -> Download PDF
    """
    # 1. Login via POST /api/auth/login
    login_res = client.post(
        "/api/auth/login",
        data={"username": "trainee1@example.com", "password": "Password123!"}
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 2. Create TRAINING session
    sess_res = client.post(
        "/api/sessions/",
        json={"user_id": test_user_1.id, "session_type": "TRAINING", "session_number": 101},
        headers=auth_headers
    )
    assert sess_res.status_code == 200
    session_data = sess_res.json()
    session_id = session_data["id"]
    assert session_data["session_type"] == "TRAINING"
    assert session_data["status"] == "IN_PROGRESS"

    # 3. Simulate all 16 steps via batch telemetry
    batch_payload = [
        {
            "session_id": session_id,
            "step_id": i,
            "attempts": 1,
            "mistakes": 0,
            "first_attempt_correct": True,
            "step_time_seconds": 7.5,
            "completed": True
        }
        for i in range(16)
    ]
    batch_res = client.post(
        "/api/step-performance/batch",
        json=batch_payload,
        headers=auth_headers
    )
    assert batch_res.status_code == 200
    assert len(batch_res.json()) == 16

    # 4. Complete session
    comp_res = client.post(
        f"/api/sessions/{session_id}/complete",
        headers=auth_headers
    )
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "COMPLETED"

    # 5. Generate AI educational feedback
    ai_res = client.post(
        f"/api/reports/{session_id}/ai",
        headers=auth_headers
    )
    assert ai_res.status_code == 200
    ai_report = ai_res.json()
    assert "ai_feedback" in ai_report
    assert ai_report["session_type"] == "TRAINING"
    deter = ai_report["deterministic_assessment"]
    assert deter["completed_steps"] == 16
    assert deter["accuracy"] == 100.0

    # 6. Download Individual Session PDF
    pdf_res = client.get(
        f"/api/reports/{session_id}/pdf",
        headers=auth_headers
    )
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF")

    reader = PdfReader(io.BytesIO(pdf_res.content))
    assert len(reader.pages) == 2


def test_scenario_2_test_fail_with_mistake(client, test_user_1):
    """
    Scenario 2:
    Login -> Create TEST -> Complete 16 steps -> Record 1 mistake -> Complete session -> Verify deterministic FAIL -> Generate PDF
    """
    # 1. Login
    login_res = client.post(
        "/api/auth/login",
        data={"username": "trainee1@example.com", "password": "Password123!"}
    )
    token = login_res.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 2. Create TEST session
    sess_res = client.post(
        "/api/sessions/",
        json={"user_id": test_user_1.id, "session_type": "TEST", "session_number": 102},
        headers=auth_headers
    )
    session_id = sess_res.json()["id"]

    # 3. Record mistake on Step 7 (Take Cannula)
    mistake_res = client.post(
        "/api/mistakes/",
        json={
            "session_id": session_id,
            "step_id": 7,
            "mistake_type": "WRONG_OBJECT",
            "attempt_number": 1
        },
        headers=auth_headers
    )
    assert mistake_res.status_code == 200
    assert mistake_res.json()["mistake_type"] == "WRONG_OBJECT"

    # 4. Log all 16 steps (Step 7 had 2 attempts, 1 mistake, first_attempt_correct=False)
    batch_payload = []
    for i in range(16):
        is_err = (i == 7)
        batch_payload.append({
            "session_id": session_id,
            "step_id": i,
            "attempts": 2 if is_err else 1,
            "mistakes": 1 if is_err else 0,
            "first_attempt_correct": not is_err,
            "step_time_seconds": 15.0 if is_err else 7.0,
            "completed": True
        })
    batch_res = client.post(
        "/api/step-performance/batch",
        json=batch_payload,
        headers=auth_headers
    )
    assert batch_res.status_code == 200

    # 5. Complete session
    comp_res = client.post(
        f"/api/sessions/{session_id}/complete",
        headers=auth_headers
    )
    assert comp_res.status_code == 200

    # 6. Verify deterministic assessment returns FAIL
    ai_res = client.post(
        f"/api/reports/{session_id}/ai",
        headers=auth_headers
    )
    assert ai_res.status_code == 200
    report = ai_res.json()
    deter = report["deterministic_assessment"]
    assert deter["result"] == "FAIL"
    assert deter["total_mistakes"] == 1
    assert deter["completed_steps"] == 16

    # 7. Generate PDF and verify FAIL appears in the PDF
    pdf_res = client.get(
        f"/api/reports/{session_id}/pdf",
        headers=auth_headers
    )
    assert pdf_res.status_code == 200
    reader = PdfReader(io.BytesIO(pdf_res.content))
    pdf_text = "\n".join([page.extract_text() or "" for page in reader.pages])
    assert "FAIL" in pdf_text
    assert "WRONG_OBJECT" in pdf_text or "Take Cannula" in pdf_text


def test_scenario_3_test_pass_clean_procedure(client, test_user_1):
    """
    Scenario 3:
    Login -> Create TEST -> Complete 16 steps -> 0 mistakes -> Complete session -> Verify deterministic PASS -> Generate PDF
    """
    login_res = client.post(
        "/api/auth/login",
        data={"username": "trainee1@example.com", "password": "Password123!"}
    )
    token = login_res.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    sess_res = client.post(
        "/api/sessions/",
        json={"user_id": test_user_1.id, "session_type": "TEST", "session_number": 103},
        headers=auth_headers
    )
    session_id = sess_res.json()["id"]

    # Ingest 16 steps with 0 mistakes
    batch_payload = [
        {
            "session_id": session_id,
            "step_id": i,
            "attempts": 1,
            "mistakes": 0,
            "first_attempt_correct": True,
            "step_time_seconds": 6.8,
            "completed": True
        }
        for i in range(16)
    ]
    batch_res = client.post(
        "/api/step-performance/batch",
        json=batch_payload,
        headers=auth_headers
    )
    assert batch_res.status_code == 200

    comp_res = client.post(
        f"/api/sessions/{session_id}/complete",
        headers=auth_headers
    )
    assert comp_res.status_code == 200

    ai_res = client.post(
        f"/api/reports/{session_id}/ai",
        headers=auth_headers
    )
    assert ai_res.status_code == 200
    report = ai_res.json()
    deter = report["deterministic_assessment"]
    assert deter["result"] == "PASS"
    assert deter["total_mistakes"] == 0
    assert deter["completed_steps"] == 16
    assert deter["accuracy"] == 100.0

    pdf_res = client.get(
        f"/api/reports/{session_id}/pdf",
        headers=auth_headers
    )
    assert pdf_res.status_code == 200
    reader = PdfReader(io.BytesIO(pdf_res.content))
    pdf_text = "\n".join([page.extract_text() or "" for page in reader.pages])
    assert "PASS" in pdf_text


def test_scenario_4_partial_session_incomplete(client, test_user_1):
    """
    Scenario 4:
    Login -> Create partial session -> Complete 2 steps -> Complete session -> Verify 2/16 -> Verify unreached steps remain Not Reached -> Generate PDF
    """
    login_res = client.post(
        "/api/auth/login",
        data={"username": "trainee1@example.com", "password": "Password123!"}
    )
    token = login_res.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    sess_res = client.post(
        "/api/sessions/",
        json={"user_id": test_user_1.id, "session_type": "TEST", "session_number": 104},
        headers=auth_headers
    )
    session_id = sess_res.json()["id"]

    # Only complete Step 0 and Step 1
    for step_id in [0, 1]:
        res = client.post(
            "/api/step-performance/",
            json={
                "session_id": session_id,
                "step_id": step_id,
                "attempts": 1,
                "mistakes": 0,
                "first_attempt_correct": True,
                "step_time_seconds": 6.0,
                "completed": True
            },
            headers=auth_headers
        )
        assert res.status_code == 200

    # Complete session early
    comp_res = client.post(
        f"/api/sessions/{session_id}/complete",
        headers=auth_headers
    )
    assert comp_res.status_code == 200

    # Request report
    ai_res = client.post(
        f"/api/reports/{session_id}/ai",
        headers=auth_headers
    )
    assert ai_res.status_code == 200
    report = ai_res.json()
    deter = report["deterministic_assessment"]
    assert deter["completed_steps"] == 2
    assert deter["result"] == "FAIL"  # Incomplete test must fail deterministically

    # Verify step performances only contain 2 steps
    assert len(report["step_performance"]) == 2
    completed_ids = {sp["step_id"] for sp in report["step_performance"]}
    assert completed_ids == {0, 1}

    # Generate PDF and verify it compiles without error
    pdf_res = client.get(
        f"/api/reports/{session_id}/pdf",
        headers=auth_headers
    )
    assert pdf_res.status_code == 200
    reader = PdfReader(io.BytesIO(pdf_res.content))
    assert len(reader.pages) == 2


def test_scenario_5_llm_offline_fallback(client, test_user_1):
    """
    Scenario 5:
    LLM unavailable -> Complete session -> Request AI -> Verify fallback -> Verify PDF still generates
    """
    login_res = client.post(
        "/api/auth/login",
        data={"username": "trainee1@example.com", "password": "Password123!"}
    )
    token = login_res.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    sess_res = client.post(
        "/api/sessions/",
        json={"user_id": test_user_1.id, "session_type": "TEST", "session_number": 105},
        headers=auth_headers
    )
    session_id = sess_res.json()["id"]

    for i in range(16):
        client.post(
            "/api/step-performance/",
            json={
                "session_id": session_id,
                "step_id": i,
                "attempts": 1,
                "mistakes": 0,
                "first_attempt_correct": True,
                "step_time_seconds": 6.0,
                "completed": True
            },
            headers=auth_headers
        )

    client.post(f"/api/sessions/{session_id}/complete", headers=auth_headers)

    # Mock LLM client to simulate external service failure
    with patch("app.engines.llm_feedback_engine.medical_llm_client.send_evidence_payload", side_effect=RuntimeError("LLM Service Offline")):
        ai_res = client.post(
            f"/api/reports/{session_id}/ai",
            headers=auth_headers
        )
        assert ai_res.status_code == 200
        report = ai_res.json()
        assert report["ai_status"] in ["FALLBACK", "UNAVAILABLE"]
        assert report["ai_feedback"] is not None

        # Verify PDF still generates successfully
        pdf_res = client.get(
            f"/api/reports/{session_id}/pdf",
            headers=auth_headers
        )
        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"] == "application/pdf"


def test_scenario_6_multi_user_isolation(client, test_user_1, test_user_2, auth_headers_user_1, auth_headers_user_2):
    """
    Scenario 6:
    User A -> User A data accessible
    User B -> User A dashboard/session/PDF inaccessible (403 Forbidden)
    """
    # Create session for User A
    sess_res = client.post(
        "/api/sessions/",
        json={"user_id": test_user_1.id, "session_type": "TEST", "session_number": 106},
        headers=auth_headers_user_1
    )
    assert sess_res.status_code == 200
    user_a_sess_id = sess_res.json()["id"]

    # User B cannot complete User A's session
    b_comp = client.post(
        f"/api/sessions/{user_a_sess_id}/complete",
        headers=auth_headers_user_2
    )
    assert b_comp.status_code == 403

    # User A completes their session
    a_comp = client.post(
        f"/api/sessions/{user_a_sess_id}/complete",
        headers=auth_headers_user_1
    )
    assert a_comp.status_code == 200

    # User B cannot generate AI report for User A's session
    b_ai = client.post(
        f"/api/reports/{user_a_sess_id}/ai",
        headers=auth_headers_user_2
    )
    assert b_ai.status_code == 403

    # User B cannot download User A's session PDF
    b_pdf = client.get(
        f"/api/reports/{user_a_sess_id}/pdf",
        headers=auth_headers_user_2
    )
    assert b_pdf.status_code == 403

    # User B cannot view User A's longitudinal dashboard
    b_dash = client.get(
        f"/api/users/{test_user_1.id}/dashboard",
        headers=auth_headers_user_2
    )
    assert b_dash.status_code == 403

    # User B cannot download User A's longitudinal portfolio PDF
    b_dash_pdf = client.get(
        f"/api/users/{test_user_1.id}/dashboard/pdf",
        headers=auth_headers_user_2
    )
    assert b_dash_pdf.status_code == 403

    # User A CAN access their own longitudinal portfolio PDF
    a_dash_pdf = client.get(
        f"/api/users/{test_user_1.id}/dashboard/pdf",
        headers=auth_headers_user_1
    )
    assert a_dash_pdf.status_code == 200
    assert a_dash_pdf.headers["content-type"] == "application/pdf"
