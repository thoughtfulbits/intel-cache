from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


HASH_MODES = ("raw", "normalized")

TRACKING_QUERY_PARAMS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "msclkid",
    "ref",
    "ref_src",
    "spm",
    "twclid",
}

VOLATILE_LINE_MARKERS = (
    "build time",
    "cache-buster",
    "cache buster",
    "cookie:",
    "fetched at",
    "generated at",
    "last generated",
    "last updated",
    "set-cookie",
    "timestamp:",
)


def canonical_source_url(url: str) -> str:
    """Return a stable URL identity by removing known tracking-only parts."""
    parts = urlsplit(url.strip())
    query_items = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking_param(key)
    ]
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path or "/",
            urlencode(query_items, doseq=True),
            "",
        )
    )


def sha256_content(content: bytes, *, mode: str = "raw") -> str:
    if mode not in HASH_MODES:
        raise ValueError(f"unknown hash mode: {mode}")
    hashed_content = normalize_content(content) if mode == "normalized" else content
    return hashlib.sha256(hashed_content).hexdigest()


def normalize_content(content: bytes) -> bytes:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return content

    lines = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        lowered = line.lower()
        if any(marker in lowered for marker in VOLATILE_LINE_MARKERS):
            lines.append(_volatile_label(line))
        else:
            lines.append(line)
    normalized = "\n".join(lines)
    normalized = re.sub(r"[ \t]+$", "", normalized, flags=re.MULTILINE)
    return normalized.encode("utf-8")


def _is_tracking_param(key: str) -> bool:
    lowered = key.lower()
    return lowered.startswith("utm_") or lowered in TRACKING_QUERY_PARAMS


def _volatile_label(line: str) -> str:
    key = line.split(":", 1)[0].strip()
    if not key:
        return "<volatile>"
    return f"{key}: <volatile>"
