from datetime import datetime, timedelta, date
from pathlib import Path
import csv
import hashlib
import hmac
import io
import json
import os
import secrets
from typing import Optional

from fastapi import FastAPI, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Numeric, UniqueConstraint, Text, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session


# =========================
# FORMATO VISUAL / LEGIBILIDAD
# =========================
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
SECRET_KEY = os.getenv("SECRET_KEY", "pilot-secret-change-me")
MAX_CREW = int(os.getenv("MAX_CREW", "9"))
MIN_CREW = int(os.getenv("MIN_CREW", "2"))
INVITED_FEE = float(os.getenv("INVITED_FEE", "45000"))
LATE_SOCIO_RATE = float(os.getenv("LATE_SOCIO_RATE", "0.70"))
VERSION = "v36.0.0"
APP_BUILD = "plano-definitivo-sin-templates-v36"
CLUB_NAME = "YCA"
APP_NAME = "Fjord VI"
APP_MODEL = "Embarque"

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
    phone = Column(String, nullable=True)
    role = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    active = Column(Boolean, default=True)

class Outing(Base):
    __tablename__ = "outings"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    departure_at = Column(DateTime, nullable=False)
    status = Column(String, default="Programada")
    max_crew = Column(Integer, default=MAX_CREW)
    min_crew = Column(Integer, default=MIN_CREW)
    guest_fee = Column(Numeric(12,2), default=INVITED_FEE)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(Integer, primary_key=True)
    outing_id = Column(Integer, ForeignKey("outings.id"), nullable=False)
    person_name = Column(String, nullable=False)
    dni = Column(String, nullable=False)
    kind = Column(String, nullable=False)
    responsible_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="Confirmado")
    attendance = Column(String, default="Por confirmar")
    charge_amount = Column(Numeric(12,2), default=0)
    cancel_reason = Column(String, default="")
    birth_date = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    cancelled_at = Column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("outing_id", "dni", name="uq_outing_dni"),)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    detail = Column(Text, default="")

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

    if "birth_date" not in reservation_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE reservations ADD COLUMN birth_date VARCHAR"))

    try:
        user_columns = [c["name"] for c in inspector.get_columns("users")]
    except Exception:
        user_columns = []

    with engine.begin() as conn:
        if "email" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR"))
        if "phone" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR"))

ensure_schema()
app = FastAPI(title=f"{CLUB_NAME} · {APP_NAME} · {APP_MODEL} · {VERSION}")

STATIC_DIR = APP_DIR / "static"
if not STATIC_DIR.exists():
    STATIC_DIR = APP_DIR
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Proyecto PLANO: los HTML viven en la raíz del proyecto.
# No usar carpeta /templates para evitar mezclas y errores TemplateNotFound en deploy manual.
templates = Jinja2Templates(directory=str(APP_DIR))
templates.env.globals.update({
    "version": VERSION,
    "app_build": APP_BUILD,
    "club_name": CLUB_NAME,
    "app_name": APP_NAME,
    "app_model": APP_MODEL,
})

def base_template_context(**extra):
    """Contrato unico de datos para templates: marca, versionado y datos comunes."""
    ctx = {
        "version": VERSION,
        "app_build": APP_BUILD,
        "club_name": CLUB_NAME,
        "app_name": APP_NAME,
        "app_model": APP_MODEL,
    }
    ctx.update(extra)
    return ctx


