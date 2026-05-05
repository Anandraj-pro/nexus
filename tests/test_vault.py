"""Unit tests for jireh-vault — session and credential management."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.vault import JirehVault


def _config(session_dir: Path) -> dict:
    return {"vault": {"credential_backend": "env", "session_dir": str(session_dir)}}


# ─── Session save / load ───────────────────────────────────────────────────────

def test_save_and_load_session_round_trips(tmp_path: Path):
    vault = JirehVault(_config(tmp_path))
    cookies = [{"name": "session", "value": "abc123", "domain": "naukri.com"}]
    vault.save_session("naukri", cookies)
    assert vault.load_session("naukri") == cookies


def test_load_session_returns_none_when_missing(tmp_path: Path):
    vault = JirehVault(_config(tmp_path))
    assert vault.load_session("linkedin") is None


def test_load_session_returns_none_for_corrupt_file(tmp_path: Path):
    path = tmp_path / "linkedin_session.json"
    path.write_text("not valid json {{{")
    vault = JirehVault(_config(tmp_path))
    assert vault.load_session("linkedin") is None


def test_save_persists_multiple_cookies(tmp_path: Path):
    vault = JirehVault(_config(tmp_path))
    cookies = [
        {"name": "a", "value": "1", "domain": "naukri.com"},
        {"name": "b", "value": "2", "domain": "naukri.com"},
    ]
    vault.save_session("naukri", cookies)
    loaded = vault.load_session("naukri")
    assert len(loaded) == 2
    assert loaded[1]["name"] == "b"


def test_save_overwrites_existing_session(tmp_path: Path):
    vault = JirehVault(_config(tmp_path))
    vault.save_session("linkedin", [{"name": "old", "value": "v1"}])
    vault.save_session("linkedin", [{"name": "new", "value": "v2"}])
    loaded = vault.load_session("linkedin")
    assert loaded[0]["name"] == "new"


# ─── Session clear ────────────────────────────────────────────────────────────

def test_clear_session_removes_file(tmp_path: Path):
    vault = JirehVault(_config(tmp_path))
    vault.save_session("linkedin", [{"name": "x", "value": "y"}])
    vault.clear_session("linkedin")
    assert not (tmp_path / "linkedin_session.json").exists()


def test_clear_session_is_noop_when_missing(tmp_path: Path):
    vault = JirehVault(_config(tmp_path))
    vault.clear_session("naukri")  # must not raise


def test_cleared_session_load_returns_none(tmp_path: Path):
    vault = JirehVault(_config(tmp_path))
    vault.save_session("linkedin", [{"name": "x", "value": "y"}])
    vault.clear_session("linkedin")
    assert vault.load_session("linkedin") is None


# ─── Session directory creation ───────────────────────────────────────────────

def test_init_creates_session_dir(tmp_path: Path):
    nested = tmp_path / "deep" / "sessions"
    JirehVault({"vault": {"credential_backend": "env", "session_dir": str(nested)}})
    assert nested.exists()


def test_save_works_in_nested_dir(tmp_path: Path):
    nested = tmp_path / "a" / "b" / "sessions"
    vault = JirehVault({"vault": {"credential_backend": "env", "session_dir": str(nested)}})
    vault.save_session("naukri", [])
    assert (nested / "naukri_session.json").exists()


# ─── Credential fallback from env ─────────────────────────────────────────────

def test_env_credentials_returned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LINKEDIN_EMAIL", "anand@example.com")
    monkeypatch.setenv("LINKEDIN_PASSWORD", "secret123")
    vault = JirehVault(_config(tmp_path))
    creds = vault.get_credentials("linkedin")
    assert creds["email"] == "anand@example.com"
    assert creds["password"] == "secret123"


def test_env_credentials_empty_when_not_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("NAUKRI_EMAIL", raising=False)
    monkeypatch.delenv("NAUKRI_PASSWORD", raising=False)
    vault = JirehVault(_config(tmp_path))
    creds = vault.get_credentials("naukri")
    assert creds["email"] == ""
    assert creds["password"] == ""


def test_env_credentials_platform_prefix_uppercase(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GREENHOUSE_EMAIL", "gh@example.com")
    monkeypatch.setenv("GREENHOUSE_PASSWORD", "ghpass")
    vault = JirehVault(_config(tmp_path))
    creds = vault.get_credentials("greenhouse")
    assert creds["email"] == "gh@example.com"