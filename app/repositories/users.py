"""Repositorio de usuarios: frontera de consultas del padrón."""
from typing import Any, Optional
from sqlalchemy.orm import Session


def get_by_id(db: Session, UserModel: Any, user_id: int) -> Optional[Any]:
    return db.get(UserModel, user_id)


def get_by_document(db: Session, UserModel: Any, dni: str) -> Optional[Any]:
    return db.query(UserModel).filter(UserModel.dni == dni).first()


def active_admin_count(db: Session, UserModel: Any) -> int:
    return db.query(UserModel).filter(UserModel.role == "admin", UserModel.active.is_(True)).count()
