from html import escape
import json
import time
from pathlib import Path

import streamlit as st
from utils.claim_extractor import extract_claims
from utils.pdf_parser import extract_text_from_pdf
from utils.verifier import verify_claim


def load_css():
    css_path = Path(__file__).parent / "assets" / "styles.css"
    if css_path.exists():
        st.markdown(
            f"<style>{css_path.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )


STATUS_STYLES = {
    "Verified": "verified",
    "Inaccurate": "inaccurate",
    "False": "false",
}


def safe_text(value, fallback=""):
    return escape(str(value if value is not None else fallback))


def status_badge(status):
    label = status or "Unknown"
    badge_class = STATUS_STYLES.get(label, "neutral")
    return f'<span class="status-badge status-{badge_class}">{safe_text(label)}</span>'


def normalize_result(result):
    reasoning = result.get("reasoning") or result.get("reason", "No reasoning available.")
    return {
        "claim": result.get("claim", ""),
        "status": result.get("status", "Inaccurate"),
        "confidence": result.get("confidence", "Low"),
        "type": result.get("type", "Fact"),
        "reasoning": reasoning,
        "reason": reasoning,
        "evidence": result.get("evidence", "No evidence found."),
        "source": result.get("source") or "AI Fact Checker",
    }


def render_hero():
    st.markdown(
        """
        <section class="hero">
            <div class="hero-badge">AI FACT CHECKER</div>
            <h1>Verify claims. <span>Instantly.</span></h1>
            <p>
                Transform dense PDF documents into a focused verification dashboard with
                extracted claims, evidence trails, and confidence signals in one premium workspace.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_summary(results):
    total_claims = len(results)
    verified_count = sum(1 for result in results if result.get("status") == "Verified")
    inaccurate_count = sum(1 for result in results if result.get("status") == "Inaccurate")
    false_count = sum(1 for result in results if result.get("status") == "False")
    cards = [
        ("Total", total_claims, 100 if total_claims else 0, "total"),
        ("Verified", verified_count, verified_count / total_claims * 100 if total_claims else 0, "verified"),
        ("Inaccurate", inaccurate_count, inaccurate_count / total_claims * 100 if total_claims else 0, "inaccurate"),
        ("False", false_count, false_count / total_claims * 100 if total_claims else 0, "false"),
    ]

    cards_html = "".join(
        f"""
        <article class="summary-card summary-{card_class}">
            <div class="summary-card__number">{value}</div>
            <div class="summary-card__label">{label}</div>
            <div class="summary-card__track">
                <span style="width: {percentage:.1f}%"></span>
            </div>
        </article>
        """
        for label, value, percentage, card_class in cards
    )

    st.markdown(
        f"""
        <section class="dashboard-section">
            <div class="section-label">Summary dashboard</div>
            <div class="summary-grid">{cards_html}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_claim_card(index, result):
    result = normalize_result(result)
    source = result.get("source") or "No source available"
    st.markdown(
        f"""
        <article class="claim-card">
            <div class="claim-card__header">
                <div>
                    <p class="claim-card__eyebrow">Claim {index}</p>
                    <h3>{safe_text(result.get("claim", ""))}</h3>
                </div>
                {status_badge(result.get("status", "Inaccurate"))}
            </div>
            <div class="claim-meta">
                <span>Confidence: {safe_text(result.get("confidence", "Low"))}</span>
                <span>Type: {safe_text(result.get("type", "Fact"))}</span>
            </div>
            <details class="evidence-panel">
                <summary>View reasoning and evidence</summary>
                <div class="evidence-panel__content">
                    <p class="claim-card__label">Reasoning</p>
                    <p class="claim-card__evidence">{safe_text(result.get("reason", "No reasoning available"))}</p>
                    <p class="claim-card__label">Evidence</p>
                    <p class="claim-card__evidence">{safe_text(result.get("evidence", "No evidence found"))}</p>
                    <div class="claim-card__source">
                        <span>Source</span>
                        <p>{safe_text(source)}</p>
                    </div>
                </div>
            </details>
        </article>
        """,
        unsafe_allow_html=True,
    )


def build_report(results):
    lines = ["AI Fact Checker Report", "=" * 24, ""]
    lines.append(f"Total claims: {len(results)}")
    lines.append(f"Verified: {sum(1 for result in results if result.get('status') == 'Verified')}")
    lines.append(f"Inaccurate: {sum(1 for result in results if result.get('status') == 'Inaccurate')}")
    lines.append(f"False: {sum(1 for result in results if result.get('status') == 'False')}")
    lines.append("")

    for index, result in enumerate(results, start=1):
        result = normalize_result(result)
        lines.append(f"Claim {index}: {result.get('claim', '')}")
        lines.append(f"Status: {result.get('status', 'Inaccurate')}")
        lines.append(f"Confidence: {result.get('confidence', 'Low')}")
        lines.append(f"Type: {result.get('type', 'Fact')}")
        lines.append(f"Reason: {result.get('reason', 'No reasoning available')}")
        lines.append(f"Evidence: {result.get('evidence', 'No evidence found')}")
        lines.append(f"Source: {result.get('source') or 'No source available'}")
        lines.append("-" * 60)

    return "\n".join(lines)


def main():
    st.set_page_config(page_title="AI Fact Checker", page_icon="\U0001f9e0", layout="wide")

    load_css()
    render_hero()

    st.markdown('<div class="upload-heading">Upload document</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Drop a PDF here or click to browse", type=["pdf"])

    if not uploaded_file:
        st.info("Choose a PDF to begin.")
        return

    try:
        with st.spinner("\U0001f50d Analyzing and verifying claims..."):
            text = extract_text_from_pdf(uploaded_file)
            claims = extract_claims(text)
    except Exception as e:
        st.error(f"Unable to process the uploaded PDF. Please ensure it is a valid, text-based PDF and try again. Details: {e}")
        return

    if not text.strip():
        st.error("No readable text was found in this PDF. Try a text-based PDF instead of a scanned image.")
        return

    st.markdown('<div class="section-label">Extracted claims</div>', unsafe_allow_html=True)

    if not claims:
        st.warning("No factual claims with numbers, dates, percentages, or target keywords were found.")
        with st.expander("Preview extracted text"):
            st.write(text[:3000])
        return

    # Limit claims to prevent rate limiting (max 5 claims per session)
    claims = claims[:5]

    st.markdown(f'<p class="muted-copy">Found {len(claims)} claim(s) to verify.</p>', unsafe_allow_html=True)

    with st.spinner("\U0001f50d Analyzing and verifying claims..."):
        results = []
        for index, claim in enumerate(claims):
            try:
                result = verify_claim(claim)
            except Exception as e:
                result = {
                    "status": "Inaccurate",
                    "confidence": "Low",
                    "type": "Fact",
                    "reasoning": "Verification could not be completed for this claim. Please review it manually.",
                    "reason": "Verification could not be completed for this claim. Please review it manually.",
                    "evidence": f"An error occurred while verifying this claim: {str(e)}",
                    "source": "App error handler",
                }
            results.append({"claim": claim, **result})

            # Add 2-second delay between API calls to avoid rate limiting
            # Skip delay after the last claim
            if index < len(claims) - 1:
                time.sleep(2)

    render_summary(results)

    st.markdown('<div class="section-label">Claim intelligence</div>', unsafe_allow_html=True)
    for index, result in enumerate(results, start=1):
        render_claim_card(index, result)

    st.download_button(
        "\U0001f4e5 Download Report",
        data=build_report(results),
        file_name="fact_check_report.txt",
        mime="text/plain",
        use_container_width=True,
    )

    st.download_button(
        "\U0001f4e5 Download JSON Report",
        data=json.dumps([normalize_result(result) for result in results], indent=2),
        file_name="fact_check_report.json",
        mime="application/json",
        use_container_width=True,
    )

    with st.expander("Preview extracted PDF text"):
        st.write(text[:5000])


if __name__ == "__main__":
    main()