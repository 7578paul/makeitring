"""The intermediate representation.

Everything upstream (briefs, blueprints) compiles down to a Plan. Everything
downstream (Editor CSV today, the Ads API later) reads a Plan and nothing else.
That separation is the whole reason adding the API backend later is cheap.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

# {KeyWord:Fallback} / {LOCATION(City):Fallback} / {CUSTOMIZER.Name:Fallback}
_INSERTION = re.compile(r"\{[A-Za-z_]+(?:\([^)]*\))?(?::(?P<fallback>[^}]*))?\}")

# Google's limits. Enforced in validators, restated here because the exporters
# assume they already hold.
MAX_HEADLINE = 30
MAX_DESCRIPTION = 90
MAX_PATH = 15
MAX_KEYWORD_CHARS = 80
MAX_KEYWORD_WORDS = 10
RSA_MIN_HEADLINES = 3
RSA_MAX_HEADLINES = 15
RSA_MIN_DESCRIPTIONS = 2
RSA_MAX_DESCRIPTIONS = 4

def display_length(text: str) -> int:
    """Length as Google counts it.

    `{KeyWord:Moving Papa}` and `{LOCATION(City):Your Area}` are insertion
    tokens: what has to fit the 30-character limit is the fallback that shows
    when insertion cannot happen, not the literal token. Measuring the raw
    string drops precisely the headlines that make these ads perform.
    """
    return len(_INSERTION.sub(lambda m: m.group("fallback") or "", text or ""))


# Not a Google limit — a strategy limit, taken from the account this tool is
# modelled on. See SPEC.md § what v0 got wrong, row 1.
MAX_KEYWORDS_PER_GROUP = 15


@dataclass
class Keyword:
    text: str
    match_type: str  # broad | phrase | exact
    final_url: Optional[str] = None


@dataclass
class NegativeKeyword:
    text: str
    match_type: str
    source: str = ""  # which theme or file put it here, for the build sheet


@dataclass
class ResponsiveSearchAd:
    headlines: list[str]
    descriptions: list[str]
    final_url: str
    path1: str = ""
    path2: str = ""


@dataclass
class Asset:
    """Sitelinks, callouts, snippets and the call asset.

    Google reports a Search campaign without these as underperforming, and the
    source account runs all of them on every campaign. Ads without them lose
    the extra lines of real estate on the results page.
    """
    kind: str                      # callout | sitelink | snippet | call
    text: str = ""
    description1: str = ""
    description2: str = ""
    final_url: str = ""
    header: str = ""
    values: list[str] = field(default_factory=list)
    phone: str = ""
    country: str = ""


@dataclass
class AdGroup:
    name: str
    keywords: list[Keyword] = field(default_factory=list)
    ads: list[ResponsiveSearchAd] = field(default_factory=list)
    max_cpc: Optional[float] = None
    status: str = "Paused"


@dataclass
class ScheduleSlot:
    day: str  # Monday .. Sunday
    start: str  # HH:MM
    end: str


@dataclass
class Campaign:
    key: str
    name: str
    market: str = ""
    campaign_type: str = "Search"
    daily_budget: float = 0.0
    bid_strategy: str = "Maximize conversions"
    max_cpc: Optional[float] = None
    status: str = "Paused"
    networks: str = "Google search"
    language: str = "en"   # Editor rejects "English" — it wants the code
    locations: list[str] = field(default_factory=list)
    excluded_locations: list[str] = field(default_factory=list)
    location_target_type: str = "Location of presence"
    location_exclusion_type: str = "Location of presence"
    target_cpa: Optional[float] = None
    tracking_template: str = ""
    ad_rotation: str = "Optimize for clicks"
    budget_type: str = "Daily"
    schedule: list[ScheduleSlot] = field(default_factory=list)
    ad_groups: list[AdGroup] = field(default_factory=list)
    negatives: list[NegativeKeyword] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)
    # Attached in Observation only: collect the data now, bid on it later.
    audience_segments: list[str] = field(default_factory=list)
    # Performance Max only: one asset group dict (headlines, long_headlines,
    # descriptions, final_url, audience_signal). None for Search campaigns.
    asset_group: Optional[dict] = None

    @property
    def keyword_count(self) -> int:
        return sum(len(g.keywords) for g in self.ad_groups)


@dataclass
class Plan:
    client_slug: str
    business_name: str
    trade: str
    blueprint_version: str
    currency: str
    monthly_budget: float
    campaigns: list[Campaign] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    @property
    def daily_budget_total(self) -> float:
        return sum(c.daily_budget for c in self.campaigns)
