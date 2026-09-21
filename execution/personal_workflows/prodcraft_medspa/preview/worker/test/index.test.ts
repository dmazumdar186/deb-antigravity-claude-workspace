import { describe, expect, it } from "vitest";
import { handleRequest, handleScheduled, slugSuffixFromHost, type Env, type PreviewMeta } from "../src/index";

// ---- Hand-rolled fakes (no miniflare) --------------------------------

class FakeR2Bucket {
  store = new Map<string, { body: string; }>();

  async get(key: string) {
    const entry = this.store.get(key);
    if (!entry) return null;
    return {
      body: entry.body,
      // Response accepts a string body directly; keep it simple.
    } as unknown as R2ObjectBody;
  }

  async put(key: string, value: string) {
    this.store.set(key, { body: value });
  }

  async delete(keys: string | string[]) {
    const list = Array.isArray(keys) ? keys : [keys];
    for (const k of list) this.store.delete(k);
  }

  async list(opts: { prefix?: string; cursor?: string } = {}) {
    const prefix = opts.prefix ?? "";
    const allKeys = [...this.store.keys()].filter((k) => k.startsWith(prefix)).sort();
    // No real pagination needed for these tests — return everything in one page.
    const objects = allKeys.map((key) => ({ key })) as unknown as R2Object[];
    return { objects, truncated: false, cursor: undefined } as unknown as R2Objects;
  }
}

class FakeKVNamespace {
  store = new Map<string, string>();

  async get(key: string) {
    return this.store.get(key) ?? null;
  }

  async put(key: string, value: string) {
    this.store.set(key, value);
  }

  async delete(key: string) {
    this.store.delete(key);
  }

  async list(opts: { prefix?: string; cursor?: string } = {}) {
    const prefix = opts.prefix ?? "";
    const keys = [...this.store.keys()]
      .filter((k) => k.startsWith(prefix))
      .sort()
      .map((name) => ({ name }));
    return { keys, list_complete: true, cursor: undefined } as unknown as KVNamespaceListResult<unknown>;
  }
}

function makeEnv(overrides: Partial<Env> = {}): { env: Env; r2: FakeR2Bucket; kv: FakeKVNamespace } {
  const r2 = new FakeR2Bucket();
  const kv = new FakeKVNamespace();
  const env: Env = {
    PREVIEWS: r2 as unknown as R2Bucket,
    META: kv as unknown as KVNamespace,
    PREVIEW_BASE_DOMAIN: "preview.prodcraft.fyi",
    REMOVE_WEBHOOK_SECRET: "test-secret",
    ...overrides,
  };
  return { env, r2, kv };
}

const fakeCtx = {} as ExecutionContext;

function futureDate(days = 30): string {
  return new Date(Date.now() + days * 24 * 60 * 60 * 1000).toISOString();
}

function pastDate(days = 1): string {
  return new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();
}

const HOST = "glow-aesthetics-k3x9qa.preview.prodcraft.fyi";

async function seedActive(kv: FakeKVNamespace, opts: Partial<PreviewMeta> = {}) {
  const meta: PreviewMeta = {
    expires_at: futureDate(),
    takedown: false,
    business_id: "biz-1",
    preview_id: "preview-1",
    status: "active",
    ...opts,
  };
  await kv.put(`meta:${slugSuffixFromHost(HOST)}`, JSON.stringify(meta));
  return meta;
}

// ---- Tests -------------------------------------------------------------

describe("slugSuffixFromHost", () => {
  it("extracts the {slug}-{suffix} label", () => {
    expect(slugSuffixFromHost(HOST)).toBe("glow-aesthetics-k3x9qa");
  });
});

describe("robots.txt", () => {
  it("disallows all crawling on any preview host", async () => {
    const { env } = makeEnv();
    const req = new Request(`https://${HOST}/robots.txt`, { headers: { Host: HOST } });
    const res = await handleRequest(req, env, fakeCtx);
    expect(res.status).toBe(200);
    const text = await res.text();
    expect(text).toContain("Disallow: /");
  });
});

describe("serving an active preview", () => {
  it("serves index.html with noindex header and correct content-type", async () => {
    const { env, r2, kv } = makeEnv();
    await seedActive(kv);
    await r2.put(`previews/${slugSuffixFromHost(HOST)}/index.html`, "<html>hi</html>");

    const req = new Request(`https://${HOST}/`, { headers: { Host: HOST } });
    const res = await handleRequest(req, env, fakeCtx);

    expect(res.status).toBe(200);
    expect(res.headers.get("X-Robots-Tag")).toBe("noindex, nofollow");
    expect(res.headers.get("Content-Type")).toContain("text/html");
    expect(await res.text()).toBe("<html>hi</html>");
  });

  it("maps a nested path to its R2 key", async () => {
    const { env, r2, kv } = makeEnv();
    await seedActive(kv);
    await r2.put(`previews/${slugSuffixFromHost(HOST)}/styles.css`, "body{}");

    const req = new Request(`https://${HOST}/styles.css`, { headers: { Host: HOST } });
    const res = await handleRequest(req, env, fakeCtx);

    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toContain("text/css");
  });

  it("404s a missing object with no custom 404.html", async () => {
    const { env, kv } = makeEnv();
    await seedActive(kv);

    const req = new Request(`https://${HOST}/nope.html`, { headers: { Host: HOST } });
    const res = await handleRequest(req, env, fakeCtx);
    expect(res.status).toBe(404);
  });
});

