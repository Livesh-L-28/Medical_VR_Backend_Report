from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.user import User
from app.services.cumulative_weak_area_service import calculate_cumulative_weak_areas
from app.utils.auth import get_current_user


router = APIRouter(
    prefix="/api/cumulative-weak-areas",
    tags=["Cumulative Weak Areas"]
)


@router.post("/{user_id}")
def create_cumulative_weak_areas(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Security: user can access only their own data
    if user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to access this user's weak areas"
        )

    weak_areas = calculate_cumulative_weak_areas(
        user_id=user_id,
        db=db
    )

    return {
        "message": "Cumulative weak-area analysis generated successfully",
        "user_id": user_id,
        "weak_areas": [
            {
                "step_id": area.step_id,
                "step_name": area.step_name,
                "total_attempts": area.total_attempts,
                "total_mistakes": area.total_mistakes,
                "mistake_ratio": area.mistake_ratio,
                "severity": area.severity,
                "rank": area.rank,
                "last_session_id": area.last_session_id
            }
            for area in weak_areas
        ]
    }