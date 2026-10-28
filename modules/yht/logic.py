from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from curl_cffi.requests import AsyncSession
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from modules.yht.config import yht_settings
from modules.yht.utils import normalize_text


class _BrowserResponse:
    def __init__(self, status_code: int, data: Any, headers: Optional[Dict[str, str]] = None) -> None:
        self.status_code = status_code
        self._data = data
        self.headers = headers or {}

    def json(self) -> Any:
        return self._data


class _BrowserTransport:
    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._lock: Optional[asyncio.Lock] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_lock(self) -> asyncio.Lock:
        current_loop = asyncio.get_running_loop()
        if self._lock is None or self._loop is not current_loop:
            self._lock = asyncio.Lock()
            self._loop = current_loop
        return self._lock

    async def _ensure_page(self) -> Page:
        if self._page is not None and not self._page.is_closed():
            return self._page

        await self._cleanup()
        self._playwright = await async_playwright().start()
        launch_args = [
            "--disable-blink-features=AutomationControlled",
        ]
        for channel in ("chrome", "msedge"):
            try:
                self._browser = await self._playwright.chromium.launch(
                    channel=channel,
                    headless=False,
                    args=launch_args,
                )
                break
            except Exception:
                continue
        if self._browser is None:
            self._browser = await self._playwright.chromium.launch(
                headless=False,
                args=launch_args,
            )

        self._context = await self._browser.new_context()
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self._page = await self._context.new_page()
        await self._page.goto(
            yht_settings.web_referer,
            wait_until="domcontentloaded",
            timeout=yht_settings.request_timeout_seconds * 1000,
        )
        await self._page.wait_for_function(
            "() => window.turnstile && Array.from(document.querySelectorAll('*')).some(el => el.__vue__ && el.__vue__.$store)",
            timeout=yht_settings.request_timeout_seconds * 1000,
        )
        await asyncio.sleep(2)
        return self._page

    async def post_tms(self, path: str, payload: Dict[str, Any]) -> _BrowserResponse:
        async with self._get_lock():
            for attempt in range(2):
                try:
                    page = await self._ensure_page()
                    result = await page.evaluate(
                        """async ({ path, payload }) => {
                            const appEl = Array.from(document.querySelectorAll('*')).find(
                                el => el.__vue__ && el.__vue__.$store
                            );
                            if (!appEl || !appEl.__vue__) {
                                throw new Error('TCDD Vue instance not ready');
                            }
                            const vm = appEl.__vue__;
                            const http = vm.axios || vm.$http;
                            const baseUrl = vm.$store.getters.getTmsServiceUrl;
                            try {
                                const r = await http.post(baseUrl + path, payload);
                                return {
                                    status: r.status || 200,
                                    data: r.data,
                                    headers: r.headers || {},
                                };
                            } catch (err) {
                                if (err && err.response) {
                                    return {
                                        status: err.response.status || 500,
                                        data: err.response.data,
                                        headers: err.response.headers || {},
                                    };
                                }
                                throw err;
                            }
                        }""",
                        {"path": path, "payload": payload},
                    )
                    return _BrowserResponse(
                        status_code=int(result.get("status", 500)),
                        data=result.get("data"),
                        headers=result.get("headers") or {},
                    )
                except Exception:
                    await self._cleanup()
                    if attempt == 1:
                        raise
        raise YHTError("TCDD tarayıcı isteği başarısız oldu.")

    async def _cleanup(self) -> None:
        for obj, method in (
            (self._page, "close"),
            (self._context, "close"),
            (self._browser, "close"),
            (self._playwright, "stop"),
        ):
            if obj is not None:
                try:
                    await getattr(obj, method)()
                except Exception:
                    pass
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None


_browser_transport = _BrowserTransport()


class YHTError(Exception):
    pass


