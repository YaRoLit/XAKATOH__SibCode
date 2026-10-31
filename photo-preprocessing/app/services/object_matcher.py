import math

from shapely import Point, Polygon

from app.core.logging import get_logger
from app.db.models import Object

log = get_logger(__name__)


def _to_meters(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    x = (lon - lon0) * 111_000.0 * math.cos(math.radians(lat0))
    y = (lat - lat0) * 111_000.0
    return x, y


def match(lat: float, lon: float, objects: list[Object], buffer_m: float) -> Object | None:
    """Point-in-polygon с буфером; при нескольких кандидатах — ближайший центроид."""
    candidates = []
    for obj in objects:
        pts = [_to_meters(p["lat"], p["lon"], lat, lon) for p in obj.plot_corners]
        poly = Polygon(pts).buffer(buffer_m)
        if poly.contains(Point(0, 0)):
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            candidates.append((math.hypot(cx, cy), obj))
    if not candidates:
        log.debug("matcher: no candidate for (%.6f, %.6f)", lat, lon)
        return None
    candidates.sort(key=lambda c: c[0])
    log.debug("matcher: candidates=%s picked=%s", [o.id for _, o in candidates], candidates[0][1].id)
    return candidates[0][1]