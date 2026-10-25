"""Run the card in real WebKit (WebKitGTK MiniBrowser via WebKitWebDriver) — Safari's engine.

    sudo apt-get install webkit2gtk-driver xvfb && pip install selenium
    xvfb-run -a -s "-screen 0 3000x2600x24" python3 webkit_test.py
"""
import json, math, pathlib, subprocess, sys, time
from selenium import webdriver
from selenium.webdriver.webkitgtk.options import Options
from selenium.webdriver.webkitgtk.service import Service

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "out" / "webkit"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(HERE))
from visual import SETUP  # same scenarios as the Chromium visual test

PORT = 8765
results = []


def check(name, cond, info=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""))


def wait(d, js, timeout=8.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if d.execute_script("return !!(" + js + ")"):
            return True
        time.sleep(0.1)
    return False


HOOK = """
window.__errs = [];
addEventListener('error', e => __errs.push(String(e.message)));
addEventListener('unhandledrejection', e => __errs.push('rejection: ' + e.reason));
return { defined: !!customElements.get('energy-ring-card'), ua: navigator.userAgent };
"""

GEOM = r"""
const c = document.getElementById(arguments[0]);
const svg = c.shadowRoot.querySelector('svg');
const b = svg.getBoundingClientRect(), k = 360 / b.width;
const cx = b.left + b.width / 2, cy = b.top + b.height / 2;
return [...c._lblEls.entries()].filter(([key, el]) => !el.g.classList.contains('off')).map(([key, el]) => {
  const r = el.g.getBoundingClientRect();
  const dx = (r.left + r.width / 2 - cx) * k, dy = (r.top + r.height / 2 - cy) * k;
  const tl = [...el.g.querySelectorAll('text')].map(t => t.getComputedTextLength());
  return { key, expected: (((el.deg + (el.bottom ? 180 : 0)) % 360) + 360) % 360,
           actual: ((Math.atan2(dx, -dy) * 180 / Math.PI) + 360) % 360, dist: Math.hypot(dx, dy), textLen: tl };
});
"""


def run(d, dark):
    tag = "dark" if dark else "light"
    d.get(f"http://127.0.0.1:{PORT}/tests/index.html")
    wait(d, "document.fonts && document.fonts.status === 'loaded'")
    info = d.execute_script(HOOK)
    if not dark:
        print("UA:", info["ua"])
    check(f"[{tag}] custom element defined", info["defined"])
    d.execute_script("return (" + SETUP + ")(arguments[0])", dark)
    check(f"[{tag}] statistics loaded", wait(d, "document.getElementById('B')._stats"))
    time.sleep(1.6)
    for cid in "ABDEFGH":
        d.find_element("id", f"slot-{cid}").screenshot(str(OUT / f"{cid}-{tag}.png"))

    diag = d.execute_script("""return [...document.querySelectorAll('energy-ring-card')].map(c => ({
        id: c.id, labeled: [...c._m.labeled], segs: c._m.segs.length,
        center: c.shadowRoot.querySelector('.c-top').textContent + ' | ' + c.shadowRoot.querySelector('.c-val').textContent + ' | ' + c.shadowRoot.querySelector('.c-sub').textContent }))""")
    for c in diag:
        print(f"   {c['id']}: {c['center']}  labels={c['labeled']}")
    check(f"[{tag}] every card rendered", all(c["segs"] > 0 or c["id"] == "G" for c in diag))

    # Curved labels: rotated into place around the ring centre, text laid out on the path.
    for cid in ("A", "E"):
        g = d.execute_script(GEOM, cid)
        bad = [x for x in g if min(abs(x["actual"] - x["expected"]), 360 - abs(x["actual"] - x["expected"])) > 6 or not (140 < x["dist"] < 175) or min(x["textLen"]) <= 0]
        check(f"[{tag}] {cid}: {len(g)} labels on the ring at the right angle", g and not bad,
              json.dumps(bad or [(x['key'], round(x['expected']), round(x['actual']), round(x['dist'])) for x in g]))

    # Hover / click / keyboard via the card's own event delegation.
    r = d.execute_script("""
      const c = document.getElementById('A'), root = c.shadowRoot, hit = root.querySelector('.hit[data-key=e0]');
      window.events = [];
      hit.dispatchEvent(new PointerEvent('pointermove', { bubbles: true, composed: true, pointerType: 'mouse' }));
      const hover = root.querySelector('.c-top').textContent + ' | ' + root.querySelector('.c-sub').textContent;
      const dim = root.querySelector('svg').classList.contains('dim');
      hit.dispatchEvent(new MouseEvent('click', { bubbles: true, composed: true }));
      root.querySelector('svg').dispatchEvent(new PointerEvent('pointerleave', { pointerType: 'mouse' }));
      const after = root.querySelector('.c-top').textContent;
      hit.focus();
      const focus = root.querySelector('.c-top').textContent;
      hit.blur();
      return { hover, dim, after, focus, events: window.events };""")
    check(f"[{tag}] hover shows item in centre", r["hover"].startswith("Lämpöpumppu |") and r["dim"], r["hover"])
    check(f"[{tag}] click opens more-info", r["events"] == ["sensor.vilp"], str(r["events"]))
    check(f"[{tag}] leave restores total, focus works", r["after"] == "NYT" and r["focus"] == "Lämpöpumppu", f"{r['after']} / {r['focus']}")

    # Draw-in animation + ResizeObserver compact mode.
    d.execute_script("""const s = { 'sensor.a': st('sensor.a', 3000, 'W', 'A'), 'sensor.b': st('sensor.b', 1000, 'W', 'B') };
      window.cI = mount('I', { type: 'custom:energy-ring-card', entities: ['sensor.a', 'sensor.b'] }, makeHass({ states: s, dark: %s }), 230, 'compact');""" % ("true" if dark else "false"))
    time.sleep(0.15)
    mid = d.execute_script("return parseFloat(getComputedStyle(cI.shadowRoot.querySelector('.seg')).strokeDasharray)")
    time.sleep(1.3)
    end = d.execute_script("return parseFloat(getComputedStyle(cI.shadowRoot.querySelector('.seg')).strokeDasharray)")
    check(f"[{tag}] draw-in animation", 0 < mid < end - 1, f"{mid:.0f} -> {end:.0f}")
    cm = d.execute_script("return { compact: cI._compact, labeled: cI._m.labeled.size, legend: cI.shadowRoot.querySelectorAll('.li').length }")
    check(f"[{tag}] narrow card switches to legend", cm["compact"] and cm["labeled"] == 0 and cm["legend"] == 2, str(cm))
    d.find_element("id", "slot-I").screenshot(str(OUT / f"I-compact-{tag}.png"))

    errs = d.execute_script("return window.__errs")
    check(f"[{tag}] no JavaScript errors", not errs, str(errs))


srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
                       cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(0.8)
opts = Options()
opts.binary_location = "/usr/lib/x86_64-linux-gnu/webkit2gtk-4.1/MiniBrowser"
opts.add_argument("--automation")
d = webdriver.WebKitGTK(options=opts, service=Service(executable_path="/usr/bin/WebKitWebDriver"))
try:
    d.set_window_size(1450, 1400)
    run(d, False)
    run(d, True)
finally:
    d.quit()
    srv.terminate()
print(f"\nWEBKIT SUMMARY: {sum(results)} / {len(results)} passed")