def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def norm_dni(v: str) -> str:
    """Normaliza DNI, pasaporte o documento extranjero.

    Mantiene letras y números, elimina puntos, espacios, guiones y símbolos.
    Ejemplos:
    - 41.325.286 -> 41325286
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
        "exported_at": datetime.utcnow().isoformat(),
        "users": [
            {"id": u.id, "name": u.name, "dni": u.dni, "member_no": u.member_no,
             "email": u.email or "", "phone": u.phone or "", "role": u.role,
             "password_hash": u.password_hash, "active": bool(u.active)}
            for u in db.query(User).order_by(User.id).all()
        ],
        "outings": [
            {"id": o.id, "title": o.title, "destination": o.destination, "departure_at": dt_to_str(o.departure_at),
             "status": o.status, "max_crew": o.max_crew, "min_crew": o.min_crew, "guest_fee": float(o.guest_fee or 0),
             "notes": o.notes or "", "created_at": dt_to_str(o.created_at)}
            for o in db.query(Outing).order_by(Outing.id).all()
        ],
        "reservations": [
            {"id": r.id, "outing_id": r.outing_id, "person_name": r.person_name, "dni": r.dni, "kind": r.kind,
             "responsible_user_id": r.responsible_user_id, "status": r.status, "attendance": r.attendance,
             "charge_amount": float(r.charge_amount or 0), "cancel_reason": r.cancel_reason or "",
             "birth_date": r.birth_date or "", "created_at": dt_to_str(r.created_at), "cancelled_at": dt_to_str(r.cancelled_at)}
            for r in db.query(Reservation).order_by(Reservation.id).all()
        ],
        "audit_logs": [
            {"id": l.id, "created_at": dt_to_str(l.created_at), "actor": l.actor, "action": l.action, "detail": l.detail or ""}
            for l in db.query(AuditLog).order_by(AuditLog.id).all()
        ],
    }

def persist_json(db: Session):
    try:
        JSON_BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = JSON_BACKUP_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(export_state(db), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(JSON_BACKUP_PATH)
    except Exception:
        pass

def import_state(db: Session, data: dict):
    db.query(AuditLog).delete()
    db.query(Reservation).delete()
    db.query(Outing).delete()
    db.query(User).delete()
    db.commit()
    for u in data.get("users", []):
        db.add(User(id=u.get("id"), name=u.get("name") or "", dni=norm_dni(u.get("dni") or ""),
                    member_no=u.get("member_no"), email=u.get("email") or None, phone=u.get("phone") or None,
                    role=u.get("role") or "socio",
                    password_hash=u.get("password_hash") or hash_password("demo1234"), active=bool(u.get("active", True))))
    db.commit()
    for o in data.get("outings", []):
        db.add(Outing(id=o.get("id"), title=o.get("title") or "Salida", destination=o.get("destination") or "",
                      departure_at=str_to_dt(o.get("departure_at")) or datetime.utcnow(), status=o.get("status") or "En reservas",
                      max_crew=int(o.get("max_crew") or MAX_CREW), min_crew=int(o.get("min_crew") or MIN_CREW),
                      guest_fee=float(o.get("guest_fee") or INVITED_FEE), notes=o.get("notes") or "",
                      created_at=str_to_dt(o.get("created_at")) or datetime.utcnow()))
    db.commit()
    for r in data.get("reservations", []):
        db.add(Reservation(id=r.get("id"), outing_id=r.get("outing_id"), person_name=r.get("person_name") or "",
                           dni=norm_dni(r.get("dni") or ""), kind=r.get("kind") or "invitado",
                           responsible_user_id=r.get("responsible_user_id"), status=r.get("status") or "Confirmado",
                           attendance=r.get("attendance") or "Por confirmar", charge_amount=float(r.get("charge_amount") or 0),
                           cancel_reason=r.get("cancel_reason") or "", birth_date=r.get("birth_date") or None,
                           created_at=str_to_dt(r.get("created_at")) or datetime.utcnow(),
                           cancelled_at=str_to_dt(r.get("cancelled_at"))))
    db.commit()
    for l in data.get("audit_logs", []):
        db.add(AuditLog(id=l.get("id"), created_at=str_to_dt(l.get("created_at")) or datetime.utcnow(),
                        actor=l.get("actor") or "sistema", action=l.get("action") or "import", detail=l.get("detail") or ""))
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

# Restore JSON backup at startup only if the database is empty
restore_json_if_db_empty()

def log(db: Session, actor: str, action: str, detail: str = ""):
    db.add(AuditLog(actor=actor, action=action, detail=detail))
    db.commit()
    persist_json(db)

def current_user(request: Request, db: Session = Depends(db_session)) -> Optional[User]:
    uid = unsign_value(request.cookies.get("fjord_uid", ""))
    if not uid:
        return None
    try:
        return db.get(User, int(uid))
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


def cascade_no_board_dependents(db: Session, outing: Outing, socio_reservation: Reservation, reason: str = "No embarcado: socio responsable no embarca") -> list:
    """Baja operativamente a todos los invitados de un socio que no embarca.

    Regla blindada: un invitado/menor no socio no puede quedar embarcado si
    su socio responsable no embarca. Esta cascada no genera cargo por sí misma,
    porque la persona queda impedida por dependencia reglamentaria del titular.
    """
    changed = []
    if not outing or not socio_reservation or canonical_kind(socio_reservation.kind) != "socio":
        return changed
    for dep in dependent_reservations_for(db, outing.id, socio_reservation):
        if is_waitlisted(dep):
            continue
        if dep.cancelled_at is not None or dep.status == "Cancelado":
            continue
        if dep.attendance != "No embarca" or (dep.cancel_reason or "") != reason:
            dep.attendance = "No embarca"
            dep.cancel_reason = reason
            dep.charge_amount = 0
            changed.append(dep.person_name)
    return changed


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
        if is_waitlisted(r) or r.cancelled_at is not None or r.status == "Cancelado":
            continue
        responsible = users_by_id.get(r.responsible_user_id)
        responsible_row = by_dni.get(responsible.dni) if responsible else None
        responsible_present = bool(responsible_row and canonical_kind(responsible_row.kind) == "socio" and responsible_row.attendance == "Presente" and reservation_is_active(responsible_row))
        if not responsible_present and r.attendance == "Presente":
            r.attendance = "No embarca"
            r.cancel_reason = "No embarcado: socio responsable no embarca"
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


def put_on_waitlist(r: Reservation, reason: str = "En lista de espera"):
    # La lista de espera no ocupa cupo y nunca genera cargo mientras no sea promovida.
    r.status = "Lista de espera"
    r.attendance = "Lista de espera"
    r.charge_amount = 0
    r.cancel_reason = reason
    r.cancelled_at = None


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

    if len(active_reservations(rows_without_target)) < outing.max_crew:
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
        if len(active_reservations(rows)) >= outing.max_crew:
            break
        waiting = [r for r in rows if is_waitlisted(r)]
        if not waiting:
            break
        # Antes del corte, socios primero. Después del corte, no hay desplazamiento por
        # prioridad: se respeta el orden cronológico de lista de espera ante una vacante real.
        if cutoff_passed(outing):
            waiting.sort(key=lambda r: (r.created_at or datetime.utcnow(), r.id or 0))
        else:
            waiting.sort(key=lambda r: (0 if canonical_kind(r.kind) == "socio" else 1, r.created_at or datetime.utcnow(), r.id or 0))
        chosen = None
        for r in waiting:
            k = canonical_kind(r.kind)
            if k in ("invitado", "hijo_menor"):
                responsible = db.get(User, r.responsible_user_id) if r.responsible_user_id else None
                if not responsible:
                    continue
                responsible_row = db.query(Reservation).filter_by(outing_id=outing.id, dni=responsible.dni).first()
                if not responsible_row or not reservation_is_active(responsible_row):
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




def enforce_capacity(db: Session, outing: Outing) -> list:
    """Garantiza que nunca haya más reservas activas que cupo.

    Si por datos heredados o por una combinación de altas/reaperturas quedaron
    más activos que el máximo, baja primero invitados/menores no presentes a
    lista de espera. No toca a personas ya marcadas Presente por el capitán.
    """
    if not outing or is_closed_outing(outing) or is_outing_cancelled_by_captain(outing):
        return []

    displaced = []
    while True:
        rows = db.query(Reservation).filter_by(outing_id=outing.id).all()
        active = active_reservations(rows)
        if len(active) <= outing.max_crew:
            break

        candidates = [
            r for r in active
            if (r.attendance or "Por confirmar") != "Presente"
            and canonical_kind(r.kind) in ("invitado", "hijo_menor")
        ]
        if not candidates:
            candidates = [r for r in active if (r.attendance or "Por confirmar") != "Presente"]
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
    return datetime.utcnow() >= cutoff_at(outing)

def late_window_passed(outing: Outing) -> bool:
    return datetime.utcnow() >= cancellation_deadline(outing)

def reservation_charge(outing: Outing, r: Reservation) -> float:
    """Cargo reglamentario por plaza perdida.

    Esta función se usa para cancelación tardía, ausencia o no embarcable.
    No se usa para cobrar navegación normal.

    Socio, incluido socio menor: 70% de tarifa invitado.
    Invitado, de cualquier edad: 100% de tarifa invitado.
    Hijo menor de socio no socio: navega sin cargo, pero si no embarca
    o cancela tarde paga 100% de tarifa invitado por plaza perdida.
    """
    fee = float(outing.guest_fee or 0)
    k = canonical_kind(r.kind)
    if k == "socio":
        return round(fee * LATE_SOCIO_RATE, 2)
    if k in ("invitado", "hijo_menor"):
        return fee
    return 0.0

def human_money(value) -> str:
    return f"{float(value or 0):,.0f}".replace(",", ".")

templates.env.filters["money"] = human_money




def captain_control_window(outing: Outing) -> dict:
    """Ventana operativa del capitán.

    Regla acordada:
    - Puede operar asistencia/cancelación/reapertura hasta 48h desde la hora programada.
    - El cierre/liquidación no puede ejecutarse antes de la hora programada.
    - Pasadas 48h, solo Administración puede corregir.
    """
    if not outing:
        return {"can_edit": False, "can_close": False, "before_departure": False, "expired": True, "label": "Sin salida", "detail": "No hay salida seleccionada."}
    now = datetime.utcnow()
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
    pero el capitán decide no embarcarla. No es no-show: no genera cargo.
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
    - Solo una salida cerrada por capitán puede producir cargo firme.
    """
    if not outing or not r:
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
            motivo = motivo or "Ausencia / plaza no utilizada"
        else:
            motivo = motivo or "Cargo reglamentario"
    elif preliminary:
        if cancelled:
            motivo = motivo or "Preliquidación por baja tardía, no firme hasta cierre"
        elif raw_attendance in ("Ausente", "No embarcable"):
            motivo = motivo or "Preliquidación por ausencia/no embarque, no firme hasta cierre"
        else:
            motivo = "Tarifa de invitado pendiente de cierre"
    elif cancelled:
        motivo = motivo or "Cancelado sin cargo"
    elif raw_attendance == "No embarcable":
        motivo = motivo or "No embarcado: socio responsable ausente"
    elif raw_attendance == "Ausente":
        motivo = motivo or "Ausente sin cargo registrado"
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
        "charge_is_preliminary": preliminary,
        "critical": bool(charge > 0 or preliminary or is_not_embarked or cancelled),
        "closed": closed,
        "cancelled": cancelled,
        "active": reservation_is_active(r),
        "embarked": is_embarked,
        "not_embarked": is_not_embarked,
        "waitlisted": is_waitlisted(r),
        "charge_label": human_money(charge),
        "charge_preview_label": human_money(charge_preview),
    }

