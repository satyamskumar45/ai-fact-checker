import json
import logging
import os
import re
import time
from typing import Any

import streamlit as st
from groq import Groq


logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

GROQ_MODEL_NAME =  "llama-3.1-8b-instant"
MAX_CLAIM_CHARS = 1000
MAX_EVIDENCE_CHARS = 1200

STATUS_VALUES = {"Verified", "Inaccurate", "False"}
CONFIDENCE_VALUES = {"High", "Medium", "Low"}
CLAIM_TYPES = {"Fact", "Statistic", "Opinion"}


def log(message: str, level: int = logging.INFO) -> None:
    LOGGER.log(level, "[Verifier] %s", message)


def load_api_key() -> str:
    try:
        api_key = st.secrets["GROQ_API_KEY"]
        if api_key:
            return str(api_key).strip()
    except Exception as error:
        log(f"Streamlit secret GROQ_API_KEY not available: {error}", logging.DEBUG)

    return (os.getenv("GROQ_API_KEY") or "").strip()


GROQ_API_KEY = load_api_key()


def initialize_groq_client():
    if not GROQ_API_KEY:
        log("GROQ_API_KEY missing", logging.ERROR)
        return None

    try:
        client = Groq(api_key=GROQ_API_KEY)
        log("Groq client initialized")
        return client
    except Exception as e:
        log(f"Groq client init failed: {e}", logging.ERROR)
        return None


client = initialize_groq_client()


@st.cache_data(show_spinner=False, ttl=3600)
def verify_claim(claim: str) -> dict[str, str]:
    normalized_claim = clean_text(claim)

    if not normalized_claim or len(normalized_claim) < 8:
        return build_result(
            status="Inaccurate",
            confidence="Low",
            claim_type="Opinion",
            reasoning="The claim is empty or too short to verify reliably.",
            evidence="A complete factual statement is required before Groq verification can be performed.",
            source="Verifier validation",
        )

    if len(normalized_claim) > MAX_CLAIM_CHARS:
        normalized_claim = normalized_claim[:MAX_CLAIM_CHARS].strip()

    result = verify_with_groq(normalized_claim)
    return calibrate_result(result)


def call_groq_with_retry(prompt: str) -> Any:
    """Call Groq API with exponential backoff retry logic for rate limit errors.

    Retries up to 4 times with delays: 2s -> 5s -> 10s -> 20s
    Only retries on 429 / RESOURCE_EXHAUSTED errors.
    """
    if client is None:
        raise RuntimeError("Groq client is not initialized. Cannot perform API call.")

    delays = [2, 5, 10, 20]
    last_error: Exception | None = None

    for attempt, delay in enumerate(delays):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.2,
            )
            if attempt > 0:
                log(f"Groq API call succeeded on retry attempt {attempt + 1}")
            return response
        except Exception as error:
            last_error = error
            error_str = str(error)

            if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
                if attempt < len(delays) - 1:
                    log(
                        f"Rate limit hit. Retrying in {delay}s (attempt {attempt + 1}/{len(delays)})...",
                        logging.WARNING,
                    )
                    time.sleep(delay)
                    continue
                else:
                    log(
                        f"Rate limit persisted after {len(delays)} retries. Giving up.",
                        logging.ERROR,
                    )
            else:
                raise error

    raise last_error


