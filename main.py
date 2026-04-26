from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Fjord VI piloto estable")

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <h1>Fjord VI OK</h1>
    <p>El sistema está funcionando.</p>
    <ul>
        <li><a href="/socio">Panel socio</a></li>
        <li><a href="/capitan">Panel capitán</a></li>
        <li><a href="/admin">Panel admin</a></li>
    </ul>
    """

@app.get("/socio")
def socio():
    return {"msg": "Panel socio funcionando"}

@app.get("/capitan")
def capitan():
    return {"msg": "Panel capitán funcionando"}

@app.get("/admin")
def admin():
    return {"msg": "Panel admin funcionando"}

@app.get("/health")
def health():
    return {"status": "ok"}
