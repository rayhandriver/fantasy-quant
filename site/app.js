/* Team Book — a static, hash-routed reader over site/data/*.json. No build step, no framework.
 *
 * Routes:  #/                        every team, by division
 *          #/CHI/2025/defense        one team-season, one tab
 *
 * Everything rendered comes from the registry in index.json, so a metric added in Python
 * (teambook/metrics.py) shows up here without a code change. Strings from data are always set
 * with textContent, never as HTML.
 */
"use strict";

const TABS = [
  ["overview", "Overview"], ["offense", "Offense"], ["defense", "Defense"],
  ["special", "Special teams and roster"], ["players", "Players"],
  ["coaching", "Coaching and comps"], ["trends", "Trends"], ["notes", "Data notes"],
];
const TREND_PICKS = {
  offense: ["epa_per_play", "pass_rate_neutral", "pass_oe_mean", "shotgun_rate", "share_p11",
            "share_p12", "motion_rate", "play_action_rate"],
  defense: ["def_epa_per_play", "def_success_rate", "man_share", "share_cover_3",
            "share_cover_1", "blitz_rate", "pressure_rate", "share_nickel"],
  special: ["fourth_go_rate", "fg_pct", "cap_share_qb", "continuity_offense"],
};
const state = { index: null, reg: null, byKey: {}, cache: new Map() };

// --- tiny DOM helpers ---------------------------------------------------------------------------
const $ = (sel, el = document) => el.querySelector(sel);
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid == null || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}
const SVGNS = "http://www.w3.org/2000/svg";
function s(tag, attrs, ...kids) {
  const el = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid == null) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

async function get(path) {
  if (!state.cache.has(path)) {
    state.cache.set(path, fetch(path).then(r => {
      if (!r.ok) throw new Error(`${path}: ${r.status}`);
      return r.json();
    }));
  }
  return state.cache.get(path);
}

// --- formatting --------------------------------------------------------------------------------
const ord = n => n + (n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th"));
const minus = t => t.replace(/^-/, "−");
function fmt(m, v) {
  if (v == null || Number.isNaN(v)) return "—";
  switch (m.fmt) {
    case "pct": return (v * 100).toFixed(1) + "%";
    case "rate3": return minus(v.toFixed(3));
    case "num2": return minus(v.toFixed(2));
    case "signed1": return (v > 0 ? "+" : "") + minus(v.toFixed(1));
    case "int": return Math.round(v).toLocaleString();
    default: return Math.abs(v) >= 100 ? Math.round(v).toLocaleString() : minus(v.toFixed(1));
  }
}
const pct = (v, d = 0) => (v == null ? "—" : (v * 100).toFixed(d) + "%");
const num = (v, d = 0) => (v == null ? "—" : minus(Number(v).toFixed(d)));

function rankText(m, rank, n) {
  if (m.polarity !== 0) return [ord(rank), ` of ${n}`];
  if (rank === 1) return ["Highest", ""];
  if (rank === n) return ["Lowest", ""];
  return rank <= n / 2 ? [`${ord(rank)} highest`, ""] : [`${ord(n - rank + 1)} lowest`, ""];
}
function rankBadge(m, cell) {
  let cls = "b-mid";
  if (m.polarity !== 0) cls = cell.rank <= 8 ? "b-good" : cell.rank > cell.n - 8 ? "b-bad" : "b-mid";
  const [a, b] = rankText(m, cell.rank, cell.n);
  const title = m.polarity !== 0 ? "Ranked so that 1st is the best in the league" : "This is a tendency, so a high or low rank is not good or bad";
  return h("span", { class: `badge ${cls}`, title }, a, b ? h("span", { class: "of" }, b) : null);
}

function whyMissing(m, season, status) {
  if (season < m.floor) return m.source === "ftn" ? `FTN started charting this in ${m.floor}.` : `This was first charted in ${m.floor}.`;
  if (m.ceiling != null && season > m.ceiling) return `The data stopped using this formation label after ${m.ceiling}.`;
  if (status.unavailable[m.source]) {
    return m.source === "participation" ? "These stats will be added once nflverse publishes this season's participation data." : status.unavailable[m.source];
  }
  return "There is no data for this team in this season.";
}

// --- tooltip -----------------------------------------------------------------------------------
const tip = () => $("#tip");
function showTip(ev, nodes) {
  const t = tip();
  t.replaceChildren(...nodes);
  t.classList.add("on");
  let x, y;
  if (ev.clientX != null && ev.type !== "focus") { x = ev.clientX; y = ev.clientY; }
  else { const r = ev.currentTarget.getBoundingClientRect(); x = r.left + r.width / 2; y = r.top; }
  const w = t.offsetWidth, hgt = t.offsetHeight;
  t.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, x + 12)) + "px";
  t.style.top = Math.max(8, y - hgt - 12) + "px";
}
const hideTip = () => tip().classList.remove("on");
const tipRow = (value, label, color) => h("div", { class: "row" },
  color ? h("span", { class: "k", style: `background:${color}` }) : null,
  h("span", { class: "tv" }, value), h("span", null, label));

