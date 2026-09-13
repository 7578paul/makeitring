/**
 * makeitring — Worker in front of the static site.
 *
 * Everything except /spend/api/* is the site exactly as before: the request
 * goes straight to the static assets. The API is one thing only — a postbox
 * for the letters, so they arrive on their own instead of by link.
 *
 * The postbox never sees a letter. The two devices share a phrase; the phrase
 * decides the postbox's name, the token that may write to it, and the key the
 * letters are encrypted with, and none of that derivation happens here. What
 * is stored is a blob this Worker cannot read.
 */

const MAX_BODY = 1024 * 1024;    // one request
const MAX_ITEMS = 25;            // letters per delivery
const MAX_BLOB = 24 * 1024;      // one letter
const KEEP = 200;                // letters kept per postbox
const CHUNK = 90 * 1024;         // a stored vault is split into pieces this size
const MAX_VAULT = 900 * 1024;    // and cannot be bigger than this in total

function json(data, status) {
  return new Response(JSON.stringify(data), {
    status: status || 200,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff'
    }
  });
}

export class Postbox {
  constructor(ctx) {
    this.ctx = ctx;
    this.store = ctx.storage;
  }

  /* the first delivery claims the box; after that the token has to match */
  async allowed(token) {
    if (!token || typeof token !== 'string' || token.length < 32 || token.length > 128) return false;
    const held = await this.store.get('token');
    if (!held) { await this.store.put('token', token); return true; }
    if (held.length !== token.length) return false;
    let same = 0;
    for (let i = 0; i < held.length; i++) same |= held.charCodeAt(i) ^ token.charCodeAt(i);
    return same === 0;
  }

  /* ── the vault slot ────────────────────────────────────────────────
     One encrypted blob per account, replaced whole. It is the same
     ciphertext the phone keeps locally: only her passphrase opens it, so
     this is a locker, not a database. */
  async vault(request) {
    const url = new URL(request.url);

    if (request.method === 'GET') {
      if (!await this.allowed(url.searchParams.get('t') || '')) return json({ error: 'no' }, 403);
      const head = await this.store.get('vault');
      if (!head) return json({ savedAt: 0, blob: '' });   /* claimed, but nothing in it yet */
      const parts = await this.store.list({ prefix: 'v:', limit: 100 });
      const keys = [...parts.keys()].sort((a, b) => Number(a.slice(2)) - Number(b.slice(2)));
      let blob = '';
      for (const k of keys) blob += parts.get(k);
      return json({ savedAt: head.savedAt, blob });
    }

    if (request.method === 'PUT') {
      const body = await request.json().catch(() => null);
      if (!body || typeof body.blob !== 'string') return json({ error: 'bad body' }, 400);
      if (!await this.allowed(body.token)) return json({ error: 'no' }, 403);
      if (body.blob.length > MAX_VAULT) return json({ error: 'too big' }, 413);

      const old = await this.store.list({ prefix: 'v:', limit: 100 });
      if (old.size) await this.store.delete([...old.keys()]);
      const writes = { vault: { savedAt: Number(body.savedAt) || Date.now(), size: body.blob.length } };
      let n = 0;
      for (let i = 0; i < body.blob.length; i += CHUNK) writes['v:' + (n++)] = body.blob.slice(i, i + CHUNK);
      await this.store.put(writes);
      return json({ ok: true, savedAt: writes.vault.savedAt, pieces: n });
    }

    return json({ error: 'method' }, 405);
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname.indexOf('/vault/') > -1) return this.vault(request);

    if (request.method === 'GET') {
      const token = url.searchParams.get('t') || '';
      if (!await this.allowed(token)) return json({ error: 'no' }, 403);
      const since = Math.max(0, parseInt(url.searchParams.get('since') || '0', 10) || 0);
      const rows = await this.store.list({ prefix: 'l:', limit: 1000 });
      const items = [];
      let seq = since;
      for (const [k, v] of rows) {
        const n = Number(k.slice(2));
        if (n > seq) seq = n;
        if (n > since) items.push({ seq: n, id: v.id, blob: v.blob });
      }
      items.sort((a, b) => a.seq - b.seq);
      return json({ seq, items });
    }

    if (request.method === 'POST') {
      const body = await request.json().catch(() => null);
      if (!body || !Array.isArray(body.items)) return json({ error: 'bad body' }, 400);
      if (!await this.allowed(body.token)) return json({ error: 'no' }, 403);
      if (body.items.length > MAX_ITEMS) return json({ error: 'too many' }, 413);

      let next = (await this.store.get('seq')) || 0;
      const writes = {};
      let wrote = 0;
      for (const item of body.items) {
        if (!item || typeof item.blob !== 'string' || typeof item.id !== 'string') continue;
        if (item.blob.length > MAX_BLOB) return json({ error: 'too big' }, 413);
        next += 1;
        writes['l:' + next] = { id: item.id, blob: item.blob, at: Date.now() };
        wrote += 1;
      }
      if (!wrote) return json({ error: 'nothing to post' }, 400);
      writes.seq = next;
      await this.store.put(writes);

      /* keep the box from growing for ever */
      const all = await this.store.list({ prefix: 'l:', limit: 1000 });
      if (all.size > KEEP) {
        const keys = [...all.keys()].sort((a, b) => Number(a.slice(2)) - Number(b.slice(2)));
        await this.store.delete(keys.slice(0, all.size - KEEP));
      }
      return json({ ok: true, seq: next, posted: wrote });
    }

    if (request.method === 'DELETE') {
      const token = url.searchParams.get('t') || '';
      if (!await this.allowed(token)) return json({ error: 'no' }, 403);
      const all = await this.store.list({ prefix: 'l:', limit: 1000 });
      await this.store.delete([...all.keys()]);
      return json({ ok: true, emptied: all.size });
    }

    return json({ error: 'method' }, 405);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname.startsWith('/spend/api/')) {
      const m = url.pathname.match(/^\/spend\/api\/(box|vault)\/([a-f0-9]{16,64})$/);
      if (!m) return json({ error: 'not a postbox' }, 404);
      if (request.method === 'POST' || request.method === 'PUT') {
        const len = Number(request.headers.get('content-length') || 0);
        if (len > MAX_BODY) return json({ error: 'too big' }, 413);
      }
      const id = env.POSTBOX.idFromName(m[1] + ':' + m[2]);
      return env.POSTBOX.get(id).fetch(request);
    }

    /* everything else is the site, untouched */
    return env.ASSETS.fetch(request);
  }
};
