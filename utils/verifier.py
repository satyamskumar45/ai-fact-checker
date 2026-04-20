import hashlib
import re
from difflib import SequenceMatcher

import requests


SEARCH_ENDPOINT = "https://api.duckduckgo.com/"

NUMERIC_PATTERN = re.compile(
    r"(\$|₹|€|£)?\s?\d{1,3}(,\d{3})*(\.\d+)?\s?(%|percent|percentage|million|billion|trillion|crore|lakh|k|m|bn)?|"
    r"\b(19|20)\d{2}\b|\b(q[1-4]|fy)\s?\d{2,4}\b",
    re.IGNORECASE,
)
STATISTIC_TERMS = {
    "population",
    "gdp",
    "inflation",
    "revenue",
    "profit",
    "loss",
    "growth",
    "market share",
    "unemployment",
    "rate",
    "percentage",
    "valuation",
    "users",
    "sales",
}
OPINION_TERMS = {
    "best",
    "worst",
    "should",
    "could",
    "might",
    "may",
    "believe",
    "think",
    "feel",
    "likely",
    "unlikely",
    "better",
    "worse",
    "important",
    "significant",
    "successful",
    "popular",
    "effective",
    "innovative",
    "leading",
}
FACT_TERMS = {
    "is",
    "are",
    "was",
    "were",
    "has",
    "have",
    "founded",
    "launched",
    "created",
    "announced",
    "reported",
    "located",
    "based",
    "released",
    "acquired",
    "merged",
}

KNOWN_FACTS = [
    {
        "label": "France capital",
        "patterns": [r"\bparis\b.*\bcapital\b.*\bfrance\b", r"\bcapital\b.*\bfrance\b.*\bparis\b"],
        "evidence": "Paris is the capital city of France.",
        "domain": "geography",
    },
    {
        "label": "Earth shape",
        "patterns": [r"\bearth\b.*\bround\b", r"\bearth\b.*\bspherical\b", r"\bearth\b.*\boblate\b"],
        "evidence": "Earth is an oblate spheroid, commonly simplified as round.",
        "domain": "science",
    },
    {
        "label": "Water boiling point",
        "patterns": [r"\bwater\b.*\bboils\b.*\b100\b.*\b(c|celsius|degree)"],
        "evidence": "At standard sea-level pressure, pure water boils at about 100 degrees Celsius.",
        "domain": "science",
    },
    {
        "label": "Sun classification",
        "patterns": [r"\bsun\b.*\bstar\b"],
        "evidence": "The Sun is a star at the center of the Solar System.",
        "domain": "science",
    },
    {
        "label": "Human heart",
        "patterns": [r"\bhuman(s)?\b.*\bone\b.*\bheart\b", r"\bhuman(s)?\b.*\b1\b.*\bheart\b"],
        "evidence": "A typical human has one heart.",
        "domain": "biology",
    },
    {
        "label": "Global population band",
        "patterns": [
            r"\b(world|global|earth)\b.*\bpopulation\b.*\b(8|eight)\b.*\bbillion\b",
            r"\bpopulation\b.*\b(world|global|earth)\b.*\b(8|eight)\b.*\bbillion\b",
        ],
        "evidence": "Recent global population estimates are in the range of roughly eight billion people.",
        "domain": "population",
    },
]

KNOWN_CONTRADICTIONS = [
    {
        "label": "Flat Earth",
        "patterns": [r"\bearth\b.*\bflat\b"],
        "evidence": "This contradicts scientific observation and measurement showing Earth is an oblate spheroid.",
        "domain": "science",
    },
    {
        "label": "Geocentric solar system",
        "patterns": [r"\bsun\b.*\brevolves\b.*\bearth\b", r"\bsun\b.*\borbits\b.*\bearth\b"],
        "evidence": "Earth orbits the Sun; the Sun does not orbit Earth in the solar-system model.",
        "domain": "science",
    },
    {
        "label": "Human hearts",
        "patterns": [r"\bhuman(s)?\b.*\bthree\b.*\bhearts\b", r"\bhuman(s)?\b.*\b3\b.*\bhearts\b"],
        "evidence": "A typical human has one heart, not three.",
        "domain": "biology",
    },
]

REASONING_TEMPLATES = {
    "Verified": [
        "The claim aligns with a stable knowledge pattern for {topic}, and the wording does not introduce a conflicting qualifier.",
        "This matches a widely accepted {topic} fact, so the system can verify it with high confidence.",
        "The statement maps cleanly to an established {topic} reference pattern.",
    ],
    "Inaccurate": [
        "The claim is plausible but needs authoritative validation before it can be treated as verified.",
        "The statement contains checkable signals, but the available evidence is not strong enough for a verified label.",
        "This claim needs source-level confirmation because the wording or figures may vary by source and date.",
    ],
    "False": [
        "The claim contradicts well-established {topic} consensus and matches a known contradiction pattern.",
        "This conflicts with a stable reference fact in {topic}, so it is classified as false.",
        "The statement is inconsistent with accepted {topic} evidence and can be rejected by rule-based checks.",
    ],
}

