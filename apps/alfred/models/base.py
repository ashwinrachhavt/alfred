"""Declarative base classes, mixins, and helpers for ORM models."""

from __future__ import annotations

from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import Iterator

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    MetaData,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

_naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=_naming_convention)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    metadata = metadata


class TimestampMixin:
    """Adds created/updated timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        server_default=func.now(),
        nullable=False,
    )


def _camel_to_snake(name: str) -> str:
    result: list[str] = []
    for index, char in enumerate(name):
        if char.isupper() and index != 0 and not name[index - 1].isupper():
            result.append("_")
        result.append(char.lower())
    return "".join(result)


class Model(TimestampMixin, Base):
    """Opinionated base with `id`/timestamps and auto table naming."""

    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    @declared_attr.directive
    def __tablename__(cls) -> str:  # type: ignore[override]
        name = _camel_to_snake(cls.__name__)
        return name if name.endswith("s") else f"{name}s"


class _FieldFactory:
    """Helper to make model field declarations concise."""

    def __call__(self, *args, **kwargs):
        return mapped_column(*args, **kwargs)

    def string(self, length: int = 255, **kwargs):
        return mapped_column(String(length), **kwargs)

    def text(self, **kwargs):
        return mapped_column(Text, **kwargs)

    def integer(self, **kwargs):
        return mapped_column(Integer, **kwargs)

    def boolean(self, **kwargs):
        return mapped_column(Boolean, **kwargs)

    def float(self, **kwargs):
        return mapped_column(Float, **kwargs)

    def numeric(self, precision: int = 10, scale: int = 2, **kwargs):
        return mapped_column(Numeric(precision=precision, scale=scale), **kwargs)

    def datetime(self, timezone: bool = True, **kwargs):
        return mapped_column(DateTime(timezone=timezone), **kwargs)

    def enum(self, enum_cls, *, name: str | None = None, **kwargs):
        enum_name = name or f"{enum_cls.__name__.lower()}_enum"
        return mapped_column(Enum(enum_cls, name=enum_name), **kwargs)

    def foreign_key(
        self,
        target: str,
        *,
        type_=Integer,
        ondelete: str | None = None,
        **kwargs,
    ):
        fk = ForeignKey(target, ondelete=ondelete)
        return mapped_column(type_, fk, **kwargs)

    def json(self, **kwargs):
        return mapped_column(JSON, **kwargs)


fields = _FieldFactory()


def iter_model_modules() -> Iterator[str]:
    """Yield import paths for all model modules.

    Modules starting with an underscore or named ``base`` are skipped.
    """

    package_dir = Path(__file__).resolve().parent
    for path in package_dir.glob("*.py"):
        stem = path.stem
        if stem.startswith("_") or stem == "base":
            continue
        yield f"{__package__}.{stem}"


def load_all_models() -> None:
    """Import all model modules so they register with the metadata."""

    for dotted_path in iter_model_modules():
        import_module(dotted_path)
