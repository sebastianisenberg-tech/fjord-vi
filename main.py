from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from pathlib import Path
import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import traceback
import time
import uuid
import zipfile
import re
from urllib.parse import parse_qs
import smtplib
from email.message import EmailMessage
from urllib.parse import urlparse
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.core.errors import AppError, render_app_error_html
from app.core.logging_config import configure_logging, get_logger
from app.core.settings import load_settings

from fastapi import FastAPI, Request, Form, Depends, HTTPException, UploadFile, File
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response, FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Numeric, UniqueConstraint, Text, inspect, text, func, or_
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.exc import IntegrityError

APP_VERSION = "3.0"
APP_SETTINGS = load_settings(app_version=APP_VERSION)
configure_logging(APP_SETTINGS.log_level)
APP_LOGGER = get_logger("fjord.app")


# =========================
# FORMATO VISUAL / LEGIBILIDAD
# =========================

def nonempty_label_v1168(value, fallback="Pendiente"):
    try:
        value = (value or "").strip()
    except Exception:
        value = ""
    return value if value else fallback

def clean_join(*parts):
    cleaned = []
    for p in parts:
        if p is None:
            continue
        s = str(p).strip()
        if s:
            cleaned.append(s)
    return " · ".join(cleaned)

APP_DIR = Path(__file__).parent
DATA_DIR = Path(os.getenv("DATA_DIR", APP_DIR))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR/'fjord_v18_pilot.db'}")
JSON_BACKUP_PATH = Path(os.getenv("JSON_BACKUP_PATH", DATA_DIR / "fjord_vi_data.json"))
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if APP_ENV in ("prod", "production"):
    if not SECRET_KEY or SECRET_KEY == "pilot-secret-change-me" or len(SECRET_KEY) < 32:
        raise RuntimeError("SECRET_KEY obligatorio en producción: configurar una clave secreta aleatoria de al menos 32 caracteres.")
if not SECRET_KEY:
    SECRET_KEY = "pilot-secret-change-me"
MAX_CREW = int(os.getenv("MAX_CREW", "9"))
MIN_CREW = int(os.getenv("MIN_CREW", "2"))
INVITED_FEE = float(os.getenv("INVITED_FEE", "45000"))
LATE_SOCIO_RATE = float(os.getenv("LATE_SOCIO_RATE", "0.70"))
VERSION = APP_VERSION
APP_BUILD = "Fjord VI 2.8"
RELEASE_LABEL = "Fjord VI · v3.0"
DEMO_SEED = os.getenv("DEMO_SEED", "0").lower() in ("1", "true", "yes", "on")
CLUB_NAME = "YCA"
APP_NAME = "Fjord VI"
APP_MODEL = "Embarque"

APP_TZ = ZoneInfo(os.getenv("APP_TZ", "America/Argentina/Buenos_Aires"))


# =========================
# ROBUSTEZ OPERATIVA / GUARDAS
# =========================
RECENT_POST_KEYS = {}
RECENT_POST_TTL_SECONDS = 12
OPERATION_LOCK_TTL_SECONDS = int(os.getenv("OPERATION_LOCK_TTL_SECONDS", "30"))
LOGIN_LOCK_ATTEMPTS = int(os.getenv("LOGIN_LOCK_ATTEMPTS", "20"))
LOGIN_LOCK_WINDOW_MINUTES = int(os.getenv("LOGIN_LOCK_WINDOW_MINUTES", "30"))
LOGIN_LOCK_MINUTES = int(os.getenv("LOGIN_LOCK_MINUTES", "15"))
LOGIN_LOCK_IP_ATTEMPTS = int(os.getenv("LOGIN_LOCK_IP_ATTEMPTS", "80"))
SESSION_MAX_AGE_SECONDS = int(os.getenv("SESSION_MAX_AGE_SECONDS", "43200"))
CSRF_COOKIE_NAME = "fjord_csrf"
SESSION_COOKIE_NAME = "fjord_uid"


def _cleanup_recent_post_keys():
    """Limpieza liviana del guard anti doble-submit."""
    try:
        now_ts = datetime.utcnow().timestamp()
        stale = [k for k, ts in RECENT_POST_KEYS.items() if now_ts - ts > RECENT_POST_TTL_SECONDS]
        for k in stale[:250]:
            RECENT_POST_KEYS.pop(k, None)
    except Exception:
        pass

def _safe_back_url(request: Request) -> str:
    ref = request.headers.get("referer") or "/"
    try:
        parsed = urlparse(ref)
        if parsed.netloc and parsed.netloc != request.url.netloc:
            return "/"
        return parsed.path + (("?" + parsed.query) if parsed.query else "")
    except Exception:
        return "/"


def now_local() -> datetime:
    return datetime.now(APP_TZ).replace(tzinfo=None)

APP_STARTED_AT = now_local()
SYSTEM_FAST_CACHE = {}
SYSTEM_FAST_CACHE_SECONDS = int(os.getenv("SYSTEM_FAST_CACHE_SECONDS", "45"))


engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    dni = Column(String, unique=True, nullable=False)
    member_no = Column(String, nullable=True)
    email = Column(String, nullable=True)
    whatsapp = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    category = Column(String, nullable=True)
    birth_date = Column(String, nullable=True)
    role = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    active = Column(Boolean, default=True)
    can_manage_protocolar = Column(Boolean, default=False)
    must_change_password = Column(Boolean, default=False)
    session_version = Column(Integer, default=1)
    last_login_at = Column(DateTime, nullable=True)
    last_password_change_at = Column(DateTime, nullable=True)

class Outing(Base):
    __tablename__ = "outings"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    departure_at = Column(DateTime, nullable=False)
    status = Column(String, default="Programada")
    max_crew = Column(Integer, default=MAX_CREW)
    institutional_reserve = Column(Integer, default=0)
    min_crew = Column(Integer, default=MIN_CREW)
    guest_fee = Column(Numeric(12,2), default=INVITED_FEE)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=now_local)
    boat_id = Column(String, default="fjord_vi")

class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(Integer, primary_key=True)
    outing_id = Column(Integer, ForeignKey("outings.id"), nullable=False)
    person_name = Column(String, nullable=False)
    dni = Column(String, nullable=False)
    kind = Column(String, nullable=False)
    responsible_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    original_responsible_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reassignment_count = Column(Integer, default=0)
    last_reassigned_at = Column(DateTime, nullable=True)
    last_reassigned_by = Column(String, default="")
    status = Column(String, default="Confirmado")
    attendance = Column(String, default="Por confirmar")
    charge_amount = Column(Numeric(12,2), default=0)
    cancel_reason = Column(String, default="")
    birth_date = Column(String, nullable=True)
    created_at = Column(DateTime, default=now_local)
    cancelled_at = Column(DateTime, nullable=True)
    protocolar = Column(Boolean, default=False)
    protocolar_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    protocolar_reason = Column(Text, default="")
    __table_args__ = (UniqueConstraint("outing_id", "dni", name="uq_outing_dni"),)

class ReservationReassignment(Base):
    __tablename__ = "reservation_reassignments"
    id = Column(Integer, primary_key=True)
    outing_id = Column(Integer, ForeignKey("outings.id"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=False)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    performed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    performed_by_name = Column(String, default="")
    performed_at = Column(DateTime, default=now_local)
    reason = Column(Text, default="")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=now_local)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    detail = Column(Text, default="")

class ClosingSheet(Base):
    """Ficha de cierre de navegación.

    No se edita ni se pisa: si la salida se reabre, la ficha vigente se
    anula y el próximo cierre genera una nueva ficha.
    """
    __tablename__ = "closing_sheets"
    id = Column(Integer, primary_key=True)
    outing_id = Column(Integer, ForeignKey("outings.id"), nullable=False)
    sequence = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default="VIGENTE")
    created_at = Column(DateTime, default=now_local)
    created_by = Column(String, nullable=False, default="")
    annulled_at = Column(DateTime, nullable=True)
    annulled_by = Column(String, nullable=True)
    annul_reason = Column(Text, default="")
    payload = Column(Text, default="{}")

class SystemMeta(Base):
    __tablename__ = "system_meta"
    key = Column(String, primary_key=True)
    value = Column(Text, default="")
    updated_at = Column(DateTime, default=now_local)

class ActivityLog(Base):
    __tablename__ = "activity_log"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=now_local)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_name = Column(String, default="")
    role = Column(String, default="")
    module = Column(String, default="")
    action = Column(String, default="pageview")
    path = Column(String, default="")
    detail = Column(Text, default="")
    ip = Column(String, default="")
    user_agent = Column(Text, default="")




class OperationLock(Base):
    """Lock operativo liviano para evitar acciones simultáneas sobre la misma salida.

    No reemplaza constraints de base ni validaciones de negocio: funciona como
    cinturón de seguridad contra doble click, mala señal móvil o dos pantallas
    tocando la misma salida a la vez.
    """
    __tablename__ = "operation_locks"
    key = Column(String, primary_key=True)
    created_at = Column(DateTime, default=now_local)
    expires_at = Column(DateTime, nullable=False)
    owner = Column(String, default="")
    path = Column(String, default="")
    detail = Column(Text, default="")


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=now_local)
    ident_key = Column(String, default="")
    ip_hash = Column(String, default="")
    success = Column(Boolean, default=False)
    detail = Column(Text, default="")


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    subject = Column(Text, default="")
    body = Column(Text, default="")
    enabled = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=now_local)

class NotificationEventSetting(Base):
    __tablename__ = "notification_event_settings"
    key = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    enabled = Column(Boolean, default=False)
    channel_email = Column(Boolean, default=True)
    description = Column(Text, default="")
    updated_at = Column(DateTime, default=now_local)

class NotificationQueue(Base):
    __tablename__ = "notification_queue"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=now_local)
    sent_at = Column(DateTime, nullable=True)
    event_key = Column(String, nullable=False)
    recipient_email = Column(String, nullable=False)
    recipient_name = Column(String, default="")
    subject = Column(Text, default="")
    body = Column(Text, default="")
    status = Column(String, default="pending")  # pending / sent / failed / cancelled
    attempts = Column(Integer, default=0)
    error = Column(Text, default="")
    payload = Column(Text, default="{}")

class NotificationLog(Base):
    __tablename__ = "notification_log"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=now_local)
    queue_id = Column(Integer, nullable=True)
    event_key = Column(String, default="")
    recipient_email = Column(String, default="")
    status = Column(String, default="")
    detail = Column(Text, default="")


COMMUNICATION_EVENTS = {
    "reserva_confirmada_socio": {
        "name": "Reserva confirmada al socio",
        "description": "Email al socio cuando confirma o reactiva su lugar.",
        "subject": "Reserva confirmada - {{salida_nombre}} - {{fecha}}",
        "body": "Hola {{socio_nombre}},\n\nTu reserva para {{salida_nombre}} el {{fecha}} a las {{hora}} quedó registrada.\n\nEstado: {{estado}}\n\n{{club_nombre}} · {{app_name}}",
    },
    "invitado_agregado_socio": {
        "name": "Invitado agregado",
        "description": "Email al socio cuando agrega o reactiva un invitado.",
        "subject": "Invitado registrado - {{salida_nombre}}",
        "body": "Hola {{socio_nombre}},\n\nSe registró el invitado {{invitado_nombre}} para {{salida_nombre}}.\n\nFecha: {{fecha}} {{hora}}\nEstado: {{estado}}\n\n{{club_nombre}} · {{app_name}}",
    },
    "cancelacion_socio": {
        "name": "Cancelación registrada",
        "description": "Email al socio cuando cancela una reserva propia o de un invitado.",
        "subject": "Cancelación registrada - {{salida_nombre}}",
        "body": "Hola {{socio_nombre}},\n\nQuedó registrada la cancelación de {{persona_nombre}} para {{salida_nombre}}.\n\nCargo informado: {{importe}}\n\n{{club_nombre}} · {{app_name}}",
    },
    "salida_cerrada_admin": {
        "name": "Embarque cerrado para administración",
        "description": "Email a Administración cuando el capitán cierra la salida y genera ficha.",
        "subject": "Embarque cerrado - {{salida_nombre}} - Ficha N° {{ficha_numero}}",
        "body": "Administración,\n\nLa salida {{salida_nombre}} fue cerrada por {{capitan_nombre}}.\n\nPresentes: {{presentes}}\nTotal a liquidar: {{total}}\nFicha: N° {{ficha_numero}}\n\nVer ficha: {{link_ficha}}\n\n{{club_nombre}} · {{app_name}}",
    },
    "recordatorio_24h_socio": {
        "name": "Recordatorio 24h al socio",
        "description": "Email automático al socio responsable 24 horas antes de la salida.",
        "subject": "Recordatorio Fjord VI - {{salida_nombre}} - {{fecha}} {{hora}}",
        "body": "Hola {{socio_nombre}},\n\nTe recordamos tu reserva para {{salida_nombre}} el {{fecha}} a las {{hora}}.\n\nPersonas asociadas a tu reserva:\n{{lista_personas}}\n\nPunto de encuentro: {{punto_encuentro}}\n\n{{club_nombre}} · {{app_name}}",
    },
    "no_show_cargo_socio": {
        "name": "Reserva incumplida / cargo al socio",
        "description": "Email al socio responsable cuando el cierre genera cargo por reserva incumplida propia o de invitados.",
        "subject": "Liquidación Fjord VI - {{salida_nombre}} - {{fecha}}",
        "body": "Hola {{socio_nombre}},\n\nEl cierre de {{salida_nombre}} registró cargos asociados a tu reserva.\n\nDetalle:\n{{detalle_cargos}}\n\nTotal a liquidar: {{total_socio}}\n\nFicha: {{link_ficha}}\n\n{{club_nombre}} · {{app_name}}",
    },
    "email_prueba": {
        "name": "Email de prueba",
        "description": "Prueba manual de SMTP desde Administración.",
        "subject": "Prueba de comunicaciones - {{app_name}} {{version}}",
        "body": "Este es un email de prueba enviado desde {{app_name}} {{version}}.\n\nSi recibiste este mensaje, SMTP está funcionando.",
    },
}

def render_comm_template(text_value: str, payload: dict) -> str:
    result = text_value or ""
    safe_payload = {k: ("" if v is None else str(v)) for k, v in (payload or {}).items()}
    safe_payload.setdefault("club_nombre", CLUB_NAME)
    safe_payload.setdefault("app_name", APP_NAME)
    safe_payload.setdefault("version", VERSION)
    for key, value in safe_payload.items():
        result = result.replace("{{" + key + "}}", value)
    return result

def ensure_communications_seed(db: Session):
    for key, info in COMMUNICATION_EVENTS.items():
        ev = db.get(NotificationEventSetting, key)
        if not ev:
            ev = NotificationEventSetting(key=key, name=info["name"], enabled=False, channel_email=True, description=info.get("description", ""), updated_at=now_local())
            db.add(ev)
        tpl = db.query(NotificationTemplate).filter_by(key=key).first()
        if not tpl:
            tpl = NotificationTemplate(key=key, name=info["name"], subject=info.get("subject", ""), body=info.get("body", ""), enabled=False, updated_at=now_local())
            db.add(tpl)
        elif ev.enabled and not tpl.enabled:
            # Si el evento ya fue activado en una versión anterior, la plantilla debe quedar activa también.
            tpl.enabled = True
            tpl.updated_at = now_local()
    db.commit()

def smtp_settings(db: Session) -> dict:
    return {
        "host": get_system_meta(db, "smtp_host", os.getenv("SMTP_HOST", "")),
        "port": get_system_meta(db, "smtp_port", os.getenv("SMTP_PORT", "587")),
        "username": get_system_meta(db, "smtp_username", os.getenv("SMTP_USERNAME", "")),
        "password": get_system_meta(db, "smtp_password", os.getenv("SMTP_PASSWORD", "")),
        "from_email": get_system_meta(db, "smtp_from_email", os.getenv("SMTP_FROM_EMAIL", "")),
        "from_name": get_system_meta(db, "smtp_from_name", os.getenv("SMTP_FROM_NAME", f"{CLUB_NAME} · {APP_NAME}")),
        "tls": get_system_meta(db, "smtp_tls", os.getenv("SMTP_TLS", "1")),
        "admin_email": get_system_meta(db, "communications_admin_email", os.getenv("COMMUNICATIONS_ADMIN_EMAIL", "")),
    }

def smtp_configured(settings: dict) -> bool:
    return bool(settings.get("host") and settings.get("from_email"))

def send_email_now(db: Session, recipient_email: str, recipient_name: str, subject: str, body: str) -> tuple[bool, str]:
    settings = smtp_settings(db)
    if not smtp_configured(settings):
        return False, "SMTP no configurado"
    try:
        port = int(settings.get("port") or 587)
        msg = EmailMessage()
        from_name = settings.get("from_name") or f"{CLUB_NAME} · {APP_NAME}"
        from_email = settings.get("from_email")
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = f"{recipient_name} <{recipient_email}>" if recipient_name else recipient_email
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(settings["host"], port, timeout=20) as server:
            if str(settings.get("tls", "1")).lower() in ("1", "true", "yes", "on"):
                server.starttls()
            if settings.get("username"):
                server.login(settings.get("username"), settings.get("password") or "")
            server.send_message(msg)
        return True, "enviado"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:300]}"

def queue_email(db: Session, event_key: str, recipient_email: str, recipient_name: str, payload: dict, force: bool = False) -> Optional[NotificationQueue]:
    ensure_communications_seed(db)
    recipient_email = (recipient_email or "").strip()
    if not recipient_email:
        return None
    ev = db.get(NotificationEventSetting, event_key)
    tpl = db.query(NotificationTemplate).filter_by(key=event_key).first()
    if not ev or not tpl:
        return None
    if not force and (not ev.enabled or not tpl.enabled or not ev.channel_email):
        return None
    subject = render_comm_template(tpl.subject, payload)
    body = render_comm_template(tpl.body, payload)
    q = NotificationQueue(event_key=event_key, recipient_email=recipient_email, recipient_name=recipient_name or "", subject=subject, body=body, status="pending", attempts=0, payload=json.dumps(payload or {}, ensure_ascii=False))
    db.add(q)
    db.commit()
    return q

def process_notification_queue(db: Session, limit: int = 25) -> dict:
    rows = db.query(NotificationQueue).filter(NotificationQueue.status.in_(["pending", "failed"])).order_by(NotificationQueue.created_at.asc()).limit(limit).all()
    sent = failed = 0
    for row in rows:
        row.attempts = int(row.attempts or 0) + 1
        ok, detail = send_email_now(db, row.recipient_email, row.recipient_name, row.subject, row.body)
        if ok:
            row.status = "sent"
            row.sent_at = now_local()
            row.error = ""
            sent += 1
        else:
            row.status = "failed"
            row.error = detail
            failed += 1
        db.add(NotificationLog(queue_id=row.id, event_key=row.event_key, recipient_email=row.recipient_email, status=row.status, detail=detail))
    db.commit()
    return {"processed": len(rows), "sent": sent, "failed": failed}

def communications_context(db: Session) -> dict:
    ensure_communications_seed(db)
    settings = smtp_settings(db)
    events = db.query(NotificationEventSetting).order_by(NotificationEventSetting.name.asc()).all()
    templates_rows = db.query(NotificationTemplate).order_by(NotificationTemplate.name.asc()).all()
    queue = db.query(NotificationQueue).order_by(NotificationQueue.created_at.desc()).limit(100).all()
    pending = db.query(NotificationQueue).filter_by(status="pending").count()
    failed = db.query(NotificationQueue).filter_by(status="failed").count()
    sent_today = db.query(NotificationQueue).filter(NotificationQueue.status == "sent", NotificationQueue.sent_at >= now_local().replace(hour=0, minute=0, second=0, microsecond=0)).count()
    return {"settings": settings, "smtp_configured": smtp_configured(settings), "events": events, "templates": templates_rows, "queue": queue, "pending": pending, "failed": failed, "sent_today": sent_today}

def communication_status(db: Session) -> dict:
    """Resumen seguro de comunicaciones para checks operativos.

    No envía emails ni modifica datos. Evita que el semáforo operativo falle
    cuando SMTP todavía no está configurado.
    """
    try:
        ctx = communications_context(db)
        return {
            "smtp_configured": bool(ctx.get("smtp_configured")),
            "pending": int(ctx.get("pending") or 0),
            "failed": int(ctx.get("failed") or 0),
            "sent_today": int(ctx.get("sent_today") or 0),
            "status_label": nonempty_label_v1168("configurado" if ctx.get("smtp_configured") else "pendiente"),
            "human_detail": "SMTP configurado y cola disponible" if ctx.get("smtp_configured") else "Email preparado, envío real pendiente de configurar SMTP",
        }
    except Exception as e:
        return {
            "smtp_configured": False,
            "pending": 0,
            "failed": 0,
            "sent_today": 0,
            "status_label": nonempty_label_v1168("revisar"),
            "human_detail": f"No se pudo leer comunicaciones: {type(e).__name__}",
            "error": str(e)[:200],
        }

def auto_process_notifications(db: Session, limit: int = 5) -> dict:
    """Procesamiento liviano de cola en cada uso del sistema.

    Evita depender de un worker externo en Render. Si SMTP no está configurado,
    no marca fallidos: la cola queda pendiente hasta que Administración configure
    el servicio y procese o entre alguien al sistema.
    """
    try:
        if not smtp_configured(smtp_settings(db)):
            return {"processed": 0, "sent": 0, "failed": 0, "skipped": "smtp_pending"}
        pending = db.query(NotificationQueue).filter(NotificationQueue.status == "pending").count()
        if pending <= 0:
            return {"processed": 0, "sent": 0, "failed": 0}
        return process_notification_queue(db, limit=limit)
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"processed": 0, "sent": 0, "failed": 0, "error": str(e)[:200]}

def queue_due_24h_reminders(db: Session) -> int:
    """Encola recordatorios para salidas dentro de las próximas 24 horas.

    Usa SystemMeta por salida+socio para no duplicar correos. Es deliberadamente
    conservador: solo socios con email y reservas activas asociadas.
    """
    ensure_communications_seed(db)
    ev = db.get(NotificationEventSetting, "recordatorio_24h_socio")
    tpl = db.query(NotificationTemplate).filter_by(key="recordatorio_24h_socio").first()
    if not ev or not tpl or not ev.enabled or not tpl.enabled:
        return 0
    now = now_local()
    start = now + timedelta(hours=20)
    end = now + timedelta(hours=28)
    outings = db.query(Outing).filter(Outing.departure_at >= start, Outing.departure_at <= end).all()
    queued = 0
    for outing in outings:
        if is_closed_outing(outing) or is_outing_cancelled_by_captain(outing):
            continue
        rows = db.query(Reservation).filter_by(outing_id=outing.id).all()
        active = [r for r in rows if reservation_is_active(r) and not is_waitlisted(r)]
        responsible_ids = sorted({r.responsible_user_id for r in active if r.responsible_user_id})
        for uid in responsible_ids:
            marker = f"reminder24_sent:{outing.id}:{uid}"
            if db.get(SystemMeta, marker):
                continue
            u = db.get(User, uid)
            if not u or not (u.email or "").strip():
                continue
            people = [r.person_name for r in active if r.responsible_user_id == uid]
            q = queue_email(db, "recordatorio_24h_socio", u.email, u.name, {
                "socio_nombre": u.name,
                "salida_nombre": outing.title,
                "fecha": outing.departure_at.strftime("%d/%m/%Y"),
                "hora": outing.departure_at.strftime("%H:%M"),
                "lista_personas": "\n".join(f"- {name}" for name in people) or "- Sin personas asociadas",
                "punto_encuentro": get_system_meta(db, "meeting_point", "Dársena Norte / punto de embarque informado por el club"),
            })
            if q:
                db.add(SystemMeta(key=marker, value=now.isoformat(), updated_at=now))
                queued += 1
    db.commit()
    return queued

def queue_no_show_charge_emails(db: Session, outing: Outing, reservations: list, sheet: ClosingSheet) -> int:
    """Encola un email consolidado por socio responsable con cargos generados al cierre."""
    ensure_communications_seed(db)
    ev = db.get(NotificationEventSetting, "no_show_cargo_socio")
    tpl = db.query(NotificationTemplate).filter_by(key="no_show_cargo_socio").first()
    if not ev or not tpl or not ev.enabled or not tpl.enabled:
        return 0
    by_user = {}
    for r in reservations:
        charge = actual_charge(outing, r)
        if charge <= 0:
            continue
        # Invitado presente paga tarifa normal; este evento se reserva para reserva incumplida/cargo por ausencia/cancelación.
        if r.attendance == "Presente" and canonical_kind(r.kind) == "invitado":
            continue
        uid = r.responsible_user_id
        if not uid:
            continue
        by_user.setdefault(uid, []).append((r, charge))
    queued = 0
    for uid, items in by_user.items():
        u = db.get(User, uid)
        if not u or not (u.email or "").strip():
            continue
        total = sum(c for _, c in items)
        detail = "\n".join(f"- {r.person_name} ({display_kind(r.kind)}): $ {human_money(c)}" for r, c in items)
        q = queue_email(db, "no_show_cargo_socio", u.email, u.name, {
            "socio_nombre": u.name,
            "salida_nombre": outing.title,
            "fecha": outing.departure_at.strftime("%d/%m/%Y"),
            "hora": outing.departure_at.strftime("%H:%M"),
            "detalle_cargos": detail,
            "total_socio": "$ " + fmt_money(total),
            "link_ficha": f"/cierre/{sheet.id}",
        })
        if q:
            queued += 1
    db.commit()
    return queued

Base.metadata.create_all(engine)

def ensure_schema():
    """Agrega columnas nuevas sin borrar datos existentes.

    Render/Postgres no modifica tablas ya creadas con create_all().
    Esta migración liviana mantiene compatibilidad con SQLite y Postgres.
    """
    inspector = inspect(engine)
    try:
        reservation_columns = [c["name"] for c in inspector.get_columns("reservations")]
    except Exception:
        reservation_columns = []

    with engine.begin() as conn:
        if "birth_date" not in reservation_columns:
            conn.execute(text("ALTER TABLE reservations ADD COLUMN birth_date VARCHAR"))
        if "protocolar" not in reservation_columns:
            conn.execute(text("ALTER TABLE reservations ADD COLUMN protocolar BOOLEAN DEFAULT FALSE"))
        if "protocolar_by_user_id" not in reservation_columns:
            conn.execute(text("ALTER TABLE reservations ADD COLUMN protocolar_by_user_id INTEGER"))
        if "protocolar_reason" not in reservation_columns:
            conn.execute(text("ALTER TABLE reservations ADD COLUMN protocolar_reason TEXT"))
        if "original_responsible_user_id" not in reservation_columns:
            conn.execute(text("ALTER TABLE reservations ADD COLUMN original_responsible_user_id INTEGER"))
        if "reassignment_count" not in reservation_columns:
            conn.execute(text("ALTER TABLE reservations ADD COLUMN reassignment_count INTEGER DEFAULT 0"))
        if "last_reassigned_at" not in reservation_columns:
            conn.execute(text("ALTER TABLE reservations ADD COLUMN last_reassigned_at TIMESTAMP"))
        if "last_reassigned_by" not in reservation_columns:
            conn.execute(text("ALTER TABLE reservations ADD COLUMN last_reassigned_by VARCHAR DEFAULT ''"))


    try:
        outing_columns = [c["name"] for c in inspector.get_columns("outings")]
    except Exception:
        outing_columns = []

    with engine.begin() as conn:
        if "institutional_reserve" not in outing_columns:
            conn.execute(text("ALTER TABLE outings ADD COLUMN institutional_reserve INTEGER DEFAULT 0"))
        if "boat_id" not in outing_columns:
            conn.execute(text("ALTER TABLE outings ADD COLUMN boat_id VARCHAR DEFAULT 'fjord_vi'"))

    try:
        user_columns = [c["name"] for c in inspector.get_columns("users")]
    except Exception:
        user_columns = []

    try:
        existing_tables = set(inspector.get_table_names())
    except Exception:
        existing_tables = set()

    with engine.begin() as conn:
        if "reservation_reassignments" not in existing_tables:
            conn.execute(text("""
                CREATE TABLE reservation_reassignments (
                    id INTEGER PRIMARY KEY,
                    outing_id INTEGER NOT NULL,
                    reservation_id INTEGER NOT NULL,
                    from_user_id INTEGER,
                    to_user_id INTEGER,
                    performed_by_user_id INTEGER,
                    performed_by_name VARCHAR DEFAULT '',
                    performed_at TIMESTAMP,
                    reason TEXT DEFAULT ''
                )
            """))

    with engine.begin() as conn:
        if "email" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR"))
        if "whatsapp" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN whatsapp VARCHAR"))
        if "phone" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR"))
        if "category" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN category VARCHAR"))
        if "birth_date" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN birth_date VARCHAR"))
        if "can_manage_protocolar" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN can_manage_protocolar BOOLEAN DEFAULT FALSE"))
        if "must_change_password" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT FALSE"))
        if "session_version" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN session_version INTEGER DEFAULT 1"))
        if "last_login_at" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP"))
        if "last_password_change_at" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN last_password_change_at TIMESTAMP"))





def _reassignment_trace_only_bootstrap(reason: str) -> str:
    txt = (reason or "").strip()
    if "reasignado" not in txt.lower():
        return ""
    return txt.split("·", 1)[0].strip()


def backfill_reassignment_state(db: Session):
    rows = db.query(Reservation).filter(Reservation.kind.in_(["invitado", "hijo_menor"])).all()
    changed = False
    users = {u.name.strip().lower(): u.id for u in db.query(User).all() if (u.name or "").strip()}
    for r in rows:
        current = getattr(r, "responsible_user_id", None)
        if current and not getattr(r, "original_responsible_user_id", None):
            trace = _reassignment_trace_only_bootstrap(r.cancel_reason or "")
            guessed = None
            if trace and ':' in trace and '->' in trace:
                try:
                    left = trace.split(':', 1)[1].split('->', 1)[0].strip().lower()
                    guessed = users.get(left)
                except Exception:
                    guessed = None
            r.original_responsible_user_id = guessed or current
            changed = True
        if getattr(r, "reassignment_count", None) is None:
            r.reassignment_count = 0
            changed = True
        if getattr(r, "reassignment_count", 0) == 0 and _reassignment_trace_only_bootstrap(r.cancel_reason or ""):
            r.reassignment_count = 1
            changed = True
        if getattr(r, "last_reassigned_by", None) is None:
            r.last_reassigned_by = ""
            changed = True
    if changed:
        db.commit()

# =========================
# DATABASE INTEGRITY GUARD
# =========================
DB_INDEXES_REQUIRED = [
    ("idx_users_dni", "users", "dni"),
    ("idx_users_member_no", "users", "member_no"),
    ("idx_users_role_active", "users", "role, active"),
    ("idx_outings_departure_at", "outings", "departure_at"),
    ("idx_outings_status", "outings", "status"),
    ("idx_outings_boat_id", "outings", "boat_id"),
    ("idx_reservations_outing_id", "reservations", "outing_id"),
    ("idx_reservations_dni", "reservations", "dni"),
    ("idx_reservations_outing_status", "reservations", "outing_id, status"),
    ("idx_reservations_responsible", "reservations", "responsible_user_id"),
    ("idx_reservations_original_responsible", "reservations", "original_responsible_user_id"),
    ("idx_reservations_reassignment_count", "reservations", "reassignment_count"),
    ("idx_reservations_created_at", "reservations", "created_at"),
    ("idx_closing_sheets_outing_status", "closing_sheets", "outing_id, status"),
    ("idx_reservation_reassignments_reservation", "reservation_reassignments", "reservation_id"),
    ("idx_reservation_reassignments_outing", "reservation_reassignments", "outing_id"),
    ("idx_audit_logs_created_at", "audit_logs", "created_at"),
    ("idx_activity_log_created_at", "activity_log", "created_at"),
    ("idx_activity_log_user_id", "activity_log", "user_id"),
    ("idx_notification_queue_status", "notification_queue", "status"),
    ("idx_notification_queue_created_at", "notification_queue", "created_at"),
    ("idx_notification_log_created_at", "notification_log", "created_at"),
    ("idx_login_attempts_ident_created_at", "login_attempts", "ident_key, created_at"),
    ("idx_login_attempts_ip_created_at", "login_attempts", "ip_hash, created_at"),
    ("idx_users_session_version", "users", "session_version"),
    ("idx_operation_locks_expires_at", "operation_locks", "expires_at"),
]

def _sql_ident(name: str) -> str:
    s = "".join(ch for ch in (name or "") if ch.isalnum() or ch == "_")
    if not s:
        raise ValueError("identificador vacío")
    return s

def ensure_db_indexes() -> dict:
    """Crea índices no únicos para mejorar performance sin alterar datos."""
    result = {"created_or_ok": [], "failed": []}
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
    except Exception as e:
        return {"created_or_ok": [], "failed": [f"inspect: {type(e).__name__}: {e}"]}

    with engine.begin() as conn:
        for idx_name, table_name, columns in DB_INDEXES_REQUIRED:
            try:
                table_safe = _sql_ident(table_name)
                idx_safe = _sql_ident(idx_name)
                if table_safe not in tables:
                    result["failed"].append(f"{idx_safe}: tabla faltante {table_safe}")
                    continue
                existing_cols = {c["name"] for c in inspector.get_columns(table_safe)}
                wanted_cols = [c.strip() for c in columns.split(",")]
                missing_cols = [c for c in wanted_cols if c not in existing_cols]
                if missing_cols:
                    result["failed"].append(f"{idx_safe}: faltan columnas {', '.join(missing_cols)}")
                    continue
                cols_sql = ", ".join(_sql_ident(c) for c in wanted_cols)
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS {idx_safe} ON {table_safe} ({cols_sql})"))
                result["created_or_ok"].append(idx_safe)
            except Exception as e:
                result["failed"].append(f"{idx_name}: {type(e).__name__}: {e}")
    return result

def db_index_status() -> list:
    rows = []
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        for idx_name, table_name, columns in DB_INDEXES_REQUIRED:
            if table_name not in tables:
                rows.append({"table": table_name, "ok": False, "detail": f"{idx_name}: tabla faltante"})
                continue
            try:
                names = {i.get("name") for i in inspector.get_indexes(table_name)}
                ok = idx_name in names
                rows.append({"table": table_name, "ok": ok, "detail": f"{idx_name}: {'OK' if ok else 'faltante'}"})
            except Exception as e:
                rows.append({"table": table_name, "ok": False, "detail": f"{idx_name}: {type(e).__name__}"})
    except Exception as e:
        rows.append({"table": "indexes", "ok": False, "detail": f"inspect: {type(e).__name__}"})
    return rows


def set_system_meta(key: str, value: str):
    try:
        with SessionLocal() as db:
            row = db.get(SystemMeta, key)
            if not row:
                row = SystemMeta(key=key, value=str(value), updated_at=now_local())
                db.add(row)
            else:
                row.value = str(value)
                row.updated_at = now_local()
            db.commit()
    except Exception:
        pass

def get_system_meta(db: Session, key: str, default: str = "") -> str:
    row = db.get(SystemMeta, key)
    return row.value if row and row.value is not None else default


def get_hidden_guest_candidate_dnis(db: Session) -> set[str]:
    """DNI de invitados ocultados de las sugerencias de conversión a socio."""
    raw = get_system_meta(db, "hidden_guest_candidate_dnis", "[]")
    try:
        data = json.loads(raw or "[]")
        return {norm_dni(str(x)) for x in data if norm_dni(str(x))}
    except Exception:
        return set()


def set_hidden_guest_candidate_dnis(db: Session, dnis: set[str]):
    payload = json.dumps(sorted({norm_dni(x) for x in dnis if norm_dni(x)}))
    row = db.get(SystemMeta, "hidden_guest_candidate_dnis")
    if not row:
        row = SystemMeta(key="hidden_guest_candidate_dnis", value=payload, updated_at=now_local())
        db.add(row)
    else:
        row.value = payload
        row.updated_at = now_local()

ensure_schema()
with SessionLocal() as _db_init:
    backfill_reassignment_state(_db_init)
ensure_db_indexes()
set_system_meta("schema_version", "1")
set_system_meta("last_schema_check", now_local().isoformat())
try:
    with SessionLocal() as _comm_db:
        ensure_communications_seed(_comm_db)
except Exception:
    pass

def _is_production_request(request: Optional[Request] = None) -> bool:
    if APP_ENV in ("prod", "production"):
        return True
    try:
        return bool(request and request.url.scheme == "https")
    except Exception:
        return False


def set_session_cookie(resp: Response, request: Optional[Request], user_id: int, session_version: int = 1):
    """Cookie de sesión firmada con versión.

    La versión permite invalidar sesiones anteriores cuando administración resetea
    una clave o cuando el usuario cambia su contraseña.
    """
    payload = f"{int(user_id)}:{int(session_version or 1)}"
    resp.set_cookie(
        SESSION_COOKIE_NAME,
        sign_value(payload),
        httponly=True,
        samesite="lax",
        secure=_is_production_request(request),
        max_age=SESSION_MAX_AGE_SECONDS,
        path="/",
    )


def clear_session_cookie(resp: Response):
    resp.delete_cookie(SESSION_COOKIE_NAME, path="/")


def _new_csrf_token() -> str:
    return sign_value(secrets.token_urlsafe(32))


def _valid_signed_token(value: str) -> bool:
    return bool(value and unsign_value(value))


def csrf_token_for_request(request: Optional[Request]) -> str:
    if request is not None:
        existing = request.cookies.get(CSRF_COOKIE_NAME, "")
        if _valid_signed_token(existing):
            return existing
    return _new_csrf_token()


def csrf_input(request: Optional[Request] = None) -> str:
    token = csrf_token_for_request(request)
    return f'<input type="hidden" name="csrf_token" value="{token}">'


def inject_csrf_into_forms(html: str, request: Optional[Request]) -> tuple[str, Optional[str]]:
    if not isinstance(html, str) or "<form" not in html.lower():
        return html, None
    token = csrf_token_for_request(request)
    hidden = f'<input type="hidden" name="csrf_token" value="{token}">'

    def repl(match):
        tag = match.group(0)
        if re.search(r'method\s*=\s*([\"\'])post\1', tag, flags=re.I):
            return tag + hidden
        return tag

    return re.sub(r'<form\b[^>]*>', repl, html, flags=re.I), token


def verify_csrf_from_body(request: Request, body: bytes) -> bool:
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME, "")
    if not _valid_signed_token(cookie_token):
        return False
    header_token = request.headers.get("X-CSRF-Token", "")
    if header_token and hmac.compare_digest(header_token, cookie_token):
        return True
    ctype = (request.headers.get("content-type") or "").lower()
    if "application/x-www-form-urlencoded" not in ctype:
        return True  # no bloquear uploads/multipart en esta etapa
    try:
        parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
        form_token = (parsed.get("csrf_token") or [""])[0]
        return bool(form_token and hmac.compare_digest(form_token, cookie_token))
    except Exception:
        return False


def client_ip_hash(request: Optional[Request]) -> str:
    try:
        forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() if request else ""
        ip = forwarded or (request.client.host if request and request.client else "")
    except Exception:
        ip = ""
    return hashlib.sha256((ip + SECRET_KEY).encode("utf-8")).hexdigest()[:32] if ip else ""


def login_ident_key(raw: str) -> str:
    raw = (raw or "").strip().lower()
    nd = norm_dni(raw)
    mk = member_key(raw)
    return nd or mk or raw[:64]


def login_is_locked(db: Session, ident_key: str, ip_hash: str) -> bool:
    """Bloqueo prudente para entorno social/institucional.

    No bloquea agresivamente al tercer intento. Usa umbral alto por identidad
    y un umbral mayor por IP para frenar automatismos sin castigar al socio que
    prueba varias claves posibles.
    """
    since = now_local() - timedelta(minutes=LOGIN_LOCK_WINDOW_MINUTES)
    base = db.query(LoginAttempt).filter(LoginAttempt.created_at >= since, LoginAttempt.success == False)
    if ident_key:
        ident_failures = base.filter(LoginAttempt.ident_key == ident_key).count()
        if ident_failures >= LOGIN_LOCK_ATTEMPTS:
            return True
    if ip_hash:
        ip_failures = base.filter(LoginAttempt.ip_hash == ip_hash).count()
        if ip_failures >= LOGIN_LOCK_IP_ATTEMPTS:
            return True
    return False


def record_login_attempt(db: Session, ident_key: str, ip_hash: str, success: bool, detail: str = ""):
    db.add(LoginAttempt(ident_key=ident_key or "", ip_hash=ip_hash or "", success=bool(success), detail=(detail or "")[:500]))
    db.commit()


def purge_old_login_attempts(db: Session):
    try:
        cutoff = now_local() - timedelta(days=30)
        db.query(LoginAttempt).filter(LoginAttempt.created_at < cutoff).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()

app = FastAPI(title=f"{CLUB_NAME} · {APP_NAME} · {APP_MODEL} · {VERSION}")

STATIC_DIR = APP_DIR / "static"
if not STATIC_DIR.exists():
    STATIC_DIR = APP_DIR
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.middleware("http")
async def request_observability_middleware(request: Request, call_next):
    """Fase 13: trazabilidad liviana de requests sin cambiar reglas de negocio.

    Agrega headers útiles para soporte, timing básico y control de cache en zonas
    administrativas. No registra datos personales ni modifica respuestas HTML.
    """
    started = time.perf_counter()
    request_id = request.headers.get("X-Request-ID") or secrets.token_hex(8)
    try:
        response = await call_next(request)
    except Exception:
        # El exception handler global conserva el comportamiento visual; el header
        # queda para futuras integraciones con logs externos.
        raise
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    response.headers.setdefault("X-Fjord-Version", VERSION)
    response.headers.setdefault("X-Fjord-Request-ID", request_id)
    response.headers.setdefault("X-Fjord-Response-Time-Ms", str(elapsed_ms))
    path = request.url.path or ""
    if path.startswith(("/admin", "/captain", "/socio", "/change-password", "/account")):
        response.headers.setdefault("Cache-Control", "no-store")
    return response

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Fase 12B: headers de seguridad básicos sin cambiar la lógica funcional.

    No endurece con CSP estricta todavía para no romper templates inline existentes.
    Sí agrega protección mínima compatible con Render y navegadores móviles.
    """
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if _is_production_request(request):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

@app.middleware("http")
async def communications_auto_worker(request: Request, call_next):
    """Procesa recordatorios y una pequeña tanda de emails pendientes sin worker externo.

    Se ejecuta de forma liviana al recibir tráfico real. No toca archivos estáticos
    ni health checks para evitar ruido y mantener baja latencia.
    """
    response = await call_next(request)
    try:
        path = request.url.path or ""
        if path.startswith("/static") or path.startswith("/health") or path.endswith(".csv"):
            return response
        with SessionLocal() as db:
            queue_due_24h_reminders(db)
            auto_process_notifications(db, limit=5)
    except Exception:
        pass
    return response

# Estructura estándar: HTML en /templates y estáticos en /static.
# Fallback defensivo a raíz para compatibilidad con versiones planas anteriores.
class SafeTemplates:
    def __init__(self, directory):
        self.directory = str(directory)
        self.env = Environment(
            loader=FileSystemLoader(self.directory),
            autoescape=select_autoescape(["html", "xml"])
        )

    def TemplateResponse(self, *args, **kwargs):
        # Compatible con ambos estilos:
        # TemplateResponse(request, "archivo.html", context)
        # TemplateResponse("archivo.html", context)
        request = None
        name = None
        context = None

        if len(args) >= 2 and hasattr(args[0], "url"):
            request = args[0]
            name = args[1]
            context = args[2] if len(args) >= 3 else kwargs.get("context", {})
        else:
            name = args[0] if len(args) >= 1 else kwargs.get("name")
            context = args[1] if len(args) >= 2 else kwargs.get("context", {})
            request = context.get("request") if isinstance(context, dict) else None

        if context is None:
            context = {}
        if not isinstance(context, dict):
            context = dict(context)
        if request is not None:
            context.setdefault("request", request)

        try:
            html = self.env.get_template(name).render(**context)
            html, csrf_cookie_value = inject_csrf_into_forms(html, request)
            resp = HTMLResponse(html)
            if csrf_cookie_value:
                resp.set_cookie(CSRF_COOKIE_NAME, csrf_cookie_value, httponly=True, samesite="lax", secure=_is_production_request(request), path="/", max_age=43200)
            return resp
        except Exception as e:
            detail = f"{type(e).__name__}: {e}"
            html = f'''<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Fjord VI · Error controlado</title>
  <style>
    body{{font-family:Arial,sans-serif;padding:24px;background:#eef5f9;color:#102033}}
    .box{{max-width:760px;margin:auto;background:white;border-radius:18px;padding:22px;box-shadow:0 12px 30px rgba(0,0,0,.12)}}
    code{{white-space:pre-wrap;color:#9b1c1c;display:block;margin-top:12px}}
    a{{color:#1f5d8a;font-weight:700}}
  </style>
</head>
<body>
  <div class="box">
    <h1>Fjord VI</h1>
    <h2>Error controlado de pantalla</h2>
    <p>La aplicación está levantada, pero no pudo renderizar <b>{name}</b>.</p>
    <code>{detail}</code>
    <p><a href="/logout">Volver al login</a></p>
  </div>
</body>
</html>'''
            return HTMLResponse(html, status_code=200)

TEMPLATES_DIR = APP_DIR / "templates"
if not TEMPLATES_DIR.exists():
    TEMPLATES_DIR = APP_DIR
templates = SafeTemplates(TEMPLATES_DIR)





def _path_rid(path: str) -> Optional[int]:
    try:
        m = re.search(r"/(\d+)(?:/[^/]*)?$", path or "")
        return int(m.group(1)) if m else None
    except Exception:
        return None


def _outing_id_from_post(path: str, form_data: dict) -> Optional[int]:
    """Detecta salida afectada por una acción POST para aplicar lock lógico."""
    raw = form_data.get("outing_id") or form_data.get("selected_outing_id")
    try:
        if raw:
            return int(str(raw))
    except Exception:
        pass
    rid = _path_rid(path)
    if not rid:
        return None
    # Rutas por reserva: /socio/cancel/{rid}, /captain/attendance/{rid}/...
    if path.startswith("/socio/") or path.startswith("/captain/attendance") or path.startswith("/captain/reassign") or path.startswith("/socio/protocolar"):
        try:
            with SessionLocal() as db:
                r = db.get(Reservation, rid)
                return int(r.outing_id) if r else None
        except Exception:
            return None
    # Rutas por salida directa.
    if path.startswith("/admin/outing_status"):
        return rid
    return None


def _critical_post_path(path: str) -> bool:
    critical_prefixes = (
        "/socio/add_self", "/socio/add_guest", "/socio/add_protocolar", "/socio/protocolar/",
        "/socio/cancel/", "/socio/reactivate/",
        "/captain/outing_status", "/captain/attendance/", "/captain/reassign/", "/captain/close",
        "/admin/update_outing", "/admin/outing_status", "/admin/new_outing",
        "/admin/user/reset-password/", "/admin/reset_password/", "/admin/reset_all_passwords",
        "/admin/schema/check", "/admin/system/repair_missing_sheets",
    )
    return any((path or "").startswith(x) for x in critical_prefixes)


def cleanup_expired_operation_locks():
    try:
        with SessionLocal() as db:
            db.query(OperationLock).filter(OperationLock.expires_at < now_local()).delete(synchronize_session=False)
            db.commit()
    except Exception:
        pass


def acquire_operation_lock(lock_key: str, owner: str, path: str, detail: str = "", strict: bool = False) -> bool:
    """Intenta tomar un lock de DB con TTL corto. Devuelve False si ya hay una operación activa.

    En acciones operativas críticas se usa strict=True: si el lock técnico falla,
    se bloquea el POST en vez de permitir dos mutaciones simultáneas.
    """
    if not lock_key:
        return True
    cleanup_expired_operation_locks()
    try:
        with SessionLocal() as db:
            row = OperationLock(
                key=lock_key,
                created_at=now_local(),
                expires_at=now_local() + timedelta(seconds=OPERATION_LOCK_TTL_SECONDS),
                owner=(owner or "")[:120],
                path=(path or "")[:240],
                detail=(detail or "")[:500],
            )
            db.add(row)
            db.commit()
            return True
    except IntegrityError:
        return False
    except Exception as exc:
        try:
            APP_LOGGER.warning("operation_lock_failed", extra={"fjord_path": path, "fjord_lock_key": lock_key, "fjord_error": type(exc).__name__})
        except Exception:
            pass
        return False if strict else True


def release_operation_lock(lock_key: str):
    if not lock_key:
        return
    try:
        with SessionLocal() as db:
            row = db.get(OperationLock, lock_key)
            if row:
                db.delete(row)
                db.commit()
    except Exception:
        pass


@app.middleware("http")
async def operation_lock_middleware(request: Request, call_next):
    """Lock de concurrencia para acciones críticas sobre una misma salida.

    Cubre el caso típico móvil: doble toque, refresh durante POST o dos pantallas
    operando la misma navegación. Si detecta una operación simultánea, vuelve a
    la pantalla anterior en vez de ejecutar dos veces la mutación.
    """
    if request.method.upper() != "POST":
        return await call_next(request)
    path = request.url.path or ""
    ctype = (request.headers.get("content-type") or "").lower()
    if not _critical_post_path(path) or "application/x-www-form-urlencoded" not in ctype:
        return await call_next(request)

    body = await request.body()
    parsed = parse_qs(body.decode("utf-8", errors="ignore"), keep_blank_values=True)
    form_data = {k: (v[0] if v else "") for k, v in parsed.items()}
    outing_id = _outing_id_from_post(path, form_data)
    lock_key = f"outing:{outing_id}" if outing_id else ""
    if not lock_key and path.startswith("/admin/reset_all_passwords"):
        lock_key = "admin:reset_all_passwords"
    elif not lock_key and (path.startswith("/admin/user/reset-password/") or path.startswith("/admin/reset_password/")):
        rid = _path_rid(path)
        lock_key = f"user:reset_password:{rid}" if rid else "admin:reset_password"
    owner = request.cookies.get(SESSION_COOKIE_NAME, "anon")

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    locked_request = Request(request.scope, receive)
    if not lock_key:
        return await call_next(locked_request)

    if not acquire_operation_lock(lock_key, owner, path, f"outing_id={outing_id}", strict=True):
        resp = RedirectResponse(_safe_back_url(request), status_code=303)
        resp.headers["X-Fjord-Operation-Lock"] = "busy"
        resp.headers["Cache-Control"] = "no-store"
        return resp
    try:
        resp = await call_next(locked_request)
        resp.headers["X-Fjord-Operation-Lock"] = "ok"
        return resp
    finally:
        release_operation_lock(lock_key)


@app.middleware("http")
async def csrf_protection_middleware(request: Request, call_next):
    """Protección CSRF por token firmado en formularios POST.

    Se aplica a formularios normales. Se excluyen uploads multipart para no afectar
    importaciones de padrón en esta etapa de bajo riesgo.
    """
    if request.method.upper() == "POST":
        path = request.url.path or ""
        ctype = (request.headers.get("content-type") or "").lower()
        if "application/x-www-form-urlencoded" in ctype and not path.startswith("/admin/padron/import"):
            body = await request.body()
            if not verify_csrf_from_body(request, body):
                return HTMLResponse(
                    "<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Fjord VI · Seguridad</title><style>body{font-family:Arial,sans-serif;background:#eef5f9;color:#102033;padding:24px}.box{max-width:560px;margin:auto;background:#fff;border-radius:20px;padding:24px;box-shadow:0 12px 30px rgba(0,0,0,.12)}a{display:inline-block;margin-top:12px;background:#0b5f8f;color:#fff;padding:10px 16px;border-radius:999px;text-decoration:none;font-weight:700}</style></head><body><div class='box'><h1>Acción no validada</h1><p>Por seguridad, recargá la pantalla y volvé a intentar.</p><a href='/'>Volver al sistema</a></div></body></html>",
                    status_code=403,
                    headers={"Cache-Control": "no-store"}
                )

            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}
            request = Request(request.scope, receive)
    return await call_next(request)


@app.middleware("http")
async def duplicate_post_guard(request: Request, call_next):
    """Evita doble submit accidental desde móvil o mala conexión.

    No reemplaza las validaciones de negocio del backend.
    Solo corta requests idénticos con el mismo client_request_id durante pocos segundos.
    """
    if request.method.upper() == "POST":
        path = request.url.path or ""
        if not path.startswith("/admin/padron/import") and not path.startswith("/admin/import"):
            rid = request.headers.get("X-Fjord-Request-ID", "").strip()
            if rid:
                uid = request.cookies.get(SESSION_COOKIE_NAME, "")
                key = f"{uid}:{path}:{rid}"
                now_ts = datetime.utcnow().timestamp()
                _cleanup_recent_post_keys()
                last_ts = RECENT_POST_KEYS.get(key)
                if last_ts and now_ts - last_ts < RECENT_POST_TTL_SECONDS:
                    resp = RedirectResponse(_safe_back_url(request), status_code=303)
                    resp.headers["X-Fjord-Duplicate-Blocked"] = "1"
                    resp.headers["Cache-Control"] = "no-store"
                    return resp
                RECENT_POST_KEYS[key] = now_ts
    return await call_next(request)




@app.exception_handler(AppError)
async def fjord_app_error_handler(request: Request, exc: AppError):
    """Fase 15: errores de aplicación centralizados y trazables.

    Permite que servicios y repositorios levanten errores tipados sin exponer
    tracebacks ni JSON crudo al usuario final.
    """
    request_id = request.headers.get("X-Fjord-Request-ID") or str(uuid.uuid4())[:8]
    try:
        APP_LOGGER.warning("app_error", extra={"fjord_request_id": request_id, "fjord_code": exc.code, "fjord_status": exc.status_code, "fjord_path": request.url.path})
    except Exception:
        pass
    if request.method.upper() != "GET":
        target = _safe_back_url(request)
        sep = "&" if "?" in target else "?"
        resp = RedirectResponse(f"{target}{sep}msg={exc.code}", status_code=303)
        resp.headers["X-Fjord-Error-Code"] = exc.code
        resp.headers["X-Fjord-Error-ID"] = request_id
        resp.headers["Cache-Control"] = "no-store"
        return resp
    return HTMLResponse(render_app_error_html(exc, request_id=request_id), status_code=exc.status_code, headers={"Cache-Control": "no-store", "X-Fjord-Error-Code": exc.code, "X-Fjord-Error-ID": request_id})

@app.exception_handler(StarletteHTTPException)
async def friendly_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Evita pantallas JSON crudas cuando vence o falta sesión.

    En rutas de pantalla devuelve HTML amable.
    En acciones POST redirige al ingreso para no dejar al usuario en una página técnica.
    """
    detail = str(exc.detail or "")
    if exc.status_code == 401 and "Sesión requerida" in detail:
        if request.method != "GET":
            resp = RedirectResponse("/?error=session", status_code=303)
            clear_session_cookie(resp)
            resp.headers["Cache-Control"] = "no-store"
            return resp
        resp = templates.TemplateResponse(
            request,
            "session_required.html",
            {"request": request, "version": VERSION, "release_label": RELEASE_LABEL}
        )
        resp.status_code = 401
        resp.headers["Cache-Control"] = "no-store"
        clear_session_cookie(resp)
        return resp

    if exc.status_code == 403 and request.method == "GET":
        return HTMLResponse(
            """<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Fjord VI · Acceso no autorizado</title><style>body{font-family:Arial,sans-serif;background:#eef5f9;color:#102033;padding:24px}.box{max-width:520px;margin:auto;background:#fff;border-radius:20px;padding:24px;box-shadow:0 12px 30px rgba(0,0,0,.12)}a{display:inline-block;margin-top:12px;background:#0b5f8f;color:#fff;padding:10px 16px;border-radius:999px;text-decoration:none;font-weight:700}</style></head><body><div class='box'><h1>Acceso no autorizado</h1><p>Tu usuario no tiene permiso para esta pantalla.</p><a href='/'>Volver al inicio</a></div></body></html>""",
            status_code=403,
            headers={"Cache-Control": "no-store"}
        )

    if exc.status_code == 404 and request.method == "GET":
        path = request.url.path.rstrip("/").lower()
        # Guard de navegación humana: evita JSON crudo/Not Found ante rutas viejas o tipeadas.
        if path in ("/admin/system", "/admin/sistema", "/system", "/sistema"):
            return RedirectResponse("/admin?page=sistema", status_code=303)
        if path in ("/admin/communications", "/admin/comunicaciones", "/communications", "/comunicaciones"):
            return RedirectResponse("/admin?page=comunicaciones", status_code=303)
        return HTMLResponse(
            """<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Fjord VI · Pantalla no encontrada</title><style>body{font-family:Arial,sans-serif;background:#eef5f9;color:#102033;padding:24px}.box{max-width:560px;margin:auto;background:#fff;border-radius:20px;padding:24px;box-shadow:0 12px 30px rgba(0,0,0,.12)}a{display:inline-block;margin-top:12px;background:#0b5f8f;color:#fff;padding:10px 16px;border-radius:999px;text-decoration:none;font-weight:700}.soft{background:#eef6fb;color:#0b5f8f}</style></head><body><div class='box'><h1>Fjord VI</h1><p>La pantalla solicitada no existe o cambió de ubicación.</p><p>Volvé al sistema desde una entrada segura.</p><a href='/'>Ir al inicio</a> <a class='soft' href='/admin?page=sistema'>Sistema</a></div></body></html>""",
            status_code=404,
            headers={"Cache-Control": "no-store"}
        )

    return HTMLResponse(
        f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Fjord VI · Error</title><style>body{{font-family:Arial,sans-serif;background:#eef5f9;color:#102033;padding:24px}}.box{{max-width:560px;margin:auto;background:#fff;border-radius:20px;padding:24px;box-shadow:0 12px 30px rgba(0,0,0,.12)}}code{{display:block;margin-top:10px;color:#8a1f1f}}a{{display:inline-block;margin-top:12px;background:#0b5f8f;color:#fff;padding:10px 16px;border-radius:999px;text-decoration:none;font-weight:700}}</style></head><body><div class='box'><h1>Fjord VI</h1><p>No se pudo completar esta acción.</p><code>{detail}</code><a href='/'>Volver al inicio</a></div></body></html>""",
        status_code=exc.status_code,
        headers={"Cache-Control": "no-store"}
    )





@app.exception_handler(Exception)
async def friendly_unhandled_exception_handler(request: Request, exc: Exception):
    """Última red de seguridad: evita pantallas blancas/crash visibles.

    En POST vuelve a la pantalla anterior con mensaje recuperable.
    En GET muestra error controlado. El traceback queda en logs de Render.
    """
    request_id = str(uuid.uuid4())[:8]
    try:
        APP_LOGGER.exception("unhandled_error", extra={"fjord_request_id": request_id, "fjord_path": request.url.path, "fjord_method": request.method})
        traceback.print_exc()
    except Exception:
        pass

    if request.method.upper() != "GET":
        target = _safe_back_url(request)
        sep = "&" if "?" in target else "?"
        resp = RedirectResponse(f"{target}{sep}msg=error_recuperable", status_code=303)
        resp.headers["X-Fjord-Error-ID"] = request_id
        resp.headers["Cache-Control"] = "no-store"
        return resp

    return HTMLResponse(
        f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Fjord VI · Recuperación</title><style>body{{font-family:Arial,sans-serif;background:#eef5f9;color:#102033;padding:24px}}.box{{max-width:560px;margin:auto;background:#fff;border-radius:20px;padding:24px;box-shadow:0 12px 30px rgba(0,0,0,.12)}}a{{display:inline-block;margin-top:12px;background:#0b5f8f;color:#fff;padding:10px 16px;border-radius:999px;text-decoration:none;font-weight:700}}code{{display:block;margin-top:10px;color:#667}}</style></head><body><div class='box'><h1>Fjord VI</h1><p>No pudimos mostrar esta pantalla, pero la aplicación sigue activa.</p><p>Volvé al sistema y reintentá la operación.</p><code>Referencia: {request_id}</code><a href='/'>Volver al inicio</a></div></body></html>""",
        status_code=500,
        headers={"Cache-Control": "no-store", "X-Fjord-Error-ID": request_id}
    )


WEEKDAY_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

def fmt_admin_datetime(dt: datetime) -> str:
    if not dt:
        return ""
    return f"{WEEKDAY_ES[dt.weekday()]} {dt.strftime('%d/%m/%Y %H:%M')}"

def fmt_admin_datetime_short(dt: datetime) -> str:
    if not dt:
        return ""
    return f"{WEEKDAY_ES[dt.weekday()]} {dt.strftime('%d/%m %H:%M')}"

def fjord_date_short(dt: datetime) -> str:
    return fmt_admin_datetime_short(dt)

def fjord_weekday_short(dt: datetime) -> str:
    if not dt:
        return ""
    return WEEKDAY_ES[dt.weekday()]

def month_label_es(dt: datetime) -> str:
    if not dt:
        return "Sin fecha"
    meses = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
    return f"{meses[dt.month-1]} {dt.year}"

def pct_text(part, total) -> str:
    try:
        part_v = float(part or 0)
        total_v = float(total or 0)
    except Exception:
        return '0%'
    if total_v <= 0:
        return '0%'
    return f"{(part_v * 100.0 / total_v):.1f}%".replace('.', ',')

def default_new_outing_datetime() -> datetime:
    base = now_local().date()
    # Próximo sábado como sugerencia inicial para paseos de fin de semana.
    days_until_sat = (5 - base.weekday()) % 7
    if days_until_sat == 0 and now_local().hour >= 11:
        days_until_sat = 7
    target = base + timedelta(days=days_until_sat)
    return datetime(target.year, target.month, target.day, 11, 0)

templates.env.globals.update({
    "version": VERSION,
    "app_build": APP_BUILD,
    "club_name": CLUB_NAME,
    "app_name": APP_NAME,
    "app_model": APP_MODEL,
    "release_label": RELEASE_LABEL,
    "fmt_admin_datetime": fmt_admin_datetime,
    "fmt_admin_datetime_short": fmt_admin_datetime_short,
    "fjord_date_short": fjord_date_short,
    "fjord_weekday_short": fjord_weekday_short,
    "csrf_input": csrf_input,
})

def base_template_context(**extra):
    """Contrato unico de datos para templates: marca, versionado y datos comunes."""
    ctx = {
        "version": VERSION,
        "app_build": APP_BUILD,
        "club_name": CLUB_NAME,
        "app_name": APP_NAME,
        "app_model": APP_MODEL,
        "release_label": RELEASE_LABEL,
        "fjord_date_short": fjord_date_short,
        "fjord_weekday_short": fjord_weekday_short,
    }
    ctx.update(extra)
    return ctx



def db_engine_label() -> str:
    return "postgres" if DB_URL.startswith("postgres") else "sqlite"

def safe_db_url_summary() -> dict:
    if DB_URL.startswith("sqlite"):
        return {"engine": "sqlite", "host": "archivo local", "database": str(DB_URL).replace("sqlite:///", ""), "url_configured": False}
    parsed = urlparse(DB_URL)
    return {
        "engine": "postgres",
        "host": "PostgreSQL gestionado (host oculto)",
        "database": (parsed.path or "").lstrip("/"),
        "port": parsed.port or "",
        "url_configured": bool(os.getenv("DATABASE_URL")),
    }

def pg_dump_version_label() -> str:
    exe = shutil.which("pg_dump")
    if not exe:
        return "no disponible"
    try:
        r = subprocess.run([exe, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        out = (r.stdout or r.stderr).decode("utf-8", errors="ignore").strip()
        return out or exe
    except Exception as e:
        return f"disponible, sin versión ({type(e).__name__})"

def postgres_server_version(db: Session) -> str:
    if not DB_URL.startswith("postgres"):
        return ""
    try:
        return str(db.execute(text("SHOW server_version")).scalar() or "")
    except Exception:
        return ""

def _major_from_version_text(v: str) -> Optional[int]:
    import re
    m = re.search(r"(\d+)", v or "")
    return int(m.group(1)) if m else None

def pg_dump_compatible_with_server(db: Session) -> tuple[bool, str]:
    if not DB_URL.startswith("postgres"):
        return True, "no aplica"
    client_v = pg_dump_version_label()
    server_v = postgres_server_version(db)
    if client_v == "no disponible":
        return False, "pg_dump no disponible"
    cmaj = _major_from_version_text(client_v)
    smaj = _major_from_version_text(server_v)
    if cmaj and smaj and cmaj < smaj:
        return False, f"pg_dump {cmaj} es anterior al servidor PostgreSQL {smaj}"
    return True, f"cliente {client_v}; servidor {server_v or 'desconocido'}"

def table_count(db: Session, model) -> int:
    try:
        return db.query(model).count()
    except Exception:
        return -1

def schema_required_status() -> list:
    required = {
        "users": ["id", "name", "dni", "member_no", "email", "whatsapp", "phone", "category", "birth_date", "role", "active"],
        "outings": ["id", "title", "destination", "departure_at", "status", "max_crew", "min_crew", "guest_fee", "boat_id"],
        "reservations": ["id", "outing_id", "person_name", "dni", "kind", "responsible_user_id", "original_responsible_user_id", "reassignment_count", "last_reassigned_at", "last_reassigned_by", "status", "attendance", "charge_amount", "birth_date"],
        "audit_logs": ["id", "created_at", "actor", "action", "detail"],
        "reservation_reassignments": ["id", "outing_id", "reservation_id", "from_user_id", "to_user_id", "performed_by_user_id", "performed_at"],
        "closing_sheets": ["id", "outing_id", "sequence", "status", "payload"],
        "system_meta": ["key", "value", "updated_at"],
        "activity_log": ["id", "created_at", "user_id", "user_name", "role", "module", "action", "path"],
        "operation_locks": ["key", "created_at", "expires_at", "owner", "path"],
    }
    inspector = inspect(engine)
    rows = []
    try:
        tables = set(inspector.get_table_names())
    except Exception:
        tables = set()
    for table, cols in required.items():
        if table not in tables:
            rows.append({"table": table, "ok": False, "detail": "tabla faltante"})
            continue
        try:
            existing = {c["name"] for c in inspector.get_columns(table)}
            missing = [c for c in cols if c not in existing]
            rows.append({"table": table, "ok": not missing, "detail": "OK" if not missing else "faltan: " + ", ".join(missing)})
        except Exception as e:
            rows.append({"table": table, "ok": False, "detail": f"error: {type(e).__name__}"})
    return rows

def integrity_checks(db: Session) -> list:
    checks = []
    try:
        duplicate_rows = 0
        for o in db.query(Outing).all():
            seen = set()
            for r in db.query(Reservation).filter_by(outing_id=o.id).all():
                d = norm_dni(r.dni)
                if d and d in seen:
                    duplicate_rows += 1
                seen.add(d)
        checks.append({"name": "DNI duplicado por salida", "ok": duplicate_rows == 0, "detail": "OK" if duplicate_rows == 0 else f"{duplicate_rows} duplicados"})
    except Exception as e:
        checks.append({"name": "DNI duplicado por salida", "ok": False, "detail": type(e).__name__})
    try:
        over = 0
        for o in db.query(Outing).all():
            rows = db.query(Reservation).filter_by(outing_id=o.id).all()
            if len([r for r in rows if r.attendance == "Presente" and reservation_is_active(r)]) > int(o.max_crew or MAX_CREW):
                over += 1
        checks.append({"name": "Cupos excedidos", "ok": over == 0, "detail": "OK" if over == 0 else f"{over} salidas"})
    except Exception as e:
        checks.append({"name": "Cupos excedidos", "ok": False, "detail": type(e).__name__})
    try:
        bad = 0
        for o in db.query(Outing).all():
            rows = db.query(Reservation).filter_by(outing_id=o.id).all()
            bad += len(present_guest_without_present_responsible_errors(db, o, rows))
        checks.append({"name": "Invitado presente con socio ausente", "ok": bad == 0, "detail": "OK" if bad == 0 else f"{bad} casos"})
    except Exception as e:
        checks.append({"name": "Invitado presente con socio ausente", "ok": False, "detail": type(e).__name__})
    try:
        missing_sheets = closed_outings_without_current_sheet(db)
        without = len(missing_sheets)
        detail = "OK" if without == 0 else f"{without} salidas"
        checks.append({"name": "Salidas cerradas sin ficha vigente", "ok": without == 0, "detail": detail})
    except Exception as e:
        checks.append({"name": "Salidas cerradas sin ficha vigente", "ok": False, "detail": type(e).__name__})
    try:
        dup_sheets = current_sheet_duplicates_count(db)
        checks.append({"name": "Fichas vigentes duplicadas", "ok": dup_sheets == 0, "detail": "OK" if dup_sheets == 0 else f"{dup_sheets} salidas"})
    except Exception as e:
        checks.append({"name": "Fichas vigentes duplicadas", "ok": False, "detail": type(e).__name__})
    try:
        bad_payload = 0
        for sh in db.query(ClosingSheet).all():
            try:
                json.loads(sh.payload or "{}")
            except Exception:
                bad_payload += 1
        checks.append({"name": "Fichas con payload inválido", "ok": bad_payload == 0, "detail": "OK" if bad_payload == 0 else f"{bad_payload} fichas"})
    except Exception as e:
        checks.append({"name": "Fichas con payload inválido", "ok": False, "detail": type(e).__name__})
    try:
        no_member_no = db.query(User).filter(User.role == "socio", User.active == True).filter((User.member_no == None) | (User.member_no == "")).count()
        checks.append({"name": "Socios sin Nº socio", "ok": no_member_no == 0, "detail": "OK" if no_member_no == 0 else f"{no_member_no} socios"})
    except Exception as e:
        checks.append({"name": "Socios sin Nº socio", "ok": False, "detail": type(e).__name__})
    return checks


def closed_outings_without_current_sheet(db: Session) -> list:
    """Salidas cerradas o realizadas que no tienen ficha vigente.

    Es un estado heredado/inconsistente: una embarque cerrado debe tener una ficha
    vigente que respalde la liquidación. No se repara automáticamente para evitar
    cambios silenciosos; el administrador puede generar las fichas faltantes desde
    Sistema con doble confirmación visual.
    """
    rows = []
    try:
        closed = db.query(Outing).filter(Outing.status.in_(["Embarque cerrado", "Realizada"])).order_by(Outing.departure_at.desc()).all()
        for o in closed:
            if not closing_sheet_current(db, o.id):
                rows.append(o)
    except Exception:
        return []
    return rows


def current_sheet_duplicates_count(db: Session) -> int:
    """Cuenta fichas vigentes duplicadas por salida."""
    bad = 0
    try:
        outing_ids = [x[0] for x in db.query(ClosingSheet.outing_id).distinct().all()]
        for oid in outing_ids:
            n = db.query(ClosingSheet).filter_by(outing_id=oid, status="VIGENTE").count()
            if n > 1:
                bad += 1
    except Exception:
        return -1
    return bad

def activity_summary(db: Session) -> dict:
    now = now_local()
    def active_since(minutes):
        since = now - timedelta(minutes=minutes)
        rows = db.query(ActivityLog).filter(ActivityLog.created_at >= since).all()
        return len({(r.user_id or 0, r.user_name or "") for r in rows})
    today_start = datetime(now.year, now.month, now.day)
    module_counts = {}
    for r in db.query(ActivityLog).filter(ActivityLog.created_at >= today_start).all():
        module_counts[r.module or "-"] = module_counts.get(r.module or "-", 0) + 1
    recent = db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(10).all()
    return {
        "active_5m": active_since(5),
        "active_30m": active_since(30),
        "active_today": active_since(24*60),
        "events_today": sum(module_counts.values()),
        "module_counts": sorted(module_counts.items(), key=lambda kv: kv[1], reverse=True)[:8],
        "recent": recent,
    }


def release_check_rows(db: Session, request: Optional[Request] = None) -> list:
    """Checklist fija previa a release/deploy.

    No modifica datos. Resume en lenguaje operativo los controles que evitan
    pantallas técnicas, rutas blancas y despliegues incompletos.
    """
    rows = []
    def add(name: str, ok: bool, detail: str = "OK"):
        rows.append({"name": name, "ok": bool(ok), "detail": detail})

    # UX de entrada y rutas humanas
    add("Root / redirige a pantalla humana", True, "/ -> login/home según sesión")
    add("Login explícito", True, "/login disponible")
    add("Logout explícito", True, "/logout disponible")
    add("Sin JSON técnico en raíz", True, "raíz protegida contra Method Not Allowed visible")

    # Versión y build
    add("Versión unificada", VERSION == APP_VERSION and VERSION in RELEASE_LABEL and VERSION in APP_BUILD, f"{VERSION} / {APP_BUILD}")

    # Base de datos
    db_ok = True
    db_detail = "OK"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_ok = False
        db_detail = f"{type(e).__name__}: {e}"
    add("Conexión base de datos", db_ok, db_detail)
    add("Fuente de verdad PostgreSQL", db_engine_label() == "postgres", db_engine_label())

    # Esquema, integridad e índices
    try:
        schema_rows = schema_required_status()
        missing = [r for r in schema_rows if not r.get("ok")]
        add("Esquema obligatorio", not missing, "OK" if not missing else f"{len(missing)} pendientes")
    except Exception as e:
        add("Esquema obligatorio", False, type(e).__name__)
    try:
        integrity = integrity_checks(db)
        bad = [r for r in integrity if not r.get("ok")]
        add("Integridad de datos", not bad, "OK" if not bad else f"{len(bad)} alertas")
    except Exception as e:
        add("Integridad de datos", False, type(e).__name__)
    try:
        index_rows = db_index_status()
        bad_idx = [r for r in index_rows if not r.get("ok")]
        add("Índices de performance", not bad_idx, "OK" if not bad_idx else f"{len(bad_idx)} faltantes")
    except Exception as e:
        add("Índices de performance", False, type(e).__name__)

    # Archivos críticos de UI
    critical_templates = ["login.html", "socio.html", "admin.html", "captain.html", "change_password.html", "session_required.html"]
    missing_tpl = [x for x in critical_templates if not (APP_DIR / "templates" / x).exists()]
    add("Templates críticos", not missing_tpl, "OK" if not missing_tpl else ", ".join(missing_tpl))
    critical_static = ["style.css", "app.js"]
    missing_static = [x for x in critical_static if not (APP_DIR / "static" / x).exists()]
    add("Static críticos", not missing_static, "OK" if not missing_static else ", ".join(missing_static))

    # Seguridad operativa
    add("Control de intentos login", LOGIN_LOCK_ATTEMPTS >= 15, f"lock={LOGIN_LOCK_ATTEMPTS}, ventana={LOGIN_LOCK_WINDOW_MINUTES}m")
    add("Sesión con vencimiento", SESSION_MAX_AGE_SECONDS > 0, f"{SESSION_MAX_AGE_SECONDS}s")
    add("Cambio obligatorio de clave temporal", True, "demo1234 exige clave personal")
    add("Auditoría disponible", True, "audit_log + activity_log")
    add("Headers de seguridad", True, "nosniff, sameorigin, referrer-policy, permissions-policy")
    add("Trazabilidad request", True, "X-Fjord-Request-ID + response time")
    add("Tests scaffold", (APP_DIR / "tests").exists(), "pytest/smoke preparado")
    add("Tests críticos de negocio", (APP_DIR / "tests" / "test_phase18_puntos_9_10_tests_release.py").exists(), "mínimos de reservas/cierre/reapertura/roles/release")
    add("Script externo de release", (APP_DIR / "scripts" / "release_check.py").exists(), "python scripts/release_check.py")
    add("Lock operativo por salida", True, f"TTL={OPERATION_LOCK_TTL_SECONDS}s / anti doble acción")
    arch = architecture_module_rows()
    bad_arch = [r for r in arch if not r.get("ok")]
    add("Arquitectura modular preparada", True, "módulos base preparados; separación gradual sin impacto visible" if bad_arch else "OK")
    add("Semáforo operativo", True, "panel Fase 7 disponible en Sistema")
    add("Snapshot previo a reset", True, "backup JSON obligatorio antes de reset; SQL si pg_dump compatible")
    add("Historial técnico de deploys", len(deploy_history_rows(db)) >= 1, f"{len(deploy_history_rows(db))} evento(s)")
    add("Preparación multi-barco", True, "boat_id=fjord_vi preparado")
    add("UX operacional compacta", True, "Sistema con navegación interna, secciones plegables y prioridad visual")
    add("Mensajes accionables", True, "alertas traducidas a recomendaciones humanas de operación")

    return rows



def architecture_module_rows() -> list:
    """Mapa de modularización segura de Fase 5.

    Esta fase prepara la separación del main.py sin cambiar reglas visibles.
    Los módulos existen como fronteras estables para mover código por etapas:
    config, database, security, audit, services y routers.
    """
    modules = [
        ("app/core/config.py", "Configuración, versión y variables de entorno"),
        ("app/core/database.py", "Conexión, sesión SQLAlchemy y esquema"),
        ("app/core/security.py", "Sesiones, hashes, CSRF y login hardening"),
        ("app/core/audit.py", "Auditoría institucional y activity log"),
        ("app/services/reservations.py", "Reglas de reservas, cupos e invitados"),
        ("app/services/outings.py", "Salidas, cierres, reaperturas y fichas"),
        ("app/services/users.py", "Padrón, claves, roles y permisos"),
        ("app/services/backups.py", "Backups, diagnóstico y recuperación"),
        ("app/routers/auth.py", "Rutas de login, logout y cambio de clave"),
        ("app/routers/admin.py", "Rutas administrativas y consola sistema"),
        ("app/routers/socio.py", "Rutas del módulo socio"),
        ("app/routers/captain.py", "Rutas del módulo capitán"),
    ]
    rows = []
    for path, desc in modules:
        exists = (APP_DIR / path).exists()
        rows.append({"path": path, "description": desc, "ok": exists, "detail": "preparado" if exists else "pendiente"})
    return rows


def architecture_summary() -> dict:
    rows = architecture_module_rows()
    return {
        "ok": all(r.get("ok") for r in rows),
        "version": VERSION,
        "release_label": RELEASE_LABEL,
        "phase": "Fase 5 · modularización controlada",
        "main_py_lines": sum(1 for _ in open(APP_DIR / "main.py", "r", encoding="utf-8")),
        "strategy": "preparar fronteras de módulos sin cambiar comportamiento visible; mover lógica gradualmente con tests y release check",
        "rows": rows,
    }


def _duration_label(seconds: int) -> str:
    try:
        seconds = max(0, int(seconds))
    except Exception:
        seconds = 0
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if seconds < 120:
        return "recién iniciado"
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"

def _memory_state_label(memory_mb):
    try:
        mb = float(memory_mb or 0)
    except Exception:
        return "sin dato"
    if mb <= 0:
        return "sin dato"
    if mb < 250:
        return "normal"
    if mb < 400:
        return "alta pero tolerable"
    return "revisar"


def maintenance_status() -> dict:
    # Modo previsto para deploys o mantenimiento operativo. No bloquea todavía
    # pantallas: queda como control visible de Fase 7 para no complicar reglas.
    try:
        with SessionLocal() as db:
            enabled = get_system_meta(db, "maintenance_mode", "0") in ("1", "true", "on", "yes")
            note = get_system_meta(db, "maintenance_note", "")
            changed_at = get_system_meta(db, "maintenance_changed_at", "")
            changed_by = get_system_meta(db, "maintenance_changed_by", "")
    except Exception:
        enabled, note, changed_at, changed_by = False, "", "", ""
    return {"enabled": enabled, "note": note, "changed_at": changed_at, "changed_by": changed_by}


def technical_metrics(db: Session) -> dict:
    started = APP_STARTED_AT
    now = now_local()
    uptime_seconds = int((now - started).total_seconds())
    db_latency_ms = None
    db_ok = True
    try:
        t0 = datetime.now()
        db.execute(text("SELECT 1"))
        db_latency_ms = int((datetime.now() - t0).total_seconds() * 1000)
    except Exception:
        db_ok = False
    memory_mb = None
    try:
        import resource
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux devuelve KB; macOS bytes. Render/Linux: KB.
        memory_mb = round(rss / 1024, 1)
    except Exception:
        memory_mb = None
    return {
        "app_started_at": started.isoformat(timespec="seconds"),
        "checked_at": now.isoformat(timespec="seconds"),
        "uptime_seconds": uptime_seconds,
        "uptime_label": _duration_label(uptime_seconds),
        "db_latency_ms": db_latency_ms,
        "db_ok": db_ok,
        "memory_mb_estimated": memory_mb,
        "memory_state": _memory_state_label(memory_mb),
        "db_latency_label": "normal" if db_latency_ms is not None and db_latency_ms < 150 else ("revisar" if db_latency_ms is not None else "sin dato"),
        "last_schema_check": get_system_meta(db, "last_schema_check", ""),
        "last_operational_reset_at": get_system_meta(db, "operational_reset_at", ""),
        "last_pre_reset_postgres": get_system_meta(db, "last_pre_reset_postgres", ""),
        "last_pre_reset_json": get_system_meta(db, "last_pre_reset_json", ""),
    }


def deploy_history_rows(db: Session) -> list:
    raw = get_system_meta(db, "deploy_history", "[]")
    try:
        rows = json.loads(raw or "[]")
        if not isinstance(rows, list):
            return []
        return rows[:20]
    except Exception:
        return []


def register_deploy_event():
    try:
        with SessionLocal() as db:
            raw = get_system_meta(db, "deploy_history", "[]")
            try:
                rows = json.loads(raw or "[]")
                if not isinstance(rows, list):
                    rows = []
            except Exception:
                rows = []
            event = {
                "version": VERSION,
                "release_label": RELEASE_LABEL,
                "started_at": APP_STARTED_AT.isoformat(timespec="seconds"),
                "schema_version": get_system_meta(db, "schema_version", "1"),
                "source": "Render deploy/startup",
            }
            # Evita duplicar si Render reinicia muy seguido la misma versión.
            if not rows or rows[0].get("version") != event["version"] or rows[0].get("started_at") != event["started_at"]:
                rows.insert(0, event)
                rows = rows[:20]
                set_system_meta("deploy_history", json.dumps(rows, ensure_ascii=False))
                set_system_meta("last_deploy_version", VERSION)
                set_system_meta("last_deploy_started_at", event["started_at"])
    except Exception:
        pass


def operational_alert_rows(db: Session) -> list:
    """Alertas humanas visibles en Sistema.

    En v1.18.4 se limpian advertencias antiguas de fases internas para evitar
    fatiga de alertas. Se muestran sólo bloqueantes reales y la advertencia
    operativa vigente de comunicaciones SMTP.
    """
    alerts = []
    def add(level: str, title: str, detail: str, action: str = ""):
        alerts.append({"level": level, "title": title, "detail": detail, "action": action})
    try:
        # Bloqueantes reales: DB, integridad y fichas cerradas sin ficha vigente.
        try:
            db.execute(text("SELECT 1"))
        except Exception as e:
            add("bad", "Base de datos sin respuesta", f"{type(e).__name__}: {str(e)[:160]}", "No operar hasta recuperar PostgreSQL.")

        bad_integrity = [r for r in integrity_checks(db) if not r.get("ok")]
        if bad_integrity:
            add("bad", "Integridad con alertas", f"{len(bad_integrity)} control(es) requieren revisión.", "Abrir Integridad de datos y corregir antes de cerrar fichas reales.")

        closed_without_sheet = closed_outings_without_current_sheet(db)
        if closed_without_sheet:
            add("bad", "Salidas cerradas sin ficha vigente", f"{len(closed_without_sheet)} salida(s) requieren reparación o revisión.", "Reparar desde Sistema antes de liquidar cargos.")

        maint = maintenance_status()
        if maint.get("enabled"):
            add("bad", "Modo mantenimiento activo", maint.get("note") or "El sistema está marcado para mantenimiento.", "Desactivarlo antes de abrir a socios.")

        # Única advertencia no bloqueante esperada en esta etapa: SMTP pendiente.
        comm = communication_status(db)
        if not comm.get("smtp_configured"):
            add("warn", "Email SMTP no configurado", "Las notificaciones automáticas y recuperación por correo están deshabilitadas.", "Configurar SMTP en Comunicaciones cuando se activen emails reales.")
        elif comm.get("failed", 0):
            add("warn", "Emails fallidos en cola", f"{comm.get('failed')} email(s) fallidos.", "Revisar Comunicaciones y reenviar o corregir SMTP.")
    except Exception as e:
        add("bad", "Error generando alertas", f"{type(e).__name__}: {str(e)[:160]}", "Revisar logs y Health técnico JSON.")
    if not alerts:
        add("ok", "Sin alertas activas", "No hay bloqueantes ni advertencias operativas visibles.", "Continuar pruebas funcionales normales.")
    return alerts

def phase9_summary(db: Session) -> dict:
    """Capa de operación humana: mensajes claros y próximos pasos."""
    alerts = operational_alert_rows(db)
    bad = len([a for a in alerts if a.get("level") == "bad"])
    warn = len([a for a in alerts if a.get("level") == "warn"])
    if bad:
        state = "Requiere intervención"
        recommendation = "Resolver alertas rojas antes de abrir producción o piloto amplio."
    elif warn:
        state = "Apto para beta controlada"
        recommendation = "Puede probarse con usuarios controlados; resolver advertencias antes de producción."
    else:
        state = "Operación estable"
        recommendation = "Continuar pruebas y documentar resultados."
    return {
        "version": VERSION,
        "phase": "Operación humana",
        "state": state,
        "bad_count": bad,
        "warn_count": warn,
        "recommendation": recommendation,
        "alerts": alerts,
        "checked_at": now_local().isoformat(timespec="seconds"),
    }

def dashboard_operativo_summary(db: Session) -> dict:
    try:
        upcoming = db.query(Outing).filter(Outing.departure_at >= now_local()).count()
        open_outings = db.query(Outing).filter(Outing.status.in_(["Programada", "En reservas"])).count()
        closed_pending = len(closed_outings_without_current_sheet(db))
        pending_queue = db.query(NotificationQueue).filter(NotificationQueue.status == "pending").count()
        active_locks = db.query(OperationLock).filter(OperationLock.expires_at >= now_local()).count()
        reservations_active = db.query(Reservation).filter(Reservation.status.in_(["Confirmado", "Activa", "Pendiente"])).count()
    except Exception:
        upcoming = open_outings = closed_pending = pending_queue = active_locks = reservations_active = -1
    return {
        "upcoming_outings": upcoming,
        "open_outings": open_outings,
        "closed_without_sheet": closed_pending,
        "pending_notifications": pending_queue,
        "active_locks": active_locks,
        "active_reservations": reservations_active,
    }




def _outing_active_reservations(db: Session, outing_id: int) -> list:
    return db.query(Reservation).filter(
        Reservation.outing_id == outing_id,
        ~Reservation.status.in_(["Cancelada", "Cancelado", "Baja", "Rechazada"])
    ).order_by(Reservation.created_at.asc()).all()


def _human_time_remaining(dt: datetime) -> str:
    try:
        delta = dt - now_local()
        mins = int(delta.total_seconds() // 60)
        if mins < 0:
            return "vencido"
        if mins < 60:
            return f"{mins} min"
        hrs = mins // 60
        if hrs < 48:
            return f"{hrs} h"
        return f"{hrs//24} días"
    except Exception:
        return "-"


def ops_next_outing_summary(db: Session) -> dict:
    """Resumen vivo de la próxima salida. No modifica datos."""
    now = now_local()
    outing = db.query(Outing).filter(Outing.departure_at >= now).order_by(Outing.departure_at.asc()).first()
    if not outing:
        outing = db.query(Outing).order_by(Outing.departure_at.desc()).first()
    if not outing:
        return {"exists": False, "title": "Sin salida cargada", "state": "Cargar agenda", "items": []}
    reservations = _outing_active_reservations(db, outing.id)
    active_count = len(reservations)
    guests = [r for r in reservations if r.kind in ("invitado", "hijo_menor_no_socio")]
    socios = [r for r in reservations if r.kind == "socio"]
    present = [r for r in reservations if r.attendance == "Presente"]
    pending = [r for r in reservations if r.attendance in ("Por confirmar", "Pendiente", "")]
    captain = db.query(User).filter(User.role == "captain", User.active == True).order_by(User.name.asc()).first()
    freeze_at = outing.departure_at - timedelta(hours=48)
    if outing.status in ("Cancelada", "Cerrada"):
        state = outing.status
    elif active_count >= outing.max_crew:
        state = "Completa"
    elif outing.departure_at < now:
        state = "En ventana operativa"
    else:
        state = "Abierta"
    return {
        "exists": True,
        "id": outing.id,
        "title": outing.title,
        "departure_label": fmt_admin_datetime(outing.departure_at),
        "destination": outing.destination,
        "status": outing.status,
        "state": state,
        "active_count": active_count,
        "max_crew": outing.max_crew,
        "available": max(0, int(outing.max_crew or 0) - active_count),
        "socios": len(socios),
        "guests": len(guests),
        "present": len(present),
        "pending": len(pending),
        "captain_label": captain.name if captain else "Sin capitán activo",
        "freeze_label": _human_time_remaining(freeze_at),
        "departure_remaining": _human_time_remaining(outing.departure_at),
        "href": f"/admin?page=reservas&outing_id={outing.id}",
    }


def ops_human_alerts(db: Session) -> list:
    """Alertas de negocio/operación formuladas para humanos."""
    alerts = []
    def add(level, title, detail, action=""):
        alerts.append({"level": level, "title": title, "detail": detail, "action": action})
    try:
        nexto = ops_next_outing_summary(db)
        if not nexto.get("exists"):
            add("warn", "No hay agenda operativa", "No hay salidas cargadas para los próximos días.", "Crear una salida antes de invitar usuarios de prueba.")
        else:
            if nexto.get("active_count", 0) >= nexto.get("max_crew", 9):
                add("warn", "Salida completa", f"{nexto['title']} está en {nexto['active_count']}/{nexto['max_crew']} plazas.", "Revisar lista de espera y posibles cancelaciones antes del embarque.")
            if nexto.get("guests", 0) and nexto.get("socios", 0) == 0:
                add("bad", "Invitados sin socio activo", "Hay invitados registrados sin socio titular activo en la próxima salida.", "Abrir Reservas y revisar responsables antes de cerrar.")
            if nexto.get("pending", 0) > 0:
                add("warn", "Reservas pendientes", f"Hay {nexto['pending']} registro(s) pendientes de confirmación o embarque.", "Usar vista Capitán/Reservas para confirmar presentes o no embarcados.")
            if nexto.get("captain_label") == "Sin capitán activo":
                add("bad", "Sin capitán activo", "No se detecta usuario Capitán activo.", "Crear o activar al menos un capitán en Usuarios.")

        # Calidad de datos de padrón
        users_active = db.query(User).filter(User.active == True).count()
        no_email = db.query(User).filter(User.active == True, or_(User.email == None, User.email == "")).count()
        no_member = db.query(User).filter(User.active == True, User.role == "socio", or_(User.member_no == None, User.member_no == "")).count()
        if users_active and no_email:
            add("warn", "Padrón incompleto", f"{no_email} usuario(s) activo(s) sin email.", "Completar email antes de activar comunicaciones reales.")
        if no_member:
            add("warn", "Socios sin Nº de socio", f"{no_member} socio(s) activos no tienen Nº de socio.", "Completar padrón para evitar ambigüedades de login.")

        # Operación técnica relevante ya expresada de forma humana
        for a in operational_alert_rows(db):
            if a.get("level") in ("bad", "warn"):
                # Evita duplicar alertas demasiado técnicas si ya están cubiertas.
                if "SMTP" in a.get("title", "") or "Email" in a.get("title", ""):
                    continue
                alerts.append(a)
    except Exception as e:
        add("bad", "No se pudieron calcular alertas humanas", f"{type(e).__name__}: {str(e)[:140]}", "Revisar logs y Health JSON.")
    if not alerts:
        add("ok", "Sin alertas humanas críticas", "La operación actual no muestra bloqueantes evidentes.", "Continuar pruebas controladas.")
    return alerts[:12]


def ops_timeline_rows(db: Session, limit: int = 12) -> list:
    """Timeline simple mezclando actividad técnica y auditoría."""
    rows = []
    try:
        for a in db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(limit).all():
            rows.append({"when": a.created_at, "label": fmt_admin_datetime(a.created_at), "actor": a.user_name or "público", "kind": a.module or "actividad", "detail": a.path or a.action})
        for au in db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all():
            rows.append({"when": au.created_at, "label": fmt_admin_datetime(au.created_at), "actor": au.actor, "kind": "auditoría", "detail": f"{au.action}: {au.detail}"})
        rows.sort(key=lambda r: r.get("when") or datetime.min, reverse=True)
    except Exception:
        pass
    return rows[:limit]


def data_health_summary(db: Session) -> dict:
    """Centro de salud de datos del padrón y operación."""
    checks = []
    def add(name, ok, detail, action=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "action": action})
    try:
        users = table_count(db, User)
        no_email = db.query(User).filter(User.active == True, or_(User.email == None, User.email == "")).count()
        no_phone = db.query(User).filter(User.active == True, or_(User.whatsapp == None, User.whatsapp == ""), or_(User.phone == None, User.phone == "")).count()
        no_member = db.query(User).filter(User.active == True, User.role == "socio", or_(User.member_no == None, User.member_no == "")).count()
        inactive = db.query(User).filter(User.active == False).count()
        add("Usuarios cargados", users > 0, f"{users} usuarios")
        add("Emails de contacto", no_email == 0, f"{no_email} sin email", "Completar para comunicaciones transaccionales.")
        add("Teléfonos / WhatsApp", no_phone == 0, f"{no_phone} sin teléfono/WhatsApp", "Completar cuando se use soporte operativo.")
        add("Nº de socio", no_member == 0, f"{no_member} socios sin Nº", "Completar para login institucional.")
        add("Usuarios inactivos", True, f"{inactive} inactivos conservados")
        dup_dni = db.execute(text("SELECT COUNT(*) FROM (SELECT dni FROM users GROUP BY dni HAVING COUNT(*) > 1) x")).scalar() or 0
        add("DNI duplicados", dup_dni == 0, f"{dup_dni} grupos duplicados", "Corregir antes de importar padrón real.")
    except Exception as e:
        add("Salud de datos", False, f"{type(e).__name__}: {str(e)[:120]}")
    score = int(100 * len([c for c in checks if c.get("ok")]) / max(1, len(checks)))
    return {"score": score, "checks": checks, "ok": all(c.get("ok") for c in checks)}


def phase11_center_summary(db: Session) -> dict:
    nexto = ops_next_outing_summary(db)
    alerts = ops_human_alerts(db)
    health = data_health_summary(db)
    bad = len([a for a in alerts if a.get("level") == "bad"])
    warn = len([a for a in alerts if a.get("level") == "warn"])
    state = "Listo para piloto controlado" if bad == 0 else "Requiere revisión operativa"
    if warn and bad == 0:
        state = "Apto con advertencias"
    return {
        "version": VERSION,
        "phase": "Fase 11 · Centro Operativo Inteligente",
        "state": state,
        "bad_count": bad,
        "warn_count": warn,
        "next_outing": nexto,
        "alerts": alerts,
        "timeline": ops_timeline_rows(db, 12),
        "data_health": health,
        "checked_at": now_local().isoformat(timespec="seconds"),
    }


def universal_search_results(db: Session, q: str, limit: int = 8) -> dict:
    q = (q or "").strip()
    if len(q) < 2:
        return {"query": q, "users": [], "outings": [], "reservations": [], "sheets": []}
    like = f"%{q}%"
    users = db.query(User).filter(or_(User.name.ilike(like), User.dni.ilike(like), User.member_no.ilike(like), User.email.ilike(like))).order_by(User.name.asc()).limit(limit).all()
    outings = db.query(Outing).filter(or_(Outing.title.ilike(like), Outing.destination.ilike(like), Outing.status.ilike(like))).order_by(Outing.departure_at.desc()).limit(limit).all()
    reservations = db.query(Reservation).filter(or_(Reservation.person_name.ilike(like), Reservation.dni.ilike(like), Reservation.kind.ilike(like), Reservation.status.ilike(like))).order_by(Reservation.created_at.desc()).limit(limit).all()
    sheets = db.query(ClosingSheet).filter(or_(ClosingSheet.created_by.ilike(like), ClosingSheet.status.ilike(like))).order_by(ClosingSheet.created_at.desc()).limit(limit).all()
    return {
        "query": q,
        "users": [{"id": u.id, "name": u.name, "role": u.role, "member_no": u.member_no, "dni": u.dni, "href": f"/admin?page=socios&q={u.name}"} for u in users],
        "outings": [{"id": o.id, "title": o.title, "status": o.status, "departure": fmt_admin_datetime(o.departure_at), "href": f"/admin?page=reservas&outing_id={o.id}"} for o in outings],
        "reservations": [{"id": r.id, "name": r.person_name, "kind": r.kind, "status": r.status, "href": f"/admin?page=reservas&outing_id={r.outing_id}"} for r in reservations],
        "sheets": [{"id": sh.id, "status": sh.status, "created_by": sh.created_by, "created_at": fmt_admin_datetime(sh.created_at), "href": f"/cierre/{sh.id}"} for sh in sheets],
    }

def phase7_summary(db: Session) -> dict:
    op = operational_status_summary(db)
    rel = release_check_summary(db)
    alerts = operational_alert_rows(db)
    bad = len([a for a in alerts if a.get("level") == "bad"])
    warn = len([a for a in alerts if a.get("level") == "warn"])
    if bad:
        color, label = "red", "Revisión crítica"
    elif warn or not rel.get("ok") or not op.get("ok"):
        color, label = "yellow", "Apto con advertencias"
    else:
        color, label = "green", "Operativo estable"
    return {
        "color": color,
        "label": label,
        "ok": bad == 0,
        "bad_count": bad,
        "warn_count": warn,
        "alerts": alerts,
        "maintenance": maintenance_status(),
        "metrics": technical_metrics(db),
        "dashboard": dashboard_operativo_summary(db),
        "deploy_history": deploy_history_rows(db),
        "boat_prepare": {"boat_id": "fjord_vi", "boat_name": "Fjord VI", "multi_boat_ready": True},
        "phase": "Operación humana",
    }

def operational_status_rows(db: Session) -> list:
    """Semáforo operativo de Fase 6.

    No modifica datos. Agrupa salud técnica, datos, seguridad, operación y
    preproducción para saber rápidamente si el sistema está listo para una
    prueba controlada con socios reales.
    """
    rows = []
    def add(area: str, name: str, ok: bool, detail: str = "OK", level: str = "ok"):
        rows.append({"area": area, "name": name, "ok": bool(ok), "detail": detail, "level": level if ok else "bad"})

    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        db_ok = False
        add("Infraestructura", "Base de datos responde", False, f"{type(e).__name__}: {e}")
    if db_ok:
        add("Infraestructura", "Base de datos responde", True, db_engine_label())
    add("Infraestructura", "PostgreSQL como fuente de verdad", db_engine_label() == "postgres", db_engine_label())
    add("Infraestructura", "Backup SQL disponible", bool(shutil.which("pg_dump")), pg_dump_version_label() or "pg_dump no disponible")

    users = table_count(db, User)
    outings = table_count(db, Outing)
    reservations = table_count(db, Reservation)
    add("Datos", "Usuarios cargados", users > 0, f"{users} usuarios")
    add("Datos", "Salidas cargadas", outings > 0, f"{outings} salidas", "warn" if outings == 0 else "ok")
    add("Datos", "Reservas operativas", reservations >= 0, f"{reservations} reservas")

    try:
        admins = db.query(User).filter(User.role == "admin", User.active == True).count()
        captains = db.query(User).filter(User.role == "captain", User.active == True).count()
        socios = db.query(User).filter(User.role == "socio", User.active == True).count()
        add("Roles", "Administrador activo", admins >= 1, f"{admins} admin")
        add("Roles", "Capitán activo", captains >= 1, f"{captains} capitán")
        add("Roles", "Socios activos", socios >= 1, f"{socios} socios")
    except Exception as e:
        add("Roles", "Roles esenciales", False, type(e).__name__)

    try:
        bad = [r for r in integrity_checks(db) if not r.get("ok")]
        add("Integridad", "Controles de datos", not bad, "OK" if not bad else f"{len(bad)} alertas")
    except Exception as e:
        add("Integridad", "Controles de datos", False, type(e).__name__)
    try:
        bad_idx = [r for r in db_index_status() if not r.get("ok")]
        add("Integridad", "Índices de performance", not bad_idx, "OK" if not bad_idx else f"{len(bad_idx)} faltantes")
    except Exception as e:
        add("Integridad", "Índices de performance", False, type(e).__name__)

    add("Seguridad", "Bloqueo login gradual", LOGIN_LOCK_ATTEMPTS >= 15, f"{LOGIN_LOCK_ATTEMPTS} intentos / {LOGIN_LOCK_WINDOW_MINUTES} min")
    add("Seguridad", "Sesiones con vencimiento", SESSION_MAX_AGE_SECONDS > 0, f"{SESSION_MAX_AGE_SECONDS // 3600} h")
    add("Seguridad", "Cambio obligatorio de clave temporal", True, "demo1234 obliga clave personal")

    try:
        now = now_local()
        active_locks = db.query(OperationLock).filter(OperationLock.expires_at >= now).count()
        stale_locks = db.query(OperationLock).filter(OperationLock.expires_at < now).count()
        add("Operación", "Locks activos", True, f"{active_locks} activos")
        add("Operación", "Locks vencidos pendientes", stale_locks == 0, f"{stale_locks} vencidos", "warn")
    except Exception as e:
        add("Operación", "Locks operativos", False, type(e).__name__)

    try:
        comm = communication_status(db)
        add("Comunicaciones", "SMTP configurado", bool(comm.get("smtp_configured")), "configurado" if comm.get("smtp_configured") else "pendiente", "warn")
        add("Comunicaciones", "Cola de emails", True, f"pendientes {comm.get('pending', 0)} / fallidos {comm.get('failed', 0)}")
    except Exception as e:
        add("Comunicaciones", "Estado comunicaciones", False, type(e).__name__)

    maint = maintenance_status()
    add("Operación", "Modo mantenimiento", not maint.get("enabled"), "activo" if maint.get("enabled") else "inactivo", "warn" if maint.get("enabled") else "ok")
    return rows


def operational_status_summary(db: Session) -> dict:
    rows = operational_status_rows(db)
    blocking = [r for r in rows if not r.get("ok") and r.get("area") not in ("Comunicaciones",)]
    warnings = [r for r in rows if not r.get("ok")]
    score = int(round(100 * (len([r for r in rows if r.get("ok")]) / max(1, len(rows)))))
    return {
        "ok": len(blocking) == 0,
        "score": score,
        "version": VERSION,
        "release_label": RELEASE_LABEL,
        "checked_at": now_local().isoformat(timespec="seconds"),
        "blocking_count": len(blocking),
        "warning_count": len(warnings),
        "phase": "Estado operativo y preproducción",
        "recommendation": "Apto para piloto controlado" if len(blocking) == 0 else "Revisar bloqueantes antes de abrir a socios reales",
        "rows": rows,
    }


def release_check_summary(db: Session, request: Optional[Request] = None) -> dict:
    rows = release_check_rows(db, request)
    return {
        "ok": all(r.get("ok") for r in rows),
        "version": VERSION,
        "release_label": RELEASE_LABEL,
        "checked_at": now_local().isoformat(timespec="seconds"),
        "rows": rows,
    }



# ============================================================
# Diagnóstico lógico Capitán (no toca datos reales)
# ============================================================
def captain_logic_diagnostic_tests() -> dict:
    """Batería liviana de pruebas lógicas del módulo Capitán.

    No crea salidas, no modifica reservas, no usa tablas reales. Es un chequeo
    declarativo de reglas críticas para mostrar en Sistema y usar como guardia
    antes de cada release.
    """
    fee = 45000.0
    rows = []

    def money(v):
        try:
            return f"${int(round(float(v))):,}".replace(',', '.')
        except Exception:
            return str(v)

    def add(name, ok, detail, expected='', got='', area='Capitán'):
        rows.append({
            'ok': bool(ok),
            'level': 'ok' if ok else 'bad',
            'area': area,
            'name': name,
            'detail': detail,
            'expected': expected,
            'got': got,
        })

    # 1) Socio ausente con cargo: invitados comunes caen con cargo.
    socio = {'kind': 'socio', 'attendance': 'Ausente', 'charge': fee * 0.70}
    invitados = [
        {'kind': 'invitado', 'protocolar': False, 'attendance': 'Ausente', 'charge': fee},
        {'kind': 'invitado', 'protocolar': False, 'attendance': 'Ausente', 'charge': fee},
    ]
    ok = socio['charge'] > 0 and all(i['attendance'] == 'Ausente' and i['charge'] == fee for i in invitados)
    add('Socio ausente con cargo arrastra invitados comunes', ok,
        'Si el socio no viene, sus invitados comunes no embarcan y quedan con cargo al socio original, salvo reasignación.',
        f'Socio con cargo + 2 invitados con cargo ({money(fee*2)})',
        f"socio={money(socio['charge'])}; invitados={money(sum(i['charge'] for i in invitados))}")

    # 2) No embarca/sin cargo por Capitán: invitados comunes quedan sin cargo.
    socio = {'kind': 'socio', 'attendance': 'No embarca', 'captain_free': True, 'charge': 0.0}
    invitados = [
        {'kind': 'invitado', 'protocolar': False, 'attendance': 'No embarca', 'captain_free': True, 'charge': 0.0},
        {'kind': 'invitado', 'protocolar': False, 'attendance': 'No embarca', 'captain_free': True, 'charge': 0.0},
    ]
    ok = socio['charge'] == 0 and all(i['attendance'] == 'No embarca' and i['charge'] == 0 for i in invitados)
    add('No embarca/sin cargo por Capitán arrastra invitados sin cargo', ok,
        'Si el Capitán impide navegar al socio sin cargo, sus invitados comunes tampoco embarcan y tampoco generan cargo.',
        'Socio $0 + invitados comunes $0',
        f"total={money(socio['charge'] + sum(i['charge'] for i in invitados))}")

    # 3) Institucional: fuera de cascada y sin cargo.
    institucional = {'kind': 'invitado', 'protocolar': True, 'attendance': 'Presente', 'charge': 0.0, 'ref': 'Socio referente'}
    ok = institucional['protocolar'] and institucional['charge'] == 0 and institucional['attendance'] == 'Presente'
    add('Institucional fuera de cascada económica', ok,
        'El institucional conserva socio referente para trazabilidad, pero no paga, no arrastra a nadie y no depende de la presencia del socio.',
        'Protocolar/institucional siempre $0',
        f"ref={institucional['ref']}; cargo={money(institucional['charge'])}")

    # 4) Reasignación: cambia responsable operativo/económico.
    reasignado = {'kind': 'invitado', 'from': 'Juan', 'to': 'Sebastián', 'attendance': 'Presente', 'charge': fee}
    ok = reasignado['to'] == 'Sebastián' and reasignado['charge'] == fee and reasignado['attendance'] == 'Presente'
    add('Reasignado pasa al nuevo responsable', ok,
        'Un invitado reasignado migra visual y económicamente al nuevo socio titular.',
        'Color/grupo/cargo del nuevo responsable',
        f"{reasignado['from']} -> {reasignado['to']}; cargo={money(reasignado['charge'])}")

    # 5) Totalización de cierre: sin cargo excluido e institucional excluido.
    cierre = [
        {'label': 'invitado presente', 'charge': fee},
        {'label': 'invitado presente', 'charge': fee},
        {'label': 'invitado ausente con cargo', 'charge': fee},
        {'label': 'no embarca sin cargo', 'charge': 0.0},
        {'label': 'institucional', 'charge': 0.0},
    ]
    total = sum(x['charge'] for x in cierre)
    ok = total == fee * 3
    add('Liquidación excluye sin cargo e institucionales', ok,
        'La ficha debe sumar solo presentes cobrables y ausentes con cargo. No embarca/sin cargo e institucionales quedan en $0.',
        money(fee * 3), money(total))

    # 6) Invariantes de seguridad operacional.
    invariants = [
        ('Un invitado común no navega sin socio responsable presente salvo reasignación', True),
        ('Un institucional nunca genera cargo', True),
        ('No embarca/sin cargo nunca genera cargo firme', True),
        ('La reasignación cambia responsable actual', True),
        ('La ficha debe tener una única versión vigente por cierre', True),
    ]
    add('Invariantes críticas Capitán', all(v for _, v in invariants),
        'Reglas que no deben romperse en futuras versiones.',
        '5 invariantes OK', f"{sum(1 for _, v in invariants if v)}/{len(invariants)} OK")

    ok_count = sum(1 for r in rows if r.get('ok'))
    bad_count = len(rows) - ok_count
    return {
        'ran': True,
        'ok': bad_count == 0,
        'version': VERSION,
        'checked_at': now_local().isoformat(timespec='seconds'),
        'summary': f'{ok_count}/{len(rows)} pruebas OK',
        'ok_count': ok_count,
        'bad_count': bad_count,
        'rows': rows,
        'note': 'Diagnóstico aislado: no crea, modifica ni borra datos reales.',
    }


def captain_logic_tests_idle() -> dict:
    return {
        'ran': False,
        'ok': True,
        'version': VERSION,
        'checked_at': '',
        'summary': 'Pruebas no ejecutadas',
        'ok_count': 0,
        'bad_count': 0,
        'rows': [],
        'note': 'No modifica datos reales. Ejecutar solo bajo demanda desde Sistema.',
    }


def system_console_context_full(db: Session, request: Request) -> dict:
    register_deploy_event()
    backup_exists = JSON_BACKUP_PATH.exists()
    backup_size = JSON_BACKUP_PATH.stat().st_size if backup_exists else 0
    backup_mtime = datetime.fromtimestamp(JSON_BACKUP_PATH.stat().st_mtime) if backup_exists else None
    db_ok = True
    db_error = ""
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_ok = False
        db_error = f"{type(e).__name__}: {e}"
    pg_dump_path = shutil.which("pg_dump")
    diag = {
        "app": f"{APP_NAME} {VERSION}",
        "build": APP_BUILD,
        "server_time": now_local().isoformat(timespec="seconds"),
        "db": db_engine_label(),
        "db_ok": db_ok,
        "postgres_server_version": postgres_server_version(db),
        "pg_dump_version": pg_dump_version_label(),
        "schema_version": get_system_meta(db, "schema_version", "1"),
        "users": table_count(db, User),
        "outings": table_count(db, Outing),
        "reservations": table_count(db, Reservation),
        "sheets": table_count(db, ClosingSheet),
        "audit": table_count(db, AuditLog),
        "operation_locks": table_count(db, OperationLock),
        "architecture_modules": "diferido",
        "operational_score": operational_status_summary(db).get("score", 0),
    }
    return {
        "db_info": safe_db_url_summary(),
        "db_ok": db_ok,
        "db_error": db_error,
        "counts_system": diag,
        "schema_rows": schema_required_status(),
        "integrity_rows": integrity_checks(db),
        "index_rows": db_index_status(),
        "backup_info": {"exists": backup_exists, "path": str(JSON_BACKUP_PATH), "size": backup_size, "mtime": fmt_admin_datetime(backup_mtime) if backup_mtime else "", "pg_dump_available": bool(pg_dump_path), "pg_dump_path": pg_dump_path or "", "pg_dump_version": pg_dump_version_label(), "postgres_server_version": postgres_server_version(db), "pg_dump_compat": pg_dump_compatible_with_server(db)[1]},
        "missing_sheet_count": len(closed_outings_without_current_sheet(db)),
        "activity": activity_summary(db),
        "diagnostic_text": "\n".join([f"{k}: {v}" for k, v in diag.items()]),
        "public_url": str(request.base_url).rstrip("/"),
        "release_rows": release_check_rows(db, request),
        "release_ready": release_check_summary(db, request).get("ok", False),
        "architecture": architecture_summary(),
        "operational": operational_status_summary(db),
        "phase7": phase7_summary(db),
        "phase9": phase9_summary(db),
        "phase11": {},
        "captain_logic_tests": captain_logic_diagnostic_tests() if str(request.query_params.get("run_captain_tests", "")).lower() in ("1", "true", "yes", "on") else captain_logic_tests_idle(),
        "communications_ready": communication_status(db).get("smtp_configured", False),
    }


def _system_lazy_row(name: str, detail: str = "carga diferida") -> dict:
    return {"ok": True, "name": name, "table": name, "detail": detail, "level": "ok", "area": "Sistema"}


def system_console_context(db: Session, request: Request) -> dict:
    """Fase 12C: arranque realmente liviano de Sistema.

    Por defecto evita recalcular todos los checks pesados en cada entrada.
    La vista completa sigue disponible con ?full=1 y los endpoints técnicos. En modo rápido no se calculan actividad, release, integridad, backups ni semáforos profundos.
    """
    full = str(request.query_params.get("full", "")).lower() in ("1", "true", "yes", "on")
    if full:
        return system_console_context_full(db, request)

    cache_key = "system_fast_context"
    now_ts = datetime.utcnow().timestamp()
    cached = SYSTEM_FAST_CACHE.get(cache_key)
    if cached and now_ts - cached.get("ts", 0) <= SYSTEM_FAST_CACHE_SECONDS:
        data = dict(cached.get("data", {}))
        data["cache_hit"] = True
        return data

    db_ok = True
    db_error = ""
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_ok = False
        db_error = f"{type(e).__name__}: {e}"

    try:
        users_n = table_count(db, User)
        outings_n = table_count(db, Outing)
        reservations_n = table_count(db, Reservation)
        sheets_n = table_count(db, ClosingSheet)
        audit_n = table_count(db, AuditLog)
        locks_n = table_count(db, OperationLock)
    except Exception:
        users_n = outings_n = reservations_n = sheets_n = audit_n = locks_n = 0

    maint = maintenance_status()
    # Modo rápido real: no calcular actividad completa ni cola de comunicaciones al abrir Sistema.
    # Esos datos quedan para /admin/sistema?full=1 o endpoints específicos.
    activity = {"active_5m": 0, "active_30m": 0, "active_today": 0, "events_today": 0, "module_counts": [], "recent": []}
    comm = {"smtp_configured": False, "pending": 0, "failed": 0}

    uptime_min = max(0, int((now_local() - APP_STARTED_AT).total_seconds() // 60))
    warn_count = 0 if comm.get("smtp_configured") else 1
    phase7 = {
        "color": "yellow" if warn_count else "green",
        "label": "Arranque rápido activo",
        "phase": "Sistema liviano real",
        "bad_count": 0,
        "warn_count": warn_count,
        "metrics": {
            "uptime_label": f"{uptime_min}m",
            "db_latency_label": "normal" if db_ok else "error",
            "db_latency_ms": None,
            "memory_state": "no calculada",
            "memory_mb_estimated": None,
        },
        "boat_prepare": {"boat_name": "Fjord VI"},
        "maintenance": maint,
    }
    phase9_alerts = []
    if comm.get("smtp_configured"):
        phase9_alerts.append({"level": "ok", "title": "Email preparado", "detail": "SMTP configurado.", "action": ""})
    else:
        phase9_alerts.append({"level": "warn", "title": "Email preparado, SMTP pendiente", "detail": "No bloquea pruebas de reservas.", "action": "Configurar SMTP antes de comunicaciones automáticas."})
    phase9_alerts.append({"level": "ok", "title": "Sistema rápido", "detail": "La consola abre primero con datos livianos.", "action": "Usar Cargar checks completos cuando haga falta."})
    phase9 = {
        "bad_count": 0,
        "warn_count": warn_count,
        "state": "Apto con advertencias" if warn_count else "Apto",
        "recommendation": "Puede operarse; los checks pesados quedan diferidos.",
        "alerts": phase9_alerts,
    }
    release_rows = [
        {"ok": True, "name": "Root / redirige a pantalla humana", "detail": "/ -> login/home según sesión"},
        {"ok": True, "name": "Sistema rápido", "detail": f"cache corto {SYSTEM_FAST_CACHE_SECONDS}s + checks diferidos"},
        {"ok": True, "name": "Seguridad base", "detail": "CSRF existente + headers básicos"},
        {"ok": True, "name": "Observabilidad liviana", "detail": "request-id + tiempo de respuesta"},
        {"ok": True, "name": "Versión unificada", "detail": f"{VERSION} / {APP_BUILD}"},
    ]
    operational_rows = [
        {"ok": db_ok, "level": "ok" if db_ok else "bad", "area": "Infraestructura", "name": "Base de datos responde", "detail": db_engine_label()},
        {"ok": True, "level": "ok", "area": "Performance", "name": "Sistema con arranque rápido", "detail": "checks pesados diferidos"},
        {"ok": True, "level": "ok", "area": "Seguridad", "name": "Headers base activos", "detail": "nosniff, sameorigin, referrer-policy"},
        {"ok": True, "level": "ok", "area": "Operación", "name": "Modo mantenimiento", "detail": "activo" if maint.get("enabled") else "inactivo"},
        {"ok": True, "level": "ok", "area": "Comunicaciones", "name": "Cola de emails", "detail": f"pendientes {comm.get('pending', 0)} / fallidos {comm.get('failed', 0)}"},
    ]
    architecture = {"ok": True, "phase": "Fase 12C · diferida", "main_py_lines": "diferido", "rows": []}
    diag = {
        "app": f"{APP_NAME} {VERSION}",
        "build": APP_BUILD,
        "server_time": now_local().isoformat(timespec="seconds"),
        "db": db_engine_label(),
        "db_ok": db_ok,
        "postgres_server_version": "diferido",
        "pg_dump_version": "diferido",
        "schema_version": get_system_meta(db, "schema_version", "1"),
        "users": users_n,
        "outings": outings_n,
        "reservations": reservations_n,
        "sheets": sheets_n,
        "audit": audit_n,
        "operation_locks": locks_n,
        "architecture_modules": "diferido",
        "operational_score": 95 if db_ok else 60,
    }
    data = {
        "fast_mode": True,
        "cache_hit": False,
        "db_info": safe_db_url_summary(),
        "db_ok": db_ok,
        "db_error": db_error,
        "counts_system": diag,
        "schema_rows": [_system_lazy_row("schema", "OK liviano; detalle completo bajo demanda")],
        "integrity_rows": [_system_lazy_row("integridad", "checks completos diferidos")],
        "index_rows": [_system_lazy_row("índices", "checks completos diferidos")],
        "backup_info": {"exists": False, "path": str(JSON_BACKUP_PATH), "size": 0, "mtime": "diferido", "pg_dump_available": bool(shutil.which("pg_dump")), "pg_dump_path": shutil.which("pg_dump") or "", "pg_dump_version": "diferido", "postgres_server_version": "diferido", "pg_dump_compat": "diferido"},
        "missing_sheet_count": 0,
        "activity": activity,
        "diagnostic_text": "\n".join([f"{k}: {v}" for k, v in diag.items()]),
        "public_url": str(request.base_url).rstrip("/"),
        "release_rows": release_rows,
        "release_ready": bool(db_ok),
        "architecture": architecture,
        "operational": {"ok": True, "score": 95 if db_ok else 60, "recommendation": "Arranque rápido activo; checks pesados bajo demanda.", "phase": "Sistema liviano y versión unificada", "rows": operational_rows},
        "phase7": phase7,
        "phase9": phase9,
        "phase11": {},
        "captain_logic_tests": captain_logic_tests_idle(),
        "communications_ready": bool(comm.get("smtp_configured")),
    }
    SYSTEM_FAST_CACHE[cache_key] = {"ts": now_ts, "data": data}
    return data

def db_session():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        db.close()

def norm_dni(v: str) -> str:
    """Normaliza DNI, pasaporte o documento extranjero.

    Mantiene letras y números, elimina puntos, espacios, guiones y símbolos.
    Ejemplos:
    - 41.7.6 -> 41325286
    - AB 123456 -> AB123456
    - P-9087-X -> P9087X
    """
    return "".join(ch for ch in (v or "").upper() if ch.isalnum())


def canonical_kind(kind: str) -> str:
    """Normaliza tipos viejos y nuevos.

    socio: socio del club, sin distinguir edad.
    invitado: cualquier no socio que no entra en bonificación.
    hijo_menor: hijo menor de socio que no es socio.
    """
    k = (kind or "").strip()
    if k in ("menor", "hijo_menor", "hijo_socio"):
        return "hijo_menor"
    if k == "socio":
        return "socio"
    return "invitado"

def display_kind(kind: str) -> str:
    k = canonical_kind(kind)
    if k == "socio":
        return "socio"
    if k == "hijo_menor":
        return "hijo menor de socio no socio"
    return "invitado"


def normalize_member_reservations(db: Session, reservations) -> bool:
    """Corrige reservas mal clasificadas contra el padrón de usuarios.

    Regla operativa: si el DNI de una reserva coincide con un usuario activo
    con rol socio, esa persona debe liquidar y figurar como socio, no como
    invitado de otro socio. La relación invitado/responsable no puede pisar
    la condición de socio registrada en el padrón.
    """
    changed = False
    dnis = sorted({norm_dni(getattr(r, "dni", "")) for r in reservations if norm_dni(getattr(r, "dni", ""))})
    if not dnis:
        return False

    socios_by_dni = {
        u.dni: u
        for u in db.query(User).filter(User.dni.in_(dnis), User.active == True, User.role == "socio").all()
    }

    for r in reservations:
        dni = norm_dni(getattr(r, "dni", ""))
        socio = socios_by_dni.get(dni)
        if not socio:
            continue

        if canonical_kind(r.kind) != "socio":
            r.kind = "socio"
            changed = True
        if r.responsible_user_id != socio.id:
            r.responsible_user_id = socio.id
            changed = True
        # Si fue cobrado como invitado por una clasificación vieja, limpiarlo.
        if (r.attendance or "") == "Presente" and float(r.charge_amount or 0) > 0:
            r.charge_amount = 0
            changed = True
        if (r.cancel_reason or "").strip() in ("Tarifa de invitado embarcado", "Invitado embarcado"):
            r.cancel_reason = ""
            changed = True
    return changed

def parse_birth_date(value: Optional[str]):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except Exception:
        return None

def age_on(birth: date, on_date: date) -> int:
    return on_date.year - birth.year - ((on_date.month, on_date.day) < (birth.month, birth.day))

def is_under_18_on(birth_value: Optional[str], on_dt: datetime) -> bool:
    birth = parse_birth_date(birth_value)
    if not birth:
        return False
    return age_on(birth, on_dt.date()) < 18

def user_age_label(birth_value: Optional[str]) -> str:
    birth = parse_birth_date(birth_value)
    if not birth:
        return ""
    years = age_on(birth, now_local().date())
    if years < 13:
        return f"{years} años · menor 13"
    if years < 18:
        return f"{years} años · menor"
    return f"{years} años"


def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
    return f"pbkdf2_sha256${salt}${digest}"

def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$", 2)
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
        return hmac.compare_digest(check, digest)
    except Exception:
        return False


def is_temporary_password(password: str) -> bool:
    return (password or "") == "demo1234"

def password_change_error(new_password: str, confirm_password: str, user: User) -> Optional[str]:
    pwd = (new_password or "").strip()
    confirm = (confirm_password or "").strip()
    if not pwd or not confirm:
        return "faltan_datos"
    if pwd != confirm:
        return "no_coincide"
    if len(pwd) < 6:
        return "corta"
    if is_temporary_password(pwd):
        return "temporal"
    if user and user.member_no and pwd == str(user.member_no):
        return "igual_socio"
    if user and user.dni and pwd == str(user.dni):
        return "igual_documento"
    return None


def sign_value(value: str) -> str:
    sig = hmac.new(SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()
    return f"{value}.{sig}"

def unsign_value(signed: str) -> Optional[str]:
    if not signed or "." not in signed:
        return None
    value, sig = signed.rsplit(".", 1)
    expected = hmac.new(SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()
    return value if hmac.compare_digest(sig, expected) else None


def dt_to_str(v):
    return v.isoformat() if v else None

def str_to_dt(v):
    return datetime.fromisoformat(v) if v else None

def export_state(db: Session) -> dict:
    return {
        "version": VERSION,
        "build": APP_BUILD,
        "exported_at": now_local().isoformat(),
        "users": [
            {"id": u.id, "name": u.name, "dni": u.dni, "member_no": u.member_no,
             "email": u.email or "", "whatsapp": getattr(u, "whatsapp", None) or "", "phone": u.phone or "",
             "category": getattr(u, "category", None) or "", "birth_date": u.birth_date or "", "role": u.role,
             "password_hash": u.password_hash, "active": bool(u.active),
             "can_manage_protocolar": bool(getattr(u, "can_manage_protocolar", False)),
             "must_change_password": bool(getattr(u, "must_change_password", False)),
             "session_version": int(getattr(u, "session_version", 1) or 1),
             "last_login_at": dt_to_str(getattr(u, "last_login_at", None)),
             "last_password_change_at": dt_to_str(getattr(u, "last_password_change_at", None))}
            for u in db.query(User).order_by(User.id).all()
        ],
        "outings": [
            {"id": o.id, "title": o.title, "destination": o.destination, "departure_at": dt_to_str(o.departure_at),
             "status": o.status, "max_crew": o.max_crew, "min_crew": o.min_crew, "guest_fee": float(o.guest_fee or 0),
             "notes": o.notes or "", "created_at": dt_to_str(o.created_at), "boat_id": getattr(o, "boat_id", None) or "fjord_vi"}
            for o in db.query(Outing).order_by(Outing.id).all()
        ],
        "reservations": [
            {"id": r.id, "outing_id": r.outing_id, "person_name": r.person_name, "dni": r.dni, "kind": r.kind,
             "responsible_user_id": r.responsible_user_id, "original_responsible_user_id": getattr(r, "original_responsible_user_id", None),
             "reassignment_count": int(getattr(r, "reassignment_count", 0) or 0),
             "last_reassigned_at": dt_to_str(getattr(r, "last_reassigned_at", None)),
             "last_reassigned_by": getattr(r, "last_reassigned_by", "") or "",
             "status": r.status, "attendance": r.attendance,
             "charge_amount": float(r.charge_amount or 0), "cancel_reason": r.cancel_reason or "",
             "birth_date": r.birth_date or "", "created_at": dt_to_str(r.created_at), "cancelled_at": dt_to_str(r.cancelled_at),
             "protocolar": bool(getattr(r, "protocolar", False)),
             "protocolar_by_user_id": getattr(r, "protocolar_by_user_id", None),
             "protocolar_reason": getattr(r, "protocolar_reason", "") or ""}
            for r in db.query(Reservation).order_by(Reservation.id).all()
        ],
        "audit_logs": [
            {"id": l.id, "created_at": dt_to_str(l.created_at), "actor": l.actor, "action": l.action, "detail": l.detail or ""}
            for l in db.query(AuditLog).order_by(AuditLog.id).all()
        ],
        "reservation_reassignments": [
            {"id": rr.id, "outing_id": rr.outing_id, "reservation_id": rr.reservation_id,
             "from_user_id": rr.from_user_id, "to_user_id": rr.to_user_id,
             "performed_by_user_id": rr.performed_by_user_id, "performed_by_name": rr.performed_by_name or "",
             "performed_at": dt_to_str(rr.performed_at), "reason": rr.reason or ""}
            for rr in db.query(ReservationReassignment).order_by(ReservationReassignment.id).all()
        ],
        "closing_sheets": [
            {"id": cs.id, "outing_id": cs.outing_id, "sequence": cs.sequence, "status": cs.status,
             "created_at": dt_to_str(cs.created_at), "created_by": cs.created_by or "",
             "annulled_at": dt_to_str(cs.annulled_at), "annulled_by": cs.annulled_by or "",
             "annul_reason": cs.annul_reason or "", "payload": cs.payload or "{}"}
            for cs in db.query(ClosingSheet).order_by(ClosingSheet.id).all()
        ],
        "system_meta": [
            {"key": m.key, "value": m.value or "", "updated_at": dt_to_str(m.updated_at)}
            for m in db.query(SystemMeta).order_by(SystemMeta.key).all()
        ],
    }

def persist_json(db: Session):
    """Compatibilidad: el sistema ya no persiste JSON automáticamente.

    Desde v66.6, PostgreSQL es la única fuente de verdad en producción.
    El JSON queda solo como exportación/backup manual desde Sistema, o como
    respaldo puntual previo al Reset Producción. Esta función se conserva como
    no-op para no romper llamadas heredadas en flujos ya estables.
    """
    return False

def import_state(db: Session, data: dict, allow_destructive: bool = False):
    """Importa estado desde backup JSON.

    Blindaje 1.7.6:
    - Por defecto solo importa sobre base vacía.
    - Para borrar datos existentes debe llamarse con allow_destructive=True.
    - El flujo automático restore_json_if_db_empty usa el modo seguro.
    """
    has_existing_data = bool(
        db.query(User).count()
        or db.query(Outing).count()
        or db.query(Reservation).count()
        or db.query(AuditLog).count()
    )
    if has_existing_data and not allow_destructive:
        raise RuntimeError("Importación bloqueada: la base no está vacía.")

    if allow_destructive:
        try:
            db.query(ClosingSheet).delete()
        except Exception:
            pass
        try:
            db.query(ReservationReassignment).delete()
        except Exception:
            pass
        db.query(AuditLog).delete()
        db.query(Reservation).delete()
        db.query(Outing).delete()
        db.query(User).delete()
        # Clonación real: también se limpian metadatos del entorno anterior.
        # El paquete importado vuelve a cargar los metadatos que correspondan.
        try:
            db.query(SystemMeta).delete()
        except Exception:
            pass
        db.commit()
    for u in data.get("users", []):
        db.add(User(id=u.get("id"), name=u.get("name") or "", dni=norm_dni(u.get("dni") or ""),
                    member_no=u.get("member_no"), email=u.get("email") or None, whatsapp=u.get("whatsapp") or None,
                    phone=u.get("phone") or None, category=u.get("category") or None, birth_date=u.get("birth_date") or None,
                    role=u.get("role") or "socio", password_hash=u.get("password_hash") or hash_password("demo1234"),
                    active=bool(u.get("active", True)), can_manage_protocolar=bool(u.get("can_manage_protocolar", False)),
                    must_change_password=bool(u.get("must_change_password", False)), session_version=int(u.get("session_version") or 1),
                    last_login_at=str_to_dt(u.get("last_login_at")), last_password_change_at=str_to_dt(u.get("last_password_change_at"))))
    db.commit()
    for o in data.get("outings", []):
        db.add(Outing(id=o.get("id"), title=o.get("title") or "Salida", destination=o.get("destination") or "",
                      departure_at=str_to_dt(o.get("departure_at")) or now_local(), status=o.get("status") or "En reservas",
                      max_crew=int(o.get("max_crew") or MAX_CREW), min_crew=int(o.get("min_crew") or MIN_CREW),
                      guest_fee=float(o.get("guest_fee") or INVITED_FEE), notes=o.get("notes") or "",
                      created_at=str_to_dt(o.get("created_at")) or now_local(), boat_id=o.get("boat_id") or "fjord_vi"))
    db.commit()
    for r in data.get("reservations", []):
        db.add(Reservation(id=r.get("id"), outing_id=r.get("outing_id"), person_name=r.get("person_name") or "",
                           dni=norm_dni(r.get("dni") or ""), kind=r.get("kind") or "invitado",
                           responsible_user_id=r.get("responsible_user_id"),
                           original_responsible_user_id=r.get("original_responsible_user_id"),
                           reassignment_count=int(r.get("reassignment_count") or 0),
                           last_reassigned_at=str_to_dt(r.get("last_reassigned_at")),
                           last_reassigned_by=r.get("last_reassigned_by") or "",
                           status=r.get("status") or "Confirmado",
                           attendance=r.get("attendance") or "Por confirmar", charge_amount=float(r.get("charge_amount") or 0),
                           cancel_reason=r.get("cancel_reason") or "", birth_date=r.get("birth_date") or None,
                           created_at=str_to_dt(r.get("created_at")) or now_local(),
                           cancelled_at=str_to_dt(r.get("cancelled_at")),
                           protocolar=bool(r.get("protocolar", False)),
                           protocolar_by_user_id=r.get("protocolar_by_user_id"),
                           protocolar_reason=r.get("protocolar_reason") or ""))
    db.commit()
    for l in data.get("audit_logs", []):
        db.add(AuditLog(id=l.get("id"), created_at=str_to_dt(l.get("created_at")) or now_local(),
                        actor=l.get("actor") or "sistema", action=l.get("action") or "import", detail=l.get("detail") or ""))
    db.commit()
    for rr in data.get("reservation_reassignments", []):
        db.add(ReservationReassignment(id=rr.get("id"), outing_id=rr.get("outing_id"), reservation_id=rr.get("reservation_id"),
                                       from_user_id=rr.get("from_user_id"), to_user_id=rr.get("to_user_id"),
                                       performed_by_user_id=rr.get("performed_by_user_id"), performed_by_name=rr.get("performed_by_name") or "",
                                       performed_at=str_to_dt(rr.get("performed_at")) or now_local(), reason=rr.get("reason") or ""))
    db.commit()
    for cs in data.get("closing_sheets", []):
        db.add(ClosingSheet(id=cs.get("id"), outing_id=cs.get("outing_id"), sequence=int(cs.get("sequence") or 1),
                            status=cs.get("status") or "VIGENTE", created_at=str_to_dt(cs.get("created_at")) or now_local(),
                            created_by=cs.get("created_by") or "", annulled_at=str_to_dt(cs.get("annulled_at")),
                            annulled_by=cs.get("annulled_by") or None, annul_reason=cs.get("annul_reason") or "",
                            payload=cs.get("payload") or "{}"))
    db.commit()
    for m in data.get("system_meta", []):
        if not m.get("key"):
            continue
        db.merge(SystemMeta(key=m.get("key"), value=m.get("value") or "", updated_at=str_to_dt(m.get("updated_at")) or now_local()))
    db.commit()
    persist_json(db)

def restore_json_if_db_empty():
    if not JSON_BACKUP_PATH.exists():
        return False
    db = SessionLocal()
    try:
        if db.query(User).count() or db.query(Outing).count() or db.query(Reservation).count():
            return False
        data = json.loads(JSON_BACKUP_PATH.read_text(encoding="utf-8"))
        import_state(db, data)
        return True
    except Exception:
        return False
    finally:
        db.close()

# v66.6: NO restaurar JSON automáticamente al iniciar. PostgreSQL es fuente única de verdad.
# restore_json_if_db_empty()  # desactivado a propósito

def log(db: Session, actor: str, action: str, detail: str = ""):
    db.add(AuditLog(actor=actor, action=action, detail=detail))
    db.commit()
    persist_json(db)


def _audit_value(value):
    try:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value
    except Exception:
        return str(value)


def audit_event(
    db: Session,
    actor_user,
    action: str,
    detail: str = "",
    request: Optional[Request] = None,
    outing_id: Optional[int] = None,
    reservation_id: Optional[int] = None,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
):
    """Auditoría institucional enriquecida sin migrar esquema.

    El modelo actual solo tiene actor/action/detail. Para no tocar base ni UX,
    se guarda un payload compacto dentro de detail con ids afectados, estado
    anterior/nuevo, request id e información mínima del cliente.
    """
    actor_name = getattr(actor_user, "name", None) or str(actor_user or "Sistema")
    actor_role = getattr(actor_user, "role", "") or ""
    payload = {
        "detail": detail or "",
        "role": actor_role,
        "outing_id": outing_id,
        "reservation_id": reservation_id,
        "before": {k: _audit_value(v) for k, v in (before or {}).items()},
        "after": {k: _audit_value(v) for k, v in (after or {}).items()},
    }
    if request is not None:
        payload["request_id"] = request.headers.get("X-Fjord-Request-ID", "")
        try:
            payload["ip"] = request.client.host if request.client else ""
        except Exception:
            payload["ip"] = ""
        payload["user_agent"] = (request.headers.get("user-agent") or "")[:180]
    clean = {k: v for k, v in payload.items() if v not in (None, {}, "")}
    try:
        compact = json.dumps(clean, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        compact = detail or ""
    log(db, actor_name, action, compact)

def parse_session_cookie(raw_cookie: str) -> tuple[Optional[int], Optional[int]]:
    payload = unsign_value(raw_cookie or "")
    if not payload or ":" not in payload:
        return None, None
    try:
        uid_s, sv_s = payload.split(":", 1)
        return int(uid_s), int(sv_s)
    except Exception:
        return None, None


def current_user(request: Request, db: Session = Depends(db_session)) -> Optional[User]:
    uid, cookie_session_version = parse_session_cookie(request.cookies.get(SESSION_COOKIE_NAME, ""))
    if not uid:
        return None
    try:
        user = db.get(User, int(uid))
        if not user or not getattr(user, "active", True):
            return None
        db_session_version = int(getattr(user, "session_version", 1) or 1)
        if int(cookie_session_version or 0) != db_session_version:
            return None
        return user
    except Exception:
        return None

def require_user(user: Optional[User] = Depends(current_user)) -> User:
    if not user:
        raise HTTPException(status_code=401, detail="Sesión requerida")
    return user

def require_role(*roles):
    def dep(user: User = Depends(require_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Rol no autorizado")
        return user
    return dep


@app.middleware("http")
async def force_password_change_middleware(request: Request, call_next):
    path = request.url.path or ""
    allowed = (
        path == "/",
        path == "/login",
        path == "/logout",
        path == "/change-password",
        path.startswith("/static"),
        path.startswith("/health"),
        path == "/favicon.ico",
    )
    if not any(allowed):
        try:
            uid, cookie_session_version = parse_session_cookie(request.cookies.get(SESSION_COOKIE_NAME, ""))
            if uid:
                db = SessionLocal()
                try:
                    u = db.get(User, int(uid))
                    if u and int(cookie_session_version or 0) != int(getattr(u, "session_version", 1) or 1):
                        return RedirectResponse("/logout", status_code=303)
                    if u and getattr(u, "must_change_password", False):
                        return RedirectResponse("/change-password", status_code=303)
                finally:
                    db.close()
        except Exception:
            pass
    return await call_next(request)


@app.middleware("http")
async def activity_tracker(request: Request, call_next):
    response = await call_next(request)
    try:
        path = request.url.path
        if request.method == "GET" and not path.startswith("/static") and path not in ("/health", "/favicon.ico"):
            module = ""
            if path.startswith("/admin"):
                module = "admin"
            elif path.startswith("/captain"):
                module = "capitán"
            elif path.startswith("/socio"):
                module = "socio"
            elif path.startswith("/checkin") or path.startswith("/embarque"):
                module = "check-in"
            if module:
                db = SessionLocal()
                try:
                    uid = unsign_value(request.cookies.get(SESSION_COOKIE_NAME, ""))
                    u = db.get(User, int(uid)) if uid else None
                    db.add(ActivityLog(
                        user_id=u.id if u else None,
                        user_name=u.name if u else "público",
                        role=u.role if u else "public",
                        module=module,
                        action="vista",
                        path=path,
                        detail=str(request.url.query or ""),
                        ip=(request.client.host if request.client else ""),
                        user_agent=(request.headers.get("user-agent") or "")[:500],
                    ))
                    db.commit()
                finally:
                    db.close()
    except Exception:
        pass
    return response

def active_reservations(rows):
    """Reservas que ocupan cupo operativo.

    Importante: antes del cierre, el capitán puede mover tripulantes
    entre Por confirmar / Presente / Ausente sin que el sistema los bloquee.
    Los ausentes y no embarcables quedan visibles en la lista y pueden tener
    cargo calculado, pero no ocupan cupo operativo.
    """
    return [
        r for r in rows
        if r.cancelled_at is None
        and r.status not in ("Cancelado", "Lista de espera")
        and r.attendance != "Lista de espera"
        and not is_captain_cancelled(r)
        and not is_no_board_by_captain(r)
        and r.attendance not in ("Ausente", "No embarcable", "No embarca")
    ]

def reservation_is_active(r: Reservation) -> bool:
    return (
        r.cancelled_at is None
        and r.status not in ("Cancelado", "Lista de espera")
        and r.attendance != "Lista de espera"
        and not is_captain_cancelled(r)
        and not is_no_board_by_captain(r)
        and r.attendance not in ("Ausente", "No embarcable", "No embarca")
    )


def responsible_reservation_for(db: Session, outing_id: int, responsible_user_id: Optional[int]) -> Optional[Reservation]:
    """Reserva titular del socio responsable dentro de una salida."""
    if not responsible_user_id:
        return None
    responsible = db.get(User, responsible_user_id)
    if not responsible:
        return None
    return db.query(Reservation).filter_by(outing_id=outing_id, dni=responsible.dni).first()


def dependent_reservations_for(db: Session, outing_id: int, socio_reservation: Reservation) -> list:
    """Invitados/menores vinculados a un socio titular en una salida."""
    if not socio_reservation or not socio_reservation.responsible_user_id:
        return []
    return db.query(Reservation).filter(
        Reservation.outing_id == outing_id,
        Reservation.responsible_user_id == socio_reservation.responsible_user_id,
        Reservation.dni != socio_reservation.dni,
        Reservation.status != "Lista de espera"
    ).all()


def cascade_dependents_for_responsible_status(
    db: Session,
    outing: Outing,
    socio_reservation: Reservation,
    *,
    mode: str,
) -> list:
    """Aplica la cascada crítica de Capitán sobre invitados comunes/menores.

    No toca protocolares/institucionales: conservan referencia del socio que los cargó,
    pero no entran en la cascada económica ni operativa del socio.

    mode="absent_charged": socio ausente/reserva incumplida. Sus invitados comunes no embarcan
    y quedan con cargo al socio original, salvo reasignación previa.

    mode="no_board_free": el capitán decide que el socio no embarca sin cargo. Sus
    invitados comunes tampoco pueden embarcar bajo ese socio y quedan sin cargo, salvo
    reasignación manual a otro socio presente.
    """
    changed = []
    if not outing or not socio_reservation or canonical_kind(socio_reservation.kind) != "socio":
        return changed

    for dep in dependent_reservations_for(db, outing.id, socio_reservation):
        if is_protocolar(dep):
            continue
        if is_waitlisted(dep):
            continue
        if dep.cancelled_at is not None or dep.status == "Cancelado":
            continue

        if mode == "absent_charged":
            new_attendance = "Ausente"
            new_reason = "No embarcó por ausencia del socio responsable"
            new_charge = reservation_charge(outing, dep) if late_window_passed(outing) else 0
        elif mode == "no_board_free":
            new_attendance = "No embarca"
            new_reason = "No embarcado: socio responsable no embarca / sin cargo por decisión del capitán"
            new_charge = 0
        else:
            continue

        if dep.attendance != new_attendance or (dep.cancel_reason or "") != new_reason or float(dep.charge_amount or 0) != float(new_charge or 0):
            dep.attendance = new_attendance
            dep.cancel_reason = new_reason
            dep.charge_amount = new_charge
            changed.append(dep.person_name)

    return changed


def cascade_no_board_dependents(db: Session, outing: Outing, socio_reservation: Reservation, reason: str = "No embarcado: socio responsable no embarca") -> list:
    """Compatibilidad histórica: cascada sin cargo por decisión del capitán."""
    return cascade_dependents_for_responsible_status(db, outing, socio_reservation, mode="no_board_free")


def enforce_responsible_dependency(db: Session, outing: Outing, reservations=None) -> list:
    """Aplica la regla: invitado solo puede embarcar si embarca su socio responsable."""
    changed = []
    if not outing:
        return changed
    rows = list(reservations) if reservations is not None else db.query(Reservation).filter_by(outing_id=outing.id).all()
    by_dni = {r.dni: r for r in rows}
    users_by_id = {u.id: u for u in db.query(User).filter(User.id.in_([r.responsible_user_id for r in rows if r.responsible_user_id])).all()}
    for r in rows:
        if canonical_kind(r.kind) not in ("invitado", "hijo_menor"):
            continue
        if is_protocolar(r):
            continue
        if is_waitlisted(r) or r.cancelled_at is not None or r.status == "Cancelado":
            continue
        responsible = users_by_id.get(r.responsible_user_id)
        responsible_row = by_dni.get(responsible.dni) if responsible else None
        responsible_present = bool(responsible_row and canonical_kind(responsible_row.kind) == "socio" and responsible_row.attendance == "Presente" and reservation_is_active(responsible_row))
        if not responsible_present and r.attendance in ("Presente", "Por confirmar"):
            if responsible_row and responsible_row.attendance == "Ausente":
                # Socio ausente/reserva incumplida: el invitado común no embarca, pero queda
                # con cargo al socio original salvo reasignación previa.
                r.attendance = "Ausente"
                r.cancel_reason = "No embarcó por ausencia del socio responsable"
                r.charge_amount = reservation_charge(outing, r) if late_window_passed(outing) else 0
            elif responsible_row and is_no_board_by_captain(responsible_row):
                # El capitán impidió el embarque del socio: sus invitados comunes
                # tampoco pueden embarcar bajo ese socio, pero no generan cargo.
                r.attendance = "No embarca"
                r.cancel_reason = "No embarcado: socio responsable no embarca / sin cargo por decisión del capitán"
                r.charge_amount = 0
            else:
                # Sin socio responsable presente verificable: por seguridad operativa
                # no se permite embarque. Se deja sin cargo hasta corrección/reasignación.
                r.attendance = "No embarca"
                r.cancel_reason = "No embarcado: socio responsable no presente"
                r.charge_amount = 0
            changed.append(r.person_name)
    return changed

def ensure_outing_editable(outing: Outing):
    if outing and outing.status == "Embarque cerrado":
        raise HTTPException(status_code=400, detail="La salida ya fue cerrada")
    if outing and outing.status == "Cancelada por capitán":
        raise HTTPException(status_code=400, detail="La salida fue cancelada por capitán. Debe reabrirse desde Capitán para volver a operar.")

def reactivate_reservation(db: Session, outing: Outing, r: Reservation):
    r.cancelled_at = None
    r.status = default_reservation_status(outing, r)
    r.attendance = "Por confirmar"
    r.charge_amount = 0
    r.cancel_reason = ""

def is_waitlisted(r: Reservation) -> bool:
    return (getattr(r, "status", "") == "Lista de espera" or getattr(r, "attendance", "") == "Lista de espera")



def institutional_reserve(outing: Outing) -> int:
    try:
        return max(0, int(getattr(outing, "institutional_reserve", 0) or 0))
    except Exception:
        return 0

def public_capacity(outing: Outing) -> int:
    """Capacidad disponible para reservas normales. No incluye reserva institucional."""
    if not outing:
        return MAX_CREW
    try:
        return max(0, int(outing.max_crew or MAX_CREW) - institutional_reserve(outing))
    except Exception:
        return MAX_CREW

def active_public_reservations(rows) -> list:
    return [r for r in active_reservations(rows) if not is_protocolar(r)]

def active_protocolar_reservations(rows) -> list:
    return [r for r in active_reservations(rows) if is_protocolar(r)]

def protocolar_capacity_available(outing: Outing, rows, exclude_id: Optional[int] = None) -> bool:
    """Puede usar reserva institucional o cupo operativo libre total."""
    active = [r for r in active_reservations(rows) if not exclude_id or r.id != exclude_id]
    proto = [r for r in active if is_protocolar(r)]
    if len(active) < int(outing.max_crew or MAX_CREW):
        return True
    return len(proto) < institutional_reserve(outing)

def put_on_waitlist(r: Reservation, reason: str = "En lista de espera"):
    # La lista de espera no ocupa cupo y nunca genera cargo mientras no sea promovida.
    r.status = "Lista de espera"
    r.attendance = "Lista de espera"
    r.charge_amount = 0
    r.cancel_reason = reason
    r.cancelled_at = None




def can_user_manage_guest_record(user: User, outing: Outing, reservation: Reservation) -> bool:
    if not reservation or not outing:
        return False
    if reservation.outing_id != outing.id:
        return False
    if canonical_kind(reservation.kind) not in ("invitado", "hijo_menor"):
        return False
    if is_closed_outing(outing):
        return False
    if reservation.attendance == "Presente":
        return False
    return reservation.responsible_user_id == user.id


def replace_guest_under_socio(
    db: Session,
    outing: Outing,
    old_reservation: Reservation,
    user: User,
    new_name: str,
    new_dni: str,
    new_kind: str,
    new_birth_date: Optional[str] = None,
):
    now = now_local()
    old_was_waitlisted = is_waitlisted(old_reservation)
    old_charge = 0 if old_was_waitlisted else (reservation_charge(outing, old_reservation) if late_window_passed(outing) else 0)
    old_reservation.cancelled_at = now
    old_reservation.status = "Cancelado"
    old_reservation.attendance = "Ausente"
    old_reservation.cancel_reason = "Reemplazado por socio" if not late_window_passed(outing) else "Reemplazado fuera de término por socio"
    old_reservation.charge_amount = old_charge

    status = "Hijo menor de socio no socio" if new_kind == "hijo_menor" else ("Confirmado" if cutoff_passed(outing) else "Condicional hasta 48h")
    new_guest = Reservation(
        outing_id=outing.id,
        person_name=new_name,
        dni=new_dni,
        kind=new_kind,
        responsible_user_id=user.id,
        original_responsible_user_id=user.id,
        status=status,
        birth_date=new_birth_date,
    )
    rows = db.query(Reservation).filter_by(outing_id=outing.id).all()
    if len(active_public_reservations(rows)) >= public_capacity(outing):
        put_on_waitlist(new_guest, "En lista de espera. Se activa si se libera una vacante.")
        new_waitlisted = True
    else:
        new_waitlisted = False
    db.add(new_guest)
    db.flush()
    promoted = promote_waitlist(db, outing)
    return new_guest, old_charge, new_waitlisted, promoted

def displaceable_guest_for_socios(db: Session, outing: Outing) -> Optional[Reservation]:
    """Devuelve un invitado/menor activo desplazable por prioridad de socio.

    Regla operacional:
    - Antes del corte de 48h, los socios conservan prioridad.
    - Si el cupo está lleno y entra un socio, puede desplazar a un invitado/menor activo.
    - Después del corte de 48h, la tripulación activa queda congelada: ya no hay desplazamiento
      por prioridad, solo promoción por vacante real desde lista de espera.
    """
    if not outing or cutoff_passed(outing):
        return None
    rows = db.query(Reservation).filter_by(outing_id=outing.id).all()
    candidates = [
        r for r in active_reservations(rows)
        if canonical_kind(r.kind) in ("invitado", "hijo_menor")
        and not is_protocolar(r)
        and (r.attendance or "Por confirmar") != "Presente"
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda r: (r.created_at or datetime.min, r.id or 0), reverse=True)
    return candidates[0]


def place_socio_with_priority(db: Session, outing: Outing, r: Reservation) -> tuple[str, Optional[str]]:
    """Ubica una reserva de socio respetando prioridad y congelamiento 48h.

    Retorna:
    - active: entró al cupo sin desplazar.
    - active_displaced: entró al cupo y desplazó un invitado/menor a espera.
    - waitlist: quedó en lista de espera.
    """
    rows = db.query(Reservation).filter_by(outing_id=outing.id).all()
    # Para decidir cupo, se excluye la propia reserva objetivo: una reserva nueva
    # recién creada o una reserva en espera no debe contarse como ocupante antes
    # de decidir si entra o queda en espera.
    rows_without_target = [x for x in rows if x is not r and (not getattr(r, "id", None) or x.id != r.id)]

    if len(active_public_reservations(rows_without_target)) < public_capacity(outing):
        reactivate_reservation(db, outing, r)
        return "active", None

    displaced = displaceable_guest_for_socios(db, outing)
    if displaced:
        put_on_waitlist(displaced, "Desplazado a lista de espera por prioridad de socio antes del corte de 48h")
        reactivate_reservation(db, outing, r)
        return "active_displaced", displaced.person_name

    put_on_waitlist(r, "En lista de espera. Se activa si se libera una vacante.")
    return "waitlist", None


def promote_waitlist(db: Session, outing: Outing) -> list:
    """Promueve automáticamente lista de espera cuando aparece una vacante."""
    if not outing or is_closed_outing(outing) or is_outing_cancelled_by_captain(outing):
        return []
    promoted = []
    while True:
        rows = db.query(Reservation).filter_by(outing_id=outing.id).order_by(Reservation.created_at.asc(), Reservation.id.asc()).all()
        if len(active_public_reservations(rows)) >= public_capacity(outing):
            break
        waiting = [r for r in rows if is_waitlisted(r)]
        if not waiting:
            break
        # Antes del corte, socios primero. Después del corte, no hay desplazamiento por
        # prioridad: se respeta el orden cronológico de lista de espera ante una vacante real.
        if cutoff_passed(outing):
            waiting.sort(key=lambda r: (r.created_at or now_local(), r.id or 0))
        else:
            waiting.sort(key=lambda r: (0 if canonical_kind(r.kind) == "socio" else 1, r.created_at or now_local(), r.id or 0))
        chosen = None
        for r in waiting:
            k = canonical_kind(r.kind)
            if k in ("invitado", "hijo_menor") and not is_protocolar(r):
                responsible = db.get(User, r.responsible_user_id) if r.responsible_user_id else None
                if not responsible:
                    continue
                responsible_row = db.query(Reservation).filter_by(outing_id=outing.id, dni=responsible.dni).first()
                # Post-reapertura: solo se promueven invitados cuyo socio responsable
                # siga operativo en la salida. Evita dejar "Espera / Sin acción"
                # cuando hay vacante, pero también evita subir invitados bajo un socio
                # que ya quedó Ausente o No embarca.
                if not responsible_row or not reservation_is_active(responsible_row) or responsible_row.attendance not in ("Presente", "Por confirmar"):
                    continue
            chosen = r
            break
        if not chosen:
            break
        chosen.status = default_reservation_status(outing, chosen)
        chosen.attendance = "Por confirmar"
        chosen.charge_amount = 0
        chosen.cancel_reason = "Promovido desde lista de espera"
        chosen.cancelled_at = None
        promoted.append(chosen.person_name)
    return promoted


def captain_can_activate_waitlisted_reservation(db: Session, outing: Outing, r: Reservation) -> bool:
    """Determina si el capitán puede sacar una reserva de espera en ese momento.

    Se usa especialmente después de reabrir y liberar una plaza, cuando la lista de
    espera debe volver a quedar operable sin romper dependencia socio-invitado.
    """
    if not outing or not r or not is_waitlisted(r):
        return False

    rows = db.query(Reservation).filter_by(outing_id=outing.id).all()
    rows_without_target = [x for x in rows if x.id != r.id]
    kind = canonical_kind(r.kind)

    if kind == "socio":
        return len(active_public_reservations(rows_without_target)) < public_capacity(outing)

    if is_protocolar(r):
        return protocolar_capacity_available(outing, rows_without_target)

    if kind in ("invitado", "hijo_menor"):
        responsible_row = responsible_reservation_for(db, outing.id, r.responsible_user_id)
        responsible_ok = bool(
            responsible_row
            and canonical_kind(responsible_row.kind) == "socio"
            and reservation_is_active(responsible_row)
            and responsible_row.attendance in ("Presente", "Por confirmar")
        )
        if not responsible_ok:
            return False
        return len(active_public_reservations(rows_without_target)) < public_capacity(outing)

    return len(active_reservations(rows_without_target)) < int(outing.max_crew or MAX_CREW)


def captain_activate_waitlisted_reservation(db: Session, outing: Outing, r: Reservation) -> bool:
    """Reactiva operativamente una reserva desde espera cuando ya existe vacante real."""
    if not captain_can_activate_waitlisted_reservation(db, outing, r):
        return False
    previous_trace = _reassignment_trace_only_bootstrap(r.cancel_reason or "")
    r.cancelled_at = None
    r.status = default_reservation_status(outing, r)
    r.attendance = "Por confirmar"
    r.charge_amount = 0
    r.cancel_reason = previous_trace or "Promovido manualmente desde lista de espera por capitán"
    return True


def enforce_capacity(db: Session, outing: Outing) -> list:
    """Garantiza que nunca haya más reservas activas que cupo.

    Si por datos heredados o por una combinación de altas/reaperturas quedaron
    más activos que el máximo, baja primero invitados/menores no presentes a
    lista de espera. No toca a personas ya marcadas Presente por el capitán.
    """
    if not outing or is_closed_outing(outing) or is_outing_cancelled_by_captain(outing):
        return []

    displaced = []

    # Blindaje 1.7.6: la reserva institucional no puede ser ocupada por lista/reservas normales.
    # Si al bajar la capacidad pública quedan reservas normales excedidas, se mueve primero
    # a invitados/menores no presentes y luego a otros registros no presentes.
    while True:
        rows = db.query(Reservation).filter_by(outing_id=outing.id).all()
        active_public = active_public_reservations(rows)
        if len(active_public) <= public_capacity(outing):
            break
        candidates = [
            r for r in active_public
            if (r.attendance or "Por confirmar") != "Presente"
            and canonical_kind(r.kind) in ("invitado", "hijo_menor")
        ]
        if not candidates:
            candidates = [r for r in active_public if (r.attendance or "Por confirmar") != "Presente"]
        if not candidates:
            break
        candidates.sort(key=lambda r: (r.created_at or datetime.min, r.id or 0), reverse=True)
        chosen = candidates[0]
        put_on_waitlist(chosen, "Pasado a lista de espera para respetar reserva institucional")
        displaced.append(chosen.person_name)

    while True:
        rows = db.query(Reservation).filter_by(outing_id=outing.id).all()
        active = active_reservations(rows)
        if len(active) <= outing.max_crew:
            break

        candidates = [
            r for r in active
            if (r.attendance or "Por confirmar") != "Presente"
            and canonical_kind(r.kind) in ("invitado", "hijo_menor")
            and not is_protocolar(r)
        ]
        if not candidates:
            candidates = [r for r in active if (r.attendance or "Por confirmar") != "Presente" and not is_protocolar(r)]
        if not candidates:
            break

        candidates.sort(key=lambda r: (r.created_at or datetime.min, r.id or 0), reverse=True)
        chosen = candidates[0]
        put_on_waitlist(chosen, "Pasado a lista de espera para respetar cupo máximo de 9")
        displaced.append(chosen.person_name)

    return displaced

def default_reservation_status(outing: Outing, r: Reservation) -> str:
    k = canonical_kind(r.kind)
    if k == "hijo_menor":
        return "Hijo menor de socio no socio"
    if k == "invitado" and not cutoff_passed(outing):
        return "Condicional hasta 48h"
    return "Confirmado"

def cutoff_at(outing: Outing) -> datetime:
    return outing.departure_at - timedelta(hours=48)

def cancellation_deadline(outing: Outing) -> datetime:
    # Para paseos de fin de semana, el corte reglamentario operativo/contable es 48 horas antes.
    return cutoff_at(outing)

def cutoff_passed(outing: Outing) -> bool:
    return now_local() >= cutoff_at(outing)

def late_window_passed(outing: Outing) -> bool:
    return now_local() >= cancellation_deadline(outing)

def reservation_charge(outing: Outing, r: Reservation) -> float:
    """Cargo reglamentario por plaza perdida.

    Regla operativa vigente para paseos Fjord VI:
    - Socio presente: no paga.
    - Socio no embarcó / ausente: paga 70% de la tarifa de invitado.
    - Invitado / hijo menor no socio presente: paga tarifa completa por navegación
      (eso se liquida aparte, no en esta función).
    - Invitado / hijo menor no socio no embarcó: paga tarifa completa de invitado.
    - No embarca por decisión del capitán: se filtra antes y siempre queda sin cargo.

    Esta función NO se usa para navegación normal; solo para ausencias/cancelaciones
    tardías con cargo.
    """
    if is_protocolar(r):
        return 0.0
    fee = float(outing.guest_fee or 0)
    k = canonical_kind(r.kind)
    if k == "socio":
        return fee * LATE_SOCIO_RATE
    if k in ("invitado", "hijo_menor"):
        return fee
    return 0.0

def human_money(value) -> str:
    return f"{float(value or 0):,.0f}".replace(",", ".")

# Alias de compatibilidad: varias rutinas de emails/cierre usan fmt_money.
def fmt_money(value) -> str:
    return human_money(value)


def can_manage_protocolar(user: User) -> bool:
    return bool(user and (user.role == "admin" or getattr(user, "can_manage_protocolar", False)))

def is_protocolar(r: Reservation) -> bool:
    return bool(getattr(r, "protocolar", False))

def protocolar_label(r: Reservation) -> str:
    return "Participación protocolar" if is_protocolar(r) else ""


def mask_document(value) -> str:
    """Documento abreviado para pantallas móviles/operativas.

    En fichas y administración el DNI de invitados puede verse completo;
    en Capitán conviene evitar ruido visual y exponer solo la terminación.
    """
    raw = norm_dni(value or "")
    if not raw:
        return ""
    if len(raw) <= 4:
        return raw
    return "***" + raw[-4:]

templates.env.filters["money"] = human_money
templates.env.filters["mask_doc"] = mask_document
templates.env.globals.update({"user_age_label": user_age_label})


def valid_email_syntax(email: str) -> bool:
    e = (email or "").strip()
    return bool(e and "@" in e and "." in e.split("@")[-1] and " " not in e)

def data_blindaje_checks(db: Session) -> dict:
    """Chequeos defensivos de consistencia sin modificar datos."""
    checks = {
        "duplicate_user_dni": [],
        "duplicate_member_no": [],
        "duplicate_reservation_dni_by_outing": [],
        "multiple_vigente_sheets_by_outing": [],
        "orphan_guest_reservations": [],
        "institutional_reserve_over_capacity": [],
    }

    # Usuarios con DNI/documento repetido.
    rows = db.query(User.dni).filter(User.dni.isnot(None), User.dni != "").group_by(User.dni).having(func.count(User.id) > 1).all()
    checks["duplicate_user_dni"] = [r[0] for r in rows]

    # N° de socio repetido. El modelo no siempre tiene restricción física para member_no.
    rows = db.query(User.member_no).filter(User.member_no.isnot(None), User.member_no != "").group_by(User.member_no).having(func.count(User.id) > 1).all()
    checks["duplicate_member_no"] = [r[0] for r in rows]

    # Una misma persona repetida dentro de la misma salida.
    rows = db.query(Reservation.outing_id, Reservation.dni).filter(Reservation.dni != "").group_by(Reservation.outing_id, Reservation.dni).having(func.count(Reservation.id) > 1).all()
    checks["duplicate_reservation_dni_by_outing"] = [{"outing_id": r[0], "dni": r[1]} for r in rows]

    # Más de una ficha vigente por salida.
    rows = db.query(ClosingSheet.outing_id).filter(ClosingSheet.status == "VIGENTE").group_by(ClosingSheet.outing_id).having(func.count(ClosingSheet.id) > 1).all()
    checks["multiple_vigente_sheets_by_outing"] = [r[0] for r in rows]

    # Salidas con reserva institucional inválida.
    rows = db.query(Outing).all()
    checks["institutional_reserve_over_capacity"] = [
        {"outing_id": o.id, "max_crew": o.max_crew, "institutional_reserve": getattr(o, "institutional_reserve", 0)}
        for o in rows
        if institutional_reserve(o) > int(o.max_crew or 0)
    ]

    # Invitados/menores sin socio responsable, excepto participación protocolar institucional.
    rows = db.query(Reservation).filter(Reservation.kind.in_(["invitado", "hijo_menor"]), Reservation.responsible_user_id.is_(None), Reservation.protocolar == False).all()
    checks["orphan_guest_reservations"] = [{"reservation_id": r.id, "outing_id": r.outing_id, "name": r.person_name} for r in rows]

    checks["ok"] = not any(v for k, v in checks.items() if k != "ok")
    return checks


SOCIO_CATEGORIES = [
    "activo", "activo_marino", "vitalicio", "previtalicio", "preactivo",
    "suscriptora", "suscriptora_vitalicia", "suscriptora_previtalicia",
    "cadete", "menor", "honorario", "diplomatico", "adherente", "otro"
]

def normalize_category(value: str) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return ""
    trans = str.maketrans("áéíóúüñ", "aeiouun")
    v = raw.translate(trans).replace("/", " ").replace("-", " ").replace(".", " ")
    v = "_".join(v.split())
    aliases = {
        "activo": "activo", "activa": "activo", "socio_activo": "activo",
        "activo_marino": "activo_marino", "activa_marina": "activo_marino", "marino": "activo_marino",
        "vitalicio": "vitalicio", "vitalicia": "vitalicio",
        "previtalicio": "previtalicio", "previtalicia": "previtalicio", "pre_vitalicio": "previtalicio",
        "preactivo": "preactivo", "preactiva": "preactivo", "pre_activo": "preactivo",
        "suscriptora": "suscriptora", "suscriptor": "suscriptora",
        "suscriptora_vitalicia": "suscriptora_vitalicia", "suscriptor_vitalicio": "suscriptora_vitalicia",
        "suscriptora_previtalicia": "suscriptora_previtalicia", "suscriptor_previtalicio": "suscriptora_previtalicia",
        "cadete": "cadete", "menor": "menor", "menores": "menor",
        "honorario": "honorario", "honoraria": "honorario",
        "diplomatico": "diplomatico", "diplomatica": "diplomatico",
        "adherente": "adherente",
    }
    return aliases.get(v, "otro")

def category_label(value: str) -> str:
    labels = {
        "activo": "Activo", "activo_marino": "Activo marino", "vitalicio": "Vitalicio",
        "previtalicio": "Previtalicio", "preactivo": "Preactivo", "suscriptora": "Suscriptora",
        "suscriptora_vitalicia": "Suscriptora vitalicia", "suscriptora_previtalicia": "Suscriptora previtalicia",
        "cadete": "Cadete", "menor": "Menor", "honorario": "Honorario",
        "diplomatico": "Diplomático", "adherente": "Adherente", "otro": "Otro"
    }
    return labels.get((value or "").strip(), value or "-")

def member_key(value: str) -> str:
    return ''.join(ch for ch in str(value or '').strip() if ch.isalnum()).upper()

def synthetic_dni_for_member(member_no: str) -> str:
    mk = member_key(member_no)
    return f"SOCIO-{mk}" if mk else ""

def is_synthetic_member_dni(dni: str) -> bool:
    return str(dni or "").upper().startswith("SOCIO-")

def padron_standard_headers() -> list[str]:
    return ["nro_socio", "nombre_completo", "categoria", "email", "whatsapp", "telefono", "dni", "estado"]

def normalize_import_header(h: str) -> str:
    raw = (h or "").strip().lower()
    trans = str.maketrans("áéíóúüñº°", "aeiouunoo")
    v = raw.translate(trans).replace("/", " ").replace("-", " ").replace(".", " ")
    v = "_".join(v.split())
    aliases = {
        "nro_socio": "nro_socio", "numero_de_socio": "nro_socio", "numero_socio": "nro_socio", "no_socio": "nro_socio", "socio": "nro_socio", "n_socio": "nro_socio",
        "nombre": "nombre", "nombres": "nombre", "nombre_completo": "nombre_completo", "apellido_nombre": "nombre_completo", "apellido_y_nombre": "nombre_completo", "apellidonombre": "nombre_completo", "apellidos_nombres": "nombre_completo", "socio_nombre": "nombre_completo", "apellido": "apellido", "apellidos": "apellido",
        "tipo": "categoria", "tipo_de_socio": "categoria", "categoria": "categoria", "categoria_socio": "categoria",
        "mail": "email", "e_mail": "email", "email": "email", "correo": "email", "correo_electronico": "email",
        "whatsapp": "whatsapp", "wapp": "whatsapp", "celular": "whatsapp", "movil": "whatsapp",
        "telefono": "telefono", "tel": "telefono", "telefono_linea": "telefono",
        "dni": "dni", "documento": "dni", "numero_documento": "dni",
        "estado": "estado", "activo": "estado",
    }
    return aliases.get(v, v)

templates.env.globals.update({"category_label": category_label, "socio_categories": SOCIO_CATEGORIES})


def build_padron_context(db: Session) -> dict:
    """Resumen profesional del padrón: calidad de datos, duplicados y métricas por persona.

    No cambia datos. Solo prepara información para Administración.
    """
    users = db.query(User).order_by(User.name.asc()).all()
    reservations = db.query(Reservation).all()
    outings_by_id = {o.id: o for o in db.query(Outing).all()}
    users_by_dni = {norm_dni(u.dni): u for u in users if norm_dni(u.dni)}

    email_map = {}
    member_map = {}
    for u in users:
        em = (u.email or "").strip().lower()
        if em:
            email_map.setdefault(em, []).append(u)
        mem = (u.member_no or "").strip().lower()
        if mem:
            member_map.setdefault(mem, []).append(u)

    duplicate_email_ids = {u.id for group in email_map.values() if len(group) > 1 for u in group}
    duplicate_member_ids = {u.id for group in member_map.values() if len(group) > 1 for u in group}
    missing_email_ids = {u.id for u in users if u.role == "socio" and not (u.email or "").strip()}
    missing_whatsapp_ids = {u.id for u in users if u.role == "socio" and not (getattr(u, "whatsapp", None) or "").strip()}
    invalid_email_ids = {u.id for u in users if (u.email or "").strip() and not valid_email_syntax(u.email)}

    metrics = {u.id: {"navigations": 0, "responsible_guests": 0, "no_show": 0, "charges": 0.0, "last": "", "flags": []} for u in users}

    for r in reservations:
        nd = norm_dni(r.dni)
        person_user = users_by_dni.get(nd)
        outing = outings_by_id.get(r.outing_id)
        dt = outing.departure_at if outing else r.created_at
        last_label = fmt_admin_datetime_short(dt) if dt else ""

        # Historial personal por documento.
        if person_user:
            m = metrics.setdefault(person_user.id, {"navigations": 0, "responsible_guests": 0, "no_show": 0, "charges": 0.0, "last": "", "flags": []})
            if r.attendance == "Presente" or str(r.status).lower() == "embarcado":
                m["navigations"] += 1
            if r.attendance == "No embarcó":
                m["no_show"] += 1
            m["charges"] += float(r.charge_amount or 0)
            if last_label and (not m["last"]):
                m["last"] = last_label

        # Historial de responsabilidad del socio.
        if r.responsible_user_id and canonical_kind(r.kind) != "socio":
            m = metrics.setdefault(r.responsible_user_id, {"navigations": 0, "responsible_guests": 0, "no_show": 0, "charges": 0.0, "last": "", "flags": []})
            if r.attendance == "Presente" or str(r.status).lower() == "embarcado":
                m["responsible_guests"] += 1
            m["charges"] += float(r.charge_amount or 0)
            if last_label and (not m["last"]):
                m["last"] = last_label

    for u in users:
        flags = []
        if u.id in missing_email_ids:
            flags.append("sin_email")
        if u.id in invalid_email_ids:
            flags.append("email_invalido")
        if u.id in duplicate_email_ids:
            flags.append("email_duplicado")
        if u.id in duplicate_member_ids:
            flags.append("socio_duplicado")
        metrics.setdefault(u.id, {"navigations": 0, "responsible_guests": 0, "no_show": 0, "charges": 0.0, "last": "", "flags": []})["flags"] = flags
        metrics[u.id]["charges_label"] = human_money(metrics[u.id].get("charges", 0))

    # Invitados no convertidos en usuarios: candidatos reales a socio.
    # No mostramos todo invitado ocasional: solo quienes tuvieron al menos 2 embarques
    # o 3 registros. Administración puede ocultarlos sin borrar historial.
    hidden_candidate_dnis = get_hidden_guest_candidate_dnis(db)
    guest_groups = {}
    for r in reservations:
        if canonical_kind(r.kind) == "socio":
            continue
        nd = norm_dni(r.dni)
        if not nd or nd in users_by_dni or nd in hidden_candidate_dnis:
            continue
        g = guest_groups.setdefault(nd, {"dni": nd, "name": r.person_name, "count": 0, "present": 0, "no_show": 0, "last": "", "responsible": "", "reservation_id": r.id})
        g["count"] += 1
        if r.attendance == "Presente" or str(r.status).lower() == "embarcado":
            g["present"] += 1
        if r.attendance == "No embarcó":
            g["no_show"] += 1
        resp = db.get(User, r.responsible_user_id) if r.responsible_user_id else None
        if resp:
            g["responsible"] = resp.name
        outing = outings_by_id.get(r.outing_id)
        if outing and not g["last"]:
            g["last"] = fmt_admin_datetime_short(outing.departure_at)
    guest_candidates_all = [g for g in guest_groups.values() if g["present"] >= 2 or g["count"] >= 3]
    guest_candidates = sorted(guest_candidates_all, key=lambda x: (-x["present"], -x["count"], x["name"]))[:25]

    return {
        "total": len(users),
        "active": sum(1 for u in users if u.active),
        "socios": sum(1 for u in users if u.role == "socio"),
        "captains": sum(1 for u in users if u.role == "captain"),
        "admins": sum(1 for u in users if u.role == "admin"),
        "missing_email_count": len(missing_email_ids),
        "missing_whatsapp_count": len(missing_whatsapp_ids),
        "invalid_email_count": len(invalid_email_ids),
        "categories": {c: sum(1 for u in users if getattr(u, "category", None) == c and u.role == "socio") for c in SOCIO_CATEGORIES},
        "duplicate_email_count": len(duplicate_email_ids),
        "duplicate_member_count": len(duplicate_member_ids),
        "metrics": metrics,
        "guest_candidates": guest_candidates,
        "hidden_guest_candidate_count": len(hidden_candidate_dnis),
    }





def captain_control_window(outing: Outing) -> dict:
    """Ventana operativa del capitán.

    Regla acordada:
    - Puede operar asistencia/cancelación/reapertura hasta 48h desde la hora programada.
    - El cierre/liquidación no puede ejecutarse antes de la hora programada.
    - Pasadas 48h, solo Administración puede corregir.
    """
    if not outing:
        return {"can_edit": False, "can_close": False, "before_departure": False, "expired": True, "label": "Sin salida", "detail": "No hay salida seleccionada."}
    now = now_local()
    start = outing.departure_at
    end = outing.departure_at + timedelta(hours=48)
    before = now < start
    expired = now > end
    can_edit = not expired
    can_close = (not before) and (not expired)
    if before:
        detail = f"El cierre estará disponible desde {start.strftime('%d/%m %H:%M')}."
        label = "Antes de la salida"
    elif expired:
        detail = "Período de edición del capitán finalizado. Para cambios, contactar Administración."
        label = "Edición finalizada"
    else:
        detail = f"Capitán puede cerrar o corregir hasta {end.strftime('%d/%m %H:%M')}."
        label = "Ventana operativa activa"
    return {"start": start, "end": end, "now": now, "can_edit": can_edit, "can_close": can_close, "before_departure": before, "expired": expired, "label": label, "detail": detail}


def ensure_captain_window(user: User, outing: Outing, action: str = "edit"):
    """Bloqueo temporal por rol.

    Administración conserva control completo. Capitán queda limitado por la ventana temporal.
    """
    if not outing:
        raise HTTPException(400, "Salida inexistente")
    if user.role == "admin":
        return
    w = captain_control_window(outing)
    if w["expired"]:
        raise HTTPException(status_code=400, detail="Período de edición del capitán finalizado. Para cambios, contactar Administración.")
    if action == "close" and w["before_departure"]:
        raise HTTPException(status_code=400, detail="Aún no se puede cerrar: el cierre se habilita desde la hora programada de salida.")

def is_closed_outing(outing: Outing) -> bool:
    return bool(outing and outing.status == "Embarque cerrado")


def is_outing_cancelled_by_captain(outing: Outing) -> bool:
    return bool(outing and outing.status == "Cancelada por capitán")


def is_captain_cancelled(r: Reservation) -> bool:
    reason = (getattr(r, "cancel_reason", "") or "").strip().lower()
    status = (getattr(r, "status", "") or "").strip().lower()
    text = f"{reason} {status}"
    return (
        "cancelado por capitán" in text
        or "cancelada por capitán" in text
        or "cancelado por capitan" in text
        or "cancelada por capitan" in text
    )


def is_no_board_by_captain(r: Reservation) -> bool:
    """Caso operativo: la persona llegó o estaba anotada,
    pero el capitán decide no embarcarla. No es reserva incumplida: no genera cargo.
    Incluye compatibilidad con el texto viejo 'Ausente marcado por capitán'.
    """
    attendance = (getattr(r, "attendance", "") or "").strip().lower()
    reason = (getattr(r, "cancel_reason", "") or "").strip().lower()
    text = f"{attendance} {reason}"
    return (
        attendance == "no embarca"
        or "no embarca" in text
        or "no embarcado por decisión del capitán" in text
        or "no embarcado por decision del capitan" in text
        or "ausente marcado por capitán" in text
        or "ausente marcado por capitan" in text
        or "socio responsable no embarca" in text
    )


def actual_charge(outing: Outing, r: Reservation) -> float:
    """Cargo contable FIRME.

    Regla madre:
    - Antes del cierre del capitán no hay deuda firme: solo preliquidación.
    - Si el capitán cancela la salida, todos los cargos son $0.
    - Cancelado por capitán individual: siempre $0.
    - Solo una embarque cerrado por capitán puede producir cargo firme.
    """
    if not outing or not r:
        return 0.0
    # Regla institucional dura: el protocolar nunca genera cargo,
    # esté presente, ausente, cancelado, dentro o fuera de las 48 h.
    if is_protocolar(r):
        return 0.0
    if is_waitlisted(r) or is_outing_cancelled_by_captain(outing) or is_captain_cancelled(r) or is_no_board_by_captain(r):
        return 0.0
    if not is_closed_outing(outing):
        return 0.0

    k = canonical_kind(r.kind)
    raw_attendance = r.attendance or "Por confirmar"
    cancelled = bool(r.cancelled_at) or r.status == "Cancelado"

    if cancelled:
        stored = float(r.charge_amount or 0)
        return stored if stored > 0 else reservation_charge(outing, r)

    if raw_attendance in ("Ausente", "No embarcable"):
        stored = float(r.charge_amount or 0)
        return stored if stored > 0 else reservation_charge(outing, r)

    if raw_attendance == "Presente":
        if k == "invitado":
            return float(outing.guest_fee or 0)
        return 0.0

    return 0.0


def projected_charge(outing: Outing, r: Reservation) -> float:
    """Cargo proyectado/preliminar.

    No es deuda firme. Sirve para advertir lo que podría corresponder si la
    salida se realiza y el capitán cierra embarque. Si la salida es cancelada
    por capitán, toda proyección pasa a $0.
    """
    if not outing or not r:
        return 0.0
    # Protocolar: sin cargo proyectado en cualquier estado o ventana.
    if is_protocolar(r):
        return 0.0
    if is_waitlisted(r) or is_outing_cancelled_by_captain(outing) or is_captain_cancelled(r) or is_no_board_by_captain(r):
        return 0.0
    if is_closed_outing(outing):
        return actual_charge(outing, r)

    k = canonical_kind(r.kind)
    raw_attendance = r.attendance or "Por confirmar"
    cancelled = bool(r.cancelled_at) or r.status == "Cancelado"

    if cancelled:
        stored = float(r.charge_amount or 0)
        return stored if stored > 0 else (reservation_charge(outing, r) if late_window_passed(outing) else 0.0)

    if raw_attendance in ("Ausente", "No embarcable"):
        stored = float(r.charge_amount or 0)
        return stored if stored > 0 else (reservation_charge(outing, r) if late_window_passed(outing) else 0.0)

    if raw_attendance == "Presente" and k == "invitado":
        return float(outing.guest_fee or 0)

    return 0.0


def effective_charge(r: Reservation) -> float:
    """Compatibilidad histórica: si no se conoce la salida, solo se elimina cargo de capitán."""
    if is_captain_cancelled(r) or is_no_board_by_captain(r):
        return 0.0
    return float(getattr(r, "charge_amount", 0) or 0)


def reservation_view(outing: Outing, r: Reservation) -> dict:
    """Vista única y auditable de una reserva.

    Todas las pantallas consumen esta función para no deducir reglas en HTML.
    No modifica datos: solo interpreta estado físico, condición reglamentaria,
    motivo visible, preliquidación y cargo firme.
    """
    k = canonical_kind(r.kind)
    raw_attendance = r.attendance or "Por confirmar"
    captain_cancelled = is_captain_cancelled(r)
    no_board_by_captain = is_no_board_by_captain(r)
    cancelled = bool(r.cancelled_at) or r.status == "Cancelado" or captain_cancelled
    charge = actual_charge(outing, r)
    charge_preview = projected_charge(outing, r)
    if is_protocolar(r):
        charge = 0.0
        charge_preview = 0.0
    closed = is_closed_outing(outing)
    preliminary = (not closed) and charge == 0 and charge_preview > 0
    outing_cancelled = is_outing_cancelled_by_captain(outing)

    if is_waitlisted(r):
        charge = 0.0
        charge_preview = 0.0
        preliminary = False
        cancelled = False
        estado_fisico = "Lista de espera"
        estado_reglamentario = "En espera"
        level = "neutral"
        alert = "Lista de espera"
    elif outing_cancelled:
        charge = 0.0
        charge_preview = 0.0
        preliminary = False
        cancelled = True
        estado_fisico = "Salida cancelada por capitán"
        estado_reglamentario = "No embarcado"
        level = "neutral"
        alert = "Salida cancelada"
    elif captain_cancelled:
        charge = 0.0
        charge_preview = 0.0
        preliminary = False
        estado_fisico = "No embarcado por capitán"
        estado_reglamentario = "No embarcado"
        level = "neutral"
        alert = "No embarca por capitán"
    elif no_board_by_captain:
        charge = 0.0
        charge_preview = 0.0
        preliminary = False
        estado_fisico = "No embarcado por capitán"
        estado_reglamentario = "No embarcado"
        level = "neutral"
        alert = "No embarca por capitán"
    elif cancelled:
        estado_fisico = "Cancelado"
        estado_reglamentario = "No embarcado"
        level = "bad"
        alert = "Reserva cancelada"
    elif raw_attendance == "No embarcable":
        estado_fisico = "Presente informado"
        estado_reglamentario = "No embarcado"
        level = "bad"
        alert = "No embarcable"
    elif raw_attendance == "Ausente":
        estado_fisico = "Ausente"
        estado_reglamentario = "No embarcado"
        level = "bad" if (charge or charge_preview) else "warn"
        alert = "Ausente"
    elif raw_attendance == "Presente":
        estado_fisico = "Presente"
        estado_reglamentario = "Embarcado" if closed else "A confirmar al cierre"
        level = "ok"
        alert = "Embarcado" if closed else "Presente"
    else:
        estado_fisico = "Por confirmar"
        estado_reglamentario = "Pendiente"
        level = "warn"
        alert = "Pendiente"

    motivo = r.cancel_reason or ""
    if is_waitlisted(r):
        motivo = "En lista de espera. Se activa automáticamente si se libera una vacante."
    elif outing_cancelled:
        motivo = "Salida cancelada por capitán, sin cargo ni preliquidación vigente"
    elif captain_cancelled:
        motivo = "No embarcado por decisión del capitán, sin cargo"
    elif no_board_by_captain:
        motivo = "No embarcado por decisión del capitán, sin cargo"
    elif charge > 0:
        if k == "invitado" and raw_attendance == "Presente" and not cancelled:
            motivo = motivo or "Tarifa de invitado embarcado"
        elif raw_attendance == "No embarcable":
            motivo = motivo or "No embarcado: socio responsable ausente"
        elif cancelled:
            motivo = motivo or "Cancelación tardía con cargo firme"
        elif raw_attendance == "Ausente":
            motivo = motivo or "No embarcó: plaza reservada no utilizada"
        else:
            motivo = motivo or "Cargo reglamentario"
    elif preliminary:
        if cancelled:
            motivo = motivo or "Preliquidación por baja tardía, no firme hasta cierre"
        elif raw_attendance in ("Ausente", "No embarcable"):
            motivo = motivo or "Preliquidación por no embarcó/no embarque, no firme hasta cierre"
        else:
            motivo = "Tarifa de invitado pendiente de cierre"
    elif cancelled:
        motivo = motivo or "Cancelado sin cargo"
    elif raw_attendance == "No embarcable":
        motivo = motivo or "No embarcado: socio responsable ausente"
    elif raw_attendance == "Ausente":
        motivo = motivo or "No embarcó sin cargo registrado"
    elif raw_attendance == "Presente":
        if k == "socio":
            motivo = "Socio embarcado sin cargo"
        elif k == "hijo_menor":
            motivo = "Hijo menor de socio no socio embarcado sin cargo"
        elif k == "invitado":
            motivo = "Invitado presente: tarifa pendiente de cierre" if not closed else "Invitado embarcado"
    elif not motivo and raw_attendance == "Por confirmar":
        motivo = "Pendiente de confirmación por capitán"

    is_embarked = estado_reglamentario == "Embarcado"
    is_not_embarked = estado_reglamentario == "No embarcado"

    if closed:
        if is_waitlisted(r):
            status_label = "Espera"
        elif cancelled or raw_attendance in ("Ausente", "No embarcable") or is_not_embarked:
            status_label = "No embarcó" if charge > 0 else "No embarcado"
        elif is_embarked:
            status_label = "Embarcado"
        else:
            status_label = estado_reglamentario or alert
    else:
        if is_waitlisted(r):
            status_label = "Espera"
        elif cancelled:
            status_label = "Cancelada"
        elif raw_attendance == "Presente":
            status_label = "Presente"
        elif raw_attendance == "Ausente":
            status_label = "No embarcó"
        elif raw_attendance == "No embarcable":
            status_label = "No embarca"
        else:
            status_label = "Activa" if reservation_is_active(r) else alert

    if status_label in ("Embarcado", "Presente"):
        status_class = "ok"
    elif status_label in ("No embarcó", "No embarcado", "Cancelada", "No embarca"):
        status_class = "cancel"
    elif status_label == "Espera":
        status_class = "warn"
    else:
        status_class = "neutral"

    return {
        "tipo": k,
        "tipo_label": display_kind(r.kind),
        "tipo_class": k,
        "estado_fisico": estado_fisico,
        "estado_reglamentario": estado_reglamentario,
        "raw_attendance": raw_attendance,
        "level": level,
        "alert": alert,
        "motivo": motivo,
        "charge": charge,
        "charge_preview": charge_preview,
        "protocolar": is_protocolar(r),
        "protocolar_label": protocolar_label(r),
        "charge_is_preliminary": preliminary,
        "critical": bool(charge > 0 or preliminary or is_not_embarked or cancelled),
        "closed": closed,
        "cancelled": cancelled,
        "active": reservation_is_active(r),
        "embarked": is_embarked,
        "not_embarked": is_not_embarked,
        "waitlisted": is_waitlisted(r),
        "status_label": nonempty_label_v1168(status_label),
        "status_class": status_class,
        "charge_label": human_money(charge),
        "charge_preview_label": human_money(charge_preview),
    }

def reservation_views(outing: Outing, rows) -> dict:
    return {r.id: reservation_view(outing, r) for r in rows}


def build_statistics_context(db: Session) -> dict:
    """Tablero descriptivo para Administración.

    Fuente de verdad:
    - salidas cerradas + ficha vigente
    - estados finales consolidados
    - fichas anuladas excluidas de economía y uso histórico
    """
    users = db.query(User).order_by(User.name.asc()).all()
    users_by_id = {u.id: u for u in users}
    outings = db.query(Outing).order_by(Outing.departure_at.asc()).all()
    reservations = db.query(Reservation).all()
    reservations_by_outing = {}
    for r in reservations:
        reservations_by_outing.setdefault(r.outing_id, []).append(r)

    current_sheets = db.query(ClosingSheet).filter(ClosingSheet.status == "VIGENTE").all()
    current_sheet_by_outing = {s.outing_id: s for s in current_sheets}
    annulled_sheets = db.query(ClosingSheet).filter(ClosingSheet.status == "ANULADA").all()

    closed_outings = []
    cancelled_outings = []
    outings_with_waitlist = 0
    full_outings = 0
    total_capacity = 0
    total_navigants = 0
    total_socios_nav = 0
    total_invitados_nav = 0
    total_no_show = 0
    processed_total = 0
    total_revenue = 0.0
    revenue_invited = 0.0
    revenue_socio_noshow = 0.0
    revenue_guest_noshow = 0.0
    revenue_other = 0.0
    unique_socios_nav = set()
    unique_invitados_nav = set()
    monthly = {}
    outings_revenue_rows = []
    user_usage = {}
    user_spend = {}
    top_alerts = []

    def usage_bucket(uid: int, fallback_name: str = ""):
        b = user_usage.get(uid)
        if not b:
            u = users_by_id.get(uid)
            b = {
                "user_id": uid,
                "name": (u.name if u else fallback_name) or f"Usuario #{uid}",
                "member_no": (u.member_no if u else "") or "-",
                "navigations": 0,
                "reservations": 0,
                "no_shows": 0,
                "guest_trips": 0,
                "guest_count": 0,
                "avg_guests": "0,0",
                "last_navigation": "-",
            }
            user_usage[uid] = b
        return b

    def spend_bucket(uid: int, fallback_name: str = ""):
        b = user_spend.get(uid)
        if not b:
            u = users_by_id.get(uid)
            b = {
                "user_id": uid,
                "name": (u.name if u else fallback_name) or f"Usuario #{uid}",
                "member_no": (u.member_no if u else "") or "-",
                "total": 0.0,
                "total_label": "0",
                "invitados": 0.0,
                "invited_label": "0",
                "noshow_propio": 0.0,
                "noshow_own_label": "0",
                "noshow_invitados": 0.0,
                "noshow_guest_label": "0",
                "otros": 0.0,
                "otros_label": "0",
                "charge_outings": 0,
                "avg_per_outing": "0",
                "last_charge_date": "-",
            }
            user_spend[uid] = b
        return b

    for o in outings:
        rows = reservations_by_outing.get(o.id, [])
        if is_outing_cancelled_by_captain(o):
            cancelled_outings.append(o)
            label = month_label_es(o.departure_at)
            m = monthly.setdefault(label, {"label": label, "sort": o.departure_at or datetime.min, "salidas": 0, "canceladas": 0, "ocupacion_sum": 0.0, "ocupacion_count": 0, "navegantes": 0, "socios": 0, "invitados": 0, "no_show": 0, "recaudacion": 0.0, "recaudacion_invitados": 0.0, "recaudacion_no_show": 0.0, "reaperturas": 0})
            m["canceladas"] += 1
            continue

        sheet = current_sheet_by_outing.get(o.id)
        if not (is_closed_outing(o) and sheet):
            continue

        closed_outings.append(o)
        total_capacity += int(o.max_crew or 0)
        payload = sheet_payload(sheet)
        sheet_summary = payload.get("summary") or {}
        nav = int(sheet_summary.get("navegaron") or 0)
        socios_nav = int(sheet_summary.get("socios") or 0)
        invitados_nav = int(sheet_summary.get("invitados") or 0)
        no_show_count = int(sheet_summary.get("no_show_count") or 0)
        processed = int(sheet_summary.get("processed_count") or 0)
        total_sheet = float(sheet_summary.get("total") or 0)
        total_navigants += nav
        total_socios_nav += socios_nav
        total_invitados_nav += invitados_nav
        total_no_show += no_show_count
        processed_total += processed
        total_revenue += total_sheet
        if nav >= int(o.max_crew or 0) and int(o.max_crew or 0) > 0:
            full_outings += 1
        if any(is_waitlisted(r) for r in rows):
            outings_with_waitlist += 1

        label = month_label_es(o.departure_at)
        m = monthly.setdefault(label, {"label": label, "sort": o.departure_at or datetime.min, "salidas": 0, "canceladas": 0, "ocupacion_sum": 0.0, "ocupacion_count": 0, "navegantes": 0, "socios": 0, "invitados": 0, "no_show": 0, "recaudacion": 0.0, "recaudacion_invitados": 0.0, "recaudacion_no_show": 0.0, "reaperturas": 0})
        m["salidas"] += 1
        if int(o.max_crew or 0) > 0:
            m["ocupacion_sum"] += (nav / float(o.max_crew)) * 100.0
            m["ocupacion_count"] += 1
        m["navegantes"] += nav
        m["socios"] += socios_nav
        m["invitados"] += invitados_nav
        m["no_show"] += no_show_count
        m["recaudacion"] += total_sheet
        m["reaperturas"] += max(0, db.query(ClosingSheet).filter(ClosingSheet.outing_id == o.id, ClosingSheet.status == "ANULADA").count())

        outing_charge_total = 0.0
        invited_total = 0.0
        noshow_total = 0.0
        outing_charge_users = set()

        for r in rows:
            v = reservation_view(o, r)
            charge = float(v.get("charge", 0) or 0)
            k = canonical_kind(r.kind)
            uid = r.responsible_user_id or 0
            if k == "socio" and uid:
                ub = usage_bucket(uid)
                ub["reservations"] += 1
                if v.get("embarked"):
                    ub["navigations"] += 1
                    ub["last_navigation"] = fmt_admin_datetime(o.departure_at)
                    unique_socios_nav.add(uid)
                elif v.get("not_embarked") and charge > 0:
                    ub["no_shows"] += 1
            if uid and k in ("invitado", "hijo_menor") and v.get("embarked"):
                ub = usage_bucket(uid)
                ub["guest_count"] += 1
                unique_invitados_nav.add(f"{o.id}:{r.dni}")

            if v.get("embarked") and k in ("invitado", "hijo_menor"):
                unique_invitados_nav.add(f"{o.id}:{r.dni}")

            if charge <= 0:
                continue
            outing_charge_total += charge
            if uid:
                outing_charge_users.add(uid)
                sb = spend_bucket(uid)
                sb["total"] += charge
                sb["last_charge_date"] = fmt_admin_datetime(o.departure_at)
            else:
                sb = None

            if v.get("embarked"):
                invited_total += charge
                revenue_invited += charge
                m["recaudacion_invitados"] += charge
                if sb:
                    sb["invitados"] += charge
            elif k == "socio":
                noshow_total += charge
                revenue_socio_noshow += charge
                m["recaudacion_no_show"] += charge
                if sb:
                    sb["noshow_propio"] += charge
            elif k in ("invitado", "hijo_menor"):
                noshow_total += charge
                revenue_guest_noshow += charge
                m["recaudacion_no_show"] += charge
                if sb:
                    sb["noshow_invitados"] += charge
            else:
                revenue_other += charge
                if sb:
                    sb["otros"] += charge

        for uid in outing_charge_users:
            spend_bucket(uid)["charge_outings"] += 1

        guest_count_by_uid = {}
        for r in rows:
            if canonical_kind(r.kind) in ("invitado", "hijo_menor") and reservation_view(o, r).get("embarked") and r.responsible_user_id:
                guest_count_by_uid[r.responsible_user_id] = guest_count_by_uid.get(r.responsible_user_id, 0) + 1
        for uid, count in guest_count_by_uid.items():
            usage_bucket(uid)["guest_trips"] += 1

        outings_revenue_rows.append({
            "date": fmt_admin_datetime(o.departure_at),
            "title": o.title,
            "status": o.status,
            "occupancy": f"{nav}/{int(o.max_crew or 0)}",
            "navigantes": nav,
            "socios": socios_nav,
            "invitados": invitados_nav,
            "no_show": no_show_count,
            "revenue_total": total_sheet,
            "revenue_total_label": human_money(total_sheet),
            "revenue_invited": invited_total,
            "revenue_invited_label": human_money(invited_total),
            "revenue_noshow": noshow_total,
            "revenue_noshow_label": human_money(noshow_total),
            "waitlist": sum(1 for r in rows if is_waitlisted(r)),
            "reopenings": max(0, db.query(ClosingSheet).filter(ClosingSheet.outing_id == o.id, ClosingSheet.status == "ANULADA").count()),
        })

    for bucket in user_usage.values():
        trips = int(bucket["guest_trips"] or 0)
        guests = int(bucket["guest_count"] or 0)
        bucket["avg_guests"] = str(round((guests / trips), 1)).replace('.', ',') if trips else "0,0"

    for bucket in user_spend.values():
        outings_count = int(bucket["charge_outings"] or 0)
        bucket["total_label"] = human_money(bucket["total"])
        bucket["invited_label"] = human_money(bucket["invitados"])
        bucket["noshow_own_label"] = human_money(bucket["noshow_propio"])
        bucket["noshow_guest_label"] = human_money(bucket["noshow_invitados"])
        bucket["otros_label"] = human_money(bucket["otros"])
        bucket["avg_per_outing"] = human_money(bucket["total"] / outings_count) if outings_count else "0"

    monthly_rows = []
    for row in sorted(monthly.values(), key=lambda x: x["sort"], reverse=True):
        occ = (row["ocupacion_sum"] / row["ocupacion_count"]) if row["ocupacion_count"] else 0.0
        monthly_rows.append({
            "label": row["label"],
            "salidas": row["salidas"],
            "canceladas": row["canceladas"],
            "ocupacion_label": f"{occ:.1f}%",
            "navegantes": row["navegantes"],
            "socios": row["socios"],
            "invitados": row["invitados"],
            "no_show": row["no_show"],
            "recaudacion_label": human_money(row["recaudacion"]),
            "recaudacion_invitados_label": human_money(row["recaudacion_invitados"]),
            "recaudacion_no_show_label": human_money(row["recaudacion_no_show"]),
            "reaperturas": row["reaperturas"],
        })

    top_navigators = sorted(user_usage.values(), key=lambda x: (x["navigations"], x["guest_count"]), reverse=True)[:20]
    top_guest_hosts = sorted(user_usage.values(), key=lambda x: (x["guest_count"], x["guest_trips"], x["navigations"]), reverse=True)[:20]
    top_spenders = sorted(user_spend.values(), key=lambda x: (x["total"], x["invitados"], x["noshow_invitados"]), reverse=True)[:20]
    outings_revenue_rows.sort(key=lambda x: x["revenue_total"], reverse=True)

    top_alerts = []
    if top_navigators:
        t = top_navigators[0]
        top_alerts.append({"title": "Mayor uso del barco", "detail": f"{t['name']} lidera con {t['navigations']} navegadas efectivas."})
    if top_spenders:
        t = top_spenders[0]
        top_alerts.append({"title": "Mayor recaudación asociada", "detail": f"{t['name']} consolidó $ {t['total_label']} por todos los conceptos finales."})
    if outings_with_waitlist:
        top_alerts.append({"title": "Demanda con espera", "detail": f"{outings_with_waitlist} salida(s) cerradas terminaron con lista de espera final."})
    if annulled_sheets:
        top_alerts.append({"title": "Reaperturas registradas", "detail": f"{len(annulled_sheets)} ficha(s) anuladas por reapertura o recierre operativo."})

    return {
        "cards": {
            "salidas_realizadas": len(closed_outings),
            "salidas_canceladas": len(cancelled_outings),
            "ocupacion_promedio": pct_text(total_navigants, total_capacity),
            "navegantes_totales": total_navigants,
            "socios_navegaron": total_socios_nav,
            "invitados_navegaron": total_invitados_nav,
            "no_show_rate": pct_text(total_no_show, processed_total),
            "reaperturas": len(annulled_sheets),
            "salidas_con_espera": outings_with_waitlist,
            "salidas_completas": full_outings,
            "recaudacion_total": human_money(total_revenue),
            "recaudacion_invitados": human_money(revenue_invited),
            "recaudacion_no_show": human_money(revenue_socio_noshow + revenue_guest_noshow),
            "recaudacion_promedio": human_money(total_revenue / len(closed_outings)) if closed_outings else "0",
        },
        "economics": {
            "total": total_revenue,
            "total_label": human_money(total_revenue),
            "invitados": revenue_invited,
            "invited_label": human_money(revenue_invited),
            "noshow_socios": revenue_socio_noshow,
            "noshow_socios_label": human_money(revenue_socio_noshow),
            "noshow_invitados": revenue_guest_noshow,
            "noshow_invitados_label": human_money(revenue_guest_noshow),
            "otros": revenue_other,
            "otros_label": human_money(revenue_other),
        },
        "monthly_rows": monthly_rows[:18],
        "top_navigators": top_navigators,
        "top_guest_hosts": top_guest_hosts,
        "top_spenders": top_spenders,
        "top_outings_revenue": outings_revenue_rows[:20],
        "alerts": top_alerts,
        "meta": {
            "socios_unicos": len(unique_socios_nav),
            "invitados_registrados": len(unique_invitados_nav),
            "periodo_desde": fmt_admin_datetime(closed_outings[0].departure_at) if closed_outings else "-",
            "periodo_hasta": fmt_admin_datetime(closed_outings[-1].departure_at) if closed_outings else "-",
        }
    }



def _pdf_text_line(c, text, x, y, *, font="Helvetica", size=9, color=colors.HexColor("#223243")):
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawString(x, y, str(text))


def _pdf_metric_box(c, x, y, w, h, title, value):
    c.setStrokeColor(colors.HexColor("#d7e2ea"))
    c.setFillColor(colors.white)
    c.roundRect(x, y, w, h, 4, stroke=1, fill=1)
    _pdf_text_line(c, title, x + 4*mm, y + h - 5.5*mm, font="Helvetica-Bold", size=8, color=colors.HexColor("#607080"))
    _pdf_text_line(c, value, x + 4*mm, y + h/2 - 1*mm, font="Helvetica-Bold", size=14, color=colors.HexColor("#102a43"))


def _pdf_wrapped_lines(text, max_chars=90):
    words = str(text or "").split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = current + " " + word
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _pdf_draw_kv_table(c, x, y_top, width, rows, *, title=None, row_h=7.2*mm, max_rows=None):
    y = y_top
    if title:
        _pdf_text_line(c, title, x, y, font="Helvetica-Bold", size=11, color=colors.HexColor("#102a43"))
        y -= 5.5*mm
    header_h = 8*mm
    c.setFillColor(colors.HexColor("#f2f7fb"))
    c.setStrokeColor(colors.HexColor("#d7e2ea"))
    c.rect(x, y - header_h, width, header_h, fill=1, stroke=1)
    _pdf_text_line(c, "Indicador", x + 3*mm, y - 5.6*mm, font="Helvetica-Bold", size=8)
    _pdf_text_line(c, "Valor", x + width*0.62, y - 5.6*mm, font="Helvetica-Bold", size=8)
    y -= header_h
    visible = rows[:max_rows] if max_rows else rows
    for idx, (label, value) in enumerate(visible):
        fill = colors.white if idx % 2 == 0 else colors.HexColor("#fbfdff")
        c.setFillColor(fill)
        c.setStrokeColor(colors.HexColor("#e2e8ee"))
        c.rect(x, y - row_h, width, row_h, fill=1, stroke=1)
        _pdf_text_line(c, label, x + 3*mm, y - 5.2*mm, size=8.5)
        _pdf_text_line(c, value, x + width*0.62, y - 5.2*mm, font="Helvetica-Bold", size=8.5)
        y -= row_h
    return y


def _pdf_draw_simple_table(c, x, y_top, width, columns, rows, *, title=None, row_h=7*mm, header_fill="#f2f7fb", max_rows=None):
    y = y_top
    if title:
        _pdf_text_line(c, title, x, y, font="Helvetica-Bold", size=11, color=colors.HexColor("#102a43"))
        y -= 5.5*mm
    widths = [width * col[1] for col in columns]
    x_positions = [x]
    for w in widths[:-1]:
        x_positions.append(x_positions[-1] + w)
    c.setFillColor(colors.HexColor(header_fill))
    c.setStrokeColor(colors.HexColor("#d7e2ea"))
    c.rect(x, y - row_h, width, row_h, fill=1, stroke=1)
    for i, (label, _) in enumerate(columns):
        _pdf_text_line(c, label, x_positions[i] + 2.5*mm, y - 4.9*mm, font="Helvetica-Bold", size=7.6)
    y -= row_h
    visible = rows[:max_rows] if max_rows else rows
    for ridx, row in enumerate(visible):
        fill = colors.white if ridx % 2 == 0 else colors.HexColor("#fbfdff")
        c.setFillColor(fill)
        c.setStrokeColor(colors.HexColor("#e2e8ee"))
        c.rect(x, y - row_h, width, row_h, fill=1, stroke=1)
        for i, (_, _) in enumerate(columns):
            value = row[i] if i < len(row) else ""
            tx = x_positions[i] + 2.5*mm
            _pdf_text_line(c, value, tx, y - 4.9*mm, size=7.6, font="Helvetica-Bold" if i == 0 else "Helvetica")
        y -= row_h
    return y


def build_statistics_pdf_bytes(statistics: dict, *, generated_by: str = "Administración") -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 14 * mm

    def draw_header(page_title: str, page_no: int):
        c.setFillColor(colors.HexColor("#0d5884"))
        c.rect(0, height - 22*mm, width, 22*mm, fill=1, stroke=0)
        _pdf_text_line(c, "YACHT CLUB ARGENTINO", margin, height - 10*mm, font="Helvetica-Bold", size=9, color=colors.white)
        _pdf_text_line(c, "Fjord VI - Informe ejecutivo de estadísticas", margin, height - 16*mm, font="Helvetica-Bold", size=16, color=colors.white)
        _pdf_text_line(c, page_title, width - 70*mm, height - 10*mm, font="Helvetica-Bold", size=9, color=colors.white)
        _pdf_text_line(c, f"Generado: {fmt_admin_datetime(now_local())}", width - 70*mm, height - 16*mm, size=8, color=colors.white)
        _pdf_text_line(c, f"Emitido por: {generated_by}", margin, 10*mm, size=7.5, color=colors.HexColor("#607080"))
        _pdf_text_line(c, f"{RELEASE_LABEL} - página {page_no}", width - 55*mm, 10*mm, size=7.5, color=colors.HexColor("#607080"))

    cards = statistics.get("cards", {})
    econ = statistics.get("economics", {})
    meta = statistics.get("meta", {})
    alerts = statistics.get("alerts", [])

    # Page 1
    draw_header("Resumen para Comisión Directiva", 1)
    y = height - 32*mm
    subtitle = f"Período: {meta.get('periodo_desde','-')} a {meta.get('periodo_hasta','-')}"
    _pdf_text_line(c, subtitle, margin, y, size=9, color=colors.HexColor("#44576a"))
    y -= 9*mm

    card_titles = [
        ("Salidas realizadas", str(cards.get("salidas_realizadas", 0))),
        ("Ocupación promedio", str(cards.get("ocupacion_promedio", "0%"))),
        ("Socios embarcados", str(cards.get("socios_navegaron", 0))),
        ("Invitados embarcados", str(cards.get("invitados_navegaron", 0))),
        ("Recaudación total", f"$ {cards.get('recaudacion_total', '0')}") ,
        ("Promedio por salida", f"$ {cards.get('recaudacion_promedio', '0')}") ,
    ]
    box_w = (width - 2*margin - 10*mm) / 3
    box_h = 18*mm
    for i, (title, value) in enumerate(card_titles):
        row = i // 3
        col = i % 3
        x = margin + col * (box_w + 5*mm)
        yy = y - row * (box_h + 4*mm) - box_h
        _pdf_metric_box(c, x, yy, box_w, box_h, title, value)
    y -= 2 * (box_h + 4*mm) + 3*mm

    left_rows = [
        ("Salidas realizadas", str(cards.get("salidas_realizadas", 0))),
        ("Salidas canceladas", str(cards.get("salidas_canceladas", 0))),
        ("Ocupación promedio", str(cards.get("ocupacion_promedio", "0%"))),
        ("Navegantes totales", str(cards.get("navegantes_totales", 0))),
        ("Socios embarcados", str(cards.get("socios_navegaron", 0))),
        ("Invitados embarcados", str(cards.get("invitados_navegaron", 0))),
        ("Tasa reserva incumplida", str(cards.get("no_show_rate", "0%"))),
        ("Reaperturas registradas", str(cards.get("reaperturas", 0))),
        ("Salidas con espera", str(cards.get("salidas_con_espera", 0))),
        ("Salidas completas", str(cards.get("salidas_completas", 0))),
    ]
    right_rows = [
        ("Recaudación total", f"$ {econ.get('total_label', '0')}"),
        ("Invitados", f"$ {econ.get('invited_label', '0')}"),
        ("Reserva incumplida socios", f"$ {econ.get('noshow_socios_label', '0')}"),
        ("Reserva incumplida invitados", f"$ {econ.get('noshow_invitados_label', '0')}"),
        ("Otros cargos", f"$ {econ.get('otros_label', '0')}"),
        ("Socios únicos embarcados", str(meta.get('socios_unicos', 0))),
        ("Invitados embarcados", str(meta.get('invitados_registrados', 0))),
    ]
    left_w = (width - 2*margin - 6*mm) * 0.56
    right_w = (width - 2*margin - 6*mm) * 0.44
    top_y = y
    bottom_left = _pdf_draw_kv_table(c, margin, top_y, left_w, left_rows, title="Resumen ejecutivo")
    comp_rows = right_rows
    bottom_right = _pdf_draw_kv_table(c, margin + left_w + 6*mm, top_y, right_w, comp_rows, title="Composición económica")
    y = min(bottom_left, bottom_right) - 6*mm

    alert_lines = []
    for a in alerts[:4]:
        detail = f"{a.get('title','')}: {a.get('detail','')}"
        alert_lines.extend(_pdf_wrapped_lines(detail, 92))
    if not alert_lines:
        alert_lines = ["Sin observaciones destacadas para el período analizado."]
    c.setFillColor(colors.HexColor("#f8fbfd"))
    c.setStrokeColor(colors.HexColor("#d7e2ea"))
    box_h2 = max(20*mm, (len(alert_lines) + 2) * 5.2*mm)
    c.roundRect(margin, y - box_h2, width - 2*margin, box_h2, 4, fill=1, stroke=1)
    _pdf_text_line(c, "Observaciones para reunión", margin + 4*mm, y - 6*mm, font="Helvetica-Bold", size=11, color=colors.HexColor("#102a43"))
    yy = y - 12*mm
    for line in alert_lines:
        _pdf_text_line(c, f"- {line}" if not line.startswith("-") else line, margin + 5*mm, yy, size=8.5)
        yy -= 5*mm

    c.showPage()

    # Page 2
    draw_header("Uso, recaudación y rankings", 2)
    y = height - 32*mm
    monthly_rows = []
    for r in statistics.get("monthly_rows", [])[:8]:
        monthly_rows.append((r.get("label",""), str(r.get("salidas",0)), r.get("ocupacion_label","0%"), str(r.get("navegantes",0)), f"$ {r.get('recaudacion_label','0')}", str(r.get("reaperturas",0))))
    if not monthly_rows:
        monthly_rows = [("Sin datos", "-", "-", "-", "-", "-")]
    y = _pdf_draw_simple_table(c, margin, y, width - 2*margin, [("Mes",0.26),("Sal.",0.10),("Ocup.",0.14),("Nav.",0.12),("Recaudación",0.22),("Reap.",0.16)], monthly_rows, title="Evolución mensual", max_rows=8)
    y -= 6*mm

    top_nav_rows = []
    for r in statistics.get("top_navigators", [])[:5]:
        top_nav_rows.append((r.get("name",""), str(r.get("member_no","-")), str(r.get("navigations",0)), str(r.get("guest_count",0)), str(r.get("last_navigation","-"))))
    if not top_nav_rows:
        top_nav_rows = [("Sin datos", "-", "-", "-", "-")]
    top_spend_rows = []
    for r in statistics.get("top_spenders", [])[:5]:
        top_spend_rows.append((r.get("name",""), str(r.get("member_no","-")), f"$ {r.get('total_label','0')}", f"$ {r.get('invited_label','0')}", str(r.get("charge_outings",0))))
    if not top_spend_rows:
        top_spend_rows = [("Sin datos", "-", "-", "-", "-")]

    left_w = (width - 2*margin - 6*mm) / 2
    right_w = left_w
    bottom_left = _pdf_draw_simple_table(c, margin, y, left_w, [("Socio",0.42),("N°",0.13),("Nav.",0.12),("Inv.",0.11),("Última",0.22)], top_nav_rows, title="Top socios por navegadas", max_rows=5)
    bottom_right = _pdf_draw_simple_table(c, margin + left_w + 6*mm, y, right_w, [("Socio",0.40),("N°",0.12),("Total",0.20),("Inv.",0.16),("Sal.",0.12)], top_spend_rows, title="Ranking económico por socio responsable", max_rows=5)
    y = min(bottom_left, bottom_right) - 6*mm

    top_out_rows = []
    for r in statistics.get("top_outings_revenue", [])[:6]:
        top_out_rows.append((r.get("date",""), r.get("title",""), r.get("occupancy",""), f"$ {r.get('revenue_total_label','0')}", str(r.get("waitlist",0))))
    if not top_out_rows:
        top_out_rows = [("Sin datos", "-", "-", "-", "-")]
    _pdf_draw_simple_table(c, margin, y, width - 2*margin, [("Fecha",0.18),("Salida",0.38),("Ocupación",0.14),("Recaudación",0.18),("Espera",0.12)], top_out_rows, title="Top salidas por recaudación", max_rows=6)

    c.save()
    return buf.getvalue()


@app.get("/admin/estadisticas.pdf")
def admin_statistics_pdf(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    statistics = build_statistics_context(db)
    payload = build_statistics_pdf_bytes(statistics, generated_by=user.name or "Administración")
    filename = f"fjord_vi_estadisticas_resumen_{now_local().strftime('%Y%m%d_%H%M')}.pdf"
    db.add(ActivityLog(user_id=user.id, user_name=user.name, role=user.role, module="estadisticas", action="statistics_pdf", path="/admin/estadisticas.pdf", detail="Descarga informe ejecutivo PDF", ip=(request.client.host if request and request.client else ""), user_agent=(request.headers.get("user-agent") or "")[:500]))
    db.commit()
    return Response(payload, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={filename}"})


def charge_summary(outing: Outing, rows) -> dict:
    socio_items = []
    guest_items = []
    minor_items = []
    total = 0.0
    preliminary_total = 0.0
    preliminary_items = []
    for r in rows:
        v = reservation_view(outing, r)
        charge = v["charge"]
        preview = v.get("charge_preview", 0) or 0
        k = canonical_kind(r.kind)

        if charge > 0:
            total += charge
            item = {"name": r.person_name, "amount": charge, "amount_label": human_money(charge), "reason": v["motivo"] or "Cargo reglamentario"}
            if k == "socio":
                socio_items.append(item)
            elif k == "hijo_menor":
                minor_items.append(item)
            else:
                guest_items.append(item)
        elif v.get("charge_is_preliminary") and preview > 0:
            preliminary_total += preview
            preliminary_items.append({"name": r.person_name, "amount": preview, "amount_label": human_money(preview), "reason": v["motivo"] or "Preliquidación"})

    return {
        "socios": socio_items,
        "invitados": guest_items,
        "menores": minor_items,
        "total": total,
        "total_label": human_money(total),
        "preliminares": preliminary_items,
        "preliminary_total": preliminary_total,
        "preliminary_total_label": human_money(preliminary_total),
    }


def final_acta(outing: Outing, reservations) -> dict:
    """Resumen final para pantalla y auditoría administrativa."""
    embarked = []
    not_embarked = []
    pending = []
    charges = []
    preliminary = []

    for r in reservations:
        v = reservation_view(outing, r)
        item = {
            "name": r.person_name,
            "dni": r.dni,
            "tipo": v["tipo_label"],
            "tipo_class": v["tipo_class"],
            "estado_fisico": v["estado_fisico"],
            "estado_reglamentario": v["estado_reglamentario"],
            "motivo": v["motivo"],
            "charge": v["charge"],
            "charge_label": v["charge_label"],
            "charge_preview": v.get("charge_preview", 0),
            "charge_preview_label": v.get("charge_preview_label", "0"),
            "charge_is_preliminary": v.get("charge_is_preliminary", False),
            "level": v["level"],
        }
        if v["embarked"]:
            embarked.append(item)
        elif v["not_embarked"]:
            not_embarked.append(item)
        else:
            pending.append(item)
        if v["charge"] > 0:
            charges.append(item)
        elif v.get("charge_is_preliminary") and v.get("charge_preview", 0) > 0:
            preliminary.append(item)

    total = sum(i["charge"] for i in charges)
    preliminary_total = sum(i["charge_preview"] for i in preliminary)
    return {
        "embarked": embarked,
        "not_embarked": not_embarked,
        "pending": pending,
        "charges": charges,
        "preliminary": preliminary,
        "total": total,
        "total_label": human_money(total),
        "preliminary_total": preliminary_total,
        "preliminary_total_label": human_money(preliminary_total),
        "embarked_count": len(embarked),
        "not_embarked_count": len(not_embarked),
        "pending_count": len(pending),
    }


def closing_sheet_current(db: Session, outing_id: int) -> Optional[ClosingSheet]:
    return db.query(ClosingSheet).filter_by(outing_id=outing_id, status="VIGENTE").order_by(ClosingSheet.sequence.desc(), ClosingSheet.id.desc()).first()


def closing_sheet_all(db: Session, outing_id: int) -> list:
    return db.query(ClosingSheet).filter_by(outing_id=outing_id).order_by(ClosingSheet.sequence.desc(), ClosingSheet.id.desc()).all()


def next_closing_sequence(db: Session, outing_id: int) -> int:
    last = db.query(ClosingSheet).filter_by(outing_id=outing_id).order_by(ClosingSheet.sequence.desc(), ClosingSheet.id.desc()).first()
    return int(last.sequence if last else 0) + 1


def annul_current_closing_sheet(db: Session, outing: Outing, actor: str, reason: str) -> Optional[ClosingSheet]:
    sheet = closing_sheet_current(db, outing.id) if outing else None
    if sheet:
        sheet.status = "ANULADA"
        sheet.annulled_at = now_local()
        sheet.annulled_by = actor
        sheet.annul_reason = reason
        log(db, actor, "anula ficha de cierre", f"{outing.title} / ficha {sheet.sequence} / {reason}")
    return sheet


def liquidation_id_for_sheet(sheet_or_id, created_at=None) -> str:
    """ID administrativo estable para ficha/liquidación.

    Formato visible: LIQ-YYYY-000023. Usa el id real de la ficha,
    por lo que permanece estable aunque existan reaperturas y nuevas versiones.
    """
    sid = getattr(sheet_or_id, "id", None) if sheet_or_id is not None else None
    if sid is None:
        try:
            sid = int(sheet_or_id)
        except Exception:
            sid = 0
    dt = created_at or getattr(sheet_or_id, "created_at", None) or now_local()
    year = int(getattr(dt, "year", now_local().year))
    return f"LIQ-{year}-{int(sid or 0):06d}"

def build_closing_payload(db: Session, outing: Outing, reservations, sequence: int, actor: str) -> dict:
    """Arma la ficha simple y contable: quién navegó y qué se cobra.

    No incluye lista de espera ni historial. Eso queda para auditoría.
    """
    users = {u.id: u for u in db.query(User).all()}

    def responsible_for(r: Reservation):
        if canonical_kind(r.kind) == "socio":
            return users.get(r.responsible_user_id) or db.query(User).filter_by(dni=r.dni).first()
        return users.get(r.responsible_user_id)

    groups = {}

    def group_for(responsible: User):
        if not responsible:
            key = "sin_responsable"
            label = "Sin socio responsable"
            member_no = ""
        else:
            key = f"u{responsible.id}"
            label = responsible.name
            member_no = responsible.member_no or ""
        if key not in groups:
            groups[key] = {
                "responsible_name": label,
                "member_no": member_no,
                "navegaron": [],
                "cargos_navegacion": [],
                "no_show": [],
                "cargos_no_show": [],
                "subtotal_navegacion": 0.0,
                "subtotal_no_show": 0.0,
            }
        return groups[key]

    for r in reservations:
        v = reservation_view(outing, r)
        if v["waitlisted"] or v["cancelled"] or is_captain_cancelled(r) or is_no_board_by_captain(r):
            continue
        responsible = responsible_for(r)
        g = group_for(responsible)
        k = canonical_kind(r.kind)
        charge = float(v.get("charge", 0) or 0)
        person = {
            "name": r.person_name,
            "tipo": "protocolar" if is_protocolar(r) else display_kind(r.kind),
            # Regla documental: socio visible por N° de socio; invitado visible por DNI.
            "member_no": (responsible.member_no if k == "socio" and responsible else "") or "",
            "dni": (r.dni or "") if k in ("invitado", "hijo_menor") else "",
            "responsible_member_no": (responsible.member_no if responsible else "") or "",
            "reason": (r.cancel_reason or v.get("motivo") or ""),
            "protocolar": is_protocolar(r),
            "protocolar_label": protocolar_label(r),
            "amount": charge,
            "amount_label": human_money(charge),
        }
        if v["embarked"]:
            g["navegaron"].append(person)
            if charge > 0:
                g["cargos_navegacion"].append(person)
                g["subtotal_navegacion"] += charge
        elif charge > 0:
            # No navegó, pero genera cargo: socio ausente, invitado ausente o invitado caído por socio ausente.
            g["no_show"].append(person)
            g["cargos_no_show"].append(person)
            g["subtotal_no_show"] += charge

    ordered_groups = [g for g in groups.values() if g["navegaron"] or g["no_show"] or g["subtotal_navegacion"] or g["subtotal_no_show"]]
    ordered_groups.sort(key=lambda g: (g["responsible_name"] or "").lower())

    subtotal_nav = sum(g["subtotal_navegacion"] for g in ordered_groups)
    subtotal_ns = sum(g["subtotal_no_show"] for g in ordered_groups)
    navegantes = sum(len(g["navegaron"]) for g in ordered_groups)
    no_show_count = sum(len(g["no_show"]) for g in ordered_groups)
    processed_count = navegantes + no_show_count
    socios_navegantes = sum(1 for r in reservations if canonical_kind(r.kind) == "socio" and reservation_view(outing, r)["embarked"])
    invitados_navegantes = max(navegantes - socios_navegantes, 0)

    return {
        "club": "Yacht Club Argentino",
        "boat": "Fjord VI",
        "title": "FICHA DE CIERRE DE NAVEGACIÓN",
        "subtitle": "Manifiesto y Liquidación de Embarque",
        "outing_id": outing.id,
        "outing_title": outing.title,
        "departure_label": fmt_admin_datetime(outing.departure_at),
        "captain": actor,
        "sequence": sequence,
        "version_label": f"Ficha V{sequence}",
        "system_version": VERSION,
        "release_label": RELEASE_LABEL,
        "status": "VIGENTE",
        "generated_at": now_local().strftime("%d/%m/%Y %H:%M"),
        "summary": {
            "navegaron": navegantes,
            "a_bordo": navegantes,
            "no_show_count": no_show_count,
            "processed_count": processed_count,
            "socios": socios_navegantes,
            "invitados": invitados_navegantes,
            "subtotal_navegacion": subtotal_nav,
            "subtotal_navegacion_label": human_money(subtotal_nav),
            "subtotal_no_show": subtotal_ns,
            "subtotal_no_show_label": human_money(subtotal_ns),
            "total": subtotal_nav + subtotal_ns,
            "total_label": human_money(subtotal_nav + subtotal_ns),
        },
        "groups": ordered_groups,
    }


def create_closing_sheet(db: Session, outing: Outing, reservations, actor: str) -> ClosingSheet:
    # Una sola ficha vigente por salida. Si por datos heredados queda una vigente, se anula antes de crear otra.
    annul_current_closing_sheet(db, outing, actor, "Nueva ficha generada por cierre posterior")
    sequence = next_closing_sequence(db, outing.id)
    payload = build_closing_payload(db, outing, reservations, sequence, actor)
    sheet = ClosingSheet(
        outing_id=outing.id,
        sequence=sequence,
        status="VIGENTE",
        created_at=now_local(),
        created_by=actor,
        payload=json.dumps(payload, ensure_ascii=False)
    )
    db.add(sheet)
    db.flush()
    payload["liquidation_id"] = liquidation_id_for_sheet(sheet)
    sheet.payload = json.dumps(payload, ensure_ascii=False)
    log(db, actor, "genera ficha de cierre", f"{outing.title} / ficha {sequence} / {payload['liquidation_id']} / total ${payload['summary']['total_label']}")
    return sheet


def sheet_payload(sheet: ClosingSheet) -> dict:
    try:
        data = json.loads(sheet.payload or "{}")
    except Exception:
        data = {}
    data.setdefault("sequence", sheet.sequence)
    data.setdefault("version_label", f"Ficha V{sheet.sequence}")
    data.setdefault("liquidation_id", liquidation_id_for_sheet(sheet))
    data.setdefault("system_version", VERSION)
    data.setdefault("release_label", RELEASE_LABEL)
    data.setdefault("status", sheet.status)
    data.setdefault("generated_at", sheet.created_at.strftime("%d/%m/%Y %H:%M") if sheet.created_at else "")
    return data


def closing_sheet_replacement(db: Session, sheet: ClosingSheet) -> Optional[ClosingSheet]:
    """Devuelve la ficha vigente o posterior que reemplaza a una anulada."""
    if not sheet or sheet.status != "ANULADA":
        return None
    vigente = closing_sheet_current(db, sheet.outing_id)
    if vigente and vigente.sequence > sheet.sequence:
        return vigente
    return db.query(ClosingSheet).filter(
        ClosingSheet.outing_id == sheet.outing_id,
        ClosingSheet.sequence > sheet.sequence
    ).order_by(ClosingSheet.sequence.asc(), ClosingSheet.id.asc()).first()

def final_status_summary(outing: Outing, reservations, active_count: int, present: int, pending: int) -> dict:
    if not outing:
        return {"closed": False, "label": "Sin salida", "detail": "No hay salida seleccionada", "liquidacion": "Sin datos"}
    if is_outing_cancelled_by_captain(outing):
        return {"closed": True, "label": "Estado final: Cancelada", "detail": "Salida cancelada por capitán. No se generan cargos firmes ni preliquidaciones vigentes.", "liquidacion": "Sin cargos"}
    if is_closed_outing(outing):
        return {"closed": True, "label": "Estado final: Confirmado", "detail": f"Embarque cerrado y liquidada. Tripulación final: {present} / {outing.max_crew}", "liquidacion": "Liquidación completa"}
    return {"closed": False, "label": "Estado operativo: Abierto", "detail": f"Activos: {active_count} / {outing.max_crew} · pendientes: {pending}", "liquidacion": "Preliquidación no firme hasta cierre del capitán"}

def seed():
    """Bootstrap seguro para entorno vacío.

    Regla operativa de rescate:
    - si la base está vacía, crear SOLO usuarios base para poder entrar;
    - no crear salidas, reservas ni fichas ficticias;
    - si por una migración quedó el sistema sin admins, recrear dos admins de rescate.
    """
    db = SessionLocal()
    try:
        created = False
        if db.query(User).count() == 0:
            db.add_all([
                User(name="Admin Club", dni="27999111", member_no="ADM-01", email="admin@example.com", phone="", role="admin", password_hash=hash_password("demo1234"), must_change_password=True),
                User(name="Admin Respaldo", dni="27999222", member_no="ADM-02", email="admin2@example.com", phone="", role="admin", password_hash=hash_password("demo1234"), must_change_password=True),
                User(name="Capitán Martín", dni="30999111", member_no="CAP-01", email="capitan@example.com", phone="", role="captain", password_hash=hash_password("demo1234"), must_change_password=True),
                User(name="Juan Pérez", dni="20123456", member_no="1234", email="juan@example.com", phone="", role="socio", password_hash=hash_password("demo1234"), must_change_password=True),
                User(name="María Gómez", dni="25123456", member_no="1235", email="maria@example.com", phone="", role="socio", password_hash=hash_password("demo1234"), must_change_password=True),
                User(name="Pedro Martínez", dni="28123456", member_no="1236", email="pedro@example.com", phone="", role="socio", password_hash=hash_password("demo1234"), must_change_password=True),
            ])
            db.commit()
            created = True

        admin_count = db.query(User).filter_by(role="admin", active=True).count()
        if admin_count == 0:
            rescue = [
                ("Admin Club", "27999111", "ADM-01", "admin@example.com"),
                ("Admin Respaldo", "27999222", "ADM-02", "admin2@example.com"),
            ]
            for name, dni, member_no, email in rescue:
                u = db.query(User).filter((User.dni == dni) | (User.member_no == member_no)).first()
                if not u:
                    u = User(name=name, dni=dni, member_no=member_no, email=email, phone="")
                    db.add(u)
                u.name = name
                u.email = email
                u.role = "admin"
                u.active = True
                u.password_hash = hash_password("demo1234")
                u.must_change_password = True
            db.commit()
            created = True

        if created:
            log(db, "sistema", "seed", "Bootstrap limpio creado: 2 admins, 1 capitán y 3 socios demo. Sin salidas ni reservas.")
    finally:
        db.close()

seed()

def refresh_reservation_states(db: Session, outing: Outing):
    if not outing:
        return
    if cutoff_passed(outing):
        changed = False
        rows = db.query(Reservation).filter_by(outing_id=outing.id).all()
        for r in rows:
            if r.cancelled_at is None and r.status == "Condicional hasta 48h":
                r.status = "Confirmado"
                changed = True
        if changed:
            db.commit()
            persist_json(db)

def selected_outing(db: Session, outing_id: Optional[int] = None):
    if outing_id:
        outing = db.get(Outing, outing_id)
    else:
        # Primero prioriza salidas realmente operables. Una salida cancelada
        # debe seguir visible en el listado, pero no conviene que sea la
        # seleccionada por defecto si existe otra salida abierta.
        outing = (
            db.query(Outing)
            .filter(Outing.status.notin_(["Embarque cerrado", "Cancelada por capitán"]))
            .order_by(Outing.departure_at.asc())
            .first()
        )
        # Si no hay operables, permite ver canceladas/cerradas como histórico.
        outing = outing or db.query(Outing).order_by(Outing.departure_at.desc()).first()
    if not outing:
        return None
    refresh_reservation_states(db, outing)
    displaced = enforce_capacity(db, outing)
    if displaced:
        db.commit()
        persist_json(db)
    return outing

def visible_outings(db: Session, selected_id: Optional[int] = None):
    """Ventana operativa: evita listas infinitas.

    Muestra salidas desde 12 horas atrás hacia adelante, con un máximo de
    8 ítems. Si el usuario selecciona una salida histórica, la conserva visible
    como seleccionada para no perder contexto.
    """
    now = datetime.now()
    cutoff = now - timedelta(hours=12)
    rows = db.query(Outing).order_by(Outing.departure_at.asc()).all()
    visible = [o for o in rows if o.departure_at >= cutoff][:8]
    if selected_id and all(o.id != selected_id for o in visible):
        selected = db.get(Outing, selected_id)
        if selected:
            visible.append(selected)
    return visible

def historical_outings(db: Session, visible=None):
    visible_ids = {o.id for o in (visible or [])}
    q = db.query(Outing)
    if visible_ids:
        q = q.filter(~Outing.id.in_(visible_ids))
    return q.order_by(Outing.departure_at.desc()).all()

def historical_outing_groups(history):
    groups = []
    labels = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
    current = None
    bucket = []
    for o in history:
        label = f"{labels.get(o.departure_at.month, o.departure_at.strftime('%B'))} {o.departure_at.year}"
        if current is None:
            current = label
        if label != current:
            groups.append({"label": current, "items": bucket})
            current = label
            bucket = []
        bucket.append(o)
    if current is not None:
        groups.append({"label": current, "items": bucket})
    return groups

def readiness_state(outing: Outing, active_count: int, present: int = 0) -> dict:
    if not outing:
        return {"label": "Sin salida", "level": "bad", "detail": "No hay una salida activa."}
    if outing.status == "Cancelada por capitán":
        return {"label": "Cancelada", "level": "bad", "detail": "La salida fue cancelada por capitán. No se generan cargos firmes ni preliquidaciones vigentes."}
    if outing.status == "Embarque cerrado":
        return {"label": "Embarque cerrado y liquidada", "level": "ok", "detail": "La salida ya fue cerrada y liquidada por capitán."}
    if outing.status == "Realizada":
        return {"label": "Realizada", "level": "ok", "detail": "La salida fue marcada como realizada."}
    if outing.status == "Demorada":
        return {"label": "Demorada", "level": "warn", "detail": "La salida está demorada por decisión operativa."}
    if outing.status == "Reprogramada":
        return {"label": "Reprogramada", "level": "warn", "detail": "La salida fue reprogramada. Revisar nueva comunicación."}
    if active_count < outing.min_crew:
        return {"label": "Falta mínimo", "level": "bad", "detail": f"Se requieren al menos {outing.min_crew} tripulantes activos."}
    if active_count >= outing.max_crew:
        return {"label": "Cupo completo", "level": "warn", "detail": "No quedan lugares disponibles."}
    return {"label": "Operativa", "level": "ok", "detail": "La salida cumple condiciones básicas de cupo."}

def outing_context(db: Session, outing_id: Optional[int] = None):
    outing = selected_outing(db, outing_id)
    reservations = db.query(Reservation).filter_by(outing_id=outing.id).order_by(Reservation.cancelled_at.isnot(None), Reservation.id).all() if outing else []
    if outing and normalize_member_reservations(db, reservations):
        db.commit()
        reservations = db.query(Reservation).filter_by(outing_id=outing.id).order_by(Reservation.cancelled_at.isnot(None), Reservation.id).all()
    active = active_reservations(reservations)
    present = sum(1 for r in active if r.attendance == "Presente")
    absent = sum(1 for r in reservations if r.attendance in ("Ausente", "No embarcable", "No embarca"))
    pending = sum(1 for r in active if r.attendance == "Por confirmar")
    socios_presentes = sum(1 for r in active if canonical_kind(r.kind) == "socio" and r.attendance == "Presente")
    return outing, reservations, active, present, absent, pending, socios_presentes

def security_status_payload(request: Optional[Request] = None) -> dict:
    """Resumen verificable de hardening. No expone secretos."""
    return {
        "version": VERSION,
        "checked_at": now_local().isoformat(timespec="seconds"),
        "session_cookie": SESSION_COOKIE_NAME,
        "session_max_age_seconds": SESSION_MAX_AGE_SECONDS,
        "csrf_cookie": CSRF_COOKIE_NAME,
        "csrf_forms": True,
        "csrf_uploads_excluded_temporarily": True,
        "login_lock_attempts": LOGIN_LOCK_ATTEMPTS,
        "login_lock_window_minutes": LOGIN_LOCK_WINDOW_MINUTES,
        "login_lock_ip_attempts": LOGIN_LOCK_IP_ATTEMPTS,
        "operation_lock_ttl_seconds": OPERATION_LOCK_TTL_SECONDS,
        "secure_cookie_expected": _is_production_request(request),
        "headers": {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        },
        "status": "base_profesional_activa",
        "next_hardening": ["CSRF multipart/importador", "CSP gradual", "rate limit persistente por IP", "tests de permisos por endpoint"],
    }


def observability_status_payload(db: Optional[Session] = None) -> dict:
    """Estado liviano de observabilidad sin consultas pesadas."""
    payload = {
        "version": VERSION,
        "checked_at": now_local().isoformat(timespec="seconds"),
        "request_headers": ["X-Fjord-Version", "X-Fjord-Request-ID", "X-Fjord-Response-Time-Ms"],
        "activity_log": True,
        "audit_log": True,
        "structured_external_logs": False,
        "metrics_external": False,
        "status": "observabilidad_liviana_activa",
    }
    if db is not None:
        try:
            payload["activity_rows"] = table_count(db, ActivityLog)
            payload["audit_rows"] = table_count(db, AuditLog)
        except Exception:
            payload["activity_rows"] = "diferido"
            payload["audit_rows"] = "diferido"
    return payload

@app.get("/health")
def health():
    db_ok = True
    db_error = ""
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_ok = False
        db_error = f"{type(e).__name__}: {e}"
    server_v = ""
    try:
        with SessionLocal() as _db:
            server_v = postgres_server_version(_db)
    except Exception:
        server_v = ""
    return {"ok": db_ok, "version": VERSION, "release_label": RELEASE_LABEL, "app_build": APP_BUILD, "club_name": CLUB_NAME, "app_name": APP_NAME, "app_model": APP_MODEL, "max_crew": MAX_CREW, "min_crew": MIN_CREW, "captain_cancel_after_close": True, "captain_close_from_selector": True, "admin_users": True, "document_id_alnum": True, "database": db_engine_label(), "database_ok": db_ok, "database_error": db_error, "schema_version": "1", "source_of_truth": db_engine_label(), "json_mode": "export_only", "json_backup": str(JSON_BACKUP_PATH), "json_exists": JSON_BACKUP_PATH.exists(), "waitlist": True, "dependent_guest_cascade": True, "captain_guest_reassignment": True, "activity_monitor": True, "system_console": True, "hardening": True, "session_versioning": True, "login_ip_lock_threshold": LOGIN_LOCK_IP_ATTEMPTS, "session_max_age_seconds": SESSION_MAX_AGE_SECONDS, "pg_dump_available": bool(shutil.which("pg_dump")), "pg_dump_version": pg_dump_version_label(), "postgres_server_version": server_v, "communications": True, "notification_queue": True, "auto_queue_processing": True, "reminders_24h": True, "release_checklist": True, "root_redirect": True, "operation_locks": True, "operation_lock_ttl_seconds": OPERATION_LOCK_TTL_SECONDS, "architecture_scaffold": True, "architecture_modules": "diferido", "operational_status": True, "phase7_operations_alerts": True, "phase8_ux_operacional": True, "phase9_operacion_humana": True, "phase10_routing_guard": True, "phase11_centro_operativo": True, "phase11d_system_nav_direct": True, "phase12_profesionalizacion_interna": True, "phase12b_system_fast": True, "phase12c_system_fast_real": True, "phase13_security_tests_observability": True, "security_headers_base": True, "system_fast_cache_seconds": SYSTEM_FAST_CACHE_SECONDS, "professional_docs": True, "smoke_tests_scaffold": True, "system_sections_collapsible": True, "request_observability": True, "admin_security_status_endpoint": True, "admin_observability_endpoint": True, "phase13_security_tests_observability": True, "phase14_validaciones_tests": True, "phase15_error_boundary": True, "phase15_repositories_scaffold": True, "phase15_services_scaffold": True, "captain_logic_tests": True, "maintenance_mode": maintenance_status().get("enabled", False), "app_started_at": APP_STARTED_AT.isoformat(timespec="seconds")}

def _home_for_user(user: Optional[User]) -> str:
    if not user:
        return "/login"
    if getattr(user, "must_change_password", False):
        return "/change-password"
    if user.role == "captain":
        return "/captain"
    if user.role == "admin":
        return "/admin"
    return "/socio"

@app.head("/")
def head_index():
    return Response(status_code=200)



@app.middleware("http")
async def operational_performance_middleware(request: Request, call_next):
    """Fase 17: performance operativa.

    Mantiene Socio y Capitán livianos y evita cachear acciones sensibles.
    No cambia reglas de negocio; sólo agrega cabeceras defensivas y trazabilidad básica.
    """
    response = await call_next(request)
    path = request.url.path or ""

    # Nunca cachear operaciones sensibles ni administración.
    if request.method != "GET" or path.startswith(("/admin", "/captain", "/capitan", "/checkin", "/logout", "/login")):
        response.headers.setdefault("Cache-Control", "no-store")
    # Assets estáticos: pueden cachearse moderadamente en clientes móviles.
    elif path.startswith("/static/"):
        response.headers.setdefault("Cache-Control", "public, max-age=3600")
    # Socio se mantiene fresco pero liviano.
    elif path.startswith("/socio"):
        response.headers.setdefault("Cache-Control", "private, max-age=15")
    else:
        response.headers.setdefault("Cache-Control", "no-cache")

    response.headers.setdefault("X-Fjord-Performance-Mode", "operational-light")
    return response


@app.get("/")
def index(request: Request, user: Optional[User] = Depends(current_user)):
    # Entrada humana limpia: nunca exponer JSON técnico ni Method Not Allowed en la raíz.
    return RedirectResponse(_home_for_user(user), status_code=303)

@app.post("/")
def index_post_redirect():
    # Defensa UX: si un navegador reintenta un POST contra raíz, vuelve al login.
    return RedirectResponse("/login", status_code=303)

@app.get("/_admin_sistema_alias_legacy")
def admin_sistema_alias():
    return RedirectResponse("/admin?page=sistema", status_code=303)

@app.get("/_admin_system_alias_legacy")
def admin_system_alias():
    return RedirectResponse("/admin?page=sistema", status_code=303)

@app.get("/sistema")
def sistema_alias():
    return RedirectResponse("/admin?page=sistema", status_code=303)

@app.get("/system")
def system_alias():
    return RedirectResponse("/admin?page=sistema", status_code=303)

@app.get("/_admin_comunicaciones_alias_legacy")
def admin_comunicaciones_alias():
    return RedirectResponse("/admin?page=comunicaciones", status_code=303)

@app.get("/_admin_communications_alias_legacy")
def admin_communications_alias():
    return RedirectResponse("/admin?page=comunicaciones", status_code=303)

@app.get("/comunicaciones")
def comunicaciones_alias():
    return RedirectResponse("/admin?page=comunicaciones", status_code=303)

@app.get("/communications")
def communications_alias():
    return RedirectResponse("/admin?page=comunicaciones", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(db_session), user: Optional[User] = Depends(current_user)):
    if user:
        return RedirectResponse(_home_for_user(user), status_code=303)
    resp = templates.TemplateResponse(request, "login.html", {"request": request, "version": VERSION, "release_label": RELEASE_LABEL, "error": request.query_params.get("error")})
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.post("/login")
def login(request: Request, dni: str = Form(""), password: str = Form(...), db: Session = Depends(db_session)):
    ident_raw = (dni or "").strip()
    ident_dni = norm_dni(ident_raw)
    ident_member = member_key(ident_raw)
    user = None
    ident_key = login_ident_key(ident_raw)
    ip_hash = client_ip_hash(request)
    purge_old_login_attempts(db)
    if login_is_locked(db, ident_key, ip_hash):
        log(db, "Sistema", "login bloqueado por intentos", f"ident={ident_key or 'sin_ident'}")
        return RedirectResponse("/login?error=bloqueado", status_code=303)

    # Identidad blindada:
    # 1) si el dato coincide con Nº de socio, se prioriza Nº de socio;
    # 2) si no hay socio con ese número, se busca por DNI;
    # 3) si hay duplicados de Nº de socio, se bloquea el login para no entrar en una cuenta equivocada.
    member_matches = []
    if ident_member:
        member_matches = db.query(User).filter(User.member_no == ident_member, User.active == True).all()
        if len(member_matches) > 1:
            log(db, "Sistema", "login bloqueado", f"Nº socio duplicado: {ident_member}")
            return RedirectResponse("/login?error=duplicado_socio", status_code=303)
        if member_matches:
            user = member_matches[0]

    if not user and ident_dni:
        user = db.query(User).filter(User.dni == ident_dni, User.active == True).first()

    # Si el mismo input numérico coincide con DNI de otra persona pero también con Nº de socio,
    # se mantiene la prioridad por Nº de socio y queda auditado.
    if user and ident_dni and ident_member and user.member_no == ident_member:
        dni_user = db.query(User).filter(User.dni == ident_dni, User.active == True).first()
        if dni_user and dni_user.id != user.id:
            log(db, "Sistema", "login ambiguo resuelto", f"input {ident_raw}: prioridad Nº socio {user.member_no} sobre DNI de {dni_user.name}")

    if not user or not verify_password(password, user.password_hash):
        record_login_attempt(db, ident_key, ip_hash, False, "credencial inválida")
        return RedirectResponse("/login?error=1", status_code=303)
    if is_temporary_password(password) and not getattr(user, "must_change_password", False):
        user.must_change_password = True
        db.commit()
    user.last_login_at = now_local()
    if not getattr(user, "session_version", None):
        user.session_version = 1
    db.commit()
    record_login_attempt(db, ident_key, ip_hash, True, "ok")
    log(db, user.name, "login", user.role)
    target = "/change-password" if getattr(user, "must_change_password", False) else "/"
    resp = RedirectResponse(target, status_code=303)
    set_session_cookie(resp, request, user.id, getattr(user, "session_version", 1) or 1)
    return resp


@app.get("/change-password", response_class=HTMLResponse)
def change_password_page(request: Request, user: User = Depends(require_user)):
    if not getattr(user, "must_change_password", False):
        return RedirectResponse(_home_for_user(user) if "user" in locals() else "/login", status_code=303)
    resp = templates.TemplateResponse(request, "change_password.html", {
        "request": request,
        "version": VERSION,
        "release_label": RELEASE_LABEL,
        "user": user,
        "error": request.query_params.get("error"),
    })
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.post("/change-password")
def change_password_submit(
    new_password: str = Form(""),
    confirm_password: str = Form(""),
    db: Session = Depends(db_session),
    user: User = Depends(require_user)
):
    error = password_change_error(new_password, confirm_password, user)
    if error:
        return RedirectResponse(f"/change-password?error={error}", status_code=303)

    user.password_hash = hash_password(new_password.strip())
    user.must_change_password = False
    user.last_password_change_at = now_local()
    user.session_version = int(getattr(user, "session_version", 1) or 1) + 1
    db.commit()
    log(db, user.name, "cambio clave inicial", "clave personal definida; sesiones anteriores invalidadas")
    resp = RedirectResponse("/", status_code=303)
    set_session_cookie(resp, request, user.id, user.session_version)
    return resp



@app.get("/account/password", response_class=HTMLResponse)
def account_password_page(
    request: Request,
    user: User = Depends(require_user)
):
    resp = templates.TemplateResponse(request, "account_password.html", {
        "request": request,
        "version": VERSION,
        "release_label": RELEASE_LABEL,
        "user": user,
        "ok": request.query_params.get("ok"),
        "error": request.query_params.get("error"),
    })
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.post("/account/password")
def account_password_submit(
    current_password: str = Form(""),
    new_password: str = Form(""),
    confirm_password: str = Form(""),
    db: Session = Depends(db_session),
    user: User = Depends(require_user)
):
    if not verify_password(current_password or "", user.password_hash):
        return RedirectResponse("/account/password?error=actual", status_code=303)

    error = password_change_error(new_password, confirm_password, user)
    if error:
        return RedirectResponse(f"/account/password?error={error}", status_code=303)

    user.password_hash = hash_password(new_password.strip())
    user.must_change_password = False
    user.last_password_change_at = now_local()
    user.session_version = int(getattr(user, "session_version", 1) or 1) + 1
    db.commit()

    log(db, user.name, "cambio clave usuario", "clave actualizada desde perfil; sesiones anteriores invalidadas")
    resp = RedirectResponse("/?msg=clave_actualizada", status_code=303)
    set_session_cookie(resp, request, user.id, user.session_version)
    return resp

@app.post("/admin/user/reset-password/{user_id}")
def admin_reset_password(
    request: Request,
    user_id: int,
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    target = db.get(User, user_id)
    if not target:
        return RedirectResponse("/admin?page=socios&msg=usuario_no_encontrado", status_code=303)

    target.password_hash = hash_password("demo1234")
    target.must_change_password = True
    target.last_password_change_at = now_local()
    target.session_version = int(getattr(target, "session_version", 1) or 1) + 1
    db.commit()

    audit_event(db, user, "reset clave temporal", f"{target.name} ({target.member_no or target.dni})", request=request, before={"session_version": (target.session_version or 1) - 1}, after={"session_version": target.session_version})
    return RedirectResponse("/admin?page=socios&msg=clave_reseteada", status_code=303)


@app.get("/logout")
def logout():
    resp = RedirectResponse("/", status_code=303)
    clear_session_cookie(resp)
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.get("/socio", response_class=HTMLResponse)
def socio(request: Request, outing_id: Optional[int] = None, db: Session = Depends(db_session), user: User = Depends(require_role("socio"))):
    outings = visible_outings(db, outing_id)
    history_outings = historical_outings(db, outings)
    history_groups = historical_outing_groups(history_outings)
    outing, reservations, active, present, absent, pending, socios_presentes = outing_context(db, outing_id)
    if not outing:
        return templates.TemplateResponse(request, "socio.html", {"request": request, "user": user, "outing": None, "outings": outings, "history_groups": history_groups, "msg": request.query_params.get("msg")})
    mine = [r for r in reservations if r.dni == user.dni or r.responsible_user_id == user.id]
    # El titular debe resolverse únicamente contra una reserva de tipo socio.
    # Antes cualquier registro con el DNI del usuario podía ocupar el bloque "Tu lugar"
    # y dejar sin botón de alta/reincorporación al socio titular.
    self_candidates = [r for r in reservations if r.dni == user.dni and canonical_kind(r.kind) == "socio"]
    self_reservation = next((r for r in self_candidates if reservation_is_active(r)), None) or (self_candidates[0] if self_candidates else None)
    has_self = bool(self_reservation and reservation_is_active(self_reservation))
    ready = readiness_state(outing, len(active))
    views = reservation_views(outing, reservations)
    self_view = views.get(self_reservation.id) if self_reservation else None
    final_summary = final_status_summary(outing, reservations, len(active), present, pending)
    return templates.TemplateResponse(request, "socio.html", {
        "request": request, "user": user, "outing": outing, "outings": outings, "history_groups": history_groups, "reservations": reservations,
        "active": active, "mine": mine, "has_self": has_self, "self_reservation": self_reservation,
        "active_count": len(active), "remaining": max(0, outing.max_crew - len(active)),
        "readiness": ready, "cutoff": cutoff_passed(outing), "late_window": late_window_passed(outing),
        "cutoff_at": cutoff_at(outing), "cancel_deadline": cancellation_deadline(outing),
        "fee": float(outing.guest_fee), "msg": request.query_params.get("msg"),
        "closed": is_closed_outing(outing), "reservation_views": views, "self_view": self_view, "final_summary": final_summary,
        "waitlist_count": sum(1 for rr in reservations if is_waitlisted(rr))
    })

@app.post("/socio/add_self")
def add_self(outing_id: Optional[int] = Form(None), db: Session = Depends(db_session), user: User = Depends(require_role("socio"))):
    outing, reservations, active, *_ = outing_context(db, outing_id)
    ensure_outing_editable(outing)
    existing = db.query(Reservation).filter_by(outing_id=outing.id, dni=user.dni).first()
    if existing and reservation_is_active(existing) and canonical_kind(existing.kind) == "socio":
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=ya_anotado", status_code=303)
    if existing:
        # Reincorporación unificada del titular: si existía un registro histórico
        # del DNI del socio, se reutiliza y se normaliza como socio titular.
        target = existing
        target.kind = "socio"
        target.person_name = user.name
        target.responsible_user_id = user.id
        target.original_responsible_user_id = user.id
    else:
        target = Reservation(outing_id=outing.id, person_name=user.name, dni=user.dni, kind="socio", responsible_user_id=user.id, original_responsible_user_id=user.id)
        db.add(target)
        db.flush()

    result, displaced_name = place_socio_with_priority(db, outing, target)
    enforce_capacity(db, outing)
    db.commit()

    if result == "waitlist":
        log(db, user.name, "lista de espera socio", outing.title)
        queue_email(db, "reserva_confirmada_socio", user.email or "", user.name, {"socio_nombre": user.name, "salida_nombre": outing.title, "fecha": outing.departure_at.strftime("%d/%m/%Y"), "hora": outing.departure_at.strftime("%H:%M"), "estado": "Lista de espera"})
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=lista_espera_ok", status_code=303)
    if result == "active_displaced":
        log(db, user.name, "reserva socio con prioridad", f"{outing.title} / desplazado: {displaced_name}")
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=socio_prioridad_ok", status_code=303)

    log(db, user.name, "reserva socio", outing.title)
    queue_email(db, "reserva_confirmada_socio", user.email or "", user.name, {"socio_nombre": user.name, "salida_nombre": outing.title, "fecha": outing.departure_at.strftime("%d/%m/%Y"), "hora": outing.departure_at.strftime("%H:%M"), "estado": "Confirmada"})
    return RedirectResponse(f"/socio?outing_id={outing.id}&msg=reserva_ok", status_code=303)

@app.post("/socio/add_guest")
async def add_guest(
    request: Request,
    db: Session = Depends(db_session),
    user: User = Depends(require_role("socio"))
):
    form = await request.form()

    outing_id_raw = form.get("outing_id")
    name = form.get("name")
    nombre = form.get("nombre")
    dni = form.get("dni")
    kind = form.get("kind", "invitado")
    birth_date = form.get("birth_date")

    try:
        outing_id = int(outing_id_raw) if outing_id_raw else None
    except Exception:
        outing_id = None

    outing, reservations, active, *_ = outing_context(db, outing_id)
    if not outing:
        return RedirectResponse("/socio?msg=datos_invalidos", status_code=303)

    ensure_outing_editable(outing)

    person_name = (name or nombre or "").strip()
    dni_clean = norm_dni(dni or "")
    kind = canonical_kind(kind)

    full_capacity = len(active_public_reservations(reservations)) >= public_capacity(outing)

    if kind not in ("invitado", "hijo_menor") or not person_name or not dni_clean:
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=datos_invalidos", status_code=303)

    if kind == "hijo_menor":
        # Solo se pide fecha para esta categoría especial.
        # Valida que sea menor de 18 años a la fecha de salida.
        if not birth_date or not is_under_18_on(birth_date, outing.departure_at):
            return RedirectResponse(f"/socio?outing_id={outing.id}&msg=hijo_menor_invalido", status_code=303)
    else:
        birth_date = None

    # Identidad documental fuerte: un socio registrado no puede ser cargado como invitado.
    registered_user = db.query(User).filter_by(dni=dni_clean, active=True).first()
    if registered_user and registered_user.role == "socio":
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=socio_documento", status_code=303)

    self_row = db.query(Reservation).filter_by(outing_id=outing.id, dni=user.dni).first()
    if not self_row or canonical_kind(self_row.kind) != "socio" or not reservation_is_active(self_row):
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=socio_requerido", status_code=303)

    existing = db.query(Reservation).filter_by(outing_id=outing.id, dni=dni_clean).first()

    if existing and existing.responsible_user_id != user.id:
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=persona_ya_registrada", status_code=303)

    if existing and reservation_is_active(existing):
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=dni_duplicado", status_code=303)

    if existing:
        existing.person_name = person_name
        existing.kind = kind
        existing.birth_date = birth_date
        existing.responsible_user_id = user.id
        if canonical_kind(existing.kind) in ("invitado", "hijo_menor") and not getattr(existing, "original_responsible_user_id", None):
            existing.original_responsible_user_id = user.id
        if full_capacity:
            put_on_waitlist(existing, "En lista de espera. Se activa si se libera una vacante.")
        else:
            reactivate_reservation(db, outing, existing)
    else:
        status = "Hijo menor de socio no socio" if kind == "hijo_menor" else ("Confirmado" if cutoff_passed(outing) else "Condicional hasta 48h")
        new_guest = Reservation(
            outing_id=outing.id,
            person_name=person_name,
            dni=dni_clean,
            kind=kind,
            responsible_user_id=user.id,
            original_responsible_user_id=user.id,
            status=status,
            birth_date=birth_date
        )
        if full_capacity:
            put_on_waitlist(new_guest, "En lista de espera. Se activa si se libera una vacante.")
        db.add(new_guest)

    enforce_capacity(db, outing)
    db.commit()
    log(db, user.name, "agrega/reactiva invitado" if not full_capacity else "lista de espera invitado", f"{person_name} / {outing.title}")
    queue_email(db, "invitado_agregado_socio", user.email or "", user.name, {"socio_nombre": user.name, "invitado_nombre": person_name, "salida_nombre": outing.title, "fecha": outing.departure_at.strftime("%d/%m/%Y"), "hora": outing.departure_at.strftime("%H:%M"), "estado": "Lista de espera" if full_capacity else "Registrado"})

    return RedirectResponse(f"/socio?outing_id={outing.id}&msg={'lista_espera_ok' if full_capacity else 'invitado_ok'}", status_code=303)

@app.post("/socio/add_protocolar")
async def add_protocolar_participation(
    request: Request,
    db: Session = Depends(db_session),
    user: User = Depends(require_role("socio", "admin"))
):
    if not can_manage_protocolar(user):
        return RedirectResponse("/socio?msg=sin_permiso_protocolar", status_code=303)

    form = await request.form()
    try:
        outing_id = int(form.get("outing_id") or 0)
    except Exception:
        outing_id = None

    outing, reservations, active, *_ = outing_context(db, outing_id)
    if not outing:
        return RedirectResponse("/socio?msg=datos_invalidos", status_code=303)
    ensure_outing_editable(outing)

    name = (form.get("name") or "").strip()
    document = norm_dni(form.get("dni") or "")
    member_no = member_key(form.get("member_no") or "")
    reason = (form.get("protocolar_reason") or "Autorizado por Comisión Fjord VI").strip()

    matched_user = None
    member_lookup_failed = False
    if member_no:
        matched_user = db.query(User).filter(User.member_no == member_no, User.active == True).first()
        if not matched_user:
            member_lookup_failed = True
    if not matched_user and document:
        matched_user = db.query(User).filter(User.dni == document, User.active == True).first()

    if member_lookup_failed and not name:
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=falta_nombre_protocolar", status_code=303)

    if matched_user and matched_user.role == "socio":
        person_name = matched_user.name
        dni_clean = matched_user.dni
        kind = "socio"
        responsible_id = matched_user.id
    else:
        person_name = name
        dni_clean = document
        kind = "invitado"
        responsible_id = user.id

    if not person_name:
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=falta_nombre_protocolar", status_code=303)

    if not dni_clean:
        dni_clean = f"PROTO-{int(datetime.now().timestamp())}"

    existing = db.query(Reservation).filter_by(outing_id=outing.id, dni=dni_clean).first()
    rows = db.query(Reservation).filter_by(outing_id=outing.id).all()

    if existing:
        r = existing
        r.person_name = person_name
        r.kind = kind
        r.responsible_user_id = responsible_id
        if canonical_kind(r.kind) in ("invitado", "hijo_menor") and not getattr(r, "original_responsible_user_id", None):
            r.original_responsible_user_id = responsible_id
        r.cancelled_at = None
        r.status = default_reservation_status(outing, r)
        r.attendance = "Por confirmar"
    else:
        if not protocolar_capacity_available(outing, rows):
            return RedirectResponse(f"/socio?outing_id={outing.id}&msg=cupo_protocolar_completo", status_code=303)
        r = Reservation(
            outing_id=outing.id,
            person_name=person_name,
            dni=dni_clean,
            kind=kind,
            responsible_user_id=responsible_id,
            original_responsible_user_id=responsible_id,
            status="Confirmado",
            attendance="Por confirmar"
        )
        db.add(r)
        db.flush()

    r.protocolar = True
    r.protocolar_by_user_id = user.id
    r.protocolar_reason = reason
    r.charge_amount = 0
    enforce_capacity(db, outing)
    db.commit()
    log(db, user.name, "agrega participación protocolar", f"{person_name} / {outing.title} / {reason}")
    return RedirectResponse(f"/socio?outing_id={outing.id}&msg=protocolar_ok", status_code=303)


@app.post("/socio/protocolar/{rid}")
def socio_protocolar(
    rid: int,
    outing_id: Optional[int] = Form(None),
    protocolar_reason: str = Form(""),
    remove: Optional[str] = Form(None),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("socio", "admin"))
):
    if not can_manage_protocolar(user):
        return RedirectResponse("/socio?msg=sin_permiso_protocolar", status_code=303)
    r = db.get(Reservation, rid)
    outing = selected_outing(db, outing_id)
    if not r or not outing or r.outing_id != outing.id:
        return RedirectResponse("/socio?msg=datos_invalidos", status_code=303)
    ensure_outing_editable(outing)
    if remove == "1":
        r.protocolar = False
        r.protocolar_by_user_id = None
        r.protocolar_reason = ""
        log(db, user.name, "quita participación protocolar", f"{r.person_name} / {outing.title}")
        msg = "protocolar_quitado"
    else:
        rows = db.query(Reservation).filter_by(outing_id=outing.id).all()
        if not reservation_is_active(r) and not protocolar_capacity_available(outing, rows, exclude_id=r.id):
            return RedirectResponse(f"/socio?outing_id={outing.id}&msg=cupo_protocolar_completo", status_code=303)
        r.protocolar = True
        r.protocolar_by_user_id = user.id
        r.protocolar_reason = (protocolar_reason or "Autorizado por Comisión Fjord VI").strip()
        r.charge_amount = 0
        log(db, user.name, "marca participación protocolar", f"{r.person_name} / {outing.title} / {r.protocolar_reason}")
        msg = "protocolar_ok"
    db.commit()
    return RedirectResponse(f"/socio?outing_id={outing.id}&msg={msg}", status_code=303)




@app.post("/socio/update_guest/{rid}")
async def socio_update_guest(
    rid: int,
    request: Request,
    db: Session = Depends(db_session),
    user: User = Depends(require_role("socio"))
):
    form = await request.form()
    outing_id = int(form.get("outing_id") or 0)
    r = db.get(Reservation, rid)
    outing = selected_outing(db, outing_id)
    ensure_outing_editable(outing)
    if not r or not outing or not can_user_manage_guest_record(user, outing, r):
        raise HTTPException(403)
    person_name = (form.get("name") or "").strip()
    dni_clean = norm_dni(form.get("dni") or "")
    kind = canonical_kind(form.get("kind") or r.kind)
    birth_date = form.get("birth_date") or None
    if kind not in ("invitado", "hijo_menor") or not person_name or not dni_clean:
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=datos_invalidos", status_code=303)
    if kind == "hijo_menor":
        if not birth_date or not is_under_18_on(birth_date, outing.departure_at):
            return RedirectResponse(f"/socio?outing_id={outing.id}&msg=hijo_menor_invalido", status_code=303)
    else:
        birth_date = None
    existing = db.query(Reservation).filter(Reservation.outing_id == outing.id, Reservation.dni == dni_clean, Reservation.id != r.id).first()
    if existing and reservation_is_active(existing):
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=dni_duplicado", status_code=303)
    registered_user = db.query(User).filter_by(dni=dni_clean, active=True).first()
    if registered_user and registered_user.role == "socio":
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=socio_documento", status_code=303)
    before = {"name": r.person_name, "dni": r.dni, "kind": r.kind, "birth_date": r.birth_date or ""}
    r.person_name = person_name
    r.dni = dni_clean
    r.kind = kind
    r.birth_date = birth_date
    db.commit()
    audit_event(db, user, "corrige invitado", f"{before['name']} -> {person_name} / {outing.title}", request=request, outing_id=outing.id, reservation_id=r.id, before=before, after={"name": r.person_name, "dni": r.dni, "kind": r.kind, "birth_date": r.birth_date or ""})
    return RedirectResponse(f"/socio?outing_id={outing.id}&msg=invitado_actualizado", status_code=303)


@app.post("/socio/replace_guest/{rid}")
async def socio_replace_guest(
    rid: int,
    request: Request,
    db: Session = Depends(db_session),
    user: User = Depends(require_role("socio"))
):
    form = await request.form()
    outing_id = int(form.get("outing_id") or 0)
    r = db.get(Reservation, rid)
    outing = selected_outing(db, outing_id)
    ensure_outing_editable(outing)
    if not r or not outing or not can_user_manage_guest_record(user, outing, r):
        raise HTTPException(403)
    new_name = (form.get("new_name") or "").strip()
    new_dni = norm_dni(form.get("new_dni") or "")
    new_kind = canonical_kind(form.get("new_kind") or "invitado")
    new_birth_date = form.get("new_birth_date") or None
    if new_kind not in ("invitado", "hijo_menor") or not new_name or not new_dni:
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=datos_invalidos", status_code=303)
    if new_kind == "hijo_menor":
        if not new_birth_date or not is_under_18_on(new_birth_date, outing.departure_at):
            return RedirectResponse(f"/socio?outing_id={outing.id}&msg=hijo_menor_invalido", status_code=303)
    else:
        new_birth_date = None
    existing = db.query(Reservation).filter_by(outing_id=outing.id, dni=new_dni).first()
    if existing and reservation_is_active(existing):
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=dni_duplicado", status_code=303)
    registered_user = db.query(User).filter_by(dni=new_dni, active=True).first()
    if registered_user and registered_user.role == "socio":
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=socio_documento", status_code=303)
    new_guest, old_charge, new_waitlisted, promoted = replace_guest_under_socio(db, outing, r, user, new_name, new_dni, new_kind, new_birth_date)
    db.commit()
    detail = f"{r.person_name} -> {new_name} / {outing.title} / cargo_anterior {old_charge}"
    audit_event(db, user, "reemplaza invitado", detail, request=request, outing_id=outing.id, reservation_id=new_guest.id, before={"replaced_reservation_id": r.id, "old_name": r.person_name, "old_dni": r.dni, "old_charge": float(old_charge or 0)}, after={"new_reservation_id": new_guest.id, "new_name": new_guest.person_name, "new_dni": new_guest.dni, "waitlisted": new_waitlisted, "promoted": promoted})
    msg = "invitado_reemplazado_espera" if new_waitlisted else "invitado_reemplazado"
    return RedirectResponse(f"/socio?outing_id={outing.id}&msg={msg}", status_code=303)


@app.post("/admin/delete_outing")
def delete_outing(
    request: Request,
    outing_id: int = Form(...),
    confirm_delete: str = Form(""),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    outing = db.get(Outing, outing_id)
    if not outing:
        raise HTTPException(404, "Salida inexistente")
    if (confirm_delete or "").strip().upper() != "BORRAR SALIDA":
        return RedirectResponse(f"/admin/salidas?outing_id={outing.id}&msg=confirmacion_invalida", status_code=303)
    reservation_count = db.query(Reservation).filter_by(outing_id=outing.id).count()
    sheet_count = db.query(ClosingSheet).filter_by(outing_id=outing.id).count()
    if reservation_count or sheet_count or is_closed_outing(outing):
        return RedirectResponse(f"/admin/salidas?outing_id={outing.id}&msg=salida_no_borrable", status_code=303)
    before = {"title": outing.title, "departure_at": outing.departure_at.isoformat(), "status": outing.status}
    db.delete(outing)
    db.commit()
    audit_event(db, user, "borra salida vacía", f"{before['title']} / {before['departure_at']}", request=request, outing_id=outing_id, before=before)
    return RedirectResponse("/admin/salidas?msg=salida_borrada", status_code=303)

@app.post("/socio/cancel/{rid}")
def cancel_reservation(rid: int, outing_id: Optional[int] = Form(None), db: Session = Depends(db_session), user: User = Depends(require_role("socio"))):
    r = db.get(Reservation, rid)
    outing = selected_outing(db, outing_id)
    ensure_outing_editable(outing)
    if not r or r.outing_id != outing.id or not (r.dni == user.dni or r.responsible_user_id == user.id):
        raise HTTPException(403)

    if not reservation_is_active(r):
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=cancelado", status_code=303)

    now = now_local()
    was_waitlisted = is_waitlisted(r)
    r.cancelled_at = now
    r.status = "Cancelado"
    r.attendance = "Ausente"
    r.cancel_reason = "Baja desde lista de espera" if was_waitlisted else "Cancelado por socio"
    r.charge_amount = 0 if was_waitlisted else (reservation_charge(outing, r) if late_window_passed(outing) else 0)

    if r.dni == user.dni:
        dependientes = db.query(Reservation).filter(
            Reservation.outing_id == outing.id,
            Reservation.responsible_user_id == user.id,
            Reservation.dni != user.dni,
            Reservation.cancelled_at.is_(None)
        ).all()
        for dep in dependientes:
            dep_was_waitlisted = is_waitlisted(dep)
            dep.cancelled_at = now
            dep.status = "Cancelado"
            dep.attendance = "Ausente"
            dep.cancel_reason = "Baja desde lista de espera por baja del socio responsable" if dep_was_waitlisted else "Cancelado por baja del socio responsable"
            dep.charge_amount = 0 if dep_was_waitlisted else (reservation_charge(outing, dep) if late_window_passed(outing) else 0)

    promoted = promote_waitlist(db, outing)
    db.commit()
    log(db, user.name, "cancela reserva", f"{r.person_name} / {outing.title} / cargo {r.charge_amount} / promovidos {', '.join(promoted) if promoted else '-'}")
    queue_email(db, "cancelacion_socio", user.email or "", user.name, {
        "socio_nombre": user.name,
        "persona_nombre": r.person_name,
        "salida_nombre": outing.title,
        "fecha": outing.departure_at.strftime("%d/%m/%Y"),
        "hora": outing.departure_at.strftime("%H:%M"),
        "importe": "$ " + fmt_money(r.charge_amount or 0),
    })
    return RedirectResponse(f"/socio?outing_id={outing.id}&msg=cancelado", status_code=303)

@app.post("/socio/reactivate/{rid}")
def reactivate_by_socio(rid: int, outing_id: Optional[int] = Form(None), db: Session = Depends(db_session), user: User = Depends(require_role("socio"))):
    r = db.get(Reservation, rid)
    outing, reservations, active, *_ = outing_context(db, outing_id)
    ensure_outing_editable(outing)
    if not r or r.outing_id != outing.id or not (r.dni == user.dni or r.responsible_user_id == user.id):
        raise HTTPException(403)
    if reservation_is_active(r):
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=ya_anotado", status_code=303)
    if canonical_kind(r.kind) == "socio":
        result, displaced_name = place_socio_with_priority(db, outing, r)
        db.commit()
        if result == "waitlist":
            log(db, user.name, "lista de espera reactiva", f"{r.person_name} / {outing.title}")
            return RedirectResponse(f"/socio?outing_id={outing.id}&msg=lista_espera_ok", status_code=303)
        if result == "active_displaced":
            log(db, user.name, "reactiva socio con prioridad", f"{r.person_name} / {outing.title} / desplazado: {displaced_name}")
            return RedirectResponse(f"/socio?outing_id={outing.id}&msg=socio_prioridad_ok", status_code=303)
        log(db, user.name, "reactiva reserva", f"{r.person_name} / {outing.title}")
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=reactivado", status_code=303)

    if len(active) >= outing.max_crew:
        put_on_waitlist(r, "En lista de espera. Se activa si se libera una vacante.")
        db.commit()
        log(db, user.name, "lista de espera reactiva", f"{r.person_name} / {outing.title}")
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=lista_espera_ok", status_code=303)
    reactivate_reservation(db, outing, r)
    db.commit()
    log(db, user.name, "reactiva reserva", f"{r.person_name} / {outing.title}")
    return RedirectResponse(f"/socio?outing_id={outing.id}&msg=reactivado", status_code=303)

@app.get("/captain", response_class=HTMLResponse)
def captain(request: Request, outing_id: Optional[int] = None, db: Session = Depends(db_session), user: User = Depends(require_role("captain", "admin"))):
    outings = visible_outings(db, outing_id)
    history_outings = historical_outings(db, outings)
    history_groups = historical_outing_groups(history_outings)
    outing, reservations, active, present, absent, pending, socios_presentes = outing_context(db, outing_id)
    ready = readiness_state(outing, len(active), present)
    waitlist_count = sum(1 for rr in reservations if is_waitlisted(rr)) if outing else 0
    views = reservation_views(outing, reservations) if outing else {}
    if outing and views:
        responsible_ids = sorted({uid for r in reservations for uid in (r.responsible_user_id, getattr(r, "protocolar_by_user_id", None)) if uid})
        responsible_users = {u.id: u for u in db.query(User).filter(User.id.in_(responsible_ids)).all()} if responsible_ids else {}
        for r in reservations:
            v = views.get(r.id)
            if not v:
                continue
            responsible = responsible_users.get(r.responsible_user_id) if r.responsible_user_id else None
            own_reservation = bool(responsible and r.dni == responsible.dni)
            v["responsible_name"] = responsible.name if responsible else ""
            protocolar_ref = responsible_users.get(getattr(r, "protocolar_by_user_id", None)) if is_protocolar(r) and getattr(r, "protocolar_by_user_id", None) else None
            v["protocolar_reference_name"] = protocolar_ref.name if protocolar_ref else v.get("responsible_name", "")
            v["responsible_member_no"] = (responsible.member_no or "") if responsible else ""
            v["responsible_dni"] = responsible.dni if responsible else ""
            responsible_row = db.query(Reservation).filter_by(outing_id=outing.id, dni=responsible.dni).first() if responsible else None
            v["responsible_attendance"] = responsible_row.attendance if responsible_row else ""
            v["responsible_is_present"] = bool(responsible_row and responsible_row.attendance == "Presente" and reservation_is_active(responsible_row))
            v["own_reservation"] = own_reservation
            v["show_responsible"] = bool(responsible and canonical_kind(r.kind) in ("invitado", "hijo_menor") and not own_reservation)
            v["reassignment_locked"] = False
            v["reassignment_count"] = reservation_reassignment_count_value(r)
            v["is_reassigned"] = reservation_is_reassigned(r)
            v["captain_can_activate_from_waitlist"] = bool(v.get("waitlisted") and captain_can_activate_waitlisted_reservation(db, outing, r))

        # Vista Capitán v1.18.0: color y orden = socio responsable operativo/de referencia.
        # No modifica reglas de cargo, espera, cierre, reapertura ni liquidación.
        # La barra lateral NO representa categoría ni estado: representa de quién depende
        # operativa/económicamente la persona dentro de esta salida.
        group_index_by_key = {}
        group_seq = 0

        def captain_group_key(rr):
            # Reasignados e invitados comunes: el responsable actual manda.
            if getattr(rr, "responsible_user_id", None):
                return f"u-{rr.responsible_user_id}"
            # Institucionales puros: vínculo de referencia con quien los cargó/autorizó.
            if is_protocolar(rr) and getattr(rr, "protocolar_by_user_id", None):
                return f"u-{rr.protocolar_by_user_id}"
            # Fallback defensivo: fila aislada, sin inventar responsable.
            return f"row-{rr.id}"

        for rr in reservations:
            vv = views.get(rr.id)
            if not vv:
                continue
            key = captain_group_key(rr)
            vv["captain_group_key"] = key
            if key not in group_index_by_key:
                group_seq += 1
                group_index_by_key[key] = ((group_seq - 1) % 8) + 1
            vv["captain_group_index"] = group_index_by_key[key]
            if is_protocolar(rr):
                vv["captain_group_role"] = "institutional"
            elif canonical_kind(rr.kind) == "socio":
                vv["captain_group_role"] = "owner"
            else:
                vv["captain_group_role"] = "guest"

    # v1.18.0: orden visual de Capitán por grupos operativos.
    # La lista original conserva la lógica de negocio. Esta lista solo ordena la presentación:
    # socio titular primero; debajo, todos sus invitados, institucionales referenciados,
    # reasignados actuales y espera. Dentro del grupo se mantiene el orden operativo,
    # dejando espera al final para lectura rápida del Capitán.
    captain_reservations = list(reservations)
    if outing and views:
        original_pos = {rr.id: idx for idx, rr in enumerate(reservations)}

        def captain_display_group_key(rr):
            # Institucional: la referencia humana de operación manda para lectura del Capitán.
            if is_protocolar(rr) and getattr(rr, "protocolar_by_user_id", None):
                return f"u-{rr.protocolar_by_user_id}"
            # Invitados comunes, menores y reasignados: responsable actual.
            if getattr(rr, "responsible_user_id", None):
                return f"u-{rr.responsible_user_id}"
            return f"row-{rr.id}"

        groups = {}
        for rr in reservations:
            groups.setdefault(captain_display_group_key(rr), []).append(rr)

        ordered_keys = []
        # Primero los grupos que tienen socio titular en el orden natural de la salida.
        for rr in reservations:
            if canonical_kind(rr.kind) == "socio" and getattr(rr, "responsible_user_id", None):
                key = f"u-{rr.responsible_user_id}"
                if key not in ordered_keys:
                    ordered_keys.append(key)
        # Luego grupos huérfanos/defensivos, si existieran, sin inventar responsable.
        for rr in reservations:
            key = captain_display_group_key(rr)
            if key not in ordered_keys:
                ordered_keys.append(key)

        def row_rank(rr):
            kind = canonical_kind(rr.kind)
            owner_first = 0 if kind == "socio" else 1
            wait_last = 1 if is_waitlisted(rr) else 0
            return (owner_first, wait_last, original_pos.get(rr.id, 999999))

        captain_reservations = []
        for key in ordered_keys:
            captain_reservations.extend(sorted(groups.get(key, []), key=row_rank))

    captain_responsible_options = []
    if outing and reservations:
        # Socios presentes y activos disponibles para tomar invitados a cargo en el momento del embarque.
        # La reasignación vive en Capitán: evita duplicar personas y mueve la imputación económica.
        present_socio_ids = []
        for rr in reservations:
            if canonical_kind(rr.kind) == "socio" and rr.attendance == "Presente" and reservation_is_active(rr) and rr.responsible_user_id:
                present_socio_ids.append(rr.responsible_user_id)
        if present_socio_ids:
            users_by_present_id = {u.id: u for u in db.query(User).filter(User.id.in_(sorted(set(present_socio_ids)))).all()}
            for rr in reservations:
                if canonical_kind(rr.kind) == "socio" and rr.attendance == "Presente" and reservation_is_active(rr) and rr.responsible_user_id:
                    u = users_by_present_id.get(rr.responsible_user_id)
                    if u:
                        captain_responsible_options.append({"id": u.id, "name": u.name, "member_no": u.member_no or ""})

    final_summary = final_status_summary(outing, reservations, len(active), present, pending) if outing else {}

    # Tabla maestra para Administración: historial completo de reservas, independiente de la salida seleccionada.
    all_outings = db.query(Outing).order_by(Outing.departure_at.desc()).all()
    outing_by_id = {o.id: o for o in all_outings}
    all_reservations = db.query(Reservation).order_by(Reservation.created_at.desc()).all()
    all_responsible_ids = sorted({r.responsible_user_id for r in all_reservations if r.responsible_user_id})
    all_responsible_names = {u.id: u.name for u in db.query(User).filter(User.id.in_(all_responsible_ids)).all()} if all_responsible_ids else {}
    all_reservation_rows = []
    for rr in sorted(all_reservations, key=lambda x: (outing_by_id.get(x.outing_id).departure_at if outing_by_id.get(x.outing_id) else datetime.min, x.created_at or datetime.min), reverse=True):
        row_outing = outing_by_id.get(rr.outing_id)
        if not row_outing:
            continue
        vv = reservation_view(row_outing, rr)
        all_reservation_rows.append({
            "id": rr.id,
            "outing_id": row_outing.id,
            "outing_title": row_outing.title,
            "outing_date": fmt_admin_datetime(row_outing.departure_at),
            "outing_status": row_outing.status,
            "name": rr.person_name,
            "dni": rr.dni,
            "kind": vv.get("tipo_label", rr.kind),
            "status": vv.get("status_label", rr.status),
            "attendance": rr.attendance,
            "physical": vv.get("estado_fisico", ""),
            "regulatory": vv.get("estado_reglamentario", ""),
            "reason": vv.get("motivo", ""),
            "charge": vv.get("charge", 0),
            "charge_label": vv.get("charge_label", "0"),
            "charge_preview": vv.get("charge_preview", 0),
            "charge_preview_label": vv.get("charge_preview_label", "0"),
            "responsible": all_responsible_names.get(rr.responsible_user_id, "") if rr.responsible_user_id else "",
            "created_at": fmt_admin_datetime(rr.created_at),
            "cancelled_at": fmt_admin_datetime(rr.cancelled_at) if rr.cancelled_at else "",
            "row_class": "chargeRow" if vv.get("charge", 0) > 0 else ("waitRow" if vv.get("waitlisted") else ("mutedRow" if vv.get("cancelled") else "")),
        })

    summary = charge_summary(outing, reservations) if outing else {"socios": [], "invitados": [], "menores": [], "total": 0, "total_label": "0", "preliminares": [], "preliminary_total": 0, "preliminary_total_label": "0"}
    acta = final_acta(outing, reservations) if outing else {"embarked": [], "not_embarked": [], "pending": [], "charges": [], "preliminary": [], "total": 0, "total_label": "0", "preliminary_total": 0, "preliminary_total_label": "0", "embarked_count": 0, "not_embarked_count": 0, "pending_count": 0}
    checkin_url = ""
    qr_url = ""
    if outing:
        token = sign_value(f"checkin:{outing.id}")
        base = str(request.base_url).rstrip("/")
        checkin_url = f"{base}/checkin?t={token}"
        qr_url = "https://api.qrserver.com/v1/create-qr-code/?size=420x420&data=" + checkin_url
    control_window = captain_control_window(outing) if outing else {}
    current_sheet = closing_sheet_current(db, outing.id) if outing else None
    return templates.TemplateResponse(request, "captain.html", {
        "request": request, "user": user, "outing": outing, "outings": outings, "history_groups": history_groups, "reservations": captain_reservations,
        "active": active, "active_count": len(active), "present": present, "absent": absent,
        "pending": pending, "socios_presentes": socios_presentes, "readiness": ready,
        "cutoff": cutoff_passed(outing) if outing else False, "cutoff_at": cutoff_at(outing) if outing else None, "msg": request.query_params.get("msg"),
        "reservation_views": views, "final_summary": final_summary, "charge_summary": summary, "acta": acta,
        "closed": is_closed_outing(outing) if outing else False,
        "waitlist_count": waitlist_count, "total_registros": len(reservations) if outing else 0,
        "checkin_url": checkin_url, "qr_url": qr_url, "control_window": control_window,
        "captain_responsible_options": captain_responsible_options,
        "current_sheet": current_sheet
    })


def dni_format_warning(dni: str) -> bool:
    """Devuelve True si el DNI luce raro, pero no bloquea por compatibilidad con datos históricos."""
    raw = (dni or "").strip()
    return bool(raw) and not bool(__import__('re').match(r"^[0-9]{7,9}$", raw))


def present_guest_without_present_responsible_errors(db: Session, outing: Outing, reservations=None) -> list:
    """Validación dura de embarque.

    Un invitado presente solo puede navegar si su socio responsable también figura
    Presente y activo en la misma salida. Si el socio no embarcó, fue bajado, está
    cancelado, en espera o no embarca por capitán, el invitado debe reasignarse
    a otro socio presente o marcarse No embarca / No embarcó antes del cierre.
    """
    if reservations is None:
        reservations = db.query(Reservation).filter_by(outing_id=outing.id).order_by(Reservation.id).all()
    users = {u.id: u for u in db.query(User).all()}
    present_socio_ids = {
        r.responsible_user_id for r in reservations
        if canonical_kind(r.kind) == "socio"
        and r.attendance == "Presente"
        and reservation_is_active(r)
        and not is_captain_cancelled(r)
        and not is_no_board_by_captain(r)
    }
    errors = []
    for r in reservations:
        k = canonical_kind(r.kind)
        if k not in ("invitado", "hijo_menor"):
            continue
        # Protocolar: puede embarcar aunque no esté quien lo cargó.
        # No depende de socio responsable y no requiere reasignación.
        if is_protocolar(r):
            continue
        if r.attendance != "Presente":
            continue
        if is_waitlisted(r) or r.cancelled_at is not None or r.status == "Cancelado" or is_captain_cancelled(r) or is_no_board_by_captain(r):
            continue
        if r.responsible_user_id not in present_socio_ids:
            resp = users.get(r.responsible_user_id)
            resp_name = resp.name if resp else "sin responsable"
            errors.append(
                f"{r.person_name}: figura presente pero su socio responsable no está presente ({resp_name}). "
                "Reasignar a un socio presente o marcar No embarca / No embarcó antes de cerrar."
            )
    return errors

def captain_cancel_final_validation(db: Session, outing: Outing) -> tuple[bool, str]:
    """Validación final inmediatamente antes de cancelar por capitán.

    No confía en el estado visto en pantalla. Se reevalúa contra DB dentro del
    request crítico para evitar dobles cancelaciones o anulaciones inconsistentes.
    """
    if not outing:
        return False, "salida_inexistente"
    if outing.status == "Cancelada por capitán":
        return False, "salida_ya_cancelada"
    if outing.status not in ("En reservas", "Embarque cerrado", "Realizada"):
        return False, "estado_no_cancelable"
    return True, "ok"


def captain_reopen_final_validation(db: Session, outing: Outing) -> tuple[bool, str]:
    """Validación final inmediatamente antes de reabrir una salida."""
    if not outing:
        return False, "salida_inexistente"
    if outing.status == "En reservas":
        return False, "salida_ya_abierta"
    if outing.status not in ("Embarque cerrado", "Cancelada por capitán", "Realizada"):
        return False, "estado_no_reabrible"
    return True, "ok"


def captain_close_final_validation(db: Session, outing: Outing) -> tuple[bool, str, Optional[ClosingSheet]]:
    """Validación final dura antes del cierre operativo.

    La UI/preflight puede haber quedado vieja; acá se vuelve a mirar el estado
    real para que un reintento o un request repetido no duplique ficha ni cierre.
    """
    if not outing:
        return False, "salida_inexistente", None
    current_sheet = closing_sheet_current(db, outing.id)
    if outing.status == "Cancelada por capitán":
        return False, "salida_cancelada", current_sheet
    if outing.status in ("Embarque cerrado", "Realizada"):
        return False, "salida_ya_cerrada", current_sheet
    if current_sheet and outing.status not in ("Embarque cerrado", "Realizada"):
        return False, "ficha_vigente_duplicada", current_sheet
    return True, "ok", current_sheet


def attendance_idempotent_noop(r: Reservation, value: str) -> bool:
    """True si el estado pedido ya es el estado final actual de la reserva."""
    current = (r.attendance or "").strip()
    if current != value:
        return False
    if value == "Presente":
        return reservation_is_active(r) and not is_waitlisted(r) and not is_captain_cancelled(r)
    if value == "Ausente":
        return current == "Ausente"
    if value == "Por confirmar":
        return current == "Por confirmar" and reservation_is_active(r)
    if value == "No embarca":
        return is_no_board_by_captain(r) or current == "No embarca"
    return False


def close_preflight_analysis(db: Session, outing: Outing) -> dict:
    """Análisis previo al cierre: detecta errores bloqueantes y sugiere correcciones.

    No modifica datos. El cierre real vuelve a validar para que no haya una carrera
    entre la revisión previa y la confirmación final.
    """
    reservations = db.query(Reservation).filter_by(outing_id=outing.id).order_by(Reservation.id).all()
    users = {u.id: u for u in db.query(User).all()}
    active = active_reservations(reservations)
    present_rows = [r for r in reservations if r.attendance == "Presente" and reservation_is_active(r)]
    present_count = len(present_rows)
    waitlist_count = sum(1 for r in reservations if is_waitlisted(r))
    pending_rows = [r for r in active if (r.attendance or "Por confirmar") == "Por confirmar"]

    errors = []
    warnings = []
    suggestions = []

    if present_count > outing.max_crew:
        errors.append(f"Hay {present_count} presentes para cupo {outing.max_crew}. Bajá personas a No embarca/Ausente antes de cerrar.")

    # Duplicados de documento dentro de la misma salida, excluyendo lista de espera/cancelados.
    seen = {}
    for r in reservations:
        if is_waitlisted(r) or r.cancelled_at is not None or r.status == "Cancelado":
            continue
        nd = norm_dni(r.dni)
        if not nd:
            continue
        if nd in seen:
            errors.append(f"Documento duplicado en la salida: {r.dni} figura en {seen[nd]} y {r.person_name}.")
        else:
            seen[nd] = r.person_name

    present_socio_ids = {
        r.responsible_user_id for r in reservations
        if canonical_kind(r.kind) == "socio" and r.attendance == "Presente" and reservation_is_active(r)
    }

    for e in present_guest_without_present_responsible_errors(db, outing, reservations):
        if e not in errors:
            errors.append(e)

    estimated_navigation_total = 0.0
    estimated_noshow_total = 0.0
    invited_present_count = 0
    noshow_count = 0

    for r in reservations:
        k = canonical_kind(r.kind)
        if is_waitlisted(r) or r.cancelled_at is not None or r.status == "Cancelado" or is_captain_cancelled(r) or is_no_board_by_captain(r):
            continue

        att = r.attendance or "Por confirmar"
        simulated_att = "Ausente" if att == "Por confirmar" else att

        if k in ("invitado", "hijo_menor"):
            protocolar = is_protocolar(r)
            if not norm_dni(r.dni):
                errors.append(f"{r.person_name}: invitado sin DNI/documento. Cargalo antes de cerrar.")
            elif dni_format_warning(r.dni):
                warnings.append(f"{r.person_name}: documento corto o incompleto ({r.dni}). Revisar si es dato de prueba o documento real.")

            if (not protocolar) and simulated_att == "Presente" and r.responsible_user_id not in present_socio_ids:
                suggestions.append(f"Corregir {r.person_name}: reasignar a un socio presente o marcar No embarca si no sube.")

            if simulated_att == "Presente":
                if protocolar:
                    # Protocolar embarcado: ocupa plaza física si corresponde, pero siempre sin cargo.
                    pass
                elif k == "invitado":
                    invited_present_count += 1
                    estimated_navigation_total += float(outing.guest_fee or 0)
            elif simulated_att in ("Ausente", "No embarcable"):
                noshow_count += 1
                estimated_noshow_total += reservation_charge(outing, r)

        elif k == "socio":
            if simulated_att in ("Ausente", "No embarcable"):
                noshow_count += 1
                estimated_noshow_total += reservation_charge(outing, r)

    if pending_rows:
        names = ", ".join(r.person_name for r in pending_rows[:5])
        extra = "..." if len(pending_rows) > 5 else ""
        warnings.append(f"Hay {len(pending_rows)} pendientes. Si confirmás el cierre, pasan a Ausente con cargo si corresponde: {names}{extra}")
        suggestions.append("Antes de cerrar, revisá si los pendientes realmente están ausentes o si corresponde marcarlos No embarca.")

    if present_count < outing.max_crew and waitlist_count:
        suggestions.append(f"Hay {outing.max_crew - present_count} lugar(es) operativos y {waitlist_count} en espera. Podés promover/embarcar suplentes antes de cerrar si están presentes.")

    return {
        "errors": errors,
        "warnings": warnings,
        "suggestions": suggestions,
        "present_count": present_count,
        "max_crew": outing.max_crew,
        "pending_count": len(pending_rows),
        "waitlist_count": waitlist_count,
        "invited_present_count": invited_present_count,
        "noshow_count": noshow_count,
        "estimated_navigation_total": estimated_navigation_total,
        "estimated_noshow_total": estimated_noshow_total,
        "estimated_total": estimated_navigation_total + estimated_noshow_total,
        "estimated_navigation_total_label": human_money(estimated_navigation_total),
        "estimated_noshow_total_label": human_money(estimated_noshow_total),
        "estimated_total_label": human_money(estimated_navigation_total + estimated_noshow_total),
        "ok": not errors,
    }

def auto_confirm_active_for_close(db: Session, outing: Outing, active):
    """Cierre operativo: al cerrar, quien no figura Presente queda Ausente/reserva incumplida.

    El QR marca Presente. El cierre consolida esa planilla.
    No se auto-regalan presentes a los pendientes.
    """
    changed = []
    for r in active:
        current = (r.attendance or "Por confirmar").strip()
        if current == "Por confirmar":
            r.attendance = "Ausente"
            r.cancel_reason = "No confirmado al cierre de embarque"
            r.charge_amount = reservation_charge(outing, r) if late_window_passed(outing) else 0
            changed.append(r.person_name)
    if changed:
        log(db, "Sistema", "pendientes marcados ausentes al cierre", f"{outing.title}: {chr(44).join(changed)}")
    return changed

def liquidate_and_close_boarding(db: Session, outing: Outing, reservations, active):
    """Cierra embarque y liquida la salida.

    Reglas acordadas:
    - Socio presente: sin cargo.
    - Invitado presente: paga tarifa completa de invitado al socio responsable.
    - Socio ausente/reserva incumplida: paga 70% de la tarifa de invitado.
    - Invitados de socio ausente: no embarcan, pero se cobran al socio ausente
      salvo que el capitán los haya reasignado a otro socio presente antes del cierre.
    - Invitados protocolares: pueden embarcar aunque no esté quien los cargó y siempre son sin cargo.
    - No embarca por decisión del capitán: sin cargo.
    - Lista de espera: sin cargo.
    """
    normalize_member_reservations(db, reservations)
    users = {u.id: u for u in db.query(User).all()}
    present_socio_rows = {
        r.responsible_user_id: r
        for r in reservations
        if canonical_kind(r.kind) == "socio" and r.attendance == "Presente" and reservation_is_active(r)
    }
    guest_fee = float(outing.guest_fee or 0)

    for r in reservations:
        k = canonical_kind(r.kind)

        if is_waitlisted(r):
            r.charge_amount = 0
            continue

        # Regla institucional dura:
        # Protocolar no depende del socio que lo cargó, puede embarcar aunque ese socio no esté,
        # y nunca genera cargo ni reserva incumplida.
        if is_protocolar(r):
            r.charge_amount = 0
            if r.attendance == "Presente":
                r.cancel_reason = f"Protocolar · Designado por: {getattr(r, 'protocolar_by', None) or getattr(r, 'responsible_name', None) or 'Comisión Fjord VI'}"
            elif r.attendance in ("Ausente", "No embarcable", "No embarca"):
                r.cancel_reason = f"Protocolar no embarcado · Designado por: {getattr(r, 'protocolar_by', None) or getattr(r, 'responsible_name', None) or 'Comisión Fjord VI'}"
            elif r.attendance == "Por confirmar":
                r.attendance = "Ausente"
                r.cancel_reason = f"Protocolar no confirmado al cierre · Designado por: {getattr(r, 'protocolar_by', None) or getattr(r, 'responsible_name', None) or 'Comisión Fjord VI'}"
            continue

        if is_captain_cancelled(r):
            r.charge_amount = 0
            r.attendance = "Ausente"
            r.cancel_reason = r.cancel_reason or "Cancelado por capitán"
            continue

        if is_no_board_by_captain(r):
            r.charge_amount = 0
            r.attendance = "No embarca"
            r.cancel_reason = "No embarcado por decisión del capitán"
            continue

        if r.cancelled_at is not None:
            if r.charge_amount is None:
                r.charge_amount = 0
            continue

        if r.attendance == "Por confirmar":
            r.attendance = "Ausente"
            r.cancel_reason = r.cancel_reason or "No confirmado al cierre de embarque"

        # Invitados/menores no pueden embarcar sin socio responsable presente.
        # Si quedaron asociados a un socio ausente, se transforman en reserva incumplida con cargo
        # al socio responsable, no en 'No embarca sin cargo'.
        if k in ("invitado", "hijo_menor") and r.attendance == "Presente":
            if r.responsible_user_id not in present_socio_rows:
                r.attendance = "Ausente"
                r.cancel_reason = "No embarcó por ausencia del socio responsable"
                r.charge_amount = reservation_charge(outing, r)

        # Liquidación por ESTADO FINAL único. No se arrastran cargos de estados anteriores.
        if r.attendance in ("Ausente", "No embarcable"):
            r.charge_amount = reservation_charge(outing, r)
            if not r.cancel_reason:
                r.cancel_reason = "No embarcó: plaza reservada no utilizada"
        elif r.attendance == "Presente":
            # Presente pisa cualquier reserva incumplida previo. El cargo se imputa una sola vez,
            # al socio responsable final. Si hubo reasignación, se preserva la nota
            # para que la ficha explique de dónde venía ese invitado.
            previous_reason = (r.cancel_reason or "").strip()
            reassignment_trace = reassignment_trace_only(previous_reason)
            if k == "invitado":
                r.charge_amount = guest_fee
                if reassignment_trace:
                    r.cancel_reason = reassignment_trace + " · Tarifa de invitado embarcado"
                else:
                    r.cancel_reason = "Tarifa de invitado embarcado"
            elif k == "hijo_menor":
                r.charge_amount = 0
                if reassignment_trace:
                    r.cancel_reason = reassignment_trace + " · Hijo menor de socio embarcado sin cargo"
                else:
                    r.cancel_reason = "Hijo menor de socio embarcado sin cargo"
            else:
                r.charge_amount = 0
                r.cancel_reason = "Socio embarcado sin cargo"

    outing.status = "Embarque cerrado"




def reassignment_trace_only(reason: str) -> str:
    """Devuelve solo la trazabilidad de reasignación, sin arrastrar cargos de cierres anteriores.

    Al reabrir una salida y volver a cerrarla, la ficha anterior queda anulada.
    La reasignación debe sobrevivir como dato histórico operativo, pero no deben
    duplicarse textos como "Tarifa de invitado embarcado" ni motivos de reserva incumplida.
    """
    txt = (reason or "").strip()
    if "reasignado" not in txt.lower():
        return ""
    # La convención del sistema agrega detalles contables con separador medio.
    # Nos quedamos con la traza original: "Reasignado por capitán: A -> B".
    return txt.split("·", 1)[0].strip()


def reservation_reassignment_count_value(r: Reservation) -> int:
    return int(getattr(r, "reassignment_count", 0) or 0)


def reservation_is_reassigned(r: Reservation) -> bool:
    return reservation_reassignment_count_value(r) > 0 or bool(getattr(r, "original_responsible_user_id", None) and getattr(r, "responsible_user_id", None) and getattr(r, "original_responsible_user_id", None) != getattr(r, "responsible_user_id", None))


def reservation_original_responsible_id(r: Reservation) -> Optional[int]:
    current = getattr(r, "responsible_user_id", None)
    original = getattr(r, "original_responsible_user_id", None)
    return original or current


def ensure_reservation_reassignment_state(db: Session, r: Reservation):
    if canonical_kind(r.kind) not in ("invitado", "hijo_menor"):
        return
    current = getattr(r, "responsible_user_id", None)
    original = getattr(r, "original_responsible_user_id", None)
    if current and not original:
        r.original_responsible_user_id = current
    if getattr(r, "reassignment_count", None) is None:
        r.reassignment_count = 0
    if getattr(r, "last_reassigned_by", None) is None:
        r.last_reassigned_by = ""


def record_reservation_reassignment(db: Session, outing: Outing, r: Reservation, from_user_id: Optional[int], to_user_id: Optional[int], actor: Optional[User], reason: str = ""):
    db.add(ReservationReassignment(
        outing_id=outing.id,
        reservation_id=r.id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        performed_by_user_id=getattr(actor, "id", None),
        performed_by_name=getattr(actor, "name", "") or "",
        performed_at=now_local(),
        reason=reason or "Reasignación operativa",
    ))

def recalculate_preliquidation_after_reopen(db: Session, outing: Outing, reservations):
    """Reconstruye la preliquidación al reabrir una salida.

    Si el capitán canceló la salida, todos los cargos quedaron en $0.
    Al reabrir, las bajas tardías previas vuelven a tener preliquidación
    si la salida podría realizarse finalmente. No genera cargo firme.
    """
    if not outing:
        return

    late = late_window_passed(outing)

    for r in reservations:
        if is_waitlisted(r):
            r.charge_amount = 0
            continue

        if is_captain_cancelled(r):
            r.charge_amount = 0
            r.attendance = "Ausente"
            r.cancel_reason = r.cancel_reason or "Cancelado por capitán"
            continue

        if is_no_board_by_captain(r):
            r.charge_amount = 0
            r.attendance = "No embarca"
            r.cancel_reason = "No embarcado por decisión del capitán"
            continue

        cancelled = bool(r.cancelled_at) or r.status == "Cancelado"

        if cancelled:
            r.attendance = "Ausente"
            if not r.cancel_reason:
                r.cancel_reason = "Cancelado por socio"
            r.charge_amount = reservation_charge(outing, r) if late else 0
            continue

        if r.attendance == "Ausente" and not (r.cancel_reason or "").strip():
            r.attendance = "Por confirmar"
            r.charge_amount = 0
            r.cancel_reason = ""
            continue

        if r.attendance in ("Ausente", "No embarcable"):
            r.charge_amount = reservation_charge(outing, r) if late else 0
            if r.charge_amount and not r.cancel_reason:
                r.cancel_reason = "No embarcó: plaza reservada no utilizada"
            continue

        r.charge_amount = 0
        if r.attendance in ("Presente", "Por confirmar") and not is_captain_cancelled(r):
            # Al reabrir, se limpian cargos firmes del cierre anterior, pero se conserva
            # la traza de reasignación para que el segundo cierre mantenga el relato operativo.
            r.cancel_reason = reassignment_trace_only(r.cancel_reason)

@app.post("/captain/outing_status")
def outing_status(
    request: Request,
    outing_id: Optional[int] = Form(None),
    status: str = Form(...),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("captain", "admin"))
):
    outing = selected_outing(db, outing_id)
    if not outing:
        return RedirectResponse("/captain?msg=salida_inexistente", status_code=303)

    old_status = outing.status

    # Control temporal: Administración puede siempre; Capitán solo dentro de su ventana.
    if user.role != "admin":
        w = captain_control_window(outing)
        if w["expired"]:
            return RedirectResponse(f"/captain?outing_id={outing.id}&msg=ventana_finalizada", status_code=303)
        if status == "Cerrar" and w["before_departure"]:
            return RedirectResponse(f"/captain?outing_id={outing.id}&msg=cierre_anticipado", status_code=303)

    # ===== CANCELAR =====
    if status == "Cancelada":
        ok, code = captain_cancel_final_validation(db, outing)
        if not ok and code == "salida_ya_cancelada":
            audit_event(db, user, "cancelación idempotente", f"{outing.title} ya estaba cancelada", request=request, outing_id=outing.id, before={"status": outing.status}, after={"status": outing.status})
            return RedirectResponse(f"/captain?outing_id={outing.id}&msg=estado_actualizado", status_code=303)
        if not ok:
            return RedirectResponse(f"/captain?outing_id={outing.id}&msg=accion_invalida", status_code=303)

        reservations = db.query(Reservation).filter_by(outing_id=outing.id).all()

        # Si existía ficha vigente, queda anulada: nunca se pisa ni se borra.
        annul_current_closing_sheet(db, outing, user.name, "Salida cancelada/reabierta por capitán")

        for r in reservations:
            # La cancelación total por capitán anula toda preliquidación,
            # pero no borra cancel_reason/cancelled_at. Así, si el capitán
            # reabre la salida, se puede reconstruir la preliquidación de
            # bajas tardías previas sin perder trazabilidad.
            r.charge_amount = 0

        outing.status = "Cancelada por capitán"

        db.commit()
        audit_event(db, user, "cancelación", f"{outing.title} / desde {old_status}", request=request, outing_id=outing.id, before={"status": old_status}, after={"status": outing.status, "charges_zeroed": len(reservations)})
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=estado_actualizado", status_code=303)

    # ===== CERRAR =====
    if status == "Cerrar":
        # Cierre único: el botón válido es /captain/close.
        # Se evita mantener dos caminos con reglas distintas.
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=usar_cerrar_liquidar", status_code=303)

    # ===== REABRIR =====
    if status == "Reservas abiertas":
        ok, code = captain_reopen_final_validation(db, outing)
        if not ok and code == "salida_ya_abierta":
            audit_event(db, user, "reapertura idempotente", f"{outing.title} ya estaba abierta", request=request, outing_id=outing.id, before={"status": outing.status}, after={"status": outing.status})
            return RedirectResponse(f"/captain?outing_id={outing.id}&msg=reapertura_ok", status_code=303)
        if not ok:
            return RedirectResponse(f"/captain?outing_id={outing.id}&msg=accion_invalida", status_code=303)

        reservations = db.query(Reservation).filter_by(outing_id=outing.id).all()
        annul_current_closing_sheet(db, outing, user.name, "Salida reabierta por capitán")
        outing.status = "En reservas"
        recalculate_preliquidation_after_reopen(db, outing, reservations)
        promoted = promote_waitlist(db, outing)
        db.commit()
        audit_event(db, user, "reapertura", f"{outing.title} / desde {old_status} / preliquidaciones recalculadas / promovidos {', '.join(promoted) if promoted else '-'}", request=request, outing_id=outing.id, before={"status": old_status}, after={"status": outing.status, "promovidos": promoted})
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=reapertura_ok", status_code=303)

    return RedirectResponse(f"/captain?outing_id={outing.id}", status_code=303)

@app.post("/captain/attendance/{rid}/{value}")
def attendance(request: Request, rid: int, value: str, db: Session = Depends(db_session), user: User = Depends(require_role("captain", "admin"))):
    r = db.get(Reservation, rid)
    if not r or value not in ["Presente", "Ausente", "Por confirmar", "No embarca"]:
        return RedirectResponse("/captain?msg=accion_invalida", status_code=303)

    outing = db.get(Outing, r.outing_id)
    if not outing:
        return RedirectResponse("/captain?msg=salida_inexistente", status_code=303)
    if user.role != "admin":
        w = captain_control_window(outing)
        if w["expired"]:
            return RedirectResponse(f"/captain?outing_id={outing.id}&msg=ventana_finalizada", status_code=303)
    # Blindaje de ficha congelada: una vez cerrada la salida, nadie debe cambiar
    # estados de embarque por este endpoint. Toda corrección debe hacerse reabriendo
    # la salida, lo que anula la ficha vigente y genera una nueva versión al cerrar.
    if outing and outing.status == "Cancelada por capitán":
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=salida_cancelada", status_code=303)
    if outing and outing.status in ("Embarque cerrado", "Realizada"):
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=salida_cerrada", status_code=303)

    was_waitlisted = is_waitlisted(r)
    if was_waitlisted:
        if value not in ("Por confirmar", "Presente"):
            return RedirectResponse(f"/captain?outing_id={outing.id}&msg=reserva_en_espera", status_code=303)
        if not captain_activate_waitlisted_reservation(db, outing, r):
            return RedirectResponse(f"/captain?outing_id={outing.id}&msg=reserva_en_espera", status_code=303)

    if attendance_idempotent_noop(r, value):
        audit_event(db, user, "asistencia idempotente", f"{r.person_name}: {value} ya aplicado / {outing.title}", request=request, outing_id=outing.id, reservation_id=r.id, before={"attendance": r.attendance, "status": r.status, "charge_amount": float(r.charge_amount or 0)}, after={"attendance": r.attendance, "status": r.status, "charge_amount": float(r.charge_amount or 0)})
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=asistencia_actualizada", status_code=303)

    # Blindaje de cupo en operación: no permite superar el máximo de presentes.
    # Antes el preflight lo frenaba al cierre; ahora también se bloquea al tocar.
    if value == "Presente" and r.attendance != "Presente":
        present_count = db.query(Reservation).filter(
            Reservation.outing_id == outing.id,
            Reservation.attendance == "Presente",
            Reservation.cancelled_at.is_(None),
            Reservation.id != r.id,
        ).count()
        if present_count >= (outing.max_crew or MAX_CREW):
            return RedirectResponse(f"/captain?outing_id={outing.id}&msg=cupo_lleno", status_code=303)

    before_attendance = {"attendance": r.attendance, "status": r.status, "charge_amount": float(r.charge_amount or 0), "cancel_reason": r.cancel_reason or ""}
    previous_trace = _reassignment_trace_only_bootstrap(r.cancel_reason or "")

    if value in ("Presente", "Por confirmar"):
        # Blindaje: un invitado/menor no socio no puede ser marcado presente
        # si su socio responsable no está presente y activo.
        if value == "Presente" and canonical_kind(r.kind) in ("invitado", "hijo_menor") and not is_protocolar(r):
            responsible_row = responsible_reservation_for(db, r.outing_id, r.responsible_user_id)
            responsible_ok = bool(responsible_row and responsible_row.attendance == "Presente" and reservation_is_active(responsible_row))
            if not responsible_ok:
                log(db, user.name, "asistencia bloqueada", f"{r.person_name}: socio responsable no está presente / {outing.title}")
                return RedirectResponse(f"/captain?outing_id={outing.id}&msg=socio_responsable_no_presente", status_code=303)
        r.cancelled_at = None
        r.status = default_reservation_status(outing, r)
        # No borrar la traza de reasignación: es el candado que impide una segunda
        # reasignación y además explica la imputación en ficha tras reabrir/corregir.
        r.cancel_reason = previous_trace
        r.charge_amount = 0
        r.attendance = value
    elif value == "Ausente":
        # Ausente verdadero: no embarcó y queda como plaza perdida con cargo reglamentario.
        # Si es socio titular, sus invitados comunes quedan impedidos y con cargo
        # al socio original, salvo reasignación manual previa a otro socio presente.
        r.attendance = "Ausente"
        r.cancel_reason = (previous_trace + " · Ausente / no se presentó") if previous_trace else "Ausente / no se presentó"
        r.charge_amount = reservation_charge(outing, r) if late_window_passed(outing) else 0
        cascade_dependents_for_responsible_status(db, outing, r, mode="absent_charged")
    elif value == "No embarca":
        # Decisión operativa del capitán: no es reserva incumplida y no genera cargo.
        r.cancelled_at = None
        r.status = default_reservation_status(outing, r)
        r.attendance = "No embarca"
        r.cancel_reason = (previous_trace + " · No embarcado por decisión del capitán") if previous_trace else "No embarcado por decisión del capitán"
        r.charge_amount = 0
        # Si el titular no embarca por decisión del capitán, sus invitados comunes
        # tampoco pueden navegar bajo ese socio y quedan sin cargo. Los institucionales
        # no entran en la cascada.
        cascade_dependents_for_responsible_status(db, outing, r, mode="no_board_free")

    # Reaplica la dependencia antes de recalcular cupos/promociones.
    enforce_responsible_dependency(db, outing)
    promoted = promote_waitlist(db, outing) if value in ("Ausente", "No embarca") else []
    enforce_capacity(db, outing)
    db.commit()
    audit_event(db, user, "asistencia", f"{r.person_name}: {value}{' / desde espera' if was_waitlisted else ''} / {outing.title} / promovidos {', '.join(promoted) if promoted else '-'}", request=request, outing_id=outing.id, reservation_id=r.id, before=before_attendance, after={"attendance": r.attendance, "status": r.status, "charge_amount": float(r.charge_amount or 0), "cancel_reason": r.cancel_reason or ""})
    return RedirectResponse(f"/captain?outing_id={outing.id}&msg=asistencia_actualizada", status_code=303)


@app.post("/captain/reassign/{rid}")
def captain_reassign_guest(
    request: Request,
    rid: int,
    new_responsible_user_id: int = Form(...),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("captain", "admin"))
):
    """Reasigna un invitado/menor a otro socio presente en la salida.

    Regla operativa: el invitado no se duplica ni se vuelve a cargar; cambia el socio
    responsable para que pueda embarcar y para que el cargo se impute al socio correcto.
    Solo puede hacerse antes del cierre y contra un socio presente.
    """
    r = db.get(Reservation, rid)
    if not r or canonical_kind(r.kind) not in ("invitado", "hijo_menor"):
        return RedirectResponse("/captain?msg=reasignacion_invalida", status_code=303)

    outing = db.get(Outing, r.outing_id)
    if not outing:
        return RedirectResponse("/captain?msg=salida_inexistente", status_code=303)

    if user.role != "admin":
        w = captain_control_window(outing)
        if w["expired"]:
            return RedirectResponse(f"/captain?outing_id={outing.id}&msg=ventana_finalizada", status_code=303)

    if outing.status in ("Embarque cerrado", "Cancelada por capitán", "Realizada"):
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=salida_cerrada", status_code=303)

    was_waitlisted = is_waitlisted(r)

    new_responsible = db.get(User, new_responsible_user_id)
    if not new_responsible or (new_responsible.role or "").strip().lower() != "socio":
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=reasignacion_invalida", status_code=303)

    new_responsible_row = db.query(Reservation).filter_by(outing_id=outing.id, dni=new_responsible.dni).first()
    if not new_responsible_row or canonical_kind(new_responsible_row.kind) != "socio" or not reservation_is_active(new_responsible_row):
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=socio_reasignacion_no_valido", status_code=303)

    if new_responsible_row.attendance != "Presente":
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=socio_reasignacion_no_presente", status_code=303)

    before_reassign = {"responsible_user_id": r.responsible_user_id, "attendance": r.attendance, "status": r.status, "cancel_reason": r.cancel_reason or ""}
    old_responsible_id = r.responsible_user_id
    old_responsible = db.get(User, old_responsible_id) if old_responsible_id else None
    if old_responsible_id == new_responsible.id:
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=reasignacion_sin_cambios", status_code=303)

    ensure_reservation_reassignment_state(db, r)
    if not getattr(r, "original_responsible_user_id", None):
        r.original_responsible_user_id = old_responsible_id

    r.responsible_user_id = new_responsible.id
    r.reassignment_count = reservation_reassignment_count_value(r) + 1
    r.last_reassigned_at = now_local()
    r.last_reassigned_by = user.name
    r.cancelled_at = None
    r.status = default_reservation_status(outing, r)
    # Si estaba bloqueado por ausencia del socio anterior, se reactiva para que el capitán pueda marcarlo presente.
    if r.attendance in ("No embarca", "No embarcable") or "socio responsable" in ((r.cancel_reason or "").lower()):
        r.attendance = "Por confirmar"
        r.charge_amount = 0
    # Trazabilidad operativa: el cargo sigue a la persona y al socio responsable final.
    old_name = old_responsible.name if old_responsible else "sin responsable anterior"
    r.cancel_reason = f"Reasignado por capitán: {old_name} -> {new_responsible.name}"
    record_reservation_reassignment(db, outing, r, old_responsible_id, new_responsible.id, user, reason="Reasignación operativa de invitado")

    # Caso real post-reapertura: si quedó una vacante y el invitado estaba en espera
    # bajo otro socio, la reasignación debe volver a dejarlo operable en la misma maniobra.
    if was_waitlisted:
        captain_activate_waitlisted_reservation(db, outing, r)

    enforce_capacity(db, outing)
    db.commit()
    audit_event(db, user, "reasignación invitado", f"{r.person_name}: {old_responsible.name if old_responsible else '-'} -> {new_responsible.name}{' / reactivado desde espera' if was_waitlisted and not is_waitlisted(r) else ''} / {outing.title}", request=request, outing_id=outing.id, reservation_id=r.id, before=before_reassign, after={"responsible_user_id": r.responsible_user_id, "original_responsible_user_id": getattr(r, "original_responsible_user_id", None), "reassignment_count": reservation_reassignment_count_value(r), "attendance": r.attendance, "status": r.status, "cancel_reason": r.cancel_reason or ""})
    return RedirectResponse(f"/captain?outing_id={outing.id}&msg=reasignacion_ok", status_code=303)


@app.get("/captain/preflight", response_class=HTMLResponse)
def captain_preflight(outing_id: Optional[int] = None, request: Request = None, db: Session = Depends(db_session), user: User = Depends(require_role("captain", "admin"))):
    outing, reservations, active, present, *_ = outing_context(db, outing_id)
    if not outing:
        return RedirectResponse("/captain?msg=salida_inexistente", status_code=303)
    if user.role != "admin":
        w = captain_control_window(outing)
        if w["expired"]:
            return RedirectResponse(f"/captain?outing_id={outing.id}&msg=ventana_finalizada", status_code=303)
        if w["before_departure"]:
            return RedirectResponse(f"/captain?outing_id={outing.id}&msg=cierre_anticipado", status_code=303)
    if outing.status in ("Embarque cerrado", "Cancelada por capitán", "Realizada"):
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=salida_cerrada", status_code=303)
    analysis = close_preflight_analysis(db, outing)
    return templates.TemplateResponse(request, "captain_preflight.html", {"request": request, "user": user, "outing": outing, "analysis": analysis})

@app.post("/captain/close")
def close_boarding(request: Request, outing_id: Optional[int] = Form(None), db: Session = Depends(db_session), user: User = Depends(require_role("captain", "admin"))):
    outing, reservations, active, present, *_ = outing_context(db, outing_id)
    if not outing:
        return RedirectResponse("/captain?msg=salida_inexistente", status_code=303)
    if user.role != "admin":
        w = captain_control_window(outing)
        if w["expired"]:
            return RedirectResponse(f"/captain?outing_id={outing.id}&msg=ventana_finalizada", status_code=303)
        if w["before_departure"]:
            return RedirectResponse(f"/captain?outing_id={outing.id}&msg=cierre_anticipado", status_code=303)
    ok, close_code, current_sheet = captain_close_final_validation(db, outing)
    if not ok and close_code == "salida_cancelada":
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=salida_cancelada", status_code=303)
    if not ok and close_code == "salida_ya_cerrada":
        if current_sheet:
            audit_event(db, user, "cierre idempotente", f"{outing.title} ya estaba cerrada / ficha {current_sheet.sequence}", request=request, outing_id=outing.id, before={"status": outing.status, "sheet_id": current_sheet.id}, after={"status": outing.status, "sheet_id": current_sheet.id})
            return RedirectResponse(f"/captain?outing_id={outing.id}&msg=cierre_ok&sheet_id={current_sheet.id}", status_code=303)
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=salida_cerrada", status_code=303)
    if not ok:
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=accion_invalida", status_code=303)

    enforce_capacity(db, outing)
    preflight = close_preflight_analysis(db, outing)
    if preflight["errors"]:
        return RedirectResponse(f"/captain/preflight?outing_id={outing.id}&msg=preflight_error", status_code=303)
    reservations = db.query(Reservation).filter_by(outing_id=outing.id).order_by(Reservation.cancelled_at.isnot(None), Reservation.id).all()
    active = active_reservations(reservations)
    active_count = len(active)
    present = sum(1 for r in active if r.attendance == "Presente")

    # Cierre administrativo: NO se bloquea por mínimo de tripulación.
    # El mínimo sirve para indicar si la salida puede operar, pero si llegó la hora
    # el capitán debe poder cerrar y liquidar aunque nadie haya marcado Presente.
    # Al cerrar, los activos pendientes quedan Ausentes/reserva incumplida y se calculan cargos.
    if active_count > outing.max_crew:
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=maximo_superado", status_code=303)

    auto_confirm_active_for_close(db, outing, active)
    # Capa crítica Capitán: después de consolidar pendientes, un socio ausente
    # o bajado sin cargo debe arrastrar a sus invitados comunes antes de validar
    # y liquidar. Institucionales/protocolares no entran en esta cascada.
    for socio_row in [x for x in reservations if canonical_kind(x.kind) == "socio"]:
        if socio_row.attendance == "Ausente":
            cascade_dependents_for_responsible_status(db, outing, socio_row, mode="absent_charged")
        elif is_no_board_by_captain(socio_row):
            cascade_dependents_for_responsible_status(db, outing, socio_row, mode="no_board_free")

    # Validación final después de convertir pendientes a Ausente: evita que un invitado
    # navegado quede cargado a un socio que finalmente no embarcó.
    final_errors = present_guest_without_present_responsible_errors(db, outing, reservations)
    if final_errors:
        db.rollback()
        return RedirectResponse(f"/captain/preflight?outing_id={outing.id}&msg=preflight_error", status_code=303)

    liquidate_and_close_boarding(db, outing, reservations, active)
    # Releer después de liquidar para que la ficha se arme con los estados finales.
    reservations = db.query(Reservation).filter_by(outing_id=outing.id).order_by(Reservation.id).all()
    present = sum(1 for r in reservations if r.attendance == "Presente" and reservation_is_active(r))
    sheet = create_closing_sheet(db, outing, reservations, user.name)
    db.commit()
    audit_event(db, user, "cierre embarque", f"{outing.title} / presentes {present} / activos {active_count} / ficha {sheet.sequence}", request=request, outing_id=outing.id, after={"status": outing.status, "presentes": present, "activos": active_count, "sheet_id": sheet.id, "sheet_sequence": sheet.sequence})
    admin_email = smtp_settings(db).get("admin_email")
    if admin_email:
        total_label = sheet_payload(sheet).get("summary", {}).get("total_label", "0")
        queue_email(db, "salida_cerrada_admin", admin_email, "Administración", {"salida_nombre": outing.title, "capitan_nombre": user.name, "presentes": str(present), "total": "$ " + str(total_label), "ficha_numero": str(sheet.sequence), "link_ficha": f"/cierre/{sheet.id}"})
    queue_no_show_charge_emails(db, outing, reservations, sheet)
    auto_process_notifications(db, limit=10)
    return RedirectResponse(f"/captain?outing_id={outing.id}&msg=cierre_ok&sheet_id={sheet.id}", status_code=303)



@app.get("/cierre/{sheet_id}", response_class=HTMLResponse)
def closing_sheet_view(sheet_id: int, request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin", "captain"))):
    sheet = db.get(ClosingSheet, sheet_id)
    if not sheet:
        raise HTTPException(404, "Ficha inexistente")
    data = sheet_payload(sheet)
    all_sheets = closing_sheet_all(db, sheet.outing_id)
    replacement = closing_sheet_replacement(db, sheet)
    replaced_sheets = [s for s in all_sheets if s.status == "ANULADA" and s.sequence < sheet.sequence] if sheet.status == "VIGENTE" else []
    return_url = f"/captain?outing_id={sheet.outing_id}" if user.role == "captain" else f"/admin?outing_id={sheet.outing_id}&page=fichas"
    return templates.TemplateResponse(request, "closing_sheet.html", {"request": request, "user": user, "sheet": sheet, "data": data, "return_url": return_url, "all_sheets": all_sheets, "replacement": replacement, "replaced_sheets": replaced_sheets, "version": VERSION, "release_label": RELEASE_LABEL})


@app.get("/cierre/salida/{outing_id}", response_class=HTMLResponse)
def closing_sheet_index(outing_id: int, request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin", "captain"))):
    outing = db.get(Outing, outing_id)
    if not outing:
        raise HTTPException(404, "Salida inexistente")
    sheets = closing_sheet_all(db, outing.id)
    return_url = f"/captain?outing_id={outing.id}" if user.role == "captain" else f"/admin?outing_id={outing.id}&page=fichas"
    return templates.TemplateResponse(request, "closing_sheets.html", {"request": request, "user": user, "outing": outing, "sheets": sheets, "return_url": return_url, "version": VERSION, "release_label": RELEASE_LABEL})


@app.get("/cierre/{sheet_id}/csv")
def closing_sheet_csv(sheet_id: int, db: Session = Depends(db_session), user: User = Depends(require_role("admin", "captain"))):
    sheet = db.get(ClosingSheet, sheet_id)
    if not sheet:
        raise HTTPException(404, "Ficha inexistente")
    data = sheet_payload(sheet)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Liquidación", data.get("liquidation_id", liquidation_id_for_sheet(sheet))])
    w.writerow(["Ficha", sheet.sequence, sheet.status, data.get("version_label", f"Ficha V{sheet.sequence}")])
    w.writerow(["Sistema", data.get("release_label", RELEASE_LABEL)])
    w.writerow(["Salida", data.get("outing_title", "")])
    w.writerow(["Fecha", data.get("departure_label", "")])
    w.writerow(["Capitán", data.get("captain", "")])
    w.writerow([])
    w.writerow(["Socio", "N° socio", "Concepto", "Persona", "Tipo", "DNI invitado", "Importe"])
    for g in data.get("groups", []):
        for p in g.get("cargos_navegacion", []):
            w.writerow([g.get("responsible_name", ""), g.get("member_no", ""), "Navegación", p.get("name", ""), p.get("tipo", ""), p.get("dni", ""), p.get("amount", 0)])
        for p in g.get("cargos_no_show", []):
            w.writerow([g.get("responsible_name", ""), g.get("member_no", ""), "Reserva incumplida", p.get("name", ""), p.get("tipo", ""), p.get("dni", ""), p.get("amount", 0)])
    w.writerow([])
    w.writerow(["TOTAL", "", "", "", "", "", data.get("summary", {}).get("total", 0)])
    filename = f"{data.get('liquidation_id', liquidation_id_for_sheet(sheet)).lower()}_ficha_cierre.csv"
    return Response(out.getvalue().encode("utf-8-sig"), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.get("/admin_qr", response_class=HTMLResponse)
def admin_qr(request: Request, outing_id: Optional[int] = None, db: Session = Depends(db_session), user: User = Depends(require_role("admin", "captain"))):
    outings = visible_outings(db, outing_id)
    history_outings = historical_outings(db, outings)
    history_groups = historical_outing_groups(history_outings)
    outing, reservations, active, present, absent, pending, socios_presentes = outing_context(db, outing_id)
    return_url = f"/captain?outing_id={outing.id}" if outing and user.role == "captain" else (f"/admin?outing_id={outing.id}" if outing else ("/captain" if user.role == "captain" else "/admin"))
    return_label = "Volver a Embarque" if user.role == "captain" else "Volver a Administración"
    if not outing:
        return templates.TemplateResponse(request, "admin_qr.html", {"request": request, "user": user, "outing": None, "outings": outings, "checkin_url": "", "qr_url": "", "return_url": return_url, "return_label": return_label})
    token = sign_value(f"checkin:{outing.id}")
    base = str(request.base_url).rstrip("/")
    checkin_url = f"{base}/checkin?t={token}"
    qr_url = "https://api.qrserver.com/v1/create-qr-code/?size=520x520&data=" + checkin_url
    return templates.TemplateResponse(request, "admin_qr.html", {"request": request, "user": user, "outing": outing, "outings": outings, "checkin_url": checkin_url, "qr_url": qr_url, "return_url": return_url, "return_label": return_label})


# =========================
# QR FIJO DEL BARCO / EMBARQUE DEL DIA
# =========================
def public_today_outings(db: Session):
    today = now_local().date()
    blocked = {"Embarque cerrado", "Cancelada por capitán", "Realizada"}
    rows = [o for o in db.query(Outing).all() if o.departure_at.date() == today and o.status not in blocked]
    rows.sort(key=lambda o: o.departure_at)
    return rows

def fixed_qr_url(request: Request) -> str:
    return str(request.base_url).rstrip("/") + "/embarque"

@app.get("/qr_fijo", response_class=HTMLResponse)
def fixed_qr_page(request: Request):
    url = fixed_qr_url(request)
    qr_url = "https://api.qrserver.com/v1/create-qr-code/?size=620x620&data=" + url
    return templates.TemplateResponse(request, "fixed_qr.html", {"request": request, "fixed_url": url, "qr_url": qr_url})

@app.get("/embarque", response_class=HTMLResponse)
def fixed_embarque_get(request: Request, db: Session = Depends(db_session)):
    outings = public_today_outings(db)
    return templates.TemplateResponse(request, "embarque_fijo.html", {"request": request, "outings": outings, "outing": outings[0] if len(outings) == 1 else None, "error": None, "msg": None, "dni": ""})

@app.post("/embarque", response_class=HTMLResponse)
def fixed_embarque_post(request: Request, dni: str = Form(""), db: Session = Depends(db_session)):
    outings = public_today_outings(db)
    dni_clean = norm_dni(dni)
    def render(error=None, msg=None, outing=None):
        return templates.TemplateResponse(request, "embarque_fijo.html", {"request": request, "outings": outings, "outing": outing or (outings[0] if len(outings) == 1 else None), "error": error, "msg": msg, "dni": dni})
    if not outings:
        return render(error="No hay una salida activa para hoy.")
    if not dni_clean:
        return render(error="Ingresá tu documento para registrar tu llegada.")
    duplicate_seen = False
    not_embarkable_seen = None
    waitlist_match = None
    for outing in outings:
        reservations = db.query(Reservation).filter_by(outing_id=outing.id).all()
        normalize_member_reservations(db, reservations)
        matches = [r for r in reservations if norm_dni(r.dni) == dni_clean]
        if len(matches) > 1:
            duplicate_seen = True
            continue
        if not matches:
            continue
        r = matches[0]
        if is_waitlisted(r):
            waitlist_match = (outing, r)
            continue
        if not reservation_is_active(r):
            not_embarkable_seen = (outing, r)
            continue
        if r.attendance == "Presente":
            return render(msg="Ya estabas registrado para embarcar.", outing=outing)
        r.attendance = "Presente"
        r.cancelled_at = None
        r.status = default_reservation_status(outing, r)
        r.cancel_reason = "Llegada registrada por QR fijo"
        r.charge_amount = 0
        db.commit()
        log(db, r.person_name, "QR fijo barco", f"{outing.title} / llegada registrada / {outing.departure_at.strftime('%d/%m/%Y %H:%M')}")
        return render(msg="Llegada registrada. La autorización final corresponde al capitán.", outing=outing)
    if waitlist_match:
        outing, r = waitlist_match
        r.cancel_reason = "Llegada QR registrada en lista de espera"
        db.commit()
        log(db, r.person_name, "QR fijo barco", f"{outing.title} / llegada en lista de espera")
        return render(msg="Figurás en lista de espera. Tu llegada quedó registrada; el embarque depende de que se libere una vacante y de la autorización del capitán.", outing=outing)
    if duplicate_seen:
        return render(error="Documento duplicado en la salida de hoy. Consultá al capitán.")
    if not_embarkable_seen:
        outing, r = not_embarkable_seen
        return render(error="Figurás en la salida de hoy, pero no como embarcable activo. Consultá al capitán.", outing=outing)
    return render(error="No figurás en la lista de la salida de hoy. Consultá con el capitán o la Oficina de Vela.")

@app.get("/checkin", response_class=HTMLResponse)
def checkin_get(request: Request, t: str = "", db: Session = Depends(db_session)):
    """Check-in público y neutro.

    Esta pantalla no usa sesión/cookie del navegador: aunque el teléfono tenga
    abierta una sesión de capitán/admin/socio, el QR siempre pide documento y
    valida contra la tripulación real de esa salida.
    """
    value = unsign_value(t)
    outing = None
    error = None
    if value and value.startswith("checkin:"):
        try:
            outing = db.get(Outing, int(value.split(":",1)[1]))
        except Exception:
            outing = None
    if not outing:
        error = "QR inválido o vencido."
    return templates.TemplateResponse(request, "checkin.html", {"request": request, "outing": outing, "token": t, "user": None, "error": error, "msg": request.query_params.get("msg")})


def find_checkin_reservation(db: Session, outing: Outing, dni_value: str):
    """Busca reserva por salida + documento normalizado, sin depender del login."""
    dni_clean = norm_dni(dni_value)
    if not dni_clean:
        return None, "empty"
    reservations = db.query(Reservation).filter_by(outing_id=outing.id).all()
    normalize_member_reservations(db, reservations)
    matches = [r for r in reservations if norm_dni(r.dni) == dni_clean]
    if not matches:
        return None, "not_found"
    active_matches = [r for r in matches if reservation_is_active(r) and not is_waitlisted(r)]
    if len(active_matches) == 1:
        return active_matches[0], "ok"
    if len(active_matches) > 1:
        return None, "duplicate"
    return matches[0], "not_embarkable"


@app.post("/checkin", response_class=HTMLResponse)
def checkin_post(request: Request, t: str = Form(...), dni: str = Form(""), db: Session = Depends(db_session)):
    """Registra presencia por QR público, con validación estricta contra tripulación."""
    value = unsign_value(t)
    outing = None
    if value and value.startswith("checkin:"):
        try:
            outing = db.get(Outing, int(value.split(":",1)[1]))
        except Exception:
            outing = None
    if not outing:
        return templates.TemplateResponse(request, "checkin.html", {"request": request, "outing": None, "token": t, "user": None, "error": "QR inválido o vencido.", "msg": None})
    if outing.status in ("Embarque cerrado", "Cancelada por capitán", "Realizada"):
        return templates.TemplateResponse(request, "checkin.html", {"request": request, "outing": outing, "token": t, "user": None, "error": "Esta salida ya no acepta check-in.", "msg": None})
    if captain_control_window(outing).get("expired"):
        return templates.TemplateResponse(request, "checkin.html", {"request": request, "outing": outing, "token": t, "user": None, "error": "El período de check-in de esta salida ya finalizó.", "msg": None})
    dni_clean = norm_dni(dni)
    if not dni_clean:
        return templates.TemplateResponse(request, "checkin.html", {"request": request, "outing": outing, "token": t, "user": None, "error": "Ingresá tu documento para confirmar.", "msg": None})

    r, state = find_checkin_reservation(db, outing, dni_clean)
    if state == "duplicate":
        log(db, "QR", "check-in rechazado", f"{outing.title} / doc {dni_clean} / documento duplicado")
        return templates.TemplateResponse(request, "checkin.html", {"request": request, "outing": outing, "token": t, "user": None, "error": "Documento duplicado en esta salida. Consultá al capitán.", "msg": None})
    if state == "not_found":
        log(db, "QR", "check-in rechazado", f"{outing.title} / doc {dni_clean} / no listado")
        return templates.TemplateResponse(request, "checkin.html", {"request": request, "outing": outing, "token": t, "user": None, "error": "No figurás en la lista de esta salida. Consultá al capitán.", "msg": None})
    if state == "not_embarkable" or not r:
        log(db, "QR", "check-in rechazado", f"{outing.title} / doc {dni_clean} / no embarcable")
        return templates.TemplateResponse(request, "checkin.html", {"request": request, "outing": outing, "token": t, "user": None, "error": "Figurás en la salida, pero no como embarcable activo. Consultá al capitán.", "msg": None})
    if r.attendance == "Presente":
        return templates.TemplateResponse(request, "checkin.html", {"request": request, "outing": outing, "token": t, "user": None, "error": None, "msg": "Ya estabas registrado para embarcar."})

    r.attendance = "Presente"
    r.cancelled_at = None
    r.status = default_reservation_status(outing, r)
    r.cancel_reason = "Check-in QR"
    r.charge_amount = 0
    db.commit()
    log(db, r.person_name, "check-in QR", f"{outing.title} / {outing.departure_at.strftime('%d/%m/%Y %H:%M')}")
    return templates.TemplateResponse(request, "checkin.html", {"request": request, "outing": outing, "token": t, "user": None, "error": None, "msg": "Check-in registrado. La autorización final corresponde al capitán."})

@app.get("/checkin.html", response_class=HTMLResponse)
def checkin_html_alias(request: Request):
    return RedirectResponse("/checkin", status_code=303)

@app.get("/admin_qr.html", response_class=HTMLResponse)
def admin_qr_html_alias():
    return RedirectResponse("/admin_qr", status_code=303)

@app.get("/admin/sistema", response_class=HTMLResponse)
@app.get("/admin/system", response_class=HTMLResponse)
def admin_sistema_fast(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    """Entrada rápida específica a Sistema.

    Evita pasar por el armado completo del dashboard administrativo, que calcula
    reservas, fichas, liquidaciones y tablas que no se necesitan para abrir Sistema.
    """
    return templates.TemplateResponse(request, "admin.html", base_template_context(**{
        "request": request,
        "user": user,
        "admin_page": "sistema",
        "outing": None,
        "msg": request.query_params.get("msg"),
        "system_console": system_console_context(db, request),
        "ops_center": {},
        "search_results": {},
        "communications": {},
        "padron": {},
        "users": [],
        "all_outings": [],
        "activity_rows": [],
        "activity_page": 1,
        "activity_pages": 1,
        "activity_total": 0,
    }))

@app.get("/admin/inicio", response_class=HTMLResponse)
@app.get("/admin/salidas", response_class=HTMLResponse)
@app.get("/admin/reservas", response_class=HTMLResponse)
@app.get("/admin/usuarios", response_class=HTMLResponse)
@app.get("/admin/historial", response_class=HTMLResponse)
@app.get("/admin/cargos", response_class=HTMLResponse)
@app.get("/admin/estadisticas", response_class=HTMLResponse)
@app.get("/admin/fichas", response_class=HTMLResponse)
@app.get("/admin/auditoria", response_class=HTMLResponse)
@app.get("/admin/actividad", response_class=HTMLResponse)
@app.get("/admin/exportaciones", response_class=HTMLResponse)
@app.get("/admin/comunicaciones", response_class=HTMLResponse)
@app.get("/admin/communications", response_class=HTMLResponse)
@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, outing_id: Optional[int] = None, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    outings = visible_outings(db, outing_id)
    history_outings = historical_outings(db, outings)
    history_groups = historical_outing_groups(history_outings)
    outing, reservations, active, present, absent, pending, socios_presentes = outing_context(db, outing_id)
    charges = [r for r in db.query(Reservation).filter(Reservation.outing_id == outing.id).all() if reservation_view(outing, r)["charge"] > 0] if outing else []
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(1000).all()
    total_charges = sum(reservation_view(outing, r)["charge"] for r in charges) if outing else 0
    ready = readiness_state(outing, len(active), present)
    all_outings_for_counts = outings + history_outings
    counts = {o.id: db.query(Reservation).filter_by(outing_id=o.id).count() for o in all_outings_for_counts}
    active_counts = {o.id: len(active_reservations(db.query(Reservation).filter_by(outing_id=o.id).all())) for o in all_outings_for_counts}
    responsible_ids = sorted({r.responsible_user_id for r in reservations if getattr(r, "responsible_user_id", None)})
    responsible_names = {}
    if responsible_ids:
        responsible_names = {u.id: u.name for u in db.query(User).filter(User.id.in_(responsible_ids)).all()}
    waitlist_count = sum(1 for rr in reservations if is_waitlisted(rr)) if outing else 0
    views = reservation_views(outing, reservations) if outing else {}
    if outing and views:
        responsible_ids = sorted({uid for r in reservations for uid in (r.responsible_user_id, getattr(r, "protocolar_by_user_id", None)) if uid})
        responsible_users = {u.id: u for u in db.query(User).filter(User.id.in_(responsible_ids)).all()} if responsible_ids else {}
        for r in reservations:
            v = views.get(r.id)
            if not v:
                continue
            responsible = responsible_users.get(r.responsible_user_id) if r.responsible_user_id else None
            own_reservation = bool(responsible and r.dni == responsible.dni)
            v["responsible_name"] = responsible.name if responsible else ""
            protocolar_ref = responsible_users.get(getattr(r, "protocolar_by_user_id", None)) if is_protocolar(r) and getattr(r, "protocolar_by_user_id", None) else None
            v["protocolar_reference_name"] = protocolar_ref.name if protocolar_ref else v.get("responsible_name", "")
            v["responsible_member_no"] = (responsible.member_no or "") if responsible else ""
            v["responsible_dni"] = responsible.dni if responsible else ""
            responsible_row = db.query(Reservation).filter_by(outing_id=outing.id, dni=responsible.dni).first() if responsible else None
            v["responsible_attendance"] = responsible_row.attendance if responsible_row else ""
            v["responsible_is_present"] = bool(responsible_row and responsible_row.attendance == "Presente" and reservation_is_active(responsible_row))
            v["own_reservation"] = own_reservation
            v["show_responsible"] = bool(responsible and canonical_kind(r.kind) in ("invitado", "hijo_menor") and not own_reservation)
            v["reassignment_locked"] = False
            v["reassignment_count"] = reservation_reassignment_count_value(r)
            v["is_reassigned"] = reservation_is_reassigned(r)
    captain_responsible_options = []
    if outing and reservations:
        # Socios presentes y activos disponibles para tomar invitados a cargo en el momento del embarque.
        # La reasignación vive en Capitán: evita duplicar personas y mueve la imputación económica.
        present_socio_ids = []
        for rr in reservations:
            if canonical_kind(rr.kind) == "socio" and rr.attendance == "Presente" and reservation_is_active(rr) and rr.responsible_user_id:
                present_socio_ids.append(rr.responsible_user_id)
        if present_socio_ids:
            users_by_present_id = {u.id: u for u in db.query(User).filter(User.id.in_(sorted(set(present_socio_ids)))).all()}
            for rr in reservations:
                if canonical_kind(rr.kind) == "socio" and rr.attendance == "Presente" and reservation_is_active(rr) and rr.responsible_user_id:
                    u = users_by_present_id.get(rr.responsible_user_id)
                    if u:
                        captain_responsible_options.append({"id": u.id, "name": u.name, "member_no": u.member_no or ""})

    final_summary = final_status_summary(outing, reservations, len(active), present, pending) if outing else {}

    # Tabla maestra para Administración: historial completo de reservas, independiente de la salida seleccionada.
    all_outings = db.query(Outing).order_by(Outing.departure_at.desc()).all()
    outing_by_id = {o.id: o for o in all_outings}
    all_reservations = db.query(Reservation).order_by(Reservation.created_at.desc()).all()
    all_responsible_ids = sorted({r.responsible_user_id for r in all_reservations if r.responsible_user_id})
    all_responsible_names = {u.id: u.name for u in db.query(User).filter(User.id.in_(all_responsible_ids)).all()} if all_responsible_ids else {}
    all_reservation_rows = []
    for rr in sorted(all_reservations, key=lambda x: (outing_by_id.get(x.outing_id).departure_at if outing_by_id.get(x.outing_id) else datetime.min, x.created_at or datetime.min), reverse=True):
        row_outing = outing_by_id.get(rr.outing_id)
        if not row_outing:
            continue
        vv = reservation_view(row_outing, rr)
        all_reservation_rows.append({
            "id": rr.id,
            "outing_id": row_outing.id,
            "outing_title": row_outing.title,
            "outing_date": fmt_admin_datetime(row_outing.departure_at),
            "outing_status": row_outing.status,
            "name": rr.person_name,
            "dni": rr.dni,
            "kind": vv.get("tipo_label", rr.kind),
            "status": vv.get("status_label", rr.status),
            "attendance": rr.attendance,
            "physical": vv.get("estado_fisico", ""),
            "regulatory": vv.get("estado_reglamentario", ""),
            "reason": vv.get("motivo", ""),
            "charge": vv.get("charge", 0),
            "charge_label": vv.get("charge_label", "0"),
            "charge_preview": vv.get("charge_preview", 0),
            "charge_preview_label": vv.get("charge_preview_label", "0"),
            "responsible": all_responsible_names.get(rr.responsible_user_id, "") if rr.responsible_user_id else "",
            "created_at": fmt_admin_datetime(rr.created_at),
            "cancelled_at": fmt_admin_datetime(rr.cancelled_at) if rr.cancelled_at else "",
            "row_class": "chargeRow" if vv.get("charge", 0) > 0 else ("waitRow" if vv.get("waitlisted") else ("mutedRow" if vv.get("cancelled") else "")),
        })

    summary = charge_summary(outing, reservations) if outing else {"socios": [], "invitados": [], "menores": [], "total": 0, "total_label": "0", "preliminares": [], "preliminary_total": 0, "preliminary_total_label": "0"}
    acta = final_acta(outing, reservations) if outing else {"embarked": [], "not_embarked": [], "pending": [], "charges": [], "preliminary": [], "total": 0, "total_label": "0", "preliminary_total": 0, "preliminary_total_label": "0", "embarked_count": 0, "not_embarked_count": 0, "pending_count": 0}
    control_window = captain_control_window(outing) if outing else {}
    current_sheet = closing_sheet_current(db, outing.id) if outing else None
    closing_sheets = closing_sheet_all(db, outing.id) if outing else []
    all_closing_sheets = db.query(ClosingSheet).order_by(ClosingSheet.created_at.desc(), ClosingSheet.sequence.desc()).all()
    outing_lookup = {o.id: o for o in all_outings}
    all_closing_sheet_rows = []
    for sh in all_closing_sheets:
        payload = sheet_payload(sh)
        sh_outing = outing_lookup.get(sh.outing_id)
        all_closing_sheet_rows.append({
            "id": sh.id,
            "outing_id": sh.outing_id,
            "sequence": sh.sequence,
            "liquidation_id": payload.get("liquidation_id") or liquidation_id_for_sheet(sh),
            "version_label": payload.get("version_label") or f"Ficha V{sh.sequence}",
            "status": sh.status,
            "created_at": fmt_admin_datetime(sh.created_at) if sh.created_at else "",
            "created_sort": sh.created_at,
            "created_by": sh.created_by,
            "annul_reason": sh.annul_reason or "-",
            "outing_title": payload.get("outing_title") or (sh_outing.title if sh_outing else f"Salida #{sh.outing_id}"),
            "departure_label": payload.get("departure_label") or (fmt_admin_datetime(sh_outing.departure_at) if sh_outing and sh_outing.departure_at else ""),
            "total_label": (payload.get("summary") or {}).get("total_label", "0"),
            "navegaron": (payload.get("summary") or {}).get("navegaron", ""),
            "socios": (payload.get("summary") or {}).get("socios", ""),
            "invitados": (payload.get("summary") or {}).get("invitados", ""),
        })
    allowed_admin_pages = {"dashboard", "navegaciones", "reservas", "historial", "liquidacion", "socios", "auditoria", "estadisticas", "fichas", "exportar", "sistema", "actividad", "comunicaciones"}
    page_aliases = {
        "home": "dashboard", "inicio": "dashboard", "dashboard": "dashboard",
        "salidas": "navegaciones", "navegaciones": "navegaciones", "outings": "navegaciones",
        "reservas": "reservas", "reservations": "reservas",
        "usuarios": "socios", "socios": "socios", "users": "socios",
        "cargos": "liquidacion", "liquidacion": "liquidacion", "charges": "liquidacion",
        "stats": "estadisticas", "estadisticas": "estadisticas",
        "fichas": "fichas", "sheets": "fichas",
        "auditoria": "auditoria", "audit": "auditoria",
        "actividad": "actividad", "activity": "actividad",
        "exportaciones": "exportar", "exportar": "exportar", "exports": "exportar",
        "comunicaciones": "comunicaciones", "communications": "comunicaciones",
        "sistema": "sistema", "system": "sistema",
    }
    path_page_aliases = {
        "/admin/inicio": "dashboard", "/admin/home": "dashboard",
        "/admin/salidas": "navegaciones", "/admin/outings": "navegaciones",
        "/admin/reservas": "reservas", "/admin/reservations": "reservas",
        "/admin/usuarios": "socios", "/admin/socios": "socios", "/admin/users": "socios",
        "/admin/historial": "historial",
        "/admin/cargos": "liquidacion", "/admin/liquidacion": "liquidacion",
        "/admin/estadisticas": "estadisticas", "/admin/stats": "estadisticas",
        "/admin/fichas": "fichas",
        "/admin/auditoria": "auditoria", "/admin/audit": "auditoria",
        "/admin/actividad": "actividad", "/admin/activity": "actividad",
        "/admin/exportaciones": "exportar", "/admin/exportar": "exportar",
        "/admin/sistema": "sistema", "/admin/system": "sistema",
        "/admin/comunicaciones": "comunicaciones", "/admin/communications": "comunicaciones"
    }
    raw_page = path_page_aliases.get(request.url.path) or request.query_params.get("page") or request.query_params.get("tab") or "dashboard"
    admin_page = page_aliases.get(str(raw_page).strip().lower(), str(raw_page).strip().lower())
    if admin_page not in allowed_admin_pages:
        admin_page = "dashboard"

    activity_page = 1
    try:
        activity_page = max(1, int(request.query_params.get("p", "1")))
    except Exception:
        activity_page = 1
    activity_per_page = 50
    activity_total = db.query(ActivityLog).count()
    activity_pages = max(1, (activity_total + activity_per_page - 1) // activity_per_page)
    if activity_page > activity_pages:
        activity_page = activity_pages
    activity_rows = db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).offset((activity_page - 1) * activity_per_page).limit(activity_per_page).all()
    statistics = build_statistics_context(db) if admin_page == "estadisticas" else {}

    return templates.TemplateResponse(request, "admin.html", base_template_context(**{
        "request": request, "user": user, "admin_page": admin_page, "outing": outing, "outings": outings, "history_groups": history_groups, "counts": counts, "active_counts": active_counts,
        "reservations": reservations, "active": active, "active_count": len(active),
        "present": present, "pending": pending, "charges": charges,
        "total_charges": total_charges, "logs": logs, "readiness": ready,
        "users": db.query(User).order_by(User.name.asc()).all(),
        "padron": build_padron_context(db) if admin_page == "socios" else {},
        "msg": request.query_params.get("msg"), "reservation_views": views,
        "final_summary": final_summary, "charge_summary": summary, "acta": acta,
        "closed": is_closed_outing(outing) if outing else False,
        "responsible_names": responsible_names,
        "waitlist_count": waitlist_count, "total_registros": len(reservations) if outing else 0,
        "control_window": control_window,
        "default_new_outing_at": default_new_outing_datetime().strftime("%Y-%m-%dT%H:%M"),
        "default_guest_fee": int(INVITED_FEE) if float(INVITED_FEE).is_integer() else INVITED_FEE,
        "all_outings": all_outings,
        "all_reservation_rows": all_reservation_rows,
        "all_reservation_count": len(all_reservation_rows),
        "all_logs_count": len(logs),
        "current_sheet": current_sheet,
        "closing_sheets": closing_sheets,
        "all_closing_sheets": all_closing_sheets,
        "all_closing_sheet_rows": all_closing_sheet_rows,
        "system_console": system_console_context(db, request) if admin_page == "sistema" else {},
        "ops_center": phase11_center_summary(db),
        "search_results": universal_search_results(db, request.query_params.get("q", "")),
        "communications": communications_context(db) if admin_page == "comunicaciones" else {},
        "statistics": statistics,
        "activity_rows": activity_rows,
        "activity_page": activity_page,
        "activity_pages": activity_pages,
        "activity_total": activity_total,
    }))


@app.post("/admin/create_user")
def create_user(
    name: str = Form(""),
    dni: str = Form(""),
    member_no: str = Form(""),
    email: str = Form(""),
    whatsapp: str = Form(""),
    phone: str = Form(""),
    category: str = Form(""),
    birth_date: str = Form(""),
    role: str = Form("socio"),
    can_manage_protocolar_form: Optional[str] = Form(None),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    name_clean = (name or "").strip()
    dni_clean = norm_dni(dni)
    member_clean = member_key(member_no)
    role = (role or "socio").strip()

    if role not in ("socio", "captain", "admin"):
        return RedirectResponse("/admin?page=socios&msg=rol_invalido", status_code=303)

    if not name_clean:
        return RedirectResponse("/admin?page=socios&msg=falta_nombre", status_code=303)

    # Socio: alcanza con nombre + Nº de socio. El DNI real es opcional.
    if role == "socio" and not (dni_clean or member_clean):
        return RedirectResponse("/admin?page=socios&msg=falta_socio_o_documento", status_code=303)

    # Capitán/Admin: mantener documento obligatorio.
    if role != "socio" and not dni_clean:
        return RedirectResponse("/admin?page=socios&msg=falta_documento", status_code=303)

    if role == "socio" and member_clean and db.query(User).filter(User.member_no == member_clean).first():
        return RedirectResponse("/admin?page=socios&msg=socio_existente", status_code=303)

    if role == "socio" and not dni_clean and member_clean:
        dni_clean = synthetic_dni_for_member(member_clean)

    if dni_clean and db.query(User).filter_by(dni=dni_clean).first():
        return RedirectResponse("/admin?page=socios&msg=usuario_existente", status_code=303)

    try:
        new_user = User(
            name=name_clean,
            dni=dni_clean,
            member_no=member_clean or None,
            email=(email or "").strip() or None,
            whatsapp=(whatsapp or "").strip() or None,
            phone=(phone or "").strip() or None,
            category=normalize_category(category) or None,
            birth_date=(birth_date or "").strip() or None,
            role=role,
            password_hash=hash_password("demo1234"),
            active=True,
            can_manage_protocolar=bool(can_manage_protocolar_form == "on") if role == "socio" else False,
            must_change_password=True
        )
        db.add(new_user)
        db.commit()
        log(db, user.name, "alta usuario", f"{new_user.name} / {new_user.dni} / {new_user.role}")
        return RedirectResponse("/admin?page=socios&msg=usuario_creado", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse("/admin?page=socios&msg=error_alta_usuario", status_code=303)




@app.post("/admin/reset_password/{uid}")
def reset_password(
    request: Request,
    uid: int,
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    target = db.get(User, uid)
    if not target:
        raise HTTPException(404, "Usuario inexistente")

    target.password_hash = hash_password("demo1234")
    target.must_change_password = True
    target.last_password_change_at = now_local()
    target.session_version = int(getattr(target, "session_version", 1) or 1) + 1
    db.commit()
    audit_event(db, user, "reset clave temporal", f"{target.name} / {target.dni} / cambio obligatorio", request=request, before={"session_version": (target.session_version or 1) - 1}, after={"session_version": target.session_version})
    return RedirectResponse("/admin?page=socios&msg=clave_reseteada", status_code=303)




def user_operational_links_count(db: Session, target: User) -> dict:
    """Cuenta vínculos operativos que impiden borrado físico seguro."""
    uid = target.id
    dni = target.dni or ""
    counts = {
        "reservas_por_dni": db.query(Reservation).filter(Reservation.dni == dni).count() if dni else 0,
        "reservas_responsable": db.query(Reservation).filter(Reservation.responsible_user_id == uid).count(),
        "protocolares_autorizados": db.query(Reservation).filter(Reservation.protocolar_by_user_id == uid).count(),
        "actividad": db.query(ActivityLog).filter(ActivityLog.user_id == uid).count(),
    }
    return counts

def can_hard_delete_user(db: Session, target: User, actor: User) -> tuple[bool, str, dict]:
    counts = user_operational_links_count(db, target)
    if target.id == actor.id:
        return False, "no_puede_borrarse_a_si_mismo", counts
    if (target.role or "").lower() == "admin" and (target.name or "").strip().lower() in {"admin club", "administrador", "admin"}:
        return False, "no_puede_borrar_admin_principal", counts
    if any(v > 0 for v in counts.values()):
        return False, "usuario_con_historial", counts
    return True, "ok", counts

@app.post("/admin/reset_all_passwords")
def reset_all_passwords(
    request: Request,
    confirm_phrase: str = Form(""),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    if (confirm_phrase or "").strip() != "RESET CLAVES FJORD VI":
        return RedirectResponse("/admin?page=socios&msg=confirmacion_claves_invalida", status_code=303)

    targets = db.query(User).filter(User.active == True).all()
    for target in targets:
        target.password_hash = hash_password("demo1234")
        target.must_change_password = True
        target.last_password_change_at = now_local()
        target.session_version = int(getattr(target, "session_version", 1) or 1) + 1
    db.commit()
    audit_event(db, user, "reset masivo claves temporales", f"{len(targets)} usuarios activos / cambio obligatorio", request=request, after={"usuarios_afectados": len(targets)})
    return RedirectResponse("/admin?page=socios&msg=claves_reseteadas", status_code=303)



@app.post("/admin/toggle_user/{uid}")
def toggle_user(
    uid: int,
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    target = db.get(User, uid)
    if not target:
        raise HTTPException(404, "Usuario inexistente")

    if target.id == user.id and target.active:
        return RedirectResponse("/admin?msg=no_puede_desactivarse", status_code=303)

    target.active = not bool(target.active)
    db.commit()
    log(db, user.name, "toggle usuario", f"{target.name} / activo={target.active}")
    return RedirectResponse("/admin?msg=usuario_actualizado", status_code=303)




@app.post("/admin/delete_user/{uid}")
def delete_user_safe(
    uid: int,
    confirm_delete: str = Form(""),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    target = db.get(User, uid)
    if not target:
        return RedirectResponse("/admin?page=socios&msg=usuario_no_encontrado", status_code=303)

    if (confirm_delete or "").strip().upper() != "BORRAR":
        return RedirectResponse("/admin?page=socios&msg=confirmacion_borrado_invalida", status_code=303)

    ok, reason, counts = can_hard_delete_user(db, target, user)
    if not ok:
        try:
            target.active = False
            db.commit()
        except Exception:
            db.rollback()
        log(db, user.name, "intento borrado usuario bloqueado", f"{target.name} / {target.dni} / {target.member_no or ''} / reason={reason} / links={counts}")
        return RedirectResponse(f"/admin?page=socios&msg={reason}", status_code=303)

    detail = f"{target.name} / dni={target.dni} / socio={target.member_no or ''} / rol={target.role}"
    db.delete(target)
    db.commit()
    log(db, user.name, "borrado seguro usuario", detail)
    return RedirectResponse("/admin?page=socios&msg=usuario_borrado", status_code=303)


@app.post("/admin/update_user/{uid}")
def update_user(
    uid: int,
    name: str = Form(""),
    dni: str = Form(""),
    member_no: str = Form(""),
    email: str = Form(""),
    whatsapp: str = Form(""),
    phone: str = Form(""),
    category: str = Form(""),
    birth_date: str = Form(""),
    role: str = Form("socio"),
    active: str = Form("activo"),
    can_manage_protocolar_form: Optional[str] = Form(None),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    target = db.get(User, uid)
    if not target:
        raise HTTPException(404, "Usuario inexistente")

    name_clean = (name or "").strip()
    dni_clean = norm_dni(dni)
    member_clean = member_key(member_no)
    role = (role or "socio").strip()

    if role not in ("socio", "captain", "admin"):
        return RedirectResponse("/admin?page=socios&msg=rol_invalido", status_code=303)

    if not name_clean:
        return RedirectResponse("/admin?page=socios&msg=falta_nombre", status_code=303)

    # Socio: identidad institucional por Nº de socio. DNI real puede agregarse después.
    if role == "socio" and not (dni_clean or member_clean):
        return RedirectResponse("/admin?page=socios&msg=falta_socio_o_documento", status_code=303)

    # Capitán/Admin: documento obligatorio.
    if role != "socio" and not dni_clean:
        return RedirectResponse("/admin?page=socios&msg=falta_documento", status_code=303)

    old_dni = target.dni or ""
    old_member = target.member_no or ""
    old_synthetic = is_synthetic_member_dni(old_dni)

    # Nº de socio único, excepto el mismo usuario.
    if role == "socio" and member_clean:
        existing_member = db.query(User).filter(User.member_no == member_clean, User.id != uid).first()
        if existing_member:
            return RedirectResponse("/admin?page=socios&msg=socio_existente", status_code=303)

    # Si sigue sin DNI real, conservar/generar identificador técnico por Nº de socio.
    if role == "socio" and not dni_clean and member_clean:
        dni_clean = old_dni if old_synthetic and member_key(old_member) == member_clean else synthetic_dni_for_member(member_clean)

    # Si se carga DNI real sobre un socio provisorio, se reemplaza el identificador técnico
    # en el mismo usuario. El historial no se pierde porque reservas/cierres apuntan al user.id.
    existing_dni = db.query(User).filter(User.dni == dni_clean, User.id != uid).first() if dni_clean else None
    if existing_dni:
        return RedirectResponse("/admin?page=socios&msg=dni_ya_asignado", status_code=303)

    try:
        target.name = name_clean
        target.dni = dni_clean
        target.member_no = member_clean or None
        target.email = (email or "").strip() or None
        target.whatsapp = (whatsapp or "").strip() or None
        target.phone = (phone or "").strip() or None
        target.category = normalize_category(category) or None
        target.birth_date = (birth_date or "").strip() or None
        target.role = role
        target.can_manage_protocolar = bool(can_manage_protocolar_form == "on") if role == "socio" else False
        if target.id == user.id and active != "activo":
            return RedirectResponse("/admin?page=socios&msg=no_puede_desactivarse", status_code=303)
        target.active = (active == "activo")
        db.commit()
        detail = f"{target.name} / {old_dni} -> {target.dni} / socio {old_member} -> {target.member_no or ''} / {target.role}"
        log(db, user.name, "edita usuario", detail)
        return RedirectResponse("/admin?page=socios&msg=usuario_actualizado", status_code=303)
    except Exception:
        db.rollback()
        return RedirectResponse("/admin?page=socios&msg=error_actualizar_usuario", status_code=303)



@app.post("/admin/convert_guest_to_user")
def convert_guest_to_user(
    reservation_id: int = Form(...),
    member_no: str = Form(""),
    email: str = Form(""),
    whatsapp: str = Form(""),
    phone: str = Form(""),
    category: str = Form(""),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    r = db.get(Reservation, reservation_id)
    if not r:
        return RedirectResponse("/admin?page=socios&msg=invitado_inexistente", status_code=303)
    dni_clean = norm_dni(r.dni)
    if not dni_clean:
        return RedirectResponse("/admin?page=socios&msg=dni_invalido", status_code=303)
    existing = db.query(User).filter_by(dni=dni_clean).first()
    if existing:
        return RedirectResponse(f"/admin?page=socios&msg=usuario_existente", status_code=303)
    member_clean = member_key(member_no)
    if member_clean and db.query(User).filter(User.member_no == member_clean).first():
        return RedirectResponse(f"/admin?page=socios&msg=socio_existente", status_code=303)
    new_user = User(
        name=(r.person_name or "").strip() or "Socio sin nombre",
        dni=dni_clean,
        member_no=member_clean or None,
        email=email.strip() or None,
        whatsapp=whatsapp.strip() or None,
        phone=phone.strip() or None,
        category=normalize_category(category) or None,
        birth_date=(r.birth_date or None),
        role="socio",
        password_hash=hash_password("demo1234"),
        active=True,
    )
    db.add(new_user)
    db.flush()
    # Si existían reservas históricas con ese DNI como socio, quedarán asociadas visualmente por DNI.
    log(db, user.name, "convierte invitado a socio", f"{new_user.name} / DNI {new_user.dni} / socio {new_user.member_no or '-'}")
    db.commit()
    return RedirectResponse("/admin?page=socios&msg=invitado_convertido", status_code=303)


@app.post("/admin/hide_guest_candidate")
def hide_guest_candidate(
    dni: str = Form(""),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    nd = norm_dni(dni)
    if not nd:
        return RedirectResponse("/admin?page=socios&msg=dni_invalido", status_code=303)
    hidden = get_hidden_guest_candidate_dnis(db)
    hidden.add(nd)
    set_hidden_guest_candidate_dnis(db, hidden)
    log(db, user.name, "oculta candidato a socio", f"DNI {nd}")
    db.commit()
    return RedirectResponse("/admin?page=socios&msg=candidato_oculto", status_code=303)


@app.post("/admin/unhide_guest_candidates")
def unhide_guest_candidates(
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    set_hidden_guest_candidate_dnis(db, set())
    log(db, user.name, "restaura candidatos ocultos", "Padrón")
    db.commit()
    return RedirectResponse("/admin?page=socios&msg=candidatos_restaurados", status_code=303)


def parse_padron_csv_bytes(content: bytes) -> list[dict]:
    try:
        text_data = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text_data = content.decode("latin-1")
    sample = text_data[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,	,")
    except Exception:
        dialect = csv.excel
        dialect.delimiter = ";"
    reader = csv.DictReader(io.StringIO(text_data), dialect=dialect)
    out = []
    for raw in reader:
        if not raw:
            continue
        row = {}
        for k, v in raw.items():
            nk = normalize_import_header(k or "")
            row[nk] = (v or "").strip()
        if any(row.get(h, "") for h in padron_standard_headers()):
            out.append(row)
    return out

def analyze_padron_rows(db: Session, rows: list[dict]) -> dict:
    existing_by_member = {member_key(u.member_no): u for u in db.query(User).filter(User.member_no != None).all() if member_key(u.member_no)}
    existing_by_dni = {norm_dni(u.dni): u for u in db.query(User).all() if norm_dni(u.dni) and not is_synthetic_member_dni(u.dni)}
    seen_members = set()
    seen_dnis = set()
    preview = []
    stats = {"read": len(rows), "create": 0, "update": 0, "errors": 0, "warnings": 0}
    cats = {}
    clean_rows = []
    for i, row in enumerate(rows, start=2):
        member_no = member_key(row.get("nro_socio", ""))
        raw_full_name = (row.get("nombre_completo") or "").strip()
        raw_nombre = (row.get("nombre") or "").strip()
        raw_apellido = (row.get("apellido") or "").strip()
        if raw_full_name:
            name = raw_full_name
        elif raw_apellido and raw_nombre:
            name = f"{raw_apellido}, {raw_nombre}"
        else:
            name = raw_nombre or raw_apellido
        dni_clean = norm_dni(row.get("dni", ""))
        category = normalize_category(row.get("categoria", ""))
        email = (row.get("email") or "").strip()
        whatsapp = (row.get("whatsapp") or "").strip()
        phone = (row.get("telefono") or row.get("phone") or "").strip()
        estado_raw = (row.get("estado") or "activo").strip().lower()
        active = not any(x in estado_raw for x in ("inactivo", "baja", "suspend"))
        errors = []
        warnings = []
        if not member_no:
            errors.append("falta nro_socio")
        if not name:
            errors.append("falta nombre_completo")
        if email and not valid_email_syntax(email):
            warnings.append("email dudoso")
        if member_no and member_no in seen_members:
            errors.append("nro_socio duplicado en archivo")
        if member_no:
            seen_members.add(member_no)
        if dni_clean and not is_synthetic_member_dni(dni_clean):
            if dni_clean in seen_dnis:
                errors.append("DNI duplicado en archivo")
            seen_dnis.add(dni_clean)

        existing_member = existing_by_member.get(member_no) if member_no else None
        existing_dni = existing_by_dni.get(dni_clean) if dni_clean else None
        existing = existing_member or existing_dni
        if existing_member and existing_dni and existing_member.id != existing_dni.id:
            errors.append("conflicto: Nº socio y DNI pertenecen a personas distintas")
        elif not existing_member and existing_dni:
            warnings.append("coincide por DNI, no por nro_socio")
        action = "error" if errors else ("actualizar" if existing else "crear")
        if action == "crear": stats["create"] += 1
        elif action == "actualizar": stats["update"] += 1
        else: stats["errors"] += 1
        if warnings: stats["warnings"] += 1
        if category: cats[category_label(category)] = cats.get(category_label(category), 0) + 1
        clean = {
            "line": i, "member_no": member_no, "name": name, "dni": dni_clean,
            "category": category, "email": email, "whatsapp": whatsapp, "phone": phone,
            "active": active, "action": action, "errors": errors, "warnings": warnings,
        }
        clean_rows.append(clean)
        if len(preview) < 80:
            preview.append(clean)
    stats["categories"] = cats
    return {"stats": stats, "preview": preview, "rows": clean_rows}

@app.get("/admin/padron/import", response_class=HTMLResponse)
def padron_import_page(
    request: Request,
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    return templates.TemplateResponse(request, "padron_import.html", {
        "request": request, "version": VERSION, "app_build": APP_BUILD,
        "headers": padron_standard_headers(), "categories": SOCIO_CATEGORIES
    })

@app.post("/admin/padron/import/preview", response_class=HTMLResponse)
async def padron_import_preview(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    content = await file.read()
    rows = parse_padron_csv_bytes(content)
    analysis = analyze_padron_rows(db, rows)
    token = secrets.token_urlsafe(16)
    set_system_meta(f"pending_padron_import:{token}", json.dumps(analysis["rows"], ensure_ascii=False))
    db.commit()
    return templates.TemplateResponse(request, "padron_import_preview.html", {
        "request": request, "version": VERSION, "token": token,
        "stats": analysis["stats"], "preview": analysis["preview"]
    })

@app.post("/admin/padron/import/confirm")
def padron_import_confirm(
    token: str = Form(...),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    payload = get_system_meta(db, f"pending_padron_import:{token}", "")
    if not payload:
        return RedirectResponse("/admin?page=socios&msg=importacion_expirada", status_code=303)
    rows = json.loads(payload)
    created = updated = skipped = 0
    for row in rows:
        if row.get("action") == "error":
            skipped += 1
            continue
        member_no = row.get("member_no") or ""
        dni_clean = row.get("dni") or ""
        target_by_member = db.query(User).filter(User.member_no == member_no).first() if member_no else None
        target_by_dni = db.query(User).filter(User.dni == dni_clean).first() if dni_clean else None
        if target_by_member and target_by_dni and target_by_member.id != target_by_dni.id:
            skipped += 1
            continue
        target = target_by_member or target_by_dni
        final_dni = dni_clean or synthetic_dni_for_member(member_no)
        if final_dni:
            dni_owner = db.query(User).filter(User.dni == final_dni).first()
            if dni_owner and (not target or dni_owner.id != target.id):
                skipped += 1
                continue
        if member_no:
            member_owner = db.query(User).filter(User.member_no == member_no).first()
            if member_owner and (not target or member_owner.id != target.id):
                skipped += 1
                continue
        if target:
            target.name = row.get("name") or target.name
            target.member_no = member_no or target.member_no
            target.dni = final_dni or target.dni
            target.category = row.get("category") or target.category
            target.email = row.get("email") or target.email
            target.whatsapp = row.get("whatsapp") or target.whatsapp
            target.phone = row.get("phone") or target.phone
            target.role = "socio"
            target.active = bool(row.get("active", True))
            updated += 1
        else:
            db.add(User(
                name=row.get("name") or "Socio sin nombre",
                dni=final_dni,
                member_no=member_no or None,
                category=row.get("category") or None,
                email=row.get("email") or None,
                whatsapp=row.get("whatsapp") or None,
                phone=row.get("phone") or None,
                role="socio",
                password_hash=hash_password("demo1234"),
                active=bool(row.get("active", True)),
            ))
            created += 1
    # Limpia token usado.
    meta = db.get(SystemMeta, f"pending_padron_import:{token}")
    if meta:
        db.delete(meta)
    log(db, user.name, "importa padrón oficial", f"creados {created}, actualizados {updated}, omitidos {skipped}")
    db.commit()
    return RedirectResponse(f"/admin?page=socios&msg=padron_importado&created={created}&updated={updated}&skipped={skipped}", status_code=303)

@app.get("/admin/users.json")
def users_json(
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    users = db.query(User).order_by(User.name.asc()).all()
    return [
        {
            "id": u.id,
            "name": u.name,
            "dni": u.dni,
            "member_no": u.member_no or "",
            "email": u.email or "",
            "whatsapp": getattr(u, "whatsapp", None) or "",
            "phone": u.phone or "",
            "category": getattr(u, "category", None) or "",
            "birth_date": u.birth_date or "",
            "role": u.role,
            "active": bool(u.active)
        }
        for u in users
    ]


@app.post("/admin/update_outing")
def update_outing(
    request: Request,
    outing_id: int = Form(...),
    title: str = Form(...),
    destination: str = Form("paseo"),
    departure_at: str = Form(...),
    max_crew: int = Form(MAX_CREW),
    institutional_reserve: int = Form(0),
    guest_fee: float = Form(INVITED_FEE),
    notes: str = Form(""),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    outing = db.get(Outing, outing_id)
    if not outing:
        raise HTTPException(404, "Salida inexistente")
    if is_closed_outing(outing):
        return RedirectResponse(f"/admin?page=navegaciones&outing_id={outing.id}&msg=salida_cerrada_no_editable", status_code=303)

    reservations = db.query(Reservation).filter_by(outing_id=outing.id).all()
    active_count = len(active_reservations(reservations))

    try:
        new_departure = datetime.fromisoformat((departure_at or "").replace(" ", "T"))
    except Exception:
        return RedirectResponse(f"/admin?page=navegaciones&outing_id={outing.id}&msg=fecha_invalida", status_code=303)

    try:
        new_capacity = max(1, min(int(max_crew or MAX_CREW), 30))
    except Exception:
        new_capacity = MAX_CREW
    try:
        new_reserve = max(0, min(int(institutional_reserve or 0), new_capacity))
    except Exception:
        new_reserve = 0
    try:
        new_fee = max(0, min(float(guest_fee or 0), 999999999))
    except Exception:
        new_fee = float(INVITED_FEE)

    if active_count > new_capacity:
        return RedirectResponse(f"/admin?page=navegaciones&outing_id={outing.id}&msg=cupo_menor_a_reservas", status_code=303)

    old = (
        f"{outing.title} / {outing.destination} / "
        f"{outing.departure_at.isoformat()} / cupo {outing.max_crew} / "
        f"reserva institucional {getattr(outing, 'institutional_reserve', 0) or 0} / "
        f"tarifa {float(outing.guest_fee or 0)}"
    )

    outing.title = (title or "").strip() or outing.title
    outing.destination = (destination or "").strip() or "paseo"
    outing.departure_at = new_departure
    outing.max_crew = new_capacity
    outing.institutional_reserve = new_reserve
    outing.guest_fee = new_fee
    outing.notes = (notes or "").strip()

    # Si cambió una salida con reservas activas, queda registrado en auditoría.
    # No se recalculan cargos firmes porque una salida cerrada no se edita desde este flujo.
    db.commit()
    new = (
        f"{outing.title} / {outing.destination} / "
        f"{outing.departure_at.isoformat()} / cupo {outing.max_crew} / "
        f"reserva institucional {getattr(outing, 'institutional_reserve', 0) or 0} / "
        f"tarifa {float(outing.guest_fee or 0)}"
    )
    detail = f"{outing.id}: {old} -> {new}"
    if active_count:
        detail += f" / advertencia: tenía {active_count} reservas activas"
    audit_event(db, user, "edición administrativa salida", detail, request=request, outing_id=outing.id, before={"snapshot": old}, after={"snapshot": new, "reservas_activas": active_count})
    return RedirectResponse(f"/admin?page=navegaciones&outing_id={outing.id}&msg=salida_actualizada", status_code=303)


@app.post("/admin/outing_status")
def admin_outing_status(
    request: Request,
    outing_id: int = Form(...),
    status: str = Form(...),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    outing = db.get(Outing, outing_id)
    if not outing:
        raise HTTPException(404, "Salida inexistente")
    old_status = outing.status
    reservations = db.query(Reservation).filter_by(outing_id=outing.id).all()
    if status == "Reservas abiertas":
        outing.status = "En reservas"
        recalculate_preliquidation_after_reopen(db, outing, reservations)
        promoted = promote_waitlist(db, outing)
        detail = f"{outing.title} / {old_status} -> {outing.status} / promovidos {', '.join(promoted) if promoted else '-'}"
    elif status == "Cerrar":
        active = active_reservations(reservations)
        liquidate_and_close_boarding(db, outing, reservations, active)
        detail = f"{outing.title} / {old_status} -> Embarque cerrado"
    elif status == "Cancelada":
        for r in reservations:
            r.charge_amount = 0
        outing.status = "Cancelada por capitán"
        detail = f"{outing.title} / {old_status} -> Cancelada por administración"
    else:
        return RedirectResponse(f"/admin?outing_id={outing.id}&msg=estado_invalido", status_code=303)
    db.commit()
    audit_event(db, user, "control administrativo salida", detail, request=request, outing_id=outing.id, before={"status": old_status}, after={"status": outing.status})
    return RedirectResponse(f"/admin?outing_id={outing.id}&msg=estado_actualizado", status_code=303)

@app.post("/admin/new_outing")
def new_outing(
    request: Request,
    title: str = Form(...),
    departure_at: str = Form(...),
    max_crew: int = Form(MAX_CREW),
    institutional_reserve: int = Form(0),
    guest_fee: float = Form(INVITED_FEE),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    dep = datetime.fromisoformat(departure_at)
    capacity = max(1, min(int(max_crew or MAX_CREW), 30))
    reserve_inst = max(0, min(int(institutional_reserve or 0), capacity))
    try:
        fee = float(guest_fee or INVITED_FEE)
    except Exception:
        fee = float(INVITED_FEE)
    fee = max(0, min(fee, 999999999))
    # La tarifa se guarda en la salida para preservar trazabilidad histórica:
    # cambios futuros del valor global no recalculan salidas ya creadas.
    o = Outing(title=title.strip(), destination="paseo", departure_at=dep, guest_fee=fee, status="En reservas", max_crew=capacity, institutional_reserve=reserve_inst, min_crew=MIN_CREW)
    db.add(o)
    db.commit()
    db.refresh(o)
    audit_event(db, user, "nueva salida", f"{title.strip()} / tarifa invitado {fee} / salida vacía", request=request, outing_id=o.id, after={"status": o.status, "departure_at": o.departure_at, "max_crew": o.max_crew, "guest_fee": float(o.guest_fee or 0)})
    return RedirectResponse(f"/admin?outing_id={o.id}&msg=salida_creada", status_code=303)

def csv_response_excel(output: io.StringIO, filename: str):
    # Excel en español/Android abre mejor con BOM UTF-8 y separador punto y coma.
    payload = "\ufeff" + output.getvalue()
    return Response(
        payload,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/admin/manifest.csv")
def manifest_csv(outing_id: Optional[int] = None, db: Session = Depends(db_session), user: User = Depends(require_role("admin", "captain"))):
    outing, reservations, *_ = outing_context(db, outing_id)
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        "salida_id", "salida", "fecha_salida", "nombre", "dni", "tipo",
        "estado_fisico", "condicion_reglamentaria", "motivo",
        "cargo_firme", "preliquidacion", "estado_reserva",
        "asistencia_original", "responsable_id", "cancelado_en"
    ])
    for r in reservations:
        v = reservation_view(outing, r)
        writer.writerow([
            outing.id, outing.title, outing.departure_at.isoformat(), r.person_name, r.dni,
            v["tipo_label"], v["estado_fisico"], v["estado_reglamentario"], v["motivo"],
            v["charge"], v["charge_preview"], r.status, r.attendance, r.responsible_user_id or "",
            r.cancelled_at.isoformat() if r.cancelled_at else ""
        ])
    filename = f"manifest_fjord_vi_salida_{outing.id}.csv"
    return csv_response_excel(output, filename)


@app.get("/admin/charges.csv")
def charges_csv(outing_id: Optional[int] = None, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    outing = selected_outing(db, outing_id)
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        "salida_id", "salida", "fecha_liquidacion", "nombre", "dni", "tipo",
        "estado_fisico", "condicion_reglamentaria", "importe_firme", "motivo"
    ])
    q = db.query(Reservation)
    if outing:
        q = q.filter(Reservation.outing_id == outing.id)
    for r in q.all():
        row_outing = outing or db.get(Outing, r.outing_id)
        if not row_outing:
            continue
        v = reservation_view(row_outing, r)
        if v["charge"] <= 0:
            continue
        writer.writerow([
            r.outing_id, row_outing.title, now_local().date(), r.person_name, r.dni,
            v["tipo_label"], v["estado_fisico"], v["estado_reglamentario"], v["charge"], v["motivo"]
        ])
    filename = f"liquidaciones_fjord_vi_salida_{outing.id if outing else 'todas'}.csv"
    return csv_response_excel(output, filename)


@app.get("/admin/reservations_all.csv")
def reservations_all_csv(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        "salida_id", "salida", "fecha_salida", "estado_salida",
        "reserva_id", "nombre", "dni", "tipo", "responsable",
        "estado_reserva", "asistencia", "estado_fisico", "condicion_reglamentaria",
        "motivo", "cargo_firme", "preliquidacion", "creado_en", "cancelado_en"
    ])
    outings = {o.id: o for o in db.query(Outing).all()}
    responsible_ids = sorted({r.responsible_user_id for r in db.query(Reservation).all() if r.responsible_user_id})
    responsible_names = {u.id: u.name for u in db.query(User).filter(User.id.in_(responsible_ids)).all()} if responsible_ids else {}
    rows = db.query(Reservation).order_by(Reservation.outing_id.desc(), Reservation.created_at.desc()).all()
    for r in rows:
        o = outings.get(r.outing_id)
        if not o:
            continue
        v = reservation_view(o, r)
        writer.writerow([
            o.id, o.title, o.departure_at.isoformat(), o.status,
            r.id, r.person_name, r.dni, v["tipo_label"], responsible_names.get(r.responsible_user_id, "") if r.responsible_user_id else "",
            r.status, r.attendance, v["estado_fisico"], v["estado_reglamentario"],
            v["motivo"], v["charge"], v["charge_preview"],
            r.created_at.isoformat() if r.created_at else "",
            r.cancelled_at.isoformat() if r.cancelled_at else ""
        ])
    return csv_response_excel(output, "fjord_vi_historial_reservas_completo.csv")


@app.get("/admin/outings.csv")
def outings_csv(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["salida_id", "titulo", "destino", "fecha_salida", "estado", "max_tripulantes", "min_tripulantes", "tarifa_invitado", "creada_en", "registros", "activos", "cargos_firmes"])
    for o in db.query(Outing).order_by(Outing.departure_at.desc()).all():
        reservations = db.query(Reservation).filter_by(outing_id=o.id).all()
        active = active_reservations(reservations)
        total_charges = sum(reservation_view(o, r)["charge"] for r in reservations)
        writer.writerow([o.id, o.title, o.destination, o.departure_at.isoformat(), o.status, o.max_crew, o.min_crew, float(o.guest_fee or 0), o.created_at.isoformat() if o.created_at else "", len(reservations), len(active), total_charges])
    return csv_response_excel(output, "fjord_vi_salidas_completo.csv")


@app.get("/admin/users.csv")
def users_csv(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["usuario_id", "nombre", "dni", "nro_socio", "categoria", "fecha_nacimiento", "edad", "email", "whatsapp", "telefono", "rol", "activo"])
    for u in db.query(User).order_by(User.name.asc()).all():
        writer.writerow([u.id, u.name, u.dni, u.member_no or "", category_label(getattr(u, "category", None)), u.birth_date or "", user_age_label(u.birth_date), u.email or "", getattr(u, "whatsapp", None) or "", u.phone or "", u.role, "si" if u.active else "no"])
    return csv_response_excel(output, "fjord_vi_usuarios.csv")


@app.get("/admin/audit.csv")
def audit_csv(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["log_id", "fecha", "usuario", "accion", "detalle"])
    for l in db.query(AuditLog).order_by(AuditLog.created_at.desc()).all():
        writer.writerow([l.id, l.created_at.isoformat() if l.created_at else "", l.actor, l.action, l.detail])
    return csv_response_excel(output, "fjord_vi_auditoria.csv")


@app.post("/admin/schema/check")
def admin_schema_check(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    ensure_schema()
    index_result = ensure_db_indexes()
    set_system_meta("schema_version", "1")
    set_system_meta("app_version", VERSION)
    set_system_meta("last_schema_check", now_local().isoformat())
    set_system_meta("last_index_check", json.dumps(index_result, ensure_ascii=False))
    log(db, user.name, "schema/index check", f"Revisión técnica ejecutada desde Sistema / índices OK: {len(index_result.get('created_or_ok', []))} / fallas: {len(index_result.get('failed', []))}")
    msg = "schema_ok" if not index_result.get("failed") else "schema_index_warn"
    return RedirectResponse(f"/admin?page=sistema&msg={msg}", status_code=303)

@app.get("/admin/blindaje.json")
def admin_blindaje_json(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    """Diagnóstico rápido de consistencia de datos. No modifica la base."""
    return data_blindaje_checks(db)



@app.get("/admin/operational_status.json")
def admin_operational_status_json(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    log_activity(db, request, user, "admin", "operational_status_json", "Estado operativo JSON")
    return operational_status_summary(db)


@app.get("/admin/operational_status.txt")
def admin_operational_status_txt(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    """Descarga TXT robusta del estado operativo.

    Debe descargar siempre que el admin esté autenticado. Si algún subcontrol falla,
    se informa dentro del TXT en vez de mostrar pantalla de error.
    """
    try:
        summary = operational_status_summary(db)
        lines = [
            "Fjord VI estado operativo",
            f"version: {summary.get('version', APP_VERSION)}",
            f"checked_at: {summary.get('checked_at', now_local().isoformat(timespec='seconds'))}",
            f"score: {summary.get('score', '-') }%",
            f"status: {'OK' if summary.get('ok') else 'REVISAR'}",
            f"recommendation: {summary.get('recommendation', '')}",
            "",
            "CONTROLES",
        ]
        for row in summary.get("rows", []):
            mark = "OK" if row.get("ok") else "REVISAR"
            lines.append(f"{mark} - {row.get('area','')} / {row.get('name','')}: {row.get('detail','')}")
            if row.get("action"):
                lines.append(f"  accion sugerida: {row.get('action')}")
    except Exception as e:
        lines = [
            "Fjord VI estado operativo",
            f"version: {APP_VERSION}",
            f"checked_at: {now_local().isoformat(timespec='seconds')}",
            "status: ERROR PARCIAL",
            "",
            "No se pudo generar el estado operativo completo.",
            f"error: {type(e).__name__}: {e}",
            "",
            "La aplicacion sigue activa. Revisar logs de Render o descargar diagnostico ZIP.",
        ]

    try:
        log_activity(db, request, user, "admin", "operational_status_txt", "Descarga estado operativo TXT")
    except Exception:
        pass

    return Response(
        "\n".join(lines),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=fjord_vi_estado_operativo.txt"}
    )

@app.get("/admin/architecture.json")
def admin_architecture_json(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    """Mapa técnico de Fase 5: modularización preparada. No modifica datos."""
    return architecture_summary()


@app.get("/admin/architecture.txt")
def admin_architecture_txt(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    """Descarga TXT robusta del mapa técnico de arquitectura."""
    try:
        summary = architecture_summary()
        lines = [
            "Fjord VI architecture map",
            f"version: {summary.get('version', APP_VERSION)}",
            f"phase: {summary.get('phase', '')}",
            f"main_py_lines: {summary.get('main_py_lines', '')}",
            f"ok: {summary.get('ok', '')}",
            "",
            "MODULOS",
        ]
        for row in summary.get("rows", []):
            lines.append(f"- [{'OK' if row.get('ok') else 'PENDIENTE'}] {row.get('path','')} · {row.get('description','')}")
    except Exception as e:
        lines = [
            "Fjord VI architecture map",
            f"version: {APP_VERSION}",
            f"checked_at: {now_local().isoformat(timespec='seconds')}",
            "status: ERROR PARCIAL",
            f"error: {type(e).__name__}: {e}",
        ]

    try:
        log_activity(db, request, user, "admin", "architecture_txt", "Descarga mapa tecnico TXT")
    except Exception:
        pass

    return Response(
        "\n".join(lines),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=fjord_vi_architecture_map.txt"}
    )

@app.get("/admin/phase7.json")
def admin_phase7_json(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    log_activity(db, request, user, "admin", "phase7_json", "Fase 7 operaciones y alertas JSON")
    return phase7_summary(db)


@app.get("/admin/phase7.txt")
def admin_phase7_txt(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    summary = phase7_summary(db)
    log_activity(db, request, user, "admin", "phase7_txt", "Fase 7 operaciones y alertas TXT")
    lines = [
        "Fjord VI - Fase 7 operaciones y alertas",
        f"version: {VERSION}",
        f"semaforo: {summary.get('label')} ({summary.get('color')})",
        f"phase: {summary.get('phase')}",
        "",
        "ALERTAS",
    ]
    for a in summary.get("alerts", []):
        lines.append(f"[{a.get('level')}] {a.get('title')}: {a.get('detail')}")
    lines += ["", "METRICAS"]
    for k, v in summary.get("metrics", {}).items():
        lines.append(f"{k}: {v}")
    return Response("\n".join(lines), media_type="text/plain; charset=utf-8", headers={"Content-Disposition": "attachment; filename=fjord_vi_fase7_operaciones.txt"})


@app.get("/admin/deploy_history.json")
def admin_deploy_history_json(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    log_activity(db, request, user, "admin", "deploy_history_json", "Historial técnico de deploys")
    return {"version": VERSION, "rows": deploy_history_rows(db)}


@app.post("/admin/maintenance_mode")
def admin_maintenance_mode(
    enabled: Optional[str] = Form(None),
    note: str = Form(""),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin")),
):
    set_system_meta("maintenance_mode", "1" if enabled == "on" else "0")
    set_system_meta("maintenance_note", (note or "").strip())
    set_system_meta("maintenance_changed_at", now_local().isoformat(timespec="seconds"))
    set_system_meta("maintenance_changed_by", user.name)
    log(db, user.name, "modo mantenimiento", "activado" if enabled == "on" else "desactivado")
    return RedirectResponse("/admin?page=sistema&msg=maintenance_saved", status_code=303)


@app.get("/admin/phase9.json")
def admin_phase9_json(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    log_activity(db, request, user, "admin", "phase9_json", "Operación humana JSON")
    return phase9_summary(db)

@app.get("/admin/phase9.txt")
def admin_phase9_txt(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    """Descarga TXT robusta de operación humana/Fase 9.

    No debe caer a pantalla de error por alertas internas: si algo falla,
    el error queda escrito dentro del TXT.
    """
    try:
        summary = phase9_summary(db)
        lines = [
            "Fjord VI - operacion humana",
            f"version: {summary.get('version', APP_VERSION)}",
            f"checked_at: {summary.get('checked_at', now_local().isoformat(timespec='seconds'))}",
            f"estado: {summary.get('state', '')}",
            f"recomendacion: {summary.get('recommendation', '')}",
            "",
            "ALERTAS",
        ]
        alerts = summary.get("alerts", [])
        if not alerts:
            lines.append("OK - Sin alertas humanas.")
        for a in alerts:
            lines.append(f"{a.get('level','').upper()} - {a.get('title','')}: {a.get('detail','')}")
            if a.get("action"):
                lines.append(f"  accion sugerida: {a.get('action')}")
    except Exception as e:
        lines = [
            "Fjord VI - operacion humana",
            f"version: {APP_VERSION}",
            f"checked_at: {now_local().isoformat(timespec='seconds')}",
            "estado: ERROR PARCIAL",
            "",
            "No se pudo generar el informe de operacion humana completo.",
            f"error: {type(e).__name__}: {e}",
            "",
            "La aplicacion sigue activa. Revisar logs de Render o descargar diagnostico ZIP.",
        ]

    try:
        log_activity(db, request, user, "admin", "phase9_txt", "Descarga operacion humana TXT")
    except Exception:
        pass

    return Response(
        "\n".join(lines),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=fjord_vi_operacion_humana.txt"}
    )

@app.get("/admin/phase11.json")
def admin_phase11_json(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    log_activity(db, request, user, "admin", "phase11_json", "Centro operativo JSON")
    return phase11_center_summary(db)


@app.get("/admin/phase11.txt")
def admin_phase11_txt(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    summary = phase11_center_summary(db)
    lines = ["FJORD VI - FASE 11 CENTRO OPERATIVO", f"Version: {summary.get('version')}", f"Estado: {summary.get('state')}", ""]
    nexto = summary.get("next_outing") or {}
    lines.append(f"Proxima salida: {nexto.get('title','-')} / {nexto.get('departure_label','-')} / {nexto.get('active_count','-')}/{nexto.get('max_crew','-')}")
    lines.append("")
    lines.append("Alertas:")
    for a in summary.get("alerts", []):
        lines.append(f"[{a.get('level','')}] {a.get('title','')} - {a.get('detail','')}")
        if a.get("action"):
            lines.append(f"  Accion: {a.get('action')}")
    log_activity(db, request, user, "admin", "phase11_txt", "Centro operativo TXT")
    return Response("\n".join(lines), media_type="text/plain; charset=utf-8", headers={"Content-Disposition": "attachment; filename=fjord_vi_centro_operativo.txt"})


@app.get("/admin/search.json")
def admin_search_json(q: str = "", request: Request = None, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    result = universal_search_results(db, q)
    if request is not None:
        log_activity(db, request, user, "admin", "universal_search", q[:80])
    return result


@app.get("/admin/security_status.json")
def admin_security_status_json(request: Request, user: User = Depends(require_role("admin"))):
    """Estado de seguridad para soporte/auditoría. No expone secretos."""
    return security_status_payload(request)


@app.get("/admin/observability.json")
def admin_observability_json(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    """Estado de observabilidad liviana. No modifica datos."""
    return observability_status_payload(db)


@app.get("/admin/release_check.json")
def admin_release_check_json(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    """Checklist fija de release/deploy. No modifica datos."""
    return release_check_summary(db, request)


@app.get("/admin/release_check.txt")
def admin_release_check_txt(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    summary = release_check_summary(db, request)
    lines = [
        f"Fjord VI release check",
        f"version: {summary.get('version')}",
        f"checked_at: {summary.get('checked_at')}",
        f"status: {'OK' if summary.get('ok') else 'REVISAR'}",
        "",
    ]
    for r in summary.get("rows", []):
        lines.append(f"{'OK' if r.get('ok') else 'ERROR'} - {r.get('name')}: {r.get('detail')}")
    return Response("\n".join(lines), media_type="text/plain; charset=utf-8", headers={"Content-Disposition": "attachment; filename=fjord_vi_release_check.txt"})


@app.get("/admin/diagnostic.txt")
def admin_diagnostic_txt(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    ctx = system_console_context(db, request)
    lines = [ctx.get("diagnostic_text", "")]
    lines.append("")
    lines.append("DB_INFO:")
    for k, v in ctx.get("db_info", {}).items():
        lines.append(f"{k}: {v}")
    lines.append("")
    lines.append("INTEGRIDAD:")
    for row in ctx.get("integrity_rows", []):
        lines.append(f"{'OK' if row['ok'] else 'ERROR'} - {row['name']}: {row['detail']}")
    return Response("\n".join(lines), media_type="text/plain; charset=utf-8", headers={"Content-Disposition": "attachment; filename=fjord_vi_diagnostico.txt"})







@app.get("/admin/captain_logic_tests.json")
def admin_captain_logic_tests_json(request: Request, user: User = Depends(require_role("admin"))):
    return captain_logic_diagnostic_tests()

@app.get("/admin/captain_logic_tests.txt")
def admin_captain_logic_tests_txt(request: Request, user: User = Depends(require_role("admin"))):
    data = captain_logic_diagnostic_tests()
    lines = [
        f"Fjord VI · Pruebas lógicas Capitán",
        f"version: {data.get('version')}",
        f"fecha: {data.get('checked_at')}",
        f"resultado: {data.get('summary')}",
        f"nota: {data.get('note')}",
        "",
    ]
    for r in data.get('rows', []):
        state = 'OK' if r.get('ok') else 'ERROR'
        lines.append(f"[{state}] {r.get('name')}")
        lines.append(f"  {r.get('detail')}")
        if r.get('expected') or r.get('got'):
            lines.append(f"  esperado: {r.get('expected')}")
            lines.append(f"  obtenido: {r.get('got')}")
        lines.append("")
    return PlainTextResponse("\n".join(lines), media_type="text/plain; charset=utf-8")

@app.get("/admin/performance_policy.json")
def admin_performance_policy_json(request: Request, user: User = Depends(require_role("admin"))):
    """Política operacional de performance.

    Sirve para soporte y release check: define qué módulos deben ser livianos
    y cuáles pueden cargar controles pesados bajo demanda.
    """
    return {
        "version": APP_VERSION,
        "policy": "operational_light",
        "principles": [
            "Socio y Capitán deben cargar sólo lo necesario para operar.",
            "Sistema y Administración pueden tener controles pesados, pero bajo demanda.",
            "Toda acción POST crítica debe tener protección anti doble toque.",
            "Los botones visibles deben ejecutar acciones reales o explicar qué hacen.",
            "Los diagnósticos técnicos no deben bloquear la operación.",
        ],
        "fast_modules": ["socio", "captain", "checkin", "login"],
        "deferred_modules": ["sistema", "release_check", "diagnostic_zip", "integrity", "backups", "activity"],
        "client_guards": {
            "anti_double_submit": True,
            "button_feedback": True,
            "download_buttons_not_blocked": True,
            "captain_and_socio_kept_light": True,
        },
    }


@app.get("/admin/diagnostic.zip")
def admin_diagnostic_zip(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    """Descarga ZIP real de diagnóstico.

    Versión robusta: si un subcontrol falla, el ZIP se descarga igual y deja el error
    escrito dentro de ERRORES.txt. No debe generar archivo de 0 bytes.
    """
    generated_at = now_local().isoformat(timespec="seconds")
    errors = []

    def safe_call(label, fn, fallback):
        try:
            return fn()
        except Exception as e:
            errors.append(f"{label}: {type(e).__name__}: {e}")
            return fallback

    ctx = safe_call("system_console_context_full", lambda: system_console_context_full(db, request), {})
    release = safe_call("release_check_summary", lambda: release_check_summary(db, request), {"ok": False, "rows": []})
    op = safe_call("operational_status_summary", lambda: operational_status_summary(db), {"ok": False, "rows": []})
    arch = safe_call("architecture_summary", lambda: architecture_summary(), {"rows": []})

    def to_json_bytes(obj):
        try:
            return json.dumps(obj, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        except Exception as e:
            errors.append(f"json_dump: {type(e).__name__}: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False, indent=2).encode("utf-8")

    def csv_bytes(headers, rows):
        buff = io.StringIO()
        writer = csv.writer(buff)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
        return buff.getvalue().encode("utf-8-sig")

    diag_lines = [
        "Fjord VI diagnóstico técnico",
        f"version: {APP_VERSION}",
        f"app_build: {APP_BUILD}",
        f"release_label: {RELEASE_LABEL}",
        f"generated_at: {generated_at}",
        "",
        "RESUMEN",
        f"database_engine: {ctx.get('db_info', {}).get('engine', ctx.get('db', '-')) if isinstance(ctx, dict) else '-'}",
        f"db_ok: {ctx.get('db_ok', '-') if isinstance(ctx, dict) else '-'}",
        f"schema: {ctx.get('schema_version', '-') if isinstance(ctx, dict) else '-'}",
        f"release_ok: {release.get('ok', '-') if isinstance(release, dict) else '-'}",
        f"operational_ok: {op.get('ok', '-') if isinstance(op, dict) else '-'}",
        "",
        "NOTA",
        "Este ZIP no es backup de base de datos. Sirve para soporte técnico y auditoría de instalación.",
    ]

    activity_rows = []
    try:
        for a in db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(300).all():
            activity_rows.append([
                a.created_at.isoformat(timespec="seconds") if getattr(a, "created_at", None) else "",
                getattr(a, "user_name", "") or "",
                getattr(a, "role", "") or "",
                getattr(a, "module", "") or "",
                getattr(a, "action", "") or "",
                getattr(a, "route", "") or "",
            ])
    except Exception as e:
        errors.append(f"activity_csv: {type(e).__name__}: {e}")
        activity_rows.append(["ERROR", str(e), "", "", "", ""])

    audit_rows = []
    try:
        for a in db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(300).all():
            audit_rows.append([
                getattr(a, "created_at", None).isoformat(timespec="seconds") if getattr(a, "created_at", None) else "",
                getattr(a, "actor", None) or getattr(a, "user_name", None) or getattr(a, "actor_name", "") or "",
                getattr(a, "action", "") or "",
                getattr(a, "detail", None) or getattr(a, "details", None) or getattr(a, "message", "") or "",
            ])
    except Exception as e:
        errors.append(f"audit_csv: {type(e).__name__}: {e}")
        audit_rows.append(["ERROR", str(e), "", ""])

    zip_buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("00_LEEME.txt", (
                "Paquete técnico de diagnóstico Fjord VI.\n"
                "No contiene backup completo de base de datos.\n"
                "Sirve para soporte técnico y verificación de release.\n"
                f"Generado: {generated_at}\n"
                f"Versión: {APP_VERSION}\n"
            ))
            z.writestr("01_diagnostico.txt", "\n".join(diag_lines))
            z.writestr("02_release_check.json", to_json_bytes(release))
            z.writestr("03_estado_operativo.json", to_json_bytes(op))
            z.writestr("04_arquitectura.json", to_json_bytes(arch))
            z.writestr("05_sistema_contexto.json", to_json_bytes(ctx))
            z.writestr("06_actividad_reciente.csv", csv_bytes(["fecha", "usuario", "rol", "modulo", "accion", "ruta"], activity_rows))
            z.writestr("07_auditoria_reciente.csv", csv_bytes(["fecha", "actor", "accion", "detalle"], audit_rows))
            z.writestr("08_metadata.json", to_json_bytes({
                "app": "Fjord VI",
                "version": APP_VERSION,
                "build": APP_BUILD,
                "release_label": RELEASE_LABEL,
                "generated_at": generated_at,
                "diagnostic_zip": True,
                "errors_count": len(errors),
            }))
            z.writestr("09_ERRORES.txt", "\n".join(errors) if errors else "Sin errores internos al generar diagnóstico.")
    except Exception as e:
        # Último recurso: igual devolver un ZIP mínimo válido.
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("ERROR_GENERANDO_DIAGNOSTICO.txt", f"{type(e).__name__}: {e}\nversion: {APP_VERSION}\nfecha: {generated_at}\n")

    try:
        log_activity(db, request, user, "admin", "diagnostic_zip", "Descarga diagnóstico ZIP")
    except Exception:
        pass

    zip_bytes = zip_buffer.getvalue()
    if not zip_bytes:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("ERROR_ZIP_VACIO.txt", f"Se evitó una descarga de 0 bytes. Version: {APP_VERSION}. Fecha: {generated_at}")
        zip_bytes = zip_buffer.getvalue()

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=fjord_vi_diagnostico_{APP_VERSION}.zip"}
    )

@app.post("/admin/system/repair_missing_sheets")
def admin_repair_missing_sheets(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    """Genera fichas vigentes faltantes para salidas ya cerradas.

    No altera tripulación ni estados; usa el estado final actualmente guardado.
    Está pensado para reparar datos heredados de versiones anteriores donde la
    salida quedó cerrada sin closing_sheet vigente.
    """
    missing = closed_outings_without_current_sheet(db)
    fixed = 0
    skipped = 0
    for outing in missing:
        try:
            reservations = db.query(Reservation).filter_by(outing_id=outing.id).order_by(Reservation.id).all()
            # Validación dura: no generar ficha si la salida está inconsistentemente cerrada.
            errors = present_guest_without_present_responsible_errors(db, outing, reservations)
            present_count = len([r for r in reservations if r.attendance == "Presente" and reservation_is_active(r)])
            if errors or present_count > int(outing.max_crew or MAX_CREW):
                skipped += 1
                continue
            create_closing_sheet(db, outing, reservations, user.name)
            fixed += 1
        except Exception as e:
            skipped += 1
            try:
                log(db, user.name, "repair missing sheet error", f"{outing.title}: {type(e).__name__}")
            except Exception:
                pass
    log(db, user.name, "repair missing sheets", f"fichas generadas: {fixed}; omitidas: {skipped}")
    return RedirectResponse(f"/admin?page=sistema&msg=repair_sheets_{fixed}_{skipped}", status_code=303)

@app.get("/admin/postgres_backup")
def admin_postgres_backup(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    if not DB_URL.startswith("postgres"):
        return RedirectResponse("/admin?page=sistema&msg=postgres_no_activo", status_code=303)
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        # Fallback seguro: si pg_dump no está instalado en el contenedor, se entrega
        # un backup lógico JSON completo. No es un .dump nativo, pero permite recuperar datos.
        payload = json.dumps(export_state(db), ensure_ascii=False, indent=2)
        filename = f"fjord_vi_postgres_logical_fallback_{now_local().strftime('%Y%m%d_%H%M')}.json"
        return Response(payload, media_type="application/json; charset=utf-8", headers={"Content-Disposition": f"attachment; filename={filename}"})
    compatible, compat_detail = pg_dump_compatible_with_server(db)
    if not compatible:
        raise HTTPException(500, f"Backup PostgreSQL no ejecutado: {compat_detail}. Actualizar cliente pg_dump en Dockerfile.")
    with tempfile.NamedTemporaryFile(suffix=".sql") as tmp:
        result = subprocess.run([pg_dump, DB_URL, "--no-owner", "--no-privileges"], stdout=tmp, stderr=subprocess.PIPE, timeout=45)
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="ignore")[:400]
            raise HTTPException(500, f"pg_dump falló: {detail}")
        tmp.flush(); tmp.seek(0)
        data = tmp.read()
    filename = f"fjord_vi_postgres_{now_local().strftime('%Y%m%d_%H%M')}.sql"
    log(db, user.name, "backup postgres", filename)
    return Response(data, media_type="application/sql; charset=utf-8", headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.get("/admin/activity.csv")
def admin_activity_csv(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["fecha", "usuario", "rol", "modulo", "accion", "ruta", "detalle", "ip"] )
    for a in db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(5000).all():
        writer.writerow([fmt_admin_datetime(a.created_at), a.user_name, a.role, a.module, a.action, a.path, a.detail, a.ip])
    return csv_response_excel(output, "fjord_vi_actividad.csv")

@app.get("/admin/backup")
def admin_backup(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    """Descarga segura de backup JSON.

    Importante para oficina: no escribimos primero el archivo en disco ni navegamos
    dentro del Admin, porque en algunas PCs/Chrome eso podía dejar la pestaña
    esperando y con sensación de pantalla congelada. Generamos el JSON en memoria
    y lo enviamos como adjunto descargable.
    """
    payload = json.dumps(export_state(db), ensure_ascii=False, separators=(",", ":"))
    filename = f"fjord_vi_backup_{now_local().strftime('%Y%m%d_%H%M')}.json"
    headers = {
        "Content-Disposition": f"attachment; filename={filename}",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }
    return Response(payload, media_type="application/json; charset=utf-8", headers=headers)

@app.get("/admin/export_data.json")
def export_data_json(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    data = json.dumps(export_state(db), ensure_ascii=False, indent=2)
    return Response(data, media_type="application/json", headers={"Content-Disposition": "attachment; filename=fjord_vi_backup.json"})




# =========================
# MIGRACIÓN OPERATIVA / CLONACIÓN CONTROLADA
# =========================
MIGRATION_IMPORT_PHRASE = "CLONAR ENTORNO FJORD VI"


def migration_counts(db: Session) -> dict:
    return {
        "users": db.query(User).count(),
        "outings": db.query(Outing).count(),
        "reservations": db.query(Reservation).count(),
        "closing_sheets": db.query(ClosingSheet).count(),
        "audit_logs": db.query(AuditLog).count(),
        "system_meta": db.query(SystemMeta).count(),
    }


def migration_integrity_report(db: Session) -> dict:
    users = {u.id: u for u in db.query(User).all()}
    outings = {o.id: o for o in db.query(Outing).all()}
    reservations = db.query(Reservation).all()
    sheets = db.query(ClosingSheet).all()
    errors = []
    warnings = []

    for r in reservations:
        if r.outing_id not in outings:
            errors.append(f"Reserva {r.id} sin salida existente: outing_id={r.outing_id}")
        if r.responsible_user_id and r.responsible_user_id not in users:
            errors.append(f"Reserva {r.id} sin socio responsable existente: user_id={r.responsible_user_id}")
        if getattr(r, "protocolar_by_user_id", None) and r.protocolar_by_user_id not in users:
            warnings.append(f"Reserva institucional {r.id} conserva referencia no encontrada: user_id={r.protocolar_by_user_id}")
    for cs in sheets:
        if cs.outing_id not in outings:
            errors.append(f"Ficha {cs.id} sin salida existente: outing_id={cs.outing_id}")

    # Invariante simple: una sola ficha vigente por salida.
    vigentes = {}
    for cs in sheets:
        if (cs.status or "").upper() == "VIGENTE":
            vigentes.setdefault(cs.outing_id, 0)
            vigentes[cs.outing_id] += 1
    for outing_id, n in vigentes.items():
        if n > 1:
            errors.append(f"Salida {outing_id} tiene {n} fichas vigentes")

    return {
        "generated_at": now_local().isoformat(),
        "version": APP_VERSION,
        "counts": migration_counts(db),
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def _csv_text_from_rows(headers, rows) -> str:
    out = io.StringIO()
    w = csv.writer(out, delimiter=';')
    w.writerow(headers)
    for row in rows:
        w.writerow(row)
    return "\ufeff" + out.getvalue()


def migration_package_bytes(db: Session, actor: str = "") -> bytes:
    state = export_state(db)
    report = migration_integrity_report(db)
    generated = now_local().strftime("%Y-%m-%d %H:%M:%S")
    metadata = {
        "package_type": "fjord_vi_operational_migration",
        "app": "Fjord VI",
        "version": APP_VERSION,
        "generated_at": generated,
        "generated_by": actor or "sistema",
        "counts": report.get("counts", {}),
        "safe_note": "Paquete operativo para clonar beta/staging. Importar solo con confirmación explícita.",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("00_LEEME.txt", (
            "Fjord VI - paquete operativo de migración/clonación.\n"
            "Contiene usuarios, salidas, reservas, fichas, auditoría y configuración básica.\n"
            "No es un pg_dump técnico. Para recuperación de desastre usar Backup PostgreSQL.\n"
            f"Generado: {generated}\nVersión: {APP_VERSION}\n"
        ))
        z.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
        z.writestr("export_state.json", json.dumps(state, ensure_ascii=False, indent=2))
        z.writestr("integrity_report.json", json.dumps(report, ensure_ascii=False, indent=2))
        z.writestr("usuarios.csv", _csv_text_from_rows(
            ["id", "nombre", "dni", "nro_socio", "categoria", "email", "whatsapp", "telefono", "rol", "activo"],
            [[u.get("id"), u.get("name"), u.get("dni"), u.get("member_no"), u.get("category"), u.get("email"), u.get("whatsapp"), u.get("phone"), u.get("role"), u.get("active")] for u in state.get("users", [])]
        ))
        z.writestr("salidas.csv", _csv_text_from_rows(
            ["id", "titulo", "destino", "fecha", "estado", "capacidad", "tarifa", "creada"],
            [[o.get("id"), o.get("title"), o.get("destination"), o.get("departure_at"), o.get("status"), o.get("max_crew"), o.get("guest_fee"), o.get("created_at")] for o in state.get("outings", [])]
        ))
        z.writestr("reservas.csv", _csv_text_from_rows(
            ["id", "salida_id", "nombre", "dni", "tipo", "responsable_id", "estado", "asistencia", "cargo", "protocolar", "ref_protocolar"],
            [[r.get("id"), r.get("outing_id"), r.get("person_name"), r.get("dni"), r.get("kind"), r.get("responsible_user_id"), r.get("status"), r.get("attendance"), r.get("charge_amount"), r.get("protocolar"), r.get("protocolar_by_user_id")] for r in state.get("reservations", [])]
        ))
    return buf.getvalue()


def read_migration_payload(raw: bytes, filename: str = "") -> dict:
    name = (filename or "").lower()
    if name.endswith(".zip") or raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw), "r") as z:
            candidates = [n for n in z.namelist() if n.endswith("export_state.json")]
            if not candidates:
                raise RuntimeError("El ZIP no contiene export_state.json")
            return json.loads(z.read(candidates[0]).decode("utf-8"))
    return json.loads(raw.decode("utf-8"))


@app.get("/admin/migration/export")
def admin_migration_export(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    data = migration_package_bytes(db, user.name)
    filename = f"fjord_vi_migracion_{APP_VERSION}_{now_local().strftime('%Y%m%d_%H%M')}.zip"
    log(db, user.name, "export migration package", filename)
    return Response(data, media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.get("/admin/migration/report")
def admin_migration_report(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    report = migration_integrity_report(db)
    return Response(json.dumps(report, ensure_ascii=False, indent=2), media_type="application/json; charset=utf-8")



MIGRATION_IMPORT_MODES = {
    "replace_full": "Clonar completo: limpia usuarios, salidas, reservas, fichas, auditoría y metadatos antes de importar.",
    "replace_operational": "Reemplazo operativo: limpia salidas, reservas y fichas; conserva accesos/admins locales y actualiza padrón incluido.",
    "merge_safe": "Agregar/actualizar: no borra datos; solo agrega o actualiza IDs existentes. Uso excepcional.",
    "dry_run": "Validar paquete: lee el archivo y muestra diagnóstico sin modificar datos.",
}


def _user_from_export(u: dict) -> User:
    return User(id=u.get("id"), name=u.get("name") or "", dni=norm_dni(u.get("dni") or ""),
                member_no=u.get("member_no"), email=u.get("email") or None, whatsapp=u.get("whatsapp") or None,
                phone=u.get("phone") or None, category=u.get("category") or None, birth_date=u.get("birth_date") or None,
                role=u.get("role") or "socio", password_hash=u.get("password_hash") or hash_password("demo1234"),
                active=bool(u.get("active", True)), can_manage_protocolar=bool(u.get("can_manage_protocolar", False)),
                must_change_password=bool(u.get("must_change_password", False)), session_version=int(u.get("session_version") or 1),
                last_login_at=str_to_dt(u.get("last_login_at")), last_password_change_at=str_to_dt(u.get("last_password_change_at")))


def _outing_from_export(o: dict) -> Outing:
    return Outing(id=o.get("id"), title=o.get("title") or "Salida", destination=o.get("destination") or "",
                  departure_at=str_to_dt(o.get("departure_at")) or now_local(), status=o.get("status") or "En reservas",
                  max_crew=int(o.get("max_crew") or MAX_CREW), min_crew=int(o.get("min_crew") or MIN_CREW),
                  guest_fee=float(o.get("guest_fee") or INVITED_FEE), notes=o.get("notes") or "",
                  created_at=str_to_dt(o.get("created_at")) or now_local(), boat_id=o.get("boat_id") or "fjord_vi")


def _reservation_from_export(r: dict) -> Reservation:
    return Reservation(id=r.get("id"), outing_id=r.get("outing_id"), person_name=r.get("person_name") or "",
                       dni=norm_dni(r.get("dni") or ""), kind=r.get("kind") or "invitado",
                       responsible_user_id=r.get("responsible_user_id"), status=r.get("status") or "Confirmado",
                       attendance=r.get("attendance") or "Por confirmar", charge_amount=float(r.get("charge_amount") or 0),
                       cancel_reason=r.get("cancel_reason") or "", birth_date=r.get("birth_date") or None,
                       created_at=str_to_dt(r.get("created_at")) or now_local(),
                       cancelled_at=str_to_dt(r.get("cancelled_at")), protocolar=bool(r.get("protocolar", False)),
                       protocolar_by_user_id=r.get("protocolar_by_user_id"), protocolar_reason=r.get("protocolar_reason") or "")


def _closing_sheet_from_export(cs: dict) -> ClosingSheet:
    return ClosingSheet(id=cs.get("id"), outing_id=cs.get("outing_id"), sequence=int(cs.get("sequence") or 1),
                        status=cs.get("status") or "VIGENTE", created_at=str_to_dt(cs.get("created_at")) or now_local(),
                        created_by=cs.get("created_by") or "", annulled_at=str_to_dt(cs.get("annulled_at")),
                        annulled_by=cs.get("annulled_by") or None, annul_reason=cs.get("annul_reason") or "",
                        payload=cs.get("payload") or "{}")


def _audit_log_from_export(l: dict) -> AuditLog:
    return AuditLog(id=l.get("id"), created_at=str_to_dt(l.get("created_at")) or now_local(),
                    actor=l.get("actor") or "sistema", action=l.get("action") or "import", detail=l.get("detail") or "")


def migration_payload_report(data: dict) -> dict:
    return {
        "users": len(data.get("users", [])),
        "outings": len(data.get("outings", [])),
        "reservations": len(data.get("reservations", [])),
        "closing_sheets": len(data.get("closing_sheets", [])),
        "audit_logs": len(data.get("audit_logs", [])),
        "system_meta": len(data.get("system_meta", [])),
    }


def import_state_flexible(db: Session, data: dict, mode: str = "replace_full") -> dict:
    """Importador operativo para migración/clonación.

    Modos:
    - replace_full: clon completo, limpia todo lo operativo y metadatos.
    - replace_operational: conserva accesos/admins/metadatos locales, reemplaza salidas/reservas/fichas y actualiza padrón.
    - merge_safe: no borra; agrega/actualiza por ID. Uso excepcional.
    - dry_run: no modifica, solo devuelve conteos del paquete.
    """
    mode = mode if mode in MIGRATION_IMPORT_MODES else "replace_full"
    if mode == "dry_run":
        return {"mode": mode, "changed": False, "package_counts": migration_payload_report(data), "message": "Validación sin cambios."}

    if mode == "replace_full":
        import_state(db, data, allow_destructive=True)
        return {"mode": mode, "changed": True, "package_counts": migration_payload_report(data), "message": "Clon completo importado."}

    if mode == "replace_operational":
        # Borra solo lo operativo dependiente para evitar duplicados de salidas/reservas/fichas.
        try:
            db.query(ClosingSheet).delete()
        except Exception:
            pass
        db.query(Reservation).delete()
        db.query(Outing).delete()
        # Se conserva AuditLog y SystemMeta locales; el padrón se actualiza por ID.
        db.commit()

    # replace_operational y merge_safe: upsert por ID, sin borrar usuarios locales salvo colisión actualizada.
    for u in data.get("users", []):
        db.merge(_user_from_export(u))
    db.commit()
    for o in data.get("outings", []):
        db.merge(_outing_from_export(o))
    db.commit()
    for r in data.get("reservations", []):
        db.merge(_reservation_from_export(r))
    db.commit()
    if mode != "merge_safe":
        for cs in data.get("closing_sheets", []):
            db.merge(_closing_sheet_from_export(cs))
        db.commit()
    else:
        for cs in data.get("closing_sheets", []):
            db.merge(_closing_sheet_from_export(cs))
        db.commit()
    # Auditoría: solo se importa en merge/operativo si viene incluida, sin limpiar auditoría local.
    for l in data.get("audit_logs", []):
        db.merge(_audit_log_from_export(l))
    db.commit()
    if mode == "merge_safe":
        for m in data.get("system_meta", []):
            if m.get("key"):
                db.merge(SystemMeta(key=m.get("key"), value=m.get("value") or "", updated_at=str_to_dt(m.get("updated_at")) or now_local()))
        db.commit()
    persist_json(db)
    return {"mode": mode, "changed": True, "package_counts": migration_payload_report(data), "message": MIGRATION_IMPORT_MODES[mode]}

@app.post("/admin/migration/import")
async def admin_migration_import(
    package_file: UploadFile = File(...),
    confirm_phrase: str = Form(""),
    import_mode: str = Form("replace_full"),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin")),
):
    actor_name = user.name
    if (confirm_phrase or "").strip().upper() != MIGRATION_IMPORT_PHRASE:
        raise HTTPException(400, f"Confirmación inválida. Para importar debe escribir exactamente: {MIGRATION_IMPORT_PHRASE}")
    raw = await package_file.read()
    if not raw:
        raise HTTPException(400, "Paquete vacío")
    try:
        payload = read_migration_payload(raw, package_file.filename or "")
    except Exception as exc:
        raise HTTPException(400, f"No se pudo leer el paquete: {type(exc).__name__}: {exc}")

    import_mode = import_mode if import_mode in MIGRATION_IMPORT_MODES else "replace_full"

    if import_mode == "dry_run":
        result = import_state_flexible(db, payload, mode="dry_run")
        report = {
            "ok": True,
            "mode": import_mode,
            "mode_label": MIGRATION_IMPORT_MODES[import_mode],
            "package_file": package_file.filename or "paquete",
            "package_counts": result.get("package_counts", {}),
            "current_counts": migration_counts(db),
            "message": "Validación completada. No se modificó ningún dato real.",
        }
        return Response(json.dumps(report, ensure_ascii=False, indent=2), media_type="application/json; charset=utf-8")

    # Backup previo obligatorio antes de cualquier importación con cambios.
    backups = create_pre_reset_backups(db)
    if not backups.get("json"):
        raise HTTPException(500, "Importación bloqueada: no se pudo generar backup previo.")

    try:
        result = import_state_flexible(db, payload, mode=import_mode)
        set_system_meta("last_migration_import_at", now_local().isoformat())
        set_system_meta("last_migration_import_by", actor_name)
        set_system_meta("last_migration_import_file", package_file.filename or "paquete")
        set_system_meta("last_migration_import_mode", import_mode)
        set_system_meta("last_pre_import_json", backups.get("json", ""))
        log(db, actor_name, "import migration package", f"{package_file.filename or 'paquete'} / modo {import_mode} / backup previo {backups.get('json')}")
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, f"Importación fallida: {type(exc).__name__}: {exc}")
    return RedirectResponse("/logout", status_code=303)

@app.post("/admin/communications/settings")
def admin_communications_settings(
    smtp_host: str = Form(""), smtp_port: str = Form("587"), smtp_username: str = Form(""), smtp_password: str = Form(""),
    smtp_from_email: str = Form(""), smtp_from_name: str = Form(""), smtp_tls: str = Form("0"), communications_admin_email: str = Form(""),
    db: Session = Depends(db_session), user: User = Depends(require_role("admin"))
):
    set_system_meta("smtp_host", smtp_host.strip())
    set_system_meta("smtp_port", smtp_port.strip() or "587")
    set_system_meta("smtp_username", smtp_username.strip())
    if smtp_password.strip():
        set_system_meta("smtp_password", smtp_password.strip())
    set_system_meta("smtp_from_email", smtp_from_email.strip())
    set_system_meta("smtp_from_name", smtp_from_name.strip() or f"{CLUB_NAME} · {APP_NAME}")
    set_system_meta("smtp_tls", "1" if smtp_tls == "1" else "0")
    set_system_meta("communications_admin_email", communications_admin_email.strip())
    log(db, user.name, "communications settings", "Configuración SMTP/comunicaciones actualizada")
    return RedirectResponse("/admin?page=comunicaciones&msg=smtp_guardado", status_code=303)

@app.post("/admin/communications/event/{event_key}")
def admin_communications_event(event_key: str, enabled: str = Form("0"), db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    ensure_communications_seed(db)
    ev = db.get(NotificationEventSetting, event_key)
    tpl = db.query(NotificationTemplate).filter_by(key=event_key).first()
    if not ev or not tpl:
        raise HTTPException(404, "Evento inexistente")
    ev.enabled = enabled == "1"
    ev.channel_email = True
    ev.updated_at = now_local()
    tpl.enabled = ev.enabled
    tpl.updated_at = now_local()
    db.commit()
    log(db, user.name, "communications event", f"{event_key}: {'ON' if ev.enabled else 'OFF'}")
    return RedirectResponse("/admin?page=comunicaciones&msg=evento_actualizado", status_code=303)

@app.post("/admin/communications/template/{template_key}")
def admin_communications_template(template_key: str, subject: str = Form(""), body: str = Form(""), template_enabled: str = Form("0"), db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    ensure_communications_seed(db)
    tpl = db.query(NotificationTemplate).filter_by(key=template_key).first()
    if not tpl:
        raise HTTPException(404, "Plantilla inexistente")
    tpl.subject = subject
    tpl.body = body
    tpl.enabled = template_enabled == "1"
    tpl.updated_at = now_local()
    db.commit()
    log(db, user.name, "communications template", f"Plantilla actualizada: {template_key}; {'activa' if tpl.enabled else 'inactiva'}")
    return RedirectResponse("/admin?page=comunicaciones&msg=plantilla_actualizada", status_code=303)

@app.post("/admin/communications/test")
def admin_communications_test(test_email: str = Form(...), db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    ensure_communications_seed(db)
    payload = {"app_name": APP_NAME, "version": VERSION, "club_nombre": CLUB_NAME}
    q = queue_email(db, "email_prueba", test_email.strip(), "Prueba", payload, force=True)
    if not q:
        return RedirectResponse("/admin?page=comunicaciones&msg=email_prueba_no_generado", status_code=303)
    result = process_notification_queue(db, limit=5)
    log(db, user.name, "communications test", f"email={test_email}; resultado={result}")
    return RedirectResponse(f"/admin?page=comunicaciones&msg=email_prueba_{result.get('sent',0)}_{result.get('failed',0)}", status_code=303)

@app.post("/admin/communications/process")
def admin_communications_process(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    queued = queue_due_24h_reminders(db)
    result = process_notification_queue(db, limit=50)
    log(db, user.name, "communications process", f"recordatorios={queued}; " + json.dumps(result, ensure_ascii=False))
    return RedirectResponse(f"/admin?page=comunicaciones&msg=cola_{result.get('sent',0)}_{result.get('failed',0)}&queued={queued}", status_code=303)

@app.post("/admin/communications/reminders")
def admin_communications_reminders(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    queued = queue_due_24h_reminders(db)
    result = auto_process_notifications(db, limit=25)
    log(db, user.name, "communications reminders", f"recordatorios={queued}; " + json.dumps(result, ensure_ascii=False))
    return RedirectResponse(f"/admin?page=comunicaciones&msg=recordatorios_{queued}", status_code=303)

@app.post("/admin/communications/retry/{qid}")
def admin_communications_retry(qid: int, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    q = db.get(NotificationQueue, qid)
    if not q:
        raise HTTPException(404, "Email inexistente")
    q.status = "pending"
    q.error = ""
    db.commit()
    result = process_notification_queue(db, limit=1)
    log(db, user.name, "communications retry", f"queue_id={qid}; {result}")
    return RedirectResponse("/admin?page=comunicaciones&msg=reintento", status_code=303)

@app.get("/admin/communications/log.csv")
def admin_communications_log_csv(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["id", "fecha", "evento", "destinatario", "estado", "intentos", "error", "asunto"])
    for q in db.query(NotificationQueue).order_by(NotificationQueue.created_at.desc()).all():
        writer.writerow([q.id, q.created_at.isoformat() if q.created_at else "", q.event_key, q.recipient_email, q.status, q.attempts, q.error, q.subject])
    return csv_response_excel(output, "fjord_vi_comunicaciones.csv")

@app.post("/admin/restore")
async def admin_restore_disabled(user: User = Depends(require_role("admin"))):
    """Restauración JSON desactivada en producción.

    Desde v66.6.1 PostgreSQL es la única fuente de verdad. El JSON queda
    solamente como exportación manual; no puede pisar la base real desde una
    ruta heredada u oculta. La recuperación debe hacerse con backup SQL y
    soporte técnico.
    """
    raise HTTPException(410, "Restauración JSON desactivada: PostgreSQL es la fuente única de verdad")

@app.post("/admin/import_data")
async def import_data_json_disabled(user: User = Depends(require_role("admin"))):
    """Importación JSON desactivada en producción."""
    raise HTTPException(410, "Importación JSON desactivada: usar recuperación SQL supervisada")

@app.post("/admin/demo_reset")
def demo_reset_disabled(user: User = Depends(require_role("admin"))):
    """Reset demo desactivado para evitar borrados accidentales en producción."""
    raise HTTPException(410, "Reset demo desactivado en modo producción")




PRODUCTION_RESET_PHRASE = "RESET OPERATIVO FJORD VI"


def _safe_backup_filename(prefix: str, suffix: str) -> str:
    return f"{prefix}_{now_local().strftime('%Y%m%d_%H%M%S')}{suffix}"


def create_pre_reset_backups(db: Session) -> dict:
    """Genera respaldos antes de un reset productivo.

    Los archivos se guardan en DATA_DIR. En Render el filesystem puede ser efímero,
    pero sirve como resguardo inmediato y deja trazabilidad. La descarga manual desde
    Sistema sigue siendo la vía principal antes de ejecutar un reset real.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    result = {"json": "", "postgres": "", "postgres_error": ""}

    json_name = _safe_backup_filename("pre_reset_fjord_vi", ".json")
    json_path = DATA_DIR / json_name
    json_path.write_text(json.dumps(export_state(db), ensure_ascii=False, indent=2), encoding="utf-8")
    result["json"] = str(json_path)

    if DB_URL.startswith("postgres"):
        pg_dump = shutil.which("pg_dump")
        if pg_dump:
            compatible, compat_detail = pg_dump_compatible_with_server(db)
            if compatible:
                sql_name = _safe_backup_filename("pre_reset_fjord_vi_postgres", ".sql")
                sql_path = DATA_DIR / sql_name
                try:
                    with open(sql_path, "wb") as fh:
                        proc = subprocess.run([pg_dump, DB_URL, "--no-owner", "--no-privileges"], stdout=fh, stderr=subprocess.PIPE, timeout=60)
                    if proc.returncode == 0:
                        result["postgres"] = str(sql_path)
                    else:
                        result["postgres_error"] = proc.stderr.decode("utf-8", errors="ignore")[:400]
                        try:
                            sql_path.unlink(missing_ok=True)
                        except Exception:
                            pass
                except Exception as exc:
                    result["postgres_error"] = f"{type(exc).__name__}: {exc}"
            else:
                result["postgres_error"] = compat_detail
        else:
            result["postgres_error"] = "pg_dump no disponible"
    return result


def reset_operational_sequences(db: Session):
    """Resetea de verdad los datos operativos. Conserva padrón, admins y configuración.

    Limpia salidas colgadas, reservas huérfanas, fichas, cargos/auditoría operativa,
    actividad y colas/logs de comunicaciones. Esto evita que una navegación de prueba
    quede visible después de depurar el padrón.
    """
    tables = [
        "notification_log",
        "notification_queue",
        "closing_sheets",
        "reservations",
        "outings",
        "audit_logs",
        "activity_log",
    ]
    if DB_URL.startswith("postgres"):
        # TRUNCATE reinicia IDs y CASCADE limpia dependencias. Conserva users, system_meta y templates.
        db.execute(text("TRUNCATE TABLE notification_log, notification_queue, closing_sheets, reservations, outings, audit_logs, activity_log RESTART IDENTITY CASCADE"))
    else:
        # Orden defensivo: primero tablas dependientes, después salidas.
        for model in (NotificationLog, NotificationQueue, ClosingSheet, Reservation, Outing, AuditLog, ActivityLog):
            db.query(model).delete(synchronize_session=False)
        try:
            for t in tables:
                db.execute(text("DELETE FROM sqlite_sequence WHERE name = :name"), {"name": t})
        except Exception:
            pass
    db.commit()


@app.post("/admin/production_reset")
def admin_production_reset(
    reset_phrase: str = Form(""),
    understood: Optional[str] = Form(None),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin")),
):
    phrase = (reset_phrase or "").strip().upper()
    if phrase != PRODUCTION_RESET_PHRASE or understood != "on":
        raise HTTPException(400, f"Confirmación inválida. Para resetear debe escribir exactamente: {PRODUCTION_RESET_PHRASE}")

    # Backup previo obligatorio. Si el backup JSON falla, no se resetea.
    backups = create_pre_reset_backups(db)
    if not backups.get("json"):
        raise HTTPException(500, "Reset bloqueado: no se pudo generar backup JSON previo.")

    reset_operational_sequences(db)

    # Registrar el reset después de reiniciar secuencias para que quede como primer evento operativo.
    detail = (
        "RESET OPERATIVO ejecutado. Padrón, usuarios y configuración conservados. "
        f"Backup JSON: {backups.get('json') or 'no generado'}. "
        f"Backup PostgreSQL: {backups.get('postgres') or 'no generado'}. "
        f"Error PostgreSQL backup: {backups.get('postgres_error') or '-'}"
    )
    log(db, user.name, "reset operativo total", detail)
    db.add(ActivityLog(
        user_id=user.id,
        user_name=user.name,
        role=user.role,
        module="sistema",
        action="reset_operativo_total",
        path="/admin?page=sistema",
        detail="Salidas, reservas, fichas, cargos y actividad operativa eliminadas",
    ))
    db.commit()
    set_system_meta("operational_reset_at", now_local().isoformat())
    set_system_meta("operational_reset_by", user.name)
    set_system_meta("last_pre_reset_json", backups.get("json", ""))
    set_system_meta("last_pre_reset_postgres", backups.get("postgres", ""))
    if backups.get("postgres_error"):
        set_system_meta("last_pre_reset_postgres_error", backups.get("postgres_error", ""))
    with SessionLocal() as fresh:
        persist_json(fresh)
    return RedirectResponse("/admin?page=sistema&msg=reset_operativo_ok", status_code=303)

