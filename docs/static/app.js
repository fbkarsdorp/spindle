// Spindle — front end of the static site. Plain ES modules, no build step.

import * as store from './store.js';
import { LETTERS } from './search.js';

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const main = $('#main');

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (n) => Number(n).toLocaleString('en-GB');
const trimDot = (s) => String(s || '').replace(/\.$/, '');
const mb = (b) => (b / 1e6).toFixed(0);

// routes are hashes, so the site works from any static host and any sub-path
const go = (path) => '#' + path;
const motifHref = (id) => go('/motif/' + encodeURIComponent(id));
const browseHref = (id) => go('/browse/' + encodeURIComponent(id));
const searchHref = (params) => go('/search?' + new URLSearchParams(params));

const CAT_COLORS = {
  A: '#b8432f', B: '#5d7f3a', C: '#7b4a8e', D: '#2f5d8a', E: '#6f6a64', F: '#c08a2b', G: '#8a3b2a', H: '#3d8a84',
  J: '#9c6b3a', K: '#d0662f', L: '#4f6fa8', M: '#8c5f99', N: '#8f8f34', P: '#b39040', Q: '#2e7a5a', R: '#6a4e3b',
  S: '#a33b5c', T: '#cf6c86', U: '#5b8fa8', V: '#7d6aa8', W: '#4c7a3a', X: '#d79a2a', Z: '#857c55',
};
const SHORT = {
  A: 'Mythological', B: 'Animals', C: 'Tabu', D: 'Magic', E: 'The dead', F: 'Marvels', G: 'Ogres', H: 'Tests',
  J: 'Wise & foolish', K: 'Deceptions', L: 'Reversals', M: 'Fate ordained', N: 'Chance & fate', P: 'Society',
  Q: 'Rewards', R: 'Captives', S: 'Cruelty', T: 'Sex', U: 'Nature of life', V: 'Religion', W: 'Character',
  X: 'Humor', Z: 'Miscellany',
};
let CATEGORIES = {};

// ------------------------------------------------------------------ art

const artCache = new Map();
function art(name) {
  if (!artCache.has(name)) {
    artCache.set(name, fetch(`art/${name}.svg`).then((r) => (r.ok ? r.text() : '')).catch(() => ''));
  }
  return artCache.get(name);
}
async function hydrateArt(root = document) {
  await Promise.all($$('[data-art]:not([data-hydrated])', root).map(async (el) => {
    el.dataset.hydrated = '1';
    const svg = await art(el.dataset.art);
    el.innerHTML = svg.replace(/<\?xml[^>]*>/, '');
    const s = el.querySelector('svg');
    if (s) { s.setAttribute('aria-hidden', 'true'); s.setAttribute('focusable', 'false'); }
  }));
}
const artEl = (name, cls = '') => `<span class="${cls}" data-art="${name}"></span>`;
const whorl = (cls = 'whorl') => artEl('spindle', cls);
const corners = () => ['tl', 'tr', 'bl', 'br'].map((c) => `<span class="corner ${c}" data-art="corner"></span>`).join('');

let toastTimer;
function toast(msg) {
  const t = $('.toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 2200);
}

// ---------------------------------------------------------------- router

const routes = [
  [/^\/$/, viewHome],
  [/^\/search\/?$/, viewSearch],
  [/^\/motif\/(.+)$/, viewMotif],
  [/^\/browse\/?$/, viewBrowse],
  [/^\/browse\/(.+)$/, viewBrowse],
  [/^\/map\/?$/, viewMap],
  [/^\/about\/?$/, viewAbout],
];
let cleanup = null;

function route() {
  const h = location.hash.replace(/^#/, '') || '/';
  const q = h.indexOf('?');
  return { path: q < 0 ? h : h.slice(0, q), params: new URLSearchParams(q < 0 ? '' : h.slice(q + 1)) };
}

function navigate(hash, { replace = false } = {}) {
  if (replace) {
    history.replaceState(null, '', hash);
    render();
  } else if (location.hash === hash) render();
  else location.hash = hash;
}

async function render() {
  const { path } = route();
  if (cleanup) { cleanup(); cleanup = null; }
  const section = path.split('/')[1] || 'home';
  $$('.nav a').forEach((a) => (a.dataset.nav === section ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current')));
  for (const [re, view] of routes) {
    const m = path.match(re);
    if (!m) continue;
    try {
      cleanup = (await view(...m.slice(1).map(decodeURIComponent))) || null;
    } catch (err) {
      console.error(err);
      main.innerHTML = `<div class="wrap empty">${artEl('owl-empty', 'owl')}<p>${esc(err.message || 'Something went wrong.')}</p></div>`;
    }
    hydrateArt(main);
    return;
  }
  main.innerHTML = `<div class="wrap empty">${artEl('owl-empty', 'owl')}<p>This page is not in the index.</p></div>`;
  hydrateArt(main);
}
window.addEventListener('hashchange', () => { render(); window.scrollTo({ top: 0 }); });

$('.theme-toggle').addEventListener('click', () => {
  const root = document.documentElement;
  const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  root.dataset.theme = dark ? 'light' : 'dark';
  try { localStorage.setItem('spindle-theme', root.dataset.theme); } catch (e) { /* private mode */ }
  window.dispatchEvent(new Event('themechange'));
});

// ---------------------------------------------------------- the query box

function modelLine(m) {
  if (m.status === 'loading') {
    const pct = m.total ? Math.round((100 * m.loaded) / m.total) : 0;
    return `<span class="model-status">${m.total ? `Loading the language model, once: ${mb(m.loaded)} of ${mb(m.total)} MB` : 'Loading the language model…'}
      <span class="model-bar"><i style="width:${pct}%"></i></span></span>`;
  }
  if (m.status === 'error') return `<span class="model-status err">The language model could not be loaded (${esc(m.error)}). Motif numbers and browsing still work.</span>`;
  if (m.status === 'ready') return '<span>A few words, or a motif number like <b>D1960.3</b>.</span>';
  return '<span>Describe what happens, in your own words — or type a motif number like <b>D1960.3</b>.</span>';
}

function queryBox({ value = '', placeholder, autofocus = false } = {}) {
  const el = document.createElement('form');
  el.className = 'query';
  el.setAttribute('role', 'search');
  el.innerHTML = `
    <label class="sr-only" for="q">Describe a motif</label>
    <textarea id="q" rows="1" spellcheck="true" enterkeyhint="search" placeholder="${esc(placeholder || 'Describe a motif in your own words…')}">${esc(value)}</textarea>
    <div class="query-bar">
      <span class="mode" aria-live="polite"></span>
      <button class="btn" type="submit">Search</button>
    </div>`;
  const ta = $('textarea', el);
  const grow = () => {
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, window.innerHeight * 0.4) + 'px';
  };
  ta.addEventListener('input', grow);
  ta.addEventListener('focus', store.warm, { once: true });
  ta.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); el.requestSubmit(); }
  });
  el.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = ta.value.trim();
    if (!text) { ta.focus(); return; }
    const keep = route().path === '/search' ? route().params : new URLSearchParams();
    const p = new URLSearchParams();
    for (const k of ['in', 'region', 'culture', 'type']) keep.getAll(k).forEach((v) => p.append(k, v));
    p.set('q', text);
    navigate(searchHref(p));
  });
  const off = store.onModel((m) => { $('.mode', el).innerHTML = modelLine(m); });
  el.dispose = off;
  requestAnimationFrame(() => {
    grow();
    if (autofocus) { ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); }
  });
  return el;
}

