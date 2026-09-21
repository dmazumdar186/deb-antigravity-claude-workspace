// Small JSON response helpers shared by every functions/api/*.ts route.

export function json(data: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set('Content-Type', 'application/json; charset=utf-8');
  return new Response(JSON.stringify(data), { ...init, headers });
}

export function errorJson(status: number, message: string, extra: Record<string, unknown> = {}): Response {
  return json({ error: message, ...extra }, { status });
}

export async function readJsonBody<T = Record<string, unknown>>(request: Request): Promise<T> {
  try {
    return (await request.json()) as T;
  } catch {
    throw new BadRequestError('request body must be valid JSON');
  }
}

export class BadRequestError extends Error {}

export async function withErrorHandling(fn: () => Promise<Response>): Promise<Response> {
  try {
    return await fn();
  } catch (err) {
    if (err instanceof BadRequestError) {
      return errorJson(400, err.message);
    }
    const message = err instanceof Error ? err.message : String(err);
    // Never log SUPABASE_SERVICE_KEY-bearing details; SupabaseError/Error
    // messages here only ever carry PostgREST's own response body + status.
    console.error('dashboard api error:', message);
    return errorJson(500, 'internal error', { detail: message });
  }
}
