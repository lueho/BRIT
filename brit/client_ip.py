"""Client IP resolution behind Cloudflare and the Heroku router."""


def get_client_ip(request):
    """Return the client address the proxy chain vouches for.

    Cloudflare-fronted traffic: Cloudflare overwrites any
    client-supplied ``CF-Connecting-IP`` with the real client IP, so it
    is trusted when ``CF-RAY`` is also present — required anyway, since
    the rightmost XFF entry on that path is a shared CF edge IP.
    Direct traffic: Heroku's router appends the observed peer IP on the
    right of ``X-Forwarded-For``, so the LAST entry is the only one the
    client cannot control; earlier entries can be forged per request.
    """
    cf_ip = request.META.get("HTTP_CF_CONNECTING_IP", "")
    if cf_ip and request.META.get("HTTP_CF_RAY"):
        return cf_ip.strip()
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")
