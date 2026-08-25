# CPPB reconstructed blind-review interface

## Start locally

From the repository root, either double-click:

```text
run_cppb_blind_review_ui.bat
```

or run:

```powershell
C:\Users\295461\AppData\Local\Programs\Python\Python312\python.exe src/experiments/cppb_blind_review_ui.py
```

Then open the URL printed by Gradio, normally:

```text
http://127.0.0.1:7860
```

The recommended setup uses the available Python 3.12 installation and the
optional UI dependencies:

```powershell
C:\Users\295461\AppData\Local\Programs\Python\Python312\python.exe -m pip install "gradio>=5,<6"
```

The same dependency is recorded in `src/requirements.txt`; installing the
full research environment is optional for this scoring interface.

## Instructions for each rater

1. Enter a unique `评分者 ID`, for example `rater_01`.
2. Select one `Prompt block`. A block contains the same task and four
   anonymous outputs labelled A, B, C, and D.
3. Read the prompt, task objective, success criteria, and required output
   components.
4. For each of A/B/C/D, select all three scores:
   - `Task success`: `1` only when the requested task/result is completed;
     otherwise `0`.
   - `Faithfulness`: `0` for wrong or unsupported content, `1` for partially
     correct content, and `2` for complete and faithful content.
   - `Required fields`: `1` when every required output component is present,
     otherwise `0`.
5. Use the comment box for a short reason, especially for a zero or partial
   score. Comments are optional.
6. Click `保存当前 prompt 的四条评分`. The four rows are saved together.
7. Use `上一条` or `下一条` to continue. Reopening the same rater ID resumes
   saved scores.

Do not try to identify the hidden condition behind A/B/C/D and do not open the
analyst method-key file. Sensitive-value exposure is checked automatically;
raters do not need to assign a separate privacy score.

## Output

The UI writes completed ratings to:

```text
data/cppb_reconstructed_blind_ratings_vgpu3090.csv
```

The original blind table is never overwritten. The saved file contains the
blind condition code, scores, rater ID, comments, and save timestamp. It does
not contain the condition-to-method key.

For remote/LAN use, bind explicitly and set authentication rather than using
an unauthenticated public share:

```powershell
python src/experiments/cppb_blind_review_ui.py `
  --server-name 0.0.0.0 --port 7860 `
  --auth-user reviewer --auth-password "choose-a-local-password"
```
