from datetime import datetime, timedelta
from pathlib import Path
import csv
import hashlib
import hmac
import io
import os
import secrets
from typing import Optional

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Numeric, UniqueConstraint, Text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

APP_DIR = Path(__file__).parent
DATA_DIR = Path(os.getenv("DATA_DIR", APP_DIR))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR/'fjord_v18_pilot.db'}")
SECRET_KEY = os.getenv("SECRET_KEY", "pilot-secret-change-me")
MAX_CREW = int(os.getenv("MAX_CREW", "9"))
MIN_CREW = int(os.getenv("MIN_CREW", "2"))
INVITED_FEE = float(os.getenv("INVITED_FEE", "4500"))
LATE_SOCIO_RATE = float(os.getenv("LATE_SOCIO_RATE", "0.70"))
VERSION = "v18-deploy-ready"

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

app = FastAPI(title="Fjord VI V18 Deploy Ready")

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

def log(db: Session, actor: str, action: str, detail: str = ""):
    db.add(AuditLog(actor=actor, action=action, detail=detail))
    db.commit()

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

def default_reservation_status(outing: Outing, r: Reservation) -> str:
    if r.kind == "menor":
        return "Hijo menor hasta 13"
    if r.kind == "invitado" and not cutoff_passed(outing):
        return "Condicional hasta 48h"
    return "Confirmado"

def cutoff_at(outing: Outing) -> datetime:
    return outing.departure_at - timedelta(hours=48)

def cancellation_deadline(outing: Outing) -> datetime:
    return outing.departure_at - timedelta(days=4)

def cutoff_passed(outing: Outing) -> bool:
    return datetime.utcnow() >= cutoff_at(outing)

def late_window_passed(outing: Outing) -> bool:
    return datetime.utcnow() >= cancellation_deadline(outing)

def reservation_charge(outing: Outing, r: Reservation) -> float:
    fee = float(outing.guest_fee or 0)
    if r.kind == "socio":
        return round(fee * LATE_SOCIO_RATE, 2)
    if r.kind == "invitado":
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
                Reservation(outing_id=o.id, person_name="Tomás Ruiz", dni="44999111", kind="menor", responsible_user_id=socio.id, status="Hijo menor hasta 13"),
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

def selected_outing(db: Session, outing_id: Optional[int] = None):
    if outing_id:
        outing = db.get(Outing, outing_id)
    else:
        outing = db.query(Outing).filter(Outing.status != "Embarque cerrado").order_by(Outing.departure_at.asc()).first()
        outing = outing or db.query(Outing).order_by(Outing.departure_at.desc()).first()
    refresh_reservation_states(db, outing)
    return outing

def readiness_state(outing: Outing, active_count: int, present: int = 0) -> dict:
    if not outing:
        return {"label": "Sin salida", "level": "bad", "detail": "No hay una salida activa."}
    if outing.status == "Embarque cerrado":
        return {"label": "Cerrada", "level": "ok", "detail": "La salida ya fue cerrada por capitán."}
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
    socios_presentes = sum(1 for r in active if r.kind == "socio" and r.attendance == "Presente")
    return outing, reservations, active, present, absent, pending, socios_presentes

@app.get("/health")
def health():
    return {"ok": True, "version": VERSION, "max_crew": MAX_CREW, "min_crew": MIN_CREW, "database": DB_URL}

@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(db_session), user: Optional[User] = Depends(current_user)):
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "version": VERSION, "error": request.query_params.get("error")})
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
    resp.delete_cookie("fjord_uid")
    return resp

@app.get("/socio", response_class=HTMLResponse)
def socio(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("socio"))):
    outing, reservations, active, present, absent, pending, socios_presentes = outing_context(db)
    mine = [r for r in reservations if r.dni == user.dni or r.responsible_user_id == user.id]
    has_self = any(r.dni == user.dni and r.cancelled_at is None for r in mine)
    ready = readiness_state(outing, len(active))
    return templates.TemplateResponse("socio.html", {
        "request": request, "user": user, "outing": outing, "reservations": reservations,
        "active": active, "mine": mine, "has_self": has_self, "active_count": len(active),
        "remaining": max(0, outing.max_crew - len(active)), "readiness": ready,
        "cutoff": cutoff_passed(outing), "late_window": late_window_passed(outing),
        "cutoff_at": cutoff_at(outing), "cancel_deadline": cancellation_deadline(outing),
        "fee": float(outing.guest_fee), "msg": request.query_params.get("msg")
    })

