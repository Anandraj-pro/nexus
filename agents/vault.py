"""nexus-vault — manages credentials and browser sessions securely."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Service name prefix used in the OS keyring
KEYRING_SERVICE = "nexus"


class NexusVault:
    """
    Central credential manager. Reads from keyring (preferred) with .env fallback.

    Usage:
        vault = NexusVault(config)
        creds = vault.get_credentials("linkedin")
        email = creds["email"]
        password = creds["password"]
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        vault_cfg = config.get("vault", {})
        self._backend: str = vault_cfg.get("credential_backend", "env")
        self._session_dir = Path(vault_cfg.get("session_dir", "resources/credentials/sessions/"))
        self._session_dir.mkdir(parents=True, exist_ok=True)

    def get_credentials(self, platform: str) -> dict[str, str]:
        """Return email + password for a platform. Keyring > .env."""
        if self._backend == "keyring":
            return self._from_keyring(platform)
        return self._from_env(platform)

    def store_credentials(self, platform: str, email: str, password: str) -> None:
        """Store credentials in the OS keyring."""
        try:
            import keyring

            keyring.set_password(f"{KEYRING_SERVICE}_{platform}", "email", email)
            keyring.set_password(f"{KEYRING_SERVICE}_{platform}", "password", password)
            logger.info("Vault → stored credentials for %s in keyring", platform)
        except Exception:
            logger.exception("Failed to store credentials for %s", platform)

    def _from_keyring(self, platform: str) -> dict[str, str]:
        try:
            import keyring

            email = keyring.get_password(f"{KEYRING_SERVICE}_{platform}", "email") or ""
            password = keyring.get_password(f"{KEYRING_SERVICE}_{platform}", "password") or ""
            if not email:
                logger.warning("Keyring has no credentials for %s — falling back to env", platform)
                return self._from_env(platform)
            return {"email": email, "password": password}
        except Exception:
            logger.exception("Keyring read failed for %s", platform)
            return self._from_env(platform)

    def _from_env(self, platform: str) -> dict[str, str]:
        prefix = platform.upper()
        return {
            "email": os.getenv(f"{prefix}_EMAIL", ""),
            "password": os.getenv(f"{prefix}_PASSWORD", ""),
        }

    # ── Session management ────────────────────────────────────────────────────

    def save_session(self, platform: str, cookies: list[dict[str, Any]]) -> None:
        """Persist browser cookies so Playwright can resume authenticated sessions."""
        path = self._session_dir / f"{platform}_session.json"
        path.write_text(json.dumps(cookies, indent=2))
        logger.info("Vault → session saved for %s", platform)

    def load_session(self, platform: str) -> list[dict[str, Any]] | None:
        """Load saved browser cookies. Returns None if expired or missing."""
        path = self._session_dir / f"{platform}_session.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return data
        except json.JSONDecodeError:
            logger.warning("Corrupt session file for %s — ignoring", platform)
            return None

    def clear_session(self, platform: str) -> None:
        path = self._session_dir / f"{platform}_session.json"
        if path.exists():
            path.unlink()
            logger.info("Vault → session cleared for %s", platform)