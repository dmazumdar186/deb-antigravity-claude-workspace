// Inline fallback pages for the preview host. Kept small and dependency-free
// since they render straight out of the Worker (no R2 round-trip needed for
// the 404/410/expired states, though an R2 _system/expired.html can override
// the expired page — see index.ts).

function page(title: string, heading: string, body: string): string {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>${title}</title>
<style>
  :root { color-scheme: light dark; }
  body {
    margin: 0;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    box-sizing: border-box;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f4f1ea;
    color: #1a1a1a;
  }
  .card {
    max-width: 480px;
    text-align: center;
  }
  h1 {
    font-size: 1.4rem;
    margin: 0 0 12px;
  }
  p {
    font-size: 1rem;
    line-height: 1.5;
    color: #444;
  }
</style>
</head>
<body>
  <div class="card">
    <h1>${heading}</h1>
    ${body}
  </div>
</body>
</html>
`;
}

export function notFoundPage(): string {
  return page(
    "Not found",
    "Preview not found",
    "<p>This preview link doesn't exist or has been taken down.</p>"
  );
}

export function takedownPage(): string {
  return page(
    "Removed",
    "This concept preview has been removed.",
    "<p>The business owner asked for it to be taken down. This link no longer serves any content.</p>"
  );
}

export function expiredPage(): string {
  return page(
    "Preview expired",
    "This concept preview has expired.",
    "<p>This concept preview has expired. Reply to the original email and I'll reactivate it.</p>"
  );
}

export function removeConfirmForm(host: string): string {
  return page(
    "Remove this preview",
    "Remove this concept preview?",
    `<p>This takes the preview offline immediately and we won't contact you again.</p>
    <form method="POST" action="/remove">
      <input type="hidden" name="confirm" value="1">
      <button type="submit" style="padding:10px 20px;font-size:1rem;border-radius:6px;border:1px solid #999;background:#fff;cursor:pointer;">
        Remove ${host}
      </button>
    </form>`
  );
}

export function removeConfirmedPage(): string {
  return page(
    "Removed",
    "Removed.",
    "<p>You won't hear from ProdCraft again.</p>"
  );
}
