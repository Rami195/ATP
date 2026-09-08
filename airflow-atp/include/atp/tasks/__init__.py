"""Tasks reutilizables del DAG ATP."""

from .discover_seasons import discover_seasons
from .land_bronze import land_bronze
from .land_bronze_aux import land_bronze_aux
from .consolidate import consolidate
from .validate import validate
from .save import save

__all__ = [
    "discover_seasons",
    "land_bronze",
    "land_bronze_aux",
    "consolidate",
    "validate",
    "save",
]