describe("missing meta", () => {
  it("returns 404 page when no KV meta exists for the host", async () => {
    const { env } = makeEnv();
    const req = new Request(`https://${HOST}/`, { headers: { Host: HOST } });
    const res = await handleRequest(req, env, fakeCtx);
    expect(res.status).toBe(404);
  });
});

describe("expired preview", () => {
  it("302s to /expired when now > expires_at", async () => {
    const { env, kv } = makeEnv();
    await seedActive(kv, { expires_at: pastDate() });

    const req = new Request(`https://${HOST}/`, { headers: { Host: HOST } });
    const res = await handleRequest(req, env, fakeCtx);

    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toBe("/expired");
  });

  it("serves the inline expired page at /expired", async () => {
    const { env, kv } = makeEnv();
    await seedActive(kv, { expires_at: pastDate() });

    const req = new Request(`https://${HOST}/expired`, { headers: { Host: HOST } });
    const res = await handleRequest(req, env, fakeCtx);

    expect(res.status).toBe(200);
    const text = await res.text();
    expect(text).toContain("expired");
  });
});

describe("takedown preview", () => {
  it("returns 410 for a taken-down host", async () => {
    const { env, kv } = makeEnv();
    await seedActive(kv, { takedown: true });

    const req = new Request(`https://${HOST}/`, { headers: { Host: HOST } });
    const res = await handleRequest(req, env, fakeCtx);

    expect(res.status).toBe(410);
    const text = await res.text();
    expect(text).toContain("removed");
  });
});

describe("POST /remove", () => {
  it("deletes R2 objects and marks KV takedown", async () => {
    const { env, r2, kv } = makeEnv();
    await seedActive(kv);
    const prefix = `previews/${slugSuffixFromHost(HOST)}/`;
    await r2.put(`${prefix}index.html`, "<html></html>");
    await r2.put(`${prefix}styles.css`, "body{}");

    const req = new Request(`https://${HOST}/remove`, {
      method: "POST",
      headers: { Host: HOST, "Content-Type": "application/x-www-form-urlencoded" },
      body: "confirm=1",
    });
    const res = await handleRequest(req, env, fakeCtx);

    expect(res.status).toBe(200);
    expect(await res.text()).toContain("won't hear from ProdCraft again");

    // R2 objects gone
    expect(await r2.get(`${prefix}index.html`)).toBeNull();
    expect(await r2.get(`${prefix}styles.css`)).toBeNull();

    // KV marked takedown
    const rawMeta = await kv.get(`meta:${slugSuffixFromHost(HOST)}`);
    const meta = JSON.parse(rawMeta as string) as PreviewMeta;
    expect(meta.takedown).toBe(true);
    expect(meta.takedown_at).toBeTruthy();
  });

  it("GET /remove shows a confirmation form", async () => {
    const { env, kv } = makeEnv();
    await seedActive(kv);
    const req = new Request(`https://${HOST}/remove`, { headers: { Host: HOST } });
    const res = await handleRequest(req, env, fakeCtx);
    expect(res.status).toBe(200);
    const text = await res.text();
    expect(text).toContain("<form");
    expect(text).toContain('name="confirm"');
  });
});

describe("POST /api/publish", () => {
  it("requires a bearer token", async () => {
    const { env } = makeEnv();
    const req = new Request("https://control.preview.prodcraft.fyi/api/publish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ host: HOST, expires_at: futureDate(), business_id: "b1", preview_id: "p1" }),
    });
    const res = await handleRequest(req, env, fakeCtx);
    expect(res.status).toBe(401);
  });

  it("writes KV meta with a valid bearer token", async () => {
    const { env, kv } = makeEnv();
    const req = new Request("https://control.preview.prodcraft.fyi/api/publish", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer test-secret" },
      body: JSON.stringify({ host: HOST, expires_at: futureDate(), business_id: "b1", preview_id: "p1" }),
    });
    const res = await handleRequest(req, env, fakeCtx);
    expect(res.status).toBe(200);

    const raw = await kv.get(`meta:${slugSuffixFromHost(HOST)}`);
    expect(raw).toBeTruthy();
    const meta = JSON.parse(raw as string) as PreviewMeta;
    expect(meta.business_id).toBe("b1");
    expect(meta.takedown).toBe(false);
  });
});

describe("handleScheduled", () => {
  it("marks expired previews and leaves recently-expired R2 objects alone", async () => {
    const { env, r2, kv } = makeEnv();
    await seedActive(kv, { expires_at: pastDate(5) });
    const prefix = `previews/${slugSuffixFromHost(HOST)}/`;
    await r2.put(`${prefix}index.html`, "<html></html>");

    const result = await handleScheduled(env);
    expect(result.expired).toBe(1);
    expect(result.deleted).toBe(0);

    const raw = await kv.get(`meta:${slugSuffixFromHost(HOST)}`);
    const meta = JSON.parse(raw as string) as PreviewMeta;
    expect(meta.status).toBe("expired");

    // Grace period: object still present (only 5 days past expiry).
    expect(await r2.get(`${prefix}index.html`)).not.toBeNull();
  });

  it("reclaims R2 storage for previews expired more than 60 days", async () => {
    const { env, r2, kv } = makeEnv();
    await seedActive(kv, { expires_at: pastDate(90), status: "expired" });
    const prefix = `previews/${slugSuffixFromHost(HOST)}/`;
    await r2.put(`${prefix}index.html`, "<html></html>");

    const result = await handleScheduled(env);
    expect(result.deleted).toBeGreaterThan(0);
    expect(await r2.get(`${prefix}index.html`)).toBeNull();
  });
});
