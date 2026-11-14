import ipaddress
import os
import secrets
import sys
from pathlib import Path
from typing import List, Optional, Set
from urllib.parse import urlparse

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.app.core.config import get_default_data_dir

BLOCKED_METADATA_HOSTS: Set[str] = {
    "metadata.google.internal",
    "metadata.azure.com",
    "instance-data",
    "metadata",
}

BLOCKED_IP_NETWORKS: List[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("169.254.0.0/16"),  # IPv4 link-local & cloud metadata
    ipaddress.ip_network("fe80::/10"),      # IPv6 link-local
    ipaddress.ip_network("100.64.0.0/10"),  # CGNAT
]

EXACT_BLOCKED_IPS: Set[ipaddress.IPv4Address | ipaddress.IPv6Address] = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("fd00:ec2::254"),  # AWS IPv6 metadata
}


def get_session_token_file() -> Path:
    return get_default_data_dir() / ".session_token"


SESSION_TOKEN_FILE = get_session_token_file()
_runtime_session_token: Optional[str] = None


def get_or_create_app_token() -> str:
    """Returns or generates a 32-byte secure ephemeral session token for local API access."""
    global _runtime_session_token
    if _runtime_session_token:
        return _runtime_session_token

    env_token = os.environ.get("APP_SESSION_TOKEN")
    if env_token and env_token.strip():
        _runtime_session_token = env_token.strip()
        return _runtime_session_token

    token_file = get_session_token_file()
    if token_file.exists():
        try:
            content = token_file.read_text(encoding="utf-8").strip()
            if content:
                _runtime_session_token = content
                return _runtime_session_token
        except Exception:
            pass

    token = secrets.token_hex(32)
    _runtime_session_token = token

    try:
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(token, encoding="utf-8")
    except Exception:
        pass

    return _runtime_session_token


def reset_app_token() -> str:
    """Forces generation of a new ephemeral session token (useful for test isolation)."""
    global _runtime_session_token
    token = secrets.token_hex(32)
    _runtime_session_token = token
    try:
        SESSION_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        SESSION_TOKEN_FILE.write_text(token, encoding="utf-8")
    except Exception:
        pass
    return token


api_key_header = APIKeyHeader(name="X-App-Token", auto_error=False)


def verify_app_token(token: Optional[str] = Security(api_key_header)) -> str:
    """FastAPI dependency to verify the ephemeral X-App-Token header."""
    expected = get_or_create_app_token()
    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autentikasi sesi aplikasi lokal diperlukan. Sediakan header 'X-App-Token' yang valid.",
        )
    return token


class AppTokenAuthMiddleware(BaseHTTPMiddleware):
    """Protects all non-exempt API routes from unauthorized local processes and cross-origin abuse."""

    EXEMPT_PATHS = {
        "/",
        "/api/v1/health",
        "/api/v1/auth/session",
        "/api/v1/openapi.json",
        "/api/v1/docs",
        "/api/v1/redoc",
    }

    async def dispatch(self, request: Request, call_next):
        # 1. Allow OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # 2. Allow exempt paths (root, health probe, auth session handshake, docs)
        if path in self.EXEMPT_PATHS or path.startswith("/api/v1/docs") or path.startswith("/api/v1/redoc"):
            return await call_next(request)

        # 3. Guard all endpoints starting with /api/v1
        if path.startswith("/api/v1"):
            token = request.headers.get("X-App-Token") or request.headers.get("x-app-token")
            expected_token = get_or_create_app_token()
            if not token or not secrets.compare_digest(token, expected_token):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "Autentikasi sesi aplikasi lokal diperlukan. Sediakan header 'X-App-Token' yang valid."
                    },
                )

        return await call_next(request)