// ------------------------------------------------------------------ home

const EXAMPLES = [
  'a man who turns into a wolf',
  'the youngest daughter is kind to an old woman',
  'animals that help the hero because he spared them',
  'why the sea is salt',
  'a ghost returns to reveal buried treasure',
  'trickster pretends to be dead',
  'Melusine',
  'D1960.3',
];

async function viewHome() {
  document.title = "Spindle · Thompson's Motif-Index";
  main.innerHTML = `
    <div class="wrap fade-in">
      <section class="hero">
        <span class="hero-art" data-art="hero"></span>
        <h1>Thompson’s Motif-Index, <i>spun anew</i></h1>
        <p class="lede">Forty-six thousand motifs of folk literature, findable by what they mean. Describe one in your own words, and Spindle finds it however Thompson worded it.</p>
        <div class="home-query"></div>
        <div class="examples">
          <span class="label eyebrow">or try</span>
          ${EXAMPLES.map((x) => `<a class="chip" href="${searchHref({ q: x })}">${esc(x)}</a>`).join('')}
        </div>
      </section>

      <section class="home-section feature">
        <div>
          <div class="section-head"><h2>Three ways in</h2></div>
          <div class="ways">
            <div class="way"><span class="num">i</span><div><h3><a href="${go('/search')}">Describe</a></h3><p>Say what happens — “a girl must not look back” — and Spindle finds the motifs that mean it, in any branch of the index.</p></div></div>
            <div class="way"><span class="num">ii</span><div><h3><a href="${go('/browse')}">Browse</a></h3><p>Walk Thompson’s own tree from A to Z, from the twenty-three branches down to the last subdivision.</p></div></div>
            <div class="way"><span class="num">iii</span><div><h3><a href="${go('/map')}">Wander</a></h3><p>Drift across a map on which kindred motifs lie together, whatever letter Thompson filed them under.</p></div></div>
          </div>
        </div>
        <div class="leaf oracle" aria-live="polite">
          ${corners()}
          <div class="oracle-body"><div class="loading">${whorl()} drawing a motif…</div></div>
        </div>
      </section>

      <section class="home-section">
        <div class="section-head"><h2>The twenty-three branches</h2><span class="aside">Thompson’s classification, A to Z</span></div>
        <div class="cats"></div>
      </section>
    </div>`;
  const box = queryBox({ autofocus: matchMedia('(min-width: 760px)').matches });
  $('.home-query', main).append(box);
  hydrateArt(main);
  $('.cats', main).innerHTML = catsHTML(await store.branches());
  hydrateArt(main);
  oracle();
  return () => box.dispose();
}

function catsHTML(branches) {
  return branches.map((b) => `
    <a class="cat" href="${browseHref(b.id)}">
      <span class="cat-art" data-art="${b.id}"></span>
      <span><span class="cat-letter">${b.id}</span> <span class="cat-name">${esc(b.title)}</span></span>
      <span class="cat-count">${fmt(b.count)} motifs</span>
    </a>`).join('');
}

async function oracle() {
  const box = $('.oracle-body', main);
  if (!box) return;
  const m = await store.random();
  box.innerHTML = `
    <div class="eyebrow"><span>A motif, at random</span><button class="again" type="button">another ↻</button></div>
    <h3><a href="${motifHref(m.id)}">${esc(trimDot(m.title))}</a></h3>
    ${m.note ? `<p>${esc(m.note)}</p>` : ''}
    <div><span class="mid">${esc(m.id)}</span> <span class="muted">· ${esc(m.path.map((p) => trimDot(p.title)).slice(-2).join(' › '))}</span></div>
    ${m.cultures.length ? `<div class="muted" style="font-size:15px;margin-top:6px;font-style:italic">${esc(m.cultures.slice(0, 6).join(', '))}${m.n_cultures > 6 ? ' …' : ''}</div>` : ''}`;
  $('.again', box).addEventListener('click', oracle);
}

// --------------------------------------------------------------- search

