"""Repositorio de actividad técnica y auditoría."""
from typing import Any
from sqlalchemy.orm import Session


def latest_activity(db: Session, ActivityLogModel: Any, limit: int = 50) -> list[Any]:
    return db.query(ActivityLogModel).order_by(ActivityLogModel.created_at.desc()).limit(limit).all()


def latest_audit(db: Session, AuditLogModel: Any, limit: int = 50) -> list[Any]:
    return db.query(AuditLogModel).order_by(AuditLogModel.created_at.desc()).limit(limit).all()
