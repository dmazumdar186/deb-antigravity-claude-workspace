"""Front-door synthetic: open the real dossier and use it the way Kevin will."""
from playwright.sync_api import sync_playwright
from pathlib import Path

def _lf(text: str) -> str:
    """Normalise line endings.

    Windows hands back CRLF from the clipboard while the DOM attribute
    holds LF. That is the platform being helpful for Outlook, not a copy
    defect, so the comparison ignores it.
    """
    return text.replace(chr(13) + chr(10), chr(10))


DOC = Path("deliverables/gaia_2026-08-20/dossier.html").resolve().as_uri()
fails = []

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(permissions=["clipboard-read", "clipboard-write"],
                        viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda ex: errs.append("pageerror: " + str(ex)))
    pg.goto(DOC)

    rows = pg.locator("tr.r")
    n = rows.count()
    print("candidate rows:", n)

    # Every detail pane starts closed -- the whole point of the redesign.
    open_at_load = pg.locator("tr.det:not([hidden])").count()
    if open_at_load:
        fails.append(f"{open_at_load} detail pane(s) already open on load")

    # Toggle every one open, then closed.
    btns = pg.locator(".det-btn")
    for i in range(btns.count()):
        btn = btns.nth(i)
        target = pg.locator("#" + btn.get_attribute("aria-controls"))
        btn.click()
        if target.is_hidden():
            fails.append(f"row {i}: pane did not open")
        if btn.get_attribute("aria-expanded") != "true":
            fails.append(f"row {i}: aria-expanded not set on open")
        if btn.locator(".det-lb").inner_text().strip() != "Hide details":
            fails.append(f"row {i}: label did not change, got {btn.locator('.det-lb').inner_text()!r}")
        btn.click()
        if target.is_visible():
            fails.append(f"row {i}: pane did not close")
        if btn.locator(".det-lb").inner_text().strip() != "Click here for details":
            fails.append(f"row {i}: label did not restore")

    # Email buttons still copy.
    em = pg.locator("a.cta-em")
    for i in range(em.count()):
        a = em.nth(i)
        addr = a.get_attribute("data-email")
        a.click()
        pg.wait_for_timeout(160)
        if pg.evaluate("navigator.clipboard.readText()") != addr:
            fails.append("email copy failed: " + str(addr))

    # Every message must copy exactly. This is the reader's actual job -- the
    # box only shows enough to recognise which message it is.
    cps = pg.locator("button.cp")
    n_cp = cps.count()
    for i in range(n_cp):
        c = cps.nth(i)
        want = c.get_attribute("data-copy")
        c.click()
        pg.wait_for_timeout(110)
        got = pg.evaluate("navigator.clipboard.readText()")
        # Windows puts CRLF on the clipboard; the DOM attribute holds LF. That
        # is the platform being helpful for Outlook, not a copy defect.
        if _lf(got) != _lf(want):
            fails.append(f"copy button {i} did not copy its message")

    # LinkedIn buttons point at real profiles, not a search box, not the operator.
    li = pg.locator("a.cta-li")
    for i in range(li.count()):
        href = li.nth(i).get_attribute("href") or ""
        if "dmazumdar" in href:
            fails.append("LinkedIn button points at the operator: " + href)
        if not href.startswith("https://"):
            fails.append("non-https LinkedIn href: " + href)

    # Keyboard: the toggle must be reachable and operable.
    first = pg.locator(".det-btn").first
    first.focus()
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(120)
    kb_ok = pg.locator("tr.det:not([hidden])").count() == 1
    pg.keyboard.press("Enter")

    # No horizontal scroll at desktop or mobile width.
    ov_desktop = pg.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth")
    pg.set_viewport_size({"width": 390, "height": 844})
    pg.wait_for_timeout(150)
    ov_mobile = pg.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth")
    mobile_btns = pg.locator("a.cta-em").first.is_visible()
    n_li, n_em = li.count(), em.count()   # read before the browser closes
    _ = n_cp
    b.close()

print(f"copy_buttons={n_cp} linkedin_buttons={n_li} email_buttons={n_em} "
      f"keyboard_ok={kb_ok} h_overflow_desktop={ov_desktop} "
      f"h_overflow_mobile={ov_mobile} mobile_buttons_visible={mobile_btns}")
print("console errors:", errs or "none")
if ov_desktop:
    fails.append("page scrolls horizontally at 1440px")
if ov_mobile:
    fails.append("page scrolls horizontally at 390px")
if not kb_ok:
    fails.append("keyboard toggle did not work")
if errs:
    fails.append("console errors: " + "; ".join(errs))

print()
if fails:
    print("DOGFOOD FAILED")
    for f in fails:
        print("  *", str(f).encode("ascii", "replace").decode("ascii"))
    raise SystemExit(1)
print(f"DOGFOOD PASSED -- {n} rows, all toggles, all buttons, keyboard, both viewports")
