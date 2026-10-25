"""Render energy-ring-card scenarios in headless Chromium and screenshot them."""
import json, sys, pathlib
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
URL = (HERE / "index.html").as_uri()
FIXED = "2026-10-25T10:37:20+02:00"

SETUP = r"""
(dark) => {
  if (dark) document.documentElement.classList.add('dark');
  const W = (id, w, n) => st(id, w, 'W', n, { device_class: 'power' });
  const kW = (id, w, n) => st(id, w, 'kW', n, { device_class: 'power' });
  const live = {
    'sensor.koko_talo': kW('sensor.koko_talo', 8.92, 'Koko talo'),
    'sensor.vilp': W('sensor.vilp', 2410, 'VILP'),
    'sensor.tesla': W('sensor.tesla', 3680, 'Tesla Wall Connector'),
    'sensor.keittio': W('sensor.keittio', 620, 'Keittiö'),
    'sensor.valaistus': W('sensor.valaistus', 180, 'Valaistus'),
    'sensor.iv': W('sensor.iv', 90, 'IV-kone'),
    'sensor.pakastin': W('sensor.pakastin', 52, 'Pakastin'),
  };
  const ents = [
    { entity: 'sensor.vilp', name: 'Lämpöpumppu' },
    { entity: 'sensor.tesla', name: 'Tesla' },
    'sensor.keittio', 'sensor.valaistus', 'sensor.iv', 'sensor.pakastin',
  ];
  mount('A', { type: 'custom:energy-ring-card', total_entity: 'sensor.koko_talo', entities: ents }, makeHass({ states: live, dark }), 420, 'A live + total, 6 entities');

  const kwf = {
    'sensor.e_total': (t) => 2.2 + 1.1 * Math.sin(t / 36e5 / 3) + 0.6 * Math.cos(t / 36e5 / 1.7),
    'sensor.e_vilp': (t) => 1.05 + 0.5 * Math.sin(t / 36e5 / 3),
    'sensor.e_tesla': (t) => ((Math.floor(t / 36e5) % 24) < 5 ? 3.6 : 0),
    'sensor.e_sauna': (t) => ((Math.floor(t / 36e5) % 24) === 17 ? 6 : 0),
    'sensor.e_kodinkoneet': (t) => 0.32 + 0.1 * Math.sin(t / 36e5),
  };
  window.kwf = kwf;
  const defs = Object.fromEntries(Object.entries(kwf).map(([k, f]) => [k, { kw: f, wh: k === 'sensor.e_vilp' }]));
  const est = {};
  for (const k of Object.keys(kwf)) est[k] = st(k, 12345, 'kWh', k.replace('sensor.e_', ''), { state_class: 'total_increasing' });
  est['sensor.e_vilp'].attributes.friendly_name = 'Lämpöpumppu';
  est['sensor.e_tesla'].attributes.friendly_name = 'Tesla';
  est['sensor.e_sauna'].attributes.friendly_name = 'Sauna';
  est['sensor.e_kodinkoneet'].attributes.friendly_name = 'Kodinkoneet';
  window.est = est; window.defs = defs;
  mount('B', { type: 'custom:energy-ring-card', title: 'Sähkönkulutus', period: 'today', total_entity: 'sensor.e_total',
    entities: ['sensor.e_vilp', 'sensor.e_tesla', 'sensor.e_sauna', 'sensor.e_kodinkoneet'] },
    makeHass({ states: est, dark, callWS: makeStatsWS(defs) }), 420, 'B stats today + title');

  mount('D', { type: 'custom:energy-ring-card', total_entity: 'sensor.koko_talo', entities: ents }, makeHass({ states: live, dark }), 300, 'D narrow 300px');

  const many = {};
  const names = ['Lämpöpumppu', 'Tesla', 'Sauna', 'Keittiö', 'Pesukone', 'Kuivausrumpu', 'Valaistus', 'IV-kone', 'Pakastin', 'Autotalli'];
  const vals = [2410, 1900, 0, 640, 410, 380, 180, 90, 52, 30];
  names.forEach((n, i) => { many['sensor.m' + i] = W('sensor.m' + i, vals[i], n); });
  mount('E', { type: 'custom:energy-ring-card', legend: true, entities: Object.keys(many) }, makeHass({ states: many, dark }), 420, 'E 10 entities, legend:true');

  const one = { 'sensor.koko_talo': kW('sensor.koko_talo', 3.2, 'Koko talo'), 'sensor.vilp': W('sensor.vilp', 2410, 'VILP') };
  mount('F', { type: 'custom:energy-ring-card', total_entity: 'sensor.koko_talo', entities: [{ entity: 'sensor.vilp', name: 'Lämpöpumppu' }] }, makeHass({ states: one, dark }), 360, 'F single entity + total');

  const zero = { 'sensor.a': W('sensor.a', 0, 'Tesla'), 'sensor.b': st('sensor.b', 'unavailable', 'W', 'Sauna'), 'sensor.c': W('sensor.c', 0, 'Kiuas') };
  mount('G', { type: 'custom:energy-ring-card', entities: ['sensor.a', 'sensor.b', 'sensor.c'] }, makeHass({ states: zero, dark }), 360, 'G all zero / unavailable');

  const two = { 'sensor.x': W('sensor.x', 5200, 'Tesla'), 'sensor.y': W('sensor.y', 1350, 'Ilmalämpöpumppu olohuone') };
  mount('H', { type: 'custom:energy-ring-card', entities: ['sensor.x', 'sensor.y'], sort: true }, makeHass({ states: two, dark, lang: 'en' }), 360, 'H two entities, en');
}
"""


