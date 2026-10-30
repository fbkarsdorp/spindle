// Spindle — front end of the static site. Plain ES modules, no build step.

import * as store from './store.js';
import * as lists from './lists.js';
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
function toast(msg, action = null) {
  const t = $('.toast');
  t.textContent = msg;
  if (action) {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = action.label;
    b.addEventListener('click', () => { action.run(); t.classList.remove('show'); });
    t.append(' ', b);
  }
  t.classList.toggle('has-action', !!action);
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), action ? 5000 : 2200);
}

// ------------------------------------------------------------ motif lists

// a ＋ that puts a motif on the current list, or takes it off again
const addBtn = (id, { mini = true } = {}) => {
  const on = lists.has(id);
  return `<button type="button" class="add${mini ? ' mini' : ''}" data-add="${esc(id)}" aria-pressed="${on}"
    aria-label="${on ? 'Remove' : 'Add'} ${esc(id)} ${on ? 'from' : 'to'} your list" title="${on ? 'On your list' : 'Add to your list'}">${mini ? '' : `<span>${on ? 'on your list' : 'add to list'}</span>`}</button>`;
};
function toggleOnList(id) {
  const r = lists.toggle(id);
  if (r.added) toast(`Added ${id} to ${lists.current().title ? `“${lists.current().title}”` : 'your list'}`);
  else toast(`Took ${id} off your list`, { label: 'Undo', run: () => lists.restore(r.item, r.index) });
}
document.addEventListener('click', (e) => {
  const b = e.target.closest('[data-add]');
  if (!b) return;
  e.preventDefault();
  e.stopPropagation();
  toggleOnList(b.dataset.add);
}, true);
function refreshLists() {
  const n = lists.count();
  $('.nav .list-count').textContent = n ? String(n) : '';
  for (const b of $$('[data-add]')) {
    const on = lists.has(b.dataset.add);
    b.setAttribute('aria-pressed', String(on));
    b.setAttribute('aria-label', `${on ? 'Remove' : 'Add'} ${b.dataset.add} ${on ? 'from' : 'to'} your list`);
    b.title = on ? 'On your list' : 'Add to your list';
    const label = $('span', b);
    if (label) label.textContent = on ? 'on your list' : 'add to list';
  }
}
lists.onChange(refreshLists);

// ---------------------------------------------------------------- router

