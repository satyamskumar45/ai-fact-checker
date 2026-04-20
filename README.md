
# 🧠 AI Fact Checker

A modern, AI-inspired web application that extracts and evaluates factual claims from PDF documents.
Built with **Streamlit**, this tool helps users quickly analyze information and understand whether claims are reliable, uncertain, or potentially false.

---

## 🚀 What This App Does

Upload any PDF, and the app will:

* 📄 Extract meaningful sentences (claims)
* 🔍 Identify important factual statements (numbers, stats, trends)
* 🧠 Analyze each claim using intelligent logic
* 📊 Classify results into:

  * ✅ **Verified**
  * ⚠️ **Inaccurate**
  * ❌ **False**
* 💡 Provide:

  * Confidence level
  * Claim type (Statistic / Fact / Opinion)
  * Reasoning
  * Supporting evidence

---

## 🎯 Why This Project

In today’s world of information overload, verifying facts quickly is crucial.
This project simulates a **lightweight AI fact-checking system** that emphasizes:

* Explainability (not just results, but *why*)
* Structured outputs (like real AI tools)
* Clean UI + usable insights

---

## 🧱 Project Structure

```text
fact-checker-app/
├── app.py                 # Main Streamlit UI
├── requirements.txt       # Dependencies
├── README.md              # Project documentation
└── utils/
    ├── pdf_parser.py      # Extracts text from PDF
    ├── claim_extractor.py # Identifies meaningful claims
    └── verifier.py        # Core verification logic
```

---

## ⚙️ How It Works

The app follows a simple but effective pipeline:

```text
PDF → Text Extraction → Claim Detection → Classification → Verification → Explanation
```

Each claim is processed and returned with structured insights to mimic a real AI system.

---

## 🛠️ Run Locally

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Start the app

```bash
streamlit run app.py
```

### 3. Open in browser

Streamlit will provide a local URL (usually):

```
http://localhost:8501
```

---

## 🌐 Deployment (Streamlit Cloud)

1. Push your project to GitHub
2. Go to: [https://streamlit.io/cloud](https://streamlit.io/cloud)
3. Click **New App**
4. Select your repository
5. Set entry file:

```text
app.py
```

6. Click **Deploy**

---

## ✨ Key Features

* 📂 PDF Upload & Processing
* 🧠 Smart Claim Detection
* 📊 Structured AI-like Output
* 🎯 Confidence Scoring
* 💬 Explainable Reasoning
* 🎨 Clean, modern UI

---

## ⚠️ Limitations

* This is a **heuristic-based system**, not a real-time fact-checking engine
* Does not fetch live verified data from authoritative sources
* Results should be treated as **guidance, not absolute truth**

---

## 🔮 Future Improvements

* 🔗 Integrate real-time APIs (Google Search, News, etc.)
* 🤖 Add LLM-based verification with citations
* 📊 Improve confidence scoring with data sources
* 🧾 Export detailed reports

---

## 🙌 Final Note

This project is designed to demonstrate how an **AI-powered fact-checking system could work**, combining:

* Intelligent logic
* Clear explanations
* User-friendly design

---

If you found this useful, feel free to ⭐ the repo or build on top of it! 
=======
# ai-fact-checker
AI-powered Streamlit app that extracts and verifies factual claims from PDFs. Uses a structured pipeline (extract → classify → verify) to label claims as Verified, Inaccurate, or False with confidence scores, reasoning, and evidence.
>>>>>>> c9d0fc843798c4802d49f2b217dfd6f27bf55980
