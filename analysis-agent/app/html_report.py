from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import storage

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=select_autoescape(["html"]))


def render_html(report: dict, payload: dict, obj: dict, original_key: str | None) -> bytes:
    crops = []
    for crop in payload.get("crops_meta") or []:
        item = dict(crop)
        item["url"] = storage.public_url(crop.get("storage_key"))
        crops.append(item)
    view = dict(payload)
    view["crops_meta"] = crops
    html = env.get_template("report.html").render(
        report=report,
        payload=view,
        object=obj,
        original_url=storage.public_url(original_key),
    )
    return html.encode("utf-8")