class YHTRateLimitError(YHTError):
    """TCDD throttled the request (HTTP 429/503).

    Carries the server-provided cooldown (``Retry-After``) when available so the
    caller can wait the requested amount instead of hammering the endpoint.
    """

    def __init__(self, message: str, *, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class TrainAvailability:
    train_id: int
    departure_time: datetime
    economy_available: int
    business_available: int

    @property
    def has_availability(self) -> bool:
        return self.economy_available > 0 or self.business_available > 0


class TCDDClient:
    def __init__(self) -> None:
        self._timezone = ZoneInfo(yht_settings.default_timezone)
        self._station_cache_path = Path(yht_settings.station_cache_path)
        self._station_cache_path.parent.mkdir(parents=True, exist_ok=True)
        # curl_cffi reproduces the TLS/JA3 + HTTP2 fingerprint AND the matching
        # identity headers (User-Agent, sec-ch-ua, sec-ch-ua-platform,
        # Accept-Encoding, header ordering) for the chosen browser profile. We let
        # it own all of those so they stay mutually consistent — hand-writing a
        # User-Agent that disagrees with the TLS fingerprint is exactly what gives
        # an automated client away.
        self._session = AsyncSession(
            impersonate=yht_settings.impersonate,
            timeout=yht_settings.request_timeout_seconds,
        )

    @property
    def _base_headers(self) -> dict[str, str]:
        # Only the headers a real ``fetch()``/XHR from the TCDD web app adds on top
        # of the browser's own defaults. Identity + transport headers
        # (User-Agent, sec-ch-ua*, Accept-Encoding) are intentionally omitted so
        # curl_cffi supplies ones that match the impersonated browser.
        return {
            "Authorization": yht_settings.authorization,
            "unit-id": yht_settings.unit_id,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "tr",
            "Origin": yht_settings.web_origin,
            "Referer": yht_settings.web_referer,
            # XHR fetch-metadata (a browser navigation would send different values,
            # so these must be set explicitly rather than left to the default).
            "Sec-Fetch-Site": "same-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        }

    @property
    def _json_headers(self) -> dict[str, str]:
        # POST bodies are JSON; a browser only sends Content-Type on requests that
        # actually carry a body, so GETs use ``_base_headers`` instead.
        return {**self._base_headers, "Content-Type": "application/json"}

    async def close(self) -> None:
        await self._session.close()

    async def refresh_station_cache(self) -> dict[str, int]:
        response = await self._session.get(yht_settings.station_base_url, headers=self._base_headers)
        self._raise_for_tcdd(response)
        payload = response.json()
        station_map = {}
        city_map = {}
        for item in payload:
            if not item.get("stationTrainTypes") or "YHT" not in item["stationTrainTypes"]:
                continue
            station_name = item["name"]
            station_map[station_name] = item["id"]
            district = item.get("district") or {}
            city = (district.get("city") or {}).get("name")
            if city:
                normalized_city = normalize_text(city)
                if normalized_city not in city_map:
                    city_map[normalized_city] = []
                city_map[normalized_city].append(station_name)
        self._station_cache_path.write_text(
            json.dumps(
                {
                    "stations": station_map,
                    "cities": {key: sorted(value) for key, value in city_map.items()},
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return station_map

    async def get_station_map(self) -> dict[str, int]:
        station_map, _ = await self._load_station_cache()
        return station_map

    async def ensure_station_cache(self) -> None:
        if not self._station_cache_path.exists():
            await self.refresh_station_cache()
            return
        ttl_hours = yht_settings.station_cache_ttl_hours
        if ttl_hours is None:
            return
        modified_at = datetime.fromtimestamp(self._station_cache_path.stat().st_mtime)
        if datetime.now() - modified_at >= timedelta(hours=ttl_hours):
            await self.refresh_station_cache()

    async def _load_station_cache(self) -> Tuple[dict[str, int], dict[str, List[str]]]:
        if not self._station_cache_path.exists():
            station_map = await self.refresh_station_cache()
            return station_map, {}
        raw_cache = json.loads(self._station_cache_path.read_text(encoding="utf-8"))
        if isinstance(raw_cache, dict) and "stations" in raw_cache:
            return raw_cache.get("stations", {}), raw_cache.get("cities", {})
        return raw_cache, {}

    async def search_station_names(self, query: str) -> list[str]:
        station_map, city_map = await self._load_station_cache()
        normalized_query = normalize_text(query)
        station_matches = [
            station_name
            for station_name in station_map
            if normalized_query in normalize_text(station_name)
        ]
        city_matches = []
        for city_name, station_names in city_map.items():
            if normalized_query in city_name:
                city_matches.extend(station_names)
        return sorted(set(station_matches + city_matches))

    async def get_matching_stations(self, query: str) -> List[str]:
        return await self.search_station_names(query)

    async def get_station_id(self, station_name: str) -> int:
        station_map = await self.get_station_map()
        try:
            return station_map[station_name]
        except KeyError as exc:
            matches = await self.search_station_names(station_name)
            if matches:
                raise YHTError(f"Station not exact. Possible matches: {', '.join(matches[:10])}") from exc
            raise YHTError(f"Unknown station: {station_name}") from exc

    async def list_train_hours(self, from_station: str, to_station: str, travel_date: date) -> list[str]:
        availabilities = await self.fetch_availability(
            from_station=from_station,
            to_station=to_station,
            travel_date=travel_date,
        )
        return [self._api_to_local_time(item.departure_time).strftime("%H:%M") for item in availabilities]

    async def fetch_availability(
        self,
        *,
        from_station: str,
        to_station: str,
        travel_date: date,
    ) -> list[TrainAvailability]:
        departure_station_id = await self.get_station_id(from_station)
        arrival_station_id = await self.get_station_id(to_station)
        payload = {
            "searchRoutes": [
                {
                    "departureStationId": departure_station_id,
                    "departureStationName": from_station,
                    "arrivalStationId": arrival_station_id,
                    "arrivalStationName": to_station,
                    "departureDate": f"{travel_date.strftime('%d-%m-%Y')} 00:00:00",
                }
            ],
            "passengerTypeCounts": [{"id": 0, "count": 1}],
            "searchReservation": False,
            "searchType": "DOMESTIC",
            "blTrainTypes": ["TURISTIK_TREN"],
        }
        response = await _browser_transport.post_tms("/train/train-availability", payload)
        data = response.json()
        if (
            response.status_code == 400
            and isinstance(data, dict)
            and data.get("code") in (604, 12511)
        ):
            return []
        self._raise_for_tcdd(response)
        if not isinstance(data, dict):
            return []
        availabilities: list[TrainAvailability] = []
        for item in data.get("trainLegs", [{}])[0].get("trainAvailabilities", []):
            trains = item.get("trains") or []
            if not trains or trains[0].get("type") != "YHT":
                continue
            train = trains[0]
            departure_time = self._extract_departure_time(train, departure_station_id)
            economy_available = next(
                (
                    availability["availabilityCount"]
                    for availability in train.get("cabinClassAvailabilities", [])
                    if availability["cabinClass"]["code"] == "Y1"
                ),
                0,
            )
            business_available = next(
                (
                    availability["availabilityCount"]
                    for availability in train.get("cabinClassAvailabilities", [])
                    if availability["cabinClass"]["code"] == "C"
                ),
                0,
            )
            availabilities.append(
                TrainAvailability(
                    train_id=train["id"],
                    departure_time=departure_time,
                    economy_available=economy_available,
                    business_available=business_available,
                ),
            )
        return availabilities

    async def hold_seat(
        self,
        *,
        train_id: int,
        from_station: str,
        to_station: str,
    ) -> Dict[str, object]:
        departure_station_id = await self.get_station_id(from_station)
        arrival_station_id = await self.get_station_id(to_station)
        payload = {
            "fromStationId": departure_station_id,
            "toStationId": arrival_station_id,
            "trainId": train_id,
            "legIndex": 0,
        }
        response = await _browser_transport.post_tms("/seat-maps/load-by-train-id", payload)
        self._raise_for_tcdd(response)
        wagon = self._select_wagon_with_empty_seat(response.json().get("seatMaps", []))
        if wagon is None:
            raise YHTError("Seat availability changed before hold operation completed.")

        reserve_payload = {
            "trainCarId": wagon["train_car_id"],
            "fromStationId": departure_station_id,
            "toStationId": arrival_station_id,
            "gender": "M",
            "seatNumber": wagon["seat_number"],
            "passengerTypeId": 0,
            "totalPassengerCount": 1,
            "fareFamilyId": 0,
        }
        response = await _browser_transport.post_tms("/inventory/select-seat", reserve_payload)
        self._raise_for_tcdd(response)
        reserve_data = response.json()
        return {
            "train_id": train_id,
            "train_car_id": wagon["train_car_id"],
            "wagon_number": wagon["wagon_number"],
            "seat_number": wagon["seat_number"],
            "allocation_id": reserve_data["allocationId"],
        }

    async def release_seat(
        self,
        *,
        train_car_id: int,
        allocation_id: str,
        seat_number: str,
    ) -> None:
        payload = {
            "trainCarId": train_car_id,
            "allocationId": allocation_id,
            "seatNumber": seat_number,
        }
        response = await _browser_transport.post_tms("/inventory/release-seat", payload)
        self._raise_for_tcdd(response)

    async def check_specific_departure(
        self,
        *,
        from_station: str,
        to_station: str,
        travel_date: date,
        travel_hour: str,
    ) -> Optional[TrainAvailability]:
        target_local = datetime.combine(
            travel_date,
            time.fromisoformat(travel_hour),
            tzinfo=self._timezone,
        )
        target_api = self._local_to_api_time(target_local)
        for availability in await self.fetch_availability(
            from_station=from_station,
            to_station=to_station,
            travel_date=travel_date,
        ):
            if availability.departure_time.replace(tzinfo=None) == target_api:
                return availability
        return None

    def _extract_departure_time(self, train: dict, departure_station_id: int) -> datetime:
        segment = next(
            (
                segment
                for segment in train.get("trainSegments", [])
                if segment.get("departureStationId") == departure_station_id
            ),
            None,
        )
        if segment is None:
            raise YHTError("Departure segment not found for requested station.")
        return datetime.strptime(segment["departureTime"], "%Y-%m-%dT%H:%M:%S")

    def _api_to_local_time(self, value: datetime) -> datetime:
        return value + timedelta(hours=3)

    def _local_to_api_time(self, value: datetime) -> datetime:
        return (value - timedelta(hours=3)).replace(tzinfo=None)

    def _select_wagon_with_empty_seat(
        self, wagons: List[dict]
    ) -> Optional[Dict[str, object]]:
        seat_pattern = re.compile(r"^\d{1,2}[ABCD]$")
        for wagon_index in range(len(wagons) - 1, -1, -1):
            wagon = wagons[wagon_index]
            if wagon.get("availableSeatCount", 0) == 0:
                continue
            all_seats = [
                item["seatNumber"]
                for item in wagon.get("seatMapTemplate", {}).get("seatMaps", [])
                if seat_pattern.match(item.get("seatNumber", ""))
            ]
            allocated = [
                item["seatNumber"]
                for item in wagon.get("allocationSeats", [])
                if item.get("seatNumber")
            ]
            empty = sorted(list(set(all_seats) - set(allocated)))
            if empty:
                return {
                    "train_car_id": wagon["trainCarId"],
                    "wagon_number": wagon_index + 1,
                    "seat_number": empty[0],
                }
        return None

    def _raise_for_tcdd(self, response) -> None:
        status = response.status_code
        if status < 400:
            return
        # Treat throttling / temporary unavailability separately so the caller can
        # back off politely instead of burning its error budget and quitting.
        if status in (429, 503):
            raise YHTRateLimitError(
                f"TCDD isteği sınırlandırıldı. HTTP durum kodu: {status}",
                retry_after=self._parse_retry_after(response),
            )
        raise YHTError(
            f"TCDD isteği başarısız oldu. HTTP durum kodu: {status}"
        )

    @staticmethod
    def _parse_retry_after(response) -> Optional[float]:
        """Read a ``Retry-After`` header, as either a seconds value or HTTP date."""
        try:
            raw = response.headers.get("Retry-After")
        except Exception:
            return None
        if not raw:
            return None
        raw = raw.strip()
        if raw.isdigit():
            return float(raw)
        try:
            retry_at = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
        if retry_at is None:
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        delta = (retry_at - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, delta)
