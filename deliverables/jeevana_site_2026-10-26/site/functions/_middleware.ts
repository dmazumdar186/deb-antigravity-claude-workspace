// Never serve sources: 404 for /wrangler.toml, /functions/*, any *.ts and /research/*.
export const onRequest: PagesFunction = async ({ request, next }) => {
  const p = new URL(request.url).pathname.toLowerCase();
  if (p === '/wrangler.toml' || p.startsWith('/functions/') || p.startsWith('/research/') || p.endsWith('.ts') || p.endsWith('.toml')) {
    return new Response('Not found', { status: 404, headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' } });
  }
  return next();
};
