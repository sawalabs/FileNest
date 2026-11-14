from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, utc_now_iso


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value_json: Mapped[str] = mapped_column(String, nullable=False, default="{}")
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso, onupdate=utc_now_iso)