const routes = [
  [/^\/$/, viewHome],
  [/^\/search\/?$/, viewSearch],
  [/^\/motif\/(.+)$/, viewMotif],
  [/^\/browse\/?$/, viewBrowse],
  [/^\/browse\/(.+)$/, viewBrowse],
  [/^\/map\/?$/, () => navigate(go('/atlas'), { replace: true })], // the meaning map, retired
  [/^\/atlas\/?$/, viewAtlas],
  [/^\/list\/?$/, viewList],
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
            <div class="way"><span class="num">iii</span><div><h3><a href="${go('/atlas')}">Travel</a></h3><p>See where Thompson’s sources tell a motif, on a papercut map of the world.</p></div></div>
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
      ${q && res.length && res[0].via === 'meaning' ? `<a class="atlas-link" href="${go('/atlas?' + new URLSearchParams({ q }))}">where are these told?</a>` : ''}
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
    if (e.key === 'a' && current && !e.metaKey && !e.ctrlKey) { toggleOnList(current); return; }
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
    <li class="result-li">${addBtn(r.id)}<a class="result" data-id="${esc(r.id)}" href="${motifHref(r.id)}">
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
      <span>${addBtn(x.id)}<a href="${motifHref(x.id)}">${esc(x.title)}</a>${x.n_children ? `<span class="more">+${x.n_children}</span>` : ''}
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
        <div class="motif-id"><span class="mid">${esc(m.id)}</span><button class="copy" type="button" title="Copy motif number and headline">copy</button>${addBtn(m.id, { mini: false })}</div>
        <h2>${esc(m.title)}</h2>
      </div>
    </div>
    ${m.note ? `<p class="note">${esc(m.note)}</p>` : ''}
    ${m.reading ? `<p class="reading"><span class="reading-label" title="Written by a language model (Claude Haiku) to help search; not Thompson’s words">In plain words</span> ${esc(m.reading)}</p>` : ''}
    ${(m.alt_titles || []).length ? `<div class="alt">Also printed as: ${m.alt_titles.map(esc).join('; ')}</div>` : ''}

    ${Object.keys(regions).length ? `<section><h4>Attested in <span class="hint">${m.cultures.length} tradition${m.cultures.length === 1 ? '' : 's'}</span></h4>
      <div class="regions">${Object.entries(regions).map(([r, cs]) => `<div class="region"><span class="rname">${esc(r)}</span><span class="cul">${cs.map((c) => `<a class="chip" href="${searchHref({ culture: c })}">${esc(c)}</a>`).join('')}</span></div>`).join('')}</div></section>` : ''}

    <section class="where-map" hidden><h4>On the map <span class="hint"></span></h4><div class="minimap"></div></section>

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
  whereMap(root, m);
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

// ---------------------------------------------------------------- atlas

const KIND_NOTE = {
  b: 'A broad label Thompson uses for a whole region; drawn as a wash, not a point.',
  t: 'A written or religious tradition rather than a place; set at its historical centre and drawn as a ring.',
};
const discPx = (n) => 2.4 + 0.27 * Math.sqrt(n);

async function figuresSVG(geo) {
  const parts = await Promise.all(geo.figures.map(async ([name, x, y, w]) => {
    const svg = (await art(name)).replace(/<\?xml[^>]*>/, '');
    const vb = (svg.match(/viewBox="([^"]+)"/) || [])[1];
    if (!vb) return '';
    const [, , vw, vh] = vb.split(/\s+/).map(Number);
    const h = (w * vh) / vw;
    return svg.replace('<svg ', `<svg class="fig" aria-hidden="true" x="${x - w / 2}" y="${y - h / 2}" width="${w}" height="${h}" `);
  }));
  return parts.join('');
}

// the sea, the graticule and the land, cut from paper: a shadow, then the sheet itself
function baseSVG(geo, id) {
  return `<defs><clipPath id="${id}"><path d="${geo.sheet}"/></clipPath></defs>
    <path class="sea" d="${geo.sheet}"/>
    <g clip-path="url(#${id})">
      <path class="grat" d="${geo.grat}"/>
      <path class="land-shadow" d="${geo.land}" transform="translate(.9 1.3)"/>
      <path class="land" d="${geo.land}"/>
    </g>
    <path class="sheet-edge" d="${geo.sheet}"/>`;
}

// one disc: its shadow, then the cut-paper disc in the style of its kind
const discSVG = (p, r, u, extra = '') => `<circle class="dshadow" cx="${p.x + 0.5 * u}" cy="${p.y + 0.8 * u}" r="${r}"/>` +
  `<circle class="disc k-${p.kind}${extra}" data-i="${p.i}" cx="${p.x}" cy="${p.y}" r="${r}"/>`;

async function whereMap(root, m) {
  const sec = $('.where-map', root);
  if (!sec) return;
  const { at, own, below } = await store.motifPlaces(m.id);
  const keys = new Set([...own.keys(), ...below.keys()]);
  if (!keys.size || !sec.isConnected) return;
  const { geo, places } = at;
  // frame the places, at least a third of the world wide, in the box's proportions
  const pts = [...keys].map((i) => places[i]);
  const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
  const aspect = 2.2;
  let w = Math.max(geo.w / 3, Math.max(...xs) - Math.min(...xs) + 80), h = Math.max(...ys) - Math.min(...ys) + 60;
  if (w / h < aspect) w = h * aspect; else h = w / aspect;
  const cx = (Math.max(...xs) + Math.min(...xs)) / 2, cy = (Math.max(...ys) + Math.min(...ys)) / 2;
  const u = w / 640; // map units per pixel at the usual width
  const order = pts.sort((a, b) => (below.get(b.i) || 0) - (below.get(a.i) || 0));
  const discs = order.map((p) => discSVG(p, (own.has(p.i) ? 5.5 : 2.6 + 0.9 * Math.sqrt(below.get(p.i))) * u, u, own.has(p.i) ? ' own' : ' below')).join('');
  const n = keys.size;
  $('h4 .hint', sec).textContent = `${n} place${n === 1 ? '' : 's'}`;
  $('.minimap', sec).innerHTML = `
    <a class="minimap-map" href="${go('/atlas?' + new URLSearchParams({ place: pts.length === 1 ? pts[0].key : order[0].key }))}" aria-label="Open in the atlas">
      <svg class="atlas mini" viewBox="${cx - w / 2} ${cy - h / 2} ${w} ${h}" role="img" aria-label="Map of where this motif is attested">${baseSVG(geo, 'mini-sheet')}<g>${discs}</g></svg></a>
    <div class="minimap-key">
      ${own.size ? '<span><i class="key own"></i>its own traditions</span>' : ''}
      ${below.size ? `<span><i class="key below"></i>traditions of the motifs filed under it</span>` : ''}
      <a href="${go('/atlas?' + new URLSearchParams({ place: order[0].key }))}">open the atlas →</a>
    </div>`;
  sec.hidden = false;
}

async function viewAtlas() {
  const params = route().params;
  const state = { q: params.get('q') || '', branch: params.get('in') || '', place: params.get('place') || '' };
  document.title = 'Atlas · Spindle';
  main.innerHTML = `<div class="wrap atlas-page fade-in">
    <div class="atlas-main">
      <header class="atlas-head">
        <h1>Atlas</h1>
        <p class="lede">Where Thompson’s sources tell each motif. Every disc is a tradition his references name — the Ekoi, the Tuamotu islanders, Iceland — sized by how many motifs cite it.</p>
      </header>
      <div class="atlas-map">
        <div class="loading map-loading">${whorl()} unfolding the atlas…</div>
        <div class="atlas-zoom"><button type="button" data-z="in" aria-label="Zoom in">+</button><button type="button" data-z="out" aria-label="Zoom out">−</button><button type="button" data-z="reset" aria-label="Show the whole world">⟲</button></div>
        <div class="map-tip"></div>
      </div>
      <div class="atlas-notes">
        <div class="atlas-key">
          <span><svg viewBox="-6 -6 12 12"><circle class="disc k-p" r="5"/></svg>a people or place</span>
          <span><svg viewBox="-6 -6 12 12"><circle class="disc k-b" r="5"/></svg>a whole region (“African”, “Polynesian”)</span>
          <span><svg viewBox="-6 -6 12 12"><circle class="disc k-t" r="4.2"/></svg>a written or religious tradition (“Jewish”, “Italian Novella”)</span>
        </div>
        <p>This is a map of Thompson’s library, not of the world’s storytelling. India, Ireland and Iceland loom large because he drew on rich collections from them — Indian story books, the Irish myth index of Cross, the Icelandic sagas — while whole continents are known to the index through a handful of books. A motif with no disc somewhere is not absent there; Thompson simply had no source for it.</p>
        <p class="muted">Coastlines from Natural Earth. Places are approximate: where the tales were collected, as Thompson’s sources describe it.</p>
      </div>
    </div>
    <aside class="atlas-panel">
      <form class="atlas-search"><input type="search" placeholder="Where is it told? e.g. a dragon guards a treasure" aria-label="Find where a motif is told" value="${esc(state.q)}"></form>
      <select class="atlas-branch" aria-label="Branch of the index"><option value="">All branches</option></select>
      <div class="atlas-detail" aria-live="polite"></div>
    </aside>
  </div>`;
  hydrateArt(main);
  const page = $('.atlas-page', main);
  const box = $('.atlas-map', page), panel = $('.atlas-detail', page), tip = $('.map-tip', page);
  const [ix, at] = await Promise.all([store.index(), store.atlas()]);
  const { geo, places } = at;
  box.style.setProperty('--ar', `${geo.w} / ${geo.h}`);
  $('.atlas-branch', page).insertAdjacentHTML('beforeend', LETTERS.map((L) => `<option value="${L}"${state.branch === L ? ' selected' : ''}>${L} · ${esc(ix.categories[L])}</option>`).join(''));
  box.insertAdjacentHTML('afterbegin', `<svg class="atlas" role="img" aria-label="World map of the traditions Thompson cites">
    ${baseSVG(geo, 'atlas-sheet')}<g class="figs">${await figuresSVG(geo)}</g><g class="discs"></g><circle class="sel-ring" r="0"/><g class="labels" aria-hidden="true"></g></svg>`);
  $('.map-loading', box).remove();
  const svg = $('svg.atlas', box);
  const gDiscs = $('.discs', svg), gLabels = $('.labels', svg), ring = $('.sel-ring', svg);

  // ------------------------------------------------------------ counts
  let matched = null, counts = [], total = 0;
  const inScope = (row) => (!state.branch || ix.rows[row][0][0] === state.branch) && (!matched || matched.has(row));
  function recount() {
    counts = places.map((p) => p.rows.reduce((a, r) => a + inScope(r), 0));
    total = ix.rows.reduce((a, _, r) => a + inScope(r), 0);
  }

  // -------------------------------------------------------------- view
  const view = { x: geo.w / 2, y: geo.h / 2, z: 1 };
  let cw = 1, ch = 1, s0 = 1;
  const scale = () => s0 * view.z;
  function clampView() {
    const s = scale(), hw = cw / (2 * s), hh = ch / (2 * s);
    view.x = hw * 2 >= geo.w ? geo.w / 2 : Math.min(geo.w - hw, Math.max(hw, view.x));
    view.y = hh * 2 >= geo.h ? geo.h / 2 : Math.min(geo.h - hh, Math.max(hh, view.y));
  }
  let raf = 0;
  function draw() {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      clampView();
      const s = scale(), u = 1 / s;
      svg.setAttribute('viewBox', `${view.x - cw / (2 * s)} ${view.y - ch / (2 * s)} ${cw / s} ${ch / s}`);
      svg.style.setProperty('--u', u);
      const shrink = Math.min(1, Math.max(0.6, cw / 1000));
      for (const el of gDiscs.querySelectorAll('circle')) {
        const n = +el.dataset.n;
        const r = discPx(n) * shrink * u;
        el.setAttribute('r', r);
        if (el.classList.contains('dshadow')) { el.setAttribute('cx', +el.dataset.x + 0.5 * u); el.setAttribute('cy', +el.dataset.y + 0.8 * u); }
      }
      const sel = state.place && at.byKey.get(state.place);
      ring.setAttribute('r', sel ? (discPx(counts[sel.i] || 0) * shrink + 4) * u : 0);
      if (sel) { ring.setAttribute('cx', sel.x); ring.setAttribute('cy', sel.y); }
      labels(s, shrink);
    });
  }
  function drawDiscs() {
    const order = places.filter((p) => counts[p.i] > 0).sort((a, b) => counts[b.i] - counts[a.i]);
    gDiscs.innerHTML = order.map((p) => {
      const n = counts[p.i];
      return `<circle class="dshadow" data-n="${n}" data-x="${p.x}" data-y="${p.y}" cx="${p.x}" cy="${p.y}" r="0"/>` +
        `<circle class="disc k-${p.kind}" data-i="${p.i}" data-n="${n}" cx="${p.x}" cy="${p.y}" r="0"/>`;
    }).join('');
    draw();
  }
  // name the biggest discs in view, skipping any name that would collide
  function labels(s, shrink) {
    const x0 = view.x - cw / (2 * s), y0 = view.y - ch / (2 * s);
    const placed = [];
    const out = [];
    const cand = places.filter((p) => counts[p.i] > 0).sort((a, b) => counts[b.i] - counts[a.i]);
    for (const p of cand) {
      if (out.length >= 26) break;
      const sx = (p.x - x0) * s, sy = (p.y - y0) * s;
      if (sx < 0 || sy < 0 || sx > cw || sy > ch) continue;
      const r = discPx(counts[p.i]) * shrink;
      const w = p.name.length * 6.6 + 4;
      const b = [sx + r + 2, sy - 8, sx + r + 4 + w, sy + 7];
      if (b[2] > cw) { b[0] = sx - r - 4 - w; b[2] = sx - r - 2; }
      if (placed.some((q) => !(b[2] < q[0] || b[0] > q[2] || b[3] < q[1] || b[1] > q[3]))) continue;
      placed.push(b);
      out.push(`<text x="${x0 + b[0] / s}" y="${y0 + (sy + 4.5) / s}">${esc(p.name)}</text>`);
    }
    gLabels.innerHTML = out.join('');
  }
  const resize = () => {
    cw = box.clientWidth; ch = box.clientHeight;
    s0 = Math.max(cw / geo.w, ch / geo.h);
    draw();
  };

  // ------------------------------------------------------------- panel
  function sync() {
    const p = new URLSearchParams();
    if (state.q) p.set('q', state.q);
    if (state.branch) p.set('in', state.branch);
    if (state.place) p.set('place', state.place);
    history.replaceState(null, '', go('/atlas' + (p.toString() ? '?' + p : '')));
  }
  const scopeText = () => [state.branch ? `in ${state.branch} · ${esc(ix.categories[state.branch])}` : '', matched ? `among the ${matched.size} closest matches to <i>${esc(state.q)}</i>` : ''].filter(Boolean).join(', ');
  function overview() {
    const top = places.filter((p) => counts[p.i] > 0).sort((a, b) => counts[b.i] - counts[a.i]);
    const max = counts[top[0]?.i] || 1;
    const placedRows = new Set(top.flatMap((p) => p.rows.filter(inScope)));
    panel.innerHTML = `
      <h2>${matched ? 'Where it is told' : 'Most cited'}</h2>
      <p class="muted scope">${top.length ? `${fmt(top.length)} places${scopeText() ? ', ' + scopeText() : ''}. ${total - placedRows.size ? `${fmt(total - placedRows.size)} of ${fmt(total)} motifs name no tradition.` : ''}` : 'No motif here names a tradition.'}</p>
      <ol class="place-list">${top.slice(0, 40).map((p) => `<li><button type="button" data-key="${esc(p.key)}">
        <span class="pname">${esc(p.name)}${p.kind !== 'p' ? ` <span class="pkind">${p.kind === 'b' ? 'region' : 'tradition'}</span>` : ''}</span>
        <span class="n">${fmt(counts[p.i])}</span><i style="width:${(100 * counts[p.i]) / max}%"></i></button></li>`).join('')}</ol>`;
  }
  function detail(p) {
    const rows = p.rows.filter(inScope);
    const byL = new Map();
    for (const r of rows) { const L = ix.rows[r][0][0]; if (!byL.has(L)) byL.set(L, []); byL.get(L).push(r); }
    const ls = [...byL.entries()].sort((a, b) => b[1].length - a[1].length);
    const max = ls[0]?.[1].length || 1;
    panel.innerHTML = `
      <button type="button" class="back">← all places</button>
      <h2>${esc(p.name)}</h2>
      ${KIND_NOTE[p.kind] ? `<p class="kind-note">${KIND_NOTE[p.kind]}</p>` : ''}
      <p class="scope"><b>${fmt(rows.length)}</b> motif${rows.length === 1 ? '' : 's'} cite it${scopeText() ? ', ' + scopeText() : ''}.</p>
      <p class="labels-line"><span class="muted">Thompson’s label${p.labels.length === 1 ? '' : 's'}:</span> ${p.labels.slice(0, 8).map((l) => `<a class="chip" href="${searchHref({ culture: l })}" title="Search within these motifs">${esc(l)}</a>`).join(' ')}${p.labels.length > 8 ? ` <span class="muted">and ${p.labels.length - 8} more</span>` : ''}</p>
      <div class="br-list">${ls.map(([L, rs]) => `
        <div class="br"><button type="button" class="br-head" data-l="${L}" aria-expanded="false">
          <span class="fart" data-art="${L}"></span><span class="bname">${L} · ${esc(SHORT[L])}</span><span class="n">${fmt(rs.length)}</span><i style="width:${(100 * rs.length) / max}%"></i></button>
          <div class="br-motifs" hidden></div></div>`).join('')}</div>`;
    hydrateArt(panel);
    panel._byL = byL;
  }
  function renderPanel() {
    const p = state.place && at.byKey.get(state.place);
    if (p) detail(p); else overview();
  }
  function motifRows(list, from) {
    return list.slice(from, from + 50).map((r) => `<li>${addBtn(ix.rows[r][0])}<a class="mid" href="${motifHref(ix.rows[r][0])}">${esc(ix.rows[r][0])}</a> <a href="${motifHref(ix.rows[r][0])}">${esc(ix.rows[r][1])}</a></li>`).join('');
  }
  panel.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.key) { select(b.dataset.key, { centre: true }); return; }
    if (b.classList.contains('back')) { select(''); return; }
    if (b.classList.contains('br-head')) {
      const list = b.nextElementSibling;
      const open = b.getAttribute('aria-expanded') !== 'true';
      b.setAttribute('aria-expanded', String(open));
      if (open && !list.innerHTML) {
        const rs = [...panel._byL.get(b.dataset.l)].sort(matched ? (x, y) => matched.get(x) - matched.get(y) : (x, y) => (ix.rows[x][0] < ix.rows[y][0] ? -1 : 1));
        list.innerHTML = `<ul class="mlist plain">${motifRows(rs, 0)}</ul>${rs.length > 50 ? `<button type="button" class="facet-more" data-from="50">${fmt(rs.length - 50)} more…</button>` : ''}`;
        list._rows = rs;
      }
      list.hidden = !open;
      return;
    }
    if (b.dataset.from) {
      const list = b.closest('.br-motifs');
      const from = +b.dataset.from;
      $('ul', list).insertAdjacentHTML('beforeend', motifRows(list._rows, from));
      if (from + 50 < list._rows.length) { b.dataset.from = from + 50; b.textContent = `${fmt(list._rows.length - from - 50)} more…`; } else b.remove();
    }
  });
  function select(key, { centre = false } = {}) {
    state.place = key;
    sync();
    renderPanel();
    const p = key && at.byKey.get(key);
    if (p && centre) { view.x = p.x; view.y = p.y; view.z = Math.max(view.z, 2.2); }
    draw();
    if (p && !matchMedia('(min-width: 1001px)').matches) panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // ------------------------------------------------------- interaction
  const pointers = new Map();
  let drag = null, pinch = null;
  svg.addEventListener('pointerdown', (e) => {
    pointers.set(e.pointerId, [e.clientX, e.clientY]);
    svg.setPointerCapture(e.pointerId);
    if (pointers.size === 1) drag = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false };
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), z: view.z };
      drag = null;
    }
  });
  svg.addEventListener('pointermove', (e) => {
    if (pointers.has(e.pointerId)) pointers.set(e.pointerId, [e.clientX, e.clientY]);
    if (pinch && pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      view.z = Math.min(14, Math.max(1, pinch.z * Math.hypot(a[0] - b[0], a[1] - b[1]) / pinch.d));
      draw();
      return;
    }
    if (drag && pointers.size === 1) {
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
      if (drag.moved) {
        view.x = drag.vx - dx / scale(); view.y = drag.vy - dy / scale();
        tip.style.display = 'none';
        draw();
        return;
      }
    }
    const c = e.target.closest?.('.disc');
    if (c) {
      const p = places[+c.dataset.i];
      const rect = box.getBoundingClientRect();
      tip.innerHTML = `<b>${esc(p.name)}</b><span class="muted"> · ${fmt(counts[p.i])} motif${counts[p.i] === 1 ? '' : 's'}</span>`;
      tip.style.display = 'block';
      tip.style.left = Math.min(rect.width - tip.offsetWidth - 8, e.clientX - rect.left + 14) + 'px';
      tip.style.top = (e.clientY - rect.top + 14) + 'px';
    } else tip.style.display = 'none';
  });
  const up = (e) => {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch = null;
    if (drag && !drag.moved && pointers.size === 0) {
      const c = e.target.closest?.('.disc');
      if (c) select(places[+c.dataset.i].key);
    }
    if (pointers.size === 0) drag = null;
  };
  svg.addEventListener('pointerup', up);
  svg.addEventListener('pointercancel', up);
  svg.addEventListener('pointerleave', () => { tip.style.display = 'none'; });
  svg.addEventListener('wheel', (e) => {
    e.preventDefault();
    const rect = svg.getBoundingClientRect();
    const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
    const s = scale();
    const wx = view.x - cw / (2 * s) + sx / s, wy = view.y - ch / (2 * s) + sy / s;
    view.z = Math.min(14, Math.max(1, view.z * Math.exp(-e.deltaY * 0.0015)));
    const s2 = scale();
    view.x = wx - sx / s2 + cw / (2 * s2); view.y = wy - sy / s2 + ch / (2 * s2);
    draw();
  }, { passive: false });
  $('.atlas-zoom', box).addEventListener('click', (e) => {
    const z = e.target.closest('button')?.dataset.z;
    if (z === 'in') view.z = Math.min(14, view.z * 1.6);
    if (z === 'out') view.z = Math.max(1, view.z / 1.6);
    if (z === 'reset') { view.z = 1; view.x = geo.w / 2; view.y = geo.h / 2; }
    draw();
  });
  $('.atlas-branch', page).addEventListener('change', (e) => {
    state.branch = e.target.value;
    sync(); recount(); drawDiscs(); renderPanel();
  });
  const input = $('.atlas-search input', page);
  input.addEventListener('focus', store.warm, { once: true });
  let stopModel = null;
  async function runQuery() {
    if (!state.q) { matched = null; recount(); drawDiscs(); renderPanel(); return; }
    panel.innerHTML = `<div class="loading">${whorl()} <span class="msg">searching the index…</span></div>`;
    hydrateArt(panel);
    stopModel?.();
    stopModel = store.onModel((m) => {
      const msg = $('.loading .msg', panel);
      if (msg && m.status === 'loading') msg.textContent = 'loading the language model — once, then searches take a moment…';
    });
    try {
      // the same sixty the search page shows; further down the list, matches thin out
      // into motifs that only crowd the places Thompson had most sources for
      const d = await store.search(state.q, { k: 60 });
      matched = new Map(d.results.map((r, k) => [ix.row.get(r.id), k]).filter(([i]) => i != null));
    } catch (err) {
      panel.innerHTML = `<p class="muted">${esc(err.message)}</p>`;
      return;
    } finally { stopModel?.(); stopModel = null; }
    recount(); drawDiscs(); renderPanel();
  }
  $('.atlas-search', page).addEventListener('submit', (e) => {
    e.preventDefault();
    state.q = input.value.trim();
    sync();
    runQuery();
  });
  input.addEventListener('input', () => { if (!input.value && state.q) { state.q = ''; sync(); runQuery(); } });

  const ro = new ResizeObserver(resize);
  ro.observe(box);
  resize();
  recount();
  drawDiscs();
  const first = state.place && at.byKey.get(state.place);
  if (first) { view.x = first.x; view.y = first.y; view.z = 2.2; }
  renderPanel();
  if (state.q) runQuery();
  return () => { ro.disconnect(); stopModel?.(); };
}

