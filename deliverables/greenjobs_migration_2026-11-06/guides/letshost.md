# LetsHost: your steps (greenjobs.co.uk)

For Diana. Use your own login. Never share your password.
LetsHost is where greenjobs.co.uk is registered. Its nameservers today are on dnsireland.
A nameserver is the address book that tells the internet where your website and email live. Cloudflare will give us {NS1} and {NS2}.
Note: LetsHost's older help pages say they are out of date and point to https://billing.letshost.ie/index.php?rp=/knowledgebase (page read 2026-11-20). Menu names may differ.

## A. Add a recovery email (on a different domain)
Use {RECOVERY_EMAIL}, NOT an @greenjobs.co.uk address.
Due by: {DATE}
1. UNVERIFIED — confirm on screen. LetsHost's help (https://kb.letshost.ie/ive-lost-access-to-my-letshost-account-what-can-i-do/, search summary 2026-11-20; page returned 503) says the login email is the address that gets LetsHost emails, and there is a Forgot Password link. No recovery-email or two-step setup is documented.
2. Suggested, unverified: log in to the client area, open your account details, and check the login email is {RECOVERY_EMAIL} or an address not on greenjobs.co.uk. UNVERIFIED — confirm on screen.

## B. Download the current DNS records
Due by: {DATE}
The records live on dnsireland nameservers, which LetsHost uses.
1. UNVERIFIED — confirm on screen. No official LetsHost page found that shows a DNS export or DNS editor.
2. Fallback: log in, look for a DNS or zone page for greenjobs.co.uk (UNVERIFIED — confirm on screen), and take screenshots of every record, scrolling down. If there is no such page, open a ticket and ask LetsHost to send the full zone file: https://www.letshostbilling.com/submitticket.php (ticket link from https://kb.letshost.ie/how-do-i-change-my-domains-nameservers/, read 2026-11-20).

## C. Change the nameservers
Due by: {DATE}
All steps from https://kb.letshost.ie/how-do-i-change-my-domains-nameservers/ (read 2026-11-20, legacy page):
1. Log in to your LetsHost client area.
2. Menu **Domains** then **My Domains**.
3. Open the blue dropdown for greenjobs.co.uk and choose **Manage Nameservers**.
4. Write down or screenshot the current nameservers shown.
5. Enter {NS1} and {NS2}, and clear any other nameserver boxes (UNVERIFIED — confirm on screen whether extra boxes must be emptied). Save.
6. If it says the domain is locked: open the **Registrar Lock** tab, click **Disable Registrar Lock**, make the change, then turn the lock back on afterwards (the page advises re-enabling it). Only do this if the error appears.

Do NOT touch: MX or email settings, renewal, transfer or EPP codes, and leave Registrar Lock on unless step 6 forces you.

## Notes
- Confirmation code by email? The page does not mention one. UNVERIFIED — confirm on screen.
- How long? "Most DNS changes finish within 24-48 hours", rarely up to 72 hours (same page).
- Undo: same screen, put the old nameservers back:
  - ns5.dnsireland.com
  - ns6.dnsireland.com
  - ns7.dnsireland.ie
  (Source: ZONE_INVENTORY_2026-11-20.md.)
