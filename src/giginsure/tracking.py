"""Experiment tracking.

Uses MLflow when it is installed. When it is not (e.g. offline CI sandbox) runs are written in MLflow's
FileStore layout (mlruns/<experiment_id>/<run_id>/{meta.yaml,params,metrics,tags,artifacts}) so the same
directory can be opened later with `mlflow ui --backend-store-uri ./mlruns`.
"""
import json, os, shutil, time, uuid, getpass
from contextlib import contextmanager

try:  # pragma: no cover - depends on environment
    import mlflow
    HAVE_MLFLOW = os.environ.get("GIGINSURE_DISABLE_MLFLOW") != "1"
except Exception:  # noqa
    mlflow = None
    HAVE_MLFLOW = False


class _FileRun:
    def __init__(self, root, exp_id, name, tags):
        self.run_id = uuid.uuid4().hex
        self.dir = os.path.join(root, exp_id, self.run_id)
        for sub in ("params", "metrics", "tags", "artifacts"):
            os.makedirs(os.path.join(self.dir, sub), exist_ok=True)
        self.exp_id, self.name, self.start = exp_id, name, int(time.time() * 1000)
        self.tags = {"mlflow.runName": name, "mlflow.user": getpass.getuser(), **(tags or {})}
        for k, v in self.tags.items():
            self._w("tags", k, v)

    def _w(self, sub, key, val, mode="w"):
        p = os.path.join(self.dir, sub, key.replace("/", os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, mode) as f:
            f.write(str(val))

    def end(self, status=3):
        end = int(time.time() * 1000)
        with open(os.path.join(self.dir, "meta.yaml"), "w") as f:
            f.write(f"artifact_uri: {os.path.abspath(os.path.join(self.dir, 'artifacts'))}\nend_time: {end}\nentry_point_name: ''\n"
                    f"experiment_id: '{self.exp_id}'\nlifecycle_stage: active\nrun_id: {self.run_id}\nrun_name: {self.name}\n"
                    f"run_uuid: {self.run_id}\nsource_name: ''\nsource_type: 4\nsource_version: ''\nstart_time: {self.start}\n"
                    f"status: {status}\ntags: []\nuser_id: {getpass.getuser()}\n")


class Tracker:
    def __init__(self, experiment="giginsure-pricing", root="mlruns", exp_id="1"):
        self.root, self.exp_id, self.experiment = root, exp_id, experiment
        self.run = None
        self.backend = "mlflow" if HAVE_MLFLOW else "filestore"
        self.records = []  # in-memory summary used for reports
        if HAVE_MLFLOW:  # pragma: no cover
            mlflow.set_tracking_uri("file:///" + os.path.abspath(root).replace("\\", "/"))
            mlflow.set_experiment(experiment)
        else:
            os.makedirs(os.path.join(root, exp_id), exist_ok=True)
            with open(os.path.join(root, exp_id, "meta.yaml"), "w") as f:
                now = int(time.time() * 1000)
                f.write(f"artifact_location: {os.path.abspath(os.path.join(root, exp_id))}\ncreation_time: {now}\nexperiment_id: '{exp_id}'\n"
                        f"last_update_time: {now}\nlifecycle_stage: active\nname: {experiment}\n")

    @contextmanager
    def start_run(self, name, tags=None):
        rec = dict(run_name=name, params={}, metrics={}, tags=dict(tags or {}))
        if HAVE_MLFLOW:  # pragma: no cover
            ctx = mlflow.start_run(run_name=name, tags=tags)
            rec["run_id"] = ctx.info.run_id
        else:
            self.run = _FileRun(self.root, self.exp_id, name, tags)
            rec["run_id"] = self.run.run_id
        self._rec = rec
        status = 4
        try:
            yield self
            status = 3
        finally:
            if HAVE_MLFLOW:  # pragma: no cover
                mlflow.end_run()
            else:
                self.run.end(status)
            self.records.append(rec)

    def log_params(self, d):
        for k, v in d.items():
            self._rec["params"][k] = v
            if HAVE_MLFLOW: mlflow.log_param(k, v)  # pragma: no cover
            else: self.run._w("params", k, v)

    def log_metric(self, k, v, step=0):
        v = float(v)
        self._rec["metrics"][k] = v
        if HAVE_MLFLOW: mlflow.log_metric(k, v, step=step)  # pragma: no cover
        else: self.run._w("metrics", k, f"{int(time.time()*1000)} {v} {step}\n", mode="a")

    def log_metrics(self, d, step=0):
        for k, v in d.items(): self.log_metric(k, v, step)

    def set_tag(self, k, v):
        self._rec["tags"][k] = v
        if HAVE_MLFLOW: mlflow.set_tag(k, v)  # pragma: no cover
        else: self.run._w("tags", k, v)

    def log_artifact(self, path, subdir=""):
        if HAVE_MLFLOW: mlflow.log_artifact(path, subdir or None)  # pragma: no cover
        else:
            dst = os.path.join(self.run.dir, "artifacts", subdir)
            os.makedirs(dst, exist_ok=True); shutil.copy(path, dst)


class ModelRegistry:
    """Minimal registry (JSON) mirroring MLflow Model Registry stages: None -> Staging -> Production -> Archived."""
    def __init__(self, path="mlruns/registry.json"):
        self.path = path
        self.state = {}
        if os.path.exists(path):
            with open(path) as f:
                self.state = json.load(f)

    def register(self, name, run_id, metrics, artifact=None):
        v = len(self.state.get(name, [])) + 1
        self.state.setdefault(name, []).append(dict(version=v, run_id=run_id, stage="None", metrics=metrics, artifact=artifact,
                                                    created=time.strftime("%Y-%m-%d %H:%M:%S")))
        self._save(); return v

    def transition(self, name, version, stage):
        if stage == "Production":
            for m in self.state[name]:
                if m["stage"] == "Production": m["stage"] = "Archived"
        for m in self.state[name]:
            if m["version"] == version: m["stage"] = stage
        self._save()

    def production(self, name):
        for m in self.state.get(name, []):
            if m["stage"] == "Production":
                return m
        return None

    def _save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.state, f, indent=2, default=float)
