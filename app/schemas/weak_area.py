from pydantic import BaseModel, ConfigDict


class WeakAreaResponse(BaseModel):

    session_id: int
    step_id: int
    step_name: str
    attempts: int
    mistakes: int
    mistake_ratio: float
    severity: str
    rank: int

    model_config = ConfigDict(from_attributes=True)