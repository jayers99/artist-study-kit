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
