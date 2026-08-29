from django.core import signing

STATE_SALT = "storage-oauth-state"
STATE_MAX_AGE_SECONDS = 600


def build_state(user_id, provider):
    return signing.dumps({"user_id": user_id, "provider": provider}, salt=STATE_SALT)


def resolve_state(state):
    """Returns (user_id, provider). Raises signing.BadSignature (or its
    subclass SignatureExpired) on an invalid or expired state -- callers
    already catch signing.BadSignature, which covers both."""
    payload = signing.loads(state, salt=STATE_SALT, max_age=STATE_MAX_AGE_SECONDS)
    return payload["user_id"], payload["provider"]
