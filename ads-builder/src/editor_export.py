"""Google Ads Editor import file.

Editor's native format is **UTF-16 with a BOM, tab separated**, with a 312
column header. A UTF-8 or comma-separated file either fails to import or
garbles silently, which is worse. The header is not reconstructed here — it is
read verbatim from `data/editor_schema_headers.txt`, taken from a real export,
and every row is padded to its full width with blanks.

One row per entity, with the row's type implied by which cells are filled.
That is how Editor writes its own exports, and how it reads them back.
"""

import csv
from pathlib import Path

from .model import RSA_MAX_DESCRIPTIONS, RSA_MAX_HEADLINES, Plan

ENCODING = "utf-16"          # Python writes UTF-16LE with a BOM, which is what Editor emits
DELIMITER = "\t"

MATCH_LABELS = {"broad": "Broad", "phrase": "Phrase", "exact": "Exact"}
NEGATIVE_LABELS = {
    "broad": "Campaign Negative Broad",
    "phrase": "Campaign Negative Phrase",
    "exact": "Campaign Negative Exact",
}


def load_geo_ids(data_dir: Path) -> dict[str, str]:
    """Google's geo criterion IDs, keyed by the location name Editor shows.

    Without an ID a location imports as "unresolved" — Editor cannot tell which
    Miami you mean until it asks Google. Supplying the ID makes it exact and
    removes the warning. The shipped file is harvested from the source account;
    a market it does not cover needs Google's published geotargets CSV.
    """
    path = data_dir / "geo-targets.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {(row["Location"] or "").strip(): (row["ID"] or "").strip()
                for row in csv.DictReader(handle) if row.get("Location")}


def load_header(data_dir: Path) -> list[str]:
    text = (data_dir / "editor_schema_headers.txt").read_text(encoding="utf-8")
    return text.rstrip("\r\n").split(DELIMITER)


def clean(value, *, keep_newlines: bool = False) -> str:
    """A tab or newline inside a cell would shift every later column.

    Structured snippets are the exception: Editor expects their values newline
    separated within a single quoted cell, which the CSV writer quotes for us.
    """
    if value is None:
        return ""
    text = str(value).replace("\t", " ")
    if keep_newlines:
        return "\n".join(line.strip() for line in text.split("\n") if line.strip())
    return " ".join(text.split())


def rows_for(plan: Plan, geo_ids: dict[str, str] | None = None,
             images: list[str] | None = None) -> list[dict[str, str]]:
    """Flatten the plan into Editor rows, in the order Editor expects to meet
    them: a campaign before its ad groups, an ad group before its keywords."""
    out: list[dict[str, str]] = []

    for campaign in plan.campaigns:
        row = {
            "Campaign": campaign.name,
            "Campaign Type": campaign.campaign_type,
            "Networks": campaign.networks,
            "Budget": f"{campaign.daily_budget:.2f}",
            "Budget type": campaign.budget_type,
            "Languages": campaign.language,
            "Bid Strategy Type": campaign.bid_strategy,
            "Ad rotation": campaign.ad_rotation,
            "Targeting method": campaign.location_target_type,
            "Exclusion method": campaign.location_exclusion_type,
            "Campaign Status": campaign.status,
        }
        if campaign.target_cpa:
            row["Target CPA"] = f"{campaign.target_cpa:.2f}"
        if campaign.tracking_template:
            row["Tracking template"] = campaign.tracking_template
        out.append(row)

        for location in campaign.locations:
            row = {"Campaign": campaign.name, "Location": location}
            if geo_id := (geo_ids or {}).get(location):
                row["ID"] = geo_id
            out.append(row)
        for location in campaign.excluded_locations:
            row = {"Campaign": campaign.name, "Location": location,
                   "Criterion Type": "Campaign Negative"}
            if geo_id := (geo_ids or {}).get(location):
                row["ID"] = geo_id
            out.append(row)

        for slot in campaign.schedule:
            out.append({"Campaign": campaign.name,
                        "Ad Schedule": f"{slot.day}, {slot.start}, {slot.end}"})

        for negative in campaign.negatives:
            out.append({
                "Campaign": campaign.name,
                "Keyword": negative.text,
                "Criterion Type": NEGATIVE_LABELS.get(negative.match_type,
                                                      NEGATIVE_LABELS["phrase"]),
                "Status": "Enabled",
            })

        for asset in campaign.assets:
            if asset.kind == "callout":
                out.append({"Campaign": campaign.name, "Callout text": asset.text})
            elif asset.kind == "sitelink":
                row = {"Campaign": campaign.name, "Link Text": asset.text,
                       "Final URL": asset.final_url}
                if asset.description1:
                    row["Description Line 1"] = asset.description1
                if asset.description2:
                    row["Description Line 2"] = asset.description2
                out.append(row)
            elif asset.kind == "snippet":
                out.append({"Campaign": campaign.name, "Header": asset.header,
                            "Snippet Values": "\n".join(asset.values)})
            elif asset.kind == "call":
                out.append({"Campaign": campaign.name, "Phone Number": asset.phone,
                            "Country of Phone": asset.country,
                            "Conversion Action": "Use account settings"})

        for image in (images or []):
            out.append({"Campaign": campaign.name, "Image": image,
                        "Asset name": Path(image).stem})

        for segment in campaign.audience_segments:
            out.append({"Campaign": campaign.name, "Audience segment": segment})

        for group in campaign.ad_groups:
            group_row = {
                "Campaign": campaign.name,
                "Ad Group": group.name,
                "Ad Group Status": group.status,
            }
            # Editor wants a bid even under smart bidding, where it is ignored.
            # The source account parks every ad group at 0.01 — low enough that
            # it cannot overspend if smart bidding is ever switched off.
            group_row["Max CPC"] = f"{group.max_cpc:.2f}" if group.max_cpc else "0.01"
            out.append(group_row)

            for keyword in group.keywords:
                out.append({
                    "Campaign": campaign.name,
                    "Ad Group": group.name,
                    "Keyword": keyword.text,
                    "Criterion Type": MATCH_LABELS.get(keyword.match_type, "Phrase"),
                    "Status": group.status,
                    "Final URL": keyword.final_url or "",
                })

            for ad in group.ads:
                ad_row = {
                    "Campaign": campaign.name,
                    "Ad Group": group.name,
                    "Ad type": "Responsive search ad",
                    "Final URL": ad.final_url,
                    "Path 1": ad.path1,
                    "Path 2": ad.path2,
                    "Status": group.status,
                }
                for index, headline in enumerate(ad.headlines[:RSA_MAX_HEADLINES], start=1):
                    ad_row[f"Headline {index}"] = headline
                for index, description in enumerate(ad.descriptions[:RSA_MAX_DESCRIPTIONS], start=1):
                    ad_row[f"Description {index}"] = description
                out.append(ad_row)

    return out


