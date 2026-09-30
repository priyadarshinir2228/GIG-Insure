"""Input validation, parameterised SQL helpers and expiring HMAC-signed tokens."""
import base64, hashlib, hmac, json, os, re, time

from .data import PERSONAS

WORKER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
UPI_RE = re.compile(r"^[a-z0-9._-]{2,64}@[a-z]{2,32}$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,59}$")
SECRET = os.environ.get("GIGINSURE_SECRET", "dev-secret-change-me").encode()


class ValidationError(ValueError):
    pass


def validate_worker_id(v):
    if not isinstance(v, str) or not WORKER_ID_RE.match(v):
        raise ValidationError("worker_id must be 3-32 chars of letters, digits, '_' or '-'")
    return v


def validate_persona(v):
    if v not in PERSONAS:
        raise ValidationError(f"persona must be one of {sorted(PERSONAS)}")
    return v


def validate_upi(v):
    v = (v or "").strip().lower()
    if not UPI_RE.match(v):
        raise ValidationError("UPI handle must look like name@bank")
    return v


def validate_name(v):
    v = (v or "").strip()
    if not NAME_RE.match(v):
        raise ValidationError("name must be 2-60 letters")
    return v


def validate_zone(v, zone_ids):
    try:
        z = int(v)
    except (TypeError, ValueError):
        raise ValidationError("zone_id must be an integer")
    if z not in zone_ids:
        raise ValidationError("unknown zone_id")
    return z


def _b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign_token(worker_id, ttl_s=3600, now=None):
    payload = json.dumps({"sub": worker_id, "exp": int((now or time.time()) + ttl_s)}, separators=(",", ":")).encode()
    sig = hmac.new(SECRET, payload, hashlib.sha256).digest()
    return f"{_b64(payload)}.{_b64(sig)}"


def verify_token(token, now=None):
    """Return the worker id for a valid, unexpired token; None otherwise."""
    try:
        p, s = token.split(".")
        payload = _unb64(p)
        if not hmac.compare_digest(hmac.new(SECRET, payload, hashlib.sha256).digest(), _unb64(s)):
            return None
        d = json.loads(payload)
        if d["exp"] < (now or time.time()):
            return None
        return d["sub"]
    except Exception:
        return None
