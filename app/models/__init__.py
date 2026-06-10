"""SQLAlchemy ORM models — import all so Base metadata is populated."""

from app.models.tenant import Tenant
from app.models.user import User
from app.models.order import Orden, Reparacion, SesionReparacion
from app.models.board import Placa, NotaPlaca, MedicionPlaca, BloquePlaca
from app.models.ic import Circuito
from app.models.measurement import Medicion
from app.models.solution import Solucion
from app.models.reference import Referencia
from app.models.config_model import Config
from app.models.score import Puntaje
from app.models.equipment import TipoEquipo
from app.models.boarddoctor import Diagrama, IcMarca, IcCompatibilidad

__all__ = [
    "Tenant",
    "User",
    "Orden",
    "Reparacion",
    "SesionReparacion",
    "Placa",
    "NotaPlaca",
    "MedicionPlaca",
    "BloquePlaca",
    "Circuito",
    "Medicion",
    "Solucion",
    "Referencia",
    "Config",
    "Puntaje",
    "TipoEquipo",
    "Diagrama",
    "IcMarca",
    "IcCompatibilidad",
]
