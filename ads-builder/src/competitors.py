"""Layer 2 of the negative wall: the competitor brand list, per market.

The inherited competitor wall is worthless for a new market — a Toronto list
does not contain a single Miami mover. So this layer has to be regenerated per
client or it does not exist for them at all.

Names come from Google Places (`searchText`), which is the supported way to ask
"who does this in this city". A scraper is cheaper and breaks; this is a
documented API and costs cents per market.

Nothing here is trusted blindly. Every generated negative is filtered against
the client's own brand and their own keywords using the same matcher the
pre-flight uses, because a competitor list is exactly where a term that blocks
your own traffic sneaks in — "Miami Movers" is both a competitor and a phrase
the client wants to rank for.
"""

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from .preflight import blocks, normalise

PLACES_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"

# Names too generic to block: they are what the client sells, not a brand.
GENERIC = {
    "moving", "movers", "mover", "move", "moves", "company", "companies", "co",
    "services", "service", "inc", "llc", "ltd", "corp", "group", "and", "the",
    "of", "a", "storage", "transport", "logistics", "van", "lines", "removals",
    "relocation", "relocations", "packing", "delivery", "solutions",
}


def search_places(query: str, *, api_key: str, max_results: int = 20,
                  timeout: int = 20) -> list[str]:
    """One Places text search. Returns business names."""
    body = json.dumps({"textQuery": query, "maxResultCount": max_results}).encode()
    request = urllib.request.Request(
        PLACES_ENDPOINT, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            # Ask only for the field we use — Places bills by field mask.
            "X-Goog-FieldMask": "places.displayName",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    return [p["displayName"]["text"] for p in payload.get("places", [])
            if p.get("displayName", {}).get("text")]


def harvest(cities: list[str], service_terms: list[str], *, api_key: str,
            per_query: int = 20) -> tuple[list[str], list[str]]:
    """Run `{service} {city}` across the market. Returns (names, problems)."""
    names: list[str] = []
    problems: list[str] = []

    for city in cities:
        for term in service_terms:
            query = f"{term} {city}"
            try:
                found = search_places(query, api_key=api_key, max_results=per_query)
                names.extend(found)
            except urllib.error.HTTPError as exc:
                problems.append(f"{query}: HTTP {exc.code} {exc.reason}")
            except Exception as exc:  # network, timeout, malformed payload
                problems.append(f"{query}: {type(exc).__name__} {exc}")

    return list(dict.fromkeys(names)), problems


def is_brandable(name: str, cities: list[str] | None = None) -> bool:
    """Does this name contain anything distinctive enough to block?

    A city plus trade words is not a brand — "Miami Moving Company" is a
    description of every mover in Miami, and it is also a search the client
    wants to win. "Two Men and a Truck" is a brand. The test is whether
    anything survives removing both the trade vocabulary and the place names.
    """
    place_words = set()
    for city in (cities or []):
        place_words.update(normalise(city).split())

    words = normalise(name).split()
    distinctive = [w for w in words if w not in GENERIC and w not in place_words]
    return bool(distinctive) and len(words) > 1


def variants(name: str) -> list[str]:
    """The misspellings people actually type.

    Taken from the patterns in the live account, which carries "1800 steemer",
    "1 800 steamer" and "chem dry" as two words alongside the real names.
    """
    base = normalise(name)
    out = {base}

    swaps = [
        (r"\btwo\b", "2"), (r"\bthree\b", "3"), (r"\bfour\b", "4"), (r"\bone\b", "1"),
        (r"\b2\b", "two"), (r"\b3\b", "three"),
        (r"\band\b", "&"), (r"&", "and"),
    ]
    for pattern, replacement in swaps:
        swapped = re.sub(pattern, replacement, base)
        if swapped != base:
            out.add(normalise(swapped))

    out.add(base.replace(" ", ""))          # "twomenandatruck"
    out.add(base.replace("-", " "))
    out.add(re.sub(r"['’]", "", base))      # "bob's" -> "bobs"

    return [v for v in dict.fromkeys(out) if v and len(v) > 3]


def to_negatives(names: list[str], *, client_keywords: list[str],
                 brand_terms: list[str], cities: list[str]) -> tuple[list[str], list[str]]:
    """Turn business names into exact negatives, dropping anything that would
    block the client. Returns (negatives, rejected-with-reason)."""
    negatives: list[str] = []
    rejected: list[str] = []
    seen: set[str] = set()

    own = [normalise(k) for k in client_keywords] + \
          [normalise(b) for b in brand_terms] + [normalise(c) for c in cities]

    for name in names:
        if not is_brandable(name, cities):
            rejected.append(f'"{name}" — a place plus trade words, not a brand: the client wants this search')
            continue

        for variant in variants(name):
            if variant in seen:
                continue
            seen.add(variant)

            hit = next((t for t in own if blocks(variant, "exact", t)), None)
            if hit:
                rejected.append(f'"{variant}" — would block the client\'s own "{hit}"')
            else:
                negatives.append(variant)

    return negatives, rejected


def build_layer2(*, cities: list[str], service_terms: list[str],
                 client_keywords: list[str], brand_terms: list[str],
                 api_key: str | None = None,
                 names_file: Path | None = None) -> dict:
    """Layer 2 end to end.

    `names_file` takes a list of business names already gathered — pasted from a
    Maps search, or a saved harvest — so the whole thing is usable and testable
    without an API key.
    """
    problems: list[str] = []

    if names_file and names_file.exists():
        names = [line.strip() for line in names_file.read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.startswith("#")]
        source = f"names file ({names_file.name})"
    elif api_key:
        names, problems = harvest(cities, service_terms, api_key=api_key)
        source = "Google Places API"
    else:
        return {
            "negatives": [], "rejected": [], "names": [], "problems": [
                "no competitor source: set GOOGLE_PLACES_API_KEY or supply a names file"
            ],
            "source": "none",
        }

    negatives, rejected = to_negatives(
        names, client_keywords=client_keywords, brand_terms=brand_terms, cities=cities)

    return {"negatives": negatives, "rejected": rejected, "names": names,
            "problems": problems, "source": source}


def api_key_from_env() -> str | None:
    return os.environ.get("GOOGLE_PLACES_API_KEY") or None
