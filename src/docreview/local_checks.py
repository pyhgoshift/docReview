from __future__ import annotations
import re
from collections import Counter

DATE_PATTERNS = [
    r"\b20\d{2}[./-]\d{1,2}[./-]\d{1,2}\b",
    r"\b20\d{2}년\s*\d{1,2}월(?:\s*\d{1,2}일)?",
]
MONEY_PATTERN = r"(?:₩|\$)?\s*\d[\d,]*(?:\.\d+)?\s*(?:원|만원|억원|달러|USD|KRW|%)"

def extract_facts(text: str) -> dict:
    dates = []
    for pattern in DATE_PATTERNS:
        dates.extend(re.findall(pattern, text))
    money = re.findall(MONEY_PATTERN, text, flags=re.IGNORECASE)
    years = re.findall(r"\b20\d{2}년?\b", text)
    return {
        "dates": list(dict.fromkeys(dates))[:80],
        "amounts_and_rates": list(dict.fromkeys(money))[:120],
        "years": list(dict.fromkeys(years))[:30],
    }

def repeated_sentences(text: str) -> list[dict]:
    sentences = [
        re.sub(r"\s+", " ", s).strip()
        for s in re.split(r"(?<=[.!?다요])\s+|\n+", text)
        if len(s.strip()) >= 20
    ]
    counts = Counter(sentences)
    return [
        {"sentence": sentence[:300], "count": count}
        for sentence, count in counts.most_common(20)
        if count > 1
    ]
