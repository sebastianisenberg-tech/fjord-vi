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
VERSION = "v19-multi-salida"

engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    dni = Column(String, unique=True, nullable=False)
    member_no = Column(String, nullable=True)
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

ensure_schema()
app = FastAPI(title="Fjord VI V19 Multi Salida")

app.mount("/static", StaticFiles(directory=str(APP_DIR)), name="static")
templates = Jinja2Templates(directory=str(APP_DIR))

def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def norm_dni(v: str) -> str:
    return "".join(ch for ch in (v or "") if ch.isdigit())


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
        "exported_at": datetime.utcnow().isoformat(),
        "users": [
            {"id": u.id, "name": u.name, "dni": u.dni, "member_no": u.member_no, "role": u.role,
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
                    member_no=u.get("member_no"), role=u.get("role") or "socio",
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
        and r.status != "Cancelado"
        and r.attendance not in ("Ausente", "No embarcable")
    ]

def reservation_is_active(r: Reservation) -> bool:
    return (
        r.cancelled_at is None
        and r.status != "Cancelado"
        and r.attendance not in ("Ausente", "No embarcable")
    )

def ensure_outing_editable(outing: Outing):
    if outing and outing.status == "Embarque cerrado":
        raise HTTPException(status_code=400, detail="La salida ya fue cerrada")

def reactivate_reservation(db: Session, outing: Outing, r: Reservation):
    r.cancelled_at = None
    r.status = default_reservation_status(outing, r)
    r.attendance = "Por confirmar"
    r.charge_amount = 0
    r.cancel_reason = ""

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

def seed():
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            db.add_all([
                User(name="Juan Pérez", dni="20123456", member_no="1234", role="socio", password_hash=hash_password("demo1234")),
                User(name="Capitán Martín", dni="30999111", member_no="CAP-01", role="captain", password_hash=hash_password("demo1234")),
                User(name="Admin Club", dni="27999111", member_no="ADM-01", role="admin", password_hash=hash_password("demo1234")),
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
            log(db, "sistema", "seed", "Datos demo V18 creados")
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
        outing = db.query(Outing).filter(Outing.status != "Embarque cerrado").order_by(Outing.departure_at.asc()).first()
        outing = outing or db.query(Outing).order_by(Outing.departure_at.desc()).first()
    if not outing:
        return None
    refresh_reservation_states(db, outing)
    return outing

def visible_outings(db: Session):
    return db.query(Outing).order_by(Outing.departure_at.asc()).all()

def readiness_state(outing: Outing, active_count: int, present: int = 0) -> dict:
    if not outing:
        return {"label": "Sin salida", "level": "bad", "detail": "No hay una salida activa."}
    if outing.status == "Cancelada por capitán":
        return {"label": "Cancelada", "level": "bad", "detail": "La salida fue cancelada por capitán. No se generan cargos."}
    if outing.status == "Embarque cerrado":
        return {"label": "Cerrada", "level": "ok", "detail": "La salida ya fue cerrada por capitán."}
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
    active = active_reservations(reservations)
    present = sum(1 for r in active if r.attendance == "Presente")
    absent = sum(1 for r in reservations if r.attendance in ("Ausente", "No embarcable"))
    pending = sum(1 for r in active if r.attendance == "Por confirmar")
    socios_presentes = sum(1 for r in active if canonical_kind(r.kind) == "socio" and r.attendance == "Presente")
    return outing, reservations, active, present, absent, pending, socios_presentes

@app.get("/health")
def health():
    return {"ok": True, "version": VERSION, "max_crew": MAX_CREW, "min_crew": MIN_CREW, "captain_cancel_after_close": True, "database": "postgres" if DB_URL.startswith("postgres") else "sqlite", "json_backup": str(JSON_BACKUP_PATH), "json_exists": JSON_BACKUP_PATH.exists()}

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
    outings = visible_outings(db)
    outing, reservations, active, present, absent, pending, socios_presentes = outing_context(db, outing_id)
    if not outing:
        return templates.TemplateResponse(request, "socio.html", {"request": request, "user": user, "outing": None, "outings": outings, "msg": request.query_params.get("msg")})
    mine = [r for r in reservations if r.dni == user.dni or r.responsible_user_id == user.id]
    has_self = any(r.dni == user.dni and reservation_is_active(r) for r in mine)
    self_reservation = next((r for r in mine if r.dni == user.dni), None)
    ready = readiness_state(outing, len(active))
    return templates.TemplateResponse(request, "socio.html", {
        "request": request, "user": user, "outing": outing, "outings": outings, "reservations": reservations,
        "active": active, "mine": mine, "has_self": has_self, "self_reservation": self_reservation,
        "active_count": len(active), "remaining": max(0, outing.max_crew - len(active)),
        "readiness": ready, "cutoff": cutoff_passed(outing), "late_window": late_window_passed(outing),
        "cutoff_at": cutoff_at(outing), "cancel_deadline": cancellation_deadline(outing),
        "fee": float(outing.guest_fee), "msg": request.query_params.get("msg"),
        "closed": outing.status == "Embarque cerrado"
    })

@app.post("/socio/add_self")
def add_self(outing_id: Optional[int] = Form(None), db: Session = Depends(db_session), user: User = Depends(require_role("socio"))):
    outing, reservations, active, *_ = outing_context(db, outing_id)
    ensure_outing_editable(outing)
    existing = db.query(Reservation).filter_by(outing_id=outing.id, dni=user.dni).first()
    if existing and reservation_is_active(existing):
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=ya_anotado", status_code=303)
    if len(active) >= outing.max_crew:
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=cupo_completo", status_code=303)
    if existing:
        existing.kind = "socio"
        existing.person_name = user.name
        existing.responsible_user_id = user.id
        reactivate_reservation(db, outing, existing)
    else:
        db.add(Reservation(outing_id=outing.id, person_name=user.name, dni=user.dni, kind="socio", responsible_user_id=user.id))
    db.commit()
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

    # Si no quedan lugares, se responde con mensaje claro antes de intentar crear/reactivar.
    if len(active) >= outing.max_crew:
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=cupo_completo", status_code=303)

    if kind not in ("invitado", "hijo_menor") or not person_name or not dni_clean:
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=datos_invalidos", status_code=303)

    if kind == "hijo_menor":
        # Solo se pide fecha para esta categoría especial.
        # Valida que sea menor de 18 años a la fecha de salida.
        if not birth_date or not is_under_18_on(birth_date, outing.departure_at):
            return RedirectResponse(f"/socio?outing_id={outing.id}&msg=hijo_menor_invalido", status_code=303)
    else:
        birth_date = None

    self_row = db.query(Reservation).filter_by(outing_id=outing.id, dni=user.dni).first()
    if not self_row or not reservation_is_active(self_row):
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=socio_requerido", status_code=303)

    existing = db.query(Reservation).filter_by(outing_id=outing.id, dni=dni_clean).first()

    if existing and existing.responsible_user_id != user.id:
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=duplicado", status_code=303)

    if existing and reservation_is_active(existing):
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=duplicado", status_code=303)

    if existing:
        existing.person_name = person_name
        existing.kind = kind
        existing.birth_date = birth_date
        existing.responsible_user_id = user.id
        reactivate_reservation(db, outing, existing)
    else:
        status = "Hijo menor de socio no socio" if kind == "hijo_menor" else ("Confirmado" if cutoff_passed(outing) else "Condicional hasta 48h")
        db.add(Reservation(
            outing_id=outing.id,
            person_name=person_name,
            dni=dni_clean,
            kind=kind,
            responsible_user_id=user.id,
            status=status,
            birth_date=birth_date
        ))

    db.commit()
    log(db, user.name, "agrega/reactiva invitado", f"{person_name} / {outing.title}")

    return RedirectResponse(f"/socio?outing_id={outing.id}&msg=invitado_ok", status_code=303)

@app.post("/socio/cancel/{rid}")
def cancel_reservation(rid: int, outing_id: Optional[int] = Form(None), db: Session = Depends(db_session), user: User = Depends(require_role("socio"))):
    r = db.get(Reservation, rid)
    outing = selected_outing(db, outing_id)
    ensure_outing_editable(outing)
    if not r or r.outing_id != outing.id or not (r.dni == user.dni or r.responsible_user_id == user.id):
        raise HTTPException(403)

    now = datetime.utcnow()
    r.cancelled_at = now
    r.status = "Cancelado"
    r.attendance = "Ausente"
    r.cancel_reason = "Cancelado por socio"
    r.charge_amount = reservation_charge(outing, r) if late_window_passed(outing) else 0

    # Regla operativa: si el socio titular se baja de una salida,
    # sus invitados/menores de esa misma salida quedan automáticamente fuera.
    # No pueden ocupar cupo ni embarcar sin el socio responsable.
    if r.dni == user.dni:
        dependientes = db.query(Reservation).filter(
            Reservation.outing_id == outing.id,
            Reservation.responsible_user_id == user.id,
            Reservation.dni != user.dni,
            Reservation.cancelled_at.is_(None)
        ).all()
        for dep in dependientes:
            dep.cancelled_at = now
            dep.status = "Cancelado"
            dep.attendance = "Ausente"
            dep.cancel_reason = "Cancelado por baja del socio responsable"
            dep.charge_amount = reservation_charge(outing, dep) if late_window_passed(outing) else 0

    db.commit()
    log(db, user.name, "cancela reserva", f"{r.person_name} / {outing.title} / cargo {r.charge_amount}")
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
    if len(active) >= outing.max_crew:
        return RedirectResponse(f"/socio?outing_id={outing.id}&msg=cupo_completo", status_code=303)
    reactivate_reservation(db, outing, r)
    db.commit()
    log(db, user.name, "reactiva reserva", f"{r.person_name} / {outing.title}")
    return RedirectResponse(f"/socio?outing_id={outing.id}&msg=reactivado", status_code=303)

@app.get("/captain", response_class=HTMLResponse)
def captain(request: Request, outing_id: Optional[int] = None, db: Session = Depends(db_session), user: User = Depends(require_role("captain", "admin"))):
    outings = visible_outings(db)
    outing, reservations, active, present, absent, pending, socios_presentes = outing_context(db, outing_id)
    ready = readiness_state(outing, len(active), present)
    return templates.TemplateResponse(request, "captain.html", {
        "request": request, "user": user, "outing": outing, "outings": outings, "reservations": reservations,
        "active": active, "active_count": len(active), "present": present, "absent": absent,
        "pending": pending, "socios_presentes": socios_presentes, "readiness": ready,
        "cutoff": cutoff_passed(outing), "cutoff_at": cutoff_at(outing), "msg": request.query_params.get("msg")
    })

@app.post("/captain/outing_status")
def outing_status(outing_id: Optional[int] = Form(None), status: str = Form(...), db: Session = Depends(db_session), user: User = Depends(require_role("captain", "admin"))):
    outing = selected_outing(db, outing_id)
    if not outing:
        raise HTTPException(400, "Salida inexistente")

    allowed_statuses = [
        "En reservas",
        "En embarque",
        "Demorada",
        "Reprogramada",
        "Cancelada por capitán",
        "Embarque cerrado",
        "Realizada",
    ]
    if status not in allowed_statuses:
        raise HTTPException(400)

    old_status = outing.status

    # Caso operativo real: la salida puede estar cerrada y aun así cancelarse
    # por decisión del capitán antes de zarpar o por fuerza mayor.
    # En ese caso no se cobra nada a nadie, pero se conserva la lista como registro.
    if status == "Cancelada por capitán":
        reservations = db.query(Reservation).filter_by(outing_id=outing.id).all()
        for r in reservations:
            r.charge_amount = 0
            r.cancel_reason = "Cancelada por capitán"
            if r.attendance == "Por confirmar":
                r.attendance = "Ausente"
        outing.status = "Cancelada por capitán"
        db.commit()
        log(db, user.name, "salida cancelada por capitán", f"{outing.title} / estado anterior: {old_status} / cargos anulados")
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=estado_actualizado", status_code=303)

    # Reapertura controlada: permite corregir una salida cerrada por error
    # o volver a embarque si la operación sigue viva.
    if old_status == "Embarque cerrado" and status in ("En embarque", "Demorada", "Reprogramada", "En reservas"):
        outing.status = status
        db.commit()
        log(db, user.name, "reabre/cambia salida cerrada", f"{outing.title}: {old_status} -> {status}")
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=estado_actualizado", status_code=303)

    # Cualquier salida cancelada puede reabrirse solo por capitán/admin.
    if old_status == "Cancelada por capitán" and status in ("En embarque", "Demorada", "Reprogramada", "En reservas"):
        outing.status = status
        db.commit()
        log(db, user.name, "reabre salida cancelada", f"{outing.title}: {old_status} -> {status}")
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=estado_actualizado", status_code=303)

    # Realizada es final administrativo, salvo que se cancele por capitán/admin.
    if old_status == "Realizada" and status not in ("Cancelada por capitán",):
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=salida_cerrada", status_code=303)

    outing.status = status
    db.commit()
    log(db, user.name, "estado salida", f"{outing.title}: {old_status} -> {status}")
    return RedirectResponse(f"/captain?outing_id={outing.id}&msg=estado_actualizado", status_code=303)

@app.post("/captain/attendance/{rid}/{value}")
def attendance(rid: int, value: str, db: Session = Depends(db_session), user: User = Depends(require_role("captain", "admin"))):
    r = db.get(Reservation, rid)
    if not r or value not in ["Presente", "Ausente", "Por confirmar"]:
        raise HTTPException(400)

    outing = db.get(Outing, r.outing_id)
    if outing and outing.status == "Embarque cerrado":
        raise HTTPException(400, "El embarque ya fue cerrado")

    if value in ("Presente", "Por confirmar"):
        r.cancelled_at = None
        r.status = default_reservation_status(outing, r)
        r.cancel_reason = ""
        r.charge_amount = 0
        r.attendance = value
    elif value == "Ausente":
        r.attendance = "Ausente"
        r.charge_amount = reservation_charge(outing, r)

    db.commit()
    log(db, user.name, "asistencia", f"{r.person_name}: {value} / {outing.title}")
    return RedirectResponse(f"/captain?outing_id={outing.id}&msg=asistencia_actualizada", status_code=303)

@app.post("/captain/close")
def close_boarding(outing_id: Optional[int] = Form(None), db: Session = Depends(db_session), user: User = Depends(require_role("captain", "admin"))):
    outing, reservations, active, present, *_ = outing_context(db, outing_id)
    if not outing:
        raise HTTPException(400, "Salida inexistente")
    if outing.status in ("Embarque cerrado", "Cancelada por capitán", "Realizada"):
        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=salida_cerrada", status_code=303)
    if present < outing.min_crew:
        raise HTTPException(400, f"No se cumple el mínimo de {outing.min_crew}")
    if present > outing.max_crew:
        raise HTTPException(400, f"Se supera el máximo de {outing.max_crew}")

    users = {u.id: u for u in db.query(User).all()}
    present_dnis = {r.dni for r in active if canonical_kind(r.kind) == "socio" and r.attendance == "Presente"}
    guest_fee = float(outing.guest_fee or 0)

    for r in reservations:
        k = canonical_kind(r.kind)

        if r.cancelled_at is not None:
            if r.charge_amount is None:
                r.charge_amount = 0
            continue

        if r.attendance == "Por confirmar":
            r.attendance = "Ausente"

        # Invitados e hijos menores no socios solo pueden embarcar si embarca su socio responsable.
        if k in ("invitado", "hijo_menor") and r.attendance == "Presente":
            responsible = users.get(r.responsible_user_id)
            if responsible and responsible.dni not in present_dnis:
                r.attendance = "No embarcable"

        # Liquidación final:
        # - Socio presente: sin cargo.
        # - Invitado presente: paga tarifa completa de invitado.
        # - Hijo menor de socio no socio presente: sin cargo.
        # - Ausente/no embarcable: aplica cargo reglamentario por plaza perdida.
        if r.attendance in ("Ausente", "No embarcable"):
            r.charge_amount = reservation_charge(outing, r)
        elif r.attendance == "Presente":
            if k == "invitado":
                r.charge_amount = guest_fee
            else:
                r.charge_amount = 0

    outing.status = "Embarque cerrado"
    db.commit()
    log(db, user.name, "cierre embarque", f"{outing.title} / presentes {present}")
    return RedirectResponse(f"/captain?outing_id={outing.id}&msg=cierre_ok", status_code=303)

@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, outing_id: Optional[int] = None, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    outings = visible_outings(db)
    outing, reservations, active, present, absent, pending, socios_presentes = outing_context(db, outing_id)
    charges = db.query(Reservation).filter(Reservation.outing_id == outing.id, Reservation.charge_amount > 0).all() if outing else []
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(15).all()
    total_charges = sum(float(r.charge_amount or 0) for r in charges)
    ready = readiness_state(outing, len(active), present)
    counts = {o.id: db.query(Reservation).filter_by(outing_id=o.id).count() for o in outings}
    active_counts = {o.id: len(active_reservations(db.query(Reservation).filter_by(outing_id=o.id).all())) for o in outings}
    return templates.TemplateResponse(request, "admin.html", {
        "request": request, "user": user, "outing": outing, "outings": outings, "counts": counts, "active_counts": active_counts,
        "reservations": reservations, "active": active, "active_count": len(active),
        "present": present, "pending": pending, "charges": charges,
        "total_charges": total_charges, "logs": logs, "readiness": ready,
        "msg": request.query_params.get("msg")
    })

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
    writer.writerow(["salida_id", "salida", "fecha", "nombre", "dni", "tipo", "estado_reserva", "asistencia", "cargo", "responsable_id", "cancelado_en"])
    for r in reservations:
        writer.writerow([outing.id, outing.title, outing.departure_at.isoformat(), r.person_name, r.dni, canonical_kind(r.kind), r.status, r.attendance, float(r.charge_amount or 0), r.responsible_user_id or "", r.cancelled_at.isoformat() if r.cancelled_at else ""])
    filename = f"manifest_fjord_vi_salida_{outing.id}.csv"
    return csv_response_excel(output, filename)

@app.get("/admin/charges.csv")
def charges_csv(outing_id: Optional[int] = None, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    outing = selected_outing(db, outing_id)
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["salida_id", "salida", "fecha_liquidacion", "nombre", "dni", "tipo", "importe", "motivo"])
    q = db.query(Reservation).filter(Reservation.charge_amount > 0)
    if outing:
        q = q.filter(Reservation.outing_id == outing.id)
    for r in q.all():
        writer.writerow([r.outing_id, outing.title if outing else "", datetime.utcnow().date(), r.person_name, r.dni, canonical_kind(r.kind), float(r.charge_amount), r.cancel_reason or r.attendance])
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
    log(db, user.name, "demo reset", "Datos demo V18 reiniciados")
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

