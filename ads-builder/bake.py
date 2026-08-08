#!/usr/bin/env python3
"""Bake the blueprints into a standalone HTML page.

    python bake.py

The browser version needs its own copy of the compiler in JavaScript, but it
must not have its own copy of the *blueprints* — those stay authored once, in
YAML, and are injected here. Re-run this after editing any blueprint, including
after regenerating one with extract.py.
"""

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parent
BLUEPRINTS = ROOT / "blueprints"
TEMPLATE = ROOT / "web" / "template.html"
OUTPUT = ROOT / "web" / "campaign-builder.html"


def main() -> int:
    blueprints = {}
    for path in sorted(BLUEPRINTS.glob("*.yaml")):
        with path.open() as handle:
            blueprints[path.stem] = yaml.safe_load(handle)
        print(f"  {path.stem}: {len(blueprints[path.stem].get('campaigns', []))} campaigns")

    if not blueprints:
        print("no blueprints found", file=sys.stderr)
        return 1

    negatives = []
    shared = BLUEPRINTS / "_shared" / "negatives-universal.txt"
    if shared.exists():
        for line in shared.read_text().splitlines():
            line = line.split("#")[0].strip()
            if line:
                negatives.append(line)

    headers = (ROOT / "data" / "editor_schema_headers.txt").read_text(
        encoding="utf-8").rstrip("\r\n").split("\t")
    print(f"  {len(headers)} Editor columns")

    html = TEMPLATE.read_text(encoding="utf-8")
    for token, value in (("__BLUEPRINTS__", blueprints), ("__NEGATIVES__", negatives),
                         ("__EDITOR_HEADERS__", headers)):
        if token not in html:
            print(f"template is missing {token}", file=sys.stderr)
            return 1
        # `</script>` inside a JSON string would close the block early.
        html = html.replace(token, json.dumps(value, ensure_ascii=False).replace("</", "<\\/"))

    OUTPUT.write_text(html, encoding="utf-8")
    size = OUTPUT.stat().st_size
    print(f"\n  {len(negatives)} shared negatives")
    print(f"wrote {OUTPUT} ({size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