def write_editor_file(plan: Plan, out_dir: Path, data_dir: Path,
                      brief: dict | None = None) -> Path:
    header = load_header(data_dir)
    known = set(header)
    geo_ids = load_geo_ids(data_dir)
    images = copy_images(brief or {}, out_dir)
    if images:
        print(f"  {len(images)} photo(s) copied for image assets")
    rows = rows_for(plan, geo_ids, images)

    unresolved = [loc for c in plan.campaigns for loc in c.locations if loc not in geo_ids]
    if unresolved:
        print(f"  note: {len(set(unresolved))} location(s) have no Google geo ID and will "
              f"import as unresolved until posted: {', '.join(sorted(set(unresolved))[:3])}"
              f"{' ...' if len(set(unresolved)) > 3 else ''}")

    # A column we invent is a column Editor ignores — better to know now.
    unknown = {key for row in rows for key in row} - known
    if unknown:
        raise ValueError(f"columns not in the Editor schema: {sorted(unknown)}")

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "campaigns_editor_import.csv"

    with path.open("w", encoding=ENCODING, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, delimiter=DELIMITER,
                                restval="", extrasaction="ignore",
                                lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: clean(value, keep_newlines=(key == "Snippet Values"))
                             for key, value in row.items()})

    return path


# Google's image asset rules. A file that breaks these imports as an error
# rather than being quietly ignored, so it is worth failing here instead.
MIN_IMAGE_PX = 300
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def image_size(data: bytes) -> tuple[int, int] | None:
    """Width and height from the file's own header. PNG and JPEG only, which is
    what Google accepts, and no dependency for something this small."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        return (int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big"))

    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            # SOF0-SOF15, excluding the non-frame markers in that range
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                return (int.from_bytes(data[i + 7:i + 9], "big"),
                        int.from_bytes(data[i + 5:i + 7], "big"))
            i += 2 + int.from_bytes(data[i + 2:i + 4], "big")
    return None


def check_image(path: Path) -> str | None:
    """Return why this file cannot be used, or None if it is fine."""
    data = path.read_bytes()
    if len(data) > MAX_IMAGE_BYTES:
        return f"{len(data) / 1024 / 1024:.1f} MB — over Google's 5 MB limit"

    size = image_size(data)
    if size is None:
        return "not a readable JPEG or PNG"

    width, height = size
    if width < MIN_IMAGE_PX or height < MIN_IMAGE_PX:
        return f"{width}x{height} — Google needs at least {MIN_IMAGE_PX}x{MIN_IMAGE_PX}"
    return None


def copy_images(brief: dict, out_dir: Path) -> list[str]:
    """Copy the client's photos next to the CSV and return their relative paths.

    Editor resolves image assets by path relative to the import file — the way
    the source export ships an images/ folder beside data.csv. Photos have to
    come from the client; nothing here can invent them.
    """
    import shutil

    sources = (brief.get("assets", {}) or {}).get("images") or []
    if not sources:
        return []

    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []

    for source in sources:
        path = Path(source).expanduser()
        if not path.is_file():
            print(f"  photo skipped, file not found — {source}")
            continue
        if problem := check_image(path):
            # Emitting the row anyway would put a red error in front of whoever
            # imports it, for a file they cannot fix from there.
            print(f"  photo skipped, {problem} — {path.name}")
            continue
        target = images_dir / path.name
        shutil.copy2(path, target)
        copied.append(f"images/{path.name}")

    return copied


def write_shared_negatives(plan: Plan, out_dir: Path) -> Path:
    """The negative wall as its own file, for Tools > Shared library import."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "shared_negative_list.csv"

    seen: set[tuple[str, str]] = set()
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Keyword", "Match type"])
        for campaign in plan.campaigns:
            for negative in campaign.negatives:
                key = (negative.text.lower(), negative.match_type)
                if key not in seen:
                    seen.add(key)
                    writer.writerow([negative.text, negative.match_type.title()])

    return path