async function viewSearch() {
  const params = route().params;
  const q = params.get('q') || '';
  const sel = { within: params.getAll('in'), regions: params.getAll('region'), cultures: params.getAll('culture'), types: params.getAll('type') };
  document.title = q ? `${q} · Spindle` : 'Search · Spindle';
  CATEGORIES = (await store.index()).categories;

  main.innerHTML = `
    <div class="wrap">
      <div class="search-top"></div>
      <div class="layout">
        <aside class="facets" aria-label="Refine"></aside>
        <section class="results-col" aria-live="polite"></section>
        <aside class="detail-pane" aria-label="Motif"></aside>
      </div>
    </div>`;
  const box = queryBox({ value: q, autofocus: !q });
  $('.search-top', main).append(box);
  const col = $('.results-col', main);
  const disposers = [() => box.dispose()];
  const anyFilter = sel.within.length || sel.regions.length || sel.cultures.length || sel.types.length;

  if (!q && !anyFilter) {
    col.innerHTML = `<div class="empty">${artEl('owl-empty', 'owl')}<p>Describe what happens, who acts, what is forbidden or transformed. Plain words are fine — Spindle searches by meaning.</p></div>`;
    $('.layout', main).classList.add('no-detail');
    renderFacets({}, sel);
    store.warm();
    return () => disposers.forEach((f) => f());
  }

  col.innerHTML = `<div class="loading">${whorl()} <span class="msg">searching the index…</span></div>`;
  hydrateArt(col);
  disposers.push(store.onModel((m) => {
    const msg = $('.loading .msg', col);
    if (msg && m.status === 'loading') msg.textContent = 'loading the language model — once, then searches take a moment…';
  }));
  const query = [q, ...sel.within.map((v) => `in:${v}`), ...sel.regions.map((v) => `region:"${v}"`),
    ...sel.cultures.map((v) => `culture:"${v}"`), ...sel.types.map((v) => `type:${v}`)].filter(Boolean).join(' ');
  let data;
  try {
    data = await store.search(query, { k: 60 });
  } catch (err) {
    col.innerHTML = `<div class="empty">${artEl('owl-empty', 'owl')}<p>${esc(err.message)}</p></div>`;
    hydrateArt(col);
    return () => disposers.forEach((f) => f());
  }
  if (route().params.toString() !== params.toString()) return () => disposers.forEach((f) => f());
  const res = data.results;
  renderFacets(data.facets, sel);
  const active = [...sel.within.map((v) => ['in', v]), ...sel.regions.map((v) => ['region', v]), ...sel.cultures.map((v) => ['culture', v]), ...sel.types.map((v) => ['type', v])];
  col.innerHTML = `
    <div class="results-meta">
      <span>${res.length ? `${res.length === 60 ? 'Best 60' : res.length} motif${res.length === 1 ? '' : 's'}` : 'Nothing found'}${q ? ` for <i>${esc(q)}</i>` : ''} <span class="muted">· ${Math.round(data.ms)} ms</span></span>
      ${active.length ? `<span class="active">${active.map(([k, v]) => `<a class="chip" aria-pressed="true" href="${esc(withoutParam(k, v))}">${esc(labelFor(k, v))} ✕</a>`).join('')}</span>` : ''}
    </div>
    ${q && res.length && res[0].score < 0.25 && res[0].via === 'meaning' && !active.length ? `<p class="weak">Nothing in the index matches this closely; these are distant guesses. Thompson may use other words — try describing what happens.</p>` : ''}
    ${res.length ? `<ol class="results">${res.map(resultItem).join('')}</ol>` : `<div class="empty">${artEl('owl-empty', 'owl')}<p>The owl found nothing. Try other words, or loosen the filters.</p></div>`}`;
  hydrateArt(col);

  const pane = $('.detail-pane', main);
  const wide = () => matchMedia('(min-width: 1181px)').matches;
  let current = null;
  const select = async (id, { scroll = false } = {}) => {
    if (!wide()) { navigate(motifHref(id)); return; }
    current = id;
    $$('.result', col).forEach((r) => r.setAttribute('aria-current', String(r.dataset.id === id)));
    const li = $(`.result[data-id="${CSS.escape(id)}"]`, col);
    if (scroll && li) li.scrollIntoView({ block: 'nearest' });
    const m = await store.full(id);
    if (current !== id) return;
    pane.innerHTML = `<div class="leaf motif fade-in">${motifHTML(m)}</div>`;
    pane.scrollTop = 0;
    wireMotif(pane, m);
    hydrateArt(pane);
  };
  col.addEventListener('click', (e) => {
    const r = e.target.closest('.result');
    if (!r || e.metaKey || e.ctrlKey) return;
    e.preventDefault();
    select(r.dataset.id);
  });
  const onKey = (e) => {
    if (e.target.matches('textarea, input')) return;
    if (!['ArrowDown', 'ArrowUp', 'j', 'k'].includes(e.key)) return;
    const ids = $$('.result', col).map((r) => r.dataset.id);
    if (!ids.length) return;
    e.preventDefault();
    const i = ids.indexOf(current);
    const next = e.key === 'ArrowDown' || e.key === 'j' ? Math.min(ids.length - 1, i + 1) : Math.max(0, i - 1);
    select(ids[next], { scroll: true });
  };
  document.addEventListener('keydown', onKey);
  disposers.push(() => document.removeEventListener('keydown', onKey));
  if (res.length && wide()) select(res[0].id);
  else $('.layout', main).classList.toggle('no-detail', !wide());
  return () => disposers.forEach((f) => f());
}

function labelFor(k, v) {
  if (k === 'in') return LETTERS.includes(v) ? `${v} · ${CATEGORIES[v] || ''}` : v;
  if (k === 'type') return `Type ${v}`;
  return v;
}
function withoutParam(k, v) {
  const p = new URLSearchParams(route().params);
  const vals = p.getAll(k).filter((x) => x !== v);
  p.delete(k);
  vals.forEach((x) => p.append(k, x));
  return searchHref(p);
}
function withParam(k, v) {
  const p = new URLSearchParams(route().params);
  if (!p.getAll(k).includes(v)) p.append(k, v);
  return searchHref(p);
}

