from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import SearchTask, SearchTaskStatus, User, UserRole
from core.models import AccessRequest, AccessRequestStatus
from modules.yht.config import yht_settings


async def upsert_user(
    session: AsyncSession,
    *,
    telegram_user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
    force_role: Optional[UserRole] = None,
    force_active: bool = False,
) -> User:
    result = await session.execute(
        select(User).where(User.telegram_user_id == telegram_user_id),
    )
    user = result.scalar_one_or_none()
    target_role = force_role or UserRole.basic
    if user is None:
        user = User(
            telegram_user_id=telegram_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            role=target_role,
            is_active=True,
        )
        session.add(user)
    else:
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        if force_role is not None:
            user.role = force_role
        elif user.role == UserRole.user:
            user.role = UserRole.basic
        if force_active:
            user.is_active = True
    await session.commit()
    await session.refresh(user)
    return user


async def sync_user_profile(
    session: AsyncSession,
    *,
    user: User,
    username: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
) -> User:
    user.username = username
    user.first_name = first_name
    user.last_name = last_name
    if user.role == UserRole.user:
        user.role = UserRole.basic
    await session.commit()
    await session.refresh(user)
    return user


async def create_search_task(
    session: AsyncSession,
    *,
    user_id: int,
    from_station: str,
    to_station: str,
    travel_date: date,
    travel_hour: str,
) -> SearchTask:
    task = SearchTask(
        task_id=str(uuid.uuid4()),
        user_id=user_id,
        from_station=from_station,
        to_station=to_station,
        travel_date=travel_date,
        travel_hour=travel_hour,
        status=SearchTaskStatus.pending,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def get_active_task_for_user(
    session: AsyncSession, user_id: int
) -> Optional[SearchTask]:
    result = await session.execute(
        select(SearchTask)
        .where(SearchTask.user_id == user_id)
        .where(
            SearchTask.status.in_(
                [
                    SearchTaskStatus.pending,
                    SearchTaskStatus.running,
                    SearchTaskStatus.seat_held,
                ]
            )
        )
        .order_by(SearchTask.created_at.desc()),
    )
    return result.scalars().first()


async def get_held_task_for_user(
    session: AsyncSession, user_id: int
) -> Optional[SearchTask]:
    result = await session.execute(
        select(SearchTask)
        .where(SearchTask.user_id == user_id)
        .where(SearchTask.status == SearchTaskStatus.seat_held)
        .order_by(SearchTask.created_at.desc()),
    )
    return result.scalars().first()


async def get_open_tasks_for_user(
    session: AsyncSession, user_id: int
) -> list[SearchTask]:
    result = await session.execute(
        select(SearchTask)
        .where(SearchTask.user_id == user_id)
        .where(
            SearchTask.status.in_(
                [
                    SearchTaskStatus.pending,
                    SearchTaskStatus.running,
                    SearchTaskStatus.seat_held,
                ]
            )
        )
        .order_by(SearchTask.created_at.desc()),
    )
    return list(result.scalars().all())


async def get_held_tasks_for_user(
    session: AsyncSession, user_id: int
) -> list[SearchTask]:
    result = await session.execute(
        select(SearchTask)
        .where(SearchTask.user_id == user_id)
        .where(SearchTask.status == SearchTaskStatus.seat_held)
        .order_by(SearchTask.created_at.desc()),
    )
    return list(result.scalars().all())


async def get_task_by_public_id(
    session: AsyncSession, task_id: str
) -> Optional[SearchTask]:
    result = await session.execute(
        select(SearchTask).where(SearchTask.task_id == task_id)
    )
    return result.scalar_one_or_none()


async def get_user_task_by_public_id(
    session: AsyncSession, *, user_id: int, task_id: str
) -> Optional[SearchTask]:
    result = await session.execute(
        select(SearchTask)
        .where(SearchTask.user_id == user_id)
        .where(SearchTask.task_id == task_id)
    )
    return result.scalar_one_or_none()


async def get_open_task_by_signature(
    session: AsyncSession,
    *,
    user_id: int,
    from_station: str,
    to_station: str,
    travel_date: date,
    travel_hour: str,
) -> Optional[SearchTask]:
    result = await session.execute(
        select(SearchTask)
        .where(SearchTask.user_id == user_id)
        .where(SearchTask.from_station == from_station)
        .where(SearchTask.to_station == to_station)
        .where(SearchTask.travel_date == travel_date)
        .where(SearchTask.travel_hour == travel_hour)
        .where(
            SearchTask.status.in_(
                [
                    SearchTaskStatus.pending,
                    SearchTaskStatus.running,
                    SearchTaskStatus.seat_held,
                ]
            )
        )
        .order_by(SearchTask.created_at.desc()),
    )
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_telegram_id(
    session: AsyncSession, telegram_user_id: int
) -> Optional[User]:
    result = await session.execute(
        select(User).where(User.telegram_user_id == telegram_user_id)
    )
    return result.scalar_one_or_none()


async def get_all_users(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User).order_by(User.created_at.asc(), User.id.asc())
    )
    return list(result.scalars().all())


