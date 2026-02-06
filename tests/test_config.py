"""Tests for configuration management."""

import os
import pytest

from app.config import Settings, get_settings, reset_settings


class TestSettings:
    def test_default_values(self):
        settings = Settings()
        assert settings.ollama_host == "http://localhost:11434"
        assert settings.ollama_model == "qwen2.5:1.5b-instruct"
        assert settings.smtp_host == "smtp.gmail.com"
        assert settings.smtp_port == 587
        assert settings.digest_cron_hour == 6
        assert settings.digest_cron_minute == 0
        assert settings.digest_timezone == "UTC"
        assert settings.pheme_port == 8020

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")
        monkeypatch.setenv("PHEME_PORT", "9999")
        reset_settings()
        settings = Settings()
        assert settings.ollama_host == "http://localhost:11434"
        assert settings.pheme_port == 9999

    def test_singleton_pattern(self):
        reset_settings()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_reset_clears_singleton(self):
        s1 = get_settings()
        reset_settings()
        s2 = get_settings()
        assert s1 is not s2