function resultItem(r) {
  const path = r.path.filter((p) => p.id.length > 1).slice(-2);
  return `
    <li><a class="result" data-id="${esc(r.id)}" href="${motifHref(r.id)}">
      <div class="result-head"><span class="mid">${esc(r.id)}</span><span class="result-title">${esc(r.title)}</span>
        ${r.via === 'meaning' ? `<span class="score" title="match ${(r.score * 100).toFixed(0)}%"><i style="width:${Math.max(4, r.score * 100)}%"></i></span>` : ''}</div>
      ${r.note ? `<div class="result-note">${esc(r.note)}</div>` : ''}
      <div class="result-path">${path.map((p) => `<span>${esc(trimDot(p.title))}</span>`).join('')}</div>
      ${r.via === 'refs' ? `<div class="result-cult">named in the references</div>` : ''}
      ${r.cultures.length ? `<div class="result-cult">${esc(r.cultures.slice(0, 5).join(', '))}${r.n_cultures > 5 ? ` and ${r.n_cultures - 5} more` : ''}</div>` : ''}
    </a></li>`;
}

async function renderFacets(f, sel) {
  const ix = await store.index();
  const box = $('.facets', main);
  if (!box) return;
  const cats = Object.entries(f.categories || {}).sort((a, b) => b[1] - a[1]);
  const regs = Object.entries(f.regions || {}).sort((a, b) => b[1] - a[1]);
  box.innerHTML = `
    <div class="facet-group">
      <h4>Branch</h4>
      ${sel.within.filter((w) => !cats.find(([L]) => L === w)).map((w) => facetBtn('in', w, labelFor('in', w), null, true)).join('')}
      ${cats.map(([L, n]) => facetBtn('in', L, ix.categories[L], n, sel.within.includes(L), L)).join('') || '<span class="muted" style="font-size:15px">—</span>'}
    </div>
    <div class="facet-group">
      <h4>Attested in</h4>
      ${(regs.length ? regs : ix.meta.regions.map((r) => [r, null])).map(([r, n]) => facetBtn('region', r, r, n, sel.regions.includes(r))).join('')}
    </div>
    <div class="facet-group">
      <h4>Culture</h4>
      <input class="facet-filter" list="cultures" placeholder="e.g. Irish, Japanese…" aria-label="Filter by culture">
      <datalist id="cultures">${ix.meta.cultures.slice(0, 500).map((c) => `<option value="${esc(c)}">`).join('')}</datalist>
      ${sel.cultures.map((c) => facetBtn('culture', c, c, null, true)).join('')}
    </div>`;
  hydrateArt(box);
  $('.facet-filter', box).addEventListener('change', (e) => {
    const v = e.target.value.trim();
    if (v) navigate(withParam('culture', v));
  });
  box.addEventListener('click', (e) => {
    const b = e.target.closest('.facet');
    if (!b) return;
    navigate(b.getAttribute('aria-pressed') === 'true' ? withoutParam(b.dataset.k, b.dataset.v) : withParam(b.dataset.k, b.dataset.v));
  });
}
function facetBtn(k, v, label, n, on, artName) {
  return `<button class="facet" type="button" data-k="${k}" data-v="${esc(v)}" aria-pressed="${on}">
    ${artName ? `<span class="fart" data-art="${artName}"></span>` : ''}<span>${esc(label)}</span>${n != null ? `<span class="n">${n}</span>` : ''}</button>`;
}

// ---------------------------------------------------------------- motif

function crumbsHTML(path) {
  return path.map((p) => {
    const href = p.kind === 'motif' ? motifHref(p.id) : browseHref(p.id);
    const label = p.kind === 'category' ? `${p.id}. ${p.title}` : trimDot(p.title);
    return `<a href="${href}">${esc(label)}</a>`;
  }).join('<span class="sep">›</span>');
}

