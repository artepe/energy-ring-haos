"""Check statistics-mode sums against ground truth at tricky times (DST, hour/day edges)."""
import json, pathlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).parent
URL = (HERE / "index.html").as_uri()
TZ = ZoneInfo("Europe/Helsinki")

TIMES = [
    "2026-10-25T10:37:20+02:00",  # autumn DST day (25 h), Sunday
    "2026-10-25T11:00:05+02:00",  # just after the hour: last hour not compiled yet
    "2026-10-26T00:03:00+02:00",  # Monday right after midnight (week starts today)
    "2026-03-29T05:10:00+03:00",  # spring DST day (23 h)
    "2026-01-01T00:20:00+02:00",  # new year: year/month/today all start at midnight
    "2026-07-15T14:44:59+03:00",  # ordinary day
]
PERIODS = ["today", "yesterday", "week", "month", "year"]


def expected_start(now, period):
    d0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "today":
        return d0, None
    if period == "yesterday":
        return (d0 - timedelta(days=1)).replace(tzinfo=None).replace(tzinfo=TZ), d0
    if period == "week":
        s = d0 - timedelta(days=d0.weekday())
        return s.replace(tzinfo=None).replace(tzinfo=TZ), None
    if period == "month":
        return d0.replace(day=1).replace(tzinfo=None).replace(tzinfo=TZ), None
    if period == "year":
        return d0.replace(month=1, day=1).replace(tzinfo=None).replace(tzinfo=TZ), None


SETUP = r"""
([period]) => {
  window.wsCalls = [];
  const kwf = {
    'sensor.a': (t) => 1 + 0.5 * Math.sin(t / 7e6) + ((t / 3e5) % 7) / 10,
    'sensor.b': (t) => ((Math.floor(t / 36e5) % 24) < 6 ? 3.7 : 0.05),
    'sensor.tot': (t) => 2.4 + 0.5 * Math.sin(t / 7e6) + ((t / 3e5) % 7) / 10 + ((Math.floor(t / 36e5) % 24) < 6 ? 3.7 : 0),
  };
  window.kwf = kwf;
  const defs = { 'sensor.a': { kw: kwf['sensor.a'], wh: true }, 'sensor.b': { kw: kwf['sensor.b'] }, 'sensor.tot': { kw: kwf['sensor.tot'] } };
  const states = {};
  for (const k of Object.keys(kwf)) states[k] = st(k, 1, 'kWh', k);
  document.getElementById('grid').innerHTML = '';
  mount('S', { type: 'custom:energy-ring-card', period, total_entity: 'sensor.tot', entities: ['sensor.a', 'sensor.b'] },
        makeHass({ states, callWS: makeStatsWS(defs) }), 380);
}
"""

CHECK = r"""
() => {
  const c = document.getElementById('S');
  const s = c._stats;
  const out = { start: s.start.toISOString(), end: s.end ? s.end.toISOString() : null, ids: {} };
  for (const id of Object.keys(window.kwf)) {
    const exp = expectedKWh(window.kwf[id], s.start.getTime(), s.end ? s.end.getTime() : null);
    out.ids[id] = [s.sums[id], exp];
  }
  out.calls = window.wsCalls.filter(m => m.type.endsWith('during_period')).map(m => [m.period, m.start_time, m.end_time || null, JSON.stringify(m.units), JSON.stringify(m.types)]);
  out.center = c.shadowRoot.querySelector('.c-val').textContent;
  return out;
}
"""

fails = 0
with sync_playwright() as p:
    b = p.chromium.launch()
    for t in TIMES:
        now = datetime.fromisoformat(t).astimezone(TZ)
        for period in PERIODS:
            ctx = b.new_context(timezone_id="Europe/Helsinki", locale="fi-FI")
            page = ctx.new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            page.clock.set_fixed_time(t)
            page.goto(URL)
            page.evaluate(SETUP, [period])
            page.wait_for_function("() => document.getElementById('S')._stats", timeout=5000)
            r = page.evaluate(CHECK)
            es, ee = expected_start(now, period)
            ok_range = r["start"] == es.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S.000Z") and \
                (r["end"] == (ee.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S.000Z") if ee else None))
            ok_sums = all(abs(a - e) < 1e-6 * max(1, abs(e)) for a, e in r["ids"].values())
            status = "OK " if ok_range and ok_sums and not errs else "FAIL"
            if status == "FAIL":
                fails += 1
            print(f"{status} {t} {period:9s} start={r['start']} sums=" +
                  ", ".join(f"{k.split('.')[1]}:{a:.4f}/{e:.4f}" for k, (a, e) in r["ids"].items()) +
                  f" center={r['center']} periods={[c[0] for c in r['calls']]}" + (f" ERR={errs}" if errs else "") +
                  ("" if ok_range else f" RANGE expected {es.isoformat()} / {ee}"))
            ctx.close()
    # show one full call log
    print(json.dumps(r["calls"], indent=0))
    b.close()
print("FAILS:", fails)
