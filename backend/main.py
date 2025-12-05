from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database import Base, engine, SessionLocal
import crud
from websocket_manager import conectar
from fastapi import Request

app = FastAPI()

Base.metadata.create_all(bind=engine)

templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------- FRONTEND ----------
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


# ---------- API ----------
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
@app.websocket("/ws/{subasta_id}")
async def websocket_endpoint(websocket: WebSocket, subasta_id: int):
    await conectar(websocket, subasta_id)
