"""Generate the standalone gallery.html contact sheet for Human Pause 1.

Reads candidate sidecars written by image_download (<candidates_dir>/<work_id>/<token>.json
with a sibling <token>.jpg), embeds them as JSON, and renders a self-contained HTML+JS
page: grid grouped by work -> detail view with a 5-star auto-advancing control -> a
curatorial gate revealed at >=4* -> Export button that downloads selection.json in the
scripts.selection schema. MVP: no overlay markup / compare view (spec section 9).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

LIKED_THRESHOLD = 4


@dataclass(frozen=True)
class CandidateView:
    work_id: str
    token: str
    image_rel: str
    meta: dict


def load_candidate_sidecars(candidates_dir: Path | str) -> list[CandidateView]:
    """Pair every <work>/<token>.json sidecar with its sibling .jpg; sorted, stable."""
    candidates_dir = Path(candidates_dir)
    views: list[CandidateView] = []
    for meta_path in sorted(candidates_dir.glob("*/*.json")):
        image_path = meta_path.with_suffix(".jpg")
        if not image_path.is_file():
            continue
        work_id = meta_path.parent.name
        token = meta_path.stem
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        views.append(
            CandidateView(
                work_id=work_id,
                token=token,
                image_rel=f"images/candidates/{work_id}/{token}.jpg",
                meta=meta,
            )
        )
    return views


def build_gallery_html(views: list[CandidateView], artist: str) -> str:
    """Render the self-contained gallery page from candidate views."""
    payload = [
        {
            "work_id": v.work_id,
            "iiif_token": v.token,
            "image_rel": v.image_rel,
            "institution": v.meta.get("institution", ""),
            "label": v.meta.get("label", ""),
            "width": v.meta.get("width", 0),
            "height": v.meta.get("height", 0),
            "license": v.meta.get("license", ""),
            "rights_status": v.meta.get("rights_status", ""),
        }
        for v in views
    ]
    data_json = json.dumps({"artist": artist, "candidates": payload}, indent=2)
    return _TEMPLATE.replace("__ARTIST__", _escape(artist)).replace("__DATA__", data_json)


def write_gallery(candidates_dir: Path | str, artist: str, out_path: Path | str) -> Path:
    """Build the gallery from sidecars and write it to out_path."""
    out_path = Path(out_path)
    views = load_candidate_sidecars(candidates_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_gallery_html(views, artist), encoding="utf-8")
    return out_path


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Curation gallery — __ARTIST__</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #111; color: #eee; }
  header { padding: 1rem; background: #1c1c1c; position: sticky; top: 0; }
  #grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; padding: 1rem; }
  .card { background: #1c1c1c; border: 2px solid transparent; cursor: pointer; }
  .card.liked { border-color: gold; }
  .card img { width: 100%; display: block; }
  .meta { font-size: 11px; padding: 4px; color: #aaa; }
  #detail { display: none; padding: 1rem; }
  #detail img { max-height: 70vh; display: block; margin: 0 auto; }
  .star { font-size: 2rem; cursor: pointer; color: #555; }
  .star.on { color: gold; }
  #gate { display: none; margin-top: 1rem; }
  #gate label { display: block; margin: 0.5rem 0; }
  #gate input, #gate textarea { width: 100%; background: #222; color: #eee; border: 1px solid #444; }
  button { font-size: 1rem; padding: 0.5rem 1rem; margin: 0.25rem; }
</style>
</head>
<body>
<header>
  <strong>Curation gallery — __ARTIST__</strong>
  <button id="export">Export selection.json</button>
  <span id="status"></span>
</header>
<div id="grid"></div>
<div id="detail">
  <button id="back">&larr; Back to grid</button>
  <img id="detail-img" alt="">
  <div id="stars"></div>
  <div id="gate">
    <p>Rated 4&#9733;+ — record the curatorial gate before this work joins the study set:</p>
    <label>thesis (why study this)<textarea data-gate="thesis" rows="2"></textarea></label>
    <label>anchor_trait (the trait to study)<input data-gate="anchor_trait"></label>
    <label>handoff_note (note for analysis)<textarea data-gate="handoff_note" rows="2"></textarea></label>
  </div>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById("data").textContent);
const LIKED = 4;
const state = {};  // key -> {rating, thesis, anchor_trait, handoff_note}
let current = 0;

function key(c) { return c.work_id + "/" + c.iiif_token; }

function renderGrid() {
  const grid = document.getElementById("grid");
  grid.innerHTML = "";
  DATA.candidates.forEach((c, i) => {
    const s = state[key(c)] || {rating: 0};
    const card = document.createElement("div");
    card.className = "card" + (s.rating >= LIKED ? " liked" : "");
    card.innerHTML =
      '<img src="' + c.image_rel + '" loading="lazy" alt="">' +
      '<div class="meta">' + c.work_id + ' &middot; ' + c.institution +
      ' &middot; ' + c.width + '&times;' + c.height +
      ' &middot; ' + c.rights_status + ' &middot; ' + (s.rating || 0) + '&#9733;</div>';
    card.onclick = () => openDetail(i);
    grid.appendChild(card);
  });
}

function openDetail(i) {
  current = i;
  document.getElementById("grid").style.display = "none";
  document.getElementById("detail").style.display = "block";
  const c = DATA.candidates[i];
  document.getElementById("detail-img").src = c.image_rel;
  renderStars();
  renderGate();
}

function renderStars() {
  const c = DATA.candidates[current];
  const s = state[key(c)] || {rating: 0};
  const box = document.getElementById("stars");
  box.innerHTML = "";
  for (let n = 1; n <= 5; n++) {
    const star = document.createElement("span");
    star.className = "star" + (n <= s.rating ? " on" : "");
    star.setAttribute("data-star", n);
    star.textContent = "\\u2605";
    star.onclick = () => rate(n);
    box.appendChild(star);
  }
}

function renderGate() {
  const c = DATA.candidates[current];
  const s = state[key(c)] || {rating: 0};
  const gate = document.getElementById("gate");
  gate.style.display = s.rating >= LIKED ? "block" : "none";
  gate.querySelectorAll("[data-gate]").forEach(el => { el.value = s[el.dataset.gate] || ""; });
  gate.querySelectorAll("[data-gate]").forEach(el => {
    el.oninput = () => {
      const st = state[key(c)] || (state[key(c)] = {rating: s.rating});
      st[el.dataset.gate] = el.value;
    };
  });
}

function rate(n) {
  const c = DATA.candidates[current];
  const st = state[key(c)] || (state[key(c)] = {});
  st.rating = n;
  renderStars();
  renderGate();
  if (n < LIKED && current < DATA.candidates.length - 1) {
    setTimeout(() => openDetail(current + 1), 200);  // auto-advance below the gate
  }
}

document.getElementById("back").onclick = () => {
  document.getElementById("detail").style.display = "none";
  document.getElementById("grid").style.display = "grid";
  renderGrid();
};

document.getElementById("export").onclick = () => {
  const ratings = DATA.candidates.map(c => {
    const s = state[key(c)] || {rating: 0};
    return {
      work_id: c.work_id, iiif_token: c.iiif_token, image_rel: c.image_rel,
      rating: s.rating || 0, thesis: s.thesis || "",
      anchor_trait: s.anchor_trait || "", handoff_note: s.handoff_note || "",
    };
  });
  const blob = new Blob([JSON.stringify({artist: DATA.artist, ratings}, null, 2)],
                        {type: "application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "selection.json";
  a.click();
  document.getElementById("status").textContent = " saved selection.json";
};

renderGrid();
</script>
</body>
</html>
"""
