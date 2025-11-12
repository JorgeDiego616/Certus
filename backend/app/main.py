from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from typing import List, Dict
import json
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================================
# 🔧 CONFIGURACIÓN BASE DE DATOS
# ========================================

DATABASE_URL = "postgresql://user:password@db:5432/subastas_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ========================================
# 🧱 MODELOS SQLALCHEMY
# ========================================

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    pujas = relationship("Puja", back_populates="usuario")


class Subasta(Base):
    __tablename__ = "subastas"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, index=True)
    descripcion = Column(String)
    precio_inicial = Column(Float)
    precio_actual = Column(Float)
    fecha_inicio = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    fecha_fin = Column(DateTime)
    activa = Column(Integer, default=1)
    pujas = relationship("Puja", back_populates="subasta")


class Puja(Base):
    __tablename__ = "pujas"

    id = Column(Integer, primary_key=True, index=True)
    monto = Column(Float)
    fecha = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    subasta_id = Column(Integer, ForeignKey("subastas.id"))

    usuario = relationship("Usuario", back_populates="pujas")
    subasta = relationship("Subasta", back_populates="pujas")


Base.metadata.create_all(bind=engine)


# ========================================
# 📦 MODELOS Pydantic
# ========================================

class SubastaCreate(BaseModel):
    titulo: str
    descripcion: str
    precio_inicial: float
    duracion_horas: int = 24


class PujaCreate(BaseModel):
    subasta_id: int
    usuario_id: int
    monto: float


class UsuarioCreate(BaseModel):
    nombre: str
    email: str


# ========================================
# 🚀 CONFIGURACIÓN FASTAPI
# ========================================

app = FastAPI(
    title="API de Subastas",
    description="Sistema de subastas en tiempo real con WebSockets",
    version="2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========================================
# 🧩 DEPENDENCIA DE SESIÓN BD
# ========================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ========================================
# 🔌 GESTOR DE CONEXIONES WEBSOCKET
# ========================================

class ConnectionManager:
    """
    Gestiona conexiones WebSocket agrupadas por subasta.
    Solo notifica a usuarios interesados en cada subasta específica.
    """
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, subasta_id: int):
        await websocket.accept()
        if subasta_id not in self.active_connections:
            self.active_connections[subasta_id] = []
        self.active_connections[subasta_id].append(websocket)
        logger.info(f"Cliente conectado a subasta {subasta_id}. Total: {len(self.active_connections[subasta_id])}")

    def disconnect(self, websocket: WebSocket, subasta_id: int):
        if subasta_id in self.active_connections:
            try:
                self.active_connections[subasta_id].remove(websocket)
                logger.info(f"Cliente desconectado de subasta {subasta_id}")
                if not self.active_connections[subasta_id]:
                    del self.active_connections[subasta_id]
            except ValueError:
                pass

    async def broadcast(self, subasta_id: int, message: str):
        """Envía mensaje a todos los clientes de una subasta específica"""
        if subasta_id not in self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections[subasta_id]:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error enviando mensaje: {e}")
                disconnected.append(connection)
        
        # Limpiar conexiones muertas
        for conn in disconnected:
            self.disconnect(conn, subasta_id)


manager = ConnectionManager()


# ========================================
# 🌐 ENDPOINTS REST
# ========================================

@app.get("/")
def read_root():
    return {
        "mensaje": "API de Subastas funcionando 🚀",
        "version": "2.0",
        "docs": "/docs"
    }


@app.post("/usuarios/", status_code=201)
def crear_usuario(usuario: UsuarioCreate, db: Session = Depends(get_db)):
    """Registra un nuevo usuario validando duplicados"""
    existing = db.query(Usuario).filter(
        (Usuario.nombre == usuario.nombre) | (Usuario.email == usuario.email)
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400, 
            detail="El nombre de usuario o email ya está registrado"
        )

    nuevo_usuario = Usuario(nombre=usuario.nombre, email=usuario.email)
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario


@app.get("/usuarios/")
def listar_usuarios(db: Session = Depends(get_db)):
    """Lista todos los usuarios registrados"""
    return db.query(Usuario).all()


