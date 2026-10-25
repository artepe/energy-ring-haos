/*!
 * energy-ring-card v1.0.0 — Home Assistant Lovelace custom card
 * https://github.com/artepe/energy-ring-haos · MIT
 * Kokonaiskulutus renkaan keskellä, kohteiden kulutukset renkaan sektoreina,
 * nimet ja arvot kaartuvat renkaan linjaa pitkin.
 *
 * Asennus: kopioi tiedosto /config/www/energy-ring-card.js ja lisää resurssi
 *   URL: /local/energy-ring-card.js?v=1.0.0   tyyppi: JavaScript-moduuli
 *
 * Konfiguraatio (YAML):
 *   type: custom:energy-ring-card
 *   title: Sähkö                  # valinnainen otsikko
 *   period: live                  # live = entiteettien tila (W/kW tai kWh)
 *                                 # today | yesterday | week | month | year = HA:n
 *                                 # pitkäaikaistilastot (energia-anturit, total_increasing)
 *   total_entity: sensor.koko_talo   # valinnainen, keskelle + "Muu"-sektori erotukselle
 *   entities:                     # 9.+ kohde lasketaan Muu-sektoriin, ellei sille anna omaa väriä
 *     - entity: sensor.vilp_teho
 *       name: Lämpöpumppu
 *       color: orange               # valinnainen (CSS-väri tai HA-värinimi)
 *     - sensor.sauna_teho           # lyhyt muoto
 *   show_other: true              # Muu = total_entity − kohteiden summa
 *   other_name: Muu
 *   sort: false                   # true = suurin ensin
 *   legend: auto                  # auto = vain ne, joiden teksti ei mahdu kehälle | true | false
 *   decimals:                     # valinnainen, pakota desimaalit
 *   center_label: / total_label:  # valinnaiset keskitekstit
 *   refresh_interval: 60          # s, tilastotilassa
 *   max_width: 440                # px, renkaan maksimileveys
 */