def verify_with_groq(claim: str) -> dict[str, str]:
    global client

    claim_type = classify_claim(claim)

    if not GROQ_API_KEY:
        log("Groq verification failed: GROQ_API_KEY is missing.", logging.ERROR)
        return build_result(
            status="Inaccurate",
            confidence="Low",
            claim_type=claim_type,
            reasoning="Groq verification could not run because GROQ_API_KEY is missing.",
            evidence="Set GROQ_API_KEY in Streamlit secrets or the environment to enable AI verification.",
            source="Groq configuration error",
        )

    if client is None:
        log("Groq client is None after key load; retrying initialization.", logging.WARNING)
        client = initialize_groq_client()

    if client is None:
        log("Groq verification failed: client is None even though an API key exists.", logging.ERROR)
        return build_result(
            status="Inaccurate",
            confidence="Low",
            claim_type=claim_type,
            reasoning="Groq verification could not run because the Groq client failed to initialize.",
            evidence="The API key was found, but the Groq client could not be created.",
            source="Groq initialization error",
        )

    prompt = build_groq_prompt(claim, claim_type)

    try:
        response = call_groq_with_retry(prompt)
    except Exception as error:
        error_str = str(error)
        log(f"Groq API call failed: {error}", logging.ERROR)

        if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
            return build_result(
                status="Inaccurate",
                confidence="Low",
                claim_type=claim_type,
                reasoning="Rate limit exceeded. Please retry shortly.",
                evidence="Groq API quota exceeded. Free tier limits have been reached. Please try again later.",
                source="Groq API - Rate Limited",
            )

        return build_result(
            status="Inaccurate",
            confidence="Low",
            claim_type=claim_type,
            reasoning="Groq verification failed while generating a response.",
            evidence=f"Groq API error: {error}",
            source="Groq API error",
        )

    raw_text = _extract_response_text(response)
    parsed = extract_json_object(raw_text)

    if parsed:
        log("Groq verification completed with valid JSON.")
        return normalize_groq_result(parsed, claim_type)

    log("Groq returned non-JSON output; returning raw model output for review.", logging.WARNING)
    return build_result(
        status="Inaccurate",
        confidence="Low",
        claim_type=claim_type,
        reasoning="Groq responded, but the response could not be parsed as valid JSON.",
        evidence=raw_text or "Groq returned an empty response.",
        source="Groq raw response",
    )


def _extract_response_text(response: Any) -> str:
    """Safely extract text content from a Groq API response."""
    try:
        if response is None:
            log("Groq response is None.", logging.WARNING)
            return ""
        choices = getattr(response, "choices", None)
        if not choices or not isinstance(choices, list) or len(choices) == 0:
            log("Groq response contains no choices.", logging.WARNING)
            return ""
        message = getattr(choices[0], "message", None)
        if message is None:
            log("Groq response choice has no message.", logging.WARNING)
            return ""
        content = getattr(message, "content", None)
        return clean_text(content) if content is not None else ""
    except Exception as error:
        log(f"Failed to extract text from Groq response: {error}", logging.ERROR)
        return ""


def build_groq_prompt(claim: str, claim_type: str) -> str:
    return f"""You are a professional fact-checking system. Your sole task is to verify the factual accuracy of the claim below.

Claim: "{claim}"
Claim Type: {claim_type}

STRICT OUTPUT RULES — YOU MUST FOLLOW THESE EXACTLY:
1. Return ONLY a single valid JSON object. No other text whatsoever.
2. Do NOT include markdown, code fences, backticks, or any wrapper text.
3. Do NOT include any explanation, preamble, or commentary outside the JSON.
4. The JSON must be parseable by Python's json.loads() with no preprocessing.

Required JSON structure (use exactly these keys):
{{
  "status": "Verified" | "Inaccurate" | "False",
  "confidence": "High" | "Medium" | "Low",
  "reasoning": "A clear, concise explanation of your verdict.",
  "evidence": "Specific facts, data, or context that support your verdict.",
  "source": "The knowledge domain used (e.g. Scientific consensus, Historical records, Geography, etc.)"
}}

IMPORTANT: Any response that is not a raw, valid JSON object will be treated as a failed verification.
"""


def extract_json_object(text: str) -> dict[str, Any] | None:
    cleaned = strip_json_fences(text)
    if not cleaned:
        return None

    for candidate in json_candidates(cleaned):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as error:
            log(f"JSON parse failed: {error}", logging.DEBUG)
            continue

        if isinstance(parsed, dict):
            return parsed

    return None


def json_candidates(text: str) -> list[str]:
    candidates = [text.strip()]
    candidates.extend(match.group(0).strip() for match in re.finditer(r"\{[\s\S]*\}", text))

    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            _, end_index = decoder.raw_decode(text[match.start():])
            candidates.append(text[match.start(): match.start() + end_index].strip())
        except json.JSONDecodeError:
            continue

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            deduped.append(candidate)
            seen.add(candidate)
    return deduped