// ----------------------------------------------------------------- list

const FORMATS = [
  ['numbers', 'Numbers', 'D1975; H481.1 — for a footnote or a tale’s motif line'],
  ['lines', 'With headlines', 'one motif per line, with Thompson’s headline and your note'],
  ['table', 'Table', 'tab-separated: pastes into a spreadsheet'],
];
const slug = (s) => (s || 'motifs').toLowerCase().normalize('NFKD').replace(/[^\w]+/g, '-').replace(/^-|-$/g, '').slice(0, 60) || 'motifs';

function exportText(ix, items, fmt) {
  const info = (id) => {
    const i = ix.row.get(id);
    return i == null ? { title: '', branch: '' } : { title: ix.rows[i][1], branch: `${id[0]}. ${ix.categories[id[0]] || ''}` };
  };
  if (fmt === 'numbers') return items.map((x) => x.id).join('; ');
  if (fmt === 'lines') return items.map((x) => `${x.id} ${info(x.id).title}${x.note ? ` — ${x.note}` : ''}`).join('\n');
  const cell = (v) => String(v || '').replace(/[\t\n]+/g, ' ');
  return ['Motif\tHeadline\tBranch\tNote', ...items.map((x) => { const f = info(x.id); return [x.id, f.title, f.branch, x.note].map(cell).join('\t'); })].join('\n');
}

