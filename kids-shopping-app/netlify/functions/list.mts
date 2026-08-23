import type { Config, Context } from "@netlify/functions";
import { getStore } from "@netlify/blobs";

// Shared shopping-list document, one per family, gated by a PIN.
// GET  /api/list  -> current document
// PUT  /api/list  -> merge client document in (last-write-wins per entry), return merged

const KEY = "family-list";

type Entry = {
  key: string;
  productId: string;
  kid: string;
  qty: number;
  purchased: boolean;
  addedBy: string;
  removed: boolean;
  ts: number;
};
type Doc = { entries: Record<string, Entry> };

function merge(a: Doc, b: Doc): Doc {
  const entries: Record<string, Entry> = { ...(a.entries || {}) };
  for (const [key, entry] of Object.entries(b.entries || {})) {
    const mine = entries[key];
    if (!mine || (entry.ts || 0) > (mine.ts || 0)) entries[key] = entry;
  }
  return { entries };
}

export default async (req: Request, _context: Context) => {
  const pin = Netlify.env.get("FAMILY_PIN");
  if (pin && req.headers.get("x-family-pin") !== pin) {
    return new Response(JSON.stringify({ error: "wrong pin" }), {
      status: 401,
      headers: { "content-type": "application/json" },
    });
  }

  const store = getStore({ name: "shopping-list", consistency: "strong" });
  const current: Doc = (await store.get(KEY, { type: "json" })) || { entries: {} };

  if (req.method === "GET") {
    return Response.json(current);
  }

  if (req.method === "PUT") {
    let incoming: Doc;
    try {
      incoming = await req.json();
      if (typeof incoming?.entries !== "object" || incoming.entries === null) throw new Error();
    } catch {
      return new Response(JSON.stringify({ error: "bad body" }), { status: 400 });
    }
    // Cap document size defensively (this is a family list, not a database).
    if (Object.keys(incoming.entries).length > 2000) {
      return new Response(JSON.stringify({ error: "too large" }), { status: 413 });
    }
    const merged = merge(current, incoming);
    await store.setJSON(KEY, merged);
    return Response.json(merged);
  }

  return new Response("Method not allowed", { status: 405 });
};

export const config: Config = {
  path: "/api/list",
};
