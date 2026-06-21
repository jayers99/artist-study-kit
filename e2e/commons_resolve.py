"""Re-run the funnel resolve step with the LIVE Commons resolver + real high-res download.

Reuses the package e2e/funnel_pipeline.py built (selection.json + study-set.json on disk)
and resolves the study-set works for real: skill's discover_commons (live Commons search +
eligibility) -> real download_candidate byte fetch into images/selected/.

Run first:  uv run python e2e/funnel_pipeline.py "<artist>"
Then:       uv run python e2e/commons_resolve.py "<artist>"

NOTE: discover_commons here is the *keyword* path (AIC-search candidates lack the QID
`commons_file` inst-id the precise P18 commons_resolver needs), so a generic title can
fuzzy-match a same-title-different-work file. In a real run works carry QIDs and the
QID-verified P18 resolver runs first. This harness is about proving Commons download works.
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skill"))

from scripts.paths import study_paths
from scripts.selection import load_selection, load_study_set, selected_rows
from scripts.resolve import resolve_selection
from scripts.commons import discover_commons
from scripts.image_download import download_candidate

ARTIST = sys.argv[1] if len(sys.argv) > 1 else "Claude Monet"
BASE = Path("/tmp/funnel-e2e-studies")
sp = study_paths(BASE, ARTIST)
FINDINGS = []


def check(label, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not cond:
        FINDINGS.append(label + (f" ({detail})" if detail else ""))


if not sp.study_set_json.is_file():
    print(f"no study-set.json at {sp.study_set_json} — run e2e/funnel_pipeline.py {ARTIST!r} first")
    sys.exit(1)

if sp.selected_dir.exists():
    shutil.rmtree(sp.selected_dir)
sp.selected_dir.mkdir(parents=True, exist_ok=True)

sel = load_selection(sp.selection_json, ARTIST)
study_set = load_study_set(sp.study_set_json, ARTIST)
print(f"Study set ({len(study_set)}): {study_set}\n")


def live_commons_resolver(entry, *, fetch=None):
    """Keyword Commons resolve: skill's real discover_commons; top PD candidate (>=1500px)."""
    cands = discover_commons(f"{ARTIST} {entry.title}", entry.work_id, artist=ARTIST,
                             want=1, min_long_edge=1500, include_cc=False)
    return cands[0] if cands else None


print("Resolving the study set via LIVE Commons + real download_candidate ...\n")
resolved = resolve_selection(
    sel, sp.selected_dir,
    resolvers=[live_commons_resolver],
    download=download_candidate,
    only=set(study_set),
)

for r in resolved:
    size = r.image_path.stat().st_size if (r.image_path and r.image_path.is_file()) else 0
    loc = str(r.image_path.relative_to(sp.root)) if r.image_path else "(no local file)"
    print(f"  {r.work_id}: {r.rights} | {loc} | {size:,} bytes")
    print(f"       {r.image_url}")

print("\nInvariants")
check("resolved exactly the study set (only= bound held)",
      sorted(x.work_id for x in resolved) == sorted(study_set))
check("every study work resolved to public_domain", all(x.rights == "public_domain" for x in resolved))
check("every study work has a real local high-res file on disk",
      all(x.image_path and x.image_path.is_file() for x in resolved))
check("downloaded files are substantial high-res (>200 KB each)",
      all(x.image_path and x.image_path.stat().st_size > 200_000 for x in resolved),
      "sizes=" + ", ".join(f"{(x.image_path.stat().st_size // 1024) if x.image_path else 0}KB" for x in resolved))
manifest = sp.selected_dir / "resolved.json"
check("resolved.json manifest written", manifest.is_file())
if manifest.is_file():
    man = json.loads(manifest.read_text())
    check("manifest covers the study set", sorted(m["work_id"] for m in man) == sorted(study_set))

print("\n=== RESULT ===")
if FINDINGS:
    print(f"{len(FINDINGS)} finding(s):")
    for f in FINDINGS:
        print("  -", f)
    sys.exit(1)
print("Live Commons resolve produced real high-res PD files for the study set.")
print(f"Selected dir: {sp.selected_dir}")
