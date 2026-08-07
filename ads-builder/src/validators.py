"""Pre-flight checks.

Two severities. `error` means the build must not be exported — Google would
reject it, or it would quietly waste money. `warning` means a human should look
before posting.

The geo check is here rather than in the runbook on purpose: presence-or-interest
targeting is the most expensive default in the product and it should be
impossible to ship past it by accident.
"""

from .model import (
    MAX_KEYWORDS_PER_GROUP,
    MAX_DESCRIPTION,
    MAX_HEADLINE,
    MAX_KEYWORD_CHARS,
    MAX_KEYWORD_WORDS,
    MAX_PATH,
    RSA_MAX_DESCRIPTIONS,
    RSA_MAX_HEADLINES,
    RSA_MIN_DESCRIPTIONS,
    RSA_MIN_HEADLINES,
    Plan,
)


class Finding:
    def __init__(self, severity: str, where: str, message: str):
        self.severity = severity
        self.where = where
        self.message = message

    def __str__(self) -> str:
        return f"[{self.severity.upper():7}] {self.where}: {self.message}"


def validate(plan: Plan) -> list[Finding]:
    findings: list[Finding] = []

    def err(where: str, msg: str) -> None:
        findings.append(Finding("error", where, msg))

    def warn(where: str, msg: str) -> None:
        findings.append(Finding("warning", where, msg))

    if not plan.campaigns:
        err(plan.client_slug, "no campaigns were enabled — check `services` in the brief")

    seen_keywords: dict[tuple[str, str], str] = {}

    for campaign in plan.campaigns:
        where = campaign.name

        if campaign.location_target_type != "presence":
            err(where, "location targeting must be `presence`, not presence-or-interest")
        if not campaign.locations:
            err(where, "no geo targets — the campaign would serve nationally")
        if campaign.daily_budget <= 0:
            err(where, "daily budget is zero")
        if not campaign.ad_groups:
            err(where, "campaign has no ad groups")
        if not campaign.negatives:
            warn(where, "no campaign-level negatives attached")

        for group in campaign.ad_groups:
            gwhere = f"{campaign.name} > {group.name}"

            if not group.keywords:
                err(gwhere, "ad group has no keywords")
            if not group.ads:
                err(gwhere, "ad group has no ads")

            # The account this is modelled on runs 5-15 phrase keywords per ad
            # group and lets phrase match plus smart bidding find the long tail.
            # A big list is not thoroughness — it splits one query's data across
            # near-duplicates and starves all of them. See SPEC.md.
            if len(group.keywords) > MAX_KEYWORDS_PER_GROUP:
                warn(
                    gwhere,
                    f"{len(group.keywords)} keywords — the target is "
                    f"5-{MAX_KEYWORDS_PER_GROUP}. This blueprint is generating "
                    f"combinations rather than themes",
                )

            for keyword in group.keywords:
                if len(keyword.text) > MAX_KEYWORD_CHARS:
                    err(gwhere, f"keyword over {MAX_KEYWORD_CHARS} chars: {keyword.text!r}")
                if len(keyword.text.split()) > MAX_KEYWORD_WORDS:
                    err(gwhere, f"keyword over {MAX_KEYWORD_WORDS} words: {keyword.text!r}")

                # A keyword in two ad groups splits its own data and makes the
                # search terms report unreadable. Report it; don't silently drop.
                fingerprint = (keyword.text.lower(), keyword.match_type)
                if fingerprint in seen_keywords and seen_keywords[fingerprint] != gwhere:
                    warn(
                        gwhere,
                        f"duplicate of {keyword.text!r} [{keyword.match_type}] "
                        f"already in {seen_keywords[fingerprint]}",
                    )
                else:
                    seen_keywords[fingerprint] = gwhere

            for index, ad in enumerate(group.ads, start=1):
                awhere = f"{gwhere} > ad {index}"

                if not RSA_MIN_HEADLINES <= len(ad.headlines) <= RSA_MAX_HEADLINES:
                    err(
                        awhere,
                        f"{len(ad.headlines)} headlines — Google needs "
                        f"{RSA_MIN_HEADLINES}-{RSA_MAX_HEADLINES}",
                    )
                if not RSA_MIN_DESCRIPTIONS <= len(ad.descriptions) <= RSA_MAX_DESCRIPTIONS:
                    err(
                        awhere,
                        f"{len(ad.descriptions)} descriptions — Google needs "
                        f"{RSA_MIN_DESCRIPTIONS}-{RSA_MAX_DESCRIPTIONS}",
                    )

                for headline in ad.headlines:
                    if len(headline) > MAX_HEADLINE:
                        err(awhere, f"headline {len(headline)} chars: {headline!r}")
                for description in ad.descriptions:
                    if len(description) > MAX_DESCRIPTION:
                        err(awhere, f"description {len(description)} chars: {description!r}")
                for path in (ad.path1, ad.path2):
                    if path and len(path) > MAX_PATH:
                        err(awhere, f"path {len(path)} chars: {path!r}")

                if len(set(ad.headlines)) != len(ad.headlines):
                    warn(awhere, "duplicate headlines — Google will reject identical assets")
                if not ad.final_url.startswith("http"):
                    err(awhere, f"final URL is not absolute: {ad.final_url!r}")

    for message in plan.warnings:
        warn(plan.client_slug, message)

    return findings


def has_errors(findings: list[Finding]) -> bool:
    return any(f.severity == "error" for f in findings)