EVIDENCE_TEMPLATES = {
    "Statistic": [
        "The claim includes numerical or time-bound data. Exact values should be checked against primary datasets because figures can change by reporting period.",
        "This is a measurement-style claim. Comparable reports may show similar directionality, but the exact number requires an authoritative source.",
        "The system detected quantitative language, so it treats the claim as data-sensitive rather than making a hard contradiction call.",
    ],
    "Fact": [
        "The claim is phrased as a factual statement and was evaluated against known reference patterns and lightweight evidence matching.",
        "The system checked whether the statement resembles a stable fact, a known contradiction, or an unsupported assertion.",
        "This was assessed as a general factual claim using pattern matching, keyword context, and available evidence overlap.",
    ],
    "Opinion": [
        "The wording contains subjective or vague language, which makes it unsuitable for direct factual verification without clearer criteria.",
        "The statement reads more like an interpretation or judgement than a claim with a single verifiable truth value.",
        "This needs a more specific benchmark or source before it can be verified as a factual assertion.",
    ],
}


def classify_claim(claim):
    """Classify a claim as Statistic, Fact, or Opinion."""
    normalized = (claim or "").strip()
    lower_claim = normalized.lower()

    if not normalized or len(normalized.split()) < 3:
        return "Opinion"

    if NUMERIC_PATTERN.search(normalized) or any(term in lower_claim for term in STATISTIC_TERMS):
        return "Statistic"

    if any(re.search(rf"\b{re.escape(term)}\b", lower_claim) for term in OPINION_TERMS):
        return "Opinion"

    return "Fact"


def analyze_claim(claim, claim_type=None):
    """Extract lightweight signals used by the verification and explanation stages."""
    normalized = re.sub(r"\s+", " ", (claim or "")).strip()
    lower_claim = normalized.lower()
    claim_type = claim_type or classify_claim(normalized)

    topics = sorted(term for term in STATISTIC_TERMS if term in lower_claim)
    opinion_signals = sorted(term for term in OPINION_TERMS if re.search(rf"\b{re.escape(term)}\b", lower_claim))
    fact_signals = sorted(term for term in FACT_TERMS if re.search(rf"\b{re.escape(term)}\b", lower_claim))
    numbers = re.findall(NUMERIC_PATTERN, normalized)

    return {
        "claim": normalized,
        "type": claim_type,
        "lower": lower_claim,
        "tokens": _tokenize(normalized),
        "topics": topics,
        "opinion_signals": opinion_signals,
        "fact_signals": fact_signals,
        "has_number": bool(numbers),
        "has_money": bool(re.search(r"[$₹€£]", normalized)),
        "has_date": bool(re.search(r"\b(19|20)\d{2}\b|\b(q[1-4]|fy)\s?\d{2,4}\b", normalized, re.IGNORECASE)),
        "word_count": len(normalized.split()),
        "fingerprint": int(hashlib.sha256(normalized.encode("utf-8")).hexdigest(), 16) if normalized else 0,
    }


def get_confidence(status, claim, analysis=None, match_score=0, matched_pattern=None):
    """Return High, Medium, or Low based on decision strength and claim context."""
    analysis = analysis or analyze_claim(claim)

    if matched_pattern and status in {"Verified", "False"}:
        return "High"

    if analysis["type"] == "Statistic":
        if status == "Verified" and ("population" in analysis["topics"] or match_score >= 0.72):
            return "Medium"
        if "gdp" in analysis["topics"] or "population" in analysis["topics"]:
            return "Medium"
        if any(topic in analysis["topics"] for topic in {"growth", "rate", "percentage"}) and match_score >= 0.35:
            return "Medium"
        return "Low"

    if status == "Verified" and match_score >= 0.6:
        return "Medium"

    if status == "False":
        return "Medium"

    if analysis["type"] == "Opinion":
        return "Low"

    if analysis["fact_signals"] and analysis["word_count"] >= 6:
        return "Medium"

    return "Low"


