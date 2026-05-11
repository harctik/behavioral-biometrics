"""
Advanced utility functions for Behavior-Based Authentication API.

This module provides additional utility functions for security, data processing,
caching, rate limiting, and other common operations.
"""

import base64
import hashlib
import hmac
import json
import random
import string
import time
import uuid
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urlencode, urlparse, urlunparse

import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


# ============================================================================
# Security Utilities
# ============================================================================


def generate_secure_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.

    Args:
        length: Length of the token in bytes (default: 32)

    Returns:
        Base64-encoded secure token
    """
    random_bytes = random.SystemRandom().randbytes(length)
    return base64.urlsafe_b64encode(random_bytes).decode("utf-8").rstrip("=")


def generate_api_key(prefix: str = "ba_") -> str:
    """
    Generate a secure API key.

    Args:
        prefix: Prefix for the API key (default: "ba_")

    Returns:
        Secure API key in format: prefix + random_part + secret_part
    """
    random_part = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    secret_part = generate_secure_token(24)
    return f"{prefix}{random_part}_{secret_part}"


def hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    """
    Hash a password using PBKDF2 with SHA-256.

    Args:
        password: Plain text password
        salt: Optional salt (generated if not provided)

    Returns:
        Tuple of (hashed_password, salt)
    """
    if salt is None:
        salt = random.SystemRandom().randbytes(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )

    hashed = kdf.derive(password.encode("utf-8"))
    return hashed, salt


def verify_password(password: str, hashed_password: bytes, salt: bytes) -> bool:
    """
    Verify a password against a hash.

    Args:
        password: Plain text password to verify
        hashed_password: Previously hashed password
        salt: Salt used during hashing

    Returns:
        True if password matches, False otherwise
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )

    try:
        kdf.verify(password.encode("utf-8"), hashed_password)
        return True
    except Exception:
        return False


def generate_jwt_token(
    payload: Dict[str, Any],
    secret_key: str,
    algorithm: str = "HS256",
    expires_in: Optional[int] = None,
) -> str:
    """
    Generate a JWT token.

    Args:
        payload: Token payload
        secret_key: Secret key for signing
        algorithm: JWT algorithm (default: HS256)
        expires_in: Token expiration in seconds

    Returns:
        JWT token string
    """
    if expires_in:
        payload["exp"] = int(time.time()) + expires_in

    payload["iat"] = int(time.time())
    payload["jti"] = str(uuid.uuid4())

    return jwt.encode(payload, secret_key, algorithm=algorithm)


def verify_jwt_token(
    token: str, secret_key: str, algorithms: List[str] = None
) -> Dict[str, Any]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string
        secret_key: Secret key for verification
        algorithms: List of allowed algorithms (default: ["HS256"])

    Returns:
        Decoded token payload

    Raises:
        jwt.InvalidTokenError: If token is invalid
    """
    if algorithms is None:
        algorithms = ["HS256"]

    return jwt.decode(token, secret_key, algorithms=algorithms)


def encrypt_data(data: Union[str, bytes], key: bytes) -> bytes:
    """
    Encrypt data using Fernet symmetric encryption.

    Args:
        data: Data to encrypt (string or bytes)
        key: Encryption key (must be 32 url-safe base64-encoded bytes)

    Returns:
        Encrypted data
    """
    if isinstance(data, str):
        data = data.encode("utf-8")

    fernet = Fernet(key)
    return fernet.encrypt(data)


def decrypt_data(encrypted_data: bytes, key: bytes) -> str:
    """
    Decrypt data using Fernet symmetric encryption.

    Args:
        encrypted_data: Encrypted data
        key: Encryption key (must be 32 url-safe base64-encoded bytes)

    Returns:
        Decrypted string
    """
    fernet = Fernet(key)
    decrypted = fernet.decrypt(encrypted_data)
    return decrypted.decode("utf-8")


def generate_encryption_key() -> bytes:
    """
    Generate a new Fernet encryption key.

    Returns:
        32 url-safe base64-encoded bytes
    """
    return Fernet.generate_key()


# ============================================================================
# Data Processing Utilities
# ============================================================================


def safe_json_parse(json_str: str, default: Any = None) -> Any:
    """
    Safely parse JSON string, returning default value on error.

    Args:
        json_str: JSON string to parse
        default: Default value to return on parse error

    Returns:
        Parsed JSON object or default value
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def deep_merge_dicts(dict1: Dict, dict2: Dict) -> Dict:
    """
    Deep merge two dictionaries.

    Args:
        dict1: First dictionary
        dict2: Second dictionary (values take precedence)

    Returns:
        Merged dictionary
    """
    result = dict1.copy()

    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value

    return result


