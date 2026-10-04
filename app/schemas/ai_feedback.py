from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class AIFeedbackImprovementArea(BaseModel):
    step_id: int = Field(..., description="Step ID (0-15) where mistake occurred")
    step_name: str = Field(..., description="Name of the procedure step")
    evidence: str = Field(..., description="Grounded factual observation based strictly on session data")


class AIFeedbackResponse(BaseModel):
    summary: str = Field(..., description="Clinical training narrative summary of the performance")
    strengths: List[str] = Field(default_factory=list, description="Verified strong performance areas")
    improvement_areas: List[AIFeedbackImprovementArea] = Field(
        default_factory=list,
        description="Specific steps requiring corrective practice"
    )
    recommendations: List[str] = Field(default_factory=list, description="Targeted practice advice")
    progress_summary: str = Field(..., description="Comparison with historical trajectory")
    next_training_focus: List[str] = Field(default_factory=list, description="Recommended focus for next session")


class HistoricalContextSchema(BaseModel):
    previous_sessions: int = Field(0, description="Count of prior completed sessions")
    previous_accuracy: List[float] = Field(default_factory=list, description="List of previous accuracies")
    previous_results: List[str] = Field(default_factory=list, description="List of previous results")
    recurring_weak_areas: List[Dict[str, Any]] = Field(default_factory=list, description="Recurring weak steps")
    average_historical_accuracy: Optional[float] = Field(None, description="Mean of previous accuracies")


class AIReportResponse(BaseModel):
    report_id: Optional[int] = None
    session_id: int
    user_id: int
    session_type: str
    session_number: int
    deterministic_assessment: Dict[str, Any]
    assessment: Optional[Dict[str, Any]] = None
    step_performance: List[Dict[str, Any]] = Field(default_factory=list)
    mistakes: List[Dict[str, Any]] = Field(default_factory=list)
    weak_areas: List[Dict[str, Any]] = Field(default_factory=list)
    historical_context: Dict[str, Any] = Field(default_factory=dict)
    ai_feedback: Optional[AIFeedbackResponse] = None
    ai_feedback_status: str = Field("SUCCESS", description="SUCCESS | UNAVAILABLE | FALLBACK")
    ai_status: str = Field("SUCCESS", description="SUCCESS | UNAVAILABLE | FALLBACK")
    model_name: str = Field("openbiollm", description="Name of the LLM model used")
    disclaimer: str = Field(
        "The deterministic assessment engine is authoritative. "
        "The AI-generated feedback is for educational and explanatory purposes only.",
        description="Safety and authority disclaimer"
    )