def reservation_views(outing: Outing, rows) -> dict:
    return {r.id: reservation_view(outing, r) for r in rows}


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

def final_status_summary(outing: Outing, reservations, active_count: int, present: int, pending: int) -> dict:
    if not outing:
        return {"closed": False, "label": "Sin salida", "detail": "No hay salida seleccionada", "liquidacion": "Sin datos"}
    if is_outing_cancelled_by_captain(outing):
        return {"closed": True, "label": "Estado final: Cancelada", "detail": "Salida cancelada por capitán. No se generan cargos firmes ni preliquidaciones vigentes.", "liquidacion": "Sin cargos"}
    if is_closed_outing(outing):
        return {"closed": True, "label": "Estado final: Confirmado", "detail": f"Salida cerrada y liquidada. Tripulación final: {present} / {outing.max_crew}", "liquidacion": "Liquidación completa"}
    return {"closed": False, "label": "Estado operativo: Abierto", "detail": f"Activos: {active_count} / {outing.max_crew} · pendientes: {pending}", "liquidacion": "Preliquidación no firme hasta cierre del capitán"}

def seed():
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            db.add_all([
                User(name="Juan Pérez", dni="20123456", member_no="1234", email="juan@example.com", phone="", role="socio", password_hash=hash_password("demo1234")),
                User(name="Capitán Martín", dni="30999111", member_no="CAP-01", email="capitan@example.com", phone="", role="captain", password_hash=hash_password("demo1234")),
                User(name="Admin Club", dni="27999111", member_no="ADM-01", email="admin@example.com", phone="", role="admin", password_hash=hash_password("demo1234")),
            ])
            db.commit()

        if db.query(Outing).count() == 0:
            dep = datetime.utcnow().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=2)
            o = Outing(
                title="Paseo de domingo",
                destination="Dársena Norte / Río de la Plata",
                departure_at=dep,
                status="En reservas",
                guest_fee=INVITED_FEE,
                notes="Piloto fin de semana. Mínimo 2, máximo 9 tripulantes sin contar capitán."
            )
            db.add(o)
            db.commit()
            db.refresh(o)

            socio = db.query(User).filter_by(role="socio").first()
            db.add_all([
                Reservation(outing_id=o.id, person_name=socio.name, dni=socio.dni, kind="socio", responsible_user_id=socio.id),
                Reservation(outing_id=o.id, person_name="María Gómez", dni="35111222", kind="invitado", responsible_user_id=socio.id, status="Condicional hasta 48h"),
                Reservation(outing_id=o.id, person_name="Carlos Rodríguez", dni="23452345", kind="socio", responsible_user_id=None),
                Reservation(outing_id=o.id, person_name="Ana López", dni="32111333", kind="invitado", responsible_user_id=socio.id, status="Condicional hasta 48h"),
                Reservation(outing_id=o.id, person_name="Pedro Martínez", dni="28456456", kind="socio", responsible_user_id=None),
                Reservation(outing_id=o.id, person_name="Lucía Fernández", dni="36777888", kind="invitado", responsible_user_id=socio.id, status="Condicional hasta 48h"),
                Reservation(outing_id=o.id, person_name="Diego Sánchez", dni="30456789", kind="socio", responsible_user_id=None),
                Reservation(outing_id=o.id, person_name="Tomás Ruiz", dni="44999111", kind="hijo_menor", responsible_user_id=socio.id, status="Hijo menor de socio no socio", birth_date="2012-01-01"),
            ])
            db.commit()
            log(db, "sistema", "seed", "Datos demo creados")
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
        return {"label": "Salida cerrada y liquidada", "level": "ok", "detail": "La salida ya fue cerrada y liquidada por capitán."}
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