function csv(ix, items) {
  const q = (v) => `"${String(v || '').replace(/"/g, '""')}"`;
  const rows = items.map((x) => {
    const i = ix.row.get(x.id);
    return [x.id, i == null ? '' : ix.rows[i][1], `${x.id[0]}. ${ix.categories[x.id[0]] || ''}`, x.note].map(q).join(',');
  });
  return '﻿' + ['Motif,Headline,Branch,Note', ...rows].join('\r\n');
}

async function copyText(text, what) {
  try { await navigator.clipboard.writeText(text); toast(`Copied ${what}`); } catch (e) { toast('Could not copy; select the text and copy it'); }
}

async function viewList() {
  const ix = await store.index();
  let fmt = 'numbers';
  try { fmt = localStorage.getItem('spindle-list-format') || fmt; } catch (e) { /* default */ }
  const sharedParam = route().params.get('share');
  let shared = sharedParam ? lists.decode(sharedParam) : null;
  if (shared) shared.items = shared.items.filter((x) => ix.row.has(x.id));
  let dragFrom = -1, confirmDrop = false;

  const itemHTML = (x, k, editable) => {
    const i = ix.row.get(x.id);
    if (i == null) return '';
    const path = ix.path(x.id).filter((p) => p.id.length > 1).slice(-2).map((p) => trimDot(p.title));
    return `<li class="li-item" data-id="${esc(x.id)}" data-k="${k}"${editable ? ' draggable="true"' : ''}>
      ${editable ? '<span class="grip" aria-hidden="true" title="Drag to reorder"></span>' : `<span class="li-n">${k + 1}</span>`}
      <div class="li-body">
        <div class="li-head"><a class="mid" href="${motifHref(x.id)}">${esc(x.id)}</a> <a class="li-title" href="${motifHref(x.id)}">${esc(ix.rows[i][1])}</a></div>
        <div class="li-path">${esc(x.id[0])} · ${esc(SHORT[x.id[0]] || '')}${path.length ? ' › ' + path.map(esc).join(' › ') : ''}</div>
        ${editable ? `<input class="li-note" type="text" value="${esc(x.note)}" placeholder="Note: where it happens in the tale…" aria-label="Note for ${esc(x.id)}">` : (x.note ? `<div class="li-note-ro">${esc(x.note)}</div>` : '')}
      </div>
      ${editable ? `<div class="li-tools">
        <button type="button" data-move="-1" aria-label="Move up"${k === 0 ? ' disabled' : ''}>↑</button>
        <button type="button" data-move="1" aria-label="Move down">↓</button>
        <button type="button" data-remove aria-label="Remove ${esc(x.id)}">✕</button></div>` : ''}
    </li>`;
  };

  function render() {
    const l = lists.current();
    const editable = !shared;
    const items = shared ? shared.items : l.items;
    document.title = `${(shared ? shared.title : l.title) || 'Your list'} · Spindle`;
    main.innerHTML = `<div class="wrap list-page">
      ${shared ? `<div class="shared-banner"><span>A list shared with you${shared.title ? `: <b>${esc(shared.title)}</b>` : ''} — ${items.length} motif${items.length === 1 ? '' : 's'}.</span>
        <span><button type="button" class="btn" data-act="keep">Keep it as a new list</button> <a class="btn ghost" href="${go('/list')}">Back to your lists</a></span></div>` : ''}
      <div class="list-layout">
        <section class="list-main">
          ${editable ? `<div class="list-switch">
            <select class="list-select" aria-label="Your lists">${lists.all().map((x) => `<option value="${x.id}"${x.id === l.id ? ' selected' : ''}>${esc(x.title || 'Untitled list')} (${x.items.length})</option>`).join('')}</select>
            <button type="button" class="chip" data-act="new">＋ New list</button>
            <button type="button" class="chip danger" data-act="drop">${confirmDrop ? 'Really delete this list?' : 'Delete list'}</button>
          </div>
          <input class="list-title" type="text" value="${esc(l.title)}" placeholder="Untitled list" aria-label="Name of this list">` : `<h1 class="list-title-ro">${esc(shared.title || 'A list of motifs')}</h1>`}
          <p class="list-meta">${items.length} motif${items.length === 1 ? '' : 's'}${editable ? ` · ${lists.persistent ? 'kept in this browser' : '<b>this browser will not keep it</b> — copy it before you leave'}` : ''}
            ${editable && items.length > 1 ? ` · <button type="button" class="linkish" data-act="sort">put in Thompson’s order</button>` : ''}</p>
          ${items.length ? `<ol class="li-list">${items.map((x, k) => itemHTML(x, k, editable)).join('')}</ol>`
            : `<div class="empty">${artEl('owl-empty', 'owl')}<p>Nothing here yet. Add motifs with the <span class="add mini demo" aria-hidden="true"></span> beside search results, on motif pages and in the lists of related motifs. In search results, <kbd>a</kbd> adds the motif you are reading.</p></div>`}
        </section>
        ${items.length ? `<aside class="list-export">
          <h4>Copy the list</h4>
          <div class="formats" role="radiogroup" aria-label="Format">${FORMATS.map(([k, label, hint]) => `<button type="button" class="chip" role="radio" data-fmt="${k}" aria-checked="${k === fmt}" aria-pressed="${k === fmt}" title="${esc(hint)}">${label}</button>`).join('')}</div>
          <p class="hint">${esc(FORMATS.find(([k]) => k === fmt)[2])}</p>
          <textarea class="export-text" readonly rows="8" aria-label="The list as text">${esc(exportText(ix, items, fmt))}</textarea>
          <div class="export-actions">
            <button type="button" class="btn" data-act="copy">Copy</button>
            <button type="button" class="btn ghost" data-act="csv">Download CSV</button>
            <button type="button" class="btn ghost" data-act="link">Copy a link to this list</button>
          </div>
        </aside>` : ''}
      </div>
    </div>`;
    hydrateArt(main);
  }

  const items = () => (shared ? shared.items : lists.current().items);
  const updateExport = () => { const t = $('.export-text', main); if (t) t.value = exportText(ix, items(), fmt); };

  const onClick = async (e) => {
    const b = e.target.closest('button');
    if (!b || !main.contains(b)) return;
    const li = b.closest('.li-item');
    if (b.dataset.fmt) {
      fmt = b.dataset.fmt;
      try { localStorage.setItem('spindle-list-format', fmt); } catch (err) { /* fine */ }
      render();
      return;
    }
    if (li && b.dataset.move) { const k = +li.dataset.k; lists.move(k, k + +b.dataset.move); return; }
    if (li && b.hasAttribute('data-remove')) {
      const r = lists.remove(li.dataset.id);
      if (r) toast(`Took ${li.dataset.id} off your list`, { label: 'Undo', run: () => lists.restore(r.item, r.index) });
      return;
    }
    const act = b.dataset.act;
    if (act === 'new') { confirmDrop = false; lists.create(); $('.list-title', main)?.focus(); }
    if (act === 'drop') {
      if (!confirmDrop) { confirmDrop = true; render(); return; }
      confirmDrop = false;
      lists.drop(lists.current().id);
      toast('List deleted');
    }
    if (act === 'sort') lists.sortBy((id) => ix.row.get(id) ?? Infinity);
    if (act === 'copy') copyText(exportText(ix, items(), fmt), fmt === 'numbers' ? 'the motif numbers' : 'the list');
    if (act === 'csv') {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([csv(ix, items())], { type: 'text/csv;charset=utf-8' }));
      a.download = `${slug(shared ? shared.title : lists.current().title)}.csv`;
      document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    }
    if (act === 'link') {
      const l = shared || lists.current();
      copyText(new URL(go('/list?' + new URLSearchParams({ share: lists.encode(l) })), location.href).href, 'a link to this list');
    }
    if (act === 'keep') {
      lists.create(shared.title, shared.items.map((x) => ({ ...x })));
      toast('Kept as a new list');
      navigate(go('/list'));
    }
  };
  main.addEventListener('click', onClick);
  const onChange = (e) => {
    if (e.target.matches('.list-select')) { confirmDrop = false; lists.select(e.target.value); }
  };
  main.addEventListener('change', onChange);
  const onInput = (e) => {
    if (e.target.matches('.list-title')) {
      lists.rename(e.target.value);
      const opt = $(`.list-select option[value="${lists.current().id}"]`, main);
      if (opt) opt.textContent = `${e.target.value || 'Untitled list'} (${lists.count()})`;
    }
    if (e.target.matches('.li-note')) { lists.setNote(e.target.closest('.li-item').dataset.id, e.target.value); updateExport(); }
  };
  main.addEventListener('input', onInput);
  // drag to reorder (with the arrows for keyboards and touch screens)
  const onDragStart = (e) => {
    const li = e.target.closest?.('.li-item[draggable]');
    if (!li || e.target.matches('input')) return;
    dragFrom = +li.dataset.k;
    li.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', li.dataset.id);
  };
  const onDragOver = (e) => {
    const li = e.target.closest?.('.li-item');
    if (dragFrom < 0 || !li) return;
    e.preventDefault();
    $$('.li-item.over', main).forEach((x) => x !== li && x.classList.remove('over'));
    li.classList.add('over');
  };
  const onDrop = (e) => {
    const li = e.target.closest?.('.li-item');
    if (dragFrom < 0 || !li) return;
    e.preventDefault();
    const from = dragFrom;
    dragFrom = -1;
    lists.move(from, +li.dataset.k);
  };
  const onDragEnd = () => { dragFrom = -1; $$('.li-item.dragging, .li-item.over', main).forEach((x) => x.classList.remove('dragging', 'over')); };
  main.addEventListener('dragstart', onDragStart);
  main.addEventListener('dragover', onDragOver);
  main.addEventListener('drop', onDrop);
  main.addEventListener('dragend', onDragEnd);

  // re-render on changes, but not under the cursor while someone types
  const off = lists.onChange(() => {
    if (shared) return;
    const a = document.activeElement;
    const typing = a && main.contains(a) && a.matches('input[type="text"]');
    if (!typing) render();
  });
  render();
  return () => {
    off();
    main.removeEventListener('click', onClick);
    main.removeEventListener('change', onChange);
    main.removeEventListener('input', onInput);
    main.removeEventListener('dragstart', onDragStart);
    main.removeEventListener('dragover', onDragOver);
    main.removeEventListener('drop', onDrop);
    main.removeEventListener('dragend', onDragEnd);
  };
}

