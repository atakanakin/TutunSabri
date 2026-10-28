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

    # --- Browser impersonation ------------------------------------------------
    # curl_cffi browser profile. Use a concrete target (e.g. "chrome131",
    # "chrome133a", "chrome136") for reproducibility, or "chrome" to always track
    # the newest profile the installed curl_cffi ships. The TLS/JA3 fingerprint,
    # User-Agent and client-hint headers all come from this single setting, so
    # they can never drift out of sync.
    impersonate: str = Field("chrome131", alias="TCDD_IMPERSONATE")
    request_timeout_seconds: int = Field(30, alias="TCDD_REQUEST_TIMEOUT_SECONDS")
    web_origin: str = Field(
        "https://ebilet.tcddtasimacilik.gov.tr", alias="TCDD_WEB_ORIGIN"
    )
    web_referer: str = Field(
        "https://ebilet.tcddtasimacilik.gov.tr/", alias="TCDD_WEB_REFERER"
    )

    # --- Polling & cooldowns --------------------------------------------------
    poll_interval_seconds: int = Field(30, alias="POLL_INTERVAL_SECONDS")
    # Each poll is spread by ±ratio so the traffic never lands on a fixed period.
    poll_jitter_ratio: float = Field(0.25, alias="POLL_JITTER_RATIO")
    max_poll_errors: int = Field(3, alias="MAX_POLL_ERRORS")
    # Exponential backoff applied after consecutive hard errors (seconds).
    error_backoff_base_seconds: float = Field(15.0, alias="ERROR_BACKOFF_BASE_SECONDS")
    error_backoff_max_seconds: float = Field(300.0, alias="ERROR_BACKOFF_MAX_SECONDS")
    # Cooldown when the server throttles us (HTTP 429/503) and sends no
    # Retry-After header; a provided Retry-After always takes precedence.
    rate_limit_cooldown_seconds: float = Field(
        120.0, alias="RATE_LIMIT_COOLDOWN_SECONDS"
    )
    # Pause between seat-hold retry attempts (seconds).
    hold_retry_delay_seconds: float = Field(2.0, alias="HOLD_RETRY_DELAY_SECONDS")
    hold_duration_minutes: int = Field(10, alias="YHT_HOLD_DURATION_MINUTES")
    max_hold_attempts: int = Field(3, alias="YHT_MAX_HOLD_ATTEMPTS")
    basic_user_max_parallel_tasks: int = Field(3, alias="YHT_BASIC_MAX_PARALLEL_TASKS")
    premium_user_max_parallel_tasks: int = Field(5, alias="YHT_PREMIUM_MAX_PARALLEL_TASKS")
    default_timezone: str = Field("Europe/Istanbul", alias="DEFAULT_TIMEZONE")
    station_cache_path: Path = Field(Path("data/stations.json"), alias="STATION_CACHE_PATH")
    station_cache_ttl_hours: Optional[int] = Field(24, alias="STATION_CACHE_TTL_HOURS")


yht_settings = YHTSettings()
