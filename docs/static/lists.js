// Motif lists: the motifs someone collects while annotating a tale, kept in
// this browser (localStorage). A list can also travel in a link.

const KEY = 'spindle-lists';
const listeners = new Set();

const uid = () => Math.random().toString(36).slice(2, 10);
const blank = (title = '', items = []) => ({ id: uid(), title, items, updated: Date.now() });

let state = load();
/** False when this browser will not keep the lists (private mode, blocked storage). */
export let persistent = true;

function load() {
  try {
    const s = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (s && Array.isArray(s.lists) && s.lists.length) return s;
  } catch (e) { /* unreadable or blocked: start afresh */ }
  const l = blank();
  return { current: l.id, lists: [l] };
}

function save({ quiet = false } = {}) {
  current().updated = Date.now();
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
    persistent = true;
  } catch (e) {
    persistent = false;
  }
  if (!quiet) listeners.forEach((f) => f());
}

/** Call f whenever the lists change (here or in another tab); returns an unsubscribe function. */
export const onChange = (f) => { listeners.add(f); return () => listeners.delete(f); };
window.addEventListener('storage', (e) => {
  if (e.key !== KEY) return;
  state = load();
  listeners.forEach((f) => f());
});

export const all = () => state.lists;
export const current = () => state.lists.find((l) => l.id === state.current) || state.lists[0];
export const has = (id) => current().items.some((x) => x.id === id);
export const count = () => current().items.length;

/** Add a motif, or take it out again; returns what happened, for an undo. */
export function toggle(id) {
  const l = current();
  const i = l.items.findIndex((x) => x.id === id);
  if (i >= 0) {
    const [item] = l.items.splice(i, 1);
    save();
    return { added: false, item, index: i };
  }
  l.items.push({ id, note: '' });
  save();
  return { added: true };
}

export function restore(item, index) {
  const l = current();
  if (l.items.some((x) => x.id === item.id)) return;
  l.items.splice(Math.min(index, l.items.length), 0, item);
  save();
}

export function remove(id) {
  const l = current();
  const index = l.items.findIndex((x) => x.id === id);
  if (index < 0) return null;
  const [item] = l.items.splice(index, 1);
  save();
  return { item, index };
}

export function move(from, to) {
  const items = current().items;
  if (from === to || from < 0 || to < 0 || from >= items.length || to >= items.length) return;
  items.splice(to, 0, items.splice(from, 1)[0]);
  save();
}

/** Put the motifs in a given order, e.g. Thompson's. */
export function sortBy(key) {
  current().items.sort((a, b) => key(a.id) - key(b.id));
  save();
}

// typing a note or a title saves without re-rendering the page under the cursor
export function setNote(id, note) {
  const x = current().items.find((y) => y.id === id);
  if (x) { x.note = note; save({ quiet: true }); }
}
export function rename(title) { current().title = title; save({ quiet: true }); }

export function select(listId) { state.current = listId; save(); }

export function create(title = '', items = []) {
  const l = blank(title, items);
  state.lists.unshift(l);
  state.current = l.id;
  save();
  return l;
}

export function drop(listId) {
  state.lists = state.lists.filter((l) => l.id !== listId);
  if (!state.lists.length) state.lists = [blank()];
  if (!state.lists.some((l) => l.id === state.current)) state.current = state.lists[0].id;
  save();
}

// ------------------------------------------------------------ in a link

const b64 = (s) => btoa(String.fromCharCode(...new TextEncoder().encode(s))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const unb64 = (s) => new TextDecoder().decode(Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0)));

/** A list as a compact string for a link: its title and its motifs with their notes. */
export const encode = (l) => b64(JSON.stringify({ t: l.title, m: l.items.map((x) => (x.note ? [x.id, x.note] : x.id)) }));

export function decode(s) {
  try {
    const d = JSON.parse(unb64(s));
    const items = (d.m || []).map((x) => (Array.isArray(x) ? { id: String(x[0]), note: String(x[1] || '') } : { id: String(x), note: '' }));
    return { title: String(d.t || ''), items };
  } catch (e) {
    return null;
  }
}
