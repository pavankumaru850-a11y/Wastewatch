"""Tests for the training pipeline's guardrails. Uses synthetic data in a temp dir;
ultralytics is NOT needed (nothing here trains or infers)."""
import importlib
import json
import shutil
import sys
from pathlib import Path

import pytest
from PIL import Image

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))


@pytest.fixture()
def env(tmp_path, monkeypatch):
    tdir = tmp_path / "training"
    (tdir).mkdir()
    shutil.copy(HERE / "data.yaml", tdir / "data.yaml")
    for sub in ("images", "labels"):
        for sp in ("train", "val", "test"):
            (tdir / "dataset" / sub / sp).mkdir(parents=True)
    root = tmp_path / "repo"
    (root / "backend" / "models").mkdir(parents=True)
    monkeypatch.setenv("WW_TRAINING_DIR", str(tdir))
    monkeypatch.setenv("WW_REPO_ROOT", str(root))
    import dataset_manager, export
    importlib.reload(dataset_manager)
    importlib.reload(export)
    return {"tdir": tdir, "root": root, "dm": dataset_manager, "export": export, "tmp": tmp_path}


def add(env, split, name, lines, color=0):
    img = Image.new("RGB", (64, 48), (color, 100, 100))
    img.putpixel((0, 0), (color, 1, 1))  # keep content unique so duplicate detection doesn't trigger
    img.putpixel((1, 1), (name.__hash__() % 255, 2, 2))
    img.save(env["tdir"] / "dataset" / "images" / split / f"{name}.jpg")
    (env["tdir"] / "dataset" / "labels" / split / f"{name}.txt").write_text("\n".join(lines) + "\n")


def test_validate_ok_and_detects_problems(env):
    add(env, "train", "a", ["0 0.5 0.5 0.2 0.2"], 10)
    assert env["dm"].validate() == 0
    add(env, "train", "bad1", ["9 0.5 0.5 0.2 0.2"], 20)      # unknown class id
    add(env, "train", "bad2", ["1 0.5 0.5 1.7 0.2"], 30)      # coords out of range
    add(env, "train", "bad3", ["1 0.5 0.5"], 40)              # malformed
    (env["tdir"] / "dataset" / "images" / "train" / "nolabel.jpg").write_bytes((env["tdir"] / "dataset" / "images" / "train" / "a.jpg").read_bytes() + b"\0")
    assert env["dm"].validate() == 1


def test_add_negatives_creates_empty_labels_and_is_valid(env):
    add(env, "train", "a", ["0 0.5 0.5 0.2 0.2"], 10)
    src = env["tmp"] / "notwaste"
    src.mkdir()
    for i in range(10):
        Image.new("RGB", (32, 32), (i * 20, 9, 9)).save(src / f"clean{i}.jpg")
    Image.open(src / "clean0.jpg").save(src / "dup.jpg")  # re-saved with identical bytes -> duplicate
    (src / "copy.jpg").write_bytes((src / "clean1.jpg").read_bytes())  # exact duplicate
    assert env["dm"].add_negatives(str(src), 0.7, 0.2, 0.1, 42) == 0
    bg = env["dm"].background_counts()
    assert sum(bg.values()) == 10  # both duplicates skipped
    for sp in ("train", "val", "test"):
        for img in (env["tdir"] / "dataset" / "images" / sp).glob("neg_*.jpg"):
            lbl = env["tdir"] / "dataset" / "labels" / sp / f"{img.stem}.txt"
            assert lbl.exists() and lbl.read_text() == ""
    assert env["dm"].validate() == 0  # empty labels are NOT an error
    assert env["dm"].add_negatives(str(src), 0.7, 0.2, 0.1, 42) == 1  # re-adding = all duplicates, no-op


def test_training_accepts_background_but_not_background_only(env, monkeypatch):
    import train
    importlib.reload(train)
    monkeypatch.setenv("WW_ALLOW_EMPTY_CLASSES", "1")
    add(env, "train", "a", ["0 0.5 0.5 0.2 0.2"], 10)
    add(env, "train", "neg_x", [], 70)
    (env["tdir"] / "dataset" / "labels" / "train" / "neg_x.txt").write_text("")
    add(env, "val", "b", ["0 0.5 0.5 0.2 0.2"], 60)
    train.check_dataset_ready(env["tdir"] / "data.yaml")
    (env["tdir"] / "dataset" / "labels" / "train" / "a.txt").write_text("")
    with pytest.raises(SystemExit):
        train.check_dataset_ready(env["tdir"] / "data.yaml")


