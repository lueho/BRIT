from django.conf import settings


def ensure_initial_data(stdout=None):
    """Ensure cookie-consent group and cookie definitions exist.

    Creates only the consent metadata the site itself needs: a required
    "essential" group holding the session and CSRF cookies, and - when a
    Google Analytics key is configured - an optional "analytics" group for
    the ``_ga`` cookie. Running this repeatedly never rewrites metadata that
    already exists.
    """
    if getattr(settings, "COOKIE_CONSENT_ENABLED", True) is False:
        return

    from cookie_consent.models import Cookie, CookieGroup

    essential, _ = CookieGroup.objects.get_or_create(
        varname="essential",
        defaults={
            "name": "Essential",
            "description": "Cookies required for this site to work.",
            "is_required": True,
            "is_deletable": False,
        },
    )
    for cookie_name, description in (
        (settings.SESSION_COOKIE_NAME, "Keeps you signed in between pages."),
        (settings.CSRF_COOKIE_NAME, "Protects forms against forged requests."),
    ):
        Cookie.objects.get_or_create(
            cookiegroup=essential,
            name=cookie_name,
            defaults={
                "description": description,
                "path": "/",
                "domain": "",
            },
        )

    if getattr(settings, "GOOGLE_ANALYTICS_KEY", None):
        analytics, _ = CookieGroup.objects.get_or_create(
            varname="analytics",
            defaults={
                "name": "Analytics",
                "description": "Optional cookies used to measure site usage.",
                "is_required": False,
            },
        )
        Cookie.objects.get_or_create(
            cookiegroup=analytics,
            name="_ga",
            defaults={
                "description": "Google Analytics identifier.",
                "path": "/",
                "domain": "",
            },
        )