def filter_dict_keys(data: Dict[str, Any], keys_to_keep: List[str]) -> Dict[str, Any]:
    """
    Filter dictionary to only include specified keys.

    Args:
        data: Input dictionary
        keys_to_keep: List of keys to keep

    Returns:
        Filtered dictionary
    """
    return {k: v for k, v in data.items() if k in keys_to_keep}


def mask_sensitive_data(
    data: Dict[str, Any], sensitive_fields: List[str] = None
) -> Dict[str, Any]:
    """
    Mask sensitive data in a dictionary.

    Args:
        data: Input dictionary
        sensitive_fields: List of sensitive field names (default: common sensitive fields)

    Returns:
        Dictionary with sensitive fields masked
    """
    if sensitive_fields is None:
        sensitive_fields = [
            "password",
            "token",
            "secret",
            "key",
            "authorization",
            "api_key",
        ]

    masked_data = data.copy()

    for key, value in masked_data.items():
        if any(sensitive in key.lower() for sensitive in sensitive_fields):
            if isinstance(value, str) and len(value) > 4:
                masked_data[key] = value[:2] + "*" * (len(value) - 4) + value[-2:]
            elif value:
                masked_data[key] = "***MASKED***"

    return masked_data


def normalize_phone_number(phone: str) -> str:
    """
    Normalize phone number to E.164 format.

    Args:
        phone: Phone number string

    Returns:
        Normalized phone number or empty string if invalid
    """
    if not phone:
        return ""

    # Remove all non-digit characters
    digits = "".join(filter(str.isdigit, phone))

    # If starts with 0, assume local format and add country code
    if digits.startswith("0"):
        digits = "91" + digits[1:]  # Default to India (+91)

    # Ensure it has country code
    if not digits.startswith("+"):
        digits = "+" + digits

    return digits


# ============================================================================
# Caching Utilities
# ============================================================================


class MemoryCache:
    """Simple in-memory cache with TTL support."""

    def __init__(self, default_ttl: int = 300):
        self._cache = {}
        self.default_ttl = default_ttl

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: instance default)
        """
        expire_at = time.time() + (ttl or self.default_ttl)
        self._cache[key] = {"value": value, "expire_at": expire_at}

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the cache.

        Args:
            key: Cache key
            default: Default value if key not found or expired

        Returns:
            Cached value or default
        """
        item = self._cache.get(key)
        if item is None:
            return default

        if time.time() > item["expire_at"]:
            del self._cache[key]
            return default

        return item["value"]

    def delete(self, key: str) -> bool:
        """
        Delete a key from the cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False if not found
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self):
        """Clear all cache entries."""
        self._cache.clear()

    def cleanup(self):
        """Remove expired entries from cache."""
        now = time.time()
        expired_keys = [k for k, v in self._cache.items() if now > v["expire_at"]]
        for key in expired_keys:
            del self._cache[key]

    def size(self) -> int:
        """Get number of entries in cache."""
        return len(self._cache)


# ============================================================================
# Rate Limiting Utilities
# ============================================================================


class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""

    def __init__(self, rate: float, capacity: int):
        """
        Initialize rate limiter.

        Args:
            rate: Tokens per second
            capacity: Maximum bucket capacity
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = threading.Lock()

    def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens acquired, False if rate limited
        """
        with self._lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        new_tokens = elapsed * self.rate

        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now

    def get_wait_time(self, tokens: int = 1) -> float:
        """
        Get time to wait before tokens become available.

        Args:
            tokens: Number of tokens needed

        Returns:
            Wait time in seconds, 0 if tokens available now
        """
        with self._lock:
            self._refill()

            if self.tokens >= tokens:
                return 0.0

            deficit = tokens - self.tokens
            return deficit / self.rate


# ============================================================================
# Decorators
# ============================================================================


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple = (Exception,),
):
    """
    Retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier
        exceptions: Tuple of exceptions to catch

    Returns:
        Decorator function
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        raise

                    time.sleep(current_delay)
                    current_delay *= backoff

            raise last_exception

        return wrapper

    return decorator


