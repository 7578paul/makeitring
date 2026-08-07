#!/usr/bin/env python3
"""Local web UI for ads-builder.

    python app.py          then open http://localhost:8765

Standard library only — no framework to install, no build step. It binds to
localhost, so it is reachable from this machine and nowhere else. That is
deliberate: briefs contain client data and this has no authentication.
"""

import argparse
import io
import re
import webbrowser
import zipfile
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml

from src.compiler import BriefError, available_trades, compile_brief
from src.exporters import export_build_sheet, export_editor_csv
from src.ui_html import error_html, form_html, results_html
from src.validators import has_errors, validate

ROOT = Path(__file__).parent
BLUEPRINTS = ROOT / "blueprints"
OUT = ROOT / "out"


def blueprint_campaigns(trade: str) -> list[dict]:
    path = BLUEPRINTS / f"{trade}.yaml"
    if not path.exists():
        return []
    with path.open() as handle:
        return yaml.safe_load(handle).get("campaigns", [])


def parse_pairs(text: str) -> dict[str, str]:
    """`key = value` per line. Tolerates ':' as the separator too."""
    pairs: dict[str, str] = {}
    for line in (text or "").splitlines():
        if match := re.match(r"\s*([\w\-]+)\s*[=:]\s*(.+?)\s*$", line):
            pairs[match.group(1)] = match.group(2)
    return pairs


def parse_window(text: str) -> list[str] | None:
    """'07:00-19:00' -> ['07:00', '19:00']."""
    if match := re.match(r"\s*(\d{1,2}:\d{2})\s*[-–to]+\s*(\d{1,2}:\d{2})\s*$", text or ""):
        return [match.group(1), match.group(2)]
    return None


def lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def form_to_brief(form: dict[str, list[str]]) -> dict:
    """Turn posted fields into the same brief structure the YAML files use, so
    the UI and the CLI compile through identical code."""
    def one(key: str, default: str = "") -> str:
        return (form.get(key, [default])[0] or "").strip()

    cities = lines(one("cities"))
    region = one("region")
    business = one("business_name")
    slug = one("slug") or re.sub(r"[^a-z0-9]+", "-", business.lower()).strip("-") or "client"

    weights = {k: float(v) for k, v in parse_pairs(one("weights")).items()
               if re.match(r"^\d+(\.\d+)?$", v)}

    hours: dict = {"always": bool(form.get("always"))}
    if not hours["always"]:
        hours["open"] = {
            "mon_fri": parse_window(one("mon_fri")),
            "sat": parse_window(one("sat")),
            "sun": parse_window(one("sun")),
        }

    return {
        "trade": one("trade", "moving"),
        "client": {
            "slug": slug,
            "business_name": business,
            "website": one("website"),
            "phone": one("phone"),
            "currency": one("currency", "CAD"),
            "customer_id": one("customer_id"),
        },
        "services": form.get("services", []),
        "service_area": {
            "cities": cities,
            "targets": [f"{city}, {region}" if region else city for city in cities],
            "exclude": [],
        },
        "budget": {"monthly_total": float(one("monthly_total", "0") or 0), "weights": weights},
        "hours": hours,
        "positioning": {
            "offer": one("offer"),
            "min_job_value": one("min_job_value"),
            "brand_terms": lines(one("brand_terms")),
        },
        "landing_pages": {"default": one("default_url"), **parse_pairs(one("page_map"))},
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quieter console
        pass

    def _send(self, body: str, status: int = 200) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        query = parse_qs(url.query)

        if url.path == "/":
            trades = available_trades(BLUEPRINTS)
            trade = (query.get("trade", [trades[0] if trades else "moving"])[0])
            values = {k: v[0] for k, v in query.items() if k != "services"}
            if "services" in query:
                values["services"] = query["services"]
            self._send(form_html(trades, trade, blueprint_campaigns(trade), values))

        elif url.path == "/download":
            self._send_zip(query.get("dir", [""])[0])

        else:
            self._send(error_html("No such page."), 404)

    def _send_zip(self, directory: str) -> None:
        target = Path(directory).resolve()
        # Only ever serve from inside out/ — this process can read the whole disk.
        if not target.is_dir() or OUT.resolve() not in target.parents:
            self._send(error_html("That download is not available."), 400)
            return

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(target.iterdir()):
                if path.is_file():
                    archive.write(path, path.name)

        payload = buffer.getvalue()
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition",
                         f'attachment; filename="{target.parent.name}-{target.name}.zip"')
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/build":
            self._send(error_html("No such page."), 404)
            return

        length = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)

        try:
            brief = form_to_brief(form)
            plan = compile_brief(brief, BLUEPRINTS)
        except BriefError as exc:
            self._send(error_html(str(exc)), 400)
            return
        except Exception as exc:  # a bad blueprint should not kill the server
            self._send(error_html(f"{type(exc).__name__}: {exc}"), 500)
            return

        findings = validate(plan)
        out_dir = OUT / plan.client_slug / date.today().isoformat()
        export_build_sheet(plan, findings, out_dir)

        blocked = has_errors(findings)
        if not blocked:
            export_editor_csv(plan, out_dir)
            # Keep the brief next to its output so any build can be reproduced.
            (out_dir / "brief.yaml").write_text(
                yaml.safe_dump(brief, sort_keys=False, allow_unicode=True), encoding="utf-8"
            )

        self._send(results_html(plan, findings, str(out_dir.resolve()), blocked))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://localhost:{args.port}"
    print(f"ads-builder running at {url}\nCtrl-C to stop.")

    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
