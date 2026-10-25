import pathlib, json
from playwright.sync_api import sync_playwright
HERE = pathlib.Path(__file__).parent; URL = (HERE / "index.html").as_uri()
(HERE / "out").mkdir(exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(); page = b.new_page(viewport={"width": 1300, "height": 600}, device_scale_factor=2)
    errs = []; page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(URL); page.evaluate("document.fonts.ready")
    page.evaluate("""() => {
      const s = { 'sensor.um_tot': st('sensor.um_tot', 23.4, 'kWh', 'Talo tänään'), 'sensor.um_vilp': st('sensor.um_vilp', 9.8, 'kWh', 'VILP tänään'),
                  'sensor.um_ev': st('sensor.um_ev', 7100, 'Wh', 'Tesla tänään'), 'sensor.cur': st('sensor.cur', 7.5, 'A', 'Virta L1'), 'sensor.cur2': st('sensor.cur2', 2.5, 'A', 'Virta L2') };
      mount('U1', { type: 'custom:energy-ring-card', total_entity: 'sensor.um_tot', entities: ['sensor.um_vilp', 'sensor.um_ev'] }, makeHass({ states: s }), 400, 'live kWh (utility_meter)');
      mount('U2', { type: 'custom:energy-ring-card', total_entity: 'sensor.um_tot', show_other: false, center_label: 'Päivä', total_label: 'Shelly 3EM', entities: ['sensor.um_vilp', 'sensor.um_ev'] }, makeHass({ states: s }), 400, 'show_other:false + labels');
      mount('U3', { type: 'custom:energy-ring-card', entities: ['sensor.cur', 'sensor.cur2'] }, makeHass({ states: s }), 400, 'unknown unit (A)');
    }""")
    page.wait_for_timeout(1300)
    out = page.evaluate("""() => ['U1','U2','U3'].map(id => { const c = document.getElementById(id), r = c.shadowRoot;
      return [id, r.querySelector('.c-top').textContent, r.querySelector('.c-val').textContent, r.querySelector('.c-sub').textContent, c._m.segs.map(s => s.name + '=' + s.valStr + '/' + s.pctStr)]; })""")
    for o in out: print(json.dumps(o, ensure_ascii=False))
    page.screenshot(path=str(HERE / "out" / "misc.png"), full_page=True)
    print("errors:", errs); b.close()