// --- charts ------------------------------------------------------------------------------------
/** League strip: every team a dot, the median a tick, this team the accent dot. */
function strip(m, league, team) {
  const c = league.metrics[m.key];
  const W = 260, H = 30, pad = 8;
  const lo = c.min, hi = c.max, span = hi - lo || 1;
  const x = v => pad + ((v - lo) / span) * (W - 2 * pad);
  const teams = Object.entries(c.values).sort((a, b) => a[1] - b[1]);
  const svg = s("svg", { class: "strip", viewBox: `0 0 ${W} ${H}`,
    role: "img", "aria-label": `${m.label}: league range ${fmt(m, lo)} to ${fmt(m, hi)}, median ${fmt(m, c.median)}` });
  svg.append(s("line", { x1: pad, x2: W - pad, y1: 13, y2: 13, class: "axis" }));
  for (const [t, v] of teams) if (t !== team) svg.append(s("circle", { cx: x(v), cy: 13, r: 3, class: "pd" }));
  svg.append(s("line", { x1: x(c.median), x2: x(c.median), y1: 5, y2: 21, class: "pmed" }));
  if (team in c.values) svg.append(s("circle", { cx: x(c.values[team]), cy: 13, r: 5, class: "pme" }));
  svg.append(s("text", { x: pad, y: 29, class: "tick" }, fmt(m, lo)));
  svg.append(s("text", { x: W - pad, y: 29, class: "tick end" }, fmt(m, hi)));
  const hit = s("rect", { x: 0, y: 0, width: W, height: H, class: "hit" });
  hit.addEventListener("pointermove", ev => {
    const r = svg.getBoundingClientRect();
    const vx = lo + ((ev.clientX - r.left) / r.width * W - pad) / (W - 2 * pad) * span;
    let best = teams[0];
    for (const tv of teams) if (Math.abs(tv[1] - vx) < Math.abs(best[1] - vx)) best = tv;
    const rank = c.rank[best[0]];
    showTip(ev, [tipRow(fmt(m, best[1]), `${best[0]}${best[0] === team ? " (this team)" : ""}`),
                 h("div", null, `Ranked ${ord(rank)} of ${c.n}, league median ${fmt(m, c.median)}`)]);
  });
  hit.addEventListener("pointerleave", hideTip);
  svg.append(hit);
  return svg;
}