def strip_json_fences(text: str) -> str:
    cleaned = clean_text(text)
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def normalize_groq_result(result: dict[str, Any], claim_type: str) -> dict[str, str]:
    return build_result(
        status=clean_text(result.get("status")) or "Inaccurate",
        confidence=clean_text(result.get("confidence")) or "Low",
        claim_type=clean_text(result.get("type") or result.get("claim_type")) or claim_type,
        reasoning=clean_text(result.get("reasoning") or result.get("reason")),
        evidence=clean_text(result.get("evidence")),
        source=clean_text(result.get("source")) or "Groq AI",
        source_url=clean_text(result.get("source_url") or result.get("url")),
    )


def calibrate_result(result: dict[str, str]) -> dict[str, str]:
    status = normalize_choice(result.get("status", "Inaccurate"), STATUS_VALUES, "Inaccurate")
    confidence = normalize_choice(result.get("confidence", "Low"), CONFIDENCE_VALUES, "Low")
    claim_type = normalize_choice(result.get("type", "Fact"), CLAIM_TYPES, "Fact")

    result["status"] = status
    result["confidence"] = confidence
    result["type"] = claim_type
    result["reasoning"] = clean_text(result.get("reasoning") or result.get("reason")) or "No reasoning was provided."
    result["reason"] = result["reasoning"]
    result["evidence"] = (clean_text(result.get("evidence")) or "No evidence was provided.")[:MAX_EVIDENCE_CHARS]
    result["source"] = normalize_source(result.get("source"))
    result["source_url"] = clean_text(result.get("source_url"))
    return result


def normalize_choice(value: Any, allowed_values: set[str], fallback: str) -> str:
    cleaned = clean_text(value).replace("/", "|")
    for allowed_value in allowed_values:
        if re.search(rf"\b{re.escape(allowed_value)}\b", cleaned, flags=re.IGNORECASE):
            return allowed_value
    return fallback


def classify_claim(claim: str) -> str:
    text = clean_text(claim)
    lower_text = text.lower()

    if not text or len(text.split()) < 3:
        return "Opinion"

    if re.search(r"[$]?\s?\d|%|\b(19|20)\d{2}\b", text):
        return "Statistic"

    statistic_terms = {
        "population",
        "gdp",
        "inflation",
        "revenue",
        "profit",
        "loss",
        "growth",
        "rate",
        "percentage",
        "market share",
        "valuation",
        "users",
        "million",
        "billion",
        "trillion",
    }
    if any(term in lower_text for term in statistic_terms):
        return "Statistic"

    opinion_terms = {
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
        "leading",
    }
    if any(re.search(rf"\b{re.escape(term)}\b", lower_text) for term in opinion_terms):
        return "Opinion"

    return "Fact"


def normalize_source(source: Any) -> str:
    cleaned = clean_text(source)
    if not cleaned:
        return "Groq AI"

    vague_sources = {
        "source",
        "trusted type",
        "unknown",
        "n/a",
        "none",
        "ai",
        "groq",
    }
    if cleaned.lower() in vague_sources:
        return "Groq AI"

    return cleaned[:120]


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def build_result(
    status: str,
    confidence: str,
    claim_type: str,
    reasoning: str,
    evidence: str,
    source: str,
    source_url: str = "",
) -> dict[str, str]:
    status = normalize_choice(status, STATUS_VALUES, "Inaccurate")
    confidence = normalize_choice(confidence, CONFIDENCE_VALUES, "Low")
    claim_type = normalize_choice(claim_type, CLAIM_TYPES, "Fact")
    reasoning = clean_text(reasoning) or "No reasoning was provided."
    evidence = (clean_text(evidence) or "No evidence was provided.")[:MAX_EVIDENCE_CHARS]
    source = normalize_source(source)
    source_url = clean_text(source_url)

    return {
        "status": status,
        "confidence": confidence,
        "type": claim_type,
        "reasoning": reasoning,
        "reason": reasoning,
        "evidence": evidence,
        "source": source,
        "source_url": source_url,
    }