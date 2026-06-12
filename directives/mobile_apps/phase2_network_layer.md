# Phase 2 — Network Layer (axios + retry + loading UX)

## Goal

Wrap every outbound HTTP call in a single configured axios client with retry, timeout, loading state, and a unified error envelope. After this phase, screens never see raw `fetch` or network errors — they consume `{data, loading, error}`.

## Inputs

- Phase 1 complete (Context + AsyncStorage working)
- Target API base URL (the app's CF Worker from Phase 4a, or a third-party API for early experimentation — placeholder OK)
- Per-app repo at `C:\Users\deban\dev\mobile-apps\<slug>\`

## Tools/Scripts

- `axios` — HTTP client
- `src/api/client.ts` — singleton axios instance, exported
- `src/api/useApi.ts` — React hook wrapping client calls with loading/error state
- `src/api/types.ts` — `ApiError` envelope

## Steps

1. **Install axios.** `npm install axios`. (Not via `expo install` — axios is pure JS, no native bindings.)
2. **Create the client.** `src/api/client.ts`:
   - `axios.create({ baseURL: process.env.EXPO_PUBLIC_API_BASE_URL, timeout: 10_000 })`
   - Request interceptor: attach `X-App-Version` header from `app.json`'s version
   - Response interceptor: pass through 2xx, normalize errors into `ApiError` shape `{status, code, message, retryable}`
3. **Retry logic on 5xx + network errors.** In the response interceptor, on `error.response?.status >= 500` or `error.code === 'ECONNABORTED'` or `!error.response` (network drop): retry up to 3 attempts with exponential backoff (`500ms`, `1500ms`, `3500ms`). Stop retrying on 4xx (client error, not transient). Do NOT retry on `POST` mutations unless explicitly opted in via a request header (`X-Idempotent: true`).
4. **Loading state hook.** `src/api/useApi.ts`:
   ```ts
   function useApi<T>(fn: () => Promise<T>) {
     // returns {data, loading, error, refetch}
   }
   ```
   Mount → call `fn` → set loading false. Expose `refetch()` for pull-to-refresh.
5. **Error catch wrapper.** Top-level `<ErrorBoundary>` component in `App.tsx` catches unhandled promise rejections (via `setupGlobalErrorHandler()` in client.ts) and shows a recoverable banner instead of a white screen.
6. **Environment config.** Add `EXPO_PUBLIC_API_BASE_URL` to `.env.example` and read via `process.env.EXPO_PUBLIC_API_BASE_URL` (Expo's runtime env convention — `EXPO_PUBLIC_` prefix is required for client bundles).
7. **Smoke test.** Point client at `https://httpbin.org/status/200`, confirm success. Point at `https://httpbin.org/status/500`, confirm 3 retries logged + final error envelope. Point at unreachable host, confirm timeout + retries + error.
8. **Commit.** `git commit -m "phase 2 — axios client with retry + loading UX"`.

## Outputs

- `src/api/client.ts` — axios singleton with interceptors + retry
- `src/api/useApi.ts` — React hook
- `src/api/types.ts` — `ApiError` envelope
- Every future screen imports `useApi`, never raw axios

## Edge Cases

- **Timeout.** 10s default. Slow networks (subway, 3G) need 15-20s for cold-start CF Workers; expose `timeout` override per-call.
- **Network drop mid-request.** axios reports as `error.code === 'ERR_NETWORK'`. Treat as retryable. After 3 failed retries, surface "you're offline" to the user, not "500 Internal Server Error".
- **Malformed response.** Server returns 200 with non-JSON body or invalid JSON. axios throws on parse → wrap in `ApiError({code: 'PARSE_FAIL'})`. Don't crash the screen.
- **Idempotency on retries.** Retrying a POST that already succeeded server-side creates duplicates. The CF Worker's idempotency-key KV (Phase 4a) catches this server-side; client opts in with `X-Idempotent: true`. Default GET requests are safe to retry.
- **Race condition: rapid refetch.** User pulls-to-refresh 3x in 500ms → 3 in-flight requests, last one's response may not be the last one written. Use `AbortController` per `useApi` call; cancel prior on refetch.
- **CORS in dev.** Expo dev server runs at `exp://192.168.x.x:8081`, the API may reject. Set permissive CORS in dev Worker, strict in prod.
- **`EXPO_PUBLIC_` prefix.** Without it, the env var is bundled but unreachable at runtime — common silent failure.

## Exit Criteria

The directive is "done" when ALL of these hold (each must be machine-verifiable):

- `src/api/client.ts` exists and exports an axios singleton with `baseURL`, `timeout`, and at least one response interceptor.
- `src/api/useApi.ts` exists and exports a hook returning `{data, loading, error, refetch}`.
- `src/api/types.ts` exists and exports an `ApiError` type with at least `status`, `code`, and `message` fields.
- Smoke test against `https://httpbin.org/status/200` exits without error (2xx response received).
- Smoke test against `https://httpbin.org/status/500` confirms retry logic fired: console shows at least 2 retry attempts before final error envelope returned.
- `EXPO_PUBLIC_API_BASE_URL` is documented in `.env.example` (and set in `.env` for dev).
- Phase 2 commit exists: `git log --oneline` includes a commit with "phase 2".

If any predicate fails, fix before claiming Phase 2 complete. Do NOT wire screens to real API calls until the retry and error-envelope logic is verified.

## Notes

- Never let screens see raw axios errors. Always go through `useApi` → `ApiError`.
- Exponential-backoff base = 500ms, factor = 2 (the spec says 500/1500/3500; that's 500 + 1000 + 2000 jitter or 500 * 1/3/7 — pick one and document in client.ts).
- Phase 4a's CF Worker is the natural endpoint, but Phase 2 can target any API for early proof-of-life. Don't block Phase 2 on Phase 4a.
- Anneal classic mode runs after this phase via the `/mobile-app` skill.
