"""Generate the standalone gallery.html contact sheet for Human Pause 1.

Reads candidate sidecars written by image_download (<candidates_dir>/<work_id>/<token>.json
with a sibling <token>.jpg), embeds them as JSON, and renders a self-contained HTML+JS
page: grid grouped by work -> detail view with a 5-star auto-advancing control ->
Export button that downloads selection.json in the scripts.selection schema.
MVP: no overlay markup / compare view (spec section 9).

Also provides build_thumbnail_gallery for the remote-thumbnail curation board used in
the image_discovery stage: local-cached thumbnails with star-rating and separate select
toggle; star filter, sort (year/stars/file-size); export writes stars.json + selection.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from scripts.dates import parse_year
from scripts.museum_search import display_url


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


def build_thumbnail_gallery(cands, artist: str, *, package_root: Path | str | None = None) -> str:
    """Render a browse *board* of museum thumbnails (local-cached preferred) with rating,
    selection, filter, and sort. Stars are seeded from each candidate (persistent axis);
    `selected` always starts false (per-session). Export writes stars.json + selection.json.

    package_root, when given, is used to stat local thumbnails for the file-size sort.
    """
    root = Path(package_root) if package_root else None
    payload = []
    for i, c in enumerate(cands):
        thumb_path = getattr(c, "thumbnail_path", "")
        image_rel = thumb_path or c.thumbnail_url
        size = 0
        if thumb_path and root is not None:
            fp = root / thumb_path
            if fp.is_file():
                size = fp.stat().st_size
        payload.append({
            "work_id": c.work_id,
            "iiif_token": f"{c.museum}-{i}",
            "image_rel": image_rel,
            "source_url": c.source_url,
            "title": c.title,
            "museum": c.museum,
            "date": c.date,
            "medium": c.medium,
            "rights": c.rights,
            "qid": c.qid,
            "inst_ids": [list(pair) for pair in c.inst_ids],
            "origin": getattr(c, "origin", "discovered"),
            "stars": getattr(c, "stars", 0),
            "selected": False,
            "year": parse_year(getattr(c, "date", "") or ""),
            "bytes": size,
            "full_url": display_url(c),
        })
    data_json = json.dumps({"artist": artist, "candidates": payload}, indent=2)
    return _THUMB_TEMPLATE.replace("__ARTIST__", _escape(artist)).replace("__DATA__", data_json)


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
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById("data").textContent);
const LIKED = 4;
const state = {};  // key -> {rating}
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

function rate(n) {
  const c = DATA.candidates[current];
  const st = state[key(c)] || (state[key(c)] = {});
  st.rating = n;
  renderStars();
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
      rating: s.rating || 0,
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


_THUMB_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Curation board — __ARTIST__</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #111; color: #eee; }
  header { padding: 0.75rem 1rem; background: #1c1c1c; position: sticky; top: 0; z-index: 5;
           display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
  header strong { font-size: 1.05rem; }
  #controls label { font-size: 12px; color: #bbb; margin-right: 0.5rem; }
  #controls select { font-size: 12px; }
  #grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
          gap: 10px; padding: 1rem; }
  #grid.zoom { grid-template-columns: repeat(auto-fill, minmax(620px, 1fr)); gap: 18px; }
  .card { background: #1c1c1c; border: 2px solid transparent; border-radius: 4px; overflow: hidden; }
  .card.selected { border-color: #4a90ff; }
  .card img { width: 100%; height: 200px; object-fit: contain; background: #000; display: block; }
  #grid.zoom .card img { height: 70vh; }
  .meta { padding: 6px 8px; font-size: 12px; }
  .meta .title { font-weight: 600; }
  .meta .sub { color: #999; font-size: 11px; margin: 2px 0; }
  .badge { font-size: 10px; padding: 1px 5px; border-radius: 3px; }
  .badge.pd { background: #1d5e2a; color: #d7ffd9; }
  .badge.copy { background: #5e1d1d; color: #ffd7d7; }
  .badge.user { background: #5b3; color: #042; }
  .stars .star { font-size: 1.25rem; cursor: pointer; color: #555; }
  .stars .star.on { color: gold; }
  .selbox { font-size: 12px; cursor: pointer; color: #9bf; user-select: none; }
  a.src { color: #7aa7ff; font-size: 11px; }
  button { font-size: 0.95rem; padding: 0.4rem 0.9rem; cursor: pointer; }
  button:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
</head>
<body>
<header>
  <strong>Curation board — __ARTIST__</strong>
  <span id="count"></span>
  <span id="controls">
    <label>stars
      <select id="star-filter">
        <option value="all">all</option>
        <option value="unstarred">unstarred</option>
        <option value="1">&ge;1</option>
        <option value="2">&ge;2</option>
        <option value="3">&ge;3</option>
        <option value="4">&ge;4</option>
        <option value="5">5</option>
      </select>
    </label>
    <label><input type="checkbox" id="only-pd"> public-domain only</label>
    <label>sort
      <select id="sort">
        <option value="year">year &uarr;</option>
        <option value="stars">stars &darr;</option>
        <option value="bytes">file size</option>
      </select>
    </label>
  </span>
  <button id="export">Export stars + selection</button>
  <button id="next">Next &rarr; zoom</button>
  <button id="back" style="display:none">&larr; Back</button>
  <button id="commit" style="display:none" disabled>Commit study set</button>
  <span id="status"></span>
</header>
<div id="grid"></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById("data").textContent);
const MAX_STUDY = 4;
// Persistent star axis (seeded) and per-session selection axis (starts empty) — orthogonal.
const stars = {};
const selected = {};
function seedStars() {
  DATA.candidates.forEach(c => { stars[c.iiif_token] = c.stars || 0; });
}
seedStars();

let stage = 1;          // 1 = board (wide scan), 2 = zoom (close look)
let wideCut = [];       // tokens frozen on Next — the session record, not mutated in stage 2

const starFilter = document.getElementById("star-filter");
const onlyPd = document.getElementById("only-pd");
const sortBy = document.getElementById("sort");
const grid = document.getElementById("grid");
const nextBtn = document.getElementById("next");
const backBtn = document.getElementById("back");
const commitBtn = document.getElementById("commit");
const exportBtn = document.getElementById("export");

function passStarFilter(c) {
  const v = starFilter.value;
  const s = stars[c.iiif_token] || 0;
  if (v === "all") return true;
  if (v === "unstarred") return s === 0;
  return s >= parseInt(v, 10);
}

function boardRows() {
  let rows = DATA.candidates.filter(c => {
    if (!passStarFilter(c)) return false;
    if (onlyPd.checked && c.rights !== "public_domain") return false;
    return true;
  });
  const mode = sortBy.value;
  rows = rows.slice().sort((a, b) => {
    if (mode === "stars") return (stars[b.iiif_token]||0) - (stars[a.iiif_token]||0);
    if (mode === "bytes") return (b.bytes||0) - (a.bytes||0);
    const ay = a.year == null ? Infinity : a.year;
    const by = b.year == null ? Infinity : b.year;
    return ay - by;
  });
  return rows;
}

function cardHtml(c, zoom) {
  const tok = c.iiif_token;
  const s = stars[tok] || 0;
  const pd = c.rights === "public_domain";
  const src = zoom ? c.full_url : c.image_rel;
  const fallback = zoom ? ' onerror="this.onerror=null;this.src=\\'' + c.image_rel + '\\'"' : '';
  let starHtml = "";
  for (let n = 1; n <= 5; n++)
    starHtml += '<span class="star' + (n <= s ? " on" : "") +
             '" data-star="' + n + '" data-tok="' + tok + '">\\u2605</span>';
  return '<img loading="lazy" src="' + src + '"' + fallback + ' alt="">' +
    '<div class="meta">' +
      '<div class="title">' + c.title + '</div>' +
      '<div class="sub">' + c.museum + ' \\u00b7 ' + (c.date || "n.d.") + ' ' +
        '<span class="badge ' + (pd ? "pd" : "copy") + '">' + (pd ? "PD" : "\\u00a9") + '</span>' +
        (c.origin === "user" ? '<span class="badge user">USER</span>' : '') + '</div>' +
      '<div class="stars">' + starHtml + '</div>' +
      '<label class="selbox"><input type="checkbox" data-select="' + tok + '"' +
        (selected[tok] ? " checked" : "") + '> select</label>' +
      '<a class="src" href="' + c.source_url + '" target="_blank">source \\u2197</a>' +
    '</div>';
}

function renderBoard() {
  grid.className = "";
  grid.innerHTML = "";
  const shown = boardRows();
  const selCount = Object.values(selected).filter(Boolean).length;
  document.getElementById("count").textContent =
    DATA.candidates.length + " works \\u00b7 " + selCount + " selected \\u00b7 " + shown.length + " shown";
  shown.forEach(c => {
    const card = document.createElement("div");
    card.className = "card" + (selected[c.iiif_token] ? " selected" : "");
    card.innerHTML = cardHtml(c, false);
    grid.appendChild(card);
  });
  bind();
}

function renderZoom() {
  grid.className = "zoom";
  grid.innerHTML = "";
  const rows = DATA.candidates.filter(c => wideCut.includes(c.iiif_token));
  const narrow = rows.filter(c => selected[c.iiif_token]).length;
  document.getElementById("count").textContent =
    "zoom \\u00b7 " + wideCut.length + " in wide cut \\u00b7 " + narrow + " study set (max " + MAX_STUDY + ")";
  rows.forEach(c => {
    const card = document.createElement("div");
    card.className = "card" + (selected[c.iiif_token] ? " selected" : "");
    card.innerHTML = cardHtml(c, true);
    grid.appendChild(card);
  });
  commitBtn.disabled = !(narrow >= 1 && narrow <= MAX_STUDY);
  bind();
}

function render() { stage === 2 ? renderZoom() : renderBoard(); }

function bind() {
  document.querySelectorAll(".star").forEach(el => {
    el.onclick = () => { stars[el.dataset.tok] = parseInt(el.dataset.star, 10); render(); };
  });
  document.querySelectorAll("[data-select]").forEach(el => {
    el.onchange = () => { selected[el.dataset.select] = el.checked; render(); };
  });
}

starFilter.onchange = render;
onlyPd.onchange = render;
sortBy.onchange = render;

nextBtn.onclick = () => {
  wideCut = DATA.candidates.filter(c => selected[c.iiif_token]).map(c => c.iiif_token);
  if (!wideCut.length) { document.getElementById("status").textContent = " select at least one work first"; return; }
  stage = 2;
  nextBtn.style.display = "none"; exportBtn.style.display = "none";
  backBtn.style.display = ""; commitBtn.style.display = "";
  render();
};

backBtn.onclick = () => {
  stage = 1; wideCut = [];
  backBtn.style.display = "none"; commitBtn.style.display = "none";
  nextBtn.style.display = ""; exportBtn.style.display = "";
  render();
};

function download(name, obj) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], {type: "application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
}

function exportStars() {
  const rows = DATA.candidates.map(c => ({work_id: c.work_id, stars: stars[c.iiif_token] || 0}));
  download("stars.json", {artist: DATA.artist, stars: rows});
}

function exportSelection(selectedTokens) {
  const set = new Set(selectedTokens);
  const ratings = DATA.candidates.map(c => ({
    work_id: c.work_id, iiif_token: c.iiif_token, image_rel: c.image_rel,
    title: c.title, date: c.date, medium: c.medium,
    source_url: c.source_url, museum: c.museum, rights: c.rights,
    qid: c.qid, inst_ids: c.inst_ids,
    selected: set.has(c.iiif_token), stars: stars[c.iiif_token] || 0,
  }));
  download("selection.json", {artist: DATA.artist, ratings});
}

exportBtn.onclick = () => {
  const live = DATA.candidates.filter(c => selected[c.iiif_token]).map(c => c.iiif_token);
  exportStars();
  exportSelection(live);
  document.getElementById("status").textContent = " saved stars.json + selection.json";
};

commitBtn.onclick = () => {
  // wide cut = frozen snapshot (session record); narrow = still-selected within it (<= MAX_STUDY).
  const narrowTokens = wideCut.filter(t => selected[t]);
  if (!(narrowTokens.length >= 1 && narrowTokens.length <= MAX_STUDY)) return;
  const tokenToWid = {};
  DATA.candidates.forEach(c => { tokenToWid[c.iiif_token] = c.work_id; });
  exportStars();
  exportSelection(wideCut);
  download("study-set.json", {artist: DATA.artist, study_set: narrowTokens.map(t => tokenToWid[t])});
  document.getElementById("status").textContent =
    " saved stars.json + selection.json + study-set.json (" + narrowTokens.length + " to study)";
};

render();
</script>
</body>
</html>
"""
