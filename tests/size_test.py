"""Card inside fixed-size Home Assistant sections-grid cells (grid_options columns/rows).

Rows are 56 px with 8 px gaps, so rows: 3 = 184 px, rows: 4 = 248 px. A 12-column section is
roughly 330-500 px wide, so columns: 6 is about 160-245 px.
"""
import json, pathlib, sys
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
URL = (HERE / "index.html").as_uri()
DARK = len(sys.argv) > 1 and sys.argv[1] == "dark"

CELLS = [  # (id, width, height or None for rows: auto, title)
    ("c6x3n", 160, 184, False),
    ("c6x3w", 236, 184, False),
    ("c6x3t", 236, 184, True),
    ("c6x4", 236, 248, False),
    ("c12x4", 330, 248, False),
    ("c12x5", 480, 312, False),
    ("cauto", 480, None, True),
]

SETUP = r"""
([cells, dark]) => {
  if (dark) document.documentElement.classList.add('dark');
  const s = {
    'sensor.kok': st('sensor.kok', 38412.5, 'Wh', 'Kokonais tänään'),
    'sensor.vilp': st('sensor.vilp', 14230.1, 'Wh', 'VILP tänään'),
    'sensor.pana': st('sensor.pana', 2.1, 'kWh', 'Makuuhuone energy today'),
    'sensor.ilp2': st('sensor.ilp2', 1510.4, 'Wh', 'ILP2 tänään'),
    'sensor.tesla': st('sensor.tesla', 11.62, 'kWh', 'Tesla tänään'),
  };
  const grid = document.getElementById('grid');
  for (const [id, w, h, title] of cells) {
    const cap = document.createElement('div');
    cap.className = 'slot';
    cap.innerHTML = `<div class="cap">${id} ${w}x${h || 'auto'}${title ? ' +title' : ''}</div>`;
    const cell = document.createElement('div');
    cell.id = 'cell-' + id;
    cell.style.cssText = `width:${w}px;${h ? `height:${h}px;` : ''}outline:1px dashed #e0457b;`;
    const card = document.createElement('energy-ring-card');
    card.id = id;
    const cfg = { type: 'custom:energy-ring-card', center_label: 'Tänään', total_entity: 'sensor.kok',
      entities: [{ entity: 'sensor.vilp', name: 'VILP' }, { entity: 'sensor.pana', name: 'ILP makuuhuone' },
                 { entity: 'sensor.ilp2', name: 'ILP 2' }, { entity: 'sensor.tesla', name: 'Tesla' }] };
    if (title) cfg.title = 'Sähkönkulutus tänään';
    card.setConfig(cfg);
    card.hass = makeHass({ states: s, dark });
    cell.appendChild(card);
    cap.appendChild(cell);
    grid.appendChild(cap);
  }
}
"""

MEASURE = r"""
(ids) => ids.map(id => {
  const c = document.getElementById(id), r = c.shadowRoot;
  const cell = c.parentElement, card = r.querySelector('ha-card');
  const ring = r.querySelector('.ring') || r.querySelector('svg');
  const svg = r.querySelector('svg');
  const cb = cell.getBoundingClientRect(), hb = card.getBoundingClientRect(), rb = ring.getBoundingClientRect();
  return { id, cell: [Math.round(cb.width), Math.round(cb.height)], card: [Math.round(hb.width), Math.round(hb.height)],
           overflow: Math.round(card.scrollHeight - card.clientHeight), ringBox: [Math.round(rb.width), Math.round(rb.height)],
           viewBox: svg.getAttribute('viewBox'), compact: !!c._compact, labels: c._m ? c._m.labeled.size : null,
           legend: r.querySelectorAll('.li').length,
           center: [...r.querySelectorAll('.center text')].map(t => t.textContent + '@' + getComputedStyle(t).fontSize) };
})
"""

with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1500, "height": 900}, device_scale_factor=2)
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.goto(URL)
    page.evaluate("document.fonts.ready")
    page.evaluate(SETUP, [CELLS, DARK])
    page.wait_for_timeout(1500)
    res = page.evaluate(MEASURE, [c[0] for c in CELLS])
    for r in res:
        print(json.dumps(r, ensure_ascii=False))
    page.screenshot(path=str(OUT / f"sizes-{'dark' if DARK else 'light'}.png"), full_page=True)
    # hover in the smallest cell
    box = page.locator("#c6x3n").bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.80, box["y"] + box["height"] * 0.35)
    page.wait_for_timeout(300)
    page.locator("#cell-c6x3n").screenshot(path=str(OUT / "size-hover.png"))
    print("hover:", page.evaluate("() => [...document.getElementById('c6x3n').shadowRoot.querySelectorAll('.center text')].map(t => t.textContent)"))
    print("errors:", errs)
    b.close()
