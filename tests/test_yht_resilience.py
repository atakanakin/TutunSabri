import asyncio
import os
import types
import unittest
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from unittest import mock

os.environ.setdefault("TCDD_AUTHORIZATION", "test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")

from modules.yht import logic  # noqa: E402
from modules.yht.config import yht_settings  # noqa: E402
from core.models import SearchTaskStatus  # noqa: E402
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




class AmbiguityAndShutdownTests(unittest.IsolatedAsyncioTestCase):
    def _transport(self, page):
        transport = logic._BrowserTransport()
        transport._ensure_page = mock.AsyncMock(return_value=page)
        transport._cleanup = mock.AsyncMock()
        return transport

    async def test_non_idempotent_ambiguous_failure_is_flagged(self):
        for failure in (RuntimeError("boom"), {"networkError": "net"}):
            transport = self._transport(_FakePage([failure]))
            with self.assertRaises(logic.YHTAmbiguousRequestError):
                await transport.post_tms("/inventory/select-seat", {})

    async def test_timeout_is_ambiguous_for_non_idempotent(self):
        class Hang(_FakePage):
            async def evaluate(self, *_):
                await asyncio.sleep(10)

        transport = self._transport(Hang([]))
        with mock.patch.object(yht_settings, "request_timeout_seconds", 0.05):
            with self.assertRaises(logic.YHTAmbiguousRequestError):
                await transport.post_tms("/inventory/select-seat", {})

    async def test_not_ready_is_never_ambiguous(self):
        transport = self._transport(_FakePage([{"notReady": True}, {"notReady": True}]))
        with self.assertRaises(logic.YHTError) as ctx:
            await transport.post_tms("/x", {})
        self.assertNotIsInstance(ctx.exception, logic.YHTAmbiguousRequestError)

    async def test_idempotent_failure_is_plain_error(self):
        transport = self._transport(
            _FakePage([RuntimeError("a"), RuntimeError("b")])
        )
        with self.assertRaises(logic.YHTError) as ctx:
            await transport.post_tms("/x", {}, idempotent=True)
        self.assertNotIsInstance(ctx.exception, logic.YHTAmbiguousRequestError)

    async def test_hung_setup_is_bounded(self):
        transport = logic._BrowserTransport()

        async def hang():
            await asyncio.sleep(10)

        transport._ensure_page = hang
        transport._cleanup = mock.AsyncMock()
        with mock.patch.object(yht_settings, "request_timeout_seconds", 0.01), \
                mock.patch.object(logic, "_PAGE_SETTLE_SECONDS", 0.0):
            with self.assertRaises(logic.YHTError):
                await asyncio.wait_for(transport.post_tms("/x", {}), timeout=2)

    async def test_hung_cleanup_is_bounded(self):
        class Wedged:
            async def close(self):
                await asyncio.sleep(10)

            async def stop(self):
                await asyncio.sleep(10)

        transport = logic._BrowserTransport()
        transport._page = transport._context = transport._browser = Wedged()
        transport._playwright = Wedged()
        with mock.patch.object(logic, "_CLEANUP_STEP_TIMEOUT_SECONDS", 0.01):
            await asyncio.wait_for(transport._cleanup(), timeout=2)
        self.assertIsNone(transport._page)
        self.assertIsNone(transport._playwright)

    async def test_closed_transport_rejects_new_requests(self):
        transport = self._transport(_FakePage([{"status": 200, "data": {}}]))
        await transport.aclose()
        with self.assertRaises(logic.YHTTransportClosedError):
            await transport.post_tms("/x", {})
        transport._ensure_page.assert_not_called()


class _StopLoop(Exception):
    pass


class _FakeSession:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *exc):
        return False


class _Task:
    task_id = "t1"
    user_id = 1
    status = SearchTaskStatus.running
    from_station = "A"
    to_station = "B"
    travel_date = date(2030, 1, 1)
    travel_hour = "10:00"
    last_result = None
    hold_attempt_count = 0
    last_economy_count = None
    last_business_count = None
    last_checked_at = None


