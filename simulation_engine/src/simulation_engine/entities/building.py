"""건물(Building) 엔티티와 유형 enum을 담는다."""

import uuid
from dataclasses import dataclass
from enum import StrEnum


class BuildingType(StrEnum):
    RESIDENTIAL = "RESIDENTIAL"
    COMMERCIAL = "COMMERCIAL"
    OFFICE = "OFFICE"
    PUBLIC = "PUBLIC"


@dataclass(slots=True, kw_only=True)
class Building:
    id: uuid.UUID
    type: str
    tile_x: int
    tile_y: int
    width: int
    height: int
    capacity: int = 0
    occupied_capacity: int = 0
    status: str