def validate_probe_url(url: str) -> str:
    """Validates an endpoint URL for HTTP probing to prevent SSRF and credential exfiltration.

    Rules:
    - Requires 'http' or 'https' scheme.
    - Rejects invalid/malicious schemes (e.g. file, gopher, ftp, ldap, dict).
    - Disallows userinfo (username:password@host).
    - Blocks Cloud Metadata IP (169.254.169.254), link-local IP ranges, and known cloud metadata hostnames.
    - Permits local loopback (localhost, 127.0.0.1) and valid remote HTTPS gateways.

    Returns:
        The validated URL string stripped of surrounding whitespace.

    Raises:
        ValueError: If the URL fails any security check.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL endpoint tidak boleh kosong.")

    url_str = url.strip()
    if not url_str:
        raise ValueError("URL endpoint tidak boleh kosong.")

    # Reject non-printable characters or null bytes
    if any(ord(c) < 32 or ord(c) == 127 for c in url_str):
        raise ValueError("URL mengandung karakter kontrol yang tidak valid.")

    try:
        parsed = urlparse(url_str)
    except Exception as e:
        raise ValueError(f"Format URL tidak valid: {str(e)}")

    # 1. Scheme check
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"Skema URL '{scheme}' tidak diizinkan. Hanya skema http dan https yang didukung.")

    # 2. Hostname check
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise ValueError("URL endpoint harus menyertakan nama host atau alamat IP yang valid.")

    # Disallow userinfo to prevent obfuscation and credential leaks
    if parsed.username or parsed.password:
        raise ValueError("URL endpoint tidak boleh menyertakan kredensial (userinfo).")

    # 3. Check blocked metadata hostnames
    if hostname in BLOCKED_METADATA_HOSTS or any(hostname.endswith("." + b) for b in BLOCKED_METADATA_HOSTS):
        raise ValueError("Akses ke host metadata cloud diblokir untuk mencegah eksfiltrasi.")

    # 4. Check IP addresses (literal, integer, hex)
    parsed_ip = None
    try:
        parsed_ip = ipaddress.ip_address(hostname)
    except ValueError:
        if hostname.isdigit():
            try:
                parsed_ip = ipaddress.ip_address(int(hostname))
            except ValueError:
                pass
        elif hostname.startswith("0x") or hostname.startswith("0X"):
            try:
                parsed_ip = ipaddress.ip_address(int(hostname, 16))
            except ValueError:
                pass

    if parsed_ip is not None:
        # Unpack IPv4-mapped IPv6 addresses (e.g. ::ffff:169.254.169.254) so IPv4 rules cannot be bypassed
        ips_to_check = [parsed_ip]
        mapped_v4 = getattr(parsed_ip, "ipv4_mapped", None)
        if mapped_v4 is not None:
            ips_to_check.append(mapped_v4)

        for ip_obj in ips_to_check:
            if ip_obj in EXACT_BLOCKED_IPS:
                raise ValueError("Akses ke IP Cloud Metadata (169.254.169.254) diblokir.")

            if ip_obj.is_unspecified or ip_obj.is_multicast:
                raise ValueError("Akses ke alamat IP unspecified atau multicast diblokir.")

            for net in BLOCKED_IP_NETWORKS:
                if ip_obj in net:
                    raise ValueError("Akses ke alamat link-local diblokir.")

    return url_str


# =============================================================================
# ReDoS Mitigation & Regex Matching Protection
# =============================================================================

import concurrent.futures
import re

_REGEX_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="regex_matcher")

# ReDoS anti-patterns
# 1. Nested quantifiers: group containing repetition followed by repetition, e.g. (a+)+, (a*)*, ([0-9]+)+
NESTED_QUANTIFIER_PATTERN = re.compile(r"\([^)]*[\+\*\?\{][^)]*\)[\+\*\{]")
# 2. Adjacent unbounded wildcards, e.g. .*.*, .+.+, .*..*
CONSECUTIVE_WILDCARDS_PATTERN = re.compile(r"(\.\*|\.\+){2,}")
# 3. Overlapping alternation with repetition, e.g. (a|a+)+
OVERLAPPING_ALTERNATION_PATTERN = re.compile(r"\([^)]*\|[^)]*[\+\*][^)]*\)[\+\*\{]")


def validate_regex_pattern(pattern: str, max_length: int = 256) -> str:
    """Validates a regex pattern for syntax correctness and ReDoS catastrophic backtracking vulnerabilities.

    Rules:
    - Length must not exceed max_length (default 256).
    - Must compile cleanly with standard `re.compile`.
    - Must not contain nested quantifiers (e.g. `(a+)+`, `(a*)*`, `([0-9]+)+`).
    - Must not contain multiple consecutive unbounded wildcards (e.g. `.*.*`).

    Raises:
        ValueError: If the pattern is invalid or poses a ReDoS risk.
    """
    if not pattern or not isinstance(pattern, str):
        raise ValueError("Pola regex tidak boleh kosong.")

    p_str = pattern.strip()
    if not p_str:
        raise ValueError("Pola regex tidak boleh kosong.")

    if len(p_str) > max_length:
        raise ValueError(f"Pola regex terlalu panjang ({len(p_str)} karakter, maksimal {max_length}).")

    # 1. Syntax check
    try:
        re.compile(p_str)
    except re.error as e:
        raise ValueError(f"Sintaks regex tidak valid: {str(e)}")

    # 2. ReDoS check: nested quantifiers
    if NESTED_QUANTIFIER_PATTERN.search(p_str):
        raise ValueError("Pola regex ditolak karena mengandung quantifier bertingkat (nested quantifiers) yang berisiko ReDoS.")

    # 3. ReDoS check: overlapping alternation with repetition
    if OVERLAPPING_ALTERNATION_PATTERN.search(p_str):
        raise ValueError("Pola regex ditolak karena mengandung alternasi bertingkat yang berisiko ReDoS.")

    # 4. ReDoS check: consecutive wildcards
    if CONSECUTIVE_WILDCARDS_PATTERN.search(p_str):
        raise ValueError("Pola regex ditolak karena mengandung wildcard berturut-turut yang berisiko ReDoS.")

    return p_str


def safe_regex_search(pattern: str, text: str, timeout_seconds: float = 0.5) -> bool:
    """Safely executes regex search with pre-validation and strict timeout enforcement."""
    if not pattern or not isinstance(pattern, str) or text is None:
        return False

    try:
        validate_regex_pattern(pattern)
    except ValueError:
        return False

    try:
        future = _REGEX_EXECUTOR.submit(re.search, pattern, str(text), re.IGNORECASE)
        match = future.result(timeout=timeout_seconds)
        return bool(match)
    except concurrent.futures.TimeoutError:
        return False
    except Exception:
        return False
