import os
from dataclasses import dataclass
from pathlib import Path

from scripts.image_manifest import ManifestEntry
from scripts.dedup import DedupAction
from scripts.library import execute_action, _abs


def _spy(record):
    def fn(src, dst=None):
        record.append((str(src), str(dst)) if dst is not None else (str(src),))
        if dst is None:          # delete
            os.remove(src)
        else:                    # move
            os.replace(src, dst)
    return fn


def _entry(work_id, cn):
    return ManifestEntry(work_id=work_id, filename=cn, path=f"images/library/{cn}")


def test_add_moves_incoming_into_library(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "A")
    inc = sp.incoming_dir / "x.jpg"; inc.write_bytes(b"img")
    action = DedupAction(kind="add", keep_path=str(inc), delete_path=None,
                         canonical_name="the-vase.jpg", entry=_entry("the-vase", "the-vase.jpg"))
    moves, deletes = [], []
    entry = execute_action(action, sp, move=_spy(moves), delete=_spy(deletes))
    assert (sp.library_dir / "the-vase.jpg").is_file()
    assert not inc.exists()
    assert deletes == []
    assert entry.path == "images/library/the-vase.jpg"


def test_merge_incoming_wins_replaces_old_library_file(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "A")
    old = sp.library_dir / "old.jpg"; old.write_bytes(b"small")
    inc = sp.incoming_dir / "big.jpg"; inc.write_bytes(b"bigimg")
    action = DedupAction(kind="merge", keep_path=str(inc),
                         delete_path="images/library/old.jpg",
                         canonical_name="old.jpg", entry=_entry("w", "old.jpg"))
    moves, deletes = [], []
    execute_action(action, sp, move=_spy(moves), delete=_spy(deletes))
    assert (sp.library_dir / "old.jpg").read_bytes() == b"bigimg"   # winner overwrote
    assert not inc.exists()
    # delete_path == destination -> no separate delete
    assert deletes == []


def test_merge_existing_wins_deletes_incoming(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "A")
    lib = sp.library_dir / "keep.jpg"; lib.write_bytes(b"bigimg")
    inc = sp.incoming_dir / "small.jpg"; inc.write_bytes(b"sm")
    action = DedupAction(kind="merge", keep_path="images/library/keep.jpg",
                         delete_path=str(inc), canonical_name="keep.jpg",
                         entry=_entry("w", "keep.jpg"))
    moves, deletes = [], []
    execute_action(action, sp, move=_spy(moves), delete=_spy(deletes))
    assert lib.read_bytes() == b"bigimg"      # untouched
    assert not inc.exists()                   # incoming deleted
    assert moves == []                        # no move (keep == dest)


def test_existing_wins_with_rename_moves_within_library(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "A")
    lib = sp.library_dir / "img001.jpg"; lib.write_bytes(b"big")
    inc = sp.incoming_dir / "s.jpg"; inc.write_bytes(b"s")
    action = DedupAction(kind="merge", keep_path="images/library/img001.jpg",
                         delete_path=str(inc), canonical_name="still-life.jpg",
                         entry=_entry("w", "still-life.jpg"))
    execute_action(action, sp, move=lambda s, d: os.replace(s, d), delete=os.remove)
    assert (sp.library_dir / "still-life.jpg").read_bytes() == b"big"
    assert not lib.exists() and not inc.exists()


def test_delete_only_targets_inside_package(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "A")
    inc = sp.incoming_dir / "x.jpg"; inc.write_bytes(b"i")
    action = DedupAction(kind="add", keep_path=str(inc), delete_path=None,
                         canonical_name="x.jpg", entry=_entry("x", "x.jpg"))
    deletes = []
    execute_action(action, sp, move=lambda s, d: os.replace(s, d), delete=_spy(deletes))
    assert deletes == []  # add never deletes


from PIL import Image, ImageDraw
from scripts.image_manifest import Manifest
from scripts.library import make_incoming, build_library


def _img(path, seed=0, size=(256, 256)):
    im = Image.new("RGB", size, "white"); d = ImageDraw.Draw(im)
    cw, ch = size[0] // 4, size[1] // 4
    for i in range(4):
        for j in range(4):
            v = (seed * 37 + (i * 4 + j) * 53) % 256
            d.rectangle([i*cw, j*ch, (i+1)*cw, (j+1)*ch], fill=(v, (v*2) % 256, (v*3) % 256))
    im.save(path); return path


def test_make_incoming_none_on_garbage(tmp_path):
    bad = tmp_path / "bad.jpg"; bad.write_bytes(b"nope")
    assert make_incoming(bad, source="user-seed") is None


def test_make_incoming_builds_from_real_image(tmp_path):
    p = _img(tmp_path / "a.png", seed=1, size=(200, 120))
    inc = make_incoming(p, source="aic", title="A", qid="Q1")
    assert inc.width == 200 and inc.height == 120 and inc.bytes > 0
    assert inc.source == "aic" and inc.title == "A" and inc.qid == "Q1"


def test_build_library_collapses_same_work_keeps_larger(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "A")
    big = _img(sp.incoming_dir / "big.png", seed=2, size=(400, 400))
    small_src = _img(tmp_path / "small_src.png", seed=2, size=(200, 200))  # same pattern, smaller
    small = sp.incoming_dir / "small.png"; Image.open(small_src).save(small)
    m = Manifest()
    inc = [make_incoming(big, source="aic", title="Vase"),
           make_incoming(small, source="commons", title="Vase")]
    summary = build_library(inc, m, sp, run_id="run1")
    assert summary.added == 1 and (summary.merged_kept + summary.merged_replaced) == 1
    assert len(m.entries) == 1
    # larger (400x400) wins
    assert m.entries[0].width == 400
    libfiles = list(sp.library_dir.glob("*.png"))
    assert len(libfiles) == 1
    assert not list(sp.incoming_dir.glob("*.png"))  # both consumed


def test_build_library_cross_run_merges_against_manifest(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "A")
    first = _img(sp.incoming_dir / "f.png", seed=3, size=(300, 300))
    m = Manifest()
    build_library([make_incoming(first, source="aic", title="W")], m, sp, run_id="r1")
    # later run: bigger copy of the same work
    bigger = _img(sp.incoming_dir / "f2.png", seed=3, size=(600, 600))
    s2 = build_library([make_incoming(bigger, source="commons", title="W")], m, sp, run_id="r2")
    assert s2.merged_replaced == 1 and len(m.entries) == 1 and m.entries[0].width == 600
