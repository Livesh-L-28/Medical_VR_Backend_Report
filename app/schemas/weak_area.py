from pydantic import BaseModel


class WeakAreaResponse(BaseModel):

    session_id: int
    step_id: int
    step_name: str
    attempts: int
    mistakes: int
    mistake_ratio: float
    severity: str
    rank: int

    class Config:
        from_attributes = True