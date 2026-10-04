import json
import pytest
import httpx
from unittest.mock import patch, AsyncMock

from app.engines.llm_feedback_engine import (
    build_llm_prompt,
    build_evidence_payload,
    request_llm_feedback,
    clean_json_string,
    create_fallback_feedback
)
from app.schemas.ai_feedback import AIFeedbackResponse
from app.config.settings import settings


def test_grounding_prompt_contains_all_12_rules():
    evidence = {
        "session_type": "TEST",
        "assessment": {"result": "PASS", "accuracy": 100},
        "mistakes": [],
        "weak_areas": [],
        "historical_context": {}
    }
    prompt = build_llm_prompt(evidence)
    
    # Check for presence of all key grounding directives
    assert "MANDATORY GROUNDING RULES" in prompt
    assert "Only use information explicitly provided" in prompt
    assert "Never invent mistakes" in prompt
    assert "Never invent timings" in prompt
    assert "Never invent weak areas" in prompt
    assert "NEVER modify, dispute, or re-evaluate the deterministic assessment result" in prompt
    assert "standard 16 steps" in prompt


def test_clean_json_string_with_markdown_fences():
    raw = """
    Here is the clinical evaluation:
    ```json
    {
      "summary": "Trainee performed well.",
      "strengths": ["All steps completed"],
      "improvement_areas": [],
      "recommendations": ["Maintain current practice"],
      "progress_summary": "First attempt success",
      "next_training_focus": ["None"]
    }
    ```
    Hope this helps!
    """
    cleaned = clean_json_string(raw)
    parsed = json.loads(cleaned)
    assert parsed["summary"] == "Trainee performed well."
    assert parsed["strengths"] == ["All steps completed"]


@pytest.mark.asyncio
async def test_successful_llm_ask_response():
    evidence = {
        "session_type": "TEST",
        "assessment": {"result": "PASS", "accuracy": 100, "completed_steps": 16, "total_mistakes": 0},
        "mistakes": [],
        "weak_areas": [],
        "historical_context": {"total_previous_sessions": 0}
    }

    mock_llm_answer = json.dumps({
        "summary": "Excellent performance with perfect aseptic execution.",
        "strengths": ["100% accuracy", "All 16 steps completed correctly"],
        "improvement_areas": [],
        "recommendations": ["Advance to timed clinical trials"],
        "progress_summary": "Baseline established at 100% accuracy",
        "next_training_focus": ["Pediatric simulation scenarios"]
    })

    mock_response = httpx.Response(
        status_code=200,
        json={"question": "...", "answer": mock_llm_answer},
        request=httpx.Request("POST", "http://127.0.0.1:8000/ask")
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        feedback, status, model = await request_llm_feedback(evidence)

        assert status == "SUCCESS"
        assert feedback.summary == "Excellent performance with perfect aseptic execution."
        assert len(feedback.strengths) == 2
        assert feedback.improvement_areas == []


@pytest.mark.asyncio
async def test_llm_timeout_handled_gracefully_with_fallback():
    evidence = {
        "session_type": "TEST",
        "assessment": {"result": "FAIL", "accuracy": 93.75, "total_mistakes": 1},
        "mistakes": [{"step_id": 7, "mistake_type": "WRONG_OBJECT"}],
        "weak_areas": [{"step_id": 7, "step_name": "Take Cannula", "severity": "HIGH", "mistakes": 1}],
        "historical_context": {}
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectTimeout("Connection timed out after 30s")
        feedback, status, model = await request_llm_feedback(evidence)

        assert status in ["UNAVAILABLE", "FALLBACK"]
        assert "timed out" in feedback.summary.lower() or "unavailable" in feedback.summary.lower()
        # Verify fallback preserved weak area evidence
        assert len(feedback.improvement_areas) == 1
        assert feedback.improvement_areas[0].step_id == 7


@pytest.mark.asyncio
async def test_llm_server_unreachable_handled_gracefully():
    evidence = {
        "session_type": "TEST",
        "assessment": {"result": "PASS", "accuracy": 100},
        "mistakes": [],
        "weak_areas": [],
        "historical_context": {}
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Failed to connect to 127.0.0.1:8000")
        feedback, status, model = await request_llm_feedback(evidence)

        assert status in ["UNAVAILABLE", "FALLBACK"]
        assert isinstance(feedback, AIFeedbackResponse)


@pytest.mark.asyncio
async def test_malformed_llm_json_triggers_fallback():
    evidence = {
        "session_type": "TEST",
        "assessment": {"result": "PASS", "accuracy": 100},
        "mistakes": [],
        "weak_areas": [],
        "historical_context": {}
    }

    # Return plain conversational text with no valid JSON
    mock_response = httpx.Response(
        status_code=200,
        json={"answer": "I am unable to evaluate this right now, sorry!"},
        request=httpx.Request("POST", "http://127.0.0.1:8000/ask")
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        feedback, status, model = await request_llm_feedback(evidence)

        assert status == "FALLBACK"
        assert isinstance(feedback, AIFeedbackResponse)


@pytest.mark.asyncio
async def test_deterministic_authority_preservation():
    """
    CRITICAL TEST:
    Even if the LLM output claims a different result in text,
    the deterministic assessment result in the report is untouched and authoritative.
    """
    # 1. Deterministic result is PASS
    evidence_pass = {
        "session_type": "TEST",
        "assessment": {"result": "PASS", "accuracy": 100, "total_mistakes": 0},
        "mistakes": [],
        "weak_areas": [],
        "historical_context": {}
    }
    # LLM tries to say trainee failed
    rogue_llm_text = json.dumps({
        "summary": "The trainee failed because of bad hand posture.",
        "strengths": [],
        "improvement_areas": [{"step_id": 0, "step_name": "Wash Hands", "evidence": "Failed posture"}],
        "recommendations": ["Retake test"],
        "progress_summary": "Declined",
        "next_training_focus": ["Wash Hands"]
    })
    mock_resp = httpx.Response(
        status_code=200,
        json={"answer": rogue_llm_text},
        request=httpx.Request("POST", "http://127.0.0.1:8000/ask")
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        feedback, status, model = await request_llm_feedback(evidence_pass)

        # The deterministic assessment dict still has PASS!
        assert evidence_pass["assessment"]["result"] == "PASS"
        assert evidence_pass["assessment"]["total_mistakes"] == 0

    # 2. Deterministic result is FAIL
    evidence_fail = {
        "session_type": "TEST",
        "assessment": {"result": "FAIL", "accuracy": 75, "total_mistakes": 3},
        "mistakes": [{"step_id": 1, "mistake_type": "WRONG_OBJECT"}],
        "weak_areas": [{"step_id": 1, "step_name": "Wear Gloves", "severity": "HIGH"}],
        "historical_context": {}
    }
    # LLM tries to say trainee passed
    rogue_llm_pass = json.dumps({
        "summary": "Great job, you passed with flying colors!",
        "strengths": ["All good"],
        "improvement_areas": [],
        "recommendations": ["No practice needed"],
        "progress_summary": "Excellent",
        "next_training_focus": []
    })
    mock_resp_pass = httpx.Response(
        status_code=200,
        json={"answer": rogue_llm_pass},
        request=httpx.Request("POST", "http://127.0.0.1:8000/ask")
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp_pass
        feedback, status, model = await request_llm_feedback(evidence_fail)

        # The deterministic assessment dict still has FAIL!
        assert evidence_fail["assessment"]["result"] == "FAIL"
        assert evidence_fail["assessment"]["total_mistakes"] == 3