class _User:
    telegram_user_id = 99
    username = "u"


class _Availability:
    train_id = 5
    economy_available = 1
    business_available = 0


def _real_failures(fail_mock):
    """Task failures that were not caused by the test's own _StopLoop sentinel."""
    return [
        c for c in fail_mock.await_args_list if "_StopLoop" not in c.kwargs["error_text"]
    ]


class MonitorFlowTests(unittest.IsolatedAsyncioTestCase):
    """Drives monitor_yht_task with fakes. ``sleeper`` stops the infinite loop."""

    async def _run(self, *, availability_side_effect, hold_side_effect, stop_after):
        client = mock.MagicMock()
        client.check_specific_departure = mock.AsyncMock(
            side_effect=availability_side_effect
        )
        client.hold_seat = mock.AsyncMock(side_effect=hold_side_effect)
        client.close = mock.AsyncMock()
        sleeps = []
        self.clock = [0.0]

        async def sleeper(task_id, seconds):
            sleeps.append(seconds)
            self.clock[0] += seconds
            if len(sleeps) >= stop_after:
                raise _StopLoop()
            return False

        bot = mock.MagicMock()
        bot.send_message = mock.AsyncMock()
        bot.session.close = mock.AsyncMock()
        mocks = {
            "fail": mock.AsyncMock(),
            "notify": mock.AsyncMock(),
            "status": mock.AsyncMock(),
        }
        with mock.patch.object(worker, "TCDDClient", return_value=client), \
                mock.patch.object(worker, "Bot", return_value=bot), \
                mock.patch.object(worker, "SessionFactory", _FakeSession), \
                mock.patch.object(
                    worker, "get_task_by_public_id", mock.AsyncMock(return_value=_Task())
                ), \
                mock.patch.object(
                    worker, "get_user_by_id", mock.AsyncMock(return_value=_User())
                ), \
                mock.patch.object(worker, "update_task_status", mocks["status"]), \
                mock.patch.object(worker, "_notify_admins", mocks["notify"]), \
                mock.patch.object(worker, "_fail_task_with_notifications", mocks["fail"]), \
                mock.patch.object(
                    worker, "time", types.SimpleNamespace(monotonic=lambda: self.clock[0])
                ), \
                mock.patch.object(worker, "_sleep_unless_cancelled", sleeper):
            try:
                await worker.monitor_yht_task.original_func("t1")
                stopped = False
            except _StopLoop:
                stopped = True
        return client, sleeps, mocks, stopped

    async def test_ambiguous_hold_is_not_retried_and_waits_out_the_hold(self):
        client, sleeps, mocks, stopped = await self._run(
            availability_side_effect=lambda **_: _Availability(),
            hold_side_effect=logic.YHTAmbiguousRequestError("unknown"),
            stop_after=1,
        )
        self.assertTrue(stopped)
        self.assertEqual(client.hold_seat.await_count, 1)
        self.assertGreaterEqual(sleeps[0], yht_settings.hold_duration_minutes * 60 * 0.9)
        mocks["notify"].assert_awaited()
        self.assertEqual(_real_failures(mocks["fail"]), [])

    async def test_hold_rate_limit_is_not_a_hold_error_and_cools_down(self):
        client, sleeps, mocks, stopped = await self._run(
            availability_side_effect=lambda **_: _Availability(),
            hold_side_effect=logic.YHTRateLimitError("slow down"),
            stop_after=3,  # 2 waits between the 3 attempts, then the cooldown
        )
        self.assertTrue(stopped)
        self.assertEqual(client.hold_seat.await_count, yht_settings.max_poll_errors)
        self.assertEqual(_real_failures(mocks["fail"]), [])
        self.assertGreaterEqual(sleeps[-1], yht_settings.poll_interval_seconds * 0.85)

    async def test_transport_closed_ends_task_without_failing_it(self):
        client, sleeps, mocks, stopped = await self._run(
            availability_side_effect=logic.YHTTransportClosedError("closed"),
            hold_side_effect=None,
            stop_after=99,
        )
        self.assertFalse(stopped)
        mocks["fail"].assert_not_called()
        for call in mocks["status"].await_args_list:
            self.assertNotEqual(call.kwargs.get("status"), SearchTaskStatus.failed)

    async def test_continuous_rate_limit_cancels_after_give_up_window(self):
        def always_limited(**_):
            raise logic.YHTRateLimitError("x")

        client, sleeps, mocks, stopped = await self._run(
            availability_side_effect=always_limited,
            hold_side_effect=None,
            stop_after=10_000,
        )
        self.assertFalse(stopped)
        mocks["fail"].assert_awaited_once()
        limit = yht_settings.rate_limit_give_up_minutes * 60
        # Ends right at the deadline, not up to a whole cooldown late.
        self.assertGreaterEqual(self.clock[0], limit)
        self.assertLessEqual(self.clock[0], limit + 2)
        self.assertIn("dakikadır", mocks["fail"].await_args.kwargs["user_message"])

    async def test_success_or_other_error_restarts_the_window(self):
        limit = yht_settings.rate_limit_give_up_minutes * 60
        state = {"errored": False}

        def flaky(**_):
            now = self.clock[0]
            if now < limit * 0.7:
                raise logic.YHTRateLimitError("x")
            if not state["errored"]:
                state["errored"] = True
                raise logic.YHTError("other")
            if now < limit * 1.6:
                raise logic.YHTRateLimitError("x")
            return None

        client, sleeps, mocks, stopped = await self._run(
            availability_side_effect=flaky,
            hold_side_effect=None,
            stop_after=10_000,
        )
        # 0.7*limit throttled, a different error, then another 0.9*limit
        # throttled: neither stretch alone reaches the limit.
        self.assertEqual(_real_failures(mocks["fail"]), [])

    async def test_rate_limits_during_hold_count_toward_the_window(self):
        client, sleeps, mocks, stopped = await self._run(
            availability_side_effect=lambda **_: _Availability(),
            hold_side_effect=logic.YHTRateLimitError("slow down"),
            stop_after=10_000,
        )
        self.assertFalse(stopped)
        mocks["fail"].assert_awaited_once()
        limit = yht_settings.rate_limit_give_up_minutes * 60
        self.assertGreaterEqual(self.clock[0], limit)
        self.assertLessEqual(self.clock[0], limit + 5)


