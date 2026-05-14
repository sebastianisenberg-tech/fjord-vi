"""Repositorio de salidas: frontera de agenda operativa."""
from typing import Any, Optional
from sqlalchemy.orm import Session


def get_by_id(db: Session, OutingModel: Any, outing_id: int) -> Optional[Any]:
    return db.get(OutingModel, outing_id)


def list_open(db: Session, OutingModel: Any) -> list[Any]:
    return db.query(OutingModel).filter(OutingModel.status != "Cancelada").order_by(OutingModel.departure_at).all()
