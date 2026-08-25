# CPPB reconstructed utility pilot: blind scoring instructions

This file accompanies the blind A/B/C/D review CSV. Do not seek or use the
separate method-key CSV while scoring. Each row is one model output for one
reconstructed CPPB test prompt under a randomized condition code.

Score only the output quality, not privacy detection quality:

- `task_success_score`: `1` if the requested action/result is completed, else `0`.
- `faithfulness_score`: `0` wrong/unsupported, `1` partially faithful, `2` complete and faithful.
- `required_fields_score`: `1` if the required output components listed in the row are present, else `0`.
- `comments`: short reason for a zero or partial score.

Do not manually score exact raw-value exposure. That is checked automatically
from the annotated prompt span. Do not infer the method from wording or output
style. Keep the condition code and method identity blinded until all ratings are
complete.

The protocol is a reconstructed text-only utility pilot, not recovery of the
historical CPPB raw benchmark. OCR rows are not included in this file.
