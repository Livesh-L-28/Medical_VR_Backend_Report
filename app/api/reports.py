from typing import Optional
import json
from fastapi import APIRouter, Depends, HTTPException, Response, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.user import User
from app.database.models.session import TrainingSession
from app.database.models.test_report import TestReport
from app.database.models.training_report import TrainingReport
from app.database.models.step_performance import StepPerformance
from app.database.models.mistake import Mistake
from app.database.models.weak_area import WeakArea
from app.database.models.cumulative_weak_area import CumulativeWeakArea
from app.database.models.guidance_profile import GuidanceProfile
from app.database.models.guidance_step import GuidanceStep
from app.database.models.ai_feedback import AIReportFeedback

from app.services.test_report_service import generate_test_report
from app.services.training_report_service import generate_training_report
from app.services.weak_area_service import analyze_weak_areas
from app.services.cumulative_weak_area_service import calculate_cumulative_weak_areas
from app.services.historical_context_service import get_user_historical_context
from app.services.pdf_report_service import generate_assessment_pdf
from app.engines.llm_feedback_engine import (
    build_evidence_payload,
    request_llm_feedback,
    create_fallback_feedback
)
from app.schemas.ai_feedback import AIReportResponse, AIFeedbackResponse
from app.utils.auth import get_current_user


router = APIRouter(
    prefix="/api/reports",
    tags=["Reports & AI Feedback"]
)


def _extract_session_assessment_details(session: TrainingSession, db: Session):
    """
    Extract deterministic report metrics, step performances, mistakes,
    session-level weak areas, and cumulative weak areas.
    """
    if session.session_type == "TEST":
        report_data = generate_test_report(session.id, db)
        assessment_dict = report_data["report"]
        step_performances = report_data.get("step_performance", [])
        mistakes = [
            {
                "step_id": m.get("step_id"),
                "mistake_type": m.get("mistake_type"),
                "attempt_number": m.get("attempt_number"),
                "timestamp": str(m.get("timestamp")) if m.get("timestamp") else None
            }
            for m in report_data.get("mistakes", [])
        ]

        # 1. Session-level weak areas (current session errors only)
        wa_records = db.query(WeakArea).filter(
            WeakArea.session_id == session.id
        ).order_by(WeakArea.rank.asc()).all()

        if not wa_records:
            has_mistakes = any(sp.get("mistakes", 0) > 0 for sp in step_performances) or len(mistakes) > 0
            if has_mistakes:
                analyze_weak_areas(session.id, db)
                wa_records = db.query(WeakArea).filter(
                    WeakArea.session_id == session.id
                ).order_by(WeakArea.rank.asc()).all()

        session_weak_areas = [
            {
                "step_id": wa.step_id,
                "step_name": wa.step_name,
                "attempts": wa.attempts,
                "mistakes": wa.mistakes,
                "mistake_ratio": wa.mistake_ratio,
                "severity": wa.severity,
                "rank": wa.rank
            }
            for wa in wa_records
        ]

        # 2. Cumulative weak areas (recurring weaknesses across all historical sessions)
        cum_records = db.query(CumulativeWeakArea).filter(
            CumulativeWeakArea.user_id == session.user_id,
            CumulativeWeakArea.total_mistakes > 0
        ).order_by(CumulativeWeakArea.rank.asc()).all()

        cumulative_weak_areas = [
            {
                "step_id": cwa.step_id,
                "step_name": cwa.step_name,
                "total_attempts": cwa.total_attempts,
                "total_mistakes": cwa.total_mistakes,
                "mistake_ratio": cwa.mistake_ratio,
                "severity": cwa.severity,
                "rank": cwa.rank,
                "last_session_id": cwa.last_session_id
            }
            for cwa in cum_records
        ]

    else:
        # TRAINING session
        training_rep = generate_training_report(session.id, db)
        assessment_dict = {
            "id": training_rep.id,
            "total_steps": training_rep.total_steps,
            "completed_steps": training_rep.completed_steps,
            "correct_steps": training_rep.correct_steps,
            "accuracy": training_rep.accuracy,
            "total_attempts": training_rep.total_attempts,
            "total_mistakes": training_rep.total_mistakes,
            "first_attempt_correct_count": training_rep.first_attempt_correct_count,
            "first_attempt_accuracy": training_rep.first_attempt_accuracy,
            "total_time_seconds": training_rep.total_time_seconds,
            "average_step_time_seconds": training_rep.average_step_time_seconds,
            "overall_result": training_rep.overall_result
        }

        # Step performances
        sp_records = db.query(StepPerformance).filter(
            StepPerformance.session_id == session.id
        ).order_by(StepPerformance.step_id.asc()).all()
        step_performances = [
            {
                "step_id": sp.step_id,
                "step_name": sp.step_name,
                "attempts": sp.attempts,
                "mistakes": sp.mistakes,
                "first_attempt_correct": sp.first_attempt_correct,
                "step_time_seconds": sp.step_time_seconds,
                "completed": sp.completed
            }
            for sp in sp_records
        ]

        # Mistakes
        m_records = db.query(Mistake).filter(
            Mistake.session_id == session.id
        ).order_by(Mistake.step_id.asc()).all()
        mistakes = [
            {
                "step_id": m.step_id,
                "mistake_type": m.mistake_type,
                "attempt_number": m.attempt_number
            }
            for m in m_records
        ]

        # 1. Session-level weak areas (current session errors only)
        wa_records = db.query(WeakArea).filter(
            WeakArea.session_id == session.id
        ).order_by(WeakArea.rank.asc()).all()

        if not wa_records:
            has_mistakes = any(sp.get("mistakes", 0) > 0 for sp in step_performances) or len(mistakes) > 0
            if has_mistakes:
                analyze_weak_areas(session.id, db)
                wa_records = db.query(WeakArea).filter(
                    WeakArea.session_id == session.id
                ).order_by(WeakArea.rank.asc()).all()

        session_weak_areas = [
            {
                "step_id": wa.step_id,
                "step_name": wa.step_name,
                "attempts": wa.attempts,
                "mistakes": wa.mistakes,
                "mistake_ratio": wa.mistake_ratio,
                "severity": wa.severity,
                "rank": wa.rank
            }
            for wa in wa_records
        ]

        # 2. Cumulative weak areas (recurring weaknesses across all historical sessions)
        calculate_cumulative_weak_areas(session.user_id, db)
        cum_records = db.query(CumulativeWeakArea).filter(
            CumulativeWeakArea.user_id == session.user_id,
            CumulativeWeakArea.total_mistakes > 0
        ).order_by(CumulativeWeakArea.rank.asc()).all()

        cumulative_weak_areas = [
            {
                "step_id": cwa.step_id,
                "step_name": cwa.step_name,
                "total_attempts": cwa.total_attempts,
                "total_mistakes": cwa.total_mistakes,
                "mistake_ratio": cwa.mistake_ratio,
                "severity": cwa.severity,
                "rank": cwa.rank,
                "last_session_id": cwa.last_session_id
            }
            for cwa in cum_records
        ]

    return assessment_dict, step_performances, mistakes, session_weak_areas, cumulative_weak_areas


