from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Fjord VI V19 Stable")

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head>
        <title>Fjord VI</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #1e3c72, #2a5298);
                color: white;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }
            .card {
                background: white;
                color: black;
                padding: 30px;
                border-radius: 16px;
                width: 90%;
                max-width: 400px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            }
            h1 {
                margin-bottom: 5px;
            }
            h2 {
                margin-top: 0;
                color: #555;
                font-size: 16px;
            }
            input {
                width: 100%;
                padding: 12px;
                margin-top: 10px;
                margin-bottom: 15px;
                border-radius: 8px;
                border: 1px solid #ccc;
            }
            button {
                width: 100%;
                padding: 14px;
                background: #0b2545;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                cursor: pointer;
            }
            .demo {
                margin-top: 20px;
                font-size: 13px;
                background: #f3f3f3;
                padding: 10px;
                border-radius: 8px;
            }
            .version {
                margin-top: 15px;
                text-align: center;
                font-size: 12px;
                color: #777;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>FJORD VI</h1>
            <h2>Sistema de reservas</h2>

            <p><b>Versión estable V19</b></p>

            <label>DNI</label>
            <input placeholder="20123456">

            <label>Clave</label>
            <input placeholder="demo1234">

            <button>Ingresar al sistema</button>

            <div class="demo">
                Socio: 20123456 / demo1234<br>
                Capitán: 30999111 / demo1234<br>
                Admin: 27999111 / demo1234
            </div>

            <div class="version">
                fjord-vi V19 stable build
            </div>
        </div>
    </body>
    </html>
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