async def get_all_active_users(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User)
        .where(User.is_active.is_(True))
        .order_by(User.created_at.asc(), User.id.asc())
    )
    return list(result.scalars().all())


async def get_first_admin_username(session: AsyncSession) -> Optional[str]:
    result = await session.execute(
        select(User.username)
        .where(User.role == UserRole.admin)
        .where(User.is_active.is_(True))
        .where(User.username.is_not(None))
        .order_by(User.id.asc()),
    )
    return result.scalars().first()


async def get_admin_users(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User)
        .where(User.role == UserRole.admin)
        .where(User.is_active.is_(True))
        .order_by(User.id.asc()),
    )
    return list(result.scalars().all())


async def get_all_open_tasks(session: AsyncSession) -> list[SearchTask]:
    result = await session.execute(
        select(SearchTask)
        .where(
            SearchTask.status.in_(
                [
                    SearchTaskStatus.pending,
                    SearchTaskStatus.running,
                    SearchTaskStatus.seat_held,
                ]
            )
        )
        .order_by(SearchTask.created_at.desc(), SearchTask.id.desc())
    )
    return list(result.scalars().all())


async def get_stale_open_tasks(
    session: AsyncSession,
    *,
    stale_before: datetime,
) -> list[SearchTask]:
    result = await session.execute(
        select(SearchTask)
        .where(
            SearchTask.status.in_(
                [
                    SearchTaskStatus.pending,
                    SearchTaskStatus.running,
                    SearchTaskStatus.seat_held,
                ]
            )
        )
        .where(
            or_(
                SearchTask.last_checked_at.is_(None),
                SearchTask.last_checked_at < stale_before,
            )
        )
        .order_by(SearchTask.created_at.desc(), SearchTask.id.desc())
    )
    return list(result.scalars().all())


async def create_or_refresh_access_request(
    session: AsyncSession,
    *,
    telegram_user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
) -> AccessRequest:
    user = await get_user_by_telegram_id(session, telegram_user_id)
    result = await session.execute(
        select(AccessRequest).where(AccessRequest.telegram_user_id == telegram_user_id)
    )
    access_request = result.scalar_one_or_none()
    if access_request is None:
        access_request = AccessRequest(
            telegram_user_id=telegram_user_id,
            user_id=user.id if user else None,
            username=username,
            first_name=first_name,
            last_name=last_name,
            status=AccessRequestStatus.pending,
            is_notified=False,
        )
        session.add(access_request)
    else:
        access_request.user_id = user.id if user else None
        access_request.username = username
        access_request.first_name = first_name
        access_request.last_name = last_name
        access_request.status = AccessRequestStatus.pending
        access_request.is_notified = False
        access_request.resolved_at = None
    await session.commit()
    await session.refresh(access_request)
    return access_request


async def mark_access_request_notified(
    session: AsyncSession,
    *,
    telegram_user_id: int,
) -> Optional[AccessRequest]:
    result = await session.execute(
        select(AccessRequest).where(AccessRequest.telegram_user_id == telegram_user_id)
    )
    access_request = result.scalar_one_or_none()
    if access_request is None:
        return None
    access_request.is_notified = True
    await session.commit()
    await session.refresh(access_request)
    return access_request


async def get_pending_access_requests(session: AsyncSession) -> list[AccessRequest]:
    result = await session.execute(
        select(AccessRequest)
        .where(AccessRequest.status == AccessRequestStatus.pending)
        .order_by(AccessRequest.requested_at.asc()),
    )
    return list(result.scalars().all())


async def approve_access_request(
    session: AsyncSession,
    *,
    telegram_user_id: int,
) -> Optional[User]:
    result = await session.execute(
        select(AccessRequest).where(AccessRequest.telegram_user_id == telegram_user_id)
    )
    access_request = result.scalar_one_or_none()
    user = await get_user_by_telegram_id(session, telegram_user_id)
    if user is None:
        user = User(
            telegram_user_id=telegram_user_id,
            username=access_request.username if access_request else None,
            first_name=access_request.first_name if access_request else None,
            last_name=access_request.last_name if access_request else None,
            role=UserRole.basic,
            is_active=True,
        )
        session.add(user)
        await session.flush()
    else:
        user.username = access_request.username if access_request else user.username
        user.first_name = access_request.first_name if access_request else user.first_name
        user.last_name = access_request.last_name if access_request else user.last_name
        if user.role == UserRole.user:
            user.role = UserRole.basic
        user.is_active = True
    if access_request is not None:
        access_request.user_id = user.id
        access_request.status = AccessRequestStatus.approved
        access_request.is_notified = True
        access_request.resolved_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(user)
    return user


