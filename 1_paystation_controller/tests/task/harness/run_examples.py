"""
Uruchamia harness.py na każdym pliku .SLDPRT w solution/ i examples/
(rekurencyjnie) i drukuje zbiorczą tabelę: który przykład, który status per
kryterium. Przydatne do sprawdzenia, czy zmiana w housing_signature()
(albo jakakolwiek inna zmiana harnessu) nie zepsuła wykrywania znanych,
złych (adversarial_*) wariantów.

Adversarialne przykłady (te w examples/adversarial_*) powinny w większości
kończyć się OVERALL FAIL -- jeśli po Twojej zmianie zaczną przechodzić jako
PASS, to zmiana najpewniej osłabiła test bardziej niż powinna.

Uruchom z katalogu harness/ (tam gdzie leży harness.py), z otwartym
SolidWorks.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK_DIR = HERE.parent   # ...\tests\task  (dopasuj jeśli inna struktura)
PROJECT_ROOT = TASK_DIR.parent.parent  # przybliżone -- patrz TODO niżej

sys.path.insert(0, str(HERE))
from harness import grade_candidate  # noqa: E402

# --------------------------------------------------------------------------
# TODO: dopasuj do realnej struktury, jeśli poniższe zgadywanie nie trafi.
# Szukamy .SLDPRT pod solution/ i examples/ zadania.
# --------------------------------------------------------------------------
CANDIDATE_ROOTS = [
    PROJECT_ROOT / "solution",
    PROJECT_ROOT / "examples",
]


def find_candidates():
    found = []
    for root in CANDIDATE_ROOTS:
        if root.is_dir():
            found.extend(sorted(root.rglob("*.SLDPRT")) + sorted(root.rglob("*.sldprt")))
    # de-dup + drop SolidWorks lock files (~$name.sldprt), which appear
    # when a document is currently open in the GUI and are not real parts
    seen, out = set(), []
    for p in found:
        if p.name.startswith("~$"):
            continue
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def main():
    candidates = find_candidates()
    if not candidates:
        print("Nie znaleziono żadnych .SLDPRT pod:")
        for r in CANDIDATE_ROOTS:
            print(" ", r)
        print("Popraw CANDIDATE_ROOTS w tym skrypcie.")
        return

    rows = []
    for path in candidates:
        name = path.stem  # nazwa pliku, nie folderu -- unika kolizji gdy
                          # solution/ ma kilka .SLDPRT (np. solution vs
                          # solutionTG)
        try:
            report = grade_candidate(str(path), close_after=True)
            crit = {}
            for k, v in report["criteria"].items():
                status = v.get("status", "?")
                score = v.get("score")
                crit[k] = f"{status}({score:.2f})" if score is not None else status
            crit["OVERALL"] = report["overall"]
        except Exception as exc:
            crit = {"OVERALL": f"ERROR: {exc}"}
        rows.append((name, crit))

    all_keys = []
    for _, crit in rows:
        for k in crit:
            if k not in all_keys:
                all_keys.append(k)

    name_w = max(len(n) for n, _ in rows) + 2
    col_w = 24
    print(f"{'przykład':<{name_w}}" + "".join(f"{k:<{col_w}}" for k in all_keys))
    print("-" * (name_w + col_w * len(all_keys)))
    for name, crit in rows:
        print(f"{name:<{name_w}}"
              + "".join(f"{crit.get(k, '-'):<{col_w}}" for k in all_keys))


if __name__ == "__main__":
    main()
