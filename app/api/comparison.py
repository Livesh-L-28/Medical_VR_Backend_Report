from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.user import User
from app.services.comparison_service import compare_training_sessions
from app.utils.auth import get_current_user


router = APIRouter(
    prefix="/api/comparison",
    tags=["Training Comparison"]
)


@router.get("/{user_id}/{session_1_number}/{session_2_number}")
def get_training_comparison(
    user_id: int,
    session_1_number: int,
    session_2_number: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    if user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to access this user's comparison"
        )

    comparison = compare_training_sessions(
        user_id,
        session_1_number,
        session_2_number,
        db
    )

    if comparison is None:
        raise HTTPException(
            status_code=404,
            detail="One or both training sessions not found"
        )

    return comparison