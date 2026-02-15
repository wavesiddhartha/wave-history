from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_LONG_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_-]{32,}(?![A-Za-z0-9])")
_JWT_RE = re.compile(r"[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}")
_LONG_NUMBER_RE = re.compile(r"(?<!\d)\d{10,}(?!\d)")
_MULTI_SPACE_RE = re.compile(r"\s+")

_SENSITIVE_KEY_PARTS = (
    "token",
    "session",
    "sid",
    "auth",
    "email",
    "mail",
    "phone",
    "user",
    "password",
    "passwd",
    "secret",
    "key",
    "signature",
    "sig",
    "code",
    "otp",
    "csrf",
    "nonce",
)



def _is_sensitive_query_key(key: str) -> bool:
    lowered = key.lower().strip()
    if not lowered:
        return False
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)



def _looks_sensitive_value(value: str) -> bool:
    candidate = value.strip()
    if not candidate:
        return False
    if _JWT_RE.search(candidate):
        return True
    if _LONG_TOKEN_RE.search(candidate):
        return True
    return False



def redact_text(text: str, max_len: int = 280) -> str:
    if not text:
        return ""

    redacted = text
    redacted = _EMAIL_RE.sub("[redacted-email]", redacted)
    redacted = _JWT_RE.sub("[redacted-token]", redacted)
    redacted = _LONG_TOKEN_RE.sub("[redacted-token]", redacted)
    redacted = _LONG_NUMBER_RE.sub("[redacted-number]", redacted)
    redacted = _MULTI_SPACE_RE.sub(" ", redacted).strip()
    if len(redacted) > max_len:
        redacted = redacted[: max_len - 1].rstrip() + "…"
    return redacted



def sanitize_url(url: str, max_len: int = 2000) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""

    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return raw[:max_len]

    cleaned_pairs: list[tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        if _is_sensitive_query_key(key):
            continue
        if _looks_sensitive_value(value):
            continue
        safe_value = value.strip()
        if len(safe_value) > 240:
            safe_value = safe_value[:240]
        cleaned_pairs.append((key, safe_value))

    query = urlencode(cleaned_pairs, doseq=True)
    sanitized = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))
    return sanitized[:max_len]



def domain_from_url(url: str) -> str:
    parsed = urlsplit(url)
    domain = parsed.netloc.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain or "unknown"
