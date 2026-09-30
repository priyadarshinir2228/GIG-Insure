import os
from giginsure import tracking as TR


def test_filestore_run_layout(tmp_path, monkeypatch):
    monkeypatch.setattr(TR, "HAVE_MLFLOW", False)
    t = TR.Tracker("exp", root=str(tmp_path), exp_id="1")
    with t.start_run("r1", tags={"stage": "test"}):
        t.log_params({"lr": 0.1}); t.log_metrics({"mae": 0.9})
    run_dir = os.path.join(tmp_path, "1", t.records[0]["run_id"])
    for sub in ("params/lr", "metrics/mae", "tags/stage", "meta.yaml"):
        assert os.path.exists(os.path.join(run_dir, sub))
    assert t.records[0]["metrics"]["mae"] == 0.9


def test_registry_promotion_archives_previous(tmp_path):
    reg = TR.ModelRegistry(str(tmp_path / "registry.json"))
    v1 = reg.register("m", "run1", {"mae": 1.0}); reg.transition("m", v1, "Production")
    v2 = reg.register("m", "run2", {"mae": 0.8}); reg.transition("m", v2, "Staging"); reg.transition("m", v2, "Production")
    stages = {m["version"]: m["stage"] for m in TR.ModelRegistry(str(tmp_path / "registry.json")).state["m"]}
    assert stages == {1: "Archived", 2: "Production"}
