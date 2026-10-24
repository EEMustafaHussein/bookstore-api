import secrets
import threading
import time
from collections import defaultdict, deque

from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()
# Checked against when the email is unknown, so a failed login takes the same time either way.
DUMMY_HASH = password_hash.hash("dummy-password-for-timing")

MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def password_problem(password: str) -> str | None:
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"كلمة المرور يجب أن تكون {MIN_PASSWORD_LENGTH} أحرف على الأقل"
    if len(password) > 128:
        return "كلمة المرور طويلة جداً"
    if password.isdigit() or password.isalpha():
        return "كلمة المرور يجب أن تحتوي على حروف وأرقام معاً"
    return None


def new_token() -> str:
    return secrets.token_urlsafe(32)


def tokens_match(expected: str | None, given: str | None) -> bool:
    if not expected or not given:
        return False
    return secrets.compare_digest(expected.encode(), given.encode())


class LoginRateLimiter:
    """Blocks a client after too many failed logins within a time window (per process)."""

    def __init__(self, max_failures: int = 8, window_seconds: int = 15 * 60):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        attempts = self._failures[key]
        while attempts and now - attempts[0] > self.window_seconds:
            attempts.popleft()
        return attempts

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key, time.monotonic())) >= self.max_failures

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


login_limiter = LoginRateLimiter()
