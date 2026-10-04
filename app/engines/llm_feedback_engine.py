import json
import re
import logging
from typing import Dict, Any, Tuple, Optional

from app.schemas.ai_feedback import AIFeedbackResponse, AIFeedbackImprovementArea
from app.services.medical_llm_client import medical_llm_client, MedicalLLMClientError

logger = logging.getLogger(__name__)


GROUNDING_PROMPT_TEMPLATE = """You are an expert Clinical Venipuncture Training Evaluator.
Analyze the provided deterministic venipuncture simulation assessment and generate educational clinical feedback for the trainee.

==================================================
MANDATORY GROUNDING RULES (NEVER VIOLATE)
==================================================
1. Only use information explicitly provided in the input JSON below.
2. Never invent mistakes that are not in the 'mistakes' list.
3. Never invent timings or duration figures.
4. Never invent weak areas that are not in the 'weak_areas' list.
5. Never invent previous performance data not in 'historical_context'.
6. Never claim improvement unless historical evidence explicitly supports it.
7. TIMING GUARD: {timing_guard_rule}
8. Never invent clinical facts or procedure steps outside the standard 16 steps.
9. NEVER modify, dispute, or re-evaluate the deterministic assessment result (PASS/FAIL/status). The deterministic engine is the sole authority.
10. If evidence is insufficient for any observation, explicitly state that no conclusion can be established.
11. Keep all feedback professional, concise, and focused on venipuncture technique.
12. Do not provide patient-specific medical treatment advice.

==================================================
INPUT DATA (EVIDENCE CONTRACT)
==================================================
{evidence_json}

==================================================
REQUIRED OUTPUT FORMAT
==================================================
Respond with valid, parseable JSON ONLY. No intro text, markdown explanation, or conversation outside the JSON block.
Follow this exact JSON structure:
{{
  "summary": "<2-3 sentence clinical summary of current performance>",
  "strengths": [
    "<Verified strength 1 based strictly on correct steps/first-attempt success>",
    "<Verified strength 2>"
  ],
  "improvement_areas": [
    {{
      "step_id": <int>,
      "step_name": "<exact step name>",
      "evidence": "<factual mistake type and attempt description from the input>"
    }}
  ],
  "recommendations": [
    "<Targeted practical clinical recommendation 1>",
    "<Targeted practical clinical recommendation 2>"
  ],
  "progress_summary": "<Summary comparing current session against historical_context, or stating first session>",
  "next_training_focus": [
    "<Specific step or protocol action to focus on in next session>"
  ]
}}
"""


