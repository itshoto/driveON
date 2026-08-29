import anthropic
from django.conf import settings


def is_configured():
    return bool(settings.ANTHROPIC_API_KEY)


def get_client():
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
