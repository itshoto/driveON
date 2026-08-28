import firebase_admin
from django.conf import settings
from firebase_admin import credentials

_app = None


def get_firebase_app():
    """Lazily initialize the Firebase Admin SDK app used to verify ID
    tokens issued to the frontend by Firebase Authentication."""
    global _app
    if _app is None:
        if settings.FIREBASE_CREDENTIALS_PATH:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        else:
            cred = credentials.ApplicationDefault()
        _app = firebase_admin.initialize_app(cred)
    return _app
