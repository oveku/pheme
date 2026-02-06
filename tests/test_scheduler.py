"""Tests for scheduler job configuration."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.scheduler.jobs import start_scheduler, stop_scheduler, get_scheduler


class TestScheduler:
    """Tests for APScheduler configuration."""

    def test_start_scheduler_creates_instance(self):
        with patch("app.scheduler.jobs.AsyncIOScheduler") as MockScheduler:
            mock_instance = MagicMock()
            MockScheduler.return_value = mock_instance

            scheduler = start_scheduler()

            MockScheduler.assert_called_once()
            mock_instance.add_job.assert_called_once()
            mock_instance.start.assert_called_once()
            assert scheduler is mock_instance

    def test_scheduler_job_id(self):
        with patch("app.scheduler.jobs.AsyncIOScheduler") as MockScheduler:
            mock_instance = MagicMock()
            MockScheduler.return_value = mock_instance

            start_scheduler()

            call_kwargs = mock_instance.add_job.call_args
            assert call_kwargs.kwargs.get("id") == "daily_digest"

    def test_stop_scheduler(self):
        with patch("app.scheduler.jobs.AsyncIOScheduler") as MockScheduler:
            mock_instance = MagicMock()
            mock_instance.running = True
            MockScheduler.return_value = mock_instance

            start_scheduler()
            stop_scheduler()

            mock_instance.shutdown.assert_called_once()

    def test_get_scheduler_none_before_start(self):
        # Reset the module-level scheduler
        import app.scheduler.jobs as jobs_mod
        jobs_mod._scheduler = None
        assert get_scheduler() is None

    def test_get_scheduler_returns_instance(self):
        with patch("app.scheduler.jobs.AsyncIOScheduler") as MockScheduler:
            mock_instance = MagicMock()
            MockScheduler.return_value = mock_instance

            start_scheduler()
            result = get_scheduler()

            assert result is mock_instance

        # Cleanup
        import app.scheduler.jobs as jobs_mod
        jobs_mod._scheduler = None