def ring_point(page, card_id, angle_deg, radius=122):
    """Viewport coordinates of a point on the ring (0deg = top, clockwise)."""
    return page.evaluate(
        """([id, a, r]) => {
          const svg = document.getElementById(id).shadowRoot.querySelector('svg');
          const b = svg.getBoundingClientRect();
          const k = b.width / 360, rad = a * Math.PI / 180;
          return [b.left + (180 + r * Math.sin(rad)) * k, b.top + (180 - r * Math.cos(rad)) * k];
        }""",
        [card_id, angle_deg, radius],
    )


def run(dark):
    tag = "dark" if dark else "light"
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1400, "height": 1700}, device_scale_factor=2,
                            timezone_id="Europe/Helsinki", locale="fi-FI")
        page = ctx.new_page()
        logs = []
        page.on("console", lambda m: logs.append(f"{m.type}: {m.text}"))
        page.on("pageerror", lambda e: logs.append(f"PAGEERROR: {e}"))
        page.clock.set_fixed_time(FIXED)
        page.goto(URL)
        page.evaluate("document.fonts.ready")
        page.evaluate(SETUP, dark)
        page.wait_for_function("() => document.getElementById('B')._stats", timeout=5000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / f"all-{tag}.png"), full_page=True)
        for cid in "ABDEFGH":
            page.locator(f"#slot-{cid}").screenshot(path=str(OUT / f"{cid}-{tag}.png"))
        # label diagnostics
        diag = page.evaluate("""() => [...document.querySelectorAll('energy-ring-card')].map(c => ({
            id: c.id,
            labeled: c._m ? [...c._m.labeled] : null,
            segs: c._m ? c._m.segs.map(s => [s.key, s.name, s.valStr, s.pctStr, +(s.sweep*180/Math.PI).toFixed(1)]) : null,
            legend: [...c.shadowRoot.querySelectorAll('.li')].map(l => l.textContent),
            center: c.shadowRoot.querySelector('.c-top').textContent + ' | ' + c.shadowRoot.querySelector('.c-val').textContent + ' | ' + c.shadowRoot.querySelector('.c-sub').textContent,
            msg: c.shadowRoot.querySelector('.msg').textContent,
        }))""")
        # hover on the first segment of A (mid angle of e0)
        mid = page.evaluate("() => document.getElementById('A')._m.segs[0].mid * 180 / Math.PI")
        x, y = ring_point(page, "A", mid)
        page.mouse.move(x, y)
        page.wait_for_timeout(450)
        page.locator("#slot-A").screenshot(path=str(OUT / f"A-hover-{tag}.png"))
        hover_center = page.evaluate("() => { const r = document.getElementById('A').shadowRoot; return r.querySelector('.c-top').textContent + ' | ' + r.querySelector('.c-val').textContent + ' | ' + r.querySelector('.c-sub').textContent; }")
        page.mouse.click(x, y)
        # hover on "Muu" segment (last)
        mid2 = page.evaluate("() => { const s = document.getElementById('A')._m.segs; return s[s.length-1].mid * 180 / Math.PI; }")
        x2, y2 = ring_point(page, "A", mid2)
        page.mouse.move(x2, y2)
        page.wait_for_timeout(300)
        hover_other = page.evaluate("() => { const r = document.getElementById('A').shadowRoot; return r.querySelector('.c-top').textContent + ' | ' + r.querySelector('.c-val').textContent + ' | ' + r.querySelector('.c-sub').textContent; }")
        page.mouse.click(x2, y2)
        # click centre
        cx, cy = ring_point(page, "A", 0, 0)
        page.mouse.move(cx, cy)
        page.mouse.click(cx, cy)
        events = page.evaluate("() => window.events")
        page.mouse.move(5, 5)
        print(json.dumps({"theme": tag, "diag": diag, "hover": hover_center, "hover_other": hover_other,
                          "events": events, "logs": logs}, ensure_ascii=False, indent=1))
        b.close()


if __name__ == "__main__":
    run(len(sys.argv) > 1 and sys.argv[1] == "dark")
