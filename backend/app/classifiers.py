import re
from typing import Protocol

from app.catalog import TOPICS
from app.models import Region


class RegionClassifier(Protocol):
    def classify(self, title: str, regions: list[Region]) -> list[int]: ...


class RuleBasedRegionClassifier:
    version = "rules-v2"

    def classify(self, title: str, regions: list[Region]) -> list[int]:
        # Accept common Korean particles after place names while rejecting compounds
        # such as 경기침체 and 서울대.
        particles = r"(?:시|군|구|도)?(?:에서는|에서|으로|로|에는|에게|부터|까지|은|는|이가|이|가|을|를|에|의|과|와|도|만)?"
        return [
            r.id
            for r in regions
            if any(
                re.search(
                    r"(?<![가-힣A-Za-z])" + re.escape(a) + particles + r"(?![가-힣A-Za-z])",
                    title,
                )
                for a in r.aliases
            )
        ]


class TopicClassifier(Protocol):
    def classify(self, title: str, categories: list[str]) -> tuple[list[str], str]: ...


class RuleBasedTopicClassifier:
    version = "rules-v1"

    def classify(self, title: str, categories: list[str]) -> tuple[list[str], str]:
        official = [
            slug for slug, (name, _) in TOPICS.items() if slug in categories or name in categories
        ]
        if official:
            return official, "source_category"
        return [
            slug
            for slug, (_, words) in TOPICS.items()
            if any(word.casefold() in title.casefold() for word in words)
        ], "title_keyword"
