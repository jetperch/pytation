# Copyright 2026 Jetperch LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""Parse pytation logs and render an HTML timing report.

Two log formats are recognized:

* Station log (``<station>/log/<timestamp>_<pid>.log``) prefixed with
  ``LEVEL:YYYY-MM-DD HH:MM:SS,mmm:filename.py:lineno:loggername:message``.
  May contain multiple back-to-back runs, each bracketed by
  ``--- TEST START suite_setup ---`` ... ``--- TEST DONE suite_teardown ... ---``.
* Run log (``log.txt`` inside ``<station>/data/<timestamp>.zip``) prefixed with
  ``YYYY-MM-DD HH:MM:SS,mmm loggername LEVEL: message``. Contains the inner
  portion of one run (no suite_setup/suite_teardown markers).
"""

from dataclasses import dataclass, field
from datetime import datetime
import html
import math
import os
import re

from pytation.zipfs import ZipReadFS


_TS_FMT = '%Y-%m-%d %H:%M:%S,%f'
_RE_STATION = re.compile(
    r'^[A-Z]+:(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}):[^:]+:\d+:[^:]+:(.*)$')
_RE_ZIP = re.compile(
    r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) \S+ [A-Z]+: (.*)$')
_RE_TEST_START = re.compile(r'^--- TEST START (.+?) ---\s*$')
_RE_TEST_DONE = re.compile(r'^--- TEST DONE (.+?) with status (\S+?) ---\s*$')
_RE_UNTIMED_START = re.compile(r'^--- UNTIMED START (.+?) ---\s*$')
_RE_UNTIMED_DONE = re.compile(r'^--- UNTIMED DONE (.+?) ---\s*$')

_PALETTE = [
    '#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
    '#edc949', '#af7aa1', '#ff9da7', '#9c755f', '#bab0ab',
]


@dataclass
class Test:
    name: str
    start: datetime
    end: datetime
    status: str
    untimed: list = field(default_factory=list)  # list of (name, start, end)

    @property
    def duration(self) -> float:
        """Wall-clock duration including any untimed regions."""
        return (self.end - self.start).total_seconds()

    @property
    def excluded(self) -> float:
        """Total seconds spent inside untimed regions."""
        return sum((e - s).total_seconds() for _n, s, e in self.untimed)

    @property
    def active(self) -> float:
        """Wall duration minus excluded untimed time."""
        return max(0.0, self.duration - self.excluded)


@dataclass
class Run:
    start: datetime
    end: datetime
    tests: list = field(default_factory=list)
    synthetic: bool = False

    @property
    def duration(self) -> float:
        """Wall-clock duration of the run."""
        return (self.end - self.start).total_seconds()

    @property
    def excluded(self) -> float:
        return sum(t.excluded for t in self.tests)

    @property
    def active(self) -> float:
        return max(0.0, self.duration - self.excluded)

    @property
    def has_excluded(self) -> bool:
        return any(t.excluded > 0 for t in self.tests)

    @property
    def status(self) -> str:
        for t in self.tests:
            if str(t.status) != '0':
                return t.status
        return '0'


def _parse_ts(s: str) -> datetime:
    return datetime.strptime(s, _TS_FMT)


def _iter_events(text: str):
    """Yield (timestamp, message) tuples for each line we can parse."""
    for line in text.splitlines():
        m = _RE_STATION.match(line) or _RE_ZIP.match(line)
        if m:
            yield _parse_ts(m.group(1)), m.group(2)


def parse_log_text(text: str) -> list:
    """Parse log text into a list of Run objects."""
    runs = []
    pending = {}  # name -> (start_ts, [untimed list])
    test_stack = []  # names currently open, innermost last
    untimed_stack = []  # list of (name, start_ts), innermost last
    current_run_tests = []
    current_run_start = None

    loose_first = None  # for synthetic-run case (zip log.txt)
    loose_last = None

    for ts, msg in _iter_events(text):
        m_ut_start = _RE_UNTIMED_START.match(msg)
        if m_ut_start:
            untimed_stack.append((m_ut_start.group(1), ts))
            loose_last = ts
            continue
        m_ut_done = _RE_UNTIMED_DONE.match(msg)
        if m_ut_done and untimed_stack:
            name, ut_start = untimed_stack.pop()
            if test_stack:
                # attach to innermost open test
                pending[test_stack[-1]][1].append((name, ut_start, ts))
            loose_last = ts
            continue
        m_start = _RE_TEST_START.match(msg)
        if m_start:
            name = m_start.group(1)
            pending[name] = (ts, [])
            test_stack.append(name)
            if name == 'suite_setup':
                current_run_tests = []
                current_run_start = ts
            if loose_first is None:
                loose_first = ts
            loose_last = ts
            continue
        m_done = _RE_TEST_DONE.match(msg)
        if m_done:
            name, status = m_done.group(1), m_done.group(2)
            entry = pending.pop(name, None)
            if entry is None:
                continue
            start, untimed = entry
            if name in test_stack:
                test_stack.remove(name)
            test = Test(name=name, start=start, end=ts, status=status,
                        untimed=untimed)
            current_run_tests.append(test)
            loose_last = ts
            if name == 'suite_teardown' and current_run_start is not None:
                runs.append(Run(start=current_run_start, end=ts,
                                tests=current_run_tests))
                current_run_tests = []
                current_run_start = None

    if not runs and current_run_tests:
        # Zip log.txt: no suite_setup/teardown wrapping; synthesize one run.
        start = loose_first or current_run_tests[0].start
        end = loose_last or current_run_tests[-1].end
        runs.append(Run(start=start, end=end,
                        tests=current_run_tests, synthetic=True))
    elif current_run_tests:
        # Trailing tests after the last suite_teardown (uncommon); attach as
        # a synthetic run so they aren't silently dropped.
        start = current_run_tests[0].start
        end = current_run_tests[-1].end
        runs.append(Run(start=start, end=end,
                        tests=current_run_tests, synthetic=True))
    return runs


def load_input(path: str):
    """Load runs from a .log file or a .zip archive containing log.txt.

    Returns (display_name, runs).
    """
    if path.lower().endswith('.zip'):
        fs = ZipReadFS(path)
        try:
            with fs.open('log.txt', 'rt') as f:
                text = f.read()
        finally:
            fs.close()
        display = os.path.basename(path)
    else:
        with open(path, 'rt', encoding='utf-8', errors='replace') as f:
            text = f.read()
        display = os.path.basename(path)
    return display, parse_log_text(text)


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f'{seconds:.3f} s'
    m, s = divmod(seconds, 60)
    if m < 60:
        return f'{int(m)}m {s:05.2f}s'
    h, m = divmod(m, 60)
    return f'{int(h)}h {int(m):02d}m {s:05.2f}s'


def _pie_svg(slices, size: int = 360) -> str:
    """Render a pie chart as inline SVG.

    :param slices: list of (label, value, color) tuples; values must be >= 0.
    """
    total = sum(v for _, v, _ in slices)
    if total <= 0:
        return f'<svg width="{size}" height="{size}"></svg>'
    cx = cy = size / 2
    r = size / 2 - 4
    parts = [f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
             f'xmlns="http://www.w3.org/2000/svg">']
    angle = -math.pi / 2  # start at 12 o'clock
    nonzero = [(lab, v, c) for lab, v, c in slices if v > 0]
    if len(nonzero) == 1:
        lab, _v, c = nonzero[0]
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}" '
                     f'stroke="#fff" stroke-width="1"><title>'
                     f'{html.escape(lab)}</title></circle>')
    else:
        for lab, v, c in nonzero:
            sweep = 2 * math.pi * (v / total)
            x1 = cx + r * math.cos(angle)
            y1 = cy + r * math.sin(angle)
            angle2 = angle + sweep
            x2 = cx + r * math.cos(angle2)
            y2 = cy + r * math.sin(angle2)
            large_arc = 1 if sweep > math.pi else 0
            d = (f'M {cx:.3f} {cy:.3f} '
                 f'L {x1:.3f} {y1:.3f} '
                 f'A {r:.3f} {r:.3f} 0 {large_arc} 1 {x2:.3f} {y2:.3f} Z')
            pct = 100 * v / total
            parts.append(f'<path d="{d}" fill="{c}" stroke="#fff" '
                         f'stroke-width="1"><title>'
                         f'{html.escape(lab)}: {_fmt_duration(v)} '
                         f'({pct:.1f}%)</title></path>')
            angle = angle2
    parts.append('</svg>')
    return ''.join(parts)


def _legend_table(slices) -> str:
    total = sum(v for _, v, _ in slices)
    rows = ['<table class="legend"><thead><tr>'
            '<th></th><th>Test</th><th>Duration</th><th>%</th>'
            '</tr></thead><tbody>']
    for lab, v, c in slices:
        pct = (100 * v / total) if total > 0 else 0.0
        rows.append(
            f'<tr><td><span class="sw" style="background:{c}"></span></td>'
            f'<td>{html.escape(lab)}</td>'
            f'<td class="num">{_fmt_duration(v)}</td>'
            f'<td class="num">{pct:.1f}%</td></tr>')
    rows.append('</tbody></table>')
    return ''.join(rows)


def _color_map(names):
    """Stable color assignment by sorted name index."""
    return {n: _PALETTE[i % len(_PALETTE)] for i, n in enumerate(names)}


def _render_run(run: Run, idx: int, total_runs: int, open_first: bool) -> str:
    names = [t.name for t in run.tests]
    cmap = _color_map(sorted(set(names)))
    show_excl = run.has_excluded
    slices = [(t.name, t.active, cmap[t.name]) for t in run.tests]

    rows = []
    for t in run.tests:
        status_cls = 'ok' if str(t.status) == '0' else 'fail'
        cells = [
            f'<td>{html.escape(t.name)}</td>',
            f'<td class="num">{t.start.strftime("%H:%M:%S.%f")[:-3]}</td>',
        ]
        if show_excl:
            cells += [
                f'<td class="num">{_fmt_duration(t.active)}</td>',
                f'<td class="num excl">'
                f'{_fmt_duration(t.excluded) if t.excluded > 0 else "-"}</td>',
                f'<td class="num">{_fmt_duration(t.duration)}</td>',
            ]
        else:
            cells.append(f'<td class="num">{_fmt_duration(t.duration)}</td>')
        cells.append(
            f'<td class="num {status_cls}">{html.escape(str(t.status))}</td>')
        rows.append('<tr>' + ''.join(cells) + '</tr>')

    if show_excl:
        header_cells = ('<th>Test</th><th>Start</th><th>Active</th>'
                        '<th>Excluded</th><th>Wall</th><th>Status</th>')
    else:
        header_cells = ('<th>Test</th><th>Start</th><th>Duration</th>'
                        '<th>Status</th>')
    table = (
        '<table class="tests"><thead><tr>' + header_cells +
        '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'
    )

    label_extra = ' (synthesized: no suite_setup/teardown in source)' \
        if run.synthetic else ''
    summary_items = [
        f'<div><span class="lbl">Started:</span> '
        f'{run.start.strftime("%Y-%m-%d %H:%M:%S")}</div>',
        f'<div><span class="lbl">Wall:</span> '
        f'{_fmt_duration(run.duration)}</div>',
    ]
    if show_excl:
        summary_items.append(
            f'<div><span class="lbl">Active:</span> '
            f'{_fmt_duration(run.active)}</div>')
        summary_items.append(
            f'<div><span class="lbl">Excluded:</span> '
            f'<span class="excl">{_fmt_duration(run.excluded)}</span></div>')
    summary_items.append(
        f'<div><span class="lbl">Status:</span> '
        f'<span class="{"ok" if str(run.status) == "0" else "fail"}">'
        f'{html.escape(str(run.status))}</span></div>')
    summary_items.append(
        f'<div><span class="lbl">Tests:</span> {len(run.tests)}</div>')
    summary = '<div class="run-summary">' + ''.join(summary_items) + '</div>'

    chart_title = ('Active duration per test (untimed regions excluded)'
                   if show_excl else '')
    chart = (
        f'<div class="chart-row">'
        f'<div class="chart">{_pie_svg(slices)}</div>'
        f'<div class="legend-wrap">'
        f'{("<div class=\"legend-title\">" + chart_title + "</div>") if chart_title else ""}'
        f'{_legend_table(slices)}</div>'
        f'</div>'
    )

    open_attr = ' open' if open_first else ''
    title = (f'Run {idx + 1} of {total_runs} '
             f'&mdash; {run.start.strftime("%Y-%m-%d %H:%M:%S")}{label_extra}')
    return (f'<details class="run"{open_attr}>'
            f'<summary>{title}</summary>'
            f'{summary}{chart}{table}'
            f'</details>')


def _render_aggregate(runs) -> str:
    show_excl = any(r.has_excluded for r in runs)
    by_name = {}
    for run in runs:
        for t in run.tests:
            by_name.setdefault(t.name, []).append(t.active)
    rows_data = []
    for name, durs in by_name.items():
        rows_data.append({
            'name': name,
            'count': len(durs),
            'avg': sum(durs) / len(durs),
            'min': min(durs),
            'max': max(durs),
            'total': sum(durs),
        })
    rows_data.sort(key=lambda r: r['total'], reverse=True)
    grand_total = sum(r['total'] for r in rows_data) or 1.0

    cmap = _color_map(sorted(by_name))
    rows = []
    for r in rows_data:
        pct = 100 * r['total'] / grand_total
        rows.append(
            f'<tr>'
            f'<td><span class="sw" style="background:{cmap[r["name"]]}"></span>'
            f'{html.escape(r["name"])}</td>'
            f'<td class="num">{r["count"]}</td>'
            f'<td class="num">{_fmt_duration(r["avg"])}</td>'
            f'<td class="num">{_fmt_duration(r["min"])}</td>'
            f'<td class="num">{_fmt_duration(r["max"])}</td>'
            f'<td class="num">{_fmt_duration(r["total"])}</td>'
            f'<td class="num">{pct:.1f}%</td>'
            f'</tr>')
    duration_label = 'Active' if show_excl else 'Duration'
    table = (
        '<table class="tests"><thead><tr>'
        f'<th>Test</th><th>Runs</th><th>Avg {duration_label.lower()}</th>'
        '<th>Min</th><th>Max</th>'
        f'<th>Total {duration_label.lower()}</th><th>% of total</th>'
        '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'
    )

    slices = [(r['name'], r['avg'], cmap[r['name']]) for r in rows_data]
    legend_title = (
        'Average active duration per test (untimed regions excluded)'
        if show_excl else 'Average duration per test')
    chart = (
        f'<div class="chart-row">'
        f'<div class="chart">{_pie_svg(slices)}</div>'
        f'<div class="legend-wrap"><div class="legend-title">{legend_title}'
        f'</div>{_legend_table(slices)}</div>'
        f'</div>'
    )
    return (f'<section class="aggregate">'
            f'<h2>Aggregate across {len(runs)} runs</h2>'
            f'{chart}{table}'
            f'</section>')


_CSS = """
body { font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
       margin: 24px; color: #222; }
h1 { margin: 0 0 4px; font-size: 22px; }
h2 { margin: 24px 0 12px; font-size: 18px; border-bottom: 1px solid #ddd;
     padding-bottom: 4px; }
.meta { color: #666; font-size: 13px; margin-bottom: 16px; }
.run-summary { display: flex; gap: 24px; flex-wrap: wrap;
               background: #f5f7fa; padding: 10px 14px; border-radius: 6px;
               margin: 8px 0 14px; font-size: 14px; }
.run-summary .lbl { color: #666; margin-right: 6px; }
.chart-row { display: flex; gap: 24px; align-items: flex-start;
             flex-wrap: wrap; margin: 12px 0; }
.chart { flex: 0 0 auto; }
.legend-wrap { flex: 1 1 320px; min-width: 280px; }
.legend-title { font-size: 13px; color: #666; margin-bottom: 4px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { padding: 5px 10px; text-align: left;
         border-bottom: 1px solid #eee; }
th { background: #f0f2f5; font-weight: 600; }
tbody tr:nth-child(even) { background: #fafbfc; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.sw { display: inline-block; width: 12px; height: 12px; border-radius: 2px;
      margin-right: 6px; vertical-align: middle; }
.ok { color: #2a7d2e; }
.fail { color: #c0392b; font-weight: 600; }
.excl { color: #8a6d3b; }
details.run { margin: 14px 0; border: 1px solid #e0e3e8; border-radius: 6px;
              padding: 8px 14px; background: #fff; }
details.run > summary { cursor: pointer; font-weight: 600; padding: 4px 0; }
section.aggregate { background: #fff; border: 1px solid #e0e3e8;
                    border-radius: 6px; padding: 8px 14px; }
"""


def render_html(display_name: str, runs: list) -> str:
    generated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    total_wall = sum(r.duration for r in runs)
    total_test_wall = sum(t.duration for r in runs for t in r.tests)
    total_excluded = sum(r.excluded for r in runs)

    bits = [
        f'Source: <code>{html.escape(display_name)}</code>',
        f'Generated: {generated}',
        f'Runs: {len(runs)}',
        f'Wall time: {_fmt_duration(total_wall)}',
        f'Test time: {_fmt_duration(total_test_wall)}',
    ]
    if total_excluded > 0:
        bits.append(
            f'Excluded (untimed): <span class="excl">'
            f'{_fmt_duration(total_excluded)}</span>')
    header = (
        f'<h1>Pytation timing report</h1>'
        f'<div class="meta">' + ' &middot; '.join(bits) + '</div>'
    )
    body = [header]
    if len(runs) > 1:
        body.append(_render_aggregate(runs))
        body.append('<h2>Per-run detail</h2>')
    for i, run in enumerate(runs):
        body.append(_render_run(run, i, len(runs), open_first=(i == 0)))

    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        f'<title>Pytation report &mdash; {html.escape(display_name)}</title>'
        f'<style>{_CSS}</style></head><body>'
        + ''.join(body) +
        '</body></html>'
    )
