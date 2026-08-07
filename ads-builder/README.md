# ads-builder

Turns a client brief plus a trade blueprint into an importable Google Ads
account structure. See [PLAN.md](PLAN.md) for the architecture and roadmap.

## Run it

```bash
pip install -r requirements.txt
python build.py clients/example-mover/brief.yaml
```

Writes to `out/<slug>/<date>/`:

| File | What it is |
| --- | --- |
| `build-sheet.md` | The human-readable review doc. **Approve this, not the CSVs.** |
| `01-campaigns.csv` … `07-ads-rsa.csv` | Google Ads Editor bulk import |

Validation errors block CSV export entirely. `--force` overrides for inspection;
it does not make the build safe to import.

## Adding a client

Copy `clients/example-mover/brief.yaml`, fill it in, run it. Required fields are
enforced — a missing field fails the build with the field name rather than
silently defaulting.

## Adding a trade

Copy `blueprints/moving.yaml`. The compiler is trade-agnostic; everything
specific to a trade lives in the blueprint. Add the trade code to `TRADE_CODES`
in `src/compiler.py` so campaign names get the right prefix.

## Status

v0. Two things are known-provisional and both are fixed by one input — a Google
Ads Editor export from the live account:

1. **`blueprints/moving.yaml` is a straw man.** It has the right *shape* and
   encodes the documented strategy, but the keywords and copy are placeholders.
2. **Editor CSV column headers are unverified.** They are defined once in
   `COLUMNS` in `src/exporters.py`. Editor matches headers on exact text and
   they vary by version and account language, so expect the first import to
   need a mapping pass.

## Moving this to its own repo

Scaffolded inside the website repo only because that is where the session had
push access. It is self-contained and has no ties to the site:

```bash
git subtree split --prefix=ads-builder -b ads-builder-only
mkdir ../ads-builder && cd ../ads-builder && git init
git pull ../makeitring ads-builder-only
```

It is listed in the site's `.assetsignore`, so it is never published to
makeitring.co while it lives here.
