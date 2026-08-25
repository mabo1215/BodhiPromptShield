# CPPB reconstructed annotation surface

`cppb_full_annotations.jsonl` and `cppb_full_annotations.csv` are generated
from the released `src/experiments/cppb_prompt_manifest.csv` and
`cppb_split_manifest.csv` by:

```text
python src/experiments/build_cppb_full_annotations.py
```

Important provenance boundary: the public CPPB release contains stubs, not the
historical raw prompt payloads. These files are therefore a deterministic
reconstruction from the public metadata. They provide complete prompt text and
machine-checkable Python Unicode code-point half-open character offsets (not
UTF-8 byte or token offsets) for a new
reconstructed protocol; they do not recover or claim to reproduce the original
private/raw CPPB prompts.

Text-only rows are prompt-ready for a separately frozen reconstructed runtime.
The 64 OCR-mediated rows contain OCR-text proxies but remain blocked for an
image-backed rerun until the original render package, images, OCR engine/version,
and preprocessing configuration are available.
