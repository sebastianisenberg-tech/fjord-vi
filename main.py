from datetime import datetime, timedelta
from pathlib import Path
import os
import hashlib
import hmac
import secrets
from typing import Optional

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# ---------------- CONFIG ----------------

APP_DIR = Path(__file__).parent
DB_URL = f"sqlite:///{APP_DIR / 'fjord.db'}"
SECRET_KEY = "cambiar-esto-en-produccion"

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

app = FastAPI(title="Fjord VI v22")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

# ---------------- MODELOS ----------------

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    dni = Column(String, unique=True)
    role = Column(String)
    password = Column(String)

# ---------------- DB ----------------

Base.metadata.create_all(engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------- AUTH ----------------

def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str):
    return hash_password(password) == hashed

# ---------------- SEED ----------------

def seed():
    db = SessionLocal()
    if db.query(User).count() == 0:
        db.add_all([
            User(name="Juan Pérez", dni="20123456", role="socio", password=hash_password("demo1234")),
            User(name="Capitán Martín", dni="30999111", role="captain", password=hash_password("demo1234")),
            User(name="Admin", dni="27999111", role="admin", password=hash_password("demo1234")),
        ])
        db.commit()
    db.close()

seed()

# ---------------- ROUTES ----------------

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(dni: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter_by(dni=dni).first()
    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    if user.role == "admin":
        return RedirectResponse("/admin", status_code=303)
    elif user.role == "captain":
        return RedirectResponse("/captain", status_code=303)
    else:
        return RedirectResponse("/socio", status_code=303)

@app.get("/socio")
def socio():
    return {"msg": "Panel socio funcionando"}

@app.get("/captain")
def captain():
    return {"msg": "Panel capitán funcionando"}

@app.get("/admin")
def admin():
    return {"msg": "Panel admin funcionando"}

@app.get("/health")
def health():
    return {"status": "ok", "version": "v22"}
