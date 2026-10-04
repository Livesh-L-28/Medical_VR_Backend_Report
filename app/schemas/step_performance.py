from pydantic import BaseModel, ConfigDict


class StepPerformanceCreate(BaseModel):
    session_id: int
    step_id: int
    attempts: int
    mistakes: int
    first_attempt_correct: bool
    step_time_seconds: float
    completed: bool


class StepPerformanceResponse(BaseModel):
    id: int
    session_id: int
    step_id: int
    step_name: str
    attempts: int
    mistakes: int
    first_attempt_correct: bool
    step_time_seconds: float
    completed: bool

    model_config = ConfigDict(from_attributes=True)