/** Line chart over seasons: this team vs the league median, crosshair tooltip. */
function seasonLine(m, rows, { small = false, live = null } = {}) {
  const W = small ? 260 : 720, H = small ? 120 : 260;
  const L = small ? 34 : 52, R = small ? 10 : 24, T = 12, B = 24;
  const seasons = rows.map(r => r[0]);
  const vals = rows.flatMap(r => [r[1], r[2]]);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const padv = (hi - lo || Math.abs(hi) || 1) * 0.12; lo -= padv; hi += padv;
  const s0 = Math.min(...seasons), s1 = Math.max(...seasons);
  const x = sn => L + (s1 === s0 ? (W - L - R) / 2 : ((sn - s0) / (s1 - s0)) * (W - L - R));
  const y = v => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const svg = s("svg", { class: "chart", viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": `${m.label} by season, this team against the league median` });
  const ticks = small ? 3 : 4;
  for (let i = 0; i <= ticks; i++) {
    const v = lo + (i / ticks) * (hi - lo);
    svg.append(s("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), class: "grid" }));
    svg.append(s("text", { x: L - 6, y: y(v) + 3, class: "tick end" }, fmt(m, v)));
  }
  for (const sn of seasons) {
    if (small && seasons.length > 5 && sn % 2 === 1) continue;
    svg.append(s("text", { x: x(sn), y: H - 6, class: "tick mid" }, small ? `'${String(sn).slice(2)}` : sn));
  }
  const path = idx => rows.map((r, i) => `${i ? "L" : "M"}${x(r[0]).toFixed(1)},${y(r[idx]).toFixed(1)}`).join("");
  svg.append(s("path", { d: path(2), class: "l-med" }));
  svg.append(s("path", { d: path(1), class: "l-team" }));
  for (const r of rows) {
    const isLive = live && r[0] === live.season && !live.complete;
    svg.append(s("circle", { cx: x(r[0]), cy: y(r[1]), r: small ? 3.5 : 4.5, class: isLive ? "d-live" : "d-team" }));
  }
  const last = rows[rows.length - 1];
  if (!small && live && last[0] === live.season && !live.complete) {
    svg.append(s("text", { x: x(last[0]), y: y(last[1]) - 10, class: "lab", "text-anchor": "end" }, `through week ${live.through_week}`));
  }
  const xh = s("line", { y1: T, y2: H - B, class: "xhair", visibility: "hidden" });
  svg.append(xh);
  const hit = s("rect", { x: L, y: 0, width: W - L - R, height: H, class: "hit" });
  hit.addEventListener("pointermove", ev => {
    const rect = svg.getBoundingClientRect();
    const px = (ev.clientX - rect.left) / rect.width * W;
    let best = rows[0];
    for (const r of rows) if (Math.abs(x(r[0]) - px) < Math.abs(x(best[0]) - px)) best = r;
    xh.setAttribute("x1", x(best[0])); xh.setAttribute("x2", x(best[0])); xh.setAttribute("visibility", "visible");
    const isLive = live && best[0] === live.season && !live.complete;
    showTip(ev, [h("div", null, `${best[0]}${isLive ? ` through week ${live.through_week}` : ""}`),
      tipRow(fmt(m, best[1]), `${ord(best[3])} of ${best[4]}`, "var(--accent)"),
      tipRow(fmt(m, best[2]), "league median", "var(--median)")]);
  });
  hit.addEventListener("pointerleave", () => { xh.setAttribute("visibility", "hidden"); hideTip(); });
  svg.append(hit);
  return svg;
}

/** Weekly results: one column per game, height = point margin, diverging blue (win) / red (loss). */
function weeklyChart(book) {
  const weeks = book.weekly;
  if (!weeks.length) return h("p", { class: "muted" }, "No games played yet.");
  const lastWeek = Math.max(...weeks.map(w => w.week), ...book.meta.bye_weeks);
  const W = 720, H = 230, L = 40, R = 10, T = 14, B = 34;
  const step = Math.max(7, ...weeks.map(w => Math.abs(w.pf - w.pa))) > 21 ? 14 : 7;
  const span = step * Math.ceil(Math.max(7, ...weeks.map(w => Math.abs(w.pf - w.pa))) / step);
  const band = (W - L - R) / lastWeek;
  const bw = Math.min(24, band - 6);
  const x = wk => L + (wk - 0.5) * band;
  const y = v => T + (1 - (v + span) / (2 * span)) * (H - T - B);
  const svg = s("svg", { class: "chart", viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": "Point margin by week; columns above the line are wins" });
  for (let vv = -span; vv <= span; vv += step) {
    if (vv === 0) continue;
    svg.append(s("line", { x1: L, x2: W - R, y1: y(vv), y2: y(vv), class: "grid" }));
    svg.append(s("text", { x: L - 6, y: y(vv) + 3, class: "tick end" }, (vv > 0 ? "+" : "") + minus(String(vv))));
  }
  svg.append(s("line", { x1: L, x2: W - R, y1: y(0), y2: y(0), class: "axis" }));
  for (let wk = 1; wk <= lastWeek; wk++) {
    svg.append(s("text", { x: x(wk), y: H - 18, class: "tick mid" }, wk));
    if (book.meta.bye_weeks.includes(wk)) svg.append(s("text", { x: x(wk), y: y(0) - 6, class: "tick mid" }, "bye"));
  }
  svg.append(s("text", { x: L, y: H - 3, class: "tick" }, "week"));
  for (const w of weeks) {
    const margin = w.pf - w.pa;
    const top = y(Math.max(margin, 0)), bot = y(Math.min(margin, 0));
    const hgt = Math.max(2, bot - top), r = Math.min(4, hgt / 2);
    const x0 = x(w.week) - bw / 2;
    // rounded data-end, square at the baseline
    const d = margin >= 0
      ? `M${x0},${bot}V${top + r}Q${x0},${top} ${x0 + r},${top}H${x0 + bw - r}Q${x0 + bw},${top} ${x0 + bw},${top + r}V${bot}Z`
      : `M${x0},${top}V${bot - r}Q${x0},${bot} ${x0 + r},${bot}H${x0 + bw - r}Q${x0 + bw},${bot} ${x0 + bw},${bot - r}V${top}Z`;
    const g = s("g", { class: "hov", tabindex: 0, role: "img",
      "aria-label": `Week ${w.week} ${w.home ? "vs" : "at"} ${w.opponent}, ${w.pf} to ${w.pa}` });
    g.append(s("path", { d, class: margin >= 0 ? "bar-pos" : "bar-neg" }));
    g.append(s("rect", { x: x(w.week) - band / 2, y: T, width: band, height: H - T - B, class: "hit" }));
    const res = margin > 0 ? "W" : margin < 0 ? "L" : "T";
    const show = ev => showTip(ev, [
      h("div", null, `Week ${w.week} ${w.home ? "vs" : "at"} ${w.opponent}`),
      tipRow(`${res} ${w.pf}–${w.pa}`, ""),
      h("div", null, `EPA per play ${num(w.epa_per_play, 3)}, allowed ${num(w.def_epa_per_play, 3)}`),
      h("div", null, `Pass rate ${pct(w.pass_rate)}, ${pct(w.pass_rate_neutral)} in neutral situations`)]);
    g.addEventListener("pointermove", show); g.addEventListener("focus", show);
    g.addEventListener("pointerleave", hideTip); g.addEventListener("blur", hideTip);
    svg.append(g);
  }
  return svg;
}

function tableView(head, rows) {
  return h("details", { class: "note" }, h("summary", null, "Show as a table"),
    h("div", { class: "tw" }, h("table", null,
      h("thead", null, h("tr", null, head.map(c => h("th", null, c)))),
      h("tbody", null, rows.map(r => h("tr", null, r.map(c => h("td", null, c))))))));
}

// --- views -------------------------------------------------------------------------------------
function chipInk(hex) {
  const n = parseInt((hex || "#888888").slice(1), 16);
  const lin = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  const L = 0.2126 * lin(n >> 16 & 255) + 0.7152 * lin(n >> 8 & 255) + 0.0722 * lin(n & 255);
  return L > 0.179 ? "#0b0b0b" : "#ffffff";   // the contrast break-even, not 0.5
}
const chip = (abbr) => {
  const c = state.index.teams[abbr]?.color || "#888888";
  return h("span", { class: "chip", style: `background:${c};color:${chipInk(c)}` }, abbr);
};
function teamName(t) { return state.index.teams[t]?.name || t; }
function seasonInfo(season) { return state.index.seasons.find(x => x.season === season); }
function defaultSeason() { return (state.index.seasons.find(x => x.complete) || state.index.seasons[0]).season; }

function renderHome() {
  document.title = "NFL Team Book";
  const app = $("#app");
  const live = seasonInfo(state.index.live_season);
  const byDiv = {};
  for (const [abbr, t] of Object.entries(state.index.teams)) (byDiv[t.division] ||= []).push([abbr, t]);
  const season = defaultSeason();
  app.replaceChildren(
    h("section", { class: "hero" },
      h("h1", null, "NFL Team Book"),
      h("p", null, "This site breaks down how every NFL team has played since 2018. Each team has a page for every season with its personnel groupings, formations, play calling tendencies, coverage and pressure numbers, and the players who were on the field the most. Every number is ranked against the rest of the league, and each page lists the five team seasons from other franchises that played the most similar style."),
      h("p", null, live && !live.complete
        ? `The ${live.season} season updates every week and currently runs through week ${live.through_week}. Personnel and coverage data are released after the season ends, so the ${live.season} pages only show what can be measured from play by play and FTN charting until then.`
        : "All numbers are from the regular season and come from nflverse play by play data and FTN charting."),
      h("p", { class: "muted" }, `Last updated ${new Date(state.index.generated_at).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}.`)),
    h("div", { class: "divs" }, Object.keys(byDiv).sort().map(div =>
      h("div", { class: "div" }, h("h3", null, div),
        byDiv[div].sort((a, b) => a[1].name.localeCompare(b[1].name)).map(([abbr, t]) =>
          h("a", { class: "tlink", href: `#/${abbr}/${season}/overview` },
            chip(abbr),
            h("span", { class: "nm" }, t.name)))))));
}

function masthead(book, info) {
  const m = book.meta, rec = m.record;
  const c = book.coaching || {};
  const callers = [c.offense?.play_caller && `Offense: ${c.offense.play_caller}`,
                   c.defense?.play_caller && `Defense: ${c.defense.play_caller}`].filter(Boolean);
  return h("header", { class: "mast" },
    h("div", { class: "stripe", style: `background:linear-gradient(${m.color},${m.color} 70%,${m.color2} 70%)` }),
    h("div", null,
      h("div", { class: "eyebrow" }, m.division),
      h("h1", null, m.name, " ", h("span", { class: "yr" }, String(book.season))),
      h("div", { class: "mastgrid" },
        rec && h("span", null, "Record ", h("b", null, `${rec.w}–${rec.l}${rec.t ? "–" + rec.t : ""}`)),
        h("span", null, "Points ", h("b", null, `${num(m.points_for)} for, ${num(m.points_against)} against`)),
        m.bye_weeks.length ? h("span", null, "Bye ", h("b", null, `week ${m.bye_weeks.join(", ")}`)) : null,
        callers.length ? h("span", null, "Play callers ", h("b", null, callers.join(", "))) : null)));
}

function liveBanner(info) {
  if (info.complete) return null;
  return h("div", { class: "banner" }, h("b", null, `Through week ${info.through_week}`), h("br"),
    `This page is updated every week during the season. Personnel groupings, formations, coverage and pressure numbers come from nflverse's participation data, which is released a few months after the season ends, so those sections are empty for now.`,
    info.participation_published ? " That data has now been released and these pages will be rebuilt with it soon." : "");
}

function tabs(team, season, active) {
  return h("nav", { class: "tabs", "aria-label": "Sections" }, h("div", { class: "tabrow" },
    TABS.map(([k, label]) => h("a", { class: "tab", href: `#/${team}/${season}/${k}`,
      "aria-current": k === active ? "page" : null }, label))));
}

function metricTable(book, league, keys) {
  const status = book.status;
  const reasons = new Set(keys.map(k => book.metrics[k] ? null : whyMissing(state.byKey[k], book.season, status)));
  if (reasons.size === 1 && !reasons.has(null)) {
    // a whole group missing for one reason is one sentence, not a column of dashes
    return h("div", { class: "note flag" }, [...reasons][0]);
  }
  return h("div", { class: "mtable", role: "table" },
    h("div", { class: "mhead", role: "row" }, h("div", null, "Metric"), h("div", null, book.team),
      h("div", null, "Rank"), h("div", null, `League spread with ${book.team} in blue`)),
    keys.map(k => {
      const m = state.byKey[k], cell = book.metrics[k];
      const label = h("div", { class: "mlab" }, m.label, m.note ? h("span", { class: "mnote" }, m.note) : null);
      if (!cell) {
        return h("div", { class: "mrow na", role: "row" }, label, h("div", { class: "mval" }, "—"),
          h("div", { class: "mrank" }, h("span", { class: "badge b-na" }, "n/a")),
          h("div", { class: "mstrip" }, whyMissing(m, book.season, status)));
      }
      return h("div", { class: "mrow", role: "row" }, label, h("div", { class: "mval" }, fmt(m, cell.v)),
        h("div", { class: "mrank" }, rankBadge(m, cell)), h("div", { class: "mstrip" }, strip(m, league, book.team)));
    }));
}

function sideSections(book, league, side) {
  const groups = [];
  for (const m of state.reg) {
    if (m.side !== side) continue;
    let g = groups.find(x => x.name === m.group);
    if (!g) groups.push(g = { name: m.group, keys: [] });
    g.keys.push(m.key);
  }
  return groups.map(g => [h("h3", null, g.name), metricTable(book, league, g.keys)]);
}

function traitSentence(t) {
  const m = state.byKey[t.key];
  let place;
  if (m.polarity !== 0) {
    const good = t.rank <= t.n / 2, r = good ? t.rank : t.n - t.rank + 1;
    place = `${r === 1 ? "the" : `the ${ord(r)}`} ${good ? "best" : "worst"} in the league`;
  } else {
    const high = t.z >= 0, r = high ? t.rank : t.n - t.rank + 1;
    place = `${r === 1 ? "the" : `the ${ord(r)}`} ${high ? "highest" : "lowest"} in the league`;
  }
  return `${fmt(m, t.value)}, which was ${place}. The league median was ${fmt(m, t.median)}.`;
}

function overview(book, league, info) {
  const M = k => book.metrics[k];
  const tile = (label, value, sub) => h("div", { class: "tile" }, h("div", { class: "tlab" }, label),
    h("div", { class: "tval" }, value), h("div", { class: "tsub" }, sub || " "));
  const rk = k => M(k) ? `${ord(M(k).rank)} of ${M(k).n}` : "";
  const g = book.meta.games || 1;
  const sides = { offense: "Offense", defense: "Defense", special: "Special teams" };
  return [
    h("h2", null, info.complete ? "Season summary" : "Season so far"),
    h("div", { class: "tiles" },
      tile("Record", book.meta.record ? `${book.meta.record.w}–${book.meta.record.l}${book.meta.record.t ? "–" + book.meta.record.t : ""}` : "—",
           info.complete ? "Regular season" : `${book.meta.games} games played`),
      tile("Points per game", num(book.meta.points_for / g, 1), `${num(book.meta.points_against / g, 1)} allowed`),
      tile("EPA per play", M("epa_per_play") ? fmt(state.byKey.epa_per_play, M("epa_per_play").v) : "—", rk("epa_per_play")),
      tile("EPA per play allowed", M("def_epa_per_play") ? fmt(state.byKey.def_epa_per_play, M("def_epa_per_play").v) : "—", rk("def_epa_per_play")),
      tile("Pass rate over expected", M("pass_oe_mean") ? fmt(state.byKey.pass_oe_mean, M("pass_oe_mean").v) : "—",
           M("pass_oe_mean") ? rankText(state.byKey.pass_oe_mean, M("pass_oe_mean").rank, M("pass_oe_mean").n).join("") : ""),
      tile("Snaps per game", M("snaps_per_game") ? fmt(state.byKey.snaps_per_game, M("snaps_per_game").v) : "—",
           M("snaps_per_game") ? rankText(state.byKey.snaps_per_game, M("snaps_per_game").rank, M("snaps_per_game").n).join("") : "")),
    h("h2", null, "Biggest outliers"),
    h("p", { class: "lede" }, "These are the stats where this team was furthest from the rest of the league. A stat shows up here if the team ranked in the top or bottom three, or if it was more than one and a half standard deviations from the league average."),
    book.traits.length
      ? h("div", { class: "traits" }, book.traits.map(t => h("div", { class: "trait" },
          h("span", { class: "side" }, sides[t.side] || t.side), h("b", { class: "tx" }, state.byKey[t.key].label),
          h("span", { class: "v" }, traitSentence(t)))))
      : h("p", { class: "muted" }, "This team was close to the league average across the board this season."),
    h("figure", { class: "fg" }, h("figcaption", null, h("span", { class: "fgt" }, "Results by week"),
      h("span", { class: "fgs" }, "Each bar is the final point margin of one game, with wins above the line and losses below it. Hover over a game to see the opponent, the score and how efficient the offense and defense were.")),
      h("div", { class: "legend" }, h("span", null, h("span", { class: "lk", style: "background:var(--pos)" }), "Win"),
        h("span", null, h("span", { class: "lk", style: "background:var(--neg)" }), "Loss")),
      h("div", { class: "scrollx" }, weeklyChart(book)),
      tableView(["Week", "Opp", "Result", "EPA/play", "EPA allowed", "Pass rate"], book.weekly.map(w =>
        [w.week, `${w.home ? "vs" : "at"} ${w.opponent}`, `${w.pf > w.pa ? "W" : w.pf < w.pa ? "L" : "T"} ${w.pf}–${w.pa}`,
         num(w.epa_per_play, 3), num(w.def_epa_per_play, 3), pct(w.pass_rate, 1)]))),
  ];
}

const OFF_COLS = [
  ["name", "Player", "l"], ["position", "Pos", "l"], ["games", "G"], ["snap_share", "Snap %", "bar"],
  ["targets", "Tgt"], ["target_share", "Tgt %", "pct"], ["receptions", "Rec"], ["rec_yds", "Rec yds"],
  ["adot", "aDOT", "1"], ["carries", "Car"], ["carry_share", "Car %", "pct"], ["rush_yds", "Rush yds"],
  ["td", "TD"], ["pass_td", "Pass TD"], ["ints", "INT"], ["rz_targets", "RZ tgt"], ["rz_carries", "RZ car"], ["pass_yds", "Pass yds"],
  ["ppr_points", "PPR", "1"], ["ppr_per_game", "PPR/G", "1"],
  ["tgt_share_p11", "Tgt % 11", "pct"], ["tgt_share_p12", "Tgt % 12", "pct"], ["tgt_share_p13", "Tgt % 13", "pct"],
];
const DEF_COLS = [
  ["name", "Player", "l"], ["position", "Pos", "l"], ["games", "G"], ["def_snaps", "Snaps"],
  ["snap_share", "Snap %", "bar"], ["sacks", "Sacks", "1"], ["qb_hits", "QB hits"], ["tfl", "TFL"],
  ["ints", "INT"], ["passes_defended", "PD"], ["base_share", "Base %", "pct"],
  ["nickel_share", "Nickel %", "pct"], ["dime_share", "Dime %", "pct"],
];

function playerTable(rows, cols, sortState, rerender) {
  const present = cols.filter(([k]) => rows.some(r => r[k] != null));
  const sorted = [...rows].sort((a, b) => {
    const va = a[sortState.key], vb = b[sortState.key];
    if (va == null) return 1; if (vb == null) return -1;
    return (typeof va === "string" ? va.localeCompare(vb) : va - vb) * sortState.dir;
  });
  const cell = (r, [k, , kind]) => {
    const v = r[k];
    if (kind === "l") return h("td", { class: k === "name" ? "nm" : "l" }, v ?? "—");
    if (kind === "bar") return h("td", null, pct(v), h("span", { class: "sbar", "aria-hidden": "true" },
      h("i", { style: `width:${Math.max(0, Math.min(1, v || 0)) * 100}%` })));
    if (kind === "pct") return h("td", null, pct(v, 1));
    if (kind === "1") return h("td", null, num(v, 1));
    return h("td", null, num(v));
  };
  return h("div", { class: "tw" }, h("table", null,
    h("thead", null, h("tr", null, present.map(([k, label, kind]) => h("th", {
      class: kind === "l" ? "l" : null, "aria-sort": sortState.key === k ? (sortState.dir > 0 ? "ascending" : "descending") : null },
      h("button", { type: "button", onclick: () => {
        sortState.dir = sortState.key === k ? -sortState.dir : (kind === "l" ? 1 : -1);
        sortState.key = k; rerender();
      } }, label))))),
    h("tbody", null, sorted.map(r => h("tr", null, present.map(c => cell(r, c)))))));
}

function players(book) {
  const off = book.players.offense.map(r => ({ ...r, td: (r.rec_td || 0) + (r.rush_td || 0) }));
  const def = book.players.defense;
  const wrap = h("div");
  const view = { side: "offense", off: { key: "ppr_points", dir: -1 }, def: { key: "def_snaps", dir: -1 } };
  const draw = () => {
    const seg = h("div", { class: "seg", role: "group", "aria-label": "Side" },
      ["offense", "defense"].map(sd => h("button", { type: "button", "aria-pressed": String(view.side === sd),
        onclick: () => { view.side = sd; draw(); } }, sd === "offense" ? "Offense" : "Defense")));
    const table = view.side === "offense" ? playerTable(off, OFF_COLS, view.off, draw) : playerTable(def, DEF_COLS, view.def, draw);
    wrap.replaceChildren(seg, table);
  };
  draw();
  return [h("h2", null, "Player usage"),
    h("p", { class: "lede" }, "These tables list the players who played the most snaps for the team. The offensive table shows how often each player was on the field, how much of the team's passing and rushing work went to them, and their full PPR fantasy points. When personnel data is available it also shows each player's share of targets in 11, 12 and 13 personnel. The defensive table shows snaps, sacks and other big plays, along with how often each player was on the field in base, nickel and dime packages. Click any column header to sort by it."),
    wrap];
}

function coaching(book) {
  const c = book.coaching || {};
  const coachCard = (title, x) => h("div", { class: "card" }, h("h3", { style: "margin-top:0" }, title),
    x ? h("dl", { class: "coach" },
      h("dt", null, "Head coach"), h("dd", null, x.head_coach || "—"),
      h("dt", null, "Coordinator"), h("dd", null, x.coordinator || "—"),
      h("dt", null, "Play caller"), h("dd", null, x.play_caller || "—", x.hc_calls ? " (head coach)" : ""),
      x.notes ? [h("dt", null, "Note"), h("dd", null, x.notes)] : null)
      : h("p", { class: "muted" }, "This staff is not in the coaching data yet. The data covers every 2026 staff and the earlier jobs of their play callers, so some older seasons are missing."));
  const lineage = (c.lineage || []);
  const compList = (rows, side) => rows.length
    ? h("div", { class: "comps" }, rows.map((r, i) => h("a", { class: "comp", href: `#/${r.team}/${r.season}/${side}` },
        h("span", { class: "rank" }, i + 1),
        chip(r.team),
        h("span", null, h("div", { class: "who" }, `${teamName(r.team)} ${r.season}`),
          h("div", { class: "pc" }, r.play_caller ? `Play caller ${r.play_caller}` : "Play caller unknown")),
        h("span", { class: "dist" }, `Distance ${num(r.distance, 2)}`, h("br"), `${r.shared} stats compared`))))
    : h("p", { class: "muted" }, "No other team season had enough of the same stats available to compare against.");
  return [
    h("h2", null, "Coaches and play callers"),
    h("div", { class: "cols2" }, coachCard("Offense", c.offense), coachCard("Defense", c.defense)),
    lineage.length ? h("div", { class: "note" },
      lineage.map(l => `This is ${l.play_caller}'s first year calling the ${l.side}. ${l.play_caller} previously worked under ${l.mentor}${l.learned_at ? ` in ${l.learned_at}` : ""}${l.seasons ? ` from ${l.seasons}` : ""}.`).join(" ")) : null,
    h("h2", null, "Most similar team seasons"),
    h("p", { class: "lede" }, "These are the seasons from other franchises that were closest in style. On offense the comparison uses personnel, formations, pass rate and play design, and on defense it uses fronts, coverage and pressure. Each stat is first compared to the league average for its own year, so seasons from different years can be matched fairly. Efficiency stats like EPA are left out on purpose, so a match means the two teams played a similar way, not that they were equally good. Only completed seasons are used, and a lower distance means a closer match."),
    h("div", { class: "cols2" },
      h("div", null, h("h3", null, "Offense"), compList(book.comps?.offense || [], "offense")),
      h("div", null, h("h3", null, "Defense"), compList(book.comps?.defense || [], "defense"))),
  ];
}

async function trends(book) {
  const series = await get(`data/trends/${book.team}.json`);
  const live = seasonInfo(state.index.live_season);
  const keys = state.reg.map(m => m.key).filter(k => series[k]);
  const view = { key: keys.includes("pass_rate_neutral") ? "pass_rate_neutral" : keys[0] };
  const main = h("div");
  const draw = () => {
    const m = state.byKey[view.key], rows = series[view.key];
    const sel = h("select", { "aria-label": "Metric", onchange: e => { view.key = e.target.value; draw(); } },
      ["offense", "defense", "special", "construction"].map(side => h("optgroup", { label: side[0].toUpperCase() + side.slice(1) },
        state.reg.filter(x => x.side === side && series[x.key]).map(x => h("option", { value: x.key, selected: x.key === view.key || null }, x.label)))));
    main.replaceChildren(h("figure", { class: "fg" },
      h("figcaption", null, h("span", { class: "fgt" }, `${m.label}, by season`),
        h("span", { class: "fgs" }, m.note || "Hover over a season to see the exact value and where it ranked.")),
      h("div", { style: "margin:0 0 10px" }, sel),
      h("div", { class: "legend" }, h("span", null, h("span", { class: "lk line", style: "background:var(--accent)" }), book.team),
        h("span", null, h("span", { class: "lk line", style: "background:var(--median)" }), "League median"),
        live && !live.complete ? h("span", null, h("span", { class: "lk", style: "border:2px solid var(--accent);border-radius:50%;width:9px;height:9px" }), `${live.season} so far`) : null),
      h("div", { class: "scrollx" }, seasonLine(m, rows, { live })),
      tableView(["Season", book.team, "Median", "Rank"], rows.map(r => [r[0], fmt(m, r[1]), fmt(m, r[2]), `${ord(r[3])} of ${r[4]}`]))));
  };
  draw();
  const smalls = Object.entries(TREND_PICKS).map(([side, picks]) => {
    const have = picks.filter(k => series[k] && series[k].length > 1);
    if (!have.length) return null;
    return [h("h3", null, side === "special" ? "Special teams and roster" : side[0].toUpperCase() + side.slice(1)),
      h("div", { class: "smalls" }, have.map(k => {
        const m = state.byKey[k], rows = series[k], last = rows[rows.length - 1];
        return h("div", { class: "small" }, h("div", { class: "t" }, m.label),
          h("div", { class: "s" }, `${fmt(m, last[1])} in ${last[0]}, ${ord(last[3])} of ${last[4]}`),
          seasonLine(m, rows, { small: true, live }));
      }))];
  });
  return [h("h2", null, "Trends since 2018"),
    h("p", { class: "lede" }, `The blue line follows the ${teamName(book.team)} from season to season and the gray line is the league median. Use the menu to pick any stat, or look through the smaller charts below. Some stats start later than 2018 because the data behind them was not collected before then.`),
    main, smalls];
}

function notes(book) {
  const info = seasonInfo(book.season);
  const bySrc = { pbp: [], ftn: [], participation: [], construction: [] };
  for (const m of state.reg) bySrc[m.source].push(m);
  const srcRow = (src, what, when) => [state.index.sources[src], what, when, `${bySrc[src].length}`];
  const note = (title, text) => h("div", { class: "note flag" }, h("b", { class: "nt" }, title), h("p", null, text));
  const missing = Object.values(info.unavailable);
  return [
    h("h2", null, "Where the data comes from"),
    h("p", { class: "lede" }, "Every stat on this site comes from one of four public data sources, and each source covers a different range of seasons. If a stat is not available for a season, the page says why instead of showing a zero."),
    h("div", { class: "tw" }, h("table", null,
      h("thead", null, h("tr", null, ["Source", "What it covers", "Seasons", "Stats"].map((c, i) => h("th", { class: i < 3 ? "l" : null }, c)))),
      h("tbody", null, [
        srcRow("pbp", "Efficiency, pass rate, shotgun and no huddle rates, fourth downs, kicking and results allowed", "Every season, updated nightly"),
        srcRow("ftn", "Motion, play action, RPOs, screens, backfield counts and charted blitzes and box counts", "2022 onward, updated during the season"),
        srcRow("participation", "Personnel groupings, formations, defensive fronts, coverage and pressure", "2016 onward with coverage from 2018, released after each season"),
        srcRow("construction", "Salary cap allocation, age, roster continuity and draft capital", "One value per season"),
      ].map(r => h("tr", null, r.map((c, i) => h("td", { class: i < 3 ? "l" : null, style: i === 0 ? "white-space:normal;min-width:180px" : i < 3 ? "white-space:normal;min-width:220px" : null }, c))))))),
    h("h3", null, `Gaps in ${book.season}`),
    h("div", { class: "note" }, missing.length ? missing.join(" ") : `Every data source is available for ${book.season}.`),
    h("h3", null, "Things to know"),
    note("How rates are calculated", "Season rates are calculated from season totals. For example, the neutral script pass rate is the number of neutral script passes divided by the number of neutral script plays over the whole season. Averaging the weekly rates instead can be off by as much as four percentage points for stats like this one, which only count some of a team's plays."),
    note("Formation labels changed in 2023", "Up to 2022 the participation data recorded singleback, I formation, empty, jumbo and wildcat as separate formations. Starting in 2023 it groups all of them as under center. Because of that, the singleback, I formation and empty rates only appear through 2022, and the under center rate only appears from 2023 on. FTN's charted under center rate covers 2022 onward and can be used to compare across the change."),
    note("Pressure rate", "Starting in 2023 the participation data marks running plays as having no pressure instead of leaving them blank. The pressure rate here only counts dropbacks, which keeps it consistent across that change. The league median was 29.1 percent in 2022 and 29.4 percent in 2023."),
    note("Two different blitz rates", "The participation data and FTN chart blitzes separately and do not always agree, so their blitz rates are shown as two different stats and are never combined."),
    note("How ranks work", "For stats where higher or lower is clearly better, like EPA or success rate, 1st is always the best team in the league. That means the defense allowing the lowest EPA ranks 1st. For tendencies like 12 personnel or Cover 3 rate, there is no good or bad, so the rank just says whether the team was among the highest or lowest in the league."),
    note("Regular season only", "Playoff games are not included. Seasons through 2020 had 17 weeks and seasons since 2021 have had 18."),
  ];
}

// --- router ------------------------------------------------------------------------------------
function fillPickers(team, season) {
  const tp = $("#pick-team"), sp = $("#pick-season");
  if (!tp.options.length) {
    tp.append(h("option", { value: "" }, "All teams"));
    const byDiv = {};
    for (const [abbr, t] of Object.entries(state.index.teams)) (byDiv[t.division] ||= []).push([abbr, t]);
    for (const div of Object.keys(byDiv).sort()) {
      tp.append(h("optgroup", { label: div }, byDiv[div].sort((a, b) => a[1].name.localeCompare(b[1].name))
        .map(([abbr, t]) => h("option", { value: abbr }, t.name))));
    }
    for (const x of state.index.seasons) {
      sp.append(h("option", { value: x.season }, x.complete ? String(x.season) : `${x.season} (through week ${x.through_week})`));
    }
    tp.addEventListener("change", () => {
      const [, , s2, tab] = location.hash.split("/");
      location.hash = tp.value ? `#/${tp.value}/${s2 || defaultSeason()}/${tab || "overview"}` : "#/";
    });
    sp.addEventListener("change", () => {
      const [, t2, , tab] = location.hash.split("/");
      if (t2) location.hash = `#/${t2}/${sp.value}/${tab || "overview"}`;
    });
  }
  tp.value = team || "";
  sp.value = String(season || defaultSeason());
}

async function route() {
  hideTip();
  const [, team, seasonStr, tab = "overview"] = location.hash.split("/");
  const app = $("#app");
  if (!team || !state.index.teams[team]) { fillPickers(null, null); renderHome(); return; }
  const season = Number(seasonStr) || defaultSeason();
  fillPickers(team, season);
  const info = seasonInfo(season);
  if (!info) { app.replaceChildren(h("p", { class: "loading" }, `No book for ${season}.`)); return; }
  app.replaceChildren(h("div", { class: "loading" }, "Loading…"));
  let book, league;
  try {
    [book, league] = await Promise.all([get(`data/${season}/${team}.json`), get(`data/league/${season}.json`)]);
  } catch (e) {
    app.replaceChildren(h("p", { class: "loading" }, `Could not load ${team} ${season}.`));
    return;
  }
  document.title = `${book.meta.name} ${season} Team Book`;
  const body = {
    overview: () => overview(book, league, info),
    offense: () => [h("h2", null, "Offensive scheme"), h("p", { class: "lede" }, "This tab covers how the offense lined up and what kinds of plays it called, with each stat ranked against the other 31 teams. Efficiency stats are marked green or red depending on whether the rank is good or bad. Tendencies like pass rate or 12 personnel usage are shown in gray because there is no right answer for them."), sideSections(book, league, "offense")],
    defense: () => [h("h2", null, "Defensive scheme"), h("p", { class: "lede" }, "The first table shows how well the defense played. The rest show how it played, including which packages it used, how often it played each coverage, how often it blitzed and how many defenders it put in the box."), sideSections(book, league, "defense")],
    special: () => [h("h2", null, "Special teams and decisions"), h("p", { class: "lede" }, "These stats cover fourth down and two point decisions, red zone finishing and kicking."), sideSections(book, league, "special"), h("h2", null, "Roster construction"), h("p", { class: "lede" }, "These stats show how the team split its salary cap between positions, how old its starters were, how many of last year's players returned and how much draft capital it had invested on each side of the ball."), sideSections(book, league, "construction")],
    players: () => players(book),
    coaching: () => coaching(book),
    trends: () => trends(book),
    notes: () => notes(book),
  }[tab] || (() => overview(book, league, info));
  let content = [await body()].flat(Infinity);
  // the written overview for this tab sits directly under the tab's title
  const text = book.overview?.[tab in (book.overview || {}) ? tab : "overview"];
  if (text) {
    const at = content[0]?.tagName === "H2" ? 1 : 0;
    content.splice(at, 0, h("p", { class: "overview" }, text));
  }
  app.replaceChildren(masthead(book, info), liveBanner(info) || "", tabs(team, season, tab), h("main", null, content));
}

async function main() {
  const theme = $("#theme");
  theme.addEventListener("click", () => {
    const cur = document.documentElement.dataset.theme
      || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("tb-theme", next); } catch (e) { /* storage unavailable */ }
  });
  try {
    state.index = await get("data/index.json");
  } catch (e) {
    $("#app").replaceChildren(h("p", { class: "loading" }, "Could not load the data index."));
    return;
  }
  state.reg = state.index.registry;
  for (const m of state.reg) state.byKey[m.key] = m;
  $("#gen").textContent = `The data was last updated on ${new Date(state.index.generated_at).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}.`;
  window.addEventListener("hashchange", () => { route(); window.scrollTo(0, 0); });
  route();
}
main();
