from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.database.models.user import User
from app.database.models.session import TrainingSession
from app.database.models.cumulative_weak_area import CumulativeWeakArea
from app.database.models.guidance_profile import GuidanceProfile
from app.database.models.guidance_step import GuidanceStep

from app.config.constants import STEPS


def determine_guidance(mistake_ratio: float) -> str:
    """
    Determine guidance level based on mistake ratio.
    """

    if mistake_ratio >= 50:
        return "HIGH"

    elif mistake_ratio >= 25:
        return "MEDIUM"

    else:
        return "LOW"


def generate_guidance_profile(
    user_id: int,
    source_session_id: int,
    target_session_number: int,
    db: Session
):
    """
    Generate adaptive guidance for the next training session
    based on cumulative weak areas.
    """

    # --------------------------------------------------
    # 1. Validate user
    # --------------------------------------------------

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # --------------------------------------------------
    # 2. Validate source session
    # --------------------------------------------------

    source_session = db.query(TrainingSession).filter(
        TrainingSession.id == source_session_id
    ).first()

    if not source_session:
        raise HTTPException(
            status_code=404,
            detail="Source session not found"
        )

    # --------------------------------------------------
    # 3. Source session must belong to user
    # --------------------------------------------------

    if source_session.user_id != user_id:
        raise HTTPException(
            status_code=400,
            detail="Source session does not belong to this user"
        )

    # --------------------------------------------------
    # 4. Source session can be TRAINING or TEST
    # --------------------------------------------------

    if source_session.session_type not in ["TRAINING", "TEST"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid source session type"
        )

    # --------------------------------------------------
    # 5. Target TRAINING session must exist
    # --------------------------------------------------
    target_session = db.query(TrainingSession).filter(
        TrainingSession.user_id == user_id,
        TrainingSession.session_type == "TRAINING",
        TrainingSession.session_number == target_session_number,
        TrainingSession.start_time > source_session.start_time
    ).order_by(
        TrainingSession.start_time.asc()
    ).first()

    if not target_session:
        raise HTTPException(
            status_code=404,
            detail="Target TRAINING session not found"
        )

    # Target must be after the source session
    if target_session.id <= source_session.id:
        raise HTTPException(
            status_code=400,
            detail="Target TRAINING session must occur after the source session"
        )

    # --------------------------------------------------
    # 6. Check duplicate guidance profile
    # --------------------------------------------------

    existing_profile = db.query(GuidanceProfile).filter(
        GuidanceProfile.user_id == user_id,
        GuidanceProfile.session_target == target_session_number
    ).first()

    if existing_profile:
        raise HTTPException(
            status_code=400,
            detail="Guidance profile already exists for this target session"
        )

    # --------------------------------------------------
    # 7. Get cumulative weak areas
    # --------------------------------------------------

    weak_areas = db.query(CumulativeWeakArea).filter(
        CumulativeWeakArea.user_id == user_id
    ).order_by(
        CumulativeWeakArea.rank.asc()
    ).all()

    # --------------------------------------------------
    # 8. Determine profile version
    # --------------------------------------------------

    latest_profile = db.query(GuidanceProfile).filter(
        GuidanceProfile.user_id == user_id
    ).order_by(
        GuidanceProfile.profile_version.desc()
    ).first()

    if latest_profile:
        profile_version = latest_profile.profile_version + 1
    else:
        profile_version = 1

    # --------------------------------------------------
    # 9. Create guidance profile
    # --------------------------------------------------

    profile = GuidanceProfile(
        user_id=user_id,
        profile_version=profile_version,
        session_target=target_session_number
    )

    db.add(profile)

    # Flush to get profile.id before creating GuidanceStep
    db.flush()

    # --------------------------------------------------
    # 10. Create lookup dictionary for weak areas
    # --------------------------------------------------

    weak_area_dict = {
        area.step_id: area
        for area in weak_areas
    }

    # --------------------------------------------------
    # 11. Generate guidance for all 16 steps
    # --------------------------------------------------

    guidance = []

    for step_id in range(16):

        weak_area = weak_area_dict.get(step_id)

        # ----------------------------------------------
        # Step has a recorded weakness
        # ----------------------------------------------

        if weak_area:

            guidance_level = determine_guidance(
                weak_area.mistake_ratio
            )

            mistake_ratio = weak_area.mistake_ratio
            mistakes = weak_area.total_mistakes
            attempts = weak_area.total_attempts

        # ----------------------------------------------
        # Step has no recorded weakness
        # ----------------------------------------------

        else:

            guidance_level = "LOW"
            mistake_ratio = 0
            mistakes = 0
            attempts = 0

        # ----------------------------------------------
        # Guidance message
        # ----------------------------------------------

        if guidance_level == "HIGH":

            guidance_message = (
                f"Pay extra attention to {STEPS[step_id]}. "
                f"Perform this step carefully and verify the "
                f"correct object and placement before proceeding."
            )

        elif guidance_level == "MEDIUM":

            guidance_message = (
                f"Be careful during {STEPS[step_id]}. "
                f"Focus on correct execution before proceeding."
            )

        else:

            guidance_message = (
                f"Perform {STEPS[step_id]} according to "
                f"the standard procedure."
            )

        # ----------------------------------------------
        # Save guidance for this step
        # ----------------------------------------------

        guidance_step = GuidanceStep(
            guidance_profile_id=profile.id,
            step_id=step_id,
            step_name=STEPS[step_id],
            guidance_level=guidance_level,
            mistake_count=mistakes,
            mistake_ratio=mistake_ratio,
            guidance_message=guidance_message
        )

        db.add(guidance_step)

        # ----------------------------------------------
        # Add step guidance to API response
        # ----------------------------------------------

        guidance.append({
            "step_id": step_id,
            "step_name": STEPS[step_id],
            "guidance_level": guidance_level,
            "mistake_ratio": mistake_ratio,
            "mistakes": mistakes,
            "attempts": attempts,
            "guidance_message": guidance_message
        })

    # --------------------------------------------------
    # 12. Save profile and all 16 guidance records
    # --------------------------------------------------

    db.commit()

    # Refresh profile after commit
    db.refresh(profile)

    # --------------------------------------------------
    # 13. Return guidance profile
    # --------------------------------------------------

    return {
        "profile_id": profile.id,
        "user_id": profile.user_id,
        "profile_version": profile.profile_version,
        "session_target": profile.session_target,
        "source_session_id": source_session_id,
        "source_session_type": source_session.session_type,
        "guidance": guidance
    }