# Waste Atlas routing, public access and permalinks

## URL layout

The Waste Atlas is a sub-package of `waste_collection` with its own mount:

| Purpose | Path |
|---------|------|
| Entry point (redirects to the map overview) | `/waste_collection/waste-atlas/` |
| Map pages | `/waste_collection/waste-atlas/map/...` |
| Data API (GeoJSON and per-theme JSON) | `/waste_collection/waste-atlas/api/...` |
| Citable permalink | `/waste_collection/waste-atlas/p/<map_set>/<theme>/<year>/` |

The former `/waste_collection/api/waste-atlas/...` paths redirect permanently
(301, query string kept): `map/...` to the new map pages, everything else to the
new API prefix. They are declared through the `legacy_redirects` mechanism of
the `waste_collection` source-domain plugin
(`sources/waste_collection/waste_atlas/legacy_urls.py`). Published links and
third-party iframe embeds keep working through it.

Stored map configurations (`WasteAtlasMapConfiguration.configuration`) contain
API URLs; migration `0027` rewrites them to the new prefix.

## Public access

Map pages, the overview and the data API are public and only ever return
published (and archived) collections to anonymous visitors. Restricted:

- map configuration pages and the data-conflicts overview: staff only;
- `collection-conflicts/` API and the conflict overlay in the map config:
  staff and collection moderators (`can_moderate_collection`);
- `scope=mine|review|all`: only for the users those scopes are meant for;
  anonymous requests fall back to `published`.

The data API is limited by its own scoped throttle (`waste_atlas`, keyed on the
proxy-vouched client IP) and is exempt from the site-wide anonymous limit in
`AnonymousRateLimitMiddleware`, because one map load issues several requests.
Query parameters are validated in `waste_atlas/params.py`; the API rejects a
malformed or oversized `nuts_prefix` list (more than 16 codes) with HTTP 400.

The client IP (`brit/client_ip.py`) is the rightmost `X-Forwarded-For` entry,
which Heroku's router appends. `CF-Connecting-IP` is trusted only when that
peer is a Cloudflare edge (`CLOUDFLARE_TRUSTED_PROXY_RANGES`, defaulting to
Cloudflare's published ranges); from any other peer the header is ignored.

## Permalinks

`/waste_collection/waste-atlas/p/<map_set>/<theme>/<year>/` names a map by its
region set (for example `DE`, `DE-NW`, `IT-ST`), theme and year instead of by
page path. It redirects (302) to the map's current page with `?year=<year>`,
always in the published scope. If page paths or the mount point change, the
permalink keeps working; only `resolve_map_page` needs to keep resolving
`(map_set, theme)`.

A permalink shows the data as published when it is opened; it is not a frozen
snapshot. Map pages of region sets show their permalink in the Options tab,
only while they show their registered region (unlocked pages can render another
region from the query string). The link follows in-place year reloads and is
hidden for selections it cannot name. Change maps have no permalink.
