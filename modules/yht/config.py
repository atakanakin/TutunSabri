from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class YHTSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_base_url: str = Field(
        "https://gise-api-prod-ytp.tcddtasimacilik.gov.tr/tms",
        alias="TCDD_API_BASE_URL",
    )
    station_base_url: str = Field(
        "https://cdn-api-prod-ytp.tcddtasimacilik.gov.tr/datas/station-pairs-INTERNET.json?environment=dev&userId=1",
        alias="TCDD_STATION_BASE_URL",
    )
    authorization: str = Field(..., alias="TCDD_AUTHORIZATION")
    unit_id: str = Field("3895", alias="TCDD_UNIT_ID")
    poll_interval_seconds: int = Field(30, alias="POLL_INTERVAL_SECONDS")
    max_poll_errors: int = Field(3, alias="MAX_POLL_ERRORS")
    basic_user_max_parallel_tasks: int = Field(3, alias="YHT_BASIC_MAX_PARALLEL_TASKS")
    premium_user_max_parallel_tasks: int = Field(5, alias="YHT_PREMIUM_MAX_PARALLEL_TASKS")
    default_timezone: str = Field("Europe/Istanbul", alias="DEFAULT_TIMEZONE")
    station_cache_path: Path = Field(Path("data/stations.json"), alias="STATION_CACHE_PATH")
    station_cache_ttl_hours: Optional[int] = Field(24, alias="STATION_CACHE_TTL_HOURS")


yht_settings = YHTSettings()
