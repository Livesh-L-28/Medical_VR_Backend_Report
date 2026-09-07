from typing import Optional, List
from pydantic import BaseModel


class DashboardUser(BaseModel):
    id: int
    name: str
    email: str


class DashboardTraining(BaseModel):
    session_id: int
    session_number: int
    total_steps: int
    completed_steps: int
    correct_steps: int
    accuracy: float
    total_attempts: int
    total_mistakes: int
    first_attempt_correct_count: int
    first_attempt_accuracy: float
    total_time_seconds: float
    average_step_time_seconds: float
    overall_result: str


class DashboardTest(BaseModel):
    session_id: int
    session_number: int
    total_steps: int
    completed_steps: int
    correct_steps: int
    accuracy: float
    total_attempts: int
    total_mistakes: int
    first_attempt_correct_count: int
    first_attempt_accuracy: float
    total_time_seconds: float
    average_step_time_seconds: float
    result: str


class DashboardProgress(BaseModel):
    session_id: int
    session_number: int
    accuracy: float
    total_mistakes: int
    total_attempts: int
    total_time_seconds: float
    completed_steps: int


class DashboardWeakArea(BaseModel):
    step_id: int
    step_name: str
    total_attempts: int
    total_mistakes: int
    mistake_ratio: float
    severity: str
    rank: int
    last_session_id: int


class DashboardGuidanceStep(BaseModel):
    step_id: int
    step_name: str
    guidance_level: str
    mistake_count: int
    mistake_ratio: float
    guidance_message: str


class DashboardGuidance(BaseModel):
    guidance_available: bool
    profile_id: Optional[int] = None
    profile_version: Optional[int] = None
    session_target: Optional[int] = None
    guidance: List[DashboardGuidanceStep]


class DashboardResponse(BaseModel):
    user: DashboardUser
    latest_training: Optional[DashboardTraining] = None
    latest_test: Optional[DashboardTest] = None
    progress: List[DashboardProgress]
    cumulative_weak_areas: List[DashboardWeakArea]
    adaptive_guidance: DashboardGuidance