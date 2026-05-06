"""Log analysis utilities (moved out of the deprecated mcp_server tools)."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parent / "sample_logs"

_SEVERITY_RE = re.compile(r"\b(ERROR|WARNING|INFO)\b")
_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
_VALID_LOG_KEYS = {"app_errors", "auth_events", "network_events"}


def _resolve_log_path(log_file: str) -> Path:
    name = log_file.strip()
    if name.endswith(".log"):
        name = name[:-4]
    if name not in _VALID_LOG_KEYS:
        raise FileNotFoundError(
            f"Unknown log file '{log_file}'. Expected one of: {sorted(_VALID_LOG_KEYS)}."
        )
    return LOGS_DIR / f"{name}.log"


def _parse_severity(line: str) -> str | None:
    match = _SEVERITY_RE.search(line)
    return match.group(1) if match else None


def _parse_timestamp(line: str) -> datetime | None:
    match = _TS_RE.match(line)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def analyze_logs(
    log_file: str,
    severity: str | None = None,
    last_n_lines: int = 20,
) -> dict:
    path = _resolve_log_path(log_file)
    if not path.exists():
        return {
            "log_file": log_file,
            "total_lines_read": 0,
            "matches_found": 0,
            "entries": [],
            "summary": f"Log file {log_file} could not be found.",
        }

    all_lines = path.read_text().splitlines()
    tail = all_lines[-last_n_lines:] if last_n_lines > 0 else all_lines
    base_index = len(all_lines) - len(tail) + 1

    severity_filter = severity.upper() if severity else None
    entries: list[dict] = []
    counts: dict[str, int] = {"ERROR": 0, "WARNING": 0, "INFO": 0}

    for offset, line in enumerate(tail):
        line_severity = _parse_severity(line)
        if severity_filter and line_severity != severity_filter:
            continue
        if line_severity:
            counts[line_severity] = counts.get(line_severity, 0) + 1
        entries.append(
            {
                "line_number": base_index + offset,
                "severity": line_severity or "UNKNOWN",
                "content": line,
            }
        )

    if severity_filter:
        summary = (
            f"Found {len(entries)} {severity_filter} entries in the last "
            f"{len(tail)} lines of {log_file}."
        )
    else:
        summary = (
            f"Scanned the last {len(tail)} lines of {log_file}: "
            f"{counts.get('ERROR', 0)} errors, "
            f"{counts.get('WARNING', 0)} warnings, "
            f"{counts.get('INFO', 0)} info."
        )

    return {
        "log_file": log_file,
        "total_lines_read": len(tail),
        "matches_found": len(entries),
        "entries": entries,
        "summary": summary,
    }


def get_recent_errors(last_n_lines: int = 10) -> dict:
    by_file: dict[str, list[str]] = {}
    most_recent: tuple[datetime | None, str | None] = (None, None)

    for key in sorted(_VALID_LOG_KEYS):
        path = LOGS_DIR / f"{key}.log"
        if not path.exists():
            by_file[f"{key}.log"] = []
            continue

        all_lines = path.read_text().splitlines()
        tail = all_lines[-last_n_lines:] if last_n_lines > 0 else all_lines
        errors = [ln for ln in tail if _parse_severity(ln) == "ERROR"]
        by_file[f"{key}.log"] = errors

        for ln in errors:
            ts = _parse_timestamp(ln)
            if ts is not None and (most_recent[0] is None or ts > most_recent[0]):
                most_recent = (ts, ln)

    if most_recent[1] is None:
        flat = [ln for lst in by_file.values() for ln in lst]
        most_recent_line = flat[-1] if flat else None
    else:
        most_recent_line = most_recent[1]

    return {
        "total_errors": sum(len(v) for v in by_file.values()),
        "by_file": by_file,
        "most_recent_error": most_recent_line,
    }
