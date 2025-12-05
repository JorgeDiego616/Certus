from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database import SessionLocal, engine
import crud
from database import Base, engine
Base.metadata.create_all(bind=engine)



app = FastAPI()

templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------- FRONTEND (HTML) ----------
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/subastas", response_class=HTMLResponse)
def subastas_page(request: Request):
    db = SessionLocal()
    lista = crud.obtener_subastas(db)
    return templates.TemplateResponse("subastas.html", {"request": request, "subastas": lista})


@app.get("/subastas/{subasta_id}", response_class=HTMLResponse)
def detalle_subasta_page(request: Request, subasta_id: int):
    return templates.TemplateResponse(
        "detalle_subasta.html",
        {"request": request, "subasta_id": subasta_id}
    )


@app.get("/crear", response_class=HTMLResponse)
def crear_subasta_page(request: Request):
    return templates.TemplateResponse("crear_subasta.html", {"request": request})


# ---------- API (JSON) ----------
@app.get("/api/subastas")
def api_listar_subastas():
    db = SessionLocal()
    return crud.obtener_subastas(db)


@app.get("/api/subastas/{subasta_id}")
def api_detalle(subasta_id: int):
    db = SessionLocal()
    return crud.obtener_subasta(db, subasta_id)


@app.post("/api/pujas")
def api_puja(data: dict):
    db = SessionLocal()
    return crud.crear_puja(db, data)


# ---------- WEBSOCKETS ----------
conexiones = {}

@app.websocket("/ws/{subasta_id}")
async def websocket_endpoint(websocket: WebSocket, subasta_id: int):
    await websocket.accept()

    if subasta_id not in conexiones:
        conexiones[subasta_id] = []

    conexiones[subasta_id].append(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        conexiones[subasta_id].remove(websocket)


def notificar_puja(subasta_id: int, nuevo_precio: float):
    if subasta_id in conexiones:
        for ws in conexiones[subasta_id]:
            ws.send_json({"tipo": "nueva_puja", "nuevo_precio": nuevo_precio})
