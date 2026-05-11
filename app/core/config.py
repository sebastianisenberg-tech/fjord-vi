"""Fase 5: frontera de configuración.

Objetivo: mover gradualmente constantes, versión, variables de entorno y settings
fuera de main.py sin cambiar el comportamiento visible del sistema.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class AppIdentity:
    club_name: str = "YCA"
    app_name: str = "Fjord VI"
    app_model: str = "Embarque"

ARCHITECTURE_PHASE = "Fase 5 · modularización controlada"