def build_evidence_payload(
    session_type: str,
    assessment_data: Dict[str, Any],
    step_performance: list,
    mistakes: list,
    weak_areas: list,
    historical_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Construct a clean, evidence-grounded input dictionary for the LLM following the API contract.
    Ensures evidence guard isolates only verified assessment facts.
    """
    # Detect whether duration/timing evidence is present
    total_time = assessment_data.get("total_time_seconds")
    avg_step_time = assessment_data.get("average_step_time_seconds")
    has_timing_data = bool((total_time is not None and total_time > 0) or (avg_step_time is not None and avg_step_time > 0))

    # Standardize historical context fields
    compact_history = {
        "previous_sessions": historical_context.get("previous_sessions", historical_context.get("total_previous_sessions", 0)),
        "previous_accuracy": historical_context.get("previous_accuracy", historical_context.get("previous_accuracy_trend", [])),
        "previous_results": historical_context.get("previous_results", []),
        "recurring_weak_areas": [
            {
                "step_id": wa.get("step_id"),
                "step_name": wa.get("step_name"),
                "occurrences": wa.get("occurrences", wa.get("prior_sessions_with_mistakes", 1))
            }
            for wa in historical_context.get("recurring_weak_areas", [])
        ]
    }

    current_assessment_payload = {
        "session_type": session_type,
        "total_steps": assessment_data.get("total_steps", 16),
        "completed_steps": assessment_data.get("completed_steps", 0),
        "correct_steps": assessment_data.get("correct_steps", 0),
        "accuracy": assessment_data.get("accuracy", 0.0),
        "total_attempts": assessment_data.get("total_attempts", 0),
        "total_mistakes": assessment_data.get("total_mistakes", 0),
        "first_attempt_correct_count": assessment_data.get("first_attempt_correct_count", 0),
        "first_attempt_accuracy": assessment_data.get("first_attempt_accuracy", 0.0),
        "total_time_seconds": total_time,
        "average_step_time_seconds": avg_step_time,
        "result": assessment_data.get("result") or assessment_data.get("overall_result", "EVALUATED")
    }

    return {
        "request_type": "assessment_feedback",
        "current_assessment": current_assessment_payload,
        "mistakes": mistakes,
        "weak_areas": weak_areas,
        "historical_context": compact_history,
        "timing_evidence_available": has_timing_data
    }


def build_llm_prompt(evidence: Dict[str, Any]) -> str:
    """Build the final grounding prompt incorporating the 12 strict rules and Timing Guard."""
    has_timing = evidence.get("timing_evidence_available", False)
    if has_timing:
        timing_rule = "Timing evidence is present in current_assessment. You may discuss efficiency and procedure pace based strictly on those duration figures."
    else:
        timing_rule = "TIMING EVIDENCE IS ABSENT. You must NOT discuss speed, efficiency, pace, or whether the trainee was fast or slow."

    evidence_str = json.dumps(evidence, indent=2, default=str)
    return GROUNDING_PROMPT_TEMPLATE.format(
        timing_guard_rule=timing_rule,
        evidence_json=evidence_str
    )


def clean_json_string(raw_text: str) -> str:
    """Extract valid JSON from potential markdown code fences or conversational text."""
    text = raw_text.strip()
    
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()
    
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace:last_brace + 1].strip()
    
    return text


def create_fallback_feedback(
    assessment_data: Dict[str, Any],
    weak_areas: list,
    reason: str = "Medical LLM feedback unavailable"
) -> AIFeedbackResponse:
    """Generate a clinically safe, deterministic fallback when LLM is unavailable or invalid."""
    result = assessment_data.get("result") or assessment_data.get("overall_result", "EVALUATED")
    accuracy = assessment_data.get("accuracy", 0.0)
    
    strengths = []
    if accuracy >= 80:
        strengths.append(f"High overall procedural accuracy achieved ({accuracy}%).")
    if assessment_data.get("first_attempt_accuracy", 0) >= 80:
        strengths.append("Strong first-attempt procedural execution.")
    if not strengths:
        strengths.append("Session telemetry successfully recorded by assessment engine.")

    improvement_areas = []
    for wa in weak_areas:
        improvement_areas.append(
            AIFeedbackImprovementArea(
                step_id=wa.get("step_id", 0),
                step_name=wa.get("step_name", "Unknown Step"),
                evidence=f"Recorded {wa.get('mistakes', wa.get('total_mistakes', 1))} mistake(s) (Severity: {wa.get('severity', 'MEDIUM')})"
            )
        )

    recommendations = []
    if weak_areas:
        recommendations.append("Prioritize review and guided practice on identified weak area steps.")
    else:
        recommendations.append("Continue standard venipuncture practice routines.")

    return AIFeedbackResponse(
        summary=(
            f"Deterministic Assessment Complete. Result: {result} with {accuracy}% accuracy. "
            f"({reason}. Deterministic assessment metrics remain fully authoritative.)"
        ),
        strengths=strengths,
        improvement_areas=improvement_areas,
        recommendations=recommendations,
        progress_summary="Performance metrics recorded into historical training profile.",
        next_training_focus=[
            wa.get("step_name", f"Step {wa.get('step_id')}") for wa in weak_areas
        ] if weak_areas else ["Maintain current aseptic technique and protocol timing."]
    )


async def request_llm_feedback(
    evidence: Dict[str, Any],
    model_name: Optional[str] = None
) -> Tuple[Optional[AIFeedbackResponse], str, str]:
    """
    Call the external Medical LLM API via MedicalLLMClient and return validated feedback.
    
    Returns:
        Tuple[Optional[AIFeedbackResponse], status ("SUCCESS" | "UNAVAILABLE" | "FALLBACK"), model_name]
    """
    prompt = build_llm_prompt(evidence)
    assessment = evidence.get("current_assessment", evidence.get("assessment", {}))
    weak_areas = evidence.get("weak_areas", [])

    try:
        raw_text, model_used = await medical_llm_client.send_evidence_payload(
            prompt=prompt,
            structured_evidence=evidence,
            model_name=model_name
        )

        cleaned = clean_json_string(raw_text)
        parsed = json.loads(cleaned)

        # Validate against Pydantic schema
        validated = AIFeedbackResponse.model_validate(parsed)
        return validated, "SUCCESS", model_used

    except MedicalLLMClientError as e:
        logger.warning(f"Medical LLM client error ({e.error_type}): {e.message}")
        status = "UNAVAILABLE" if e.error_type in ["CONNECTION_REFUSED", "TIMEOUT"] else "FALLBACK"
        fallback = create_fallback_feedback(
            assessment,
            weak_areas,
            reason=f"Medical LLM service {status.lower()} ({e.message})"
        )
        return fallback, status, (model_name or medical_llm_client.model_name)

    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Invalid LLM feedback format: {str(e)}")
        fallback = create_fallback_feedback(
            assessment,
            weak_areas,
            reason=f"Failed to parse LLM response as structured JSON: {str(e)}"
        )
        return fallback, "FALLBACK", (model_name or medical_llm_client.model_name)
