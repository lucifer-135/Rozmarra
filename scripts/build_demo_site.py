"""Build the mobile demo page, site/index.html, from the running Rozmarra API.

The page lets a judge follow one guided run of the prototype on a phone: the doctor's
patient list, Ramesh's two plans, the warning at 10:50 am, Sunita's trade-off and the
family plan in English and Hindi. Every number and every patient sentence on the page
comes from the API at build time, so the page needs no server and no JavaScript library.

Before running it, restore the prepared demo state and start the API:

    Copy-Item data\\demo\\approvals.finale.sqlite data\\demo\\approvals.sqlite -Force
    cd backend; uv run rozmarra serve

Then run, from the repository root:

    python scripts/build_demo_site.py

The script uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "index.html"
REPO = "https://github.com/lucifer-135/Rozmarra"

RAMESH, SUNITA = "SY-0002", "SY-0001"
PLAN_B = "plan-b"
# The moment the monitor raised its first warning for Ramesh (checked in the finale video).
ALERT_AT = "2026-10-15T10:50:00"
# Twelve hours of readings end at this moment, so the page can show the fall after the warning.
AFTER_AT = "2026-10-15T13:00:00"

# These results are the ones on deck slide 6. They come from reports/metrics.json and docs/model_card.md.
EVIDENCE = [
    ("94 in 100", "Rozmarra picks the hour that ends in low blood sugar.", "Real data: normal days of 89 patients."),
    ("97 in 100", "Rozmarra finds the patient at risk before the fast.", "Simulated: 1,500 fasting days."),
    ("88 in 100", "Rozmarra catches low blood sugar events in time.", "Simulated: 1,500 fasting days."),
    ("25 minutes", "This is the typical warning before low blood sugar.", "Simulated: 1,500 fasting days."),
]

INK, MUTED, TEAL, PLAN_A_GREY, AMBER = "#1A1D1E", "#6B7477", "#0F6B73", "#8A9396", "#C2690B"


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def get(self, path: str):
        with urllib.request.urlopen(self.base + path) as response:
            body = response.read().decode("utf-8")
        return json.loads(body) if response.headers.get_content_type() == "application/json" else body

    def post(self, path: str, payload: dict):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


def clock(moment: datetime) -> str:
    """12-hour clock in the project's style: "8 pm", "10:50 am"."""
    hour = moment.hour % 12 or 12
    suffix = "am" if moment.hour < 12 else "pm"
    return f"{hour} {suffix}" if moment.minute == 0 else f"{hour}:{moment.minute:02d} {suffix}"


def esc(text) -> str:
    return html.escape(str(text), quote=True)


def plan_main(document: str) -> str:
    """The body of the printable plan, without its page wrapper and print styles."""
    match = re.search(r"<main>(.*)</main>", document, re.S)
    if match is None:
        raise SystemExit("The plan document has no <main> element.")
    return match.group(1).strip()


