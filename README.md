
# storygold — SolidWorks PS controller task

This repository contains the harness and shared code for the
`solidworks-0001-playstation-controller` task.

## Layout

| Path | Purpose |
|---|---|
| `1_paystation_controller/` | The task itself: `task.toml`, the harness (`tests/task/harness/harness.py`), the frozen baseline (`tests/task/prompt/input.json`), and the reference solution (`solution/solutionTG.SLDPRT`). |
| `common/` | Shared SolidWorks/COM plumbing and measurement code used by the harness (`solidworks_session.py`, `solidworks_capture.py`, `solidworks_measure.py`, `harness_base.py`). |
| `tools/` | Support scripts (`fetch.py`). |

Large CAD assets (`.SLDPRT`, `.STL`, `.png`) are excluded from this
repository via `.gitignore`, with one explicit exception: the reference
solution (`solutionTG.SLDPRT`), which is small enough to keep versioned.

## Running the harness

Requires Windows with a licensed, running SolidWorks session (the harness
attaches to it via COM — it does not launch SolidWorks itself).

```bat
cd 1_paystation_controller
python tests\task\harness\harness.py solution\solutionTG.SLDPRT
```

## Results

Every harness run writes a full JSON report (status, continuous score, and
detailed checks for each criterion) to:
