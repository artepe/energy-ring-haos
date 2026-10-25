import pathlib
from playwright.sync_api import sync_playwright
URL = (pathlib.Path(__file__).parent / "index.html").as_uri()
with sync_playwright() as p:
    b = p.chromium.launch(); page = b.new_page()
    page.goto(URL)
    page.evaluate("""() => { const s = { 'sensor.a': st('sensor.a', 3000, 'W', 'A'), 'sensor.b': st('sensor.b', 1000, 'W', 'B') };
      window.c = mount('I', { type: 'custom:energy-ring-card', entities: ['sensor.a', 'sensor.b'] }, makeHass({ states: s }), 400); }""")
    page.wait_for_timeout(120)
    mid = page.evaluate("() => parseFloat(getComputedStyle(c.shadowRoot.querySelector('.seg[data-key=e0]')).strokeDasharray)")
    page.wait_for_timeout(1200)
    end = page.evaluate("() => parseFloat(getComputedStyle(c.shadowRoot.querySelector('.seg[data-key=e0]')).strokeDasharray)")
    print("intro mid:", round(mid,1), "end:", round(end,1), "ANIMATES" if 0 < mid < end - 1 else "NO ANIMATION")
    # hass set AFTER attach (fresh path)
    page.evaluate("""() => { const el = document.createElement('energy-ring-card'); el.id='J'; el.setConfig({ type: 'custom:energy-ring-card', entities: ['sensor.a'] });
      document.getElementById('grid').appendChild(el); el.hass = makeHass({ states: { 'sensor.a': st('sensor.a', 3000, 'W', 'A') } }); window.j = el; }""")
    page.wait_for_timeout(120)
    mid = page.evaluate("() => parseFloat(getComputedStyle(j.shadowRoot.querySelector('.seg')).strokeDasharray)")
    page.wait_for_timeout(1200)
    end = page.evaluate("() => parseFloat(getComputedStyle(j.shadowRoot.querySelector('.seg')).strokeDasharray)")
    print("fresh mid:", round(mid,1), "end:", round(end,1), "ANIMATES" if 0 < mid < end - 1 else "NO ANIMATION")
    b.close()