(() => {
  'use strict';

  const VERSION = '1.0.0';
  const TAG = 'energy-ring-card';
  if (customElements.get(TAG)) return;

  /* ---------- geometry, SVG user units (viewBox 0 0 360 360) ---------- */
  const CX = 180, CY = 180;
  const R = 122;                 // ring centre-line radius
  const SW = 22;                 // ring thickness
  const GAP = 2;                 // surface gap between segments
  const R_IN = R - SW / 2;       // inner edge of the ring
  const FS_NAME = 12.5, FS_VAL = 15;
  const R_L1 = R + SW / 2 + 14;  // label line next to the ring (glyph centre)
  const R_L2 = R_L1 + 17;        // outer label line (glyph centre)
  const BL = 0.36;               // baseline → glyph centre, in em
  const DOT_R = 3.4, DOT_GAP = 4, DOT_SPACE = DOT_R * 2 + DOT_GAP;
  const TAU = Math.PI * 2;
  const CIRC = TAU * R;
  const SPAN = (178 * Math.PI) / 180;           // label guide paths: ±89°
  const LABEL_GAP = 10 / R_L1;                  // min angle between labels
  const Y_TOP = CY - 31, Y_VAL = CY + 17, Y_SUB = CY + 41;
  const NB = ' ';
  const COMPACT_W = 250;         // px: below this the ring drops its labels (legend shows all)

  // Label guide lines. Top half: path runs clockwise, glyphs grow outwards.
  // Bottom half: path runs counter-clockwise (text stays upright), glyphs
  // grow inwards — so the baseline is offset in opposite directions.
  const LINE = {
    tn: { rc: R_L2, rb: R_L2 - BL * FS_NAME, bottom: false },
    tv: { rc: R_L1, rb: R_L1 - BL * FS_VAL, bottom: false },
    bn: { rc: R_L1, rb: R_L1 + BL * FS_NAME, bottom: true },
    bv: { rc: R_L2, rb: R_L2 + BL * FS_VAL, bottom: true },
  };
  for (const l of Object.values(LINE)) l.len = l.rb * SPAN;
  const RB_NAME = Math.min(LINE.tn.rb, LINE.bn.rb);
  const RB_VAL = Math.min(LINE.tv.rb, LINE.bv.rb);

  const PERIODS = ['today', 'yesterday', 'week', 'month', 'year'];

  // Categorical palette, fixed order (validated for adjacent + ring wrap-around
  // pairs, colour-vision deficiency safe) — light and dark steps.
  const PALETTE = {
    light: ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948'],
    dark: ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'],
  };
  const OTHER_COLOR = { light: '#a3a29b', dark: '#6d6c66' };
  const HA_COLOR = {
    red: '#f44336', pink: '#e91e63', purple: '#926bc7', 'deep-purple': '#6e41ab',
    indigo: '#3f51b5', blue: '#2196f3', 'light-blue': '#03a9f4', cyan: '#00bcd4',
    teal: '#009688', green: '#4caf50', 'light-green': '#8bc34a', lime: '#cddc39',
    yellow: '#ffeb3b', amber: '#ffc107', orange: '#ff9800', 'deep-orange': '#ff6f22',
    brown: '#795548', 'light-grey': '#bdbdbd', grey: '#9e9e9e', 'dark-grey': '#606060',
    'blue-grey': '#607d8b', black: '#000000', white: '#ffffff',
  };
  const UNITS = {
    W: ['power', 1], kW: ['power', 1e3], MW: ['power', 1e6],
    Wh: ['energy', 1], kWh: ['energy', 1e3], MWh: ['energy', 1e6], GWh: ['energy', 1e9],
  };
  const STR = {
    fi: {
      now: 'Nyt', today: 'Tänään', yesterday: 'Eilen', week: 'Tämä viikko', month: 'Tämä kuukausi',
      year: 'Tämä vuosi', other: 'Muu', totalPower: 'Kokonaisteho', totalEnergy: 'Kokonaiskulutus',
      ofPower: 'kokonaistehosta', ofEnergy: 'kokonaiskulutuksesta', total: 'Yhteensä', ofTotal: 'kokonaismäärästä',
      unavailable: 'ei saatavilla',
      nostats: 'ei tilastoja', loading: 'Ladataan…', error: 'Tilastojen haku epäonnistui',
    },
    sv: {
      now: 'Nu', today: 'Idag', yesterday: 'Igår', week: 'Denna vecka', month: 'Denna månad',
      year: 'Detta år', other: 'Övrigt', totalPower: 'Total effekt', totalEnergy: 'Total förbrukning',
      ofPower: 'av total effekt', ofEnergy: 'av total förbrukning', total: 'Totalt', ofTotal: 'av totalen',
      unavailable: 'inte tillgänglig',
      nostats: 'ingen statistik', loading: 'Laddar…', error: 'Kunde inte hämta statistik',
    },
    en: {
      now: 'Now', today: 'Today', yesterday: 'Yesterday', week: 'This week', month: 'This month',
      year: 'This year', other: 'Other', totalPower: 'Total power', totalEnergy: 'Total consumption',
      ofPower: 'of total power', ofEnergy: 'of total consumption', total: 'Total', ofTotal: 'of total',
      unavailable: 'unavailable',
      nostats: 'no statistics', loading: 'Loading…', error: 'Failed to load statistics',
    },
  };
  const SVGNS = 'http://www.w3.org/2000/svg';
  const XLINK = 'http://www.w3.org/1999/xlink';

  /* ---------- helpers ---------- */
  const r2 = (n) => Math.round(n * 100) / 100;
  const pt = (a, r) => [CX + r * Math.sin(a), CY - r * Math.cos(a)]; // 0 = top, clockwise
  function arcPath(r, a0, a1) {
    const [x0, y0] = pt(a0, r), [x1, y1] = pt(a1, r);
    const large = Math.abs(a1 - a0) > Math.PI ? 1 : 0;
    return `M${r2(x0)} ${r2(y0)}A${r2(r)} ${r2(r)} 0 ${large} ${a1 > a0 ? 1 : 0} ${r2(x1)} ${r2(y1)}`;
  }
  function svgEl(tag, attrs) {
    const el = document.createElementNS(SVGNS, tag);
    if (attrs) for (const k in attrs) el.setAttribute(k, attrs[k]);
    return el;
  }
  function setHref(el, id) {
    el.setAttribute('href', `#${id}`);
    el.setAttributeNS(XLINK, 'xlink:href', `#${id}`);
  }
  const norm180 = (d) => ((((d + 180) % 360) + 360) % 360) - 180;

  let canvasCtx;
  function textW(str, size, weight, fam) {
    if (!canvasCtx) canvasCtx = document.createElement('canvas').getContext('2d');
    canvasCtx.font = `${weight} ${size}px ${fam}`;
    return canvasCtx.measureText(str).width;
  }
  function fitText(str, maxW, size, weight, fam, ls = 0) {
    const w = (s) => textW(s, size, weight, fam) + ls * [...s].length;
    if (w(str) <= maxW) return str;
    const ch = [...str];
    let lo = 1, hi = ch.length - 1, best = '…';
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      const s = ch.slice(0, mid).join('').trimEnd() + '…';
      if (w(s) <= maxW) { best = s; lo = mid + 1; } else hi = mid - 1;
    }
    return best;
  }
  function truncations(name) {
    const out = [name];
    const ch = [...name];
    if (ch.length > 6) {
      for (const f of [0.72, 0.52, 0.36]) {
        const n = Math.max(4, Math.round(ch.length * f));
        if (n < ch.length - 1) {
          const s = ch.slice(0, n).join('').trimEnd() + '…';
          if (!out.includes(s)) out.push(s);
        }
      }
    }
    return out;
  }
  function resolveColor(c) {
    if (c == null || c === '') return null;
    if (Array.isArray(c) && c.length >= 3) return `rgb(${c.slice(0, 3).join(',')})`;
    const s = String(c).trim();
    if (s === 'primary' || s === 'accent' || s === 'disabled') return `var(--${s}-color)`;
    if (HA_COLOR[s]) return `var(--${s}-color, ${HA_COLOR[s]})`;
    return s;
  }
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  function toMs(v) {
    if (typeof v === 'number') return v < 1e11 ? v * 1000 : v;
    const t = Date.parse(v);
    return Number.isFinite(t) ? t : NaN;
  }
  function periodRange(period, now, firstDay) {
    const d0 = startOfDay(now);
    switch (period) {
      case 'yesterday': {
        const s = new Date(d0);
        s.setDate(s.getDate() - 1);
        return { start: s, end: d0 };
      }
      case 'week': {
        const s = new Date(d0);
        s.setDate(s.getDate() - ((s.getDay() - firstDay + 7) % 7));
        return { start: s, end: null };
      }
      case 'month': return { start: new Date(now.getFullYear(), now.getMonth(), 1), end: null };
      case 'year': return { start: new Date(now.getFullYear(), 0, 1), end: null };
      default: return { start: d0, end: null };
    }
  }

  // 1-D circular label layout. Labels keep their order, are pushed apart
  // until they don't overlap, and must keep overlapping their own sector.
  function placeLabels(ls) {
    const n = ls.length;
    if (!n) return { ok: true, conflicts: [] };
    const need = ls.reduce((a, l) => a + l.w, 0) + (n > 1 ? n * LABEL_GAP : 0);
    if (need > TAU) return { ok: false, conflicts: [] };
    for (const l of ls) {
      const k = 0.35 * Math.min(l.w, l.b - l.a);
      l.lo = l.a - l.w / 2 + k;
      l.hi = l.b + l.w / 2 - k;
      if (l.lo > l.hi) l.lo = l.hi = l.mid;
      l.c = l.mid;
    }
    if (n === 1) return { ok: true, conflicts: [] };
    const dist = (i) => ls[(i + 1) % n].c - ls[i].c + (i === n - 1 ? TAU : 0);
    for (let it = 0; it < 600; it++) {
      let moved = false;
      for (let i = 0; i < n; i++) {
        const a = ls[i], b = ls[(i + 1) % n];
        const want = (a.w + b.w) / 2 + LABEL_GAP;
        const d = dist(i);
        if (d < want - 1e-7) {
          const p = (want - d) / 2;
          a.c -= p;
          b.c += p;
          moved = true;
        }
      }
      for (const l of ls) l.c = Math.min(l.hi, Math.max(l.lo, l.c));
      if (!moved) break;
    }
    const conflicts = new Set();
    for (let i = 0; i < n; i++) {
      const a = ls[i], b = ls[(i + 1) % n];
      if (dist(i) < (a.w + b.w) / 2 + LABEL_GAP - 1e-4) { conflicts.add(a); conflicts.add(b); }
    }
    return { ok: conflicts.size === 0, conflicts: [...conflicts] };
  }

  const CSS = `
    :host { display: block; --erc-ease: cubic-bezier(.22,.8,.24,1); }
    ha-card { height: 100%; box-sizing: border-box; overflow: hidden; }
    .wrap { padding: 8px 8px 12px; }
    .wrap.has-header { padding-top: 0; }
    svg { display: block; width: 100%; height: auto; margin: 0 auto; overflow: visible;
      font-family: inherit; -webkit-tap-highlight-color: transparent; user-select: none; -webkit-user-select: none; }
    .track { fill: none; stroke: var(--divider-color, rgba(127,127,127,.2)); stroke-width: ${SW}px; }
    .seg { fill: none; stroke-width: ${SW}px;
      transition: stroke-dasharray .9s var(--erc-ease), stroke-dashoffset .9s var(--erc-ease), stroke-width .18s ease, opacity .2s ease; }
    .seg.on { stroke-width: ${SW + 5}px; }
    .hit, .lhit { fill: none; stroke: transparent; pointer-events: stroke; cursor: pointer; outline: none; }
    .hit { stroke-width: ${SW + 20}px; }
    .lhit { stroke-width: 34px; }
    .lbl { transform-origin: ${CX}px ${CY}px; transition: transform .9s var(--erc-ease), opacity .25s ease; }
    .lbl.off { opacity: 0; pointer-events: none; }
    .ln { text-anchor: middle; pointer-events: none; }
    .nm { font-size: ${FS_NAME}px; font-weight: 500; fill: var(--secondary-text-color, #6f6f6f); }
    .vl { font-size: ${FS_VAL}px; font-weight: 600; fill: var(--primary-text-color, #1f1f1f); }
    .pc { font-weight: 400; fill: var(--secondary-text-color, #6f6f6f); }
    svg.dim .seg:not(.on), svg.dim .lbl:not(.on):not(.off) { opacity: .25; }
    .loading .segs, .loading .lbls { opacity: .45; }
    .c-top { font-size: 11.5px; font-weight: 500; letter-spacing: .1em; text-anchor: middle; fill: var(--secondary-text-color, #6f6f6f); }
    .c-top.named { font-size: 13.5px; letter-spacing: 0; fill: var(--primary-text-color, #1f1f1f); }
    .c-val { text-anchor: middle; }
    .c-num { font-size: 48px; font-weight: 400; fill: var(--primary-text-color, #1f1f1f); }
    .c-unit { font-size: 19px; font-weight: 400; fill: var(--secondary-text-color, #6f6f6f); }
    .c-sub { font-size: 12.5px; text-anchor: middle; fill: var(--secondary-text-color, #6f6f6f); }
    .c-hit { fill: transparent; }
    .c-hit.link { cursor: pointer; }
    .legend { display: flex; flex-wrap: wrap; justify-content: center; gap: 4px 14px; margin-top: 8px;
      font-size: 13px; line-height: 20px; }
    .legend:empty { display: none; }
    .li { display: inline-flex; align-items: center; gap: 6px; color: var(--secondary-text-color, #6f6f6f);
      transition: opacity .2s ease; outline: none; }
    .li[role=button] { cursor: pointer; }
    .li .sw { width: 10px; height: 10px; border-radius: 3px; flex: none; }
    .li .v { color: var(--primary-text-color, #1f1f1f); font-weight: 500; }
    .li.na .v { color: var(--secondary-text-color, #6f6f6f); font-weight: 400; font-style: italic; }
    .legend.dim .li:not(.on) { opacity: .45; }
    .msg { margin-top: 6px; text-align: center; font-size: 12px; color: var(--error-color, #db4437); }
    .msg:empty { display: none; }
    @media (prefers-reduced-motion: reduce) { .seg, .lbl, .li { transition: none; } }
  `;

  class EnergyRingCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this._uid = 'erc' + Math.random().toString(36).slice(2, 8);
      this._nf = new Map();
      this._segEls = new Map();
      this._lblEls = new Map();
      this._hover = null;
      this._sig = null;
      this._stats = null;
      this._statsVer = 0;
      this._statsErr = null;
      this._meta = null;
      this._timer = null;
      this._warned = new Set();
      this._introDone = false;
      this._compact = false;
      this._onVis = () => { if (!document.hidden) this._maybeRefetch(); };
      this._ro = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver((entries) => {
        const w = entries[entries.length - 1].contentRect.width;
        const compact = w > 0 && w < COMPACT_W;
        if (compact !== this._compact) {
          this._compact = compact;
          this._render(true);
        }
      });
    }

    static getStubConfig(hass) {
      const watts = (s) => {
        const u = UNITS[s.attributes?.unit_of_measurement];
        return u && u[0] === 'power' ? Number(s.state) * u[1] : NaN;
      };
      const ids = Object.values(hass?.states || {})
        .filter((s) => s.entity_id.startsWith('sensor.') && Number.isFinite(watts(s)))
        .sort((a, b) => watts(b) - watts(a))
        .slice(0, 5)
        .map((s) => s.entity_id);
      return { entities: ids.length ? ids : ['sensor.power'] };
    }

    setConfig(config) {
      if (!config || typeof config !== 'object') throw new Error('energy-ring-card: virheellinen konfiguraatio');
      if (!Array.isArray(config.entities) || !config.entities.length) {
        throw new Error('energy-ring-card: lisää vähintään yksi entiteetti (entities:)');
      }
      const entities = config.entities.map((e, i) => {
        const o = typeof e === 'string' ? { entity: e } : { ...(e || {}) };
        if (typeof o.entity !== 'string' || !o.entity.includes('.')) {
          throw new Error(`energy-ring-card: entities[${i}].entity puuttuu tai on virheellinen`);
        }
        return o;
      });
      const period = config.period && config.period !== 'live' ? String(config.period) : null;
      if (period && !PERIODS.includes(period)) {
        throw new Error(`energy-ring-card: period: ${['live', ...PERIODS].join(' | ')}`);
      }
      if (config.total_entity != null && (typeof config.total_entity !== 'string' || !config.total_entity.includes('.'))) {
        throw new Error('energy-ring-card: total_entity on virheellinen');
      }
      let legend = config.legend === undefined ? 'auto' : config.legend;
      if (legend === 'all' || legend === 'on') legend = true;
      if (legend === 'none' || legend === 'off') legend = false;
      this._config = {
        ...config,
        entities,
        period,
        legend,
        show_other: config.show_other !== false,
        sort: config.sort === true,
        refresh_interval: Math.max(15, Number(config.refresh_interval) || 60),
      };
      this._stats = null;
      this._statsErr = null;
      this._meta = null;
      this._sig = null;
      this._hover = null;
      this._stopTimer();
      this._buildDom();
      if (this.isConnected) this._startTimer();
      if (this._hass) {
        if (period) this._fetchStats();
        this._render(true);
      }
    }

    set hass(hass) {
      const first = !this._hass;
      this._hass = hass;
      if (!this._config) return;
      if (this._config.period && first) this._fetchStats();
      this._render();
    }

    get hass() {
      return this._hass;
    }

    connectedCallback() {
      document.addEventListener('visibilitychange', this._onVis);
      if (this._ro && this._svg) this._ro.observe(this._svg);
      this._startTimer();
      if (this._config && this._hass) {
        // Cards usually get config + hass before they are attached: play the
        // draw-in animation now that the ring is actually on screen.
        if (!this._introDone) this._intro();
        this._maybeRefetch();
        this._render(true);
      }
      if (!this._fontsHooked && document.fonts && document.fonts.ready) {
        this._fontsHooked = true;
        document.fonts.ready.then(() => this._render(true));
      }
    }

    disconnectedCallback() {
      document.removeEventListener('visibilitychange', this._onVis);
      if (this._ro) this._ro.disconnect();
      this._stopTimer();
    }

    getCardSize() {
      const h = this.offsetHeight;
      if (h) return Math.max(4, Math.ceil(h / 50));
      return 8 + (this._config && this._config.title ? 1 : 0);
    }

    getGridOptions() {
      return { columns: 12, rows: 'auto', min_columns: 6 };
    }

    /* ---------- DOM ---------- */
    _buildDom() {
      const u = this._uid;
      const cfg = this._config;
      const maxW = Number(cfg.max_width) > 0 ? `${Number(cfg.max_width)}px` : '440px';
      this._segEls.clear();
      this._lblEls.clear();
      this._introDone = false;
      const paths = Object.entries(LINE).map(([k, l]) => {
        const d = l.bottom ? arcPath(l.rb, Math.PI + SPAN / 2, Math.PI - SPAN / 2) : arcPath(l.rb, -SPAN / 2, SPAN / 2);
        return `<path id="${u}-${k}" d="${d}" fill="none"/>`;
      }).join('');
      this.shadowRoot.innerHTML = `
        <style>${CSS}</style>
        <ha-card>
          <div class="wrap">
            <svg viewBox="0 0 360 360" role="img" style="max-width:${maxW}">
              <defs>${paths}</defs>
              <circle class="track" cx="${CX}" cy="${CY}" r="${R}"/>
              <g class="segs" transform="rotate(-90 ${CX} ${CY})"></g>
              <g class="hits" transform="rotate(-90 ${CX} ${CY})"></g>
              <g class="lbls"></g>
              <g class="center">
                <circle class="c-dot" r="${DOT_R}" style="display:none"/>
                <text class="c-top" x="${CX}" y="${Y_TOP}"></text>
                <text class="c-val" x="${CX}" y="${Y_VAL}"><tspan class="c-num"></tspan><tspan class="c-unit"></tspan></text>
                <text class="c-sub" x="${CX}" y="${Y_SUB}"></text>
                <circle class="c-hit" cx="${CX}" cy="${CY}" r="${R_IN - 10}"/>
              </g>
            </svg>
            <div class="legend"></div>
            <div class="msg"></div>
          </div>
        </ha-card>`;
      const $ = (s) => this.shadowRoot.querySelector(s);
      this._card = $('ha-card');
      if (cfg.title) {
        this._card.header = cfg.title;
        this._card.setAttribute('header', cfg.title);
        $('.wrap').classList.add('has-header');
      }
      if (this._ro) this._ro.disconnect();
      this._svg = $('svg');
      if (this._ro && this.isConnected) this._ro.observe(this._svg);
      this._segG = $('.segs');
      this._hitG = $('.hits');
      this._lblG = $('.lbls');
      this._cDot = $('.c-dot');
      this._cTop = $('.c-top');
      this._cNum = $('.c-num');
      this._cUnit = $('.c-unit');
      this._cSub = $('.c-sub');
      this._cHit = $('.c-hit');
      this._legend = $('.legend');
      this._msg = $('.msg');

      const keyOf = (e) => {
        const el = e.target && e.target.closest ? e.target.closest('[data-key]') : null;
        return el ? el.getAttribute('data-key') : null;
      };
      for (const root of [this._svg, this._legend]) {
        root.addEventListener('pointermove', (e) => { if (e.pointerType !== 'touch') this._setHover(keyOf(e)); });
        root.addEventListener('pointerleave', () => this._setHover(null));
        root.addEventListener('focusin', (e) => this._setHover(keyOf(e)));
        root.addEventListener('focusout', () => this._setHover(null));
        root.addEventListener('click', (e) => {
          const k = keyOf(e);
          if (k) this._openKey(k);
          else if (e.target === this._cHit) this._moreInfo(this._config.total_entity);
        });
        root.addEventListener('keydown', (e) => {
          if (e.key !== 'Enter' && e.key !== ' ') return;
          const k = keyOf(e);
          if (k) { e.preventDefault(); this._openKey(k); }
        });
      }
      this._cHit.classList.toggle('link', !!cfg.total_entity);
    }

    /* ---------- statistics ---------- */
    _startTimer() {
      if (this._timer || !this._config || !this._config.period) return;
      this._timer = setInterval(() => this._fetchStats(), this._config.refresh_interval * 1000);
    }

    _stopTimer() {
      if (this._timer) clearInterval(this._timer);
      this._timer = null;
    }

    _maybeRefetch() {
      if (!this._config || !this._config.period || !this._hass) return;
      if (!this._stats || Date.now() - this._stats.at > (this._config.refresh_interval - 5) * 1000) this._fetchStats();
    }

    _firstWeekday() {
      const names = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
      const fw = this._hass && this._hass.locale && this._hass.locale.first_weekday;
      if (names.includes(fw)) return names.indexOf(fw);
      try {
        const loc = new Intl.Locale(this._lang());
        const info = typeof loc.getWeekInfo === 'function' ? loc.getWeekInfo() : loc.weekInfo;
        if (info && info.firstDay) return info.firstDay % 7;
      } catch (e) { /* ignore */ }
      return 1;
    }

    async _fetchStats() {
      const cfg = this._config, hass = this._hass;
      // One request chain per config at a time; a newer config may start its own.
      if (!cfg || !cfg.period || !hass || typeof hass.callWS !== 'function' || this._inflight === cfg) return;
      if (document.hidden && this._stats) return;
      this._inflight = cfg;
      const cfgRef = cfg;
      const ids = [...new Set([...cfg.entities.map((e) => e.entity), ...(cfg.total_entity ? [cfg.total_entity] : [])])];
      try {
        const meta = this._meta || (await this._loadMeta(ids));
        if (cfgRef !== this._config) return;
        this._meta = meta;
        const now = new Date();
        const { start, end } = periodRange(cfg.period, now, this._firstWeekday());
        const today = startOfDay(now);
        const call = (s, e, period) => {
          const msg = {
            type: 'recorder/statistics_during_period',
            start_time: s.toISOString(),
            statistic_ids: ids,
            period,
            units: { energy: 'kWh' },
            types: ['change'],
          };
          if (e) msg.end_time = e.toISOString();
          return hass.callWS(msg);
        };
        const sums = Object.fromEntries(ids.map((id) => [id, 0]));
        const add = (res, keep) => {
          for (const id of ids) {
            const rows = res && res[id];
            if (!Array.isArray(rows)) continue;
            for (const row of rows) {
              if (keep && !keep(id, row)) continue;
              const c = Number(row.change);
              if (Number.isFinite(c)) sums[id] += c;
            }
          }
        };
        if (end) {
          add(await call(start, end, 'hour'));
        } else {
          // Completed days in one coarse call, today's completed hours,
          // then the newest 5-minute statistics for the running hour.
          if (start < today) add(await call(start, today, 'month'));
          const hs = start < today ? today : start;
          const hourly = await call(hs, null, 'hour');
          add(hourly);
          const last = {};
          for (const id of ids) {
            let le = hs.getTime();
            for (const row of (hourly && hourly[id]) || []) {
              const t = toMs(row.end);
              if (Number.isFinite(t)) le = Math.max(le, t);
            }
            last[id] = le;
          }
          const from = Math.min(...ids.map((id) => last[id]));
          if (now.getTime() - from > 60e3) {
            const short = await call(new Date(from), null, '5minute');
            add(short, (id, row) => toMs(row.start) >= last[id]);
          }
        }
        if (cfgRef !== this._config) return;
        this._stats = { sums, at: Date.now(), start, end };
        this._statsErr = null;
      } catch (err) {
        if (cfgRef !== this._config) return;
        console.error('[energy-ring-card] tilastojen haku epäonnistui', err);
        this._statsErr = (err && (err.message || err.code)) || String(err);
        if (this._stats) this._stats.at = Date.now();
      } finally {
        if (this._inflight === cfgRef) this._inflight = null;
        if (cfgRef === this._config) {
          this._statsVer++;
          this._render();
        }
      }
    }

    async _loadMeta(ids) {
      try {
        const res = await this._hass.callWS({ type: 'recorder/get_statistics_metadata', statistic_ids: ids });
        const ok = new Set((res || []).filter((m) => m && m.has_sum !== false).map((m) => m.statistic_id));
        const missing = new Set(ids.filter((id) => !ok.has(id)));
        if (missing.size) {
          console.warn('[energy-ring-card] Näillä entiteeteillä ei ole energiatilastoja (state_class total/total_increasing tarvitaan):', [...missing].join(', '));
        }
        return { missing };
      } catch (e) {
        return { missing: new Set() };
      }
    }

    /* ---------- model ---------- */
    _lang() {
      const h = this._hass || {};
      return (h.locale && h.locale.language) || h.language || 'en';
    }

    _t() {
      return STR[this._lang().slice(0, 2)] || STR.en;
    }

    _numFmt(opts) {
      const l = (this._hass && this._hass.locale) || {};
      const key = `${l.language}|${l.number_format}|${JSON.stringify(opts)}`;
      let f = this._nf.get(key);
      if (!f) {
        let loc;
        switch (l.number_format) {
          case 'comma_decimal': loc = ['en-US', 'en']; break;
          case 'decimal_comma': loc = ['de', 'es', 'it']; break;
          case 'space_comma': loc = ['fr', 'sv', 'cs']; break;
          case 'system': loc = undefined; break;
          default: loc = this._lang();
        }
        const o = { ...opts };
        if (l.number_format === 'none') o.useGrouping = false;
        try { f = new Intl.NumberFormat(loc, o); } catch (e) { f = new Intl.NumberFormat(undefined, o); }
        this._nf.set(key, f);
      }
      return f;
    }

    _fmt(base, kind, unit) {
      if (base == null || !Number.isFinite(base)) return { num: '–', unit: '' };
      let v = base, u = unit || '';
      const a = Math.abs(base);
      if (kind === 'power') {
        if (a >= 1e6) { v = base / 1e6; u = 'MW'; } else if (a >= 1e3) { v = base / 1e3; u = 'kW'; } else { u = 'W'; }
      } else if (kind === 'energy') {
        // kWh is the unit people know from their bills — switch only at 100 MWh.
        if (a >= 1e8) { v = base / 1e6; u = 'MWh'; } else { v = base / 1e3; u = 'kWh'; }
      }
      let dec = this._config.decimals;
      if (dec == null || dec === '') {
        if (u === 'W') dec = 0;
        else { const av = Math.abs(v); dec = av >= 100 ? 0 : av >= 10 ? 1 : 2; }
      }
      dec = Math.min(6, Math.max(0, Number(dec) || 0));
      return { num: this._numFmt({ minimumFractionDigits: dec, maximumFractionDigits: dec }).format(v), unit: u };
    }

    _pct(p) {
      const d = p > 0 && p < 0.095 ? 1 : 0;
      return this._numFmt({ style: 'percent', minimumFractionDigits: d, maximumFractionDigits: d }).format(p || 0);
    }

    _inputSig() {
      const h = this._hass, c = this._config;
      const parts = [h.themes && h.themes.darkMode ? 1 : 0, this._lang(), h.locale && h.locale.number_format];
      if (c.period) parts.push(this._statsVer, this._statsErr || '');
      const ids = c.entities.map((e) => e.entity);
      if (c.total_entity) ids.push(c.total_entity);
      for (const id of ids) {
        const s = h.states[id];
        if (!s) parts.push('∅');
        else if (c.period) parts.push(s.attributes.friendly_name);
        else parts.push(`${s.state}|${s.attributes.unit_of_measurement}|${s.attributes.friendly_name}`);
      }
      return parts.join('§');
    }

    _model() {
      const cfg = this._config, hass = this._hass, t = this._t();
      const dark = !!(hass.themes && hass.themes.darkMode);
      const pal = PALETTE[dark ? 'dark' : 'light'];
      const otherColor = OTHER_COLOR[dark ? 'dark' : 'light'];
      const statsMode = !!cfg.period;
      const stats = this._stats;
      const read = (id) => {
        if (statsMode) {
          if (this._meta && this._meta.missing.has(id)) return { base: null, kind: 'energy', unit: 'kWh', why: 'nostats' };
          if (!stats) return { base: null, kind: 'energy', unit: 'kWh', why: 'pending' };
          return { base: (stats.sums[id] || 0) * 1000, kind: 'energy', unit: 'kWh' };
        }
        const s = hass.states[id];
        if (!s) return { base: null, kind: null, unit: '', why: 'unavailable' };
        const unit = (s.attributes && s.attributes.unit_of_measurement) || '';
        const u = UNITS[unit];
        const v = s.state === 'unavailable' || s.state === 'unknown' ? NaN : Number(s.state);
        if (!Number.isFinite(v)) return { base: null, kind: u ? u[0] : null, unit, why: 'unavailable' };
        return { base: u ? v * u[1] : v, kind: u ? u[0] : 'other', unit };
      };

      const items = cfg.entities.map((ec, idx) => {
        const s = hass.states[ec.entity];
        const r = read(ec.entity);
        const color = resolveColor(ec.color) || (idx < pal.length ? pal[idx] : null);
        return {
          key: `e${idx}`, idx, entity: ec.entity,
          name: String(ec.name != null ? ec.name : (s && s.attributes.friendly_name) || ec.entity),
          color, folded: !color, ...r,
          available: r.base != null,
          v: r.base != null ? Math.max(0, r.base) : 0,
        };
      });
      const tot = cfg.total_entity ? read(cfg.total_entity) : null;
      const total = tot && tot.base != null ? Math.max(0, tot.base) : null;
      const firstKind = items.find((i) => i.available && i.kind);
      const kind = (tot && tot.kind) || (firstKind && firstKind.kind) || (items.find((i) => i.kind) || {}).kind || 'other';
      const unitOther = kind === 'other' ? ((tot && tot.unit) || (items.find((i) => i.unit) || {}).unit || '') : '';
      const kinds = new Set(items.filter((i) => i.available).map((i) => i.kind));
      if (tot && tot.kind) kinds.add(tot.kind);
      if (kinds.size > 1) this._warn('mix', 'energy-ring-card: entiteeteillä on eri suureita (teho W vs. energia kWh) — osuudet eivät ole vertailukelpoisia.');

      const vis = items.filter((i) => !i.folded);
      const fold = items.filter((i) => i.folded);
      const visSum = vis.reduce((a, i) => a + i.v, 0);
      const foldSum = fold.reduce((a, i) => a + i.v, 0);
      const parts = visSum + foldSum;
      const D = Math.max(total != null ? total : 0, parts);
      const otherV = total != null && cfg.show_other ? D - visSum : foldSum;

      let segs = vis.filter((i) => i.v > 0);
      if (cfg.sort) segs = segs.slice().sort((a, b) => b.v - a.v);
      let other = null;
      if (otherV > 0 && otherV > D * 1e-4) {
        other = {
          key: 'other', name: String(cfg.other_name || t.other), color: otherColor, v: otherV, base: otherV,
          entity: cfg.total_entity || null, isOther: true, available: true, kind, unit: unitOther,
        };
        segs.push(other);
      }
      let a = 0;
      for (const s of segs) {
        const sw = D > 0 ? (s.v / D) * TAU : 0;
        s.start = a; s.sweep = sw; s.end = a + sw; s.mid = a + sw / 2;
        a += sw;
      }
      const all = other ? [...items, other] : items;
      for (const i of all) {
        i.pct = D > 0 ? i.v / D : 0;
        i.fmtd = i.available ? this._fmt(i.base, i.kind || kind, i.kind ? i.unit : unitOther) : { num: '–', unit: '' };
        i.valStr = i.available ? `${i.fmtd.num}${NB}${i.fmtd.unit}`.trim() : '';
        i.pctStr = this._pct(i.pct);
        i.display = i.available ? i.valStr : i.why === 'pending' ? '…' : i.why === 'nostats' ? t.nostats : t.unavailable;
        i.swatch = i.folded ? otherColor : i.color;
      }

      const anyData = items.some((i) => i.available);
      const centerBase = total != null ? total : anyData ? parts : null;
      const loading = statsMode && !stats;
      let centerSub;
      if (loading && !this._statsErr) centerSub = t.loading;
      else if (loading) centerSub = t.error;
      else if (cfg.total_label != null) centerSub = String(cfg.total_label);
      else centerSub = kind === 'power' ? t.totalPower : kind === 'energy' ? t.totalEnergy : t.total;
      const centerTop = cfg.center_label != null ? String(cfg.center_label) : statsMode ? t[cfg.period] : kind === 'power' ? t.now : '';
      const center = this._fmt(centerBase, kind, unitOther);

      const msgs = [];
      if (this._statsErr) msgs.push(`${t.error}: ${this._statsErr}`);
      if (statsMode && this._meta && this._meta.missing.size) msgs.push(`${t.nostats}: ${[...this._meta.missing].join(', ')}`);

      return {
        items, other, segs, D, kind, center, centerTop, centerSub, loading,
        byKey: new Map(all.map((i) => [i.key, i])),
        legendAll: other ? [...items, other] : items,
        labeled: new Set(),
        msg: msgs.join(' · '),
        aria: `${centerTop} ${center.num} ${center.unit}: ${segs.map((s) => `${s.name} ${s.valStr}`).join(', ')}`,
      };
    }

    _warn(key, text) {
      if (this._warned.has(key)) return;
      this._warned.add(key);
      console.warn(text);
    }

    /* ---------- render ---------- */
    _font() {
      const f = this.isConnected && this._svg ? getComputedStyle(this._svg).fontFamily : '';
      return f || 'Roboto, Noto, sans-serif';
    }

    _render(force) {
      if (!this._config || !this._hass || !this._svg) return;
      const sig = this._inputSig();
      if (!force && sig === this._sig) return;
      this._sig = sig;
      const m = this._model();
      this._m = m;
      this._fam = this._font();
      this._svg.classList.toggle('loading', m.loading);
      this._svg.setAttribute('aria-label', m.aria);
      this._drawRing(m);
      this._drawLabels(m);
      this._drawLegend(m);
      if (this._hover && !m.byKey.has(this._hover)) this._hover = null;
      this._applyHover();
      this._msg.textContent = m.msg;
    }

    _intro() {
      this._introDone = true;
      if (!this._segEls.size || (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches)) return;
      const els = [...this._segEls.values()].filter((el) => el.live);
      for (const el of els) {
        el.seg.style.transition = 'none';
        el.seg.style.strokeDasharray = `0 ${CIRC}`;
      }
      this._svg.getBoundingClientRect();
      for (const el of els) {
        el.seg.style.transition = '';
        el.seg.style.strokeDasharray = `${el.dash} ${CIRC}`;
      }
    }

    _drawRing(m) {
      const live = new Set();
      const single = m.segs.length === 1 && m.segs[0].sweep >= TAU - 1e-6;
      let fresh = false;
      for (const s of m.segs) {
        live.add(s.key);
        let el = this._segEls.get(s.key);
        if (!el) {
          const seg = svgEl('circle', { class: 'seg', cx: CX, cy: CY, r: R, 'data-key': s.key });
          const hit = svgEl('circle', { class: 'hit', cx: CX, cy: CY, r: R, 'data-key': s.key, tabindex: '0', role: 'button' });
          seg.style.strokeDasharray = `0 ${CIRC}`;
          seg.style.strokeDashoffset = `${-(s.start * R + GAP / 2)}`;
          this._segG.appendChild(seg);
          this._hitG.appendChild(hit);
          el = { seg, hit };
          this._segEls.set(s.key, el);
          fresh = true;
        }
        const len = s.sweep * R;
        el.live = true;
        el.dash = single ? CIRC + 1 : Math.max(0, len - GAP);
        el.off = single ? 0 : s.start * R + GAP / 2;
        el.seg.style.stroke = s.color;
        el.hit.style.display = '';
        el.hit.style.strokeDasharray = `${Math.max(0, len)} ${CIRC}`;
        el.hit.style.strokeDashoffset = `${-s.start * R}`;
        el.hit.setAttribute('aria-label', `${s.name}: ${s.valStr} (${s.pctStr})`);
      }
      // Segments that dropped to zero shrink away to their centre; the element
      // is kept so the segment can grow back smoothly later.
      for (const [k, el] of this._segEls) {
        if (live.has(k) || !el.live) continue;
        el.live = false;
        el.off += el.dash / 2;
        el.dash = 0;
        el.hit.style.display = 'none';
        el.seg.classList.remove('on');
      }
      if (fresh && this.isConnected) {
        this._svg.getBoundingClientRect(); // commit start state so new segments grow in
        this._introDone = true;
      }
      for (const el of this._segEls.values()) {
        el.seg.style.strokeDasharray = `${el.dash} ${CIRC}`;
        el.seg.style.strokeDashoffset = `${-el.off}`;
      }
    }

    _mkLabel(key) {
      const u = this._uid;
      const g = svgEl('g', { class: 'lbl off', 'data-key': key });
      const hit = svgEl('path', { class: 'lhit' });
      const dot = svgEl('circle', { class: 'dot', r: DOT_R });
      const tName = svgEl('text', { class: 'ln nm' });
      const pName = svgEl('textPath', {});
      const sName = svgEl('tspan', {});
      pName.appendChild(sName);
      tName.appendChild(pName);
      const tVal = svgEl('text', { class: 'ln vl' });
      const pVal = svgEl('textPath', { startOffset: '50%' });
      const sVal = svgEl('tspan', {});
      const sPct = svgEl('tspan', { class: 'pc' });
      pVal.append(sVal, sPct);
      tVal.appendChild(pVal);
      g.append(hit, dot, tName, tVal);
      this._lblG.appendChild(g);
      setHref(pName, `${u}-tn`);
      setHref(pVal, `${u}-tv`);
      const el = { g, hit, dot, pName, sName, pVal, sVal, sPct, bottom: false, deg: null };
      this._lblEls.set(key, el);
      return el;
    }

    _drawLabels(m) {
      const fam = this._fam;
      const cands = m.segs.filter((s) => s.sweep > 1e-4).map((s) => {
        const vW = textW(s.valStr, FS_VAL, 600, fam);
        const pW = textW(`${NB}·${NB}${s.pctStr}`, FS_VAL, 400, fam);
        const variants = [];
        truncations(s.name).forEach((nm, i) => {
          const nW = DOT_SPACE + textW(nm, FS_NAME, 500, fam);
          if (i === 0) variants.push({ name: nm, nW, pct: true, w: Math.max(nW / RB_NAME, (vW + pW) / RB_VAL) });
          variants.push({ name: nm, nW, pct: false, w: Math.max(nW / RB_NAME, vW / RB_VAL) });
        });
        return { s, key: s.key, a: s.start, b: s.end, mid: s.mid, value: s.v, variants, vi: 0, w: 0, c: s.mid };
      });

      // Fit: shorten or drop the smallest conflicting label until all fit.
      // Very narrow cards skip ring labels entirely; the legend takes over.
      let active = this._compact ? [] : cands.slice();
      for (let guard = 0; guard < 500 && active.length; guard++) {
        for (const l of active) l.w = l.variants[l.vi].w;
        const res = placeLabels(active);
        if (res.ok) break;
        const pool = res.conflicts.length ? res.conflicts : active;
        let victim = null;
        for (const l of pool) if (!victim || l.value < victim.value) victim = l;
        if (victim.vi < victim.variants.length - 1) victim.vi++;
        else active = active.filter((l) => l !== victim);
      }
      const placed = new Map(active.map((l) => [l.key, l]));
      m.labeled = new Set(placed.keys());

      const live = new Set(cands.map((l) => l.key));
      for (const [k, el] of this._lblEls) if (!live.has(k)) el.g.classList.add('off');
      for (const l of cands) {
        let el = this._lblEls.get(l.key);
        const isNew = !el;
        if (!el) el = this._mkLabel(l.key);
        const p = placed.get(l.key);
        if (!p) { el.g.classList.add('off'); continue; }
        const v = p.variants[p.vi];
        const c = ((p.c % TAU) + TAU) % TAU;
        const bottom = c > Math.PI / 2 && c < 1.5 * Math.PI;
        const flip = isNew || el.bottom !== bottom;
        const ln = bottom ? LINE.bn : LINE.tn;
        const lv = bottom ? LINE.bv : LINE.tv;
        if (flip) {
          setHref(el.pName, `${this._uid}-${bottom ? 'bn' : 'tn'}`);
          setHref(el.pVal, `${this._uid}-${bottom ? 'bv' : 'tv'}`);
        }
        el.sName.textContent = v.name;
        el.sVal.textContent = l.s.valStr;
        el.sPct.textContent = v.pct ? `${NB}·${NB}${l.s.pctStr}` : '';
        // Name centred together with its colour dot; dot sits just before the text.
        const start = ln.len / 2 + DOT_SPACE / 2;
        el.pName.setAttribute('startOffset', r2(start));
        const textStart = start - (v.nW - DOT_SPACE) / 2;
        const aStart = bottom ? Math.PI + SPAN / 2 - textStart / ln.rb : -SPAN / 2 + textStart / ln.rb;
        const aDot = bottom ? aStart + (DOT_GAP + DOT_R) / ln.rc : aStart - (DOT_GAP + DOT_R) / ln.rc;
        const [dx, dy] = pt(aDot, ln.rc);
        el.dot.setAttribute('cx', r2(dx));
        el.dot.setAttribute('cy', r2(dy));
        el.dot.style.fill = l.s.color;
        // Hover target across the whole label.
        const hw = l.w / 2 + 0.02;
        const hr = (R_L1 + R_L2) / 2;
        el.hit.setAttribute('d', bottom ? arcPath(hr, Math.PI - hw, Math.PI + hw) : arcPath(hr, -hw, hw));
        // Rotate the label group into place (animated unless it jumps or flips).
        const target = ((bottom ? c - Math.PI : c) * 180) / Math.PI;
        const wasOff = el.g.classList.contains('off');
        let deg = target;
        if (!flip && !wasOff && el.deg != null) deg = el.deg + norm180(target - el.deg);
        if (flip || wasOff) {
          el.g.style.transition = 'none';
          el.g.style.transform = `rotate(${r2(deg)}deg)`;
          el.g.getBoundingClientRect();
          el.g.style.transition = '';
        } else {
          el.g.style.transform = `rotate(${r2(deg)}deg)`;
        }
        el.deg = deg;
        el.bottom = bottom;
        el.g.classList.remove('off');
      }
    }

    _drawLegend(m) {
      const mode = this._config.legend;
      let list = [];
      if (mode === true) list = m.legendAll;
      else if (mode === 'auto') list = m.legendAll.filter((i) => !m.labeled.has(i.key));
      this._legend.replaceChildren(...list.map((i) => {
        const d = document.createElement('div');
        d.className = `li${i.available ? '' : ' na'}`;
        d.setAttribute('data-key', i.key);
        if (i.entity) { d.tabIndex = 0; d.setAttribute('role', 'button'); }
        const sw = document.createElement('span');
        sw.className = 'sw';
        sw.style.background = i.swatch;
        const n = document.createElement('span');
        n.className = 'n';
        n.textContent = i.name;
        const v = document.createElement('span');
        v.className = 'v';
        v.textContent = i.display;
        d.append(sw, n, v);
        return d;
      }));
    }

    _setHover(key) {
      if (key === this._hover) return;
      this._hover = key;
      this._applyHover();
    }

    _applyHover() {
      const m = this._m;
      if (!m) return;
      const it = this._hover ? m.byKey.get(this._hover) : null;
      const hl = it ? (it.folded ? 'other' : it.key) : null;
      this._svg.classList.toggle('dim', !!it);
      this._legend.classList.toggle('dim', !!it);
      for (const [k, el] of this._segEls) el.seg.classList.toggle('on', k === hl && !!el.live);
      for (const [k, el] of this._lblEls) el.g.classList.toggle('on', k === hl);
      for (const li of this._legend.children) li.classList.toggle('on', li.getAttribute('data-key') === (it && it.key));
      this._drawCenter(it);
    }

    _drawCenter(it) {
      const m = this._m, t = this._t(), fam = this._fam;
      let num, unit, sub;
      if (it) {
        const nm = fitText(it.name, 168 - DOT_SPACE, 13.5, 500, fam);
        const full = textW(nm, 13.5, 500, fam) + DOT_SPACE;
        this._cTop.classList.add('named');
        this._cTop.textContent = nm;
        this._cTop.setAttribute('x', r2(CX + DOT_SPACE / 2));
        this._cDot.setAttribute('cx', r2(CX - full / 2 + DOT_R));
        this._cDot.setAttribute('cy', r2(Y_TOP - BL * 13.5));
        this._cDot.style.fill = it.swatch;
        this._cDot.style.display = '';
        num = it.fmtd.num;
        unit = it.fmtd.unit;
        const of = m.kind === 'power' ? t.ofPower : m.kind === 'energy' ? t.ofEnergy : t.ofTotal;
        sub = it.available ? `${it.pctStr} ${of}` : it.display;
      } else {
        this._cTop.classList.remove('named');
        this._cTop.textContent = fitText(m.centerTop.toLocaleUpperCase(this._lang()), 172, 11.5, 500, fam, 1.15);
        this._cTop.setAttribute('x', CX);
        this._cDot.style.display = 'none';
        num = m.center.num;
        unit = m.center.unit;
        sub = m.centerSub;
      }
      const nW = textW(num, 48, 400, fam);
      const uW = unit ? 5 + textW(unit, 19, 400, fam) : 0;
      const k = Math.min(1, 196 / (nW + uW));
      this._cNum.textContent = num;
      this._cNum.style.fontSize = `${r2(48 * k)}px`;
      this._cUnit.textContent = unit;
      this._cUnit.style.fontSize = `${r2(19 * k)}px`;
      this._cUnit.setAttribute('dx', unit ? r2(5 * k) : 0);
      this._cSub.textContent = fitText(sub || '', 176, 12.5, 400, fam);
    }

    _openKey(key) {
      const it = this._m && this._m.byKey.get(key);
      if (it) this._moreInfo(it.isOther ? this._config.total_entity : it.entity);
    }

    _moreInfo(entityId) {
      if (!entityId) return;
      this.dispatchEvent(new CustomEvent('hass-more-info', { detail: { entityId }, bubbles: true, composed: true }));
    }
  }

  customElements.define(TAG, EnergyRingCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: TAG,
    name: 'Energy Ring Card',
    description: 'Kokonaiskulutus renkaan keskellä, kohteiden kulutukset renkaan kaarella.',
    preview: true,
  });
  console.info(
    `%c ENERGY-RING-CARD %c v${VERSION} `,
    'color:#fff;background:#2a78d6;font-weight:600;border-radius:3px 0 0 3px',
    'color:#fff;background:#555;border-radius:0 3px 3px 0'
  );
})();
