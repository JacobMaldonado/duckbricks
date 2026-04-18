"""Tests for job execution page helper functions."""

from datetime import datetime, timezone

from app.ui.pages.job_execution import _format_datetime, _human_duration


class TestHumanDuration:
    def test_none_returns_dash(self):
        assert _human_duration(None) == "—"

    def test_under_1000ms_shows_ms(self):
        assert _human_duration(432) == "432 ms"

    def test_exactly_1000ms_shows_seconds(self):
        assert _human_duration(1000) == "1.0 s"

    def test_over_1000ms_shows_seconds(self):
        assert _human_duration(1500) == "1.5 s"

    def test_zero_ms(self):
        assert _human_duration(0) == "0 ms"


class TestFormatDatetime:
    def test_none_returns_dash(self):
        assert _format_datetime(None) == "—"

    def test_aware_datetime_formats_as_utc(self):
        dt = datetime(2026, 4, 18, 17, 30, 0, tzinfo=timezone.utc)
        assert _format_datetime(dt) == "2026-04-18 17:30:00 UTC"

    def test_naive_datetime_treated_as_utc(self):
        dt = datetime(2026, 4, 18, 12, 0, 0)
        result = _format_datetime(dt)
        assert "2026-04-18" in result
        assert "UTC" in result
