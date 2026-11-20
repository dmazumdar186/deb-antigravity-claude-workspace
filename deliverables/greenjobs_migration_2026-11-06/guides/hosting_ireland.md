# Hosting Ireland: your steps (greenjobs.ie)

For Diana. Use your own login. Never share your password with anyone, including us.
Log in at https://clients.hostingireland.ie/clientarea.php (read 2026-11-20 in the official article, see SOURCES.md).
A nameserver is the address book that tells the internet where your website and email live. Cloudflare will give us two new ones: {NS1} and {NS2}.

## A. Add a recovery email (on a different domain)
Pick an address that is NOT @greenjobs.ie: {RECOVERY_EMAIL}.
Due by: {DATE}
1. UNVERIFIED — confirm on screen. (Hosting Ireland's help pages searched on 2026-11-20 show no article for this.) Look in the client area for your name or "Account Details" or "Contact Details" and add {RECOVERY_EMAIL}.
2. UNVERIFIED — confirm on screen. Save, then check that {RECOVERY_EMAIL} receives a test message.

## B. Download the current DNS records
DNS records are the settings that point your web and email to the right places.
Due by: {DATE}
1. Log in at https://clients.hostingireland.ie/clientarea.php. (Read 2026-11-20, https://clients.hostingireland.ie/index.php/knowledgebase/2231/DNS-Record-and-Nameserver-Amendments.html)
2. Top menu: **Domain** then **My Domains**. (same article, 2026-11-20)
3. Find greenjobs.ie and click **Manage Domain**. (same article)
4. Under **Management Tools** click **DNS Manager**. This shows the zone file (the full list of records). (same article)
5. Export: UNVERIFIED — confirm on screen. The article does not mention an export button.
6. Fallback: take clear screenshots of every page of the list, scrolling down, and save them. Send them to Debanjan.
Note from the article: this only works while the domain uses Hosting Ireland's nameservers (it does today).

## C. Change the nameservers
Due by: {DATE}
1. Log in, then **Domain** then **My Domains** then **Manage Domain** for greenjobs.ie. (2026-11-20, same article)
2. Find the nameserver details. The article says nameservers can be changed "from the same location". Exact button name: UNVERIFIED — confirm on screen.
3. Replace all four current entries with {NS1} and {NS2} only. Exact fields: UNVERIFIED — confirm on screen.
4. Save. Take a screenshot of the old values BEFORE you save.

Do NOT touch: MX or any email settings, Autorenew/renewal, any domain lock or transfer settings, hosting or mailbox settings.

## Notes
- Confirmation code by email? Not mentioned in the article. UNVERIFIED — confirm on screen.
- How long? The article does not say. UNVERIFIED — confirm on screen. (Ask Hosting Ireland. Allow up to 48 hours as a precaution; this is our estimate, not from their docs.)
- .ie domains: IEDR registers the change. Another provider, LetsHost, says .ie changes only apply after an IEDR reload (10:00, 12:00, 17:00, 22:00 daily) and the new nameservers must already hold the zone (https://www.letshost.ie/blog/why-am-i-having-issues-repointing-dns-for-a-ie-domain/, via search summary 2026-11-20; page itself returned 503). Not Hosting Ireland's own docs. Cloudflare must have the zone set up first.
- Undo: put the old nameservers back (same screen):
  - ns1.webhostingireland.ie
  - ns2.webhostingireland.ie
  - ns3.webhostingireland.ie
  - ns4.webhostingireland.eu
  (Source: ZONE_INVENTORY_2026-11-20.md.)
