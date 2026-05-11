"""Repositorio de reservas: frontera para consultas por salida/persona."""
from typing import Any, Iterable, Optional
from sqlalchemy.orm import Session


def list_by_outing(db: Session, ReservationModel: Any, outing_id: int) -> list[Any]:
    return db.query(ReservationModel).filter(ReservationModel.outing_id == outing_id).order_by(ReservationModel.id).all()


def find_by_outing_document(db: Session, ReservationModel: Any, outing_id: int, dni: str) -> Optional[Any]:
    return db.query(ReservationModel).filter(ReservationModel.outing_id == outing_id, ReservationModel.dni == dni).first()


def active_count(reservations: Iterable[Any]) -> int:
    return sum(1 for r in reservations if (getattr(r, "status", "") or "").lower() not in {"cancelada", "cancelado"})
