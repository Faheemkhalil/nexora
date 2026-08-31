"""Tests for Phase 10: Auto-update, Crash Reporting, and Analytics."""
import asyncio
import time
import pytest

from app.core.db import init_db


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    """Initialize the database for all tests."""
    loop = asyncio.new_event_loop()
    loop.run_until_complete(init_db())
    yield
    loop.close()


# ── Updater Tests ────────────────────────────────────────────────────


class TestUpdater:
    """Tests for the auto-update system."""

    def test_updater_init(self):
        from app.core.updater import UpdateManager
        um = UpdateManager()
        assert um is not None

    def test_get_current_version(self):
        from app.core.updater import UpdateManager
        um = UpdateManager()
        v = um.get_current_version()
        assert "version" in v
        assert "build" in v
        assert isinstance(v["version"], str)

    def test_auto_update_setting_default(self):
        from app.core.updater import UpdateManager
        um = UpdateManager()
        enabled = um.get_auto_update_setting()
        assert isinstance(enabled, bool)

    def test_set_auto_update(self):
        from app.core.updater import UpdateManager
        um = UpdateManager()
        um.set_auto_update(False)
        assert um.get_auto_update_setting() is False
        um.set_auto_update(True)
        assert um.get_auto_update_setting() is True

    def test_record_and_complete_update(self):
        from app.core.updater import UpdateManager
        um = UpdateManager()
        update_id = um.record_update_attempt("1.0.0")
        assert update_id.startswith("upd_")
        um.complete_update(update_id, True)
        history = um.get_update_history()
        assert len(history) >= 1

    def test_update_history(self):
        from app.core.updater import UpdateManager
        um = UpdateManager()
        history = um.get_update_history()
        assert isinstance(history, list)


# ── Crash Reporter Tests ─────────────────────────────────────────────


class TestCrashReporter:
    """Tests for the crash reporting system."""

    def test_crash_reporter_init(self):
        from app.core.crash_reporter import CrashReporter
        cr = CrashReporter()
        assert cr is not None

    def test_capture_exception(self):
        from app.core.crash_reporter import CrashReporter
        cr = CrashReporter()
        report_id = cr.capture_exception(
            ValueError("test error"),
            component="test",
            context={"test": True},
        )
        assert report_id.startswith("crash_")

    def test_get_reports(self):
        from app.core.crash_reporter import CrashReporter
        cr = CrashReporter()
        cr.capture_exception(RuntimeError("capture test"), component="test_reports")
        reports = cr.get_reports(component="test_reports")
        assert isinstance(reports, list)
        assert len(reports) >= 1
        assert reports[0]["error_type"] == "RuntimeError"

    def test_crash_stats(self):
        from app.core.crash_reporter import CrashReporter
        cr = CrashReporter()
        stats = cr.get_crash_stats()
        assert "total_crashes" in stats
        assert "recent_24h" in stats
        assert "by_component" in stats
        assert "by_error_type" in stats

    def test_delete_report(self):
        from app.core.crash_reporter import CrashReporter
        cr = CrashReporter()
        report_id = cr.capture_exception(Exception("delete me"))
        ok = cr.delete_report(report_id)
        assert ok is True

    def test_clear_all(self):
        from app.core.crash_reporter import CrashReporter
        cr = CrashReporter()
        cr.capture_exception(Exception("clear test"))
        count = cr.clear_all()
        assert isinstance(count, int)


# ── Analytics Tests ──────────────────────────────────────────────────


class TestAnalytics:
    """Tests for the analytics dashboard."""

    def test_analytics_init(self):
        from app.core.analytics import AnalyticsManager
        am = AnalyticsManager()
        assert am is not None

    def test_start_end_session(self):
        from app.core.analytics import AnalyticsManager
        am = AnalyticsManager()
        session_id = am.start_session()
        assert session_id.startswith("ses_")
        am.end_session()

    def test_track_event(self):
        from app.core.analytics import AnalyticsManager
        am = AnalyticsManager()
        am.track_event("test_event", "test_component", {"key": "value"})
        # Should not raise

    def test_usage_stats(self):
        from app.core.analytics import AnalyticsManager
        am = AnalyticsManager()
        am.track_event("usage_test", "test_usage")
        stats = am.get_usage_stats()
        assert "total_events" in stats
        assert "total_sessions" in stats
        assert "events_by_type" in stats

    def test_performance_metrics(self):
        from app.core.analytics import AnalyticsManager
        am = AnalyticsManager()
        perf = am.get_performance_metrics()
        assert "process" in perf
        assert "system" in perf
        assert "memory_mb" in perf["process"]
        assert "cpu_percent" in perf["system"]

    def test_feature_adoption(self):
        from app.core.analytics import AnalyticsManager
        am = AnalyticsManager()
        am.track_event("adopt_test", "adoption_test")
        adoption = am.get_feature_adoption()
        assert "features" in adoption
        assert isinstance(adoption["features"], list)

    def test_dashboard(self):
        from app.core.analytics import AnalyticsManager
        am = AnalyticsManager()
        dash = am.get_dashboard()
        assert "health_score" in dash
        assert "usage" in dash
        assert "performance" in dash
        assert "adoption" in dash
        assert isinstance(dash["health_score"], int)
        assert 0 <= dash["health_score"] <= 100

    def test_clear_old_events(self):
        from app.core.analytics import AnalyticsManager
        am = AnalyticsManager()
        am.track_event("old_event", "test")
        count = am.clear_old_events(0)  # 0 days = clear all
        assert isinstance(count, int)
