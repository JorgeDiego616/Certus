from sqlalchemy.orm import Session
from models import Subasta, Puja
from main import notificar_puja

def obtener_subastas(db: Session):
    return db.query(Subasta).all()


def obtener_subasta(db: Session, subasta_id: int):
    return db.query(Subasta).filter(Subasta.id == subasta_id).first()


def crear_subasta(db: Session, data: dict):
    nueva = Subasta(
        titulo=data["titulo"],
        descripcion=data["descripcion"],
        precio_inicial=data["precio_inicial"],
        precio_actual=data["precio_inicial"]
    )

    db.add(nueva)
    db.commit()
    db.refresh(nueva)

    return nueva


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

    # Notificar a WebSocket
    notificar_puja(subasta.id, subasta.precio_actual)

    return nueva
