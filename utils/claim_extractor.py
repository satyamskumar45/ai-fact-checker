import re


CLAIM_KEYWORDS = {
    "acquired",
    "announced",
    "based",
    "created",
    "increase",
    "decrease",
    "founded",
    "growth",
    "launched",
    "located",
    "rate",
    "gdp",
    "revenue",
    "profit",
    "loss",
    "market",
    "inflation",
    "unemployment",
    "population",
    "million",
    "billion",
    "trillion",
    "valuation",
    "users",
}

OPINION_KEYWORDS = {
    "best",
    "better",
    "could",
    "effective",
    "important",
    "likely",
    "may",
    "might",
    "popular",
    "should",
    "significant",
    "successful",
    "worst",
}

FACT_VERBS = {
    "are",
    "had",
    "has",
    "have",
    "is",
    "was",
    "were",
    "will",
}

IRRELEVANT_PATTERNS = (
    r"^page\s+\d+",
    r"^table\s+of\s+contents$",
    r"^confidential$",
    r"^copyright\b",
    r"^figure\s+\d+",
)


def split_sentences(text):
    """Split text into simple sentence-like chunks."""
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    return re.split(r"(?<=[.!?])\s+", normalized)


def has_fact_signal(sentence):
    """Return True when a sentence looks like a factual claim worth checking."""
    lower_sentence = sentence.lower()
    has_number = bool(re.search(r"\d|%|[$₹€£]|\b(19|20)\d{2}\b", sentence))
    has_keyword = any(keyword in lower_sentence for keyword in CLAIM_KEYWORDS)
    has_opinion_signal = any(keyword in lower_sentence for keyword in OPINION_KEYWORDS)
    has_fact_verb = any(re.search(rf"\b{verb}\b", lower_sentence) for verb in FACT_VERBS)
    has_named_subject = bool(re.search(r"\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?\b", sentence))
    return has_number or has_keyword or has_opinion_signal or (has_fact_verb and has_named_subject)


def is_relevant_claim(sentence):
    """Filter PDF artifacts and fragments that are unlikely to be useful claims."""
    clean_sentence = sentence.strip()
    lower_sentence = clean_sentence.lower()

    if len(clean_sentence) < 20 or len(clean_sentence.split()) < 4:
        return False

    if any(re.search(pattern, lower_sentence) for pattern in IRRELEVANT_PATTERNS):
        return False

    if clean_sentence.count(":") > 2 and not re.search(r"\d|%", clean_sentence):
        return False

    return has_fact_signal(clean_sentence)


def extract_claims(text):
    try:
        sentences = text.split(".")
        claims = []

        keywords = ["increase", "population", "gdp", "energy", "ai"]

        for s in sentences:
            s = s.strip()

            if len(s) < 20:  # ❗ ignore small/invalid lines
                continue

            if any(char.isdigit() for char in s) or any(k in s.lower() for k in keywords):
                claims.append(s)

        return claims[:10]
    except Exception:
        return []