@app.post("/subastas/", status_code=201)
def crear_subasta(subasta: SubastaCreate, db: Session = Depends(get_db)):
    """Crea una nueva subasta con duración configurable"""
    fecha_fin = datetime.now(timezone.utc) + timedelta(hours=subasta.duracion_horas)
    
    nueva_subasta = Subasta(
        titulo=subasta.titulo,
        descripcion=subasta.descripcion,
        precio_inicial=subasta.precio_inicial,
        precio_actual=subasta.precio_inicial,
        fecha_fin=fecha_fin
    )
    db.add(nueva_subasta)
    db.commit()
    db.refresh(nueva_subasta)
    logger.info(f"Subasta creada: {nueva_subasta.titulo} (ID: {nueva_subasta.id})")
    return nueva_subasta


@app.get("/subastas/")
def obtener_subastas(activas_solo: bool = True, db: Session = Depends(get_db)):
    """Lista todas las subastas, opcionalmente solo las activas"""
    query = db.query(Subasta)
    if activas_solo:
        query = query.filter(Subasta.activa == 1)
    return query.all()


@app.get("/subastas/{subasta_id}")
def obtener_subasta(subasta_id: int, db: Session = Depends(get_db)):
    """Obtiene detalles de una subasta específica"""
    subasta = db.query(Subasta).filter(Subasta.id == subasta_id).first()
    if not subasta:
        raise HTTPException(status_code=404, detail="Subasta no encontrada")
    return subasta


@app.post("/pujas/", status_code=201)
async def crear_puja(puja: PujaCreate, db: Session = Depends(get_db)):
    """Registra una nueva puja y notifica a los usuarios conectados"""
    
    # Validar subasta
    subasta = db.query(Subasta).filter(Subasta.id == puja.subasta_id).first()
    if not subasta:
        raise HTTPException(status_code=404, detail="Subasta no encontrada")
    
    if not subasta.activa:
        raise HTTPException(status_code=400, detail="Subasta no está activa")

    # Verificar si expiró
    if datetime.now(timezone.utc) > subasta.fecha_fin:
        subasta.activa = 0
        db.commit()
        raise HTTPException(status_code=400, detail="Subasta finalizada")

    # Validar monto
    if puja.monto <= subasta.precio_actual:
        raise HTTPException(
            status_code=400, 
            detail=f"La puja debe ser mayor a ${subasta.precio_actual:.2f}"
        )

    # Validar usuario
    usuario = db.query(Usuario).filter(Usuario.id == puja.usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Crear puja
    nueva_puja = Puja(
        monto=puja.monto,
        usuario_id=puja.usuario_id,
        subasta_id=puja.subasta_id
    )

    subasta.precio_actual = puja.monto
    db.add(nueva_puja)
    db.commit()
    db.refresh(nueva_puja)

    # Notificar vía WebSocket
    await manager.broadcast(
        puja.subasta_id,
        json.dumps({
            "tipo": "nueva_puja",
            "subasta_id": puja.subasta_id,
            "nuevo_precio": puja.monto,
            "usuario_id": puja.usuario_id,
            "usuario_nombre": usuario.nombre,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    )

    logger.info(f"Nueva puja: ${puja.monto} por {usuario.nombre} en subasta {puja.subasta_id}")
    
    return {
        "mensaje": "Puja realizada exitosamente",
        "puja": nueva_puja,
        "usuario": usuario.nombre
    }


# ========================================
# 🔄 ENDPOINT WEBSOCKET
# ========================================

@app.websocket("/ws/{subasta_id}")
async def websocket_endpoint(websocket: WebSocket, subasta_id: int, db: Session = Depends(get_db)):
    """
    Conexión WebSocket para recibir actualizaciones en tiempo real.
    Cada subasta tiene su propio canal independiente.
    """
    # Validar que la subasta existe
    subasta = db.query(Subasta).filter(Subasta.id == subasta_id).first()
    if not subasta:
        await websocket.close(code=4004, reason="Subasta no encontrada")
        return
    
    await manager.connect(websocket, subasta_id)
    
    try:
        # Enviar estado inicial
        await websocket.send_text(json.dumps({
            "tipo": "conexion_exitosa",
            "subasta_id": subasta_id,
            "precio_actual": subasta.precio_actual,
            "mensaje": "Conectado a actualizaciones en tiempo real"
        }))
        
        # Mantener conexión viva
        while True:
            data = await websocket.receive_text()
            # Aquí podrías manejar mensajes del cliente si es necesario
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, subasta_id)
        logger.info(f"WebSocket desconectado de subasta {subasta_id}")
    except Exception as e:
        logger.error(f"Error en WebSocket: {e}")
        manager.disconnect(websocket, subasta_id)