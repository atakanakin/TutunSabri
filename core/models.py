from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class UserRole(str, Enum):
    admin = "admin"
    premium = "premium"
    basic = "basic"
    user = "user"


class SearchTaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    seat_held = "seat_held"
    cancelled = "cancelled"
    completed = "completed"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(UserRole, native_enum=False),
        default=UserRole.basic,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    search_tasks: Mapped[List["SearchTask"]] = relationship(back_populates="user")


class SearchTask(Base):
    __tablename__ = "search_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    taskiq_message_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    from_station: Mapped[str] = mapped_column(String(255), index=True)
    to_station: Mapped[str] = mapped_column(String(255), index=True)
    travel_date: Mapped[date] = mapped_column(Date, index=True)
    travel_hour: Mapped[str] = mapped_column(String(5))
    train_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    train_car_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    allocation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    seat_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    hold_attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    hold_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_economy_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_business_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[SearchTaskStatus] = mapped_column(
        SqlEnum(SearchTaskStatus, native_enum=False),
        default=SearchTaskStatus.pending,
        index=True,
    )
    last_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="search_tasks")
