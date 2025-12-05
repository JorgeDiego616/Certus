from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Subasta(Base):
    __tablename__ = "subastas"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, nullable=False)
    descripcion = Column(String)
    precio_inicial = Column(Float, nullable=False)
    precio_actual = Column(Float, nullable=False, default=0)

    pujas = relationship("Puja", back_populates="subasta")


class Puja(Base):
    __tablename__ = "pujas"

    id = Column(Integer, primary_key=True, index=True)
    subasta_id = Column(Integer, ForeignKey("subastas.id"))
    usuario_id = Column(Integer)
    monto = Column(Float, nullable=False)

    subasta = relationship("Subasta", back_populates="pujas")
