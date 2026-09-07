from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.user import User
from app.database.models.session import TrainingSession
from app.database.models.guidance_profile import GuidanceProfile
from app.database.models.guidance_step import GuidanceStep
from app.services.guidance_service import generate_guidance_profile
from app.utils.auth import get_current_user


router = APIRouter(
    prefix="/api/guidance",
    tags=["Adaptive Guidance"]
)


# ==========================================================
# 1. Generate Adaptive Guidance
# ==========================================================

@router.post("/generate")
def create_guidance_profile(
    user_id: int,
    source_session_id: int,
    target_session_number: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate adaptive guidance for the next training session.
    """

    # Check requested user
    if user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to generate guidance for this user"
        )

    # Check source session
    source_session = db.query(TrainingSession).filter(
        TrainingSession.id == source_session_id
    ).first()

    if not source_session:
        raise HTTPException(
            status_code=404,
            detail="Source session not found"
        )

    # Check session ownership
    if source_session.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to access this session"
        )

    result = generate_guidance_profile(
        user_id=user_id,
        source_session_id=source_session_id,
        target_session_number=target_session_number,
        db=db
    )

    return {
        "message": "Adaptive guidance generated successfully",
        **result
    }


# ==========================================================
# 2. Get Guidance for a Training Session
# ==========================================================

@router.get("/user/{user_id}/training/{training_number}")
def get_training_guidance(
    user_id: int,
    training_number: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get adaptive guidance for a specific TRAINING session.

    Guidance is enabled only for TRAINING.
    """

    # Check requested user
    if user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to access this user's guidance"
        )

    # Validate user
    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # Find guidance profile
    profile = db.query(GuidanceProfile).filter(
        GuidanceProfile.user_id == user_id,
        GuidanceProfile.session_target == training_number
    ).first()

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Guidance profile not found for this training session"
        )

    # Get all 16 guidance steps
    guidance_steps = db.query(GuidanceStep).filter(
        GuidanceStep.guidance_profile_id == profile.id
    ).order_by(
        GuidanceStep.step_id.asc()
    ).all()

    if not guidance_steps:
        raise HTTPException(
            status_code=404,
            detail="No guidance steps found for this profile"
        )

    guidance = []

    for step in guidance_steps:
        guidance.append({
            "step_id": step.step_id,
            "step_name": step.step_name,
            "guidance_level": step.guidance_level,
            "mistake_count": step.mistake_count,
            "mistake_ratio": step.mistake_ratio,
            "guidance_message": step.guidance_message
        })

    return {
        "user_id": user_id,
        "training_session_number": training_number,
        "guidance_enabled": True,
        "profile_id": profile.id,
        "profile_version": profile.profile_version,
        "guidance": guidance
    }


# ==========================================================
# 3. Check Guidance Status for a Session
# ==========================================================

@router.get("/session/{session_id}")
def get_guidance_status(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check whether adaptive guidance is enabled
    for the given session.

    TRAINING -> guidance ON
    TEST     -> guidance OFF
    """

    # Find session
    session = db.query(TrainingSession).filter(
        TrainingSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    # Check session ownership
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to access this session"
        )

    # Determine guidance status
    if session.session_type == "TRAINING":
        guidance_enabled = True

    elif session.session_type == "TEST":
        guidance_enabled = False

    else:
        guidance_enabled = False

    return {
        "session_id": session.id,
        "user_id": session.user_id,
        "session_type": session.session_type,
        "session_number": session.session_number,
        "guidance_enabled": guidance_enabled
    }