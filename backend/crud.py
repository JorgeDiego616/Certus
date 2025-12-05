from sqlalchemy.orm import Session
from models import Subasta, Puja, Usuario
from websocket_manager import notificar_puja
import auth


# ==========================
#     SUBASTAS
# ==========================

def obtener_subastas(db: Session):
    """Obtiene solo las subastas activas (no finalizadas)"""
    from datetime import datetime
    subastas = db.query(Subasta).all()
    
    # Filtrar solo las que no han terminado
    subastas_activas = []
    for s in subastas:
        if s.fecha_fin > datetime.now():
            subastas_activas.append(s)
    
    return subastas_activas


def obtener_subasta(db: Session, subasta_id: int):
    return db.query(Subasta).filter(Subasta.id == subasta_id).first()


def crear_subasta(db: Session, data: dict):
    nueva = Subasta(
        titulo=data["titulo"],
        descripcion=data["descripcion"],
        precio_inicial=data["precio_inicial"],
        precio_actual=data["precio_inicial"],
        duracion_horas=data.get("duracion_horas", 24)
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva


# ==========================
#         PUJAS
# ==========================

def crear_puja(db: Session, data: dict):
    subasta = obtener_subasta(db, data["subasta_id"])
    if not subasta:
        return {"error": "Subasta no existe"}

    monto = data["monto"]
    if monto <= subasta.precio_actual:
        return {"error": "Puja muy baja"}

    nueva = Puja(
        subasta_id=data["subasta_id"],
        usuario_id=data["usuario_id"],
        monto=monto
    )

    subasta.precio_actual = monto

    db.add(nueva)
    db.add(subasta)
    db.commit()
    db.refresh(nueva)

    # Notificar WebSocket
    import asyncio
    asyncio.create_task(notificar_puja(subasta.id, subasta.precio_actual))

    return nueva


def obtener_pujas_usuario(db: Session, usuario_id: int):
    """Obtiene todas las pujas de un usuario con info de subastas"""
    from datetime import datetime
    
    # Usar join para reducir consultas a la BD
    pujas = (db.query(Puja)
            .join(Subasta)
            .filter(Puja.usuario_id == usuario_id)
            .order_by(Puja.fecha.desc())
            .limit(50)  # Limitar a las últimas 50 pujas
            .all())
    
    resultado = []
    
    for puja in pujas:
        # Verificar que la subasta no haya terminado
        if puja.subasta.fecha_fin > datetime.now():
            resultado.append({
                "puja_id": puja.id,
                "monto": puja.monto,
                "fecha": puja.fecha,
                "subasta": {
                    "id": puja.subasta.id,
                    "titulo": puja.subasta.titulo,
                    "descripcion": puja.subasta.descripcion,
                    "precio_actual": puja.subasta.precio_actual,
                    "fecha_inicio": puja.subasta.fecha_inicio,
                    "duracion_horas": puja.subasta.duracion_horas
                }
            })
    
    return resultado


# ==========================
#        USUARIOS
# ==========================

def obtener_usuario(db: Session, usuario_id: int):
    """Obtiene un usuario por su ID"""
    return db.query(Usuario).filter(Usuario.id == usuario_id).first()


def obtener_usuario_por_correo(db: Session, correo: str):
    """Obtiene un usuario por su correo"""
    return db.query(Usuario).filter(Usuario.correo == correo).first()


def crear_usuario(db: Session, data: dict):
    """Registra un nuevo usuario"""
    # Verificar si el correo ya existe
    usuario_existente = obtener_usuario_por_correo(db, data["correo"])
    if usuario_existente:
        return {"error": "El correo ya está registrado"}
    
    # Encriptar contraseña
    password_hash = auth.hash_password(data["password"])
    
    # Crear usuario
    nuevo = Usuario(
        nombre=data["nombre"],
        correo=data["correo"],
        password_hash=password_hash
    )
    
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    
    return nuevo


def autenticar_usuario(db: Session, correo: str, password: str):
    """Verifica credenciales y devuelve el usuario si son correctas"""
    usuario = obtener_usuario_por_correo(db, correo)
    
    if not usuario:
        return None
    
    if not auth.verify_password(password, usuario.password_hash):
        return None
    
    return usuario


def actualizar_usuario(db: Session, data: dict):
    """Actualiza la información de un usuario"""
    usuario = obtener_usuario(db, data["id"])

    if not usuario:
        return {"error": "Usuario no encontrado"}

    usuario.nombre = data["nombre"]
    
    # Solo actualizar correo si cambió y no está en uso
    if data["correo"] != usuario.correo:
        correo_existente = obtener_usuario_por_correo(db, data["correo"])
        if correo_existente:
            return {"error": "El correo ya está en uso"}
        usuario.correo = data["correo"]

    db.commit()
    db.refresh(usuario)
    return {"status": "ok", "usuario": usuario}