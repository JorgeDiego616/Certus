from pydantic import BaseModel

class SubastaBase(BaseModel):
    titulo: str
    descripcion: str
    precio_inicial: float

class PujaBase(BaseModel):
    subasta_id: int
    usuario_id: int
    monto: float
