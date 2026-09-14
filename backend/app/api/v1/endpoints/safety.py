from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.v1.deps import db_session, require_roles
from app.db.models.safety_eval import SafetyEvalRun
from app.db.models.user import UserRole
from app.middleware.tenant import TenantContext
from app.safety.evaluation_runner import render_report, run_evaluation

router = APIRouter()


@router.post("/run-eval", status_code=202)
def run_eval(db: Session = Depends(db_session), context: TenantContext = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN))):
    matrix, results = run_evaluation()
    report = render_report(matrix, results)
    row = SafetyEvalRun(total_cases=len(results), true_positives=matrix.true_positives, false_positives=matrix.false_positives, true_negatives=matrix.true_negatives, false_negatives=matrix.false_negatives, false_negative_rate=matrix.false_negative_rate, report_markdown=report)
    db.add(row); db.commit(); db.refresh(row)
    return {"status": "completed", "id": str(row.id), "false_negative_rate": row.false_negative_rate}


@router.get("/reports")
def reports(db: Session = Depends(db_session), context: TenantContext = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN))):
    if context.role == UserRole.PLATFORM_ADMIN.value:
        rows = db.query(SafetyEvalRun).order_by(SafetyEvalRun.run_timestamp.desc()).all()
    else:
        rows = db.query(SafetyEvalRun).order_by(SafetyEvalRun.run_timestamp.desc()).all()
    return [{"id": str(row.id), "run_timestamp": row.run_timestamp, "total_cases": row.total_cases, "false_negative_rate": row.false_negative_rate} for row in rows]


@router.get("/reports/latest")
def latest(db: Session = Depends(db_session), context: TenantContext = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN))):
    row = db.query(SafetyEvalRun).order_by(SafetyEvalRun.run_timestamp.desc()).first()
    if row is None:
        raise HTTPException(status_code=404, detail="No safety evaluation runs found")
    return {"id": str(row.id), "total_cases": row.total_cases, "true_positives": row.true_positives, "false_positives": row.false_positives, "true_negatives": row.true_negatives, "false_negatives": row.false_negatives, "false_negative_rate": row.false_negative_rate, "report_markdown": row.report_markdown}