// ---------------------------------------------------------------- about

async function viewAbout() {
  document.title = 'About · Spindle';
  const ix = await store.index();
  const at = await store.atlas();
  main.innerHTML = `<article class="wrap about fade-in">
    <h1>About Spindle</h1>
    <p>Stith Thompson’s <i>Motif-Index of Folk-Literature</i> (1932–36; revised and enlarged 1955–58) classifies the recurring elements of traditional narrative — the swan maiden, the forbidden chamber, the trickster who feigns death — into a tree of some ${fmt(ix.n)} numbered motifs, each with a trail of references to the collections where it occurs. It remains the common language of folk-narrative research, and it remains hard to search: a motif is found only if one guesses Thompson’s wording, or the branch he filed it under.</p>
    <p>Spindle searches it by meaning. It is a successor to MOMFER, the <i>Meertens Online Motif FindER</i> (Karsdorp, Van der Meulen, Meder &amp; Van den Bosch, <a href="https://doi.org/10.1080/0015587X.2015.1006954"><i>Folklore</i> 126 (2015)</a>), which matched words and expanded them through WordNet. Spindle compares meanings directly, and does so entirely in your browser: there is no server.</p>
    <p>The mole peeking out from behind the tree of tales is for MOMFER, whose name also belonged to Momfer de Mol of <i>De Fabeltjeskrant</i>.</p>

    <h2>How it works</h2>
    <ul>
      <li><b>Text.</b> The index was re-parsed from the HTML edition at ruthenia.ru, the fullest digital transcription of the revised edition, keeping each motif’s headline, explanatory note and references apart. A character-encoding fault that had turned <i>Métraux</i> into <i>Mйtraux</i> throughout was reversed.</li>
      <li><b>Tree.</b> Every motif is placed under its parent: the dotted subdivisions under their stems, the numbered motifs under Thompson’s own section headings (e.g. <span class="mid">D100–D199</span> <i>Transformation: man to animal</i>).</li>
      <li><b>Traditions.</b> The labels in the references (“Irish myth:”, “India:”, “N. A. Indian (Zuñi):”) are normalised into ${fmt(ix.meta.cultures.length)} traditions in ${ix.meta.regions.length} broad regions, so that results can be filtered by where a motif is attested.</li>
      <li><b>Meaning.</b> Every motif’s headline and note were embedded with a sentence encoder and stored compactly (256 dimensions, one byte each). When you search, your browser downloads the same encoder once (about 110 MB, then cached), embeds your description, and compares it with all motifs in a few milliseconds. For one- and two-word queries exact word matches count for a little more, and a name found in no headline is looked up in the references — which is how <a href="${searchHref({ q: 'Melusine' })}">Melusine</a> finds the Melusine tabu.</li>
      <li><b>Trained on tales.</b> The encoder, <code>bge-base-en-v1.5</code>, was fine-tuned on some 1,800 plot fragments from the tale-type summaries of the Aarne–Thompson–Uther index, each with the motif cited for it (“…he falls into a magic sleep [D1975]”), and on 4,700 searches written from real tales: a language model (Claude Sonnet) found where a telling expresses one of its type’s motifs, then, without seeing Thompson’s wording, wrote what someone half-remembering the episode might type. Both come from Joshua Hagedorn’s <a href="https://github.com/j-hagedorn/trilogy">trilogy</a> datasets. The encoder has learned how stories, and people, put what Thompson puts tersely.</li>
      <li><b>In plain words.</b> For every motif a language model (Claude Haiku) wrote one or two plain sentences and a few phrases one might search with. These count as a second description of the motif when you search, and are shown on motif pages marked <i>In plain words</i>. They are generated, not Thompson’s, and can be wrong in detail.</li>
      <li><b>The atlas.</b> Each tradition is placed where its tales were collected — the Ekoi on the Cross River, the Toba in the Gran Chaco — ${fmt(at.places.length)} places in all, from a gazetteer written for Spindle. Labels for a whole region (“African”, “Polynesian”) and written or religious traditions (“Jewish”, “Italian Novella”) are drawn differently from peoples and places. The <a href="${go('/atlas')}">atlas</a> shows what Thompson’s sources cover, not where a motif is or is not told; coastlines are from <a href="https://www.naturalearthdata.com/">Natural Earth</a>.</li>
      <li><b>Echoes.</b> On every motif page, Spindle lists the most similar motifs that Thompson filed in other branches — the duplications and near-duplications he himself acknowledged (<a href="${motifHref('D1645.9')}">D1645.9</a> and <a href="${motifHref('F718.5')}">F718.5</a>), and many he did not.</li>
    </ul>

    <h2>How well it works</h2>
    <p>The main test is 687 plot fragments from tale-type summaries, each with the motif the summary cites, all from tale types the encoder never saw in training (“when the princess laughs at him, he wishes her pregnant” → <a href="${motifHref('T513')}">T513</a>). Many fragments are hard out of context, so the ceiling is well below 100%.</p>
    <table>
      <tr><th></th><th>right motif first</th><th>in the top ten</th></tr>
      <tr><td>Spindle, first version</td><td>24%</td><td>44%</td></tr>
      <tr><td>Spindle, trained and with plain words</td><td>33%</td><td>55%</td></tr>
    </table>
    <p>A second test comes closer to how Spindle is used: 1,600 searches from 400 passages of folktales, again of tale types the encoder never saw — the passages themselves, and vague lines, descriptions and keywords written from them without Thompson’s wording (“a bird sat on the bones and they turned into a boy again”). The index lists the motifs of a tale <i>type</i>, so a telling usually contains motifs beyond the one a search was written for; a language model judged the top results, and the second column counts any motif a folklorist would cite for the episode.</p>
    <table>
      <tr><th></th><th>in the top ten, the listed motif</th><th>in the top ten, any fitting motif</th></tr>
      <tr><td>Spindle, trained on summaries only</td><td>47%</td><td>75%</td></tr>
      <tr><td>Spindle, trained on summaries and tales</td><td>51%</td><td>79%</td></tr>
    </table>
    <p>Describing the episode works better than pasting the passage: about four in five descriptions find a fitting motif in the top ten, against two in three passages.</p>
    <p>Against MOMFER, on forty queries written before either system was run on them — twenty plain-language descriptions (“a man trades his soul for riches”) and twenty short keyword searches (“flying carpet”) — with MOMFER’s search reconstructed from its source code:</p>
    <table>
      <tr><th></th><th>right motif first</th><th>in the top ten</th></tr>
      <tr><td>Spindle, descriptions</td><td>90%</td><td>100%</td></tr>
      <tr><td>MOMFER, descriptions</td><td>45%</td><td>60%</td></tr>
      <tr><td>Spindle, keywords</td><td>80%</td><td>90%</td></tr>
      <tr><td>MOMFER, keywords</td><td>65%</td><td>80%</td></tr>
    </table>
    <p>MOMFER misses outright what it cannot match word for word — “werewolf” when Thompson wrote <i>werwolf</i>, “the trickster gets stuck to a figure covered in tar” for the tar-baby. Forty queries is a small sample, and these were also looked at while choosing the trained encoder; the tests above are the fairer measure. Treat the results as a well-read colleague’s suggestions, and check the index.</p>

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
    <h2>Keeping a list</h2>
    <p>Annotating a tale means collecting motifs. The <span class="add mini demo" aria-hidden="true"></span> beside a search result, on a motif page or in a list of related motifs puts it on <a href="${go('/list')}">your list</a> (in search results, <kbd>a</kbd> does the same for the motif you are reading). Keep a list per tale, note where each motif occurs, put them in Thompson’s order, and copy the list as motif numbers (“D1975; H481.1”), as numbers with headlines, or as a table for a spreadsheet. Lists stay in your browser; a link carries one to a colleague.</p>
    <p>In references, Thompson’s asterisk marks a reference with further bibliography, the double asterisk an especially full treatment.</p>
  </article>`;
}

hydrateArt(document);
refreshLists();
render();