def timeout(seconds: float):
    """
    Timeout decorator for functions.

    Args:
        seconds: Timeout in seconds

    Returns:
        Decorator function
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = None
            exception = None

            def target():
                nonlocal result, exception
                try:
                    result = func(*args, **kwargs)
                except Exception as e:
                    exception = e

            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout=seconds)

            if thread.is_alive():
                raise TimeoutError(
                    f"Function {func.__name__} timed out after {seconds} seconds"
                )

            if exception:
                raise exception

            return result

        return wrapper

    return decorator


def memoize(ttl: Optional[int] = None, maxsize: Optional[int] = 128):
    """
    Memoization decorator with TTL support.

    Args:
        ttl: Time to live in seconds (None for infinite)
        maxsize: Maximum cache size (LRU eviction)

    Returns:
        Decorator function
    """
    cache = {}
    cache_order = []

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from args and kwargs
            key = (args, tuple(sorted(kwargs.items())))

            # Check cache
            if key in cache:
                value, timestamp = cache[key]
                if ttl is None or time.time() - timestamp < ttl:
                    # Update LRU order
                    if key in cache_order:
                        cache_order.remove(key)
                    cache_order.append(key)
                    return value

            # Call function
            result = func(*args, **kwargs)

            # Store in cache
            cache[key] = (result, time.time())
            cache_order.append(key)

            # Evict if over maxsize
            if maxsize and len(cache) > maxsize:
                oldest_key = cache_order.pop(0)
                del cache[oldest_key]

            return result

        return wrapper

    return decorator


# ============================================================================
# URL and Path Utilities
# ============================================================================


def build_url(
    base_url: str,
    path: str = "",
    query_params: Dict[str, Any] = None,
    fragment: str = "",
) -> str:
    """
    Build a URL from components.

    Args:
        base_url: Base URL (e.g., https://api.example.com)
        path: URL path (e.g., /api/v1/users)
        query_params: Dictionary of query parameters
        fragment: URL fragment

    Returns:
        Complete URL
    """
    # Parse base URL
    parsed = urlparse(base_url)

    # Append path
    if path:
        parsed_path = parsed.path.rstrip("/") + "/" + path.lstrip("/")
    else:
        parsed_path = parsed.path

    # Build query string
    query_string = ""
    if query_params:
        # Filter out None values
        filtered_params = {k: v for k, v in query_params.items() if v is not None}
        if filtered_params:
            query_string = urlencode(filtered_params)

    # Reconstruct URL
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed_path,
            parsed.params,
            query_string,
            fragment,
        )
    )


def is_safe_url(url: str, allowed_hosts: List[str] = None) -> bool:
    """
    Check if a URL is safe (not open redirect).

    Args:
        url: URL to check
        allowed_hosts: List of allowed hosts (None allows any)

    Returns:
        True if URL is safe, False otherwise
    """
    if not url:
        return False

    try:
        parsed = urlparse(url)

        # Check scheme
        if parsed.scheme not in ("http", "https", ""):
            return False

        # Check host if specified
        if parsed.netloc and allowed_hosts is not None:
            if parsed.netloc not in allowed_hosts:
                return False

        return True
    except Exception:
        return False


# ============================================================================
# Date/Time Utilities
# ============================================================================

import threading


def parse_date_string(date_str: str, formats: List[str] = None) -> Optional[datetime]:
    """
    Parse date string with multiple format attempts.

    Args:
        date_str: Date string to parse
        formats: List of format strings to try

    Returns:
        datetime object or None if parsing fails
    """
    if formats is None:
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y",
        ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def format_timedelta(delta: timedelta) -> str:
    """
    Format timedelta as human-readable string.

    Args:
        delta: timedelta object

    Returns:
        Human-readable string (e.g., "2 days, 3 hours, 15 minutes")
    """
    total_seconds = int(delta.total_seconds())

    if total_seconds < 60:
        return f"{total_seconds} seconds"

    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds > 0 and days == 0 and hours == 0:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    return ", ".join(parts)


def get_utc_timestamp() -> str:
    """
    Get current UTC timestamp in ISO format.

    Returns:
        ISO format timestamp string
    """
    from datetime import timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ============================================================================
# Validation and Sanitization
# ============================================================================


def sanitize_html(text: str) -> str:
    """
    Basic HTML sanitization to prevent XSS.

    Args:
        text: Input text

    Returns:
        Sanitized text
    """
    if not text:
        return ""

    # Replace potentially dangerous characters
    replacements = {
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
        "&": "&amp;",
    }

    for char, replacement in replacements.items():
        text = text.replace(char, replacement)

    return text


def validate_ip_address(ip: str) -> bool:
    """
    Validate IP address (IPv4 or IPv6).

    Args:
        ip: IP address string

    Returns:
        True if valid, False otherwise
    """
    import ipaddress

    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def validate_domain(domain: str) -> bool:
    """
    Validate domain name.

    Args:
        domain: Domain name string

    Returns:
        True if valid, False otherwise
    """
    import re

    pattern = r"^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
    return bool(re.match(pattern, domain))


# ============================================================================
# File and I/O Utilities
# ============================================================================


def read_file_safe(filepath: str, default: str = "") -> str:
    """
    Safely read file content.

    Args:
        filepath: Path to file
        default: Default value if file cannot be read

    Returns:
        File content or default
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except (IOError, OSError, FileNotFoundError):
        return default


def write_file_safe(filepath: str, content: str) -> bool:
    """
    Safely write content to file.

    Args:
        filepath: Path to file
        content: Content to write

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except (IOError, OSError):
        return False


def get_file_hash(filepath: str, algorithm: str = "sha256") -> Optional[str]:
    """
    Calculate file hash.

    Args:
        filepath: Path to file
        algorithm: Hash algorithm (sha256, md5, etc.)

    Returns:
        File hash or None if error
    """
    try:
        hash_obj = hashlib.new(algorithm)
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    except (IOError, OSError, FileNotFoundError):
        return None


# ============================================================================
# Performance Utilities
# ============================================================================


class Timer:
    """Context manager for timing code execution."""

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.end = time.time()
        self.elapsed = self.end - self.start

    def get_elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return self.elapsed * 1000

    def get_elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        return self.elapsed


def benchmark(
    func: Callable, iterations: int = 1000, *args, **kwargs
) -> Dict[str, float]:
    """
    Benchmark a function.

    Args:
        func: Function to benchmark
        iterations: Number of iterations
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Dictionary with benchmark results
    """
    import statistics

    times = []

    for _ in range(iterations):
        start = time.time()
        func(*args, **kwargs)
        end = time.time()
        times.append(end - start)

    return {
        "iterations": iterations,
        "total_time": sum(times),
        "avg_time": statistics.mean(times),
        "min_time": min(times),
        "max_time": max(times),
        "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
    }


# ============================================================================
# Main Execution Guard
# ============================================================================

if __name__ == "__main__":
    # Smoke-test utilities — no secrets in source code
    print("Testing advanced utilities...")

    token = generate_secure_token()
    print(f"Secure token generated: {len(token)} chars")

    api_key = generate_api_key()
    print(f"API key generated: {len(api_key)} chars")

    date_str = "2023-12-25T14:30:00Z"
    parsed = parse_date_string(date_str)
    print(f"Parsed date: {parsed}")

    print("Advanced utilities test complete.")