@app.post("/socio/add_self")
def add_self(db: Session = Depends(db_session), user: User = Depends(require_role("socio"))):
    outing, reservations, active, *_ = outing_context(db)
    if len(active) >= outing.max_crew:
        return RedirectResponse("/socio?msg=cupo_completo", status_code=303)
    existing = db.query(Reservation).filter_by(outing_id=outing.id, dni=user.dni).first()
    if existing and existing.cancelled_at is None:
        return RedirectResponse("/socio?msg=ya_anotado", status_code=303)
    if existing and existing.cancelled_at is not None:
        existing.cancelled_at = None
        existing.status = "Confirmado"
        existing.attendance = "Por confirmar"
        existing.charge_amount = 0
        existing.cancel_reason = ""
    else:
        db.add(Reservation(outing_id=outing.id, person_name=user.name, dni=user.dni, kind="socio", responsible_user_id=user.id))
    db.commit()
    log(db, user.name, "reserva socio", outing.title)
    return RedirectResponse("/socio?msg=reserva_ok", status_code=303)

@app.post("/socio/add_guest")
def add_guest(name: str = Form(...), dni: str = Form(...), kind: str = Form("invitado"), db: Session = Depends(db_session), user: User = Depends(require_role("socio"))):
    outing, reservations, active, *_ = outing_context(db)
    if len(active) >= outing.max_crew:
        return RedirectResponse("/socio?msg=cupo_completo", status_code=303)
    dni_clean = norm_dni(dni)
    if kind not in ("invitado", "menor") or not name.strip() or not dni_clean:
        return RedirectResponse("/socio?msg=datos_invalidos", status_code=303)
    if not db.query(Reservation).filter_by(outing_id=outing.id, dni=user.dni, cancelled_at=None).first():
        return RedirectResponse("/socio?msg=socio_requerido", status_code=303)
    if db.query(Reservation).filter_by(outing_id=outing.id, dni=dni_clean).first():
        return RedirectResponse("/socio?msg=duplicado", status_code=303)
    status = "Hijo menor hasta 13" if kind == "menor" else ("Confirmado" if cutoff_passed(outing) else "Condicional hasta 48h")
    db.add(Reservation(outing_id=outing.id, person_name=name.strip(), dni=dni_clean, kind=kind, responsible_user_id=user.id, status=status))
    db.commit()
    log(db, user.name, "agrega invitado", f"{name.strip()} / {outing.title}")
    return RedirectResponse("/socio?msg=invitado_ok", status_code=303)

@app.post("/socio/cancel/{rid}")
def cancel_reservation(rid: int, db: Session = Depends(db_session), user: User = Depends(require_role("socio"))):
    r = db.get(Reservation, rid)
    outing = selected_outing(db)
    if not r or r.outing_id != outing.id or not (r.dni == user.dni or r.responsible_user_id == user.id):
        raise HTTPException(403)
    r.cancelled_at = datetime.utcnow()
    r.status = "Cancelado"
    r.attendance = "Ausente"
    r.cancel_reason = "Cancelado por socio"
    r.charge_amount = reservation_charge(outing, r) if late_window_passed(outing) else 0
    db.commit()
    log(db, user.name, "cancela reserva", f"{r.person_name} / cargo {r.charge_amount}")
    return RedirectResponse("/socio?msg=cancelado", status_code=303)

@app.get("/captain", response_class=HTMLResponse)
def captain(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("captain", "admin"))):
    outing, reservations, active, present, absent, pending, socios_presentes = outing_context(db)
    ready = readiness_state(outing, len(active), present)
    return templates.TemplateResponse("captain.html", {
        "request": request, "user": user, "outing": outing, "reservations": reservations,
        "active": active, "active_count": len(active), "present": present, "absent": absent,
        "pending": pending, "socios_presentes": socios_presentes, "readiness": ready,
        "cutoff": cutoff_passed(outing), "cutoff_at": cutoff_at(outing), "msg": request.query_params.get("msg")
    })

@app.post("/captain/outing_status")
def outing_status(status: str = Form(...), db: Session = Depends(db_session), user: User = Depends(require_role("captain", "admin"))):
    outing = selected_outing(db)
    if status not in ["En reservas", "En embarque", "Demorada", "Cancelada por capitán", "Programada"]:
        raise HTTPException(400)
    outing.status = status
    db.commit()
    log(db, user.name, "estado salida", status)
    return RedirectResponse("/captain?msg=estado_actualizado", status_code=303)

@app.post("/captain/attendance/{rid}/{value}")
def attendance(rid: int, value: str, db: Session = Depends(db_session), user: User = Depends(require_role("captain", "admin"))):
    r = db.get(Reservation, rid)
    if not r or value not in ["Presente", "Ausente", "Por confirmar"]:
        raise HTTPException(400)

    outing = db.get(Outing, r.outing_id)
    if outing and outing.status == "Embarque cerrado":
        raise HTTPException(400, "El embarque ya fue cerrado")

    # Regla operativa: hasta el cierre, el capitán puede rearmar la tripulación.
    # Por eso una reserva cancelada/ausente puede volver a lista o pasar a presente.
    if value in ("Presente", "Por confirmar"):
        r.cancelled_at = None
        r.status = default_reservation_status(outing, r)
        r.cancel_reason = ""
        r.charge_amount = 0
        r.attendance = value
    elif value == "Ausente":
        r.attendance = "Ausente"
        r.charge_amount = reservation_charge(outing, r)
        # No la convertimos en estado terminal. Queda reversible hasta el cierre.

    db.commit()
    log(db, user.name, "asistencia", f"{r.person_name}: {value}")
    return RedirectResponse("/captain?msg=asistencia_actualizada", status_code=303)

