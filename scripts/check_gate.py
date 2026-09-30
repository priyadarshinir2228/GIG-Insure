"""CI model-evaluation gate: exits non-zero if any metric in outputs/results.json regresses past its threshold."""
import json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from giginsure.console import banner, table, ok, warn

CHECKS = [  # (name, getter, op, threshold)
    ("Pricing test MAE (₹)", lambda R: R["pricing"]["gbdt_champion"]["test"]["mae"], "<=", 1.20),
    ("Pricing test R²", lambda R: R["pricing"]["gbdt_champion"]["test"]["r2"], ">=", 0.93),
    ("MAE ratio to linear baseline", lambda R: R["pricing"]["gbdt_champion"]["test"]["mae"] / R["pricing"]["ridge_linear"]["test"]["mae"], "<=", 0.60),
    ("Fraud recall", lambda R: R["fraud"]["iforest"]["recall"], ">=", 0.85),
    ("Fraud false-positive rate", lambda R: R["fraud"]["iforest"]["fpr"], "<=", 0.03),
    ("Fraud ROC-AUC", lambda R: R["fraud"]["iforest"]["roc_auc"], ">=", 0.97),
    ("Trigger F1 (any trigger)", lambda R: R["triggers"]["any"]["f1"], ">=", 0.85),
    ("Pricing p95 latency (ms)", lambda R: R["performance"]["price_latency_ms_p95"], "<=", 50.0),
]


def run(path):
    with open(path) as f:
        R = json.load(f)
    rows = []
    for name, get, op, thr in CHECKS:
        v = float(get(R))
        passed = v <= thr if op == "<=" else v >= thr
        rows.append(dict(check=name, threshold=f"{op} {thr}", measured=v, result="PASS" if passed else "FAIL"))
    return rows


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "results.json")
    rows = run(path)
    banner("Model evaluation gate")
    table(rows, ["check", "threshold", "measured", "result"], highlight=lambda r: "green" if r["result"] == "PASS" else "red")
    n_ok = sum(r["result"] == "PASS" for r in rows)
    (ok if n_ok == len(rows) else warn)(f"{n_ok}/{len(rows)} checks passed")
    sys.exit(0 if n_ok == len(rows) else 1)