const ID_IN_TEXT = /(?<![A-Za-z\d])([A-HJ-NP-Z]\d{1,4}(?:\.\d+)*)(?=[\s.,;:)\]]|$)/g;
function refsHTML(refs) {
  let s = esc(refs);
  s = s.replace(/(^|[;—]\s*|\.\s+|\(\s*)(\*{0,2}[A-Z][A-Za-zÀ-ÿ.’'\- ]{1,40}?(?:\s\([^)]{1,50}\))?)(:)/g, '$1<span class="lab">$2</span>$3');
  s = s.replace(ID_IN_TEXT, (m, id) => `<a class="xr" href="${motifHref(id)}">${id}</a>`);
  return s;
}

function mlist(items, { ctx = true } = {}) {
  return `<ul class="mlist">${items.map((x) => {
    const where = ctx && x.path ? x.path.filter((p) => p.id.length > 1).slice(-1).map((p) => trimDot(p.title))[0] : '';
    return `<li><a class="mid" href="${motifHref(x.id)}">${esc(x.id)}</a>
      <span><a href="${motifHref(x.id)}">${esc(x.title)}</a>${x.n_children ? `<span class="more">+${x.n_children}</span>` : ''}
      ${where ? `<span class="ctx">${esc(where)}</span>` : ''}</span></li>`;
  }).join('')}</ul>`;
}

function motifHTML(m, { full = false } = {}) {
  const regions = {};
  for (const [c, r] of m.culture_regions || []) (regions[r] ??= []).push(c);
  const children = (m.children || []).filter((c) => c.kind === 'motif');
  const refs = m.refs || '';
  const longRefs = refs.length > 700;
  return `
    ${!full ? `<a class="open-full" href="${motifHref(m.id)}">open page ↗</a>` : ''}
    <div class="crumbs">${crumbsHTML(m.path)}</div>
    <div class="motif-head">
      <span class="emblem" data-art="${m.letter}"></span>
      <div>
        <div class="motif-id"><span class="mid">${esc(m.id)}</span><button class="copy" type="button" title="Copy motif number and headline">copy</button></div>
        <h2>${esc(m.title)}</h2>
      </div>
    </div>
    ${m.note ? `<p class="note">${esc(m.note)}</p>` : ''}
    ${(m.alt_titles || []).length ? `<div class="alt">Also printed as: ${m.alt_titles.map(esc).join('; ')}</div>` : ''}

    ${Object.keys(regions).length ? `<section><h4>Attested in <span class="hint">${m.cultures.length} tradition${m.cultures.length === 1 ? '' : 's'}</span></h4>
      <div class="regions">${Object.entries(regions).map(([r, cs]) => `<div class="region"><span class="rname">${esc(r)}</span><span class="cul">${cs.map((c) => `<a class="chip" href="${searchHref({ culture: c })}">${esc(c)}</a>`).join('')}</span></div>`).join('')}</div></section>` : ''}

    ${(m.types || []).length ? `<section><h4>Tale types <span class="hint">Aarne–Thompson</span></h4><div class="types">${m.types.map((t) => `<a class="chip" href="${searchHref({ type: t })}">Type ${esc(t)}</a>`).join('')}</div></section>` : ''}

    ${refs ? `<section><h4>References</h4><div class="refs">${longRefs ? `<span class="short">${refsHTML(refs.slice(0, 520).replace(/\s\S*$/, ''))} …</span><details><summary>all references</summary>${refsHTML(refs)}</details>` : refsHTML(refs)}</div></section>` : ''}

    ${children.length ? `<section><h4>Subdivisions <span class="hint">${children.length}</span></h4>${mlist(children.slice(0, full ? 400 : 40), { ctx: false })}${!full && children.length > 40 ? `<a class="muted" href="${motifHref(m.id)}">all ${children.length} →</a>` : ''}</section>` : ''}

    ${(m.cf || []).length ? `<section><h4>Compare <span class="hint">Thompson’s cross-references</span></h4>${mlist(m.cf)}</section>` : ''}
    ${(m.cited_by || []).length ? `<section><h4>Referred to from</h4>${mlist(m.cited_by)}</section>` : ''}

    ${(m.echoes || []).length ? `<section><h4>Echoes elsewhere <span class="hint">similar motifs filed under other headings</span></h4>${mlist(m.echoes)}</section>` : ''}
    ${(m.kin || []).length ? `<section><h4>Close kin <span class="hint">nearby in meaning and place</span></h4>${mlist(m.kin)}</section>` : ''}

    ${m.prev || m.next ? `<nav class="sibnav">
      ${m.prev ? `<a class="prev" href="${motifHref(m.prev.id)}"><span class="dir">‹ previous</span><span class="mid">${esc(m.prev.id)}</span> ${esc(m.prev.title)}</a>` : '<span></span>'}
      ${m.next ? `<a class="next" href="${motifHref(m.next.id)}"><span class="dir">next ›</span><span class="mid">${esc(m.next.id)}</span> ${esc(m.next.title)}</a>` : ''}
    </nav>` : ''}`;
}

function wireMotif(root, m) {
  const copy = $('.copy', root);
  if (copy) copy.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(`${m.id}. ${m.title}`); toast('Copied ' + m.id); } catch (e) { toast('Could not copy'); }
  });
}

async function viewMotif(id) {
  main.innerHTML = `<div class="wrap motif-page"><div class="loading">${whorl()} opening ${esc(id)}…</div></div>`;
  hydrateArt(main);
  const m = await store.full(id);
  if (m.kind !== 'motif') { navigate(browseHref(m.id), { replace: true }); return; }
  document.title = `${m.id} ${trimDot(m.title)} · Spindle`;
  main.innerHTML = `<div class="wrap motif-page fade-in"><article class="leaf motif full">${corners()}${motifHTML(m, { full: true })}</article></div>`;
  wireMotif(main, m);
  const onKey = (e) => {
    if (e.target.matches('textarea, input')) return;
    if (e.key === 'ArrowLeft' && m.prev) navigate(motifHref(m.prev.id));
    if (e.key === 'ArrowRight' && m.next) navigate(motifHref(m.next.id));
  };
  document.addEventListener('keydown', onKey);
  return () => document.removeEventListener('keydown', onKey);
}

// --------------------------------------------------------------- browse

async function viewBrowse(id) {
  const ix = await store.index();
  document.title = 'Browse · Spindle';
  const letter = id ? id[0] : null;
  main.innerHTML = `<div class="wrap browse-page fade-in">
      <h1>Browse the index</h1>
      <nav class="browse-letters" aria-label="Branches">${LETTERS.map((L) => `<a href="${browseHref(L)}" title="${esc(ix.categories[L])}" ${L === letter ? 'aria-current="page"' : ''}>${L}</a>`).join('')}</nav>
      <div class="browse-body"></div></div>`;
  const body = $('.browse-body', main);
  const branches = await store.branches();
  if (!id) {
    body.innerHTML = `<p class="muted" style="font-style:italic;max-width:60ch">Thompson arranged the motifs in a tree: twenty-three lettered branches, divided into numbered sections and subdivided again and again, from the general (<span class="mid">D100</span> transformation: man to animal) to the particular (<span class="mid">D113.1.1</span> werwolf).</p>
      <div class="cats" style="margin-top:20px">${catsHTML(branches)}</div>`;
    return;
  }
  const node = await store.full(id);
  if (node.kind === 'motif' && !node.children.length) { navigate(motifHref(id), { replace: true }); return; }
  document.title = `${node.kind === 'category' ? node.id + '. ' : ''}${trimDot(node.title)} · Browse · Spindle`;
  const count = branches.find((b) => b.id === node.id)?.count;
  body.innerHTML = `
    ${node.path.length ? `<div class="motif"><div class="crumbs">${crumbsHTML(node.path)}</div></div>` : ''}
    <div class="browse-cat-head">
      <span class="emblem" data-art="${node.id[0]}"></span>
      <div>
        <div class="letter">${node.kind === 'category' ? node.id : `<span class="mid">${esc(node.id)}</span>`}</div>
        <h2 style="font-size:clamp(28px,4vw,40px)">${esc(trimDot(node.title))}</h2>
        <div class="muted">${node.kind === 'category' ? `${fmt(count)} motifs` : `${node.children.length} subdivision${node.children.length === 1 ? '' : 's'}`}
        ${node.kind === 'motif' ? ` · <a href="${motifHref(node.id)}">the motif itself →</a>` : ''}
        · <a href="${searchHref({ in: node.id })}">all motifs within</a></div>
      </div>
    </div>
    <ul class="outline">${node.children.map(outlineNode).join('')}</ul>`;
  // open the first level, so the page shows the shape of the branch at a glance
  if (node.kind !== 'motif' && node.children.length <= 16) {
    await Promise.all(node.children.filter((c) => c.n_children && c.n_children <= 40).map(async (c) => {
      const li = $(`li[data-id="${CSS.escape(c.id)}"]`, body);
      const sub = await store.full(c.id);
      const ul = document.createElement('ul');
      ul.innerHTML = sub.children.map(outlineNode).join('');
      li.append(ul);
      $('.tw', li).setAttribute('aria-expanded', 'true');
    }));
  }
  body.addEventListener('click', async (e) => {
    const tw = e.target.closest('.tw');
    if (!tw || tw.classList.contains('leafy')) return;
    const li = tw.closest('li');
    const open = tw.getAttribute('aria-expanded') === 'true';
    tw.setAttribute('aria-expanded', String(!open));
    let ul = $(':scope > ul', li);
    if (open) { ul?.remove(); return; }
    ul = document.createElement('ul');
    const sub = await store.full(li.dataset.id);
    ul.innerHTML = sub.children.map(outlineNode).join('');
    li.append(ul);
  });
}

function outlineNode(c) {
  const href = c.kind === 'section' ? browseHref(c.id) : motifHref(c.id);
  return `<li data-id="${esc(c.id)}"><div class="node ${c.kind}">
    <button class="tw ${c.n_children ? '' : 'leafy'}" type="button" aria-expanded="false" aria-label="Expand ${esc(c.id)}">▸</button>
    <a class="mid" href="${href}">${esc(c.id)}</a>
    <a class="t" href="${href}">${esc(trimDot(c.title))}</a>${c.n_children ? `<span class="cnt">${c.n_children}</span>` : ''}${c.has_note ? '<span class="dot" title="has an explanatory note">✶</span>' : ''}
  </div></li>`;
}

// ------------------------------------------------------------------ map

async function viewMap() {
  document.title = 'Map · Spindle';
  const ix = await store.index();
  main.innerHTML = `<div class="map-page">
    <canvas aria-label="Map of all motifs"></canvas>
    <div class="map-panel">
      <h1>A map of motifs</h1>
      <p>Each point is one of ${fmt(ix.n)} motifs, placed so that motifs alike in meaning lie together, whatever branch Thompson filed them under. Colour is the branch.</p>
      <form class="map-search"><input type="search" placeholder="Light up a theme: dragons, riddles…" aria-label="Highlight motifs on the map"></form>
      <div class="map-legend">${LETTERS.map((L) => `<button type="button" data-l="${L}" title="${esc(ix.categories[L])}"><i style="background:${CAT_COLORS[L]}"></i>${L} ${esc(SHORT[L])}</button>`).join('')}</div>
    </div>
    <div class="map-tip"></div>
    <div class="map-hint">scroll to zoom · drag to pan · click a point to open it</div>
    <div class="loading map-loading">${whorl()} unrolling the map…</div>
  </div>`;
  hydrateArt(main);
  const page = $('.map-page', main);
  const canvas = $('canvas', page);
  const tip = $('.map-tip', page);
  const { buf, rows } = await store.mapData();
  $('.map-loading', page).remove();
  const n = rows.length;
  const dv = new DataView(buf);
  const X = new Float32Array(n), Y = new Float32Array(n), C = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    X[i] = dv.getUint16(i * 5, true) / 65535;
    Y[i] = dv.getUint16(i * 5 + 2, true) / 65535;
    C[i] = dv.getUint8(i * 5 + 4);
  }
  const G = 128;
  const grid = Array.from({ length: G * G }, () => []);
  for (let i = 0; i < n; i++) grid[Math.min(G - 1, (Y[i] * G) | 0) * G + Math.min(G - 1, (X[i] * G) | 0)].push(i);

  const off = new Set();
  let hi = null, hover = -1;
  const view = { s: 1, tx: 0, ty: 0 };
  let W = 0, H = 0, dpr = 1;
  const pad = 40;
  const base = () => Math.min(W, H) - pad * 2;
  const toScreen = (x, y) => { const b = base(); return [(W - b) / 2 + x * b * view.s + view.tx, (H - b) / 2 + y * b * view.s + view.ty]; };
  const toWorld = (sx, sy) => { const b = base(); return [(sx - view.tx - (W - b) / 2) / (b * view.s), (sy - view.ty - (H - b) / 2) / (b * view.s)]; };
  const ctx = canvas.getContext('2d');
  const colors = LETTERS.map((L) => CAT_COLORS[L]);
  let raf = 0;
  function draw() {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      const css = getComputedStyle(document.documentElement);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.fillStyle = css.getPropertyValue('--paper');
      ctx.fillRect(0, 0, W, H);
      const r = Math.max(1.1, Math.min(4, 1.2 * Math.sqrt(view.s)));
      ctx.globalAlpha = hi ? 0.18 : 0.72;
      for (let c = 0; c < LETTERS.length; c++) {
        if (off.has(LETTERS[c])) continue;
        ctx.fillStyle = colors[c];
        ctx.beginPath();
        for (let i = 0; i < n; i++) {
          if (C[i] !== c) continue;
          const [sx, sy] = toScreen(X[i], Y[i]);
          if (sx < -5 || sy < -5 || sx > W + 5 || sy > H + 5) continue;
          ctx.rect(sx - r / 2, sy - r / 2, r, r);
        }
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      if (hi) {
        ctx.lineWidth = 1.5;
        hi.forEach((i, rank) => {
          const [sx, sy] = toScreen(X[i], Y[i]);
          ctx.strokeStyle = css.getPropertyValue('--ink');
          ctx.fillStyle = colors[C[i]];
          ctx.beginPath(); ctx.arc(sx, sy, rank < 10 ? 5 : 3.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        });
        ctx.font = '14px "EB Garamond", serif';
        // label the best hits, skipping any label that would overlap one already placed
        const placed = [];
        let shown = 0;
        for (const i of hi) {
          if (shown >= 10) break;
          const [sx, sy] = toScreen(X[i], Y[i]);
          const t = rows[i][1];
          const label = t.length > 44 ? t.slice(0, 42) + '…' : t;
          const w = ctx.measureText(label).width;
          const box = [sx + 8, sy - 10, sx + 12 + w, sy + 6];
          if (box[2] > W || placed.some((b) => !(box[2] < b[0] || box[0] > b[2] || box[3] < b[1] || box[1] > b[3]))) continue;
          placed.push(box);
          ctx.fillStyle = css.getPropertyValue('--card');
          ctx.globalAlpha = 0.85;
          ctx.fillRect(box[0] - 2, box[1], box[2] - box[0], box[3] - box[1]);
          ctx.globalAlpha = 1;
          ctx.fillStyle = css.getPropertyValue('--ink');
          ctx.fillText(label, sx + 9, sy + 3);
          shown++;
        }
      }
      if (hover >= 0) {
        const [sx, sy] = toScreen(X[hover], Y[hover]);
        ctx.strokeStyle = css.getPropertyValue('--red');
        ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(sx, sy, 7, 0, Math.PI * 2); ctx.stroke();
      }
    });
  }
  const resize = () => {
    dpr = window.devicePixelRatio || 1;
    W = page.clientWidth; H = page.clientHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    draw();
  };
  function nearest(sx, sy) {
    const [wx, wy] = toWorld(sx, sy);
    const gx = (wx * G) | 0, gy = (wy * G) | 0;
    let best = -1, bd = Infinity;
    const rad = Math.max(1, Math.ceil(2 / view.s));
    for (let y = gy - rad; y <= gy + rad; y++) for (let x = gx - rad; x <= gx + rad; x++) {
      if (x < 0 || y < 0 || x >= G || y >= G) continue;
      for (const i of grid[y * G + x]) {
        if (off.has(LETTERS[C[i]])) continue;
        const [px, py] = toScreen(X[i], Y[i]);
        const d = (px - sx) ** 2 + (py - sy) ** 2;
        if (d < bd) { bd = d; best = i; }
      }
    }
    return bd < 144 ? best : -1;
  }
  let drag = null;
  canvas.addEventListener('pointerdown', (e) => { drag = { x: e.clientX, y: e.clientY, tx: view.tx, ty: view.ty, moved: false }; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener('pointermove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
    if (drag) {
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
      view.tx = drag.tx + dx; view.ty = drag.ty + dy;
      tip.style.display = 'none';
      draw();
      return;
    }
    const i = nearest(sx, sy);
    if (i !== hover) { hover = i; draw(); }
    if (i >= 0) {
      tip.innerHTML = `<span class="mid">${esc(rows[i][0])}</span>${esc(rows[i][1])}`;
      tip.style.display = 'block';
      tip.style.left = Math.min(W - tip.offsetWidth - 10, sx + 14) + 'px';
      tip.style.top = (sy + 14) + 'px';
    } else tip.style.display = 'none';
  });
  canvas.addEventListener('pointerup', () => {
    const wasDrag = drag?.moved;
    drag = null;
    if (!wasDrag && hover >= 0) navigate(motifHref(rows[hover][0]));
  });
  canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
    const [wx, wy] = toWorld(sx, sy);
    view.s = Math.min(60, Math.max(0.7, view.s * Math.exp(-e.deltaY * 0.0015)));
    const [nx, ny] = toScreen(wx, wy);
    view.tx += sx - nx; view.ty += sy - ny;
    draw();
  }, { passive: false });
  $('.map-legend', page).addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    const L = b.dataset.l;
    if (e.altKey || e.metaKey) {
      const solo = off.size === LETTERS.length - 1 && !off.has(L);
      off.clear();
      if (!solo) LETTERS.forEach((x) => x !== L && off.add(x));
    } else if (off.has(L)) off.delete(L);
    else off.add(L);
    $$('.map-legend button', page).forEach((x) => x.classList.toggle('off', off.has(x.dataset.l)));
    draw();
  });
  const input = $('.map-search input', page);
  input.addEventListener('focus', store.warm, { once: true });
  $('.map-search', page).addEventListener('submit', async (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) { hi = null; draw(); return; }
    input.disabled = true;
    try {
      const d = await store.search(q, { k: 150 });
      hi = d.results.map((r) => ix.row.get(r.id)).filter((i) => i != null);
    } finally { input.disabled = false; input.focus(); }
    if (hi.length) {
      const top = hi.slice(0, 15);
      const cx = top.reduce((s, i) => s + X[i], 0) / top.length, cy = top.reduce((s, i) => s + Y[i], 0) / top.length;
      view.s = Math.max(view.s, 2.5);
      const [sx, sy] = toScreen(cx, cy);
      view.tx += W / 2 - sx; view.ty += H / 2 - sy;
    }
    draw();
  });
  input.addEventListener('input', (e) => { if (!e.target.value) { hi = null; draw(); } });
  const ro = new ResizeObserver(resize);
  ro.observe(page);
  window.addEventListener('themechange', draw);
  const mq = matchMedia('(prefers-color-scheme: dark)');
  mq.addEventListener('change', draw);
  resize();
  return () => { ro.disconnect(); window.removeEventListener('themechange', draw); mq.removeEventListener('change', draw); };
}

