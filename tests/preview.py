import pathlib
from playwright.sync_api import sync_playwright
from PIL import Image
# Regenerates images/preview.png (English locale, light + dark).
HERE = pathlib.Path(__file__).parent; OUT = HERE / "out"; URL = (HERE / "index.html").as_uri()
OUT.mkdir(exist_ok=True)
LIVE = r"""() => {
  const W = (id, w, n) => st(id, w, 'W', n, { device_class: 'power' });
  const s = { 'sensor.house': st('sensor.house', 7.48, 'kW', 'House'), 'sensor.hp': W('sensor.hp', 2850, 'Heat pump'),
    'sensor.ev': W('sensor.ev', 3320, 'EV charger'), 'sensor.kitchen': W('sensor.kitchen', 410, 'Kitchen'),
    'sensor.lights': W('sensor.lights', 160, 'Lighting'), 'sensor.vent': W('sensor.vent', 70, 'Ventilation') };
  mount('P', { type: 'custom:energy-ring-card', title: 'Power now', total_entity: 'sensor.house',
    entities: ['sensor.hp', 'sensor.ev', 'sensor.kitchen', 'sensor.lights', 'sensor.vent'] },
    makeHass({ states: s, lang: 'en' }), 440);
}"""
STATS = r"""() => {
  document.documentElement.classList.add('dark');
  const kwf = { 'sensor.t': (t) => 2.6 + 0.9 * Math.sin(t / 36e5 / 3), 'sensor.v': (t) => 1.25 + 0.5 * Math.sin(t / 36e5 / 3),
    'sensor.e': (t) => ((Math.floor(t / 36e5) % 24) < 4 ? 3.6 : 0), 'sensor.s': (t) => ((Math.floor(t / 36e5) % 24) === 7 ? 5.5 : 0),
    'sensor.k': (t) => 0.3 };
  const defs = Object.fromEntries(Object.entries(kwf).map(([k, f]) => [k, { kw: f }]));
  const names = { 'sensor.t': 'House', 'sensor.v': 'Heat pump', 'sensor.e': 'EV charger', 'sensor.s': 'Sauna', 'sensor.k': 'Appliances' };
  const s = Object.fromEntries(Object.keys(kwf).map(k => [k, st(k, 1, 'kWh', names[k])]));
  mount('Q', { type: 'custom:energy-ring-card', title: 'Energy today', period: 'today', total_entity: 'sensor.t',
    entities: ['sensor.v', 'sensor.e', 'sensor.s', 'sensor.k'] }, makeHass({ states: s, dark: true, lang: 'en', callWS: makeStatsWS(defs) }), 440);
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
canvas.save(HERE.parent / "images" / "preview.png"); print(canvas.size)
