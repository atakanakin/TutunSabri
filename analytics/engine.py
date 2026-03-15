from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Union

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import SearchTask, SearchTaskStatus


async def get_trending_routes(
    session: AsyncSession,
    *,
    limit: int = 10,
    days: Optional[int] = 7,
    successful_only: bool = False,
) -> List[Dict[str, Union[int, str]]]:
    statement = (
        select(
            SearchTask.from_station,
            SearchTask.to_station,
            func.count(SearchTask.id).label("search_count"),
        )
        .group_by(SearchTask.from_station, SearchTask.to_station)
        .order_by(func.count(SearchTask.id).desc())
        .limit(limit)
    )
    if days is not None:
        statement = statement.where(
            SearchTask.created_at >= datetime.now(timezone.utc) - timedelta(days=days),
        )
    if successful_only:
        statement = statement.where(SearchTask.status == SearchTaskStatus.seat_held)
    result = await session.execute(statement)
    return [
        {
            "from_station": from_station,
            "to_station": to_station,
            "search_count": search_count,
        }
        for from_station, to_station, search_count in result.all()
    ]


async def get_user_search_frequency(
    session: AsyncSession,
    *,
    user_id: int,
    days: Optional[int] = 30,
) -> Dict[str, int]:
    statement = select(
        func.count(SearchTask.id).label("total_searches"),
        func.count(func.distinct(SearchTask.travel_date)).label("distinct_travel_dates"),
    ).where(SearchTask.user_id == user_id)
    if days is not None:
        statement = statement.where(
            SearchTask.created_at >= datetime.now(timezone.utc) - timedelta(days=days),
        )
    result = await session.execute(statement)
    total_searches, distinct_travel_dates = result.one()
    return {
        "user_id": user_id,
        "total_searches": total_searches or 0,
        "distinct_travel_dates": distinct_travel_dates or 0,
    }
