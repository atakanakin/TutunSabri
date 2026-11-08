import asyncio
import os
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest import mock

os.environ.setdefault("TCDD_AUTHORIZATION", "test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")

from modules.yht import logic  # noqa: E402
from modules.yht.config import yht_settings  # noqa: E402
from tasks import worker  # noqa: E402


class RetryAfterTests(unittest.TestCase):
    def _resp(self, headers):
        return logic._BrowserResponse(429, {}, headers)

    def test_seconds_any_header_case(self):
        resp = self._resp({"Retry-After": "42"})
        self.assertEqual(logic.TCDDClient._parse_retry_after(resp), 42.0)

    def test_http_date(self):
        when = datetime.now(timezone.utc) + timedelta(seconds=90)
        resp = self._resp({"retry-after": format_datetime(when, usegmt=True)})
        value = logic.TCDDClient._parse_retry_after(resp)
        self.assertIsNotNone(value)
        self.assertTrue(60 <= value <= 90)

    def test_missing_or_garbage(self):
        self.assertIsNone(logic.TCDDClient._parse_retry_after(self._resp({})))
        self.assertIsNone(
            logic.TCDDClient._parse_retry_after(self._resp({"retry-after": "soon"}))
        )

    def test_rate_limit_status_raises_with_retry_after(self):
        client = logic.TCDDClient.__new__(logic.TCDDClient)
        with self.assertRaises(logic.YHTRateLimitError) as ctx:
            client._raise_for_tcdd(
                logic._BrowserResponse(429, {}, {"Retry-After": "7"})
            )
        self.assertEqual(ctx.exception.retry_after, 7.0)

    def test_other_error_is_plain_yht_error(self):
        client = logic.TCDDClient.__new__(logic.TCDDClient)
        with self.assertRaises(logic.YHTError) as ctx:
            client._raise_for_tcdd(logic._BrowserResponse(500, {}))
        self.assertNotIsInstance(ctx.exception, logic.YHTRateLimitError)


class BackoffTests(unittest.TestCase):
    def test_error_backoff_grows_and_is_capped(self):
        with mock.patch.object(worker, "_jittered", side_effect=lambda v, *_: v):
            base = yht_settings.error_backoff_base_seconds
            cap = yht_settings.error_backoff_max_seconds
            self.assertEqual(worker._error_backoff(1), base)
            self.assertEqual(worker._error_backoff(2), base * 2)
            self.assertEqual(worker._error_backoff(50), cap)

    def test_rate_limit_sleep_is_bounded(self):
        with mock.patch.object(worker, "_jittered", side_effect=lambda v, *_: v):
            floor = float(yht_settings.poll_interval_seconds)
            cap = yht_settings.error_backoff_max_seconds
            self.assertEqual(worker._rate_limit_sleep(1), floor)
            self.assertEqual(worker._rate_limit_sleep(10**6), cap)

    def test_retry_after_delay_is_capped(self):
        with mock.patch.object(worker, "_jittered", side_effect=lambda v, *_: v):
            cap = yht_settings.error_backoff_max_seconds
            self.assertEqual(worker._retry_after_delay(10**6, 2.0), cap)
            self.assertEqual(worker._retry_after_delay(None, 2.0), 2.0)


class _FakePage:
    def __init__(self, results):
        self._results = list(results)
        self.calls = 0

    def is_closed(self):
        return False

    async def evaluate(self, *_):
        self.calls += 1
        result = self._results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class TransportRetryTests(unittest.IsolatedAsyncioTestCase):
    async def _run(self, results, idempotent):
        transport = logic._BrowserTransport()
        page = _FakePage(results)
        transport._ensure_page = mock.AsyncMock(return_value=page)
        transport._cleanup = mock.AsyncMock()
        try:
            resp = await transport.post_tms("/x", {}, idempotent=idempotent)
        except logic.YHTError as exc:
            return page, exc
        return page, resp

    async def test_not_ready_is_retried_even_if_not_idempotent(self):
        page, resp = await self._run(
            [{"notReady": True}, {"status": 200, "data": {"ok": 1}}], False
        )
        self.assertEqual(page.calls, 2)
        self.assertEqual(resp.json(), {"ok": 1})

    async def test_ambiguous_failure_not_replayed_for_non_idempotent(self):
        page, err = await self._run(
            [RuntimeError("boom"), {"status": 200, "data": {}}], False
        )
        self.assertEqual(page.calls, 1)
        self.assertIsInstance(err, logic.YHTError)

    async def test_ambiguous_failure_replayed_for_idempotent(self):
        page, resp = await self._run(
            [{"networkError": "net"}, {"status": 200, "data": {}}], True
        )
        self.assertEqual(page.calls, 2)
        self.assertEqual(resp.status_code, 200)

    async def test_hung_evaluate_times_out(self):
        class Hang(_FakePage):
            async def evaluate(self, *_):
                await asyncio.sleep(10)

        transport = logic._BrowserTransport()
        transport._ensure_page = mock.AsyncMock(return_value=Hang([]))
        transport._cleanup = mock.AsyncMock()
        with mock.patch.object(yht_settings, "request_timeout_seconds", 0.05):
            with self.assertRaises(logic.YHTError):
                await transport.post_tms("/x", {})


if __name__ == "__main__":
    unittest.main()