def test_split_keeps_pairs_and_ratios(env):
    src_i, src_l = env["tmp"] / "si", env["tmp"] / "sl"
    src_i.mkdir(); src_l.mkdir()
    for i in range(20):
        img = Image.new("RGB", (32, 32), (i * 10, 5, 5)); img.save(src_i / f"p{i}.jpg")
        (src_l / f"p{i}.txt").write_text("1 0.5 0.5 0.3 0.3\n")
    assert env["dm"].split(str(src_i), str(src_l), 0.7, 0.2, 0.1, 42) == 0
    n = {sp: len(list((env["tdir"] / "dataset" / "images" / sp).glob("*.jpg"))) for sp in ("train", "val", "test")}
    assert sum(n.values()) == 20 and n["train"] >= 13 and n["val"] >= 3 and n["test"] >= 1
    for sp in n:  # every image has its label in the SAME split (no leakage between splits)
        for img in (env["tdir"] / "dataset" / "images" / sp).glob("*.jpg"):
            assert (env["tdir"] / "dataset" / "labels" / sp / f"{img.stem}.txt").exists()


def test_stats_and_version_change(env, capsys):
    add(env, "train", "a", ["0 0.5 0.5 0.2 0.2", "0 0.3 0.3 0.1 0.1"], 10)
    add(env, "val", "b", ["0 0.5 0.5 0.2 0.2"], 50)
    counts = env["dm"].class_counts()
    assert counts["train"][0] == {"instances": 2, "images": 1}
    assert counts["val"][0]["instances"] == 1
    v1 = env["dm"].dataset_version()
    env["dm"].stats()
    out = capsys.readouterr().out
    assert "WARNING" in out and "waste" in out  # 2 examples is far too thin and is called out
    add(env, "train", "c", ["0 0.5 0.5 0.2 0.2"], 90)
    assert env["dm"].dataset_version() != v1


def test_training_refuses_empty_dataset_and_no_waste_examples(env, monkeypatch):
    import train
    importlib.reload(train)
    data_yaml = env["tdir"] / "data.yaml"
    with pytest.raises(SystemExit):  # empty dataset
        train.check_dataset_ready(data_yaml)
    add(env, "train", "neg", [], 10)
    add(env, "val", "neg2", [], 60)
    with pytest.raises(SystemExit):  # only background (not-waste) images: nothing to learn "waste" from
        train.check_dataset_ready(data_yaml)
    add(env, "train", "a", ["0 0.5 0.5 0.2 0.2", "1 0.3 0.3 0.1 0.1", "2 0.7 0.7 0.1 0.1"], 20)  # data.yaml has 3 classes
    train.check_dataset_ready(data_yaml)  # waste + not-waste together is the intended dataset


def test_build_binary_merges_dedupes_and_balances(env, tmp_path):
    import train_classifier as tc
    wa, wb, nw = tmp_path / "wa", tmp_path / "wb" / "sub", tmp_path / "nw"
    for d in (wa, wb, nw):
        d.mkdir(parents=True)
    for i in range(30):
        Image.new("RGB", (16, 16), (i * 7, 1, 1)).save(wa / f"w{i}.jpg")
    (wb / "copy.jpg").write_bytes((wa / "w0.jpg").read_bytes())          # duplicate of a waste photo
    for i in range(5):
        Image.new("RGB", (16, 16), (1, i * 9, 200)).save(nw / f"n{i}.jpg")
    out = tc.build_binary([wa, tmp_path / "wb"], [nw], tmp_path / "out", max_ratio=2.0)
    assert len(list((out / "not_waste").glob("*.jpg"))) == 5
    assert len(list((out / "waste").glob("*.jpg"))) == 10                # balanced: at most 2x the not-waste count
    with pytest.raises(SystemExit):
        tc.build_binary([wa], [], tmp_path / "out2")                      # both classes are required


