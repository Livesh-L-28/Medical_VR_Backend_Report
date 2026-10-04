import json
import pytest
from unittest.mock import patch, AsyncMock

from app.services.medical_llm_client import MedicalLLMClient, MedicalLLMClientError
from app.engines.llm_feedback_engine import (
    build_evidence_payload,
    build_llm_prompt,
    request_llm_feedback
)
from app.services.historical_context_service import get_user_historical_context


# ==============================================================================
# TEST A: Successful LLM response
# ==============================================================================
@pytest.mark.asyncio
async def test_a_successful_llm_response():
    evidence = build_evidence_payload(
        session_type="TEST",
        assessment_data={"result": "PASS", "accuracy": 100.0, "total_time_seconds": 120.0},
        step_performance=[],
        mistakes=[],
        weak_areas=[],
        historical_context={}
    )
    valid_llm_json = json.dumps({
        "summary": "Trainee demonstrated exemplary protocol execution.",
        "strengths": ["100% correct steps", "Maintained sterility"],
        "improvement_areas": [],
        "recommendations": ["Proceed to live clinical observation"],
        "progress_summary": "First attempt passed successfully",
        "next_training_focus": ["Pediatric venipuncture"]
    })

    with patch.object(MedicalLLMClient, "send_evidence_payload", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (valid_llm_json, "openbiollm")

        feedback, status, model = await request_llm_feedback(evidence)
        assert status == "SUCCESS"
        assert model == "openbiollm"
        assert feedback.summary == "Trainee demonstrated exemplary protocol execution."
        assert len(feedback.strengths) == 2


# ==============================================================================
# TEST B: LLM timeout
# ==============================================================================
@pytest.mark.asyncio
async def test_b_llm_timeout():
    evidence = build_evidence_payload(
        session_type="TEST",
        assessment_data={"result": "PASS", "accuracy": 100.0},
        step_performance=[],
        mistakes=[],
        weak_areas=[],
        historical_context={}
    )

    with patch.object(MedicalLLMClient, "send_evidence_payload", new_callable=AsyncMock) as mock_send:
        mock_send.side_effect = MedicalLLMClientError(
            message="Connection to Medical LLM server timed out after 30s",
            error_type="TIMEOUT"
        )

        feedback, status, model = await request_llm_feedback(evidence)
        assert status == "UNAVAILABLE"
        assert "unavailable" in feedback.summary.lower() or "timed out" in feedback.summary.lower()


# ==============================================================================
# TEST C: LLM unavailable (Connection refused / server down)
# ==============================================================================
@pytest.mark.asyncio
async def test_c_llm_unavailable():
    evidence = build_evidence_payload(
        session_type="TEST",
        assessment_data={"result": "FAIL", "accuracy": 87.5},
        step_performance=[],
        mistakes=[{"step_id": 7, "mistake_type": "WRONG_OBJECT"}],
        weak_areas=[{"step_id": 7, "step_name": "Take Cannula", "severity": "HIGH", "mistakes": 1}],
        historical_context={}
    )

    with patch.object(MedicalLLMClient, "send_evidence_payload", new_callable=AsyncMock) as mock_send:
        mock_send.side_effect = MedicalLLMClientError(
            message="Unable to connect to Medical LLM server at http://127.0.0.1:8000/ask",
            error_type="CONNECTION_REFUSED"
        )

        feedback, status, model = await request_llm_feedback(evidence)
        assert status == "UNAVAILABLE"
        assert len(feedback.improvement_areas) == 1
        assert feedback.improvement_areas[0].step_id == 7


# ==============================================================================
# TEST D: Invalid JSON from LLM
# ==============================================================================
@pytest.mark.asyncio
async def test_d_invalid_json():
    evidence = build_evidence_payload(
        session_type="TEST",
        assessment_data={"result": "PASS", "accuracy": 100.0},
        step_performance=[],
        mistakes=[],
        weak_areas=[],
        historical_context={}
    )

    with patch.object(MedicalLLMClient, "send_evidence_payload", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = ("Here is my response but it is not JSON at all!", "openbiollm")

        feedback, status, model = await request_llm_feedback(evidence)
        assert status == "FALLBACK"
        assert feedback is not None
        assert "parse" in feedback.summary.lower() or "unavailable" in feedback.summary.lower()


# ==============================================================================
# TEST E: Invalid feedback schema (Missing required fields)
# ==============================================================================
@pytest.mark.asyncio
async def test_e_invalid_feedback_schema():
    evidence = build_evidence_payload(
        session_type="TEST",
        assessment_data={"result": "PASS", "accuracy": 100.0},
        step_performance=[],
        mistakes=[],
        weak_areas=[],
        historical_context={}
    )

    # Valid JSON, but missing required fields 'summary' and 'progress_summary'
    incomplete_json = json.dumps({
        "strengths": ["Good gloves donned"],
        "recommendations": ["Do more practice"]
    })

    with patch.object(MedicalLLMClient, "send_evidence_payload", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (incomplete_json, "openbiollm")

        feedback, status, model = await request_llm_feedback(evidence)
        assert status == "FALLBACK"
        assert feedback is not None
        assert feedback.summary is not None


# ==============================================================================
# TEST F: User / Session Authorization
# ==============================================================================
def test_f_user_session_authorization(client, completed_test_session_pass, auth_headers_user_2):
    # Unauthenticated
    res_unauth = client.post(f"/api/reports/{completed_test_session_pass.id}/ai")
    assert res_unauth.status_code == 401

    # Unauthorized user (User 2 requesting User 1's report)
    res_forbidden = client.post(
        f"/api/reports/{completed_test_session_pass.id}/ai",
        headers=auth_headers_user_2
    )
    assert res_forbidden.status_code == 403
    assert "Unauthorized" in res_forbidden.json()["detail"]


# ==============================================================================
# TEST G: Historical Context Isolation
# ==============================================================================
def test_g_historical_context_isolation(db_session, test_user_1, test_user_2):
    from datetime import datetime
    from app.database.models.session import TrainingSession

    # Session for User 1
    s1 = TrainingSession(
        session_id="sec-u1",
        user_id=test_user_1.id,
        session_type="TRAINING",
        session_number=1,
        start_time=datetime.utcnow(),
        status="COMPLETED"
    )
    db_session.add(s1)

    # Session for User 2
    s2 = TrainingSession(
        session_id="sec-u2",
        user_id=test_user_2.id,
        session_type="TRAINING",
        session_number=1,
        start_time=datetime.utcnow(),
        status="IN_PROGRESS"
    )
    db_session.add(s2)
    db_session.commit()

    u2_history = get_user_historical_context(
        user_id=test_user_2.id,
        current_session_id=s2.id,
        db=db_session
    )
    # User 2 MUST see 0 previous sessions
    assert u2_history["previous_sessions"] == 0
    assert u2_history["previous_accuracy"] == []


# ==============================================================================
# TEST H: Deterministic PASS Preserved
# ==============================================================================
@pytest.mark.asyncio
async def test_h_deterministic_pass_preserved():
    evidence = build_evidence_payload(
        session_type="TEST",
        assessment_data={"result": "PASS", "accuracy": 100.0, "total_mistakes": 0},
        step_performance=[],
        mistakes=[],
        weak_areas=[],
        historical_context={}
    )

    # LLM hallucinates and claims failure
    rogue_llm_json = json.dumps({
        "summary": "Trainee failed the exam due to hesitation.",
        "strengths": [],
        "improvement_areas": [{"step_id": 0, "step_name": "Wash Hands", "evidence": "Hesitation"}],
        "recommendations": ["Re-do entire course"],
        "progress_summary": "Unsatisfactory",
        "next_training_focus": ["Wash Hands"]
    })

    with patch.object(MedicalLLMClient, "send_evidence_payload", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (rogue_llm_json, "openbiollm")

        feedback, status, model = await request_llm_feedback(evidence)
        # Authoritative assessment data remains unchanged!
        assert evidence["current_assessment"]["result"] == "PASS"
        assert evidence["current_assessment"]["accuracy"] == 100.0
        assert evidence["current_assessment"]["total_mistakes"] == 0


# ==============================================================================
# TEST I: Deterministic FAIL Preserved
# ==============================================================================
@pytest.mark.asyncio
async def test_i_deterministic_fail_preserved():
    evidence = build_evidence_payload(
        session_type="TEST",
        assessment_data={"result": "FAIL", "accuracy": 80.0, "total_mistakes": 2},
        step_performance=[],
        mistakes=[{"step_id": 7, "mistake_type": "WRONG_OBJECT"}],
        weak_areas=[{"step_id": 7, "step_name": "Take Cannula", "severity": "HIGH"}],
        historical_context={}
    )

    # LLM hallucinates and claims pass
    rogue_pass_json = json.dumps({
        "summary": "Congratulations! You passed the venipuncture test!",
        "strengths": ["All good"],
        "improvement_areas": [],
        "recommendations": ["Ready for clinical work"],
        "progress_summary": "Passed with honors",
        "next_training_focus": []
    })

    with patch.object(MedicalLLMClient, "send_evidence_payload", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (rogue_pass_json, "openbiollm")

        feedback, status, model = await request_llm_feedback(evidence)
        # Authoritative assessment data remains strictly FAIL!
        assert evidence["current_assessment"]["result"] == "FAIL"
        assert evidence["current_assessment"]["total_mistakes"] == 2


# ==============================================================================
# TEST J: Timing Evidence Correctly Passed
# ==============================================================================
def test_j_timing_evidence_correctly_passed():
    evidence = build_evidence_payload(
        session_type="TEST",
        assessment_data={
            "result": "PASS",
            "accuracy": 100.0,
            "total_time_seconds": 120.0,
            "average_step_time_seconds": 7.5
        },
        step_performance=[],
        mistakes=[],
        weak_areas=[],
        historical_context={}
    )
    assert evidence["timing_evidence_available"] is True
    prompt = build_llm_prompt(evidence)
    # The prompt must permit efficiency discussion based on timing numbers
    assert "Timing evidence is present" in prompt
    assert "You may discuss efficiency" in prompt


# ==============================================================================
# TEST K: No Timing Evidence Means No Speed Claim
# ==============================================================================
def test_k_no_timing_evidence_means_no_speed_claim():
    evidence = build_evidence_payload(
        session_type="TEST",
        assessment_data={
            "result": "PASS",
            "accuracy": 100.0,
            "total_time_seconds": None,
            "average_step_time_seconds": None
        },
        step_performance=[],
        mistakes=[],
        weak_areas=[],
        historical_context={}
    )
    assert evidence["timing_evidence_available"] is False
    prompt = build_llm_prompt(evidence)
    # The prompt must explicitly forbid speed/efficiency claims
    assert "TIMING EVIDENCE IS ABSENT" in prompt
    assert "You must NOT discuss speed, efficiency, pace" in prompt
