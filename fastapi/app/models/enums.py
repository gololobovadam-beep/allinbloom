from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    ADMIN = "ADMIN"
    CUSTOMER = "CUSTOMER"


class FlowerType(str, Enum):
    ROSE = "ROSE"
    TULIP = "TULIP"
    PEONY = "PEONY"
    ORCHID = "ORCHID"
    HYDRANGEAS = "HYDRANGEAS"
    SPRAY_ROSES = "SPRAY_ROSES"
    RANUNCULUSES = "RANUNCULUSES"
    MIXED = "MIXED"


class BouquetType(str, Enum):
    MONO = "MONO"
    MIXED = "MIXED"
    SEASON = "SEASON"


class CatalogType(str, Enum):
    """Top-level catalog a stored product belongs to."""

    FLOWERS = "FLOWERS"
    BALOONS = "BALOONS"
    GIFTS = "GIFTS"
    EVENT_SPACE = "EVENT_SPACE"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