def generate_reasoning(claim, claim_type, status, analysis=None, context=None):
    """Generate varied, context-aware reasoning for the final result."""
    analysis = analysis or analyze_claim(claim, claim_type)
    context = context or {}
    topic = context.get("topic") or _primary_topic(analysis)
    template = _pick_template(REASONING_TEMPLATES[status], analysis["fingerprint"])

    if claim_type == "Statistic" and status == "Inaccurate":
        if "gdp" in analysis["topics"]:
            return "This GDP-related claim depends on reporting period, currency basis, and data source, so it is marked Inaccurate until checked against an official dataset."
        if "population" in analysis["topics"]:
            return "This population claim is numerical and may be broadly plausible, but exact figures shift over time and require a current demographic source."
        if any(topic in analysis["topics"] for topic in {"growth", "rate", "percentage", "users", "revenue"}):
            return "This claim includes performance or growth metrics that can vary by timeframe, so the system avoids a hard false label without primary validation."
        return "This claim includes numerical data but lacks real-time authoritative validation, so it is marked as Inaccurate rather than False."

    if claim_type == "Opinion":
        signal = analysis["opinion_signals"][0] if analysis["opinion_signals"] else "subjective"
        return f"The wording uses {signal!r} language, which makes the statement judgement-based rather than directly verifiable."

    return template.format(topic=topic)


