import math

import cv2
import numpy as np
from shapely import Polygon, box

from app.core.logging import get_logger

log = get_logger(__name__)


def _geo_to_px(lat, lon, meta, w, h):
    lat0, lon0 = meta["coordinates"]["lat"], meta["coordinates"]["lon"]
    alt = meta["altitude"]["relative"]
    cam = meta["camera"]
    gsd_x = cam["sensor_width_mm"] * alt / (cam["focal_length"] * w) / 1000.0 * 1000  # m/px
    gsd_x = cam["sensor_width_mm"] * alt / (cam["focal_length"] * w)
    gsd_y = cam["sensor_height_mm"] * alt / (cam["focal_length"] * h)
    e = (lon - lon0) * 111_000.0 * math.cos(math.radians(lat0))
    n = (lat - lat0) * 111_000.0
    yaw = math.radians(meta["orientation"]["yaw"])
    px, py = e / gsd_x, -n / gsd_y
    rx = px * math.cos(yaw) + py * math.sin(yaw)
    ry = -px * math.sin(yaw) + py * math.cos(yaw)
    return w / 2 + rx, h / 2 + ry


def compute(img: np.ndarray, meta: dict, plot_corners: list[dict]) -> tuple[float, np.ndarray, list[tuple[int, int]]]:
    """Возвращает (coverage, нормализованное изображение, углы участка в пикселях нормализованного)."""
    h, w = img.shape[:2]
    if len(plot_corners) == 1:
        if not (meta.get("altitude") or {}).get("relative"):
            return 1.0, img, []
        px, py = _geo_to_px(plot_corners[0]["lat"], plot_corners[0]["lon"], meta, w, h)
        coverage = 1.0 if 0 <= px < w and 0 <= py < h else 0.0
        log.debug("coverage: single-point in_frame=%s", coverage == 1.0)
        return coverage, img, [(int(px), int(py))]
    corners = [_geo_to_px(p["lat"], p["lon"], meta, w, h) for p in plot_corners]
    poly = Polygon(corners)
    if poly.area <= 0:
        return 0.0, img, [(int(x), int(y)) for x, y in corners]
    coverage = poly.intersection(box(0, 0, w, h)).area / poly.area
    log.debug("coverage: raw=%.3f", coverage)
    norm, norm_corners = _normalize(img, corners, meta["orientation"]["yaw"])
    return coverage, norm, norm_corners


def _normalize(img: np.ndarray, corners, yaw_deg: float):
    h, w = img.shape[:2]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    bx = int((max(xs) - min(xs)) * 0.15)
    by = int((max(ys) - min(ys)) * 0.15)
    x1, y1 = max(0, int(min(xs)) - bx), max(0, int(min(ys)) - by)
    x2, y2 = min(w, int(max(xs)) + bx), min(h, int(max(ys)) + by)
    crop = img[y1:y2, x1:x2]
    cc = [(c[0] - x1, c[1] - y1) for c in corners]
    cx = sum(p[0] for p in cc) / len(cc)
    cy = sum(p[1] for p in cc) / len(cc)

    angle = -yaw_deg
    rad = math.radians(angle)
    ch, cw = crop.shape[:2]
    rot_pts = []
    for px, py in [(0, 0), (cw, 0), (cw, ch), (0, ch)]:
        dx, dy = px - cx, py - cy
        rot_pts.append((cx + dx * math.cos(rad) - dy * math.sin(rad),
                        cy + dx * math.sin(rad) + dy * math.cos(rad)))
    rxs = [p[0] for p in rot_pts]
    rys = [p[1] for p in rot_pts]
    ox, oy = -min(rxs), -min(rys)
    nw, nh = int(max(rxs) - min(rxs)), int(max(rys) - min(rys))

    m = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
    m[0, 2] += ox
    m[1, 2] += oy
    rotated = cv2.warpAffine(crop, m, (nw, nh), flags=cv2.INTER_CUBIC,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
    nc = []
    for px, py in cc:
        dx, dy = px - cx, py - cy
        nc.append((cx + ox + dx * math.cos(rad) - dy * math.sin(rad),
                   cy + oy + dx * math.sin(rad) + dy * math.cos(rad)))

    mask = np.zeros((nh, nw), dtype=np.uint8)
    cv2.fillPoly(mask, [np.array(nc, dtype=np.int32)], 255)
    rotated[mask == 0] = (0, 0, 0)

    nxs = [int(p[0]) for p in nc]
    nys = [int(p[1]) for p in nc]
    buf = 20
    fx1, fy1 = max(0, min(nxs) - buf), max(0, min(nys) - buf)
    fx2, fy2 = min(nw, max(nxs) + buf), min(nh, max(nys) + buf)
    final = rotated[fy1:fy2, fx1:fx2]
    final_corners = [(int(p[0]) - fx1, int(p[1]) - fy1) for p in nc]
    return final, final_corners