@app.get("/health")
def health():
    return {"ok": True, "version": VERSION, "app_build": APP_BUILD, "club_name": CLUB_NAME, "app_name": APP_NAME, "app_model": APP_MODEL, "max_crew": MAX_CREW, "min_crew": MIN_CREW, "captain_cancel_after_close": True, "captain_close_from_selector": True, "admin_users": True, "document_id_alnum": True, "database": "postgres" if DB_URL.startswith("postgres") else "sqlite", "json_backup": str(JSON_BACKUP_PATH), "json_exists": JSON_BACKUP_PATH.exists(), "waitlist": True, "dependent_guest_cascade": True}

@app.head("/")
def head_index():
    return Response(status_code=200)

@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(db_session), user: Optional[User] = Depends(current_user)):
    if not user:
        resp = templates.TemplateResponse(request, "login.html", {"request": request, "version": VERSION, "error": request.query_params.get("error")})
        resp.headers["Cache-Control"] = "no-store"
        return resp
    if user.role == "captain":
        return RedirectResponse("/captain", status_code=303)
    if user.role == "admin":
        return RedirectResponse("/admin", status_code=303)
    return RedirectResponse("/socio", status_code=303)

@app.post("/login")
def login(dni: str = Form(...), password: str = Form(...), db: Session = Depends(db_session)):
    user = db.query(User).filter_by(dni=norm_dni(dni), active=True).first()
    if not user or not verify_password(password, user.password_hash):
        return RedirectResponse("/?error=1", status_code=303)
    log(db, user.name, "login", user.role)
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie("fjord_uid", sign_value(str(user.id)), httponly=True, samesite="lax", max_age=43200)
    return resp

@app.get("/logout")
def logout():
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("fjord_uid", path="/")
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
    else:
        target = Reservation(outing_id=outing.id, person_name=user.name, dni=user.dni, kind="socio", responsible_user_id=user.id)
        db.add(target)
        db.flush()

    result, displaced_name = place_socio_with_priority(db, outing, target)
    enforce_capacity(db, outing)
    db.commit()

    if result == "waitlist":
        log(db, user.name, "lista de espera socio", outing.title)
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=lista_espera_ok", status_code=303)
    if result == "active_displaced":
        log(db, user.name, "reserva socio con prioridad", f"{outing.title} / desplazado: {displaced_name}")
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=socio_prioridad_ok", status_code=303)

    log(db, user.name, "reserva socio", outing.title)
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

    full_capacity = len(active) >= outing.max_crew

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
            status=status,
            birth_date=birth_date
        )
        if full_capacity:
            put_on_waitlist(new_guest, "En lista de espera. Se activa si se libera una vacante.")
        db.add(new_guest)

    enforce_capacity(db, outing)
    db.commit()
    log(db, user.name, "agrega/reactiva invitado" if not full_capacity else "lista de espera invitado", f"{person_name} / {outing.title}")

    return RedirectResponse(f"/socio?outing_id={outing.id}&msg={'lista_espera_ok' if full_capacity else 'invitado_ok'}", status_code=303)

@app.post("/socio/cancel/{rid}")
def cancel_reservation(rid: int, outing_id: Optional[int] = Form(None), db: Session = Depends(db_session), user: User = Depends(require_role("socio"))):
    r = db.get(Reservation, rid)
    outing = selected_outing(db, outing_id)
    ensure_outing_editable(outing)
    if not r or r.outing_id != outing.id or not (r.dni == user.dni or r.responsible_user_id == user.id):
        raise HTTPException(403)

    now = datetime.utcnow()
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
    final_summary = final_status_summary(outing, reservations, len(active), present, pending) if outing else {}
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
    return templates.TemplateResponse(request, "captain.html", {
        "request": request, "user": user, "outing": outing, "outings": outings, "history_groups": history_groups, "reservations": reservations,
        "active": active, "active_count": len(active), "present": present, "absent": absent,
        "pending": pending, "socios_presentes": socios_presentes, "readiness": ready,
        "cutoff": cutoff_passed(outing) if outing else False, "cutoff_at": cutoff_at(outing) if outing else None, "msg": request.query_params.get("msg"),
        "reservation_views": views, "final_summary": final_summary, "charge_summary": summary, "acta": acta,
        "closed": is_closed_outing(outing) if outing else False,
        "waitlist_count": waitlist_count, "total_registros": len(reservations) if outing else 0,
        "checkin_url": checkin_url, "qr_url": qr_url, "control_window": control_window
    })

def auto_confirm_active_for_close(db: Session, outing: Outing, active):
    """Cierre inteligente operativo: valida mínimo por cupo activo y confirma pendientes al cerrar."""
    changed = []
    for r in active:
        current = (r.attendance or "Por confirmar").strip()
        if current == "Por confirmar":
            r.attendance = "Presente"
            r.cancel_reason = ""
            r.charge_amount = 0
            changed.append(r.person_name)
    if changed:
        log(db, "Sistema", "auto-confirmación cierre", f"{outing.title}: {chr(44).join(changed)}")
    return changed

def liquidate_and_close_boarding(db: Session, outing: Outing, reservations, active):
    """Cierra embarque y liquida la salida.

    Reglas:
    - Socio presente: sin cargo.
    - Invitado presente: paga tarifa completa de invitado.
    - Hijo menor de socio no socio presente: sin cargo.
    - Ausente/no embarcable: cargo reglamentario por plaza perdida.
    """
    normalize_member_reservations(db, reservations)
    # Blindaje previo al cierre: ningún invitado/menor puede quedar embarcado
    # si su socio responsable no está presente.
    enforce_responsible_dependency(db, outing, reservations)
    users = {u.id: u for u in db.query(User).all()}
    present_dnis = {r.dni for r in reservations if canonical_kind(r.kind) == "socio" and r.attendance == "Presente" and reservation_is_active(r)}
    guest_fee = float(outing.guest_fee or 0)

    for r in reservations:
        k = canonical_kind(r.kind)

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

        if r.cancelled_at is not None:
            if r.charge_amount is None:
                r.charge_amount = 0
            continue

        if r.attendance == "Por confirmar":
            r.attendance = "Ausente"
            r.cancel_reason = r.cancel_reason or "No confirmado al cierre de embarque"

        # Invitados e hijos menores no socios solo pueden embarcar si embarca su socio responsable.
        if k in ("invitado", "hijo_menor") and r.attendance == "Presente":
            responsible = users.get(r.responsible_user_id)
            if responsible and responsible.dni not in present_dnis:
                r.attendance = "No embarca"
                r.cancel_reason = "No embarcado: socio responsable no embarca"
                r.charge_amount = 0

        if r.attendance in ("Ausente", "No embarcable"):
            r.charge_amount = reservation_charge(outing, r)
            if not r.cancel_reason:
                r.cancel_reason = "Ausencia / plaza no utilizada"
        elif r.attendance == "Presente":
            if k == "invitado":
                r.charge_amount = guest_fee
                r.cancel_reason = "Tarifa de invitado embarcado"
            else:
                r.charge_amount = 0
                r.cancel_reason = ""

    outing.status = "Embarque cerrado"


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
                r.cancel_reason = "Ausencia / plaza no utilizada"
            continue

        r.charge_amount = 0
        if r.attendance in ("Presente", "Por confirmar") and not is_captain_cancelled(r):
            r.cancel_reason = ""

@app.post("/captain/outing_status")
def outing_status(
    outing_id: Optional[int] = Form(None),
    status: str = Form(...),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("captain", "admin"))
):
    outing = selected_outing(db, outing_id)
    if not outing:
        raise HTTPException(400, "Salida inexistente")

    old_status = outing.status

    # Control temporal: Administración puede siempre; Capitán solo dentro de su ventana.
    if status == "Cerrar":
        ensure_captain_window(user, outing, "close")
    else:
        ensure_captain_window(user, outing, "edit")

    # ===== CANCELAR =====
    if status == "Cancelada":
        reservations = db.query(Reservation).filter_by(outing_id=outing.id).all()

        for r in reservations:
            # La cancelación total por capitán anula toda preliquidación,
            # pero no borra cancel_reason/cancelled_at. Así, si el capitán
            # reabre la salida, se puede reconstruir la preliquidación de
            # bajas tardías previas sin perder trazabilidad.
            r.charge_amount = 0

        outing.status = "Cancelada por capitán"

        db.commit()
        log(db, user.name, "cancelación", f"{outing.title} / desde {old_status}")
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=estado_actualizado", status_code=303)

    # ===== CERRAR =====
    if status == "Cerrar":
        if old_status == "Cancelada por capitán":
            return RedirectResponse(f"/captain?outing_id={outing.id}&msg=salida_cerrada", status_code=303)

        reservations = db.query(Reservation).filter_by(outing_id=outing.id).all()
        enforce_capacity(db, outing)
        active = active_reservations(reservations)
        active_count = len(active)
        present = sum(1 for r in active if r.attendance == "Presente")

        if active_count < outing.min_crew:
            raise HTTPException(400, f"No se alcanza el mínimo de {outing.min_crew} tripulantes activos")
        if active_count > outing.max_crew:
            raise HTTPException(400, f"Se supera el cupo máximo de {outing.max_crew}")

        auto_confirm_active_for_close(db, outing, active)
        present = sum(1 for r in active if r.attendance == "Presente")
        liquidate_and_close_boarding(db, outing, reservations, active)

        db.commit()
        log(db, user.name, "cierre", f"{outing.title} / presentes {present} / activos {active_count}")
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=cierre_ok", status_code=303)

    # ===== REABRIR =====
    if status == "Reservas abiertas":
        reservations = db.query(Reservation).filter_by(outing_id=outing.id).all()
        outing.status = "En reservas"
        recalculate_preliquidation_after_reopen(db, outing, reservations)
        promoted = promote_waitlist(db, outing)
        db.commit()
        log(db, user.name, "reapertura", f"{outing.title} / desde {old_status} / preliquidaciones recalculadas / promovidos {', '.join(promoted) if promoted else '-'}")
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=reapertura_ok", status_code=303)

    return RedirectResponse(f"/captain?outing_id={outing.id}", status_code=303)

@app.post("/captain/attendance/{rid}/{value}")
def attendance(rid: int, value: str, db: Session = Depends(db_session), user: User = Depends(require_role("captain", "admin"))):
    r = db.get(Reservation, rid)
    if not r or value not in ["Presente", "Ausente", "Por confirmar", "No embarca"]:
        raise HTTPException(400)

    outing = db.get(Outing, r.outing_id)
    ensure_captain_window(user, outing, "edit")
    if outing and outing.status == "Embarque cerrado" and user.role != "admin":
        raise HTTPException(400, "El embarque ya fue cerrado. Reabrí la salida dentro de la ventana operativa o contactá Administración.")

    if is_waitlisted(r):
        raise HTTPException(400, "La reserva está en lista de espera. Solo puede operar cuando sea promovida al cupo.")

    if value in ("Presente", "Por confirmar"):
        # Blindaje: un invitado/menor no socio no puede ser marcado presente
        # si su socio responsable no está presente y activo.
        if value == "Presente" and canonical_kind(r.kind) in ("invitado", "hijo_menor"):
            responsible_row = responsible_reservation_for(db, r.outing_id, r.responsible_user_id)
            responsible_ok = bool(responsible_row and responsible_row.attendance == "Presente" and reservation_is_active(responsible_row))
            if not responsible_ok:
                r.cancelled_at = None
                r.status = default_reservation_status(outing, r)
                r.attendance = "No embarca"
                r.cancel_reason = "No embarcado: socio responsable no embarca"
                r.charge_amount = 0
                db.commit()
                log(db, user.name, "asistencia bloqueada", f"{r.person_name}: socio responsable no embarca / {outing.title}")
                return RedirectResponse(f"/captain?outing_id={outing.id}&msg=asistencia_actualizada", status_code=303)
        r.cancelled_at = None
        r.status = default_reservation_status(outing, r)
        r.cancel_reason = ""
        r.charge_amount = 0
        r.attendance = value
    elif value == "Ausente":
        # Ausente verdadero: no vino y queda como plaza perdida con cargo reglamentario.
        # Normalmente se genera automáticamente al cerrar embarque si quedó Por confirmar.
        r.attendance = "Ausente"
        r.cancel_reason = "Ausente / no se presentó"
        r.charge_amount = reservation_charge(outing, r) if late_window_passed(outing) else 0
    elif value == "No embarca":
        # Decisión operativa del capitán: no es no-show y no genera cargo.
        r.cancelled_at = None
        r.status = default_reservation_status(outing, r)
        r.attendance = "No embarca"
        r.cancel_reason = "No embarcado por decisión del capitán"
        r.charge_amount = 0
        # Si el titular no embarca, sus invitados/menores no pueden quedar a bordo.
        cascade_no_board_dependents(db, outing, r)

    # Reaplica la dependencia antes de recalcular cupos/promociones.
    enforce_responsible_dependency(db, outing)
    promoted = promote_waitlist(db, outing) if value in ("Ausente", "No embarca") else []
    enforce_capacity(db, outing)
    db.commit()
    log(db, user.name, "asistencia", f"{r.person_name}: {value} / {outing.title} / promovidos {', '.join(promoted) if promoted else '-'}")
    return RedirectResponse(f"/captain?outing_id={outing.id}&msg=asistencia_actualizada", status_code=303)

@app.post("/captain/close")
def close_boarding(outing_id: Optional[int] = Form(None), db: Session = Depends(db_session), user: User = Depends(require_role("captain", "admin"))):
    outing, reservations, active, present, *_ = outing_context(db, outing_id)
    if not outing:
        raise HTTPException(400, "Salida inexistente")
    ensure_captain_window(user, outing, "close")
    if outing.status in ("Embarque cerrado", "Cancelada por capitán", "Realizada"):
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=salida_cerrada", status_code=303)

    enforce_capacity(db, outing)
    reservations = db.query(Reservation).filter_by(outing_id=outing.id).order_by(Reservation.cancelled_at.isnot(None), Reservation.id).all()
    active = active_reservations(reservations)
    active_count = len(active)
    present = sum(1 for r in active if r.attendance == "Presente")

    # Cierre inteligente: el mínimo se valida por cupo activo. Al cerrar,
    # los activos aún pendientes se confirman automáticamente como presentes.
    if active_count < outing.min_crew:
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=minimo_no_cumple", status_code=303)
    if active_count > outing.max_crew:
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=maximo_superado", status_code=303)

    auto_confirm_active_for_close(db, outing, active)
    present = sum(1 for r in active if r.attendance == "Presente")
    liquidate_and_close_boarding(db, outing, reservations, active)
    db.commit()
    log(db, user.name, "cierre embarque", f"{outing.title} / presentes {present} / activos {active_count}")
    return RedirectResponse(f"/captain?outing_id={outing.id}&msg=cierre_ok", status_code=303)



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
    today = datetime.utcnow().date()
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

@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, outing_id: Optional[int] = None, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    outings = visible_outings(db, outing_id)
    history_outings = historical_outings(db, outings)
    history_groups = historical_outing_groups(history_outings)
    outing, reservations, active, present, absent, pending, socios_presentes = outing_context(db, outing_id)
    charges = [r for r in db.query(Reservation).filter(Reservation.outing_id == outing.id).all() if reservation_view(outing, r)["charge"] > 0] if outing else []
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(15).all()
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
    final_summary = final_status_summary(outing, reservations, len(active), present, pending) if outing else {}
    summary = charge_summary(outing, reservations) if outing else {"socios": [], "invitados": [], "menores": [], "total": 0, "total_label": "0", "preliminares": [], "preliminary_total": 0, "preliminary_total_label": "0"}
    acta = final_acta(outing, reservations) if outing else {"embarked": [], "not_embarked": [], "pending": [], "charges": [], "preliminary": [], "total": 0, "total_label": "0", "preliminary_total": 0, "preliminary_total_label": "0", "embarked_count": 0, "not_embarked_count": 0, "pending_count": 0}
    control_window = captain_control_window(outing) if outing else {}
    return templates.TemplateResponse(request, "admin.html", base_template_context(**{
        "request": request, "user": user, "outing": outing, "outings": outings, "history_groups": history_groups, "counts": counts, "active_counts": active_counts,
        "reservations": reservations, "active": active, "active_count": len(active),
        "present": present, "pending": pending, "charges": charges,
        "total_charges": total_charges, "logs": logs, "readiness": ready,
        "users": db.query(User).order_by(User.name.asc()).all(),
        "msg": request.query_params.get("msg"), "reservation_views": views,
        "final_summary": final_summary, "charge_summary": summary, "acta": acta,
        "closed": is_closed_outing(outing) if outing else False,
        "responsible_names": responsible_names,
        "waitlist_count": waitlist_count, "total_registros": len(reservations) if outing else 0,
        "control_window": control_window
    }))


