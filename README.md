# Discharge Navigator

**Offline structuring of clinical discharge notes using MedGemma**

Discharge Navigator converts unstructured clinical notes into schema-validated, evidence-grounded discharge packets using MedGemma 4B, running entirely offline on a consumer laptop.

## Quick Start (Kaggle)

1. Open the [Kaggle notebook](notebooks/04_kaggle_entrypoint.ipynb)
2. Enable GPU (T4) and add your `HF_TOKEN` as a Kaggle Secret
3. Run All — repo clones, model loads, live extraction runs, demo launches

## Quick Start (Local / Edge)

```bash
# Install Ollama
ollama serve
ollama pull williamljx/medgemma-4b-it-Q4_K_M-GGUF

# Run
pip install requests pydantic pandas gradio matplotlib
python src/demo_app.py
```

## Pipeline

```
Clinical Note → MedGemma 4B → Evidence Grounding → Schema Validation → Clinician Review
```

- **CPU only** — no GPU required for edge deployment
- **No internet required** — fully offline via Ollama + GGUF
- **Every claim traceable** — evidence spans verified as exact substrings
- **Human approval required** — assistive system, not autonomous

## Evaluation (50 notes, MTSamples CC0)

| Metric | Value |
|--------|-------|
| Parse rate | 92% (46/50) |
| Median latency | 34s |
| Diagnosis grounding | 94.4% |
| Medication grounding | 90.2% |
| Overall grounding | 93.2% |

4 failures are documented transparently in `eval/results/failures_report.md`.

## Project Structure

```
src/            Source modules (navigator, grounding, schemas, prompts, demo_app)
data/           Golden test note + MTSamples subset (50 notes)
eval/results/   Pre-computed evaluation artifacts (metrics, samples, histogram)
notebooks/      Kaggle entrypoint notebook
```

## Inference Backends

| Backend | Environment | Model |
|---------|-------------|-------|
| Ollama (GGUF) | Local CPU, edge devices | MedGemma 4B IT Q4_K_M |
| HuggingFace Transformers | Kaggle T4 GPU | google/medgemma-4b-it (bfloat16) |

The notebook auto-detects the environment and selects the appropriate backend.

## License

Code: MIT | Dataset: CC0 (MTSamples) | Model: Google MedGemma terms apply