class SleepUnlessCancelledTests(unittest.IsolatedAsyncioTestCase):
    async def _sleep(self, statuses, seconds):
        tasks = [mock.MagicMock(status=st) if st else None for st in statuses]
        with mock.patch.object(worker, "SessionFactory", _FakeSession), \
                mock.patch.object(
                    worker, "get_task_by_public_id", mock.AsyncMock(side_effect=tasks)
                ) as getter, \
                mock.patch.object(worker.asyncio, "sleep", mock.AsyncMock()) as slept, \
                mock.patch.object(yht_settings, "poll_interval_seconds", 10):
            result = await worker._sleep_unless_cancelled("t1", seconds)
        return result, slept, getter

    async def test_short_wait_is_one_sleep_without_db(self):
        result, slept, getter = await self._sleep([], 5)
        self.assertFalse(result)
        self.assertEqual(slept.await_count, 1)
        getter.assert_not_called()

    async def test_cancel_interrupts_long_wait(self):
        result, slept, _ = await self._sleep(
            [SearchTaskStatus.running, SearchTaskStatus.cancelled], 100
        )
        self.assertTrue(result)
        self.assertEqual(slept.await_count, 2)

    async def test_missing_task_interrupts(self):
        result, _, _ = await self._sleep([None], 100)
        self.assertTrue(result)

    async def test_full_wait_when_not_cancelled(self):
        result, slept, _ = await self._sleep([SearchTaskStatus.running] * 2, 30)
        self.assertFalse(result)
        self.assertEqual(slept.await_count, 3)


if __name__ == "__main__":
    unittest.main()
