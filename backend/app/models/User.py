from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id_user: Mapped[int] = mapped_column(primary_key=True)
    google_sub: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    picture_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    id_user: Mapped[int] = mapped_column(ForeignKey("users.id_user", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GoogleAccount(Base):
    __tablename__ = "google_accounts"

    id_user: Mapped[int] = mapped_column(ForeignKey("users.id_user", ondelete="CASCADE"), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320))
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id_usage: Mapped[int] = mapped_column(primary_key=True)
    id_user: Mapped[int] = mapped_column(ForeignKey("users.id_user", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class UserCv(Base):
    __tablename__ = "user_cvs"

    id_user: Mapped[int] = mapped_column(ForeignKey("users.id_user", ondelete="CASCADE"), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    candidate_name: Mapped[str | None] = mapped_column(String(200))
    skills_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    profile_json: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
