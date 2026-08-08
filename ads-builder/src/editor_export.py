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


def rows_for(plan: Plan) -> list[dict[str, str]]:
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
            out.append({"Campaign": campaign.name, "Location": location})
        for location in campaign.excluded_locations:
            out.append({"Campaign": campaign.name, "Location": location,
                        "Criterion Type": "Campaign Negative"})

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

        for segment in campaign.audience_segments:
            out.append({"Campaign": campaign.name, "Audience segment": segment})

        for group in campaign.ad_groups:
            group_row = {
                "Campaign": campaign.name,
                "Ad Group": group.name,
                "Ad Group Status": group.status,
            }
            if group.max_cpc:
                group_row["Max CPC"] = f"{group.max_cpc:.2f}"
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


def write_editor_file(plan: Plan, out_dir: Path, data_dir: Path) -> Path:
    header = load_header(data_dir)
    known = set(header)
    rows = rows_for(plan)

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
