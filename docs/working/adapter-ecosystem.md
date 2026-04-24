# Adapter ecosystem — vision, audio, multimodal, custom

**Status:** Designed 2026-04-23. Target ship: v0.3–v0.4 staged.
Owner: Benjamin Booth.

## Claim

Dendra's core (rule → MODEL_SHADOW → MODEL_PRIMARY → ML_*)
does not care whether the model is an LLM, a vision classifier,
a speech transcriber, or a diffusion-based anomaly detector.
All the core needs is a `ModelClassifier` — something that
takes an input, returns a label and a confidence.

Shipping Dendra with adapters for **more than just LLMs**
widens the adoption TAM substantially. Every team running a
CLIP zero-shot pipeline, a Whisper transcription + intent
classifier, a diffusion-based image-safety gate, etc. is a
potential Dendra user — and most of them currently rewrite
the graduated-autonomy pattern by hand.

## Baked-in adapters (v0.3 target)

### Text / LLM (v0.2 already shipped)

- `OpenAIAdapter` — GPT-5 / GPT-5-mini / o-series.
- `AnthropicAdapter` — Claude Opus / Sonnet / Haiku 4.x.
- `OllamaAdapter` — any model served via Ollama.
- `LlamafileAdapter` — Mozilla llamafile binaries.

All four implement `ModelClassifier.classify(input, labels) -> ModelPrediction`.

### Vision — zero-shot classifiers

- `CLIPAdapter(model="openai/clip-vit-large-patch14")` — accepts
  PIL image or path, runs CLIP against the label list as text
  prompts, returns label + softmax confidence. Uses the HF
  `transformers` package when present.
- `SigLIPAdapter(model="google/siglip-base-patch16-224")` —
  same protocol, SigLIP backbone (better calibration than CLIP
  for zero-shot).
- Future: `OwlV2Adapter` for zero-shot object detection
  collapsed to a "does this image contain X" classifier.

### Vision — captioner-then-classify chain

- `VLMClassifierAdapter(vlm=...)` — runs a VLM (GPT-4V,
  Claude-vision, Gemini) as an image captioner + label-pick
  step. Useful when you want a reasoning trace, not just a
  similarity score.

### Audio

- `WhisperClassifierAdapter(model="openai/whisper-small")` —
  transcribes audio, then routes the transcript through a
  secondary text classifier (LLM or sklearn head). Shipped as
  a single composite adapter so users don't have to chain
  two switches.
- Future: `AudioCLAPAdapter` for direct audio-to-label zero-shot
  (sound-event detection, acoustic scene classification).

### Multimodal / embedded

- `SentenceTransformersAdapter(model="all-MiniLM-L6-v2")` — for
  embedding-based classifiers. Pairs well with the existing
  `SklearnTextHead` as the ML side.
- `ONNXClassifierAdapter(path=..., labels_path=...)` — any
  exported classifier that runs under onnxruntime. Targets
  embedded deployment (Raspberry Pi, edge devices, browser via
  the Rust+WASM core).

## Development packaging

Adapters are **optional install extras** — never mandatory
deps of the core SDK:

```toml
[project.optional-dependencies]
openai = ["openai>=1.0"]
anthropic = ["anthropic>=0.18"]
vision = ["transformers>=4.40", "torch>=2.0", "pillow>=10"]
audio = ["openai-whisper>=20231117", "soundfile>=0.12"]
embeddings = ["sentence-transformers>=2.5"]
onnx = ["onnxruntime>=1.16"]
all = ["dendra[openai,anthropic,vision,audio,embeddings,onnx]"]
```

Installing the core is zero-dependency. A team running a
vision classifier does `pip install dendra[vision]`; a team
running audio does `pip install dendra[audio]`. The core never
imports the heavy stuff.

## Runtime-location story

The baked-in adapters live in `src/dendra/adapters/` and lazy-
import their heavy deps inside `__init__` / `classify()`:

```
src/dendra/
    adapters/
        __init__.py            # registers adapter names
        text.py                # OpenAI, Anthropic, Ollama, Llamafile
        vision.py              # CLIP, SigLIP, VLM
        audio.py               # Whisper + composite
        multimodal.py          # SentenceTransformers, ONNX
```

The current `src/dendra/models.py` (formerly `llm.py`) stays
as the home for the text adapters; the vision/audio/multimodal
files live alongside it under `adapters/` in v0.3.

## Custom-adapter dev guide

Custom adapters implement two duck-typed methods:

```python
class MyAdapter:
    def classify(self, input: Any, labels: list[str]) -> ModelPrediction:
        """Run your model. Return (label, confidence in [0, 1])."""
        ...

    def estimate_cost(self, input: Any) -> float | None:
        """Optional: return USD estimate for this call.
        Used by `dendra compare` cost columns.
        """
        return None
```

That's it. No protocol inheritance needed — Dendra uses
duck-typing (structural protocols) for adapters. A class with
`classify(input, labels) -> ModelPrediction` is an adapter.

For adapters that also need to be asynchronous (typical for
LLM providers), implement `async def aclassify(...)`. The
multi-LLM comparison path (from
`docs/working/feature-llm-comparison.md`) calls `aclassify`
under `asyncio.gather` when available, and falls back to
`classify` in a thread-pool otherwise.

## Patent coverage

The adapter ecosystem surface is covered by `patent-strategy.md`
§14 — "learned-component interchangeability." The provisional
names LLM, ML, and "other learned classifiers" as
interchangeable instances of the decision-maker abstraction.
Shipping these adapters moves that claim from "anticipated" to
"demonstrated."

## Non-goals (for v0.3)

- **Tool-use / agent adapters** (Claude + MCP, OpenAI function
  calling) — out of scope for the classifier primitive. A
  classifier returns a label, not an action plan. If a user
  wants action dispatch, the `Label(on=...)` mechanism
  provides it without coupling the classifier to agent
  frameworks.
- **Training adapters** (fine-tuning pipelines, RLHF loops).
  Dendra's scope ends at *inference*. The outcome log feeds a
  user's external training pipeline; Dendra does not own the
  training loop.

## Tasks to ship (v0.3)

1. `src/dendra/adapters/` package structure.
2. Move existing text adapters from `models.py` into
   `adapters/text.py` (keep re-exports in `dendra.models` for
   backward compat).
3. `CLIPAdapter` + `SigLIPAdapter` implementations with
   transformers-lazy-import.
4. `WhisperClassifierAdapter` composite.
5. `SentenceTransformersAdapter` + `ONNXClassifierAdapter`.
6. Add `examples/08_vision_zero_shot.py`, `09_audio_intent.py`,
   `10_embedded_onnx.py`.
7. Update landing page + README with vision/audio taglines.
8. Update `brand/messaging.md` with adjacent-domain framings.
