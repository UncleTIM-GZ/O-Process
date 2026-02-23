"""Project configuration — reads [tool.oprocess] from pyproject.toml."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

_DEFAULTS = {
    "boundary_threshold": 0.45,
    "audit_log_enabled": True,
    "default_language": "zh",
}

_config: dict | None = None


def _find_pyproject() -> Path | None:
    """Walk up from cwd to find pyproject.toml."""
    for parent in [Path.cwd(), *Path.cwd().parents]:
        candidate = parent / "pyproject.toml"
        if candidate.exists():
            return candidate
    return None


def get_config() -> dict:
    """Return [tool.oprocess] config, merged with defaults."""
    global _config
    if _config is not None:
        return _config

    _config = dict(_DEFAULTS)
    pyproject = _find_pyproject()
    if pyproject:
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            overrides = data.get("tool", {}).get("oprocess", {})
            _config.update(overrides)
        except Exception:
            pass  # Fall back to defaults
    return _config
