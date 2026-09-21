// Tiny PostgREST client over the Supabase service key. No SDK dependency —
// this is the entire surface the dashboard needs (select/patch/insert), kept
// small enough to audit. Never log SUPABASE_SERVICE_KEY or the Authorization
// header; errors below include only the response status + PostgREST's own
// (already-sanitized) error body.

export interface SupabaseConfig {
  url: string;
  serviceKey: string;
}

export type FilterOp = 'eq' | 'neq' | 'lt' | 'lte' | 'gt' | 'gte' | 'in' | 'is';

export interface Filter {
  column: string;
  op: FilterOp;
  value: string | number | boolean | (string | number)[];
}

export interface SelectOptions {
  select?: string;
  filters?: Filter[];
  order?: { column: string; ascending?: boolean }[];
  limit?: number;
}

function encodeFilterValue(op: FilterOp, value: Filter['value']): string {
  if (op === 'in') {
    const list = Array.isArray(value) ? value : [value];
    return `in.(${list.map((v) => String(v)).join(',')})`;
  }
  return `${op}.${String(value)}`;
}

function baseHeaders(cfg: SupabaseConfig): HeadersInit {
  return {
    apikey: cfg.serviceKey,
    Authorization: `Bearer ${cfg.serviceKey}`,
    'Content-Type': 'application/json',
  };
}

export class SupabaseError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string) {
    super(`PostgREST ${status}: ${body}`);
    this.status = status;
    this.body = body;
  }
}

async function readBody(res: Response): Promise<string> {
  try {
    return await res.text();
  } catch {
    return '';
  }
}

export class SupabaseClient {
  constructor(private cfg: SupabaseConfig) {}

  private restUrl(table: string): URL {
    return new URL(`${this.cfg.url.replace(/\/+$/, '')}/rest/v1/${table}`);
  }

  async select<T = Record<string, unknown>>(table: string, opts: SelectOptions = {}): Promise<T[]> {
    const url = this.restUrl(table);
    url.searchParams.set('select', opts.select ?? '*');
    for (const f of opts.filters ?? []) {
      url.searchParams.set(f.column, encodeFilterValue(f.op, f.value));
    }
    if (opts.order?.length) {
      url.searchParams.set(
        'order',
        opts.order.map((o) => `${o.column}.${o.ascending === false ? 'desc' : 'asc'}`).join(','),
      );
    }
    if (typeof opts.limit === 'number') {
      url.searchParams.set('limit', String(opts.limit));
    }
    const res = await fetch(url.toString(), { headers: baseHeaders(this.cfg) });
    if (!res.ok) throw new SupabaseError(res.status, await readBody(res));
    return (await res.json()) as T[];
  }

  async getById<T = Record<string, unknown>>(table: string, id: string, select = '*'): Promise<T | null> {
    const rows = await this.select<T>(table, { select, filters: [{ column: 'id', op: 'eq', value: id }], limit: 1 });
    return rows[0] ?? null;
  }

  async patch<T = Record<string, unknown>>(table: string, id: string, patch: Record<string, unknown>): Promise<T> {
    const url = this.restUrl(table);
    url.searchParams.set('id', `eq.${id}`);
    const res = await fetch(url.toString(), {
      method: 'PATCH',
      headers: { ...baseHeaders(this.cfg), Prefer: 'return=representation' },
      body: JSON.stringify(patch),
    });
    if (!res.ok) throw new SupabaseError(res.status, await readBody(res));
    const rows = (await res.json()) as T[];
    const row = rows[0];
    if (!row) throw new SupabaseError(404, `no row updated in ${table} for id=${id}`);
    return row;
  }

  async insert<T = Record<string, unknown>>(
    table: string,
    row: Record<string, unknown>,
    opts: { onConflict?: string; ignoreDuplicates?: boolean } = {},
  ): Promise<T | null> {
    const url = this.restUrl(table);
    if (opts.onConflict) url.searchParams.set('on_conflict', opts.onConflict);
    const preferParts = ['return=representation'];
    if (opts.ignoreDuplicates) preferParts.push('resolution=ignore-duplicates');
    const res = await fetch(url.toString(), {
      method: 'POST',
      headers: { ...baseHeaders(this.cfg), Prefer: preferParts.join(',') },
      body: JSON.stringify(row),
    });
    if (!res.ok) throw new SupabaseError(res.status, await readBody(res));
    const text = await res.text();
    if (!text) return null; // ignore-duplicates with no insert returns empty body
    const rows = JSON.parse(text) as T[];
    return rows[0] ?? null;
  }

  async logEvent(entity: string, entityId: string, event: string, payload: Record<string, unknown> = {}): Promise<void> {
    await this.insert('events', { entity, entity_id: entityId, event, payload });
  }

  async getConfig<T = unknown>(key: string): Promise<T | null> {
    const rows = await this.select<{ key: string; value: T }>('config', {
      select: 'key,value',
      filters: [{ column: 'key', op: 'eq', value: key }],
      limit: 1,
    });
    return rows[0]?.value ?? null;
  }

  async setConfig(key: string, value: unknown): Promise<void> {
    const url = this.restUrl('config');
    const res = await fetch(url.toString(), {
      method: 'POST',
      headers: { ...baseHeaders(this.cfg), Prefer: 'resolution=merge-duplicates,return=minimal' },
      body: JSON.stringify({ key, value, updated_at: new Date().toISOString() }),
    });
    if (!res.ok) throw new SupabaseError(res.status, await readBody(res));
  }
}

export function requireSupabase(env: { SUPABASE_URL?: string; SUPABASE_SERVICE_KEY?: string }): SupabaseClient {
  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_KEY) {
    throw new Error('SUPABASE_URL / SUPABASE_SERVICE_KEY not configured');
  }
  return new SupabaseClient({ url: env.SUPABASE_URL, serviceKey: env.SUPABASE_SERVICE_KEY });
}