def _fake_run(env, with_eval=True, map50=0.61):
    run = env["tmp"] / "run"
    shutil.rmtree(run, ignore_errors=True)
    (run / "weights").mkdir(parents=True)
    (run / "weights" / "best.pt").write_bytes(b"fake-weights")
    (run / "results.csv").write_text("epoch,metrics/mAP50(B)\n1,0.1\n")
    (run / "run_info.json").write_text(json.dumps({"dataset_version": "abc123"}))
    (run / "eval_test").mkdir()
    (run / "eval_test" / "confusion_matrix.png").write_bytes(b"png")
    if with_eval:
        (run / "evaluation.json").write_text(json.dumps({
            "split": "test", "images": 40, "dataset_version": "abc123", "precision": 0.7, "recall": 0.6,
            "map50": map50, "map5095": 0.35, "per_class": {"plastic": {"ap50": 0.5}}}))
    return run


def test_export_refuses_without_evaluation(env):
    run = _fake_run(env, with_eval=False)
    assert env["export"].main(["--run", str(run), "--version", "v1"]) == 1
    assert not (env["root"] / "backend" / "models" / "model_versions.json").exists()


def test_export_registers_versioned_folder_with_real_metrics(env):
    run = _fake_run(env)
    assert env["export"].main(["--run", str(run), "--version", "v1", "--notes", "first"]) == 0
    models = env["root"] / "backend" / "models"
    reg = json.loads((models / "model_versions.json").read_text())
    assert len(reg) == 1 and reg[0]["version"] == "v1" and reg[0]["map50"] == 0.61
    assert reg[0]["dataset_version"] == "abc123" and reg[0]["metrics_split"] == "test" and reg[0]["deployed"] is False
    assert reg[0]["path"] == "backend/models/wastewatch_v1/best.pt"
    folder = models / "wastewatch_v1"
    assert (folder / "best.pt").exists() and (folder / "confusion_matrix.png").exists() and (folder / "metrics.json").exists()
    assert not (models / "best.pt").exists()  # registering does not deploy
    assert env["export"].main(["--run", str(run), "--version", "v1"]) == 1  # no overwriting a version


def test_deploy_refused_for_zero_map_and_switches_flags(env):
    assert env["export"].main(["--run", str(_fake_run(env, map50=0.0)), "--version", "v1", "--deploy"]) == 1
    assert env["export"].main(["--run", str(_fake_run(env)), "--version", "v1", "--deploy"]) == 0
    assert env["export"].main(["--run", str(_fake_run(env)), "--version", "v2", "--deploy"]) == 0
    reg = json.loads((env["root"] / "backend" / "models" / "model_versions.json").read_text())
    assert [r["deployed"] for r in reg] == [False, True]  # only one deployed at a time


def test_evaluate_report_uses_real_numbers_only():
    import evaluate

    class Box:
        mp, mr, map50, map = 0.8, 0.7, 0.65, 0.4
        ap_class_index = [1, 2]
        def class_result(self, i):
            return [(0.9, 0.8, 0.7, 0.5), (0.6, 0.5, 0.4, 0.2)][i]

    r = evaluate.build_report({0: "general_waste", 1: "plastic", 2: "paper"}, Box(), "test", 33, "v9")
    assert r["map50"] == 0.65 and r["images"] == 33 and r["dataset_version"] == "v9"
    assert set(r["per_class"]) == {"plastic", "paper"}  # classes absent from the split are not invented
    assert r["per_class"]["paper"]["ap50"] == 0.4


def test_scene_binary_splits_by_source_photo(tmp_path):
    """A photo and the background crops taken from it must never be spread across splits."""
    import build_scene_binary as b
    imgs, labs = tmp_path / "images", tmp_path / "labels"
    imgs.mkdir(); labs.mkdir()
    for i in range(10):
        Image.new("RGB", (200, 150), (i * 20, 90, 90)).save(imgs / f"p{i}.jpg")
        (labs / f"p{i}.txt").write_text("0 0.2 0.2 0.3 0.3\n")  # waste only in the top-left corner
    out = tmp_path / "out"
    b.build(imgs, labs, out, seed=1)
    where = {}
    for f in out.rglob("*.jpg"):
        src = f.stem.split("_bg")[0]
        where.setdefault(src, set()).add(f.parts[-3])
    assert where and all(len(v) == 1 for v in where.values())
    assert any((out / "train" / "not_waste").iterdir())
