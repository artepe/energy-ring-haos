"""Behavioural tests: live updates, reconfigure, timers, errors, formats, keyboard."""
import json, pathlib
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
URL = (HERE / "index.html").as_uri()
results = []


def check(name, cond, info=""):
    results.append((name, bool(cond), info))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""))


BASE = r"""
() => {
  const W = (id, w, n) => st(id, w, 'W', n, { device_class: 'power' });
  window.mk = (v) => ({
    'sensor.tot': st('sensor.tot', v.tot, 'kW', 'Koko talo'),
    'sensor.vilp': W('sensor.vilp', v.vilp, 'VILP'),
    'sensor.tesla': W('sensor.tesla', v.tesla, 'Tesla'),
    'sensor.valo': W('sensor.valo', v.valo, 'Valaistus'),
  });
  window.cfgA = { type: 'custom:energy-ring-card', total_entity: 'sensor.tot',
    entities: [{ entity: 'sensor.vilp', name: 'Lämpöpumppu' }, 'sensor.tesla', 'sensor.valo'] };
  window.card = mount('L', cfgA, makeHass({ states: mk({ tot: 6, vilp: 2400, tesla: 3000, valo: 150 }) }), 420);
}
"""

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 900, "height": 900}, device_scale_factor=2, timezone_id="Europe/Helsinki")
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.goto(URL)
    page.evaluate("document.fonts.ready")
    page.evaluate(BASE)
    page.wait_for_timeout(1100)

    # 1. intro animation ran and segments reached targets
    dash = page.evaluate("() => [...card.shadowRoot.querySelectorAll('.seg')].map(s => getComputedStyle(s).strokeDasharray)")
    check("segments drawn with non-zero dash", all(not d.startswith("0px") and not d.startswith("0,") for d in dash), str(dash))

    # 2. live update: Tesla stops, lighting grows; segment removed, label appears
    page.evaluate("() => { card.hass = makeHass({ states: mk({ tot: 4.1, vilp: 2600, tesla: 0, valo: 900 }) }); }")
    page.wait_for_timeout(250)
    page.locator("#slot-L").screenshot(path=str(OUT / "L-mid-transition.png"))
    page.wait_for_timeout(900)
    page.locator("#slot-L").screenshot(path=str(OUT / "L-after-update.png"))
    m = page.evaluate("() => ({ segs: card._m.segs.map(s => s.key), labeled: [...card._m.labeled], legend: [...card.shadowRoot.querySelectorAll('.li')].map(l => l.textContent), center: card.shadowRoot.querySelector('.c-val').textContent, segEls: card.shadowRoot.querySelectorAll('.seg').length, lblEls: card.shadowRoot.querySelectorAll('.lbl').length })")
    check("tesla segment removed on 0 W", "e1" not in m["segs"], json.dumps(m, ensure_ascii=False))
    gone = page.evaluate("() => { const s = card.shadowRoot.querySelector('.seg[data-key=e1]'); const h = card.shadowRoot.querySelector('.hit[data-key=e1]'); return [getComputedStyle(s).strokeDasharray, h.style.display]; }")
    check("zeroed segment shrinks to 0 and is not focusable", gone[0].startswith("0px") and gone[1] == "none", str(gone))
    check("tesla listed in auto legend", any(l.startswith("Tesla") for l in m["legend"]))
    check("lighting label shown", "e2" in m["labeled"])
    check("center updated", m["center"].startswith("4,10"), m["center"])
    vis_lbls = page.evaluate("() => card.shadowRoot.querySelectorAll('.lbl:not(.off)').length")
    check("visible labels == labelled segments", vis_lbls == len(m["labeled"]), f"{vis_lbls} vs {m['labeled']}")
    page.evaluate("() => { card.hass = makeHass({ states: mk({ tot: 6, vilp: 2400, tesla: 3000, valo: 150 }) }); }")
    page.wait_for_timeout(1000)
    back = page.evaluate("() => ({ n: card.shadowRoot.querySelectorAll('.seg[data-key=e1]').length, dash: getComputedStyle(card.shadowRoot.querySelector('.seg[data-key=e1]')).strokeDasharray, hit: card.shadowRoot.querySelector('.hit[data-key=e1]').style.display, labeled: [...card._m.labeled] })")
    check("segment grows back without duplicates", back["n"] == 1 and not back["dash"].startswith("0px") and back["hit"] == "" and "e1" in back["labeled"], str(back))

    # 3. unrelated hass update does not re-render (signature check)
    page.evaluate("() => { window._rc = 0; const o = card._model.bind(card); card._model = () => { window._rc++; return o(); }; const h = makeHass({ states: { ...card.hass.states, 'sensor.other': st('sensor.other', 1, 'W', 'x') } }); card.hass = h; card.hass = { ...h }; }")
    check("unrelated state changes skip render", page.evaluate("() => window._rc") == 0)
    page.evaluate("() => { card.hass = makeHass({ states: mk({ tot: 4.2, vilp: 2600, tesla: 0, valo: 900 }) }); }")
    check("relevant change renders once", page.evaluate("() => window._rc") == 1)

    # 4. hover via keyboard focus + Enter opens more-info
    page.evaluate("() => { window.events = []; card.shadowRoot.querySelector('.hit[data-key=e0]').focus(); }")
    page.wait_for_timeout(50)
    top = page.evaluate("() => card.shadowRoot.querySelector('.c-top').textContent")
    check("keyboard focus shows readout", top == "Lämpöpumppu", top)
    page.keyboard.press("Enter")
    check("Enter opens more-info", page.evaluate("() => window.events") == ["sensor.vilp"])
    page.evaluate("() => card.shadowRoot.querySelector('.hit[data-key=e0]').blur()")
    check("blur restores total", page.evaluate("() => card.shadowRoot.querySelector('.c-top').textContent") == "NYT")

    # 5. dark mode toggle switches palette
    c1 = page.evaluate("() => card.shadowRoot.querySelector('.seg[data-key=e0]').style.stroke")
    page.evaluate("() => { const h = makeHass({ states: card.hass.states, dark: true }); card.hass = h; }")
    c2 = page.evaluate("() => card.shadowRoot.querySelector('.seg[data-key=e0]').style.stroke")
    check("dark palette applied", c1 != c2, f"{c1} -> {c2}")

    # 6. reconfigure: sort, colours, legend false, decimals, ha colour names
    page.evaluate("""() => card.setConfig({ ...cfgA, sort: true, legend: false, decimals: 1,
        entities: [{ entity: 'sensor.vilp', name: 'Lämpöpumppu', color: 'orange' }, { entity: 'sensor.tesla', color: '#123456' }, { entity: 'sensor.valo', color: [10, 200, 30] }] })""")
    page.wait_for_timeout(1000)
    r = page.evaluate("() => ({ order: card._m.segs.map(s => s.key), strokes: [...card.shadowRoot.querySelectorAll('.seg')].map(s => s.getAttribute('data-key') + '=' + s.style.stroke), legend: card.shadowRoot.querySelectorAll('.li').length, val: card._m.byKey.get('e0').valStr, segs: card.shadowRoot.querySelectorAll('.seg').length, hits: card.shadowRoot.querySelectorAll('.hit').length })")
    check("sort desc", r["order"][:2] == ["e0", "e2"], str(r["order"]))
    check("custom colours", "e0=var(--orange-color, #ff9800)" in r["strokes"] and "e2=rgb(10, 200, 30)" in r["strokes"], str(r["strokes"]))
    check("legend false", r["legend"] == 0)
    check("decimals forced", r["val"] == "2,6 kW", r["val"])
    check("no duplicate elements after reconfigure", r["segs"] == r["hits"] == len(r["order"]), str(r))

    # 7. number formats
    for nf, expect in [("comma_decimal", "4.2"), ("space_comma", "4,2"), ("none", "4,2"), ("decimal_comma", "4,2")]:
        page.evaluate(f"() => {{ const h = makeHass({{ states: card.hass.states }}); h.locale.number_format = '{nf}'; card.hass = h; }}")
        v = page.evaluate("() => card.shadowRoot.querySelector('.c-num').textContent")
        check(f"number_format {nf}", v == expect, v)

    # 8. errors in config
    for bad, label in [("{}", "no entities"), ("{ entities: [] }", "empty"), ("{ entities: [{ name: 'x' }] }", "missing entity"), ("{ entities: ['sensor.a'], period: 'decade' }", "bad period")]:
        msg = page.evaluate(f"() => {{ try {{ document.createElement('energy-ring-card').setConfig({bad}); return 'NO ERROR'; }} catch (e) {{ return e.message; }} }}")
        check(f"config error: {label}", msg != "NO ERROR", msg)

    # 9. stub config + card picker registration
    stub = page.evaluate("() => customElements.get('energy-ring-card').getStubConfig(makeHass({ states: mk({ tot: 4, vilp: 2600, tesla: 0, valo: 900 }) }))")
    check("stub config picks power sensors, largest first", stub["entities"] == ["sensor.tot", "sensor.vilp", "sensor.valo", "sensor.tesla"], json.dumps(stub))
    check("customCards registered", page.evaluate("() => window.customCards.some(c => c.type === 'energy-ring-card')"))

    # 10. long names & many labels: everything either labelled or in legend
    page.evaluate("""() => {
      const s = {}; const names = ['Ilma-vesilämpöpumppu ulkoyksikkö', 'Tesla Wall Connector Gen 3', 'Saunan kiuas', 'Astianpesukone', 'Lattialämmitys kylpyhuone', 'Ulkovalaistus'];
      [3100, 2800, 0, 800, 600, 45].forEach((v, i) => s['sensor.n' + i] = st('sensor.n' + i, v, 'W', names[i]));
      window.cardN = mount('N', { type: 'custom:energy-ring-card', entities: Object.keys(s) }, makeHass({ states: s }), 360, 'N long names');
    }""")
    page.wait_for_timeout(1100)
    n = page.evaluate("() => ({ labeled: [...cardN._m.labeled], legend: [...cardN.shadowRoot.querySelectorAll('.li')].map(l => l.getAttribute('data-key')), all: cardN._m.items.map(i => i.key), names: [...cardN.shadowRoot.querySelectorAll('.lbl:not(.off) .nm tspan')].map(t => t.textContent) })")
    covered = set(n["labeled"]) | set(n["legend"])
    check("every entity labelled or in legend", set(n["all"]) <= covered, json.dumps(n, ensure_ascii=False))
    page.locator("#slot-N").screenshot(path=str(OUT / "N-long-names.png"))

    # 11. compact mode on very narrow cards
    page.evaluate("""() => { window.cardC = mount('C', cfgA, makeHass({ states: mk({ tot: 6, vilp: 2400, tesla: 3000, valo: 150 }) }), 230, 'C compact'); }""")
    page.wait_for_timeout(1100)
    cm = page.evaluate("() => ({ labeled: [...cardC._m.labeled], legend: cardC.shadowRoot.querySelectorAll('.li').length, items: cardC._m.legendAll.length, compact: cardC._compact })")
    check("compact: no ring labels, legend lists all", cm["compact"] and not cm["labeled"] and cm["legend"] == cm["items"], str(cm))
    page.locator("#slot-C").screenshot(path=str(OUT / "C-compact.png"))
    page.evaluate("() => { document.getElementById('slot-C').style.width = '420px'; }")
    page.wait_for_timeout(300)
    cm2 = page.evaluate("() => ({ labeled: [...cardC._m.labeled], compact: cardC._compact })")
    check("compact mode turns off when widened", not cm2["compact"] and len(cm2["labeled"]) >= 3, str(cm2))
    check("grid options", page.evaluate("() => JSON.stringify(cardC.getGridOptions())") == '{"columns":12,"rows":"auto","min_columns":3,"min_rows":2}')
    check("no page errors", not errs, str(errs))
    ctx.close()

    # ---------- timers / stats errors with an installed fake clock ----------
    ctx = b.new_context(timezone_id="Europe/Helsinki")
    page = ctx.new_page()
    errs2 = []
    page.on("pageerror", lambda e: errs2.append(str(e)))
    page.clock.install(time="2026-10-25T10:37:20+02:00")
    page.goto(URL)
    page.evaluate(r"""() => {
      const kw = (t) => 1.5;
      const states = { 'sensor.a': st('sensor.a', 1, 'kWh', 'A'), 'sensor.b': st('sensor.b', 1, 'kWh', 'B'), 'sensor.p': st('sensor.p', 1, 'W', 'Power sensor') };
      window.defs = { 'sensor.a': { kw }, 'sensor.b': { kw } };
      window.cardT = mount('T', { type: 'custom:energy-ring-card', period: 'today', refresh_interval: 30, entities: ['sensor.a', 'sensor.b', 'sensor.p'] },
        makeHass({ states, callWS: makeStatsWS(defs) }), 380);
    }""")
    page.clock.run_for(2000)
    calls0 = page.evaluate("() => wsCalls.length")
    page.clock.run_for(30000)
    calls1 = page.evaluate("() => wsCalls.length")
    check("refresh timer refetches", calls1 > calls0, f"{calls0} -> {calls1}")
    leg = page.evaluate("() => [...cardT.shadowRoot.querySelectorAll('.li')].map(l => l.textContent)")
    msg = page.evaluate("() => cardT.shadowRoot.querySelector('.msg').textContent")
    check("entity without statistics flagged", any("ei tilastoja" in l for l in leg) and "sensor.p" in msg, f"{leg} | {msg}")
    # reconfigure must not leave a second interval running
    page.evaluate("() => cardT.setConfig({ type: 'custom:energy-ring-card', period: 'today', refresh_interval: 30, entities: ['sensor.a', 'sensor.b'] })")
    page.clock.run_for(2000)
    c_a = page.evaluate("() => wsCalls.filter(m => m.type.endsWith('during_period')).length")
    page.clock.run_for(30000)
    c_b = page.evaluate("() => wsCalls.filter(m => m.type.endsWith('during_period')).length")
    check("single interval after reconfigure", c_b - c_a <= 3, f"{c_b - c_a} calls in one interval")
    # disconnect stops the timer
    page.evaluate("() => cardT.remove()")
    c_c = page.evaluate("() => wsCalls.length")
    page.clock.run_for(65000)
    check("timer stops when removed", page.evaluate("() => wsCalls.length") == c_c)
    # failing WS shows message and keeps the frame
    page.evaluate(r"""() => {
      const states = { 'sensor.a': st('sensor.a', 1, 'kWh', 'A') };
      window.cardF = mount('F', { type: 'custom:energy-ring-card', period: 'week', entities: ['sensor.a'] },
        makeHass({ states, callWS: makeStatsWS(defs, { failWith: 'Recorder not ready' }) }), 380);
    }""")
    page.clock.run_for(1500)
    fmsg = page.evaluate("() => cardF.shadowRoot.querySelector('.msg').textContent + ' | ' + cardF.shadowRoot.querySelector('.c-sub').textContent")
    check("ws failure surfaced", "Recorder not ready" in fmsg and "epäonnistui" in fmsg, fmsg)
    # reconfigure while the first request chain is still in flight
    page.evaluate(r"""() => {
      const states = { 'sensor.a': st('sensor.a', 1, 'kWh', 'A'), 'sensor.b': st('sensor.b', 1, 'kWh', 'B') };
      window.cardR = mount('R', { type: 'custom:energy-ring-card', period: 'today', entities: ['sensor.a'] },
        makeHass({ states, callWS: makeStatsWS(defs) }), 380);
      cardR.setConfig({ type: 'custom:energy-ring-card', period: 'month', entities: ['sensor.a', 'sensor.b'] });
    }""")
    page.clock.run_for(1500)
    rr = page.evaluate("() => ({ has: !!cardR._stats, ids: cardR._stats ? Object.keys(cardR._stats.sums) : [], start: cardR._stats ? cardR._stats.start.toISOString() : null, sub: cardR.shadowRoot.querySelector('.c-sub').textContent })")
    check("reconfigure during fetch loads new config", rr["has"] and rr["ids"] == ["sensor.a", "sensor.b"] and rr["start"] == "2026-09-30T21:00:00.000Z", str(rr))
    check("no page errors (timers)", not errs2, str(errs2))
    ctx.close()
    b.close()

print("\nSUMMARY:", sum(1 for r in results if r[1]), "/", len(results), "passed")
