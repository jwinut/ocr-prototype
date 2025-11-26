# Typhoon OCR Research Report

**Date:** 2025-11-26
**Purpose:** Evaluate Typhoon OCR for Thai text accuracy comparison

---

## Executive Summary

Typhoon OCR is a bilingual (Thai/English) vision-language model developed by SCB 10X specifically optimized for Thai document understanding. Version 1.5 (latest) outperforms GPT-4 and Gemini 2.5 Pro on Thai documents, making it an ideal candidate for comparing against our current OCR pipeline.

---

## API Access Information

### Getting an API Key

1. Navigate to [Playground > API Keys](https://playground.opentyphoon.ai/api-key)
2. Create an account and log in
3. Generate a new API key (store securely - shown only once)
4. Set environment variable: `TYPHOON_OCR_API_KEY`

### Endpoints

| Endpoint | Model Size | Status | Deprecation |
|----------|-----------|--------|-------------|
| `typhoon-ocr` | 2B (v1.5) | **Current default** | Active |
| `typhoon-ocr-preview` | 7B (v1) | Legacy | Dec 31, 2025 |

### Base URL
```
https://api.opentyphoon.ai/v1
```

### Rate Limits
- **2 requests/second**
- **20 requests/minute**

### Authentication
```
Authorization: Bearer <YOUR_API_KEY>
```

---

## Installation

### Python Package
```bash
pip install typhoon-ocr
```

### System Dependencies (for PDF support)
```bash
# macOS
brew install poppler

# Ubuntu/Debian
sudo apt-get install poppler-utils
```

---

## Code Examples

### Using typhoon-ocr Package (Recommended)
```python
from typhoon_ocr import ocr_document

# Set environment variable first
# export TYPHOON_OCR_API_KEY=your_key_here

# Process a document
markdown = ocr_document(
    pdf_or_image_path="document.pdf",
    page_num=1  # Optional, defaults to 1
)
print(markdown)
```

### Using OpenAI-Compatible API
```python
from openai import OpenAI
import base64

client = OpenAI(
    api_key="<YOUR_API_KEY>",
    base_url="https://api.opentyphoon.ai/v1"
)

# For image-based OCR with vision model
with open("image.png", "rb") as f:
    image_base64 = base64.b64encode(f.read()).decode()

response = client.chat.completions.create(
    model="typhoon-ocr",  # or "typhoon-ocr-preview" for v1
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                {"type": "text", "text": "Extract all text from this document"}
            ]
        }
    ],
    max_tokens=4096,
    temperature=0.0
)

print(response.choices[0].message.content)
```

---

## Supported Formats

### Input Formats
- **Images:** PNG, JPEG
- **Documents:** PDF (requires poppler)

### Output Formats
- **Text:** Markdown format
- **Tables:** HTML (supports merged cells)
- **Figures:** `<figure>` tags with descriptions
- **Math:** LaTeX format
- **Structure:** `<page_number>` tags

---

## Performance Benchmarks (Thai Documents)

### Typhoon OCR v1.5 vs v1 Comparison

| Metric | v1 (7B) | v1.5 (2B) | Improvement |
|--------|---------|-----------|-------------|
| BLEU | 0.558 | 0.644 | +15.4% |
| ROUGE-L | 0.686 | 0.774 | +12.8% |
| Levenshtein | 0.332 | 0.251 | -24.4% (better) |

### Performance by Document Type

| Document Type | BLEU | ROUGE-L | Levenshtein |
|---------------|------|---------|-------------|
| Thai Government Forms | 0.870 | 0.967 | 0.035 |
| Thai Books | 0.746 | 0.949 | Low |
| Handwritten Forms | 0.522 | 0.645 | - |
| Infographics | 0.408 | 0.527 | - |

### Comparison with Competitors

On Thai government forms, Typhoon OCR v1.5 **outperforms both Gemini 2.5 Pro and GPT-4** in:
- Word/phrase-level precision (BLEU)
- Structural/contextual alignment (ROUGE-L)
- Character-level accuracy (Levenshtein)

---

## Supported Document Types

1. **Financial Documents** - Annual reports, financial statements
2. **Government Forms** - Official Thai documents
3. **Academic Papers** - Research documents, books
4. **Handwritten Content** - Notes, forms with handwriting
5. **Infographics** - Charts, graphs, visual data
6. **Mathematical Content** - Equations, formulas
7. **Thai-Pali Buddhist Texts** - Specialized religious documents
8. **Receipts/Bills** - Commercial documents

---

## Implementation Plan for Accuracy Comparison

### Architecture Design

```
┌─────────────────────────────────────────────────────────┐
│                   OCR Comparison System                  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │  Document    │───►│   Router     │                   │
│  │   Input      │    │              │                   │
│  └──────────────┘    └──────┬───────┘                   │
│                             │                            │
│         ┌───────────────────┼───────────────────┐       │
│         ▼                   ▼                   ▼       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐│
│  │  Current OCR │    │ Typhoon OCR  │    │  Future OCR  ││
│  │  (Docling)   │    │    API       │    │   (Plugin)   ││
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘│
│         │                   │                   │        │
│         └───────────────────┼───────────────────┘       │
│                             ▼                            │
│                    ┌──────────────┐                      │
│                    │  Comparison  │                      │
│                    │   Engine     │                      │
│                    └──────┬───────┘                      │
│                           ▼                              │
│                    ┌──────────────┐                      │
│                    │   Results    │                      │
│                    │   Database   │                      │
│                    └──────────────┘                      │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Proposed File Structure

```
claude/
├── processing/
│   ├── ocr_typhoon.py      # Typhoon OCR integration
│   ├── ocr_comparison.py   # Comparison engine
│   └── ocr.py              # Existing OCR (update to support plugins)
├── app/
│   └── pages/
│       └── 7_🔬_Compare.py # New comparison page
└── scripts/
    └── run_comparison.py   # Batch comparison script
```

### Key Implementation Components

1. **TyphoonOCRClient** - API wrapper class
2. **OCRComparisonEngine** - Side-by-side comparison
3. **AccuracyMetrics** - BLEU, ROUGE-L, Levenshtein calculations
4. **ComparisonUI** - Streamlit page for visual comparison

---

## Next Steps

1. **Get API Key:** Sign up at https://playground.opentyphoon.ai/api-key
2. **Install Package:** `pip install typhoon-ocr`
3. **Test Connection:** Run sample OCR on test document
4. **Implement Wrapper:** Create `ocr_typhoon.py`
5. **Build Comparison:** Create comparison engine and UI
6. **Run Benchmarks:** Compare on Y67 dataset

---

## Sources

- [Typhoon OCR Documentation](https://docs.opentyphoon.ai/en/ocr/)
- [Typhoon Quick Start Guide](https://docs.opentyphoon.ai/en/quickstart/)
- [Typhoon OCR 1.5 Release Blog](https://opentyphoon.ai/blog/en/typhoon-ocr-release)
- [Typhoon OCR on Hugging Face](https://huggingface.co/scb10x/typhoon-ocr-7b)
- [OpenTyphoon Main Site](https://opentyphoon.ai/)