@app.post("/captain/close")
def close_boarding(db: Session = Depends(db_session), user: User = Depends(require_role("captain", "admin"))):
    outing, reservations, active, present, *_ = outing_context(db)
    if present < outing.min_crew:
        raise HTTPException(400, f"No se cumple el mínimo de {outing.min_crew}")
    if present > outing.max_crew:
        raise HTTPException(400, f"Se supera el máximo de {outing.max_crew}")
    users = {u.id: u for u in db.query(User).all()}
    present_dnis = {r.dni for r in active if r.kind == "socio" and r.attendance == "Presente"}
    for r in reservations:
        if r.cancelled_at is not None:
            continue
        if r.attendance == "Por confirmar":
            r.attendance = "Ausente"
        if r.kind in ("invitado", "menor") and r.attendance == "Presente":
            responsible = users.get(r.responsible_user_id)
            if responsible and responsible.dni not in present_dnis:
                r.attendance = "No embarcable"
        if r.attendance in ("Ausente", "No embarcable"):
            r.charge_amount = reservation_charge(outing, r)
        elif r.attendance == "Presente":
            r.charge_amount = 0
    outing.status = "Embarque cerrado"
    db.commit()
    log(db, user.name, "cierre embarque", f"presentes {present}")
    return RedirectResponse("/captain?msg=cierre_ok", status_code=303)

@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    outing, reservations, active, present, absent, pending, socios_presentes = outing_context(db)
    charges = db.query(Reservation).filter(Reservation.charge_amount > 0).all()
    outings = db.query(Outing).order_by(Outing.departure_at.asc()).all()
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(15).all()
    total_charges = sum(float(r.charge_amount or 0) for r in charges)
    ready = readiness_state(outing, len(active), present)
    return templates.TemplateResponse("admin.html", {
        "request": request, "user": user, "outing": outing, "outings": outings,
        "reservations": reservations, "active": active, "active_count": len(active),
        "present": present, "pending": pending, "charges": charges,
        "total_charges": total_charges, "logs": logs, "readiness": ready,
        "msg": request.query_params.get("msg")
    })

@app.post("/admin/new_outing")
def new_outing(title: str = Form(...), destination: str = Form(...), departure_at: str = Form(...), guest_fee: float = Form(INVITED_FEE), db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    dep = datetime.fromisoformat(departure_at)
    db.add(Outing(title=title.strip(), destination=destination.strip(), departure_at=dep, guest_fee=guest_fee, status="En reservas", max_crew=MAX_CREW, min_crew=MIN_CREW))
    db.commit()
    log(db, user.name, "nueva salida", title.strip())
    return RedirectResponse("/admin?msg=salida_creada", status_code=303)

@app.get("/admin/manifest.csv")
def manifest_csv(db: Session = Depends(db_session), user: User = Depends(require_role("admin", "captain"))):
    outing, reservations, *_ = outing_context(db)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["salida", "fecha", "nombre", "dni", "tipo", "estado_reserva", "asistencia", "cargo", "responsable_id", "cancelado_en"])
    for r in reservations:
        writer.writerow([outing.title, outing.departure_at.isoformat(), r.person_name, r.dni, r.kind, r.status, r.attendance, float(r.charge_amount or 0), r.responsible_user_id or "", r.cancelled_at.isoformat() if r.cancelled_at else ""])
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=manifest_fjord_vi_v18.csv"})

@app.get("/admin/charges.csv")
def charges_csv(db: Session = Depends(db_session), user: User = Depends(require_role("admin"))):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["fecha_liquidacion", "nombre", "dni", "tipo", "importe", "motivo"])
    for r in db.query(Reservation).filter(Reservation.charge_amount > 0).all():
        writer.writerow([datetime.utcnow().date(), r.person_name, r.dni, r.kind, float(r.charge_amount), r.cancel_reason or r.attendance])
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=liquidaciones_fjord_vi_v18.csv"})

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
        Reservation(outing_id=o.id, person_name="Tomás Ruiz", dni="44999111", kind="menor", responsible_user_id=socio.id, status="Hijo menor hasta 13"),
    ])
    db.commit()
    log(db, user.name, "demo reset", "Datos demo V18 reiniciados")
    return RedirectResponse("/admin?msg=demo_reset", status_code=303)