def generate_explanation(claim, claim_type, status, analysis=None, context=None):
    """Create evidence text that is natural and specific to the claim type."""
    analysis = analysis or analyze_claim(claim, claim_type)
    context = context or {}

    if context.get("evidence"):
        return context["evidence"]

    if status == "False" and context.get("contradiction_evidence"):
        return context["contradiction_evidence"]

    if claim_type == "Statistic":
        if "population" in analysis["topics"]:
            return "Population figures are often supported by national statistical offices, UN-style estimates, or census releases; exact values depend on date and methodology."
        if "gdp" in analysis["topics"]:
            return "GDP figures should be validated against official sources such as national accounts, the World Bank, IMF, or government statistical releases."
        if analysis["has_money"]:
            return "Financial figures require source, currency, and reporting-period checks before they can be treated as verified."

    template = _pick_template(EVIDENCE_TEMPLATES[claim_type], analysis["fingerprint"] // 7)
    if context.get("web_summary"):
        return f"{template} A lightweight lookup found related context: {context['web_summary']}"
    return template


def verify_claim(claim):
    """
    Multi-stage pipeline:
    extract -> classify -> analyze -> verify -> explain.
    """
    try:
        normalized = re.sub(r"\s+", " ", (claim or "")).strip()
        if not normalized or len(normalized) < 12:
            return _build_result(
                status="Inaccurate",
                claim_type="Opinion",
                claim=normalized,
                reason="The input is empty or too short to verify reliably.",
                evidence="A professional fact-check requires a complete factual statement with enough context.",
                source="AI heuristic engine",
            )

        claim_type = classify_claim(normalized)
        analysis = analyze_claim(normalized, claim_type)
        decision = _verify_with_layers(normalized, analysis)
        status = decision["status"]
        confidence = get_confidence(
            status=status,
            claim=normalized,
            analysis=analysis,
            match_score=decision.get("match_score", 0),
            matched_pattern=decision.get("matched_pattern"),
        )
        reason = generate_reasoning(normalized, claim_type, status, analysis, decision)
        evidence = generate_explanation(normalized, claim_type, status, analysis, decision)

        return _build_result(
            status=status,
            confidence=confidence,
            claim_type=claim_type,
            reason=reason,
            evidence=evidence,
            source=decision.get("source", "AI heuristic engine"),
        )
    except Exception as error:
        return _build_result(
            status="Inaccurate",
            confidence="Low",
            claim_type="Fact",
            reason="The verification pipeline hit an internal error and returned a safe manual-review result.",
            evidence=f"Verification could not complete safely: {str(error)}",
            source="AI heuristic engine",
        )


def _verify_with_layers(claim, analysis):
    known = _match_known_patterns(analysis)
    if known:
        return known

    if analysis["type"] == "Opinion":
        return {
            "status": "Inaccurate",
            "source": "AI heuristic engine",
            "topic": "subjective language",
        }

    web_result = _search_web(claim, analysis)
    if web_result:
        return web_result

    return _heuristic_decision(analysis)


def _match_known_patterns(analysis):
    for item in KNOWN_CONTRADICTIONS:
        if any(re.search(pattern, analysis["lower"]) for pattern in item["patterns"]):
            return {
                "status": "Inaccurate" if analysis["type"] == "Statistic" else "False",
                "source": "AI heuristic engine",
                "matched_pattern": item["label"],
                "topic": item["domain"],
                "contradiction_evidence": item["evidence"],
            }

    for item in KNOWN_FACTS:
        if any(re.search(pattern, analysis["lower"]) for pattern in item["patterns"]):
            return {
                "status": "Verified",
                "source": "AI heuristic engine",
                "matched_pattern": item["label"],
                "topic": item["domain"],
                "evidence": item["evidence"],
            }

    return None


def _search_web(claim, analysis):
    """Optional no-key lookup. The app still works when network access is unavailable."""
    try:
        response = requests.get(
            SEARCH_ENDPOINT,
            params={
                "q": claim,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1,
            },
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()

        evidence = data.get("AbstractText") or data.get("Answer")
        source = data.get("AbstractURL") or data.get("AnswerType") or "DuckDuckGo Instant Answer + AI heuristic engine"
        if evidence:
            score = _match_score(claim, evidence)
            if score >= 0.62 and analysis["type"] != "Statistic":
                return {
                    "status": "Verified",
                    "source": source,
                    "match_score": score,
                    "web_summary": evidence[:240],
                    "evidence": evidence[:700],
                    "topic": _primary_topic(analysis),
                }
            return {
                "status": "Inaccurate",
                "source": source,
                "match_score": score,
                "web_summary": evidence[:240],
                "topic": _primary_topic(analysis),
            }

        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict) and topic.get("Text"):
                evidence = topic["Text"]
                score = _match_score(claim, evidence)
                if score >= 0.7 and analysis["type"] != "Statistic":
                    status = "Verified"
                else:
                    status = "Inaccurate"
                return {
                    "status": status,
                    "source": topic.get("FirstURL", "DuckDuckGo related result + AI heuristic engine"),
                    "match_score": score,
                    "web_summary": evidence[:240],
                    "topic": _primary_topic(analysis),
                }
    except Exception:
        return None

    return None


def _heuristic_decision(analysis):
    if analysis["type"] == "Statistic":
        status = "Verified" if _is_plausible_population_band(analysis) else "Inaccurate"
        return {
            "status": status,
            "source": "AI heuristic engine",
            "topic": _primary_topic(analysis),
            "match_score": 0.58 if status == "Verified" else 0,
            "matched_pattern": "Population plausibility band" if status == "Verified" else None,
        }

    if _looks_like_irrelevant_fragment(analysis):
        return {
            "status": "Inaccurate",
            "source": "AI heuristic engine",
            "topic": "insufficient context",
        }

    return {
        "status": "Inaccurate",
        "source": "AI heuristic engine",
        "topic": _primary_topic(analysis),
        "match_score": 0.35 if analysis["fact_signals"] else 0,
    }


def _build_result(status, claim_type, reason, evidence, source, confidence=None, claim=None):
    allowed_statuses = {"Verified", "Inaccurate", "False"}
    allowed_confidence = {"High", "Medium", "Low"}
    allowed_types = {"Statistic", "Fact", "Opinion"}

    if confidence is None:
        confidence = "Low" if status == "Inaccurate" else "Medium"

    return {
        "status": status if status in allowed_statuses else "Inaccurate",
        "confidence": confidence if confidence in allowed_confidence else "Low",
        "type": claim_type if claim_type in allowed_types else "Fact",
        "reason": reason or "The system could not generate a decisive explanation.",
        "evidence": evidence or "No supporting evidence was available.",
        "source": source or "AI heuristic engine",
    }


def _tokenize(text):
    stopwords = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "of",
        "in",
        "on",
        "for",
        "with",
        "by",
        "from",
        "as",
        "is",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
        "that",
        "this",
        "it",
        "its",
        "their",
    }
    return {
        word
        for word in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(word) > 2 and word not in stopwords
    }


def _match_score(claim, evidence):
    claim_tokens = _tokenize(claim)
    evidence_tokens = _tokenize(evidence)
    if not claim_tokens or not evidence_tokens:
        return 0

    overlap = len(claim_tokens & evidence_tokens) / len(claim_tokens)
    similarity = SequenceMatcher(None, claim.lower(), evidence.lower()).ratio()
    return max(overlap, similarity * 0.75)


def _primary_topic(analysis):
    if analysis["topics"]:
        return analysis["topics"][0]
    if analysis["type"] == "Statistic":
        return "quantitative data"
    if analysis["type"] == "Opinion":
        return "subjective language"
    return "general fact"


def _pick_template(options, fingerprint):
    return options[fingerprint % len(options)]


def _is_plausible_population_band(analysis):
    text = analysis["lower"]
    return "population" in text and re.search(r"\b(7|8|9|seven|eight|nine)\b", text) and "billion" in text


def _looks_like_irrelevant_fragment(analysis):
    return analysis["word_count"] < 5 or (not analysis["fact_signals"] and len(analysis["tokens"]) < 4)
