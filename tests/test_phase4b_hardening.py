import json
import os
import pytest
import httpx
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.config.settings import settings
from app.services.medical_llm_client import MedicalLLMClient, medical_llm_client
from app.engines.llm_feedback_engine import request_llm_feedback
from app.database.models.session import TrainingSession
from app.database.models.step_performance import StepPerformance
from app.database.models.test_report import TestReport
from app.config.constants import STEPS


# =============================================================================
# TEST A — DEFAULT CONFIGURED MODEL IS RETURNED WHEN NO OVERRIDE SUPPLIED
# =============================================================================
@pytest.mark.asyncio
async def test_default_model_returned_when_no_override():
    """Verify that when no explicit model override is provided, configured default is returned."""
    evidence = {
        "session_type": "TEST",
        "current_assessment": {"result": "PASS", "accuracy": 100.0, "total_mistakes": 0, "total_steps": 16, "completed_steps": 16},
        "mistakes": [],
        "weak_areas": [],
        "historical_context": {}
    }

    mock_answer = json.dumps({
        "summary": "Standard performance summary.",
        "strengths": ["Perfect adherence"],
        "improvement_areas": [],
        "recommendations": ["Continue"],
        "progress_summary": "Initial trial",
        "next_training_focus": ["None"]
    })

    mock_response = httpx.Response(
        status_code=200,
        json={"question": "...", "answer": mock_answer},
        request=httpx.Request("POST", "http://127.0.0.1:8000/ask")
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        # 1. Direct client call
        raw_text, model_used = await medical_llm_client.send_evidence_payload(
            prompt="Test prompt",
            structured_evidence=evidence,
            model_name=None
        )
        assert model_used == settings.MEDICAL_LLM_MODEL
        assert model_used == "openbiollm"

        # 2. Engine call
        feedback, status, engine_model = await request_llm_feedback(evidence, model_name=None)
        assert status == "SUCCESS"
        assert engine_model == settings.MEDICAL_LLM_MODEL


# =============================================================================
# TEST B — EXPLICIT MODEL OVERRIDE RETURNED ACCURATELY (PHASE 4A FINDING FIX)
# =============================================================================
@pytest.mark.asyncio
async def test_explicit_model_override_returned_when_supplied():
    """Verify that when explicit model override is supplied, the requested model is returned."""
    evidence = {
        "session_type": "TEST",
        "current_assessment": {"result": "PASS", "accuracy": 100.0, "total_mistakes": 0, "total_steps": 16, "completed_steps": 16},
        "mistakes": [],
        "weak_areas": [],
        "historical_context": {}
    }

    mock_answer = json.dumps({
        "summary": "Llama performance summary.",
        "strengths": ["Fast execution"],
        "improvement_areas": [],
        "recommendations": ["Refine needle angle"],
        "progress_summary": "Progression noted",
        "next_training_focus": ["Take Cannula"]
    })

    mock_response = httpx.Response(
        status_code=200,
        json={"question": "...", "answer": mock_answer},
        request=httpx.Request("POST", "http://127.0.0.1:8000/ask")
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        # 1. Direct client call with "llama-3.2-3b"
        _, model_1 = await medical_llm_client.send_evidence_payload(
            prompt="Test prompt",
            structured_evidence=evidence,
            model_name="llama-3.2-3b"
        )
        assert model_1 == "llama-3.2-3b"

        # 2. Engine call with "llama-3.2-3b"
        feedback_1, status_1, engine_model_1 = await request_llm_feedback(evidence, model_name="llama-3.2-3b")
        assert status_1 == "SUCCESS"
        assert engine_model_1 == "llama-3.2-3b"

        # 3. Direct client call with "medical-transformer"
        _, model_2 = await medical_llm_client.send_evidence_payload(
            prompt="Test prompt",
            structured_evidence=evidence,
            model_name="medical-transformer"
        )
        assert model_2 == "medical-transformer"

        # 4. Engine call with "medical-transformer"
        feedback_2, status_2, engine_model_2 = await request_llm_feedback(evidence, model_name="medical-transformer")
        assert status_2 == "SUCCESS"
        assert engine_model_2 == "medical-transformer"


# =============================================================================
# TEST C — LLM FALLBACK PRESERVES REQUESTED MODEL ACROSS FAILURE MODES
# =============================================================================
@pytest.mark.asyncio
async def test_llm_fallback_preserves_requested_model_on_failures():
    """Verify that timeout, connection refusal, and malformed JSON preserve requested model name."""
    evidence = {
        "session_type": "TEST",
        "current_assessment": {"result": "FAIL", "accuracy": 75.0, "total_mistakes": 2, "total_steps": 16, "completed_steps": 16},
        "mistakes": [{"step_id": 7, "mistake_type": "WRONG_OBJECT"}],
        "weak_areas": [{"step_id": 7, "step_name": "Take Cannula", "severity": "HIGH", "mistakes": 1}],
        "historical_context": {}
    }

    override_model = "llama-3.2-3b"

    # 1. Timeout failure
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectTimeout("Connection timed out after 30s")
        feedback_to, status_to, model_to = await request_llm_feedback(evidence, model_name=override_model)
        assert status_to == "UNAVAILABLE"
        assert model_to == override_model
        assert evidence["current_assessment"]["result"] == "FAIL"

    # 2. Connection refused failure
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused at 127.0.0.1:8000")
        feedback_conn, status_conn, model_conn = await request_llm_feedback(evidence, model_name=override_model)
        assert status_conn == "UNAVAILABLE"
        assert model_conn == override_model
        assert evidence["current_assessment"]["result"] == "FAIL"

    # 3. Malformed JSON response
    mock_malformed = httpx.Response(
        status_code=200,
        json={"answer": "This is non-JSON unstructured text from LLM"},
        request=httpx.Request("POST", "http://127.0.0.1:8000/ask")
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_malformed
        feedback_mal, status_mal, model_mal = await request_llm_feedback(evidence, model_name=override_model)
        assert status_mal == "FALLBACK"
        assert model_mal == override_model
        assert evidence["current_assessment"]["result"] == "FAIL"


# =============================================================================
# TEST D — UNITY PORTFOLIO PDF HELPER AUDIT
# =============================================================================
def test_unity_portfolio_pdf_helper_code_structure():
    """
    Static verification of unity_assets/MedicalVRClient.cs for:
    - DownloadPortfolioPdf public method
    - DownloadPortfolioPdfRoutine private coroutine
    - Correct API route: /api/users/{userId}/dashboard/pdf
    - Correct Authorization header
    - Success and error callbacks
    """
    cs_path = os.path.join(os.path.dirname(__file__), "..", "unity_assets", "MedicalVRClient.cs")
    assert os.path.exists(cs_path), "MedicalVRClient.cs must exist"

    with open(cs_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Method declaration
    assert "public void DownloadPortfolioPdf(int userId, string destinationPath, Action<bool, string> onComplete = null)" in content
    # Coroutine declaration
    assert "private IEnumerator DownloadPortfolioPdfRoutine(int userId, string destinationPath, Action<bool, string> onComplete)" in content
    # URL construction
    assert 'string url = $"{serverBaseUrl}/api/users/{userId}/dashboard/pdf";' in content
    # Header attachment
    assert 'req.SetRequestHeader("Authorization", "Bearer " + jwtBearerToken);' in content
    # File write
    assert "System.IO.File.WriteAllBytes(destinationPath, req.downloadHandler.data);" in content
    # Success callback
    assert "onComplete?.Invoke(true, destinationPath);" in content
    # Failure callback
    assert "onComplete?.Invoke(false, req.error);" in content
