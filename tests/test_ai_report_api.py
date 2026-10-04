import json
import pytest
from unittest.mock import patch, AsyncMock
import httpx


def test_ai_report_unauthenticated_rejected(client, completed_test_session_pass):
    res = client.post(f"/api/reports/{completed_test_session_pass.id}/ai")
    assert res.status_code == 401


def test_ai_report_unauthorized_user_forbidden(
    client, completed_test_session_pass, auth_headers_user_2
):
    """User 2 cannot generate or view User 1's AI report."""
    res = client.post(
        f"/api/reports/{completed_test_session_pass.id}/ai",
        headers=auth_headers_user_2
    )
    assert res.status_code == 403
    assert "Unauthorized" in res.json()["detail"]


def test_ai_report_nonexistent_session_404(client, auth_headers_user_1):
    res = client.post("/api/reports/99999/ai", headers=auth_headers_user_1)
    assert res.status_code == 404


def test_ai_report_success_flow(
    client, completed_test_session_pass, auth_headers_user_1
):
    mock_llm_json = json.dumps({
        "summary": "Trainee demonstrated exemplary venipuncture technique.",
        "strengths": ["Completed 16/16 steps correctly", "Aseptic technique maintained"],
        "improvement_areas": [],
        "recommendations": ["Advance to next clinical stage"],
        "progress_summary": "First completed test session passed.",
        "next_training_focus": ["Timed cannula insertions"]
    })
    mock_response = httpx.Response(
        status_code=200,
        json={"question": "...", "answer": mock_llm_json},
        request=httpx.Request("POST", "http://127.0.0.1:8000/ask")
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        res = client.post(
            f"/api/reports/{completed_test_session_pass.id}/ai",
            headers=auth_headers_user_1
        )

        assert res.status_code == 200
        data = res.json()

        # Check Deterministic Assessment Section
        assert data["deterministic_assessment"]["result"] == "PASS"
        assert data["deterministic_assessment"]["accuracy"] == 100.0
        assert data["deterministic_assessment"]["total_mistakes"] == 0
        assert len(data["step_performance"]) == 16

        # Check AI Feedback Section
        assert data["ai_status"] == "SUCCESS"
        assert data["ai_feedback"]["summary"] == "Trainee demonstrated exemplary venipuncture technique."
        assert len(data["ai_feedback"]["strengths"]) == 2

        # Check Authority Disclaimer
        assert "deterministic assessment engine is authoritative" in data["disclaimer"].lower()


def test_ai_report_fallback_on_llm_offline(
    client, completed_test_session_fail, auth_headers_user_1
):
    """When LLM is offline, assessment report still returns 200 with fallback feedback."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        res = client.post(
            f"/api/reports/{completed_test_session_fail.id}/ai",
            headers=auth_headers_user_1
        )

        assert res.status_code == 200
        data = res.json()

        # Deterministic result is strictly FAIL
        assert data["deterministic_assessment"]["result"] == "FAIL"
        assert data["deterministic_assessment"]["total_mistakes"] == 1

        # AI Status is UNAVAILABLE or FALLBACK
        assert data["ai_status"] in ["UNAVAILABLE", "FALLBACK"]
        assert data["ai_feedback_status"] in ["UNAVAILABLE", "FALLBACK"]
        assert len(data["ai_feedback"]["improvement_areas"]) == 1
        assert data["ai_feedback"]["improvement_areas"][0]["step_id"] == 7


def test_pdf_report_download(
    client, completed_test_session_pass, auth_headers_user_1, auth_headers_user_2
):
    # User 2 forbidden
    res_forbidden = client.get(
        f"/api/reports/{completed_test_session_pass.id}/pdf",
        headers=auth_headers_user_2
    )
    assert res_forbidden.status_code == 403

    # User 1 succeeds
    res_success = client.get(
        f"/api/reports/{completed_test_session_pass.id}/pdf",
        headers=auth_headers_user_1
    )
    assert res_success.status_code == 200
    assert res_success.headers["content-type"] == "application/pdf"
    assert "attachment; filename=" in res_success.headers["content-disposition"]
    # Verify PDF magic bytes
    assert res_success.content.startswith(b"%PDF")