@app.post("/admin/create_user")
def create_user(
    name: str = Form(...),
    dni: str = Form(...),
    member_no: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    role: str = Form("socio"),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    dni_clean = norm_dni(dni)
    if not name.strip() or not dni_clean:
        return RedirectResponse("/admin?msg=datos_usuario_invalidos", status_code=303)

    if role not in ("socio", "captain", "admin"):
        return RedirectResponse("/admin?msg=rol_invalido", status_code=303)

    existing = db.query(User).filter_by(dni=dni_clean).first()
    if existing:
        return RedirectResponse("/admin?msg=usuario_existente", status_code=303)

    new_user = User(
        name=name.strip(),
        dni=dni_clean,
        member_no=member_no.strip() or None,
        email=email.strip() or None,
        phone=phone.strip() or None,
        role=role,
        password_hash=hash_password("demo1234"),
        active=True
    )
    db.add(new_user)
    db.commit()
    log(db, user.name, "alta usuario", f"{new_user.name} / {new_user.dni} / {new_user.role}")
    return RedirectResponse("/admin?msg=usuario_creado", status_code=303)


@app.post("/admin/reset_password/{uid}")
def reset_password(
    uid: int,
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    target = db.get(User, uid)
    if not target:
        raise HTTPException(404, "Usuario inexistente")

    target.password_hash = hash_password("demo1234")
    db.commit()
    log(db, user.name, "reset password", f"{target.name} / {target.dni}")
    return RedirectResponse("/admin?msg=clave_reseteada", status_code=303)


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


@app.post("/admin/update_user/{uid}")
def update_user(
    uid: int,
    name: str = Form(...),
    dni: str = Form(...),
    member_no: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    role: str = Form("socio"),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    target = db.get(User, uid)
    if not target:
        raise HTTPException(404, "Usuario inexistente")

    dni_clean = norm_dni(dni)
    if not name.strip() or not dni_clean:
        return RedirectResponse("/admin?msg=datos_usuario_invalidos", status_code=303)

    if role not in ("socio", "captain", "admin"):
        return RedirectResponse("/admin?msg=rol_invalido", status_code=303)

    existing = db.query(User).filter(User.dni == dni_clean, User.id != uid).first()
    if existing:
        return RedirectResponse("/admin?msg=usuario_existente", status_code=303)

    target.name = name.strip()
    target.dni = dni_clean
    target.member_no = member_no.strip() or None
    target.email = email.strip() or None
    target.phone = phone.strip() or None
    target.role = role
    db.commit()
    log(db, user.name, "edita usuario", f"{target.name} / {target.dni} / {target.role}")
    return RedirectResponse("/admin?msg=usuario_actualizado", status_code=303)


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
            "phone": u.phone or "",
            "role": u.role,
            "active": bool(u.active)
        }
        for u in users
    ]


@app.post("/admin/update_outing")
def update_outing(
    outing_id: int = Form(...),
    title: str = Form(...),
    destination: str = Form(...),
    departure_at: str = Form(...),
    guest_fee: float = Form(INVITED_FEE),
    db: Session = Depends(db_session),
    user: User = Depends(require_role("admin"))
):
    outing = db.get(Outing, outing_id)
    if not outing:
        raise HTTPException(404, "Salida inexistente")
    old = f"{outing.title} / {outing.destination} / {outing.departure_at.isoformat()} / tarifa {float(outing.guest_fee or 0)}"
    outing.title = title.strip() or outing.title
    outing.destination = destination.strip() or outing.destination
    outing.departure_at = datetime.fromisoformat(departure_at)
    outing.guest_fee = guest_fee
    # Si la tarifa cambió y la salida está cerrada, recalcula cargos firmes sin tocar asistencia.
    reservations = db.query(Reservation).filter_by(outing_id=outing.id).all()
    if is_closed_outing(outing):
        liquidate_and_close_boarding(db, outing, reservations, active_reservations(reservations))
    db.commit()
    new = f"{outing.title} / {outing.destination} / {outing.departure_at.isoformat()} / tarifa {float(outing.guest_fee or 0)}"
    log(db, user.name, "edición administrativa salida", f"{outing.id}: {old} -> {new}")
    return RedirectResponse(f"/admin?outing_id={outing.id}&msg=salida_actualizada", status_code=303)


@app.post("/admin/outing_status")
def admin_outing_status(
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
    log(db, user.name, "control administrativo salida", detail)
    return RedirectResponse(f"/admin?outing_id={outing.id}&msg=estado_actualizado", status_code=303)

@app.post("/admin/new_outing")
def new_outing(title: str = Form(...), destination: str = Form(...), departure_at: str = Form(...), guest_fee: float = Form(INVITED_FEE), db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    dep = datetime.fromisoformat(departure_at)
    o = Outing(title=title.strip(), destination=destination.strip(), departure_at=dep, guest_fee=guest_fee, status="En reservas", max_crew=MAX_CREW, min_crew=MIN_CREW)
    db.add(o)
    db.commit()
    db.refresh(o)
    log(db, user.name, "nueva salida", f"{title.strip()} / salida vacía")
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
            r.outing_id, row_outing.title, datetime.utcnow().date(), r.person_name, r.dni,
            v["tipo_label"], v["estado_fisico"], v["estado_reglamentario"], v["charge"], v["motivo"]
        ])
    filename = f"liquidaciones_fjord_vi_salida_{outing.id if outing else 'todas'}.csv"
    return csv_response_excel(output, filename)


@app.get("/admin/backup")
def admin_backup(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    persist_json(db)
    return FileResponse(
        str(JSON_BACKUP_PATH),
        media_type="application/json",
        filename="fjord_vi_backup.json"
    )

@app.get("/admin/export_data.json")
def export_data_json(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    data = json.dumps(export_state(db), ensure_ascii=False, indent=2)
    return Response(data, media_type="application/json", headers={"Content-Disposition": "attachment; filename=fjord_vi_backup.json"})


@app.post("/admin/restore")
async def admin_restore(file: UploadFile = File(...), db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    raw = await file.read()
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(400, "Archivo JSON inválido")
    import_state(db, data)
    log(db, user.name, "restore json", "Datos restaurados desde backup JSON")
    return RedirectResponse("/admin?msg=json_restaurado", status_code=303)

@app.post("/admin/import_data")
async def import_data_json(file: UploadFile = File(...), db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    raw = await file.read()
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(400, "Archivo JSON inválido")
    import_state(db, data)
    log(db, user.name, "import json", "Datos restaurados desde backup JSON")
    return RedirectResponse("/admin?msg=json_importado", status_code=303)

@app.post("/admin/demo_reset")
def demo_reset(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    db.query(AuditLog).delete()
    db.query(Reservation).delete()
    db.query(Outing).delete()
    db.commit()

    dep = datetime.utcnow().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=2)
    o = Outing(
        title="Paseo de domingo",
        destination="Dársena Norte / Río de la Plata",
        departure_at=dep,
        status="En reservas",
        guest_fee=INVITED_FEE,
        notes="Piloto fin de semana. Mínimo 2, máximo 9 tripulantes sin contar capitán."
    )
    db.add(o)
    db.commit()
    db.refresh(o)

    socio = db.query(User).filter_by(role="socio").first()
    db.add_all([
        Reservation(outing_id=o.id, person_name=socio.name, dni=socio.dni, kind="socio", responsible_user_id=socio.id),
        Reservation(outing_id=o.id, person_name="María Gómez", dni="35111222", kind="invitado", responsible_user_id=socio.id, status="Condicional hasta 48h"),
        Reservation(outing_id=o.id, person_name="Carlos Rodríguez", dni="23452345", kind="socio", responsible_user_id=None),
        Reservation(outing_id=o.id, person_name="Ana López", dni="32111333", kind="invitado", responsible_user_id=socio.id, status="Condicional hasta 48h"),
        Reservation(outing_id=o.id, person_name="Pedro Martínez", dni="28456456", kind="socio", responsible_user_id=None),
        Reservation(outing_id=o.id, person_name="Tomás Ruiz", dni="44999111", kind="hijo_menor", responsible_user_id=socio.id, status="Hijo menor de socio no socio", birth_date="2012-01-01"),
    ])
    db.commit()
    log(db, user.name, "demo reset", "Datos demo reiniciados")
    return RedirectResponse("/admin?msg=demo_reset", status_code=303)




@app.post("/admin/reset_clean")
def admin_reset_clean(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    db.query(AuditLog).delete()
    db.query(Reservation).delete()
    db.query(Outing).delete()
    db.commit()
    log(db, user.name, "sistema limpio", "Salidas, reservas, cargos y auditoría demo eliminados. Usuarios conservados.")
    persist_json(db)
    return RedirectResponse("/admin?msg=Sistema limpio creado", status_code=303)

