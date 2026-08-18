"""
SQLAlchemy declarative base — imported by models.
Keep this file free of model imports to prevent circular imports.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
