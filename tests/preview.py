import pathlib
from playwright.sync_api import sync_playwright
from PIL import Image
HERE = pathlib.Path(__file__).parent; OUT = HERE / "out"; URL = (HERE / "index.html").as_uri()
LIVE = r"""() => {
  const W = (id, w, n) => st(id, w, 'W', n, { device_class: 'power' });
  const s = { 'sensor.koko': st('sensor.koko', 7.48, 'kW', 'Koko talo'), 'sensor.vilp': W('sensor.vilp', 2850, 'VILP'),
    'sensor.tesla': W('sensor.tesla', 3320, 'Tesla'), 'sensor.keittio': W('sensor.keittio', 410, 'Keittiö'),
    'sensor.valot': W('sensor.valot', 160, 'Valaistus'), 'sensor.iv': W('sensor.iv', 70, 'IV-kone') };
  mount('P', { type: 'custom:energy-ring-card', title: 'Sähkö nyt', total_entity: 'sensor.koko',
    entities: [{ entity: 'sensor.vilp', name: 'Lämpöpumppu' }, { entity: 'sensor.tesla', name: 'Tesla' }, 'sensor.keittio', 'sensor.valot', 'sensor.iv'] },
    makeHass({ states: s }), 440);
}"""
STATS = r"""() => {
  document.documentElement.classList.add('dark');
  const kwf = { 'sensor.t': (t) => 2.6 + 0.9 * Math.sin(t / 36e5 / 3), 'sensor.v': (t) => 1.25 + 0.5 * Math.sin(t / 36e5 / 3),
    'sensor.e': (t) => ((Math.floor(t / 36e5) % 24) < 4 ? 3.6 : 0), 'sensor.s': (t) => ((Math.floor(t / 36e5) % 24) === 7 ? 5.5 : 0),
    'sensor.k': (t) => 0.3 };
  const defs = Object.fromEntries(Object.entries(kwf).map(([k, f]) => [k, { kw: f }]));
  const names = { 'sensor.t': 'Koko talo', 'sensor.v': 'Lämpöpumppu', 'sensor.e': 'Tesla', 'sensor.s': 'Sauna', 'sensor.k': 'Kodinkoneet' };
  const s = Object.fromEntries(Object.keys(kwf).map(k => [k, st(k, 1, 'kWh', names[k])]));
  mount('Q', { type: 'custom:energy-ring-card', title: 'Kulutus tänään', period: 'today', total_entity: 'sensor.t',
    entities: ['sensor.v', 'sensor.e', 'sensor.s', 'sensor.k'] }, makeHass({ states: s, dark: true, callWS: makeStatsWS(defs) }), 440);
}"""
shots = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, js, cid in [("live", LIVE, "P"), ("stats", STATS, "Q")]:
        ctx = b.new_context(viewport={"width": 520, "height": 700}, device_scale_factor=2, timezone_id="Europe/Helsinki")
        page = ctx.new_page(); page.clock.set_fixed_time("2026-10-25T10:37:20+02:00"); page.goto(URL)
        page.evaluate("document.fonts.ready"); page.evaluate(js); page.wait_for_timeout(1600)
        page.evaluate("document.body.style.background = 'transparent'")
        path = OUT / f"preview-{name}.png"; page.locator(f"#{cid}").screenshot(path=str(path), omit_background=True); shots.append(path); ctx.close()
    b.close()
ims = [Image.open(s).convert("RGBA") for s in shots]
pad = 40; w = sum(i.width for i in ims) + pad * 3; h = max(i.height for i in ims) + pad * 2
canvas = Image.new("RGB", (w, h), (236, 236, 233)); x = pad
for i in ims:
    canvas.paste(i, (x, pad), i); x += i.width + pad
OUT.mkdir(exist_ok=True); canvas.save(HERE.parent / "images" / "preview.png"); print(canvas.size)
