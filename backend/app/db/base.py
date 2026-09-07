"""SQLAlchemy declarative base shared by every PostgreSQL model."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
