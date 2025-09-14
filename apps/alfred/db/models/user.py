from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from alfred.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[object] = mapped_column(server_default=func.now())

