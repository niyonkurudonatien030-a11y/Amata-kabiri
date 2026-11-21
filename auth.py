"""Authentication: password hashing, sessions, role checks, login throttling."""
import time
from functools import wraps

from flask import session
from werkzeug.security import check_password_hash, generate_password_hash

from . import database as db

_FAILS = {}  # (phone) -> [count, first_failure_time]; in-memory, resets on restart
MAX_FAILS, WINDOW = 5, 300


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


def hash_password(raw):
    return generate_password_hash(raw)


def throttled(phone):
    rec = _FAILS.get(phone)
    if not rec:
        return False
    if time.time() - rec[1] > WINDOW:
        _FAILS.pop(phone, None)
        return False
    return rec[0] >= MAX_FAILS


def record_failure(phone):
    rec = _FAILS.get(phone)
    if not rec or time.time() - rec[1] > WINDOW:
        _FAILS[phone] = [1, time.time()]
    else:
        rec[0] += 1


def verify_login(phone, password):
    if throttled(phone):
        raise ApiError("Too many failed attempts. Wait 5 minutes and try again.", 429)
    user = db.one("SELECT * FROM users WHERE phone = ?", (phone,))
    if not user or not check_password_hash(user["password_hash"], password or ""):
        record_failure(phone)
        raise ApiError("Wrong phone number or password", 401)
    if not user["is_active"]:
        raise ApiError("This account is disabled. Contact an administrator.", 403)
    _FAILS.pop(phone, None)
    return user


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    user = db.one("SELECT * FROM users WHERE id = ? AND is_active = 1", (uid,))
    return user


def login_required(*roles):
    """@login_required() = any signed-in user; @login_required('admin') = only those roles."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                raise ApiError("Please sign in", 401)
            if roles and user["role"] not in roles:
                raise ApiError("Your role is not allowed to do this", 403)
            return fn(user, *args, **kwargs)
        return wrapper
    return decorator
