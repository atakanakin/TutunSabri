from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import httpx

from modules.yht.config import yht_settings
from modules.yht.utils import normalize_text


class YHTError(Exception):
    pass


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

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "tr",
            "Authorization": yht_settings.authorization,
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Origin": "https://ebilet.tcddtasimacilik.gov.tr",
            "Referer": "https://ebilet.tcddtasimacilik.gov.tr/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
            ),
            "unit-id": yht_settings.unit_id,
        }

    async def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(headers=self.headers, timeout=30.0)

    async def refresh_station_cache(self) -> dict[str, int]:
        async with await self._client() as client:
            response = await client.get(yht_settings.station_base_url)
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
                    "arrivalStationId": arrival_station_id,
                    "departureDate": f"{travel_date.strftime('%d-%m-%Y')} 00:00:00",
                }
            ],
            "passengerTypeCounts": [{"id": 0, "count": 1}],
            "searchReservation": False,
        }
        url = f"{yht_settings.api_base_url}/train/train-availability?environment=dev&userId=1"
        async with await self._client() as client:
            response = await client.post(url, json=payload)
            self._raise_for_tcdd(response)
        data = response.json()
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
        seat_map_url = (
            f"{yht_settings.api_base_url}/seat-maps/load-by-train-id?environment=dev&userId=1"
        )
        async with await self._client() as client:
            response = await client.post(seat_map_url, json=payload)
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
        reserve_url = (
            f"{yht_settings.api_base_url}/inventory/select-seat?environment=dev&userId=1"
        )
        async with await self._client() as client:
            response = await client.post(reserve_url, json=reserve_payload)
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
        url = f"{yht_settings.api_base_url}/inventory/release-seat?environment=dev&userId=1"
        async with await self._client() as client:
            response = await client.post(url, json=payload)
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

    def _raise_for_tcdd(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise YHTError(
                f"TCDD isteği başarısız oldu. HTTP durum kodu: {response.status_code}"
            ) from exc