async def revoke_user_access(
    session: AsyncSession,
    *,
    telegram_user_id: int,
) -> Optional[User]:
    user = await get_user_by_telegram_id(session, telegram_user_id)
    if user is None:
        return None
    user.is_active = False
    result = await session.execute(
        select(AccessRequest).where(AccessRequest.telegram_user_id == telegram_user_id)
    )
    access_request = result.scalar_one_or_none()
    if access_request is not None:
        access_request.status = AccessRequestStatus.rejected
        access_request.resolved_at = datetime.now(timezone.utc)
        access_request.is_notified = True
    await session.commit()
    await session.refresh(user)
    return user


async def update_user_role(
    session: AsyncSession,
    *,
    telegram_user_id: int,
    role: UserRole,
) -> Optional[User]:
    user = await get_user_by_telegram_id(session, telegram_user_id)
    if user is None:
        return None
    user.role = role
    await session.commit()
    await session.refresh(user)
    return user


async def reject_access_request(
    session: AsyncSession,
    *,
    telegram_user_id: int,
) -> Optional[AccessRequest]:
    result = await session.execute(
        select(AccessRequest).where(AccessRequest.telegram_user_id == telegram_user_id)
    )
    access_request = result.scalar_one_or_none()
    if access_request is None:
        return None
    access_request.status = AccessRequestStatus.rejected
    access_request.resolved_at = datetime.now(timezone.utc)
    access_request.is_notified = True
    await session.commit()
    await session.refresh(access_request)
    return access_request


async def set_task_message_id(
    session: AsyncSession,
    *,
    task_id: str,
    taskiq_message_id: str,
) -> None:
    task = await get_task_by_public_id(session, task_id)
    if task is None:
        return
    task.taskiq_message_id = taskiq_message_id
    await session.commit()


async def update_task_status(
    session: AsyncSession,
    *,
    task_id: str,
    status: SearchTaskStatus,
    last_result: Optional[str] = None,
) -> Optional[SearchTask]:
    task = await get_task_by_public_id(session, task_id)
    if task is None:
        return None
    task.status = status
    task.last_checked_at = datetime.now(timezone.utc)
    if last_result is not None:
        task.last_result = last_result
    if status == SearchTaskStatus.cancelled:
        task.cancelled_at = datetime.now(timezone.utc)
    if status in {SearchTaskStatus.completed, SearchTaskStatus.failed}:
        task.completed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(task)
    return task


async def set_task_hold_details(
    session: AsyncSession,
    *,
    task_id: str,
    train_id: int,
    train_car_id: int,
    allocation_id: str,
    seat_number: str,
    last_result: str,
) -> Optional[SearchTask]:
    task = await get_task_by_public_id(session, task_id)
    if task is None:
        return None
    task.train_id = train_id
    task.train_car_id = train_car_id
    task.allocation_id = allocation_id
    task.seat_number = seat_number
    task.hold_attempt_count = (task.hold_attempt_count or 0) + 1
    task.hold_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=yht_settings.hold_duration_minutes
    )
    task.status = SearchTaskStatus.seat_held
    task.last_result = last_result
    task.last_checked_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(task)
    return task


async def update_task_counts(
    session: AsyncSession,
    *,
    task_id: str,
    economy_count: int,
    business_count: int,
    last_result: Optional[str] = None,
) -> Optional[SearchTask]:
    task = await get_task_by_public_id(session, task_id)
    if task is None:
        return None
    task.last_economy_count = economy_count
    task.last_business_count = business_count
    task.last_checked_at = datetime.now(timezone.utc)
    if last_result is not None:
        task.last_result = last_result
    await session.commit()
    await session.refresh(task)
    return task


async def clear_task_hold_details(
    session: AsyncSession,
    *,
    task_id: str,
    status: SearchTaskStatus,
    last_result: str,
) -> Optional[SearchTask]:
    task = await get_task_by_public_id(session, task_id)
    if task is None:
        return None
    task.train_id = None
    task.train_car_id = None
    task.allocation_id = None
    task.seat_number = None
    task.hold_expires_at = None
    task.status = status
    task.last_result = last_result
    task.last_checked_at = datetime.now(timezone.utc)
    if status in (
        SearchTaskStatus.cancelled,
        SearchTaskStatus.completed,
        SearchTaskStatus.failed,
    ):
        task.completed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(task)
    return task


async def set_user_yht_active(
    session: AsyncSession,
    *,
    telegram_user_id: int,
    is_active: bool,
) -> Optional[User]:
    user = await get_user_by_telegram_id(session, telegram_user_id)
    if user is None:
        return None
    user.is_yht_active = is_active
    await session.commit()
    await session.refresh(user)
    return user


async def cancel_task(session: AsyncSession, task_id: str) -> Optional[SearchTask]:
    return await update_task_status(
        session,
        task_id=task_id,
        status=SearchTaskStatus.cancelled,
        last_result="task cancelled by user",
    )
