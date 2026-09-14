from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.v1.deps import db_session, get_current_context
from app.db.models.notification import Notification
from app.middleware.tenant import TenantContext

router = APIRouter()


@router.get("")
def list_notifications(db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    rows = db.query(Notification).filter(Notification.hospital_id == context.hospital_id, Notification.recipient_user_id == context.user_id).order_by(Notification.sent_at.desc()).all()
    return [{"id": str(row.id), "channel": row.channel.value, "message": row.message, "is_read": row.is_read, "sent_at": row.sent_at} for row in rows]