// ---------------------------------------------------------------- about

async function viewAbout() {
  document.title = 'About · Spindle';
  const ix = await store.index();
  main.innerHTML = `<article class="wrap about fade-in">
    <h1>About Spindle</h1>
    <p>Stith Thompson’s <i>Motif-Index of Folk-Literature</i> (1932–36; revised and enlarged 1955–58) classifies the recurring elements of traditional narrative — the swan maiden, the forbidden chamber, the trickster who feigns death — into a tree of some ${fmt(ix.n)} numbered motifs, each with a trail of references to the collections where it occurs. It remains the common language of folk-narrative research, and it remains hard to search: a motif is found only if one guesses Thompson’s wording, or the branch he filed it under.</p>
    <p>Spindle searches it by meaning. It is a successor to MOMFER, the <i>Meertens Online Motif FindER</i> (Karsdorp, Van der Meulen, Meder &amp; Van den Bosch, <a href="https://doi.org/10.1080/0015587X.2015.1006954"><i>Folklore</i> 126 (2015)</a>), which matched words and expanded them through WordNet. Spindle compares meanings directly, and does so entirely in your browser: there is no server.</p>
    <p>The mole on the hill below the tree of tales is for MOMFER, whose name also belonged to Momfer de Mol of <i>De Fabeltjeskrant</i>.</p>

    <h2>How it works</h2>
    <ul>
      <li><b>Text.</b> The index was re-parsed from the HTML edition at ruthenia.ru, the fullest digital transcription of the revised edition, keeping each motif’s headline, explanatory note and references apart. A character-encoding fault that had turned <i>Métraux</i> into <i>Mйtraux</i> throughout was reversed.</li>
      <li><b>Tree.</b> Every motif is placed under its parent: the dotted subdivisions under their stems, the numbered motifs under Thompson’s own section headings (e.g. <span class="mid">D100–D199</span> <i>Transformation: man to animal</i>).</li>
      <li><b>Traditions.</b> The labels in the references (“Irish myth:”, “India:”, “N. A. Indian (Zuñi):”) are normalised into ${fmt(ix.meta.cultures.length)} traditions in ${ix.meta.regions.length} broad regions, so that results can be filtered by where a motif is attested.</li>
      <li><b>Meaning.</b> Every motif’s headline and note were embedded with the sentence encoder <code>bge-base-en-v1.5</code> and stored compactly (256 dimensions, one byte each). When you search, your browser downloads the same encoder once (about 110 MB, then cached), embeds your description, and compares it with all motifs in a few milliseconds. For one- and two-word queries exact word matches count for a little more, and a name found in no headline is looked up in the references — which is how <a href="${searchHref({ q: 'Melusine' })}">Melusine</a> finds the Melusine tabu.</li>
      <li><b>Echoes.</b> On every motif page, Spindle lists the most similar motifs that Thompson filed in other branches — the duplications and near-duplications he himself acknowledged (<a href="${motifHref('D1645.9')}">D1645.9</a> and <a href="${motifHref('F718.5')}">F718.5</a>), and many he did not.</li>
    </ul>

    <h2>How well it works</h2>
    <p>Forty test queries, written before either system was run on them: twenty plain-language descriptions (“a man trades his soul for riches”) and twenty short keyword searches (“flying carpet”), each with the motifs a folklorist would accept. MOMFER’s search was reconstructed from its source code for the comparison.</p>
    <table>
      <tr><th></th><th>right motif first</th><th>right motif in the top ten</th></tr>
      <tr><td>Spindle, descriptions</td><td>50%</td><td>95%</td></tr>
      <tr><td>MOMFER, descriptions</td><td>45%</td><td>60%</td></tr>
      <tr><td>Spindle, keywords</td><td>70%</td><td>100%</td></tr>
      <tr><td>MOMFER, keywords</td><td>65%</td><td>80%</td></tr>
    </table>
    <p>Where both find the motif they often put it first; the difference is in how rarely Spindle misses altogether — “werewolf” when Thompson wrote <i>werwolf</i>, “the trickster gets stuck to a figure covered in tar” for the tar-baby. Forty queries is a small sample: treat the results as a well-read colleague’s suggestions, and check the index.</p>

    <h2>Searching</h2>
    <table>
      <tr><th>Type</th><th>Does</th></tr>
      <tr><td><code>a girl must not look back</code></td><td>search by meaning</td></tr>
      <tr><td><code>D1960.3</code></td><td>open a motif by number (and list its subdivisions)</td></tr>
      <tr><td><code>dragon in:B</code></td><td>search within a branch, section or motif</td></tr>
      <tr><td><code>trickster culture:Irish</code></td><td>only motifs attested in a tradition</td></tr>
      <tr><td><code>ogre region:"South Asia"</code></td><td>only motifs attested in a region</td></tr>
      <tr><td><code>type:510</code></td><td>motifs referring to a tale type (510, 510A, 510B …)</td></tr>
    </table>
    <p>In references, Thompson’s asterisk marks a reference with further bibliography, the double asterisk an especially full treatment.</p>
  </article>`;
}

hydrateArt(document);
render();