class Chart:
    """A small SVG line chart with a time axis and a glucose axis in mg/dL."""

    def __init__(self, start: datetime, end: datetime, low: float, high: float, width=360, height=230):
        self.start, self.end, self.low, self.high = start, end, low, high
        self.width, self.height = width, height
        self.left, self.right, self.top, self.bottom = 36, 12, 14, 30
        self.parts: list[str] = []

    def x(self, moment: datetime) -> float:
        span = (self.end - self.start).total_seconds()
        share = (moment - self.start).total_seconds() / span
        return self.left + share * (self.width - self.left - self.right)

    def y(self, value: float) -> float:
        share = (value - self.low) / (self.high - self.low)
        return self.height - self.bottom - share * (self.height - self.top - self.bottom)

    def inside(self, moment: datetime) -> bool:
        return self.start <= moment <= self.end

    def points(self, times, values) -> list[tuple[float, float]]:
        return [
            (self.x(parse(t)), self.y(v))
            for t, v in zip(times, values)
            if v is not None and self.inside(parse(t))
        ]

    def grid(self, ticks: list[datetime], levels: list[int]) -> None:
        for level in levels:
            y = self.y(level)
            self.parts.append(f'<line x1="{self.left}" x2="{self.width - self.right}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
            self.parts.append(f'<text x="{self.left - 6}" y="{y + 4:.1f}" class="axis" text-anchor="end">{level}</text>')
        for tick in ticks:
            x = self.x(tick)
            # The first and last labels hug the plot edges so they are not cut off on a narrow screen.
            anchor = "start" if tick == ticks[0] else "end" if tick == ticks[-1] else "middle"
            x = self.left if anchor == "start" else self.width - self.right if anchor == "end" else x
            self.parts.append(f'<text x="{x:.1f}" y="{self.height - 10}" class="axis" text-anchor="{anchor}">{clock(tick)}</text>')

    def low_line(self, label_at_left: bool = False) -> None:
        y = self.y(70)
        self.parts.append(f'<line x1="{self.left}" x2="{self.width - self.right}" y1="{y:.1f}" y2="{y:.1f}" class="low"/>')
        if label_at_left:
            self.parts.append(f'<text x="{self.left + 4}" y="{y + 14:.1f}" class="low-label">70 mg/dL: low</text>')
        else:
            self.parts.append(f'<text x="{self.width - self.right}" y="{y + 14:.1f}" class="low-label" text-anchor="end">70 mg/dL: low</text>')

    def band(self, times, lower, upper, css_class: str) -> None:
        top = self.points(times, upper)
        bottom = self.points(times, lower)
        if not top:
            return
        outline = top + list(reversed(bottom))
        path = " ".join(f"{x:.1f},{y:.1f}" for x, y in outline)
        self.parts.append(f'<polygon points="{path}" class="{css_class}"/>')

    def line(self, times, values, css_class: str) -> None:
        pts = self.points(times, values)
        path = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        self.parts.append(f'<polyline points="{path}" class="{css_class}"/>')

    def raw(self, svg: str) -> None:
        self.parts.append(svg)

    def svg(self, label: str) -> str:
        body = "\n".join(self.parts)
        return (
            f'<svg viewBox="0 0 {self.width} {self.height}" role="img" aria-label="{esc(label)}">'
            f"{body}</svg>"
        )


def dot(x: float, y: float, css_class: str, r: float = 5) -> str:
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" class="{css_class}"/>'


def label(x: float, y: float, text: str, css_class: str, anchor: str = "middle") -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" class="{css_class}" text-anchor="{anchor}">{esc(text)}</text>'


def plans_chart(compare: dict) -> str:
    plan_a, plan_b = compare["plan_a"], compare["plan_b"]
    fast = plan_a["markers"]["fast"]
    start, end = parse(fast["start"]), parse(fast["end"])
    chart = Chart(start, end, 50, 250)
    ticks = [start, start + timedelta(hours=6), start + timedelta(hours=12), start + timedelta(hours=18), end]
    chart.grid(ticks, [70, 150, 250])
    chart.low_line()
    curve_a, curve_b = plan_a["curve"], plan_b["curve"]
    chart.band(curve_a["times"], curve_a["p10"], curve_a["p90"], "band-a")
    chart.band(curve_b["times"], curve_b["p10"], curve_b["p90"], "band-b")
    chart.line(curve_a["times"], curve_a["p50"], "line-a")
    chart.line(curve_b["times"], curve_b["p50"], "line-b")
    for plan, css, offset in ((plan_a, "dot-a", 18), (plan_b, "dot-b", -10)):
        summary = plan["summary"]
        moment = parse(summary["lowest_glucose_time"])
        x, y = chart.x(moment), chart.y(summary["lowest_glucose_mg_dl"])
        chart.raw(dot(x, y, css, 4.5))
        chart.raw(label(x, y + offset, f'{summary["lowest_glucose_mg_dl"]:.0f}', css.replace("dot", "val")))
    return chart.svg("Ramesh's glucose during the fast under Plan A and Plan B, simulated by the twin.")


def monitor_chart(at_alert: dict, after: dict) -> str:
    alert_time = parse(at_alert["time"])
    start = alert_time.replace(hour=8, minute=0)
    end = alert_time.replace(hour=13, minute=0)
    chart = Chart(start, end, 50, 200)
    chart.grid([start + timedelta(hours=h) for h in range(6)], [70, 100, 150, 200])
    chart.low_line(label_at_left=True)
    forecast = at_alert["forecast"]
    chart.band(forecast["times"], forecast["p10"], forecast["p90"], "band-f")
    chart.line(forecast["times"], forecast["p50"], "line-f")
    glucose = at_alert["glucose"]
    chart.line(glucose["times"], glucose["values"], "line-g")
    x = chart.x(alert_time)
    chart.raw(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{chart.top}" y2="{chart.height - chart.bottom}" class="alert-line"/>')
    chart.raw(label(x - 4, chart.top + 10, f"Warning, {clock(alert_time)}", "alert-label", "end"))

    later = [
        (t, v)
        for t, v in zip(after["glucose"]["times"], after["glucose"]["values"])
        if v is not None and parse(t) > alert_time
    ]
    first_low = next((t, v) for t, v in later if v < 70)
    shown = "".join(dot(chart.x(parse(t)), chart.y(v), "dot-after", 2.6) for t, v in later if chart.inside(parse(t)))
    lx, ly = chart.x(parse(first_low[0])), chart.y(first_low[1])
    shown += dot(lx, ly, "dot-low", 5)
    # The callout sits in the empty space above the forecast, clear of the axis labels and the 70 mg/dL line.
    shown += label(chart.width - chart.right, chart.y(130), "First reading below 70:", "low-callout", "end")
    shown += label(chart.width - chart.right, chart.y(130) + 15, f"{first_low[1]:.1f} mg/dL at {clock(parse(first_low[0]))}", "low-callout", "end")
    chart.raw(f'<g id="after" class="after">{shown}</g>')
    return chart.svg("Ramesh's glucose readings until 10:50 am with the forecast, and the readings that followed.")


def medicine_changes(compare: dict) -> list[str]:
    """Sentences for each medicine whose dose or time differs between Plan A and Plan B."""
    before = compare["plan_a"]["markers"]["medicines"]
    after = compare["plan_b"]["markers"]["medicines"]
    if len(before) != len(after):
        raise SystemExit("Plan A and Plan B list a different number of medicines.")
    changes = []
    for old, new in zip(before, after):
        if old["name"] != new["name"]:
            raise SystemExit("Plan A and Plan B list the medicines in a different order.")
        if old["dose"] == new["dose"] and old["time"] == new["time"]:
            continue
        unit = new["unit"]
        changes.append(
            f'{esc(new["display_name"])}: {old["dose"]:g} {esc(unit)} at {clock(parse(old["time"]))} '
            f'<span class="arrow">becomes</span> <strong>{new["dose"]:g} {esc(unit)} at {clock(parse(new["time"]))}</strong>'
        )
    return changes


def percent(chance: dict) -> str:
    # A chance such as 0.5% rounds to "0%", which reads as "no risk"; say "under 1%" instead.
    if chance["percent"] == 0 and chance["value"] > 0:
        return "under 1%"
    return f'{chance["percent"]}%'


def build(api: Api) -> str:
    patients = api.get("/patients")
    names = {p["patient_id"]: p for p in patients}
    ramesh, sunita = names[RAMESH], names[SUNITA]

    def compare(patient_id: str) -> dict:
        plan_a = api.get(f"/patients/{patient_id}/plans/default")
        saved = api.get(f"/patients/{patient_id}/plans")["plans"]
        if PLAN_B not in saved:
            raise SystemExit(f"{patient_id} has no saved Plan B. Restore approvals.finale.sqlite first.")
        return api.post(f"/patients/{patient_id}/compare", {"plan_a": plan_a, "plan_b": saved[PLAN_B]})

    r_compare, s_compare = compare(RAMESH), compare(SUNITA)
    at_alert = api.get(f"/patients/{RAMESH}/replay?at={ALERT_AT}")
    after = api.get(f"/patients/{RAMESH}/replay?at={AFTER_AT}")
    if not at_alert["alert"]:
        raise SystemExit(f"The monitor shows no warning at {ALERT_AT}.")
    s_plan = api.get(f"/patients/{SUNITA}/plans")["plans"][PLAN_B]
    if s_plan["status"] != "approved":
        raise SystemExit("Sunita's Plan B is not approved. Restore approvals.finale.sqlite first.")
    plan_en = plan_main(api.get(f"/patients/{SUNITA}/plans/{PLAN_B}/document?lang=en"))
    plan_hi = plan_main(api.get(f"/patients/{SUNITA}/plans/{PLAN_B}/document?lang=hi"))

    ra, rb = r_compare["plan_a"]["summary"], r_compare["plan_b"]["summary"]
    sa, sb = s_compare["plan_a"]["summary"], s_compare["plan_b"]["summary"]
    r_changes = medicine_changes(r_compare)
    s_changes = medicine_changes(s_compare)
    caution = s_compare["plan_a"]["dehydration_caution"]

    later = [
        (t, v)
        for t, v in zip(after["glucose"]["times"], after["glucose"]["values"])
        if v is not None and parse(t) > parse(at_alert["time"])
    ]
    first_low_time = parse(next(t for t, v in later if v < 70))
    alert_time = parse(at_alert["time"])
    lead_minutes = int((first_low_time - alert_time).total_seconds() // 60)

    rows = []
    for rank, p in enumerate(patients, start=1):
        status = {"approved": "Approved", "draft": "Draft", "not_started": "Not started"}.get(p["plan_status"], p["plan_status"])
        rows.append(
            f'<li class="patient{" top" if rank == 1 else ""}">'
            f'<div><strong>{esc(p["name"])}</strong>, {p["age"]}<br>'
            f'<span class="muted">{esc(p["fast"])}, {esc(p["fast_date_text"])}</span></div>'
            f'<div class="right"><span class="chance">{percent(p["chance_of_low_during_fast"])}</span>'
            f'<span class="muted small">chance of low</span><span class="status">{status}</span></div></li>'
        )

    reasons = "".join(
        f'<li><span data-lang-block="en">{esc(r["en"])}</span><span data-lang-block="hi" lang="hi" hidden>{esc(r["hi"])}</span></li>'
        for r in at_alert["reasons"]
    )
    evidence = "".join(
        f'<li><span class="big">{esc(v)}</span><span>{esc(t)}</span><span class="muted small">{esc(d)}</span></li>'
        for v, t, d in EVIDENCE
    )
    caution_html = ""
    if caution:
        caution_html = (
            f'<div class="caution"><strong>{esc(caution["title"])}.</strong> {esc(caution["message"])} '
            f'<span class="muted">{" ".join(esc(r) for r in caution["reasons"])}</span></div>'
        )

    approved_on = parse(s_plan["approved_on"])
    approved_text = f"Approved by Dr {s_plan['approved_by']} on {approved_on.day} {approved_on:%B %Y}"

    return PAGE.format(
        css=CSS,
        script=SCRIPT,
        repo=REPO,
        patient_rows="".join(rows),
        ramesh_name=esc(ramesh["name"]),
        ramesh_age=ramesh["age"],
        ramesh_fast=esc(ramesh["fast"]),
        ramesh_date=esc(ramesh["fast_date_text"]),
        r_change="".join(f"<li>{c}</li>" for c in r_changes),
        plans_chart=plans_chart(r_compare),
        ra_low=f'{ra["lowest_glucose_mg_dl"]:.0f}',
        rb_low=f'{rb["lowest_glucose_mg_dl"]:.0f}',
        ra_chance=percent(ra["chance_of_low_during_fast"]),
        rb_chance=percent(rb["chance_of_low_during_fast"]),
        ra_time=esc(ra["lowest_glucose_time_text"]),
        rb_time=esc(rb["lowest_glucose_time_text"]),
        alert_time=clock(alert_time),
        alert_chance=percent(at_alert["chance_of_low_next_60_min"]),
        alert_word=esc(at_alert["chance_of_low_next_60_min"]["word"].lower()),
        reasons=reasons,
        monitor_chart=monitor_chart(at_alert, after),
        low_time=clock(first_low_time),
        lead=lead_minutes,
        sunita_name=esc(sunita["name"]),
        sunita_fast=esc(sunita["fast"]),
        s_change="".join(f"<li>{c}</li>" for c in s_changes),
        sa_low=percent(sa["chance_of_low_during_fast"]),
        sb_low=percent(sb["chance_of_low_during_fast"]),
        sa_high=percent(sa["chance_of_high_after_fast"]),
        sb_high=percent(sb["chance_of_high_after_fast"]),
        caution=caution_html,
        approved=esc(approved_text),
        plan_en=plan_en,
        plan_hi=plan_hi,
        evidence=evidence,
    )


CSS = """
@font-face { font-family: "Fraunces"; font-weight: 700; font-display: swap; src: url("fonts/Fraunces_72pt-Bold.woff2") format("woff2"); }
@font-face { font-family: "Plus Jakarta Sans"; font-weight: 400; font-display: swap; src: url("fonts/PlusJakartaSans-Regular.woff2") format("woff2"); }
@font-face { font-family: "Plus Jakarta Sans"; font-weight: 600; font-display: swap; src: url("fonts/PlusJakartaSans-SemiBold.woff2") format("woff2"); }
@font-face { font-family: "Plus Jakarta Sans"; font-weight: 700; font-display: swap; src: url("fonts/PlusJakartaSans-Bold.woff2") format("woff2"); }
@font-face { font-family: "Noto Sans Devanagari"; font-weight: 400; font-display: swap; src: url("fonts/noto-sans-devanagari-devanagari-400-normal.woff2") format("woff2"); unicode-range: U+0900-097F, U+1CD0-1CF9, U+200C-200D, U+20A8, U+20B9, U+25CC, U+A830-A839, U+A8E0-A8FF; }
@font-face { font-family: "Noto Sans Devanagari"; font-weight: 600; font-display: swap; src: url("fonts/noto-sans-devanagari-devanagari-600-normal.woff2") format("woff2"); unicode-range: U+0900-097F, U+1CD0-1CF9, U+200C-200D, U+20A8, U+20B9, U+25CC, U+A830-A839, U+A8E0-A8FF; }
:root {
  --bg: #F6F4EF; --card: #FFFFFF; --ink: #1A1D1E; --muted: #5F686B; --line: #E2DED3;
  --teal: #0F6B73; --deep: #0E2A33; --amber: #C2690B; --amber-soft: #FBEFE1; --a: #8A9396;
  --serif: "Fraunces", Georgia, serif;
  --sans: "Plus Jakarta Sans", "Noto Sans Devanagari", "Nirmala UI", system-ui, sans-serif;
  color-scheme: light;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 400 16px/1.55 var(--sans); }
main { max-width: 600px; margin: 0 auto; padding: 0 16px 48px; }
header.hero { background: var(--deep); color: #F4F3EE; padding: 28px 16px 26px; }
header.hero .wrap { max-width: 600px; margin: 0 auto; }
.kicker { font: 700 12px/1.4 var(--sans); letter-spacing: .12em; text-transform: uppercase; color: #E58A2A; margin: 0 0 8px; }
h1 { font: 700 40px/1.05 var(--serif); margin: 0 0 10px; }
.hero p { margin: 0 0 10px; color: #DCE5E4; }
.synthetic { display: inline-block; margin-top: 6px; font-size: 13px; color: #A9BDBF; border: 1px solid #2E5560; border-radius: 999px; padding: 4px 12px; }
nav.steps { position: sticky; top: 0; z-index: 2; background: rgba(246,244,239,.94); backdrop-filter: blur(6px); border-bottom: 1px solid var(--line); }
nav.steps ol { display: flex; gap: 6px; overflow-x: auto; list-style: none; margin: 0 auto; padding: 10px 16px; max-width: 600px; scrollbar-width: none; }
nav.steps a { display: block; white-space: nowrap; font-size: 13px; font-weight: 600; color: var(--teal); text-decoration: none; padding: 6px 12px; border-radius: 999px; background: #E6EFEE; }
section { padding-top: 34px; scroll-margin-top: 56px; }
.step { font: 700 12px/1.4 var(--sans); letter-spacing: .12em; text-transform: uppercase; color: var(--amber); margin: 0 0 6px; }
h2 { font: 700 27px/1.15 var(--serif); margin: 0 0 10px; }
h3 { font-size: 16px; margin: 18px 0 6px; }
p { margin: 0 0 12px; }
.muted { color: var(--muted); }
.small { font-size: 13px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 16px; margin: 14px 0; }
ul.patients { list-style: none; padding: 0; margin: 14px 0; }
.patient { display: flex; justify-content: space-between; gap: 12px; background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; margin-bottom: 8px; }
.patient.top { border: 2px solid var(--amber); }
.patient .right { text-align: right; display: flex; flex-direction: column; align-items: flex-end; flex: none; }
.patient .right .small { white-space: nowrap; }
.chance { font: 700 22px/1.1 var(--serif); }
.status { font-size: 12px; font-weight: 600; color: var(--teal); margin-top: 2px; }
.compare { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 14px 0; }
.compare > div { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 12px; }
.compare .tag { font-size: 12px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.compare .a .tag { color: #6B7477; } .compare .b .tag { color: var(--teal); }
.compare .num { font: 700 30px/1.1 var(--serif); margin: 4px 0 0; white-space: nowrap; }
.compare .num small { font: 600 14px/1 var(--sans); color: var(--muted); }
.compare .b .num { color: var(--teal); }
.legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 13px; margin: 4px 0 6px; }
.legend span::before { content: ""; display: inline-block; width: 16px; height: 3px; border-radius: 2px; margin-right: 6px; vertical-align: middle; background: currentColor; }
.legend .la { color: #6B7477; } .legend .lb { color: var(--teal); } .legend .lg { color: var(--ink); } .legend .lf { color: var(--teal); }
.legend .lr { color: #B4232A; } .legend .lr.shown { display: inline; } .legend .lr::before { width: 7px; height: 7px; border-radius: 50%; }
.legend .lf::before { background: repeating-linear-gradient(90deg, currentColor 0 4px, transparent 4px 7px); }
svg { display: block; width: 100%; height: auto; font-family: var(--sans); }
svg .grid { stroke: #ECE8DE; stroke-width: 1; }
svg .axis { fill: #6B7477; font-size: 11px; }
svg .low { stroke: var(--amber); stroke-width: 1.5; stroke-dasharray: 5 4; }
svg .low-label { fill: var(--amber); font-size: 11px; font-weight: 600; }
svg .band-a { fill: #8A9396; opacity: .16; } svg .band-b { fill: #0F6B73; opacity: .16; } svg .band-f { fill: #0F6B73; opacity: .14; }
svg .line-a { fill: none; stroke: #8A9396; stroke-width: 2; stroke-linejoin: round; }
svg .line-b { fill: none; stroke: #0F6B73; stroke-width: 2.5; stroke-linejoin: round; }
svg .line-g { fill: none; stroke: #1A1D1E; stroke-width: 2; stroke-linejoin: round; }
svg .line-f { fill: none; stroke: #0F6B73; stroke-width: 2; stroke-dasharray: 4 3; }
svg .dot-a { fill: #8A9396; stroke: #fff; stroke-width: 2; } svg .dot-b { fill: #0F6B73; stroke: #fff; stroke-width: 2; }
svg .val-a { fill: #5F686B; font-size: 12px; font-weight: 700; } svg .val-b { fill: #0F6B73; font-size: 12px; font-weight: 700; }
svg .alert-line { stroke: var(--amber); stroke-width: 2; }
svg .alert-label { fill: var(--amber); font-size: 11px; font-weight: 700; }
svg .after { opacity: 0; transition: opacity .4s ease; }
svg .after.shown { opacity: 1; }
svg .dot-after { fill: #B4232A; } svg .dot-low { fill: #B4232A; stroke: #fff; stroke-width: 2; }
svg .low-callout { fill: #B4232A; font-size: 11.5px; font-weight: 700; }
.alert { border: 2px solid var(--amber); background: var(--amber-soft); border-radius: 14px; padding: 14px 16px; margin: 14px 0; }
.alert .title { font-weight: 700; color: #8A4A06; margin: 0 0 6px; }
.alert ol { margin: 6px 0 0; padding-left: 20px; }
.alert li { margin: 4px 0; }
.toggle { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0; }
button { font: 600 14px/1 var(--sans); color: var(--teal); background: #fff; border: 1.5px solid var(--teal); border-radius: 999px; padding: 10px 16px; min-height: 44px; cursor: pointer; }
button[aria-pressed="true"] { background: var(--teal); color: #fff; }
.reveal { display: none; } .reveal.shown { display: block; }
.outcome { border-left: 4px solid #B4232A; padding: 6px 0 6px 12px; margin: 12px 0; }
ul.changes { padding-left: 20px; margin: 8px 0; }
ul.changes li { margin: 6px 0; }
.arrow { color: var(--muted); font-size: 13px; }
.trade { display: grid; grid-template-columns: 1fr auto; gap: 6px 12px; align-items: baseline; }
.trade .num { font: 700 22px/1.2 var(--serif); white-space: nowrap; }
.trade .good { color: var(--teal); } .trade .watch { color: var(--amber); }
.caution { font-size: 14px; background: #F1F4F4; border-radius: 10px; padding: 10px 12px; margin: 12px 0; }
.plan { background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: 16px; margin: 12px 0; font-size: 15px; }
.plan h1 { font: 700 20px/1.3 var(--sans); margin: 0 0 4px; }
.plan h2 { font: 700 16px/1.3 var(--sans); margin: 16px 0 4px; border-bottom: 1px solid #E2DED3; padding-bottom: 3px; }
.plan .patient { display: block; border: 0; padding: 0; margin: 0 0 10px; font-weight: 600; background: none; }
.plan .rule { border: 3px solid #B42318; border-radius: 8px; padding: 10px 12px; margin: 12px 0; font-weight: 700; background: #FFF5F4; }
.plan .rule-title { display: block; font-size: 12px; letter-spacing: .05em; text-transform: uppercase; color: #B42318; }
.plan .fast { border-left: 5px solid #3730A3; background: #EEEDFB; border-radius: 0 8px 8px 0; padding: 2px 12px 6px; margin: 16px 0 6px; }
.plan .fast h2 { color: #3730A3; border-bottom-color: #C7C4EF; }
.plan .approval { margin-top: 16px; padding: 8px 12px; border: 1px solid #0B6B3A; border-radius: 8px; font-weight: 600; }
.plan .note { color: #52514E; font-size: 13px; margin-top: 12px; }
.plan ul { padding-left: 20px; }
.plan .time { font-weight: 600; white-space: nowrap; }
ul.facts { list-style: none; padding: 0; margin: 12px 0; }
ul.facts li { padding: 10px 0; border-top: 1px solid var(--line); }
ul.evidence { list-style: none; padding: 0; margin: 12px 0; display: grid; gap: 10px; }
ul.evidence li { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; display: flex; flex-direction: column; }
ul.evidence .big { font: 700 26px/1.1 var(--serif); color: var(--teal); }
footer { background: var(--deep); color: #DCE5E4; padding: 26px 16px 34px; font-size: 14px; }
footer .wrap { max-width: 600px; margin: 0 auto; }
footer a { color: #7FD1D6; }
a { color: var(--teal); }
:focus-visible { outline: 3px solid var(--amber); outline-offset: 2px; }
@media (prefers-reduced-motion: reduce) { svg .after { transition: none; } html { scroll-behavior: auto; } }
@media (min-width: 640px) { h1 { font-size: 52px; } h2 { font-size: 32px; } }
"""

SCRIPT = """
document.querySelectorAll("[data-reveal]").forEach(function (button) {
  button.addEventListener("click", function () {
    var shown = button.getAttribute("aria-pressed") !== "true";
    button.setAttribute("aria-pressed", String(shown));
    button.textContent = shown ? button.dataset.hideText : button.dataset.showText;
    document.querySelectorAll(button.dataset.reveal).forEach(function (el) { el.classList.toggle("shown", shown); });
  });
});
document.querySelectorAll("[data-lang-group]").forEach(function (group) {
  group.querySelectorAll("button[data-lang]").forEach(function (button) {
    button.addEventListener("click", function () {
      var lang = button.dataset.lang;
      group.querySelectorAll("button[data-lang]").forEach(function (b) { b.setAttribute("aria-pressed", String(b === button)); });
      document.querySelectorAll(group.dataset.langGroup).forEach(function (scope) {
        scope.querySelectorAll("[data-lang-block]").forEach(function (el) {
          el.hidden = el.dataset.langBlock !== lang;
        });
      });
    });
  });
});
"""

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rozmarra: a guided demo run</title>
<meta name="description" content="A guided run of the Rozmarra prototype with synthetic patients: a digital twin that helps doctors plan religious fasts for adults with Type 2 Diabetes.">
<meta name="theme-color" content="#0E2A33">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%230E2A33'/%3E%3Ccircle cx='16' cy='16' r='7' fill='none' stroke='%23D9770F' stroke-width='3'/%3E%3C/svg%3E">
<link rel="preload" href="fonts/Fraunces_72pt-Bold.woff2" as="font" type="font/woff2" crossorigin>
<style>{css}</style>
</head>
<body>
<header class="hero"><div class="wrap">
<p class="kicker">Digital Twin Challenge 2026 · Happiest Health</p>
<h1>Rozmarra</h1>
<p>A digital twin that helps a doctor plan a religious fast for a person with Type 2 Diabetes. This page walks through one run of our prototype, in five steps.</p>
<span class="synthetic">Every patient on this page is synthetic.</span>
</div></header>

<nav class="steps" aria-label="Steps"><ol>
<li><a href="#list">1. The list</a></li>
<li><a href="#plans">2. Before the fast</a></li>
<li><a href="#monitor">3. During the fast</a></li>
<li><a href="#tradeoff">4. A trade-off</a></li>
<li><a href="#plan">5. The family plan</a></li>
<li><a href="#evidence">The evidence</a></li>
</ol></nav>

<main>
<section id="list">
<p class="step">Step 1 · The doctor's list</p>
<h2>Dr Ananya sees who needs her first.</h2>
<p>Four of her patients plan to fast. Rozmarra sorts them by the chance of low blood sugar during the fast, so Ramesh is at the top.</p>
<ul class="patients">{patient_rows}</ul>
</section>

<section id="plans">
<p class="step">Step 2 · Before the fast</p>
<h2>The doctor tests a plan on Ramesh's twin.</h2>
<p>{ramesh_name}, {ramesh_age}, keeps the {ramesh_fast} fast on {ramesh_date}. Plan A keeps his usual medicines. In Plan B, Dr Ananya changes one dose:</p>
<ul class="changes">{r_change}</ul>
<div class="card">
<div class="legend"><span class="la">Plan A: usual dose</span><span class="lb">Plan B: changed dose</span></div>
{plans_chart}
<p class="muted small">The lines show the twin's middle estimate. The shaded bands show the range from the 10th to the 90th percentile.</p>
</div>
<div class="compare">
<div class="a"><span class="tag">Plan A</span><p class="num">{ra_low} <small>mg/dL</small></p><p class="small muted">lowest, at {ra_time}</p><p class="num">{ra_chance}</p><p class="small muted">chance of low blood sugar</p></div>
<div class="b"><span class="tag">Plan B</span><p class="num">{rb_low} <small>mg/dL</small></p><p class="small muted">lowest, at {rb_time}</p><p class="num">{rb_chance}</p><p class="small muted">chance of low blood sugar</p></div>
</div>
<p><strong>Rozmarra does not choose the dose.</strong> It shows what each plan may do, and the doctor decides.</p>
</section>

<section id="monitor">
<p class="step">Step 3 · During the fast</p>
<h2>At {alert_time}, Rozmarra warns the doctor.</h2>
<p>During the fast, Rozmarra reads Ramesh's glucose sensor every five minutes.</p>
<div class="alert" id="reasons">
<p class="title">{alert_chance} chance of low blood sugar in the next 60 minutes ({alert_word}).</p>
<div class="toggle" data-lang-group="#reasons"><button type="button" data-lang="en" aria-pressed="true">English</button><button type="button" data-lang="hi" aria-pressed="false">हिन्दी</button></div>
<ol>{reasons}</ol>
</div>
<div class="card">
<div class="legend"><span class="lg">Readings until {alert_time}</span><span class="lf">Forecast</span><span class="lr reveal" id="after-key">Readings after the warning</span></div>
{monitor_chart}
</div>
<div class="toggle"><button type="button" data-reveal="#after, #outcome, #after-key" aria-pressed="false" data-show-text="Show what happened next" data-hide-text="Hide what happened next">Show what happened next</button></div>
<p class="outcome reveal" id="outcome">His glucose fell below 70 mg/dL at <strong>{low_time}</strong>, {lead} minutes after the warning. In a real clinic, those minutes are time to act.</p>
</section>

<section id="tradeoff">
<p class="step">Step 4 · A trade-off</p>
<h2>Sunita fasts without food or water.</h2>
<p>{sunita_name} keeps {sunita_fast}. Dr Ananya tests a changed plan:</p>
<ul class="changes">{s_change}</ul>
<div class="card trade">
<span>Chance of low blood sugar during the fast</span><span class="num good">{sa_low} → {sb_low}</span>
<span>Chance of high blood sugar after the fast</span><span class="num watch">{sa_high} → {sb_high}</span>
</div>
<p>The changed plan lowers one risk and raises another. <strong>Rozmarra shows the trade-off. It does not hide it.</strong></p>
{caution}
</section>

<section id="plan">
<p class="step">Step 5 · The family plan</p>
<h2>After approval, the family gets a clear plan.</h2>
<p>The plan comes from fixed, written templates in English and Hindi. The rule to break the fast comes first. {approved}.</p>
<div class="toggle" data-lang-group="#plans-doc"><button type="button" data-lang="en" aria-pressed="true">English</button><button type="button" data-lang="hi" aria-pressed="false">हिन्दी</button></div>
<div id="plans-doc">
<div class="plan" data-lang-block="en" lang="en">{plan_en}</div>
<div class="plan" data-lang-block="hi" lang="hi" hidden>{plan_hi}</div>
</div>
</section>

<section id="safe">
<p class="step">Safe by design</p>
<h2>The doctor decides.</h2>
<ul class="facts">
<li>Every sentence a patient reads comes from fixed, written templates. Rozmarra does not use AI to write medical advice.</li>
<li>Rozmarra never changes a medicine on its own.</li>
<li>Rozmarra never judges the decision to fast.</li>
</ul>
</section>

<section id="evidence">
<p class="step">The evidence</p>
<h2>How well does Rozmarra predict low blood sugar?</h2>
<ul class="evidence">{evidence}</ul>
<p class="small muted">“94 in 100” means that, when Rozmarra compares an hour that ended in low blood sugar with one that did not, it gives the risky hour the higher chance 94 times in 100. Random guessing would get 50. It is not accuracy. Technical measures: AUROC 0.943 and 0.973.</p>
<p class="small muted">Rozmarra is a research prototype. It is not an approved medical device, and no doctor has reviewed its medical content yet.</p>
</section>
</main>

<footer><div class="wrap">
<p><strong>Team NOT_SOMEONE_IMPORTANT</strong>, IIT (ISM) Dhanbad: Shivansh Gautam, Aman Soni and Divy Sharma.</p>
<p>The code, the model card and the data card are on GitHub: <a href="{repo}">github.com/lucifer-135/Rozmarra</a>.</p>
<p class="small">Rozmarra (रोज़मर्रा) means “everyday”. Safer fasts, every day.</p>
</div></footer>
<script>{script}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://127.0.0.1:8000/api", help="The base URL of the running Rozmarra API.")
    args = parser.parse_args()
    page = build(Api(args.api))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8", newline="\n")
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(page.encode('utf-8')) // 1024} KB)")


if __name__ == "__main__":
    main()