@router.post("/{session_id}/ai", response_model=AIReportResponse)
async def generate_ai_report(
    session_id: int,
    model_name: Optional[str] = Query(default=None, description="Optional LLM model override: openbiollm | llama-3.2-3b | medical-transformer"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate evidence-grounded AI feedback for an evaluated session.
    
    Security:
    - User authentication enforced.
    - Strict session ownership verified.
    - User historical context isolated to current_user.id.
    """
    # 1. Verify session exists and belongs to current user
    session = db.query(TrainingSession).filter(
        TrainingSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized access to this session")

    # 2. Extract deterministic assessment metrics
    assessment_dict, step_performances, mistakes, session_weak_areas, cumulative_weak_areas = _extract_session_assessment_details(session, db)
    report_id = assessment_dict.get("id")

    # 3. Retrieve user-isolated historical context
    historical_context = get_user_historical_context(
        user_id=current_user.id,
        current_session_id=session_id,
        db=db
    )

    # 4. Build evidence payload for LLM
    evidence = build_evidence_payload(
        session_type=session.session_type,
        assessment_data=assessment_dict,
        step_performance=step_performances,
        mistakes=mistakes,
        weak_areas=session_weak_areas,
        historical_context=historical_context
    )

    # 5. Request AI feedback from Medical LLM
    ai_feedback, ai_status, model_used = await request_llm_feedback(evidence, model_name=model_name)

    # 6. Persist or update AIReportFeedback in DB
    existing_ai = db.query(AIReportFeedback).filter(
        AIReportFeedback.session_id == session_id
    ).first()

    if existing_ai:
        existing_ai.model_name = model_used
        existing_ai.feedback_json = json.dumps(ai_feedback.model_dump())
        existing_ai.status = ai_status
        db.commit()
    else:
        new_ai = AIReportFeedback(
            session_id=session.id,
            user_id=current_user.id,
            model_name=model_used,
            feedback_json=json.dumps(ai_feedback.model_dump()),
            status=ai_status
        )
        db.add(new_ai)
        db.commit()

    return AIReportResponse(
        report_id=report_id,
        session_id=session.id,
        user_id=current_user.id,
        session_type=session.session_type,
        session_number=session.session_number,
        deterministic_assessment=assessment_dict,
        assessment=assessment_dict,
        step_performance=step_performances,
        mistakes=mistakes,
        weak_areas=session_weak_areas,
        historical_context=historical_context,
        ai_feedback=ai_feedback,
        ai_feedback_status=ai_status,
        ai_status=ai_status,
        model_name=model_used
    )


@router.get("/{session_id}/pdf")
async def download_pdf_report(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate and stream a formal clinical PDF report for the given session.
    """
    # 1. Verify session ownership
    session = db.query(TrainingSession).filter(
        TrainingSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized access to this session")

    # 2. Extract deterministic assessment metrics
    assessment_dict, step_performances, mistakes, session_weak_areas, cumulative_weak_areas = _extract_session_assessment_details(session, db)

    # 3. Retrieve user-isolated historical context
    historical_context = get_user_historical_context(
        user_id=current_user.id,
        current_session_id=session_id,
        db=db
    )

    # 4. Retrieve active adaptive guidance for current_user
    latest_guidance_profile = db.query(GuidanceProfile).filter(
        GuidanceProfile.user_id == current_user.id
    ).order_by(
        GuidanceProfile.profile_version.desc()
    ).first()

    guidance_data = []
    if latest_guidance_profile:
        guidance_steps = db.query(GuidanceStep).filter(
            GuidanceStep.guidance_profile_id == latest_guidance_profile.id
        ).order_by(
            GuidanceStep.step_id.asc()
        ).all()

        for step in guidance_steps:
            guidance_data.append({
                "step_id": step.step_id,
                "step_name": step.step_name,
                "guidance_level": step.guidance_level,
                "mistake_count": step.mistake_count,
                "mistake_ratio": step.mistake_ratio,
                "guidance_message": step.guidance_message
            })

    adaptive_guidance = {
        "guidance_available": latest_guidance_profile is not None,
        "profile_id": latest_guidance_profile.id if latest_guidance_profile else None,
        "profile_version": latest_guidance_profile.profile_version if latest_guidance_profile else None,
        "session_target": latest_guidance_profile.session_target if latest_guidance_profile else None,
        "guidance": guidance_data
    }

    # 5. Check for existing AI feedback, or create fallback
    ai_record = db.query(AIReportFeedback).filter(
        AIReportFeedback.session_id == session_id
    ).first()

    if ai_record:
        ai_data = json.loads(ai_record.feedback_json)
        ai_status = ai_record.status
        model_name = ai_record.model_name
    else:
        fallback_obj = create_fallback_feedback(
            assessment_dict,
            session_weak_areas,
            reason="AI feedback not previously generated"
        )
        ai_data = fallback_obj.model_dump()
        ai_status = "PENDING_GENERATION"
        model_name = "openbiollm"

    # 6. Compile PDF
    user_info = {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email
    }
    session_info = {
        "session_id": session.id,
        "session_number": session.session_number,
        "session_type": session.session_type,
        "user_id": current_user.id
    }

    pdf_buffer = generate_assessment_pdf(
        user_info=user_info,
        session_info=session_info,
        assessment_data=assessment_dict,
        step_performance=step_performances,
        mistakes=mistakes,
        weak_areas=session_weak_areas,
        historical_context=historical_context,
        ai_feedback=ai_data,
        ai_status=ai_status,
        model_name=model_name,
        cumulative_weak_areas=cumulative_weak_areas,
        adaptive_guidance=adaptive_guidance
    )

    filename = f"venipuncture_report_session_{session.id}.pdf"
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
