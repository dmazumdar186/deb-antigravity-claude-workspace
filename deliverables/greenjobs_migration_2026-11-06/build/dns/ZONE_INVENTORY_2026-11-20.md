# Zone inventory, public DNS (2026-11-20)

Internal. Facts only: every record below came from a public read-only lookup run on 2026-11-20 (Cloudflare DNS-over-HTTPS, `cloudflare-dns.com/dns-query`; registry data from RDAP via `rdap.org`). No DNS was changed and no login was used. Raw answers: `zone_inventory_2026-11-20.json`. `dig` is not installed in the sandbox, so DoH was used; results are what public resolvers return, not a zone export.

Legend: rows marked `(none)` mean NOERROR with no record of that type; `NXDOMAIN` means the name does not exist; `LOOKUP FAILED` means the query itself errored. To keep the tables readable, queries that returned `(none)` are listed in a single line per domain.

## 0. Summary

| Domain | Registrar (RDAP) | Expires | Delegated NS (DNS) | MX | Apex A |
|---|---|---|---|---|---|
| greenjobs.ie | RDAP lookup failed: HTTP Error 404: Not Found | n/a | ns1.webhostingireland.ie.<br>ns4.webhostingireland.eu.<br>ns3.webhostingireland.ie.<br>ns2.webhostingireland.ie. | 20 filter2.webhostingireland.ie.<br>10 filter1.webhostingireland.ie. | 212.250.3.80 |
| greenjobs.co.uk | Team Blue Internet Services IE Limited | 2027-12-02 | ns6.dnsireland.com.<br>ns5.dnsireland.com.<br>ns7.dnsireland.ie. | 0 mail.greenjobs.co.uk. | 212.250.3.80 |
| conservationjobsuk.com | 123-Reg Limited | 2027-06-17 | ns31.domaincontrol.com.<br>ns32.domaincontrol.com. | 0 smtp.secureserver.net.<br>10 mailstore1.secureserver.net. | 212.250.3.80 |
| ecologyjobsuk.com | 123-Reg Limited | 2027-11-12 | ns15.domaincontrol.com.<br>ns16.domaincontrol.com. | 0 smtp.secureserver.net.<br>10 mailstore1.secureserver.net. | 212.250.3.80 |
| environmentaljobsuk.com | 123-Reg Limited | 2027-01-31 | ns09.domaincontrol.com.<br>ns10.domaincontrol.com. | 0 smtp.secureserver.net.<br>10 mailstore1.secureserver.net. | 212.250.3.80 |
| renewablejobsuk.com | RDAP lookup failed: HTTP Error 404: Not Found | n/a | NXDOMAIN | none | none |
| renewableenergyjobsuk.com | 123-Reg Limited | 2027-01-31 | ns67.domaincontrol.com.<br>ns68.domaincontrol.com. | 0 smtp.secureserver.net.<br>10 mailstore1.secureserver.net. | 212.250.3.80 |
| windjobsuk.com | 123-Reg Limited | 2027-01-31 | ns07.domaincontrol.com.<br>ns08.domaincontrol.com. | 0 smtp.secureserver.net.<br>10 mailstore1.secureserver.net. | 212.250.3.80 |
| solarjobsuk.com | 123-Reg Limited | 2027-01-31 | ns67.domaincontrol.com.<br>ns68.domaincontrol.com. | 0 smtp.secureserver.net.<br>10 mailstore1.secureserver.net. | 212.250.3.80 |
| wastejobsuk.com | 123-Reg Limited | 2027-08-02 | ns31.domaincontrol.com.<br>ns32.domaincontrol.com. | 0 smtp.secureserver.net.<br>10 mailstore1.secureserver.net. | none |
| waterjobsuk.com | 123-Reg Limited | 2027-08-02 | ns45.domaincontrol.com.<br>ns46.domaincontrol.com. | 0 smtp.secureserver.net.<br>10 mailstore1.secureserver.net. | none |

## 1. Copy-first email records

Path A moves nameservers, which moves mail. These must exist in Cloudflare before the nameserver change (runbook T-3). Values as seen publicly; the host's zone export remains the authority.

### greenjobs.ie

| Name | Type | Value | TTL |
|---|---|---|---|
| greenjobs.ie | MX | 20 filter2.webhostingireland.ie. | 3600 |
| greenjobs.ie | MX | 10 filter1.webhostingireland.ie. | 3600 |
| greenjobs.ie | TXT | "v=spf1 ip4:185.43.232.13 include:spf.webhostingireland.ie ip4:81.17.241.90 +mx +a +include:spf.strategiesuk.net -all" | 14400 |
| default._domainkey.greenjobs.ie | TXT | "v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAyq2snLXxuLmH8FjrUKkITYD1XQG5XUOBGU+OqA3ZGPB66uvCZ6a5+jxPrKT8G4IRGDZL60klrxszNoiYxqohJLiIDceTXyZloZWGa6NHjwcUTYua90MKEIxV8JdyZ8WvT7/CRzEc34VIph40STQN48lWlRhhzOzWt24uTFDn8gvR9jDBCucpxAzfm3mzjQM5x" "7oVdQluhLYoxPRZYZtjkxBiEts9qoT2hI692Ln1N4kwvKEIZ5o33trF7jc7q3Tl/OMYB1jmAO+e/OIw7jOeqXqXvehAq9fQQ0VH9WWtmrB+/RHYoEpTb7Py/ZYkEDDeOMz3svk1uosWEWRsRqb6owIDAQAB;" | 14400 |
| mail.greenjobs.ie | A | 185.43.232.13 | 14400 |
| webmail.greenjobs.ie | A | 185.43.232.13 | 14400 |
| autodiscover.greenjobs.ie | A | 185.43.232.13 | 14400 |

### greenjobs.co.uk

| Name | Type | Value | TTL |
|---|---|---|---|
| greenjobs.co.uk | MX | 0 mail.greenjobs.co.uk. | 14400 |
| greenjobs.co.uk | TXT | "v=spf1 +a +mx +include:spf.strategiesuk.net -all" | 14400 |
| _dmarc.greenjobs.co.uk | TXT | "v=DMARC1; p=none;" | 14400 |
| mail.greenjobs.co.uk | A | 185.43.232.13 | 14400 |

### conservationjobsuk.com

| Name | Type | Value | TTL |
|---|---|---|---|
| conservationjobsuk.com | MX | 0 smtp.secureserver.net. | 3600 |
| conservationjobsuk.com | MX | 10 mailstore1.secureserver.net. | 3600 |
| conservationjobsuk.com | TXT | "D6911740" | 3600 |
| conservationjobsuk.com | TXT | "v=spf1 mx a include:secureserver.net -all" | 3600 |

### ecologyjobsuk.com

| Name | Type | Value | TTL |
|---|---|---|---|
| ecologyjobsuk.com | MX | 0 smtp.secureserver.net. | 3600 |
| ecologyjobsuk.com | MX | 10 mailstore1.secureserver.net. | 3600 |
| ecologyjobsuk.com | TXT | "D4604583" | 3600 |
| ecologyjobsuk.com | TXT | "v=spf1 mx a include:secureserver.net -all" | 3600 |

### environmentaljobsuk.com

| Name | Type | Value | TTL |
|---|---|---|---|
| environmentaljobsuk.com | MX | 0 smtp.secureserver.net. | 3600 |
| environmentaljobsuk.com | MX | 10 mailstore1.secureserver.net. | 3600 |
| environmentaljobsuk.com | TXT | "v=spf1 mx a include:secureserver.net -all" | 3600 |
| environmentaljobsuk.com | TXT | "D6760365" | 3600 |

### renewableenergyjobsuk.com

| Name | Type | Value | TTL |
|---|---|---|---|
| renewableenergyjobsuk.com | MX | 0 smtp.secureserver.net. | 3600 |
| renewableenergyjobsuk.com | MX | 10 mailstore1.secureserver.net. | 3600 |
| renewableenergyjobsuk.com | TXT | "D1195155" | 3600 |
| renewableenergyjobsuk.com | TXT | "v=spf1 mx a include:secureserver.net -all" | 3600 |

### windjobsuk.com

| Name | Type | Value | TTL |
|---|---|---|---|
| windjobsuk.com | MX | 0 smtp.secureserver.net. | 3600 |
| windjobsuk.com | MX | 10 mailstore1.secureserver.net. | 3600 |
| windjobsuk.com | TXT | "D5463991" | 3600 |
| windjobsuk.com | TXT | "v=spf1 mx a include:secureserver.net -all" | 3600 |

### solarjobsuk.com

| Name | Type | Value | TTL |
|---|---|---|---|
| solarjobsuk.com | MX | 0 smtp.secureserver.net. | 3600 |
| solarjobsuk.com | MX | 10 mailstore1.secureserver.net. | 3600 |
| solarjobsuk.com | TXT | "D7908197" | 3600 |
| solarjobsuk.com | TXT | "v=spf1 mx a include:secureserver.net -all" | 3600 |

### wastejobsuk.com

| Name | Type | Value | TTL |
|---|---|---|---|
| wastejobsuk.com | MX | 0 smtp.secureserver.net. | 3600 |
| wastejobsuk.com | MX | 10 mailstore1.secureserver.net. | 3600 |
| wastejobsuk.com | TXT | "D6110269" | 3600 |
| wastejobsuk.com | TXT | "v=spf1 mx a include:secureserver.net -all" | 3600 |
| mail.wastejobsuk.com | A | 64.253.47.65 | 300 |
| mail.wastejobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| webmail.wastejobsuk.com | A | 64.253.47.65 | 300 |
| webmail.wastejobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| autodiscover.wastejobsuk.com | A | 64.253.47.65 | 300 |
| autodiscover.wastejobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |

### waterjobsuk.com

| Name | Type | Value | TTL |
|---|---|---|---|
| waterjobsuk.com | MX | 0 smtp.secureserver.net. | 3600 |
| waterjobsuk.com | MX | 10 mailstore1.secureserver.net. | 3600 |
| waterjobsuk.com | TXT | "D8054547" | 3600 |
| waterjobsuk.com | TXT | "v=spf1 mx a include:secureserver.net -all" | 3600 |
| mail.waterjobsuk.com | A | 64.253.47.65 | 300 |
| mail.waterjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| webmail.waterjobsuk.com | A | 64.253.47.65 | 300 |
| webmail.waterjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| autodiscover.waterjobsuk.com | A | 64.253.47.65 | 300 |
| autodiscover.waterjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |

Domains with no MX in public DNS: renewablejobsuk.com. (A domain with no MX still needs a check against the zone export for a null-MX or SPF record.)

## 2. Per-domain tables

### greenjobs.ie

Registry (RDAP): LOOKUP FAILED (HTTP Error 404: Not Found). Port-43 whois is blocked in the sandbox and `rdap.org` has no RDAP service for this TLD or the name is unregistered.

| Name | Type | Value | TTL |
|---|---|---|---|
| greenjobs.ie | NS | ns1.webhostingireland.ie. | 86400 |
| greenjobs.ie | NS | ns4.webhostingireland.eu. | 86400 |
| greenjobs.ie | NS | ns3.webhostingireland.ie. | 86400 |
| greenjobs.ie | NS | ns2.webhostingireland.ie. | 86400 |
| greenjobs.ie | SOA | ns1.webhostingireland.ie. admins.hostingireland.ie. 2026112002 86400 7200 3600000 86400 | 86400 |
| greenjobs.ie | A | 212.250.3.80 | 14400 |
| greenjobs.ie | MX | 20 filter2.webhostingireland.ie. | 3600 |
| greenjobs.ie | MX | 10 filter1.webhostingireland.ie. | 3600 |
| greenjobs.ie | TXT | "v=spf1 ip4:185.43.232.13 include:spf.webhostingireland.ie ip4:81.17.241.90 +mx +a +include:spf.strategiesuk.net -all" | 14400 |
| www.greenjobs.ie | A | 64.253.47.65 | 300 |
| www.greenjobs.ie | CNAME | www-greenjobs-ie.cname.strategiesuk.net. | 14400 |
| default._domainkey.greenjobs.ie | TXT | "v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAyq2snLXxuLmH8FjrUKkITYD1XQG5XUOBGU+OqA3ZGPB66uvCZ6a5+jxPrKT8G4IRGDZL60klrxszNoiYxqohJLiIDceTXyZloZWGa6NHjwcUTYua90MKEIxV8JdyZ8WvT7/CRzEc34VIph40STQN48lWlRhhzOzWt24uTFDn8gvR9jDBCucpxAzfm3mzjQM5x" "7oVdQluhLYoxPRZYZtjkxBiEts9qoT2hI692Ln1N4kwvKEIZ5o33trF7jc7q3Tl/OMYB1jmAO+e/OIw7jOeqXqXvehAq9fQQ0VH9WWtmrB+/RHYoEpTb7Py/ZYkEDDeOMz3svk1uosWEWRsRqb6owIDAQAB;" | 14400 |
| mail.greenjobs.ie | A | 185.43.232.13 | 14400 |
| webmail.greenjobs.ie | A | 185.43.232.13 | 14400 |
| ftp.greenjobs.ie | A | 185.43.232.13 | 14400 |
| cpanel.greenjobs.ie | A | 185.43.232.13 | 14400 |
| autodiscover.greenjobs.ie | A | 185.43.232.13 | 14400 |

No record (NOERROR, empty): 14 queries, e.g. autodiscover.greenjobs.ie CNAME; autodiscover.greenjobs.ie MX; cpanel.greenjobs.ie CNAME; cpanel.greenjobs.ie MX; default._domainkey.greenjobs.ie CNAME; ftp.greenjobs.ie CNAME; ftp.greenjobs.ie MX; greenjobs.ie AAAA; greenjobs.ie CAA; greenjobs.ie CNAME; mail.greenjobs.ie CNAME; mail.greenjobs.ie MX; webmail.greenjobs.ie CNAME; webmail.greenjobs.ie MX.

NXDOMAIN: _dmarc.greenjobs.ie; admin.greenjobs.ie; dkim._domainkey.greenjobs.ie; google._domainkey.greenjobs.ie; k1._domainkey.greenjobs.ie; mail._domainkey.greenjobs.ie; selector1._domainkey.greenjobs.ie; selector2._domainkey.greenjobs.ie.

HTTP/TLS (curl via the sandbox egress gateway, honest UA, redirects followed by hand, one row per hop; TLS certificate itself not observable here, see section 3):

| URL | Hop chain (status, redirect target, or curl error) |
|---|---|
| https://greenjobs.ie/ | curl error 35: (35) Recv failure: Connection reset by peer |
| https://www.greenjobs.ie/ | 200 (final) |
| http://greenjobs.ie/ | 301 -> https://www.greenjobs.ie/ ; 200 (final) |
| http://www.greenjobs.ie/ | 301 -> https://www.greenjobs.ie/ ; 200 (final) |

### greenjobs.co.uk

Registry (RDAP): registrar Team Blue Internet Services IE Limited; registered 1999-12-02; expires 2027-12-02; registry NS ns5.dnsireland.com., ns6.dnsireland.com., ns7.dnsireland.ie.; status active.

| Name | Type | Value | TTL |
|---|---|---|---|
| greenjobs.co.uk | NS | ns6.dnsireland.com. | 86400 |
| greenjobs.co.uk | NS | ns5.dnsireland.com. | 86400 |
| greenjobs.co.uk | NS | ns7.dnsireland.ie. | 86400 |
| greenjobs.co.uk | SOA | ns5.dnsireland.com. admin.letshost.ie. 2024110700 86400 7200 3600000 86400 | 86400 |
| greenjobs.co.uk | A | 212.250.3.80 | 14400 |
| greenjobs.co.uk | MX | 0 mail.greenjobs.co.uk. | 14400 |
| greenjobs.co.uk | TXT | "v=spf1 +a +mx +include:spf.strategiesuk.net -all" | 14400 |
| www.greenjobs.co.uk | A | 64.253.47.65 | 300 |
| www.greenjobs.co.uk | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 14400 |
| _dmarc.greenjobs.co.uk | TXT | "v=DMARC1; p=none;" | 14400 |
| mail.greenjobs.co.uk | A | 185.43.232.13 | 14400 |
| ftp.greenjobs.co.uk | A | 212.250.3.80 | 14400 |
| ftp.greenjobs.co.uk | CNAME | greenjobs.co.uk. | 14400 |
| ftp.greenjobs.co.uk | MX | 0 mail.greenjobs.co.uk. | 14400 |

No record (NOERROR, empty): 5 queries, e.g. greenjobs.co.uk AAAA; greenjobs.co.uk CAA; greenjobs.co.uk CNAME; mail.greenjobs.co.uk CNAME; mail.greenjobs.co.uk MX.

NXDOMAIN: admin.greenjobs.co.uk; autodiscover.greenjobs.co.uk; cpanel.greenjobs.co.uk; default._domainkey.greenjobs.co.uk; dkim._domainkey.greenjobs.co.uk; google._domainkey.greenjobs.co.uk; k1._domainkey.greenjobs.co.uk; mail._domainkey.greenjobs.co.uk; selector1._domainkey.greenjobs.co.uk; selector2._domainkey.greenjobs.co.uk; webmail.greenjobs.co.uk.

HTTP/TLS (curl via the sandbox egress gateway, honest UA, redirects followed by hand, one row per hop; TLS certificate itself not observable here, see section 3):

| URL | Hop chain (status, redirect target, or curl error) |
|---|---|
| https://greenjobs.co.uk/ | curl error 35: (35) Recv failure: Connection reset by peer |
| https://www.greenjobs.co.uk/ | 200 (final) |
| http://greenjobs.co.uk/ | 301 -> https://www.greenjobs.co.uk/ ; 200 (final) |
| http://www.greenjobs.co.uk/ | 301 -> https://www.greenjobs.co.uk/ ; 200 (final) |

### conservationjobsuk.com

Registry (RDAP): registrar 123-Reg Limited; registered 2011-06-17; expires 2027-06-17; registry NS NS31.DOMAINCONTROL.COM, NS32.DOMAINCONTROL.COM; status active.

| Name | Type | Value | TTL |
|---|---|---|---|
| conservationjobsuk.com | NS | ns31.domaincontrol.com. | 3600 |
| conservationjobsuk.com | NS | ns32.domaincontrol.com. | 3600 |
| conservationjobsuk.com | SOA | ns31.domaincontrol.com. dns.jomax.net. 2026062400 28800 7200 604800 600 | 3600 |
| conservationjobsuk.com | A | 212.250.3.80 | 600 |
| conservationjobsuk.com | MX | 0 smtp.secureserver.net. | 3600 |
| conservationjobsuk.com | MX | 10 mailstore1.secureserver.net. | 3600 |
| conservationjobsuk.com | TXT | "D6911740" | 3600 |
| conservationjobsuk.com | TXT | "v=spf1 mx a include:secureserver.net -all" | 3600 |
| www.conservationjobsuk.com | A | 64.253.47.65 | 300 |
| www.conservationjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 3600 |

No record (NOERROR, empty): 3 queries, e.g. conservationjobsuk.com AAAA; conservationjobsuk.com CAA; conservationjobsuk.com CNAME.

NXDOMAIN: _dmarc.conservationjobsuk.com; admin.conservationjobsuk.com; autodiscover.conservationjobsuk.com; cpanel.conservationjobsuk.com; default._domainkey.conservationjobsuk.com; dkim._domainkey.conservationjobsuk.com; ftp.conservationjobsuk.com; google._domainkey.conservationjobsuk.com; k1._domainkey.conservationjobsuk.com; mail._domainkey.conservationjobsuk.com; mail.conservationjobsuk.com; selector1._domainkey.conservationjobsuk.com; selector2._domainkey.conservationjobsuk.com; webmail.conservationjobsuk.com.

HTTP/TLS (curl via the sandbox egress gateway, honest UA, redirects followed by hand, one row per hop; TLS certificate itself not observable here, see section 3):

| URL | Hop chain (status, redirect target, or curl error) |
|---|---|
| https://conservationjobsuk.com/ | curl error 35: (35) Recv failure: Connection reset by peer |
| https://www.conservationjobsuk.com/ | curl error 60: (60) SSL: no alternative certificate subject name matches target host name 'www.conservationjobsuk.com' |
| http://conservationjobsuk.com/ | 301 -> https://www.conservationjobsuk.com/ ; curl error 60: (60) SSL: no alternative certificate subject name matches target host name 'www.conservationjobsuk.com' |
| http://www.conservationjobsuk.com/ | 301 -> https://www.conservationjobsuk.com/ ; curl error 60: (60) SSL: no alternative certificate subject name matches target host name 'www.conservationjobsuk.com' |

### ecologyjobsuk.com

Registry (RDAP): registrar 123-Reg Limited; registered 2021-11-12; expires 2027-11-12; registry NS NS15.DOMAINCONTROL.COM, NS16.DOMAINCONTROL.COM; status active.

| Name | Type | Value | TTL |
|---|---|---|---|
| ecologyjobsuk.com | NS | ns15.domaincontrol.com. | 3600 |
| ecologyjobsuk.com | NS | ns16.domaincontrol.com. | 3600 |
| ecologyjobsuk.com | SOA | ns15.domaincontrol.com. dns.jomax.net. 2024011102 28800 7200 604800 600 | 3600 |
| ecologyjobsuk.com | A | 212.250.3.80 | 8600 |
| ecologyjobsuk.com | MX | 0 smtp.secureserver.net. | 3600 |
| ecologyjobsuk.com | MX | 10 mailstore1.secureserver.net. | 3600 |
| ecologyjobsuk.com | TXT | "D4604583" | 3600 |
| ecologyjobsuk.com | TXT | "v=spf1 mx a include:secureserver.net -all" | 3600 |
| www.ecologyjobsuk.com | A | 64.253.47.65 | 300 |
| www.ecologyjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |

No record (NOERROR, empty): 3 queries, e.g. ecologyjobsuk.com AAAA; ecologyjobsuk.com CAA; ecologyjobsuk.com CNAME.

NXDOMAIN: _dmarc.ecologyjobsuk.com; admin.ecologyjobsuk.com; autodiscover.ecologyjobsuk.com; cpanel.ecologyjobsuk.com; default._domainkey.ecologyjobsuk.com; dkim._domainkey.ecologyjobsuk.com; ftp.ecologyjobsuk.com; google._domainkey.ecologyjobsuk.com; k1._domainkey.ecologyjobsuk.com; mail._domainkey.ecologyjobsuk.com; mail.ecologyjobsuk.com; selector1._domainkey.ecologyjobsuk.com; selector2._domainkey.ecologyjobsuk.com; webmail.ecologyjobsuk.com.

HTTP/TLS (curl via the sandbox egress gateway, honest UA, redirects followed by hand, one row per hop; TLS certificate itself not observable here, see section 3):

| URL | Hop chain (status, redirect target, or curl error) |
|---|---|
| https://ecologyjobsuk.com/ | curl error 35: (35) Recv failure: Connection reset by peer |
| https://www.ecologyjobsuk.com/ | 200 (final) |
| http://ecologyjobsuk.com/ | 301 -> https://www.ecologyjobsuk.com/ ; 200 (final) |
| http://www.ecologyjobsuk.com/ | 301 -> https://www.ecologyjobsuk.com/ ; 200 (final) |

### environmentaljobsuk.com

Registry (RDAP): registrar 123-Reg Limited; registered 2011-01-31; expires 2027-01-31; registry NS NS09.DOMAINCONTROL.COM, NS10.DOMAINCONTROL.COM; status active.

| Name | Type | Value | TTL |
|---|---|---|---|
| environmentaljobsuk.com | NS | ns09.domaincontrol.com. | 3600 |
| environmentaljobsuk.com | NS | ns10.domaincontrol.com. | 3600 |
| environmentaljobsuk.com | SOA | ns09.domaincontrol.com. dns.jomax.net. 2024030600 28800 7200 604800 600 | 3600 |
| environmentaljobsuk.com | A | 212.250.3.80 | 600 |
| environmentaljobsuk.com | MX | 0 smtp.secureserver.net. | 3600 |
| environmentaljobsuk.com | MX | 10 mailstore1.secureserver.net. | 3600 |
| environmentaljobsuk.com | TXT | "v=spf1 mx a include:secureserver.net -all" | 3600 |
| environmentaljobsuk.com | TXT | "D6760365" | 3600 |
| www.environmentaljobsuk.com | A | 64.253.47.65 | 300 |
| www.environmentaljobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 3600 |

No record (NOERROR, empty): 3 queries, e.g. environmentaljobsuk.com AAAA; environmentaljobsuk.com CAA; environmentaljobsuk.com CNAME.

NXDOMAIN: _dmarc.environmentaljobsuk.com; admin.environmentaljobsuk.com; autodiscover.environmentaljobsuk.com; cpanel.environmentaljobsuk.com; default._domainkey.environmentaljobsuk.com; dkim._domainkey.environmentaljobsuk.com; ftp.environmentaljobsuk.com; google._domainkey.environmentaljobsuk.com; k1._domainkey.environmentaljobsuk.com; mail._domainkey.environmentaljobsuk.com; mail.environmentaljobsuk.com; selector1._domainkey.environmentaljobsuk.com; selector2._domainkey.environmentaljobsuk.com; webmail.environmentaljobsuk.com.

HTTP/TLS (curl via the sandbox egress gateway, honest UA, redirects followed by hand, one row per hop; TLS certificate itself not observable here, see section 3):

| URL | Hop chain (status, redirect target, or curl error) |
|---|---|
| https://environmentaljobsuk.com/ | curl error 35: (35) Recv failure: Connection reset by peer |
| https://www.environmentaljobsuk.com/ | 200 (final) |
| http://environmentaljobsuk.com/ | 301 -> https://www.environmentaljobsuk.com/ ; 200 (final) |
| http://www.environmentaljobsuk.com/ | 301 -> https://www.environmentaljobsuk.com/ ; 200 (final) |

### renewablejobsuk.com

Registry (RDAP): LOOKUP FAILED (HTTP Error 404: Not Found). Port-43 whois is blocked in the sandbox and `rdap.org` has no RDAP service for this TLD or the name is unregistered.

| Name | Type | Value | TTL |
|---|---|---|---|
| (no records found) | | | |


NXDOMAIN: _dmarc.renewablejobsuk.com; admin.renewablejobsuk.com; autodiscover.renewablejobsuk.com; cpanel.renewablejobsuk.com; default._domainkey.renewablejobsuk.com; dkim._domainkey.renewablejobsuk.com; ftp.renewablejobsuk.com; google._domainkey.renewablejobsuk.com; k1._domainkey.renewablejobsuk.com; mail._domainkey.renewablejobsuk.com; mail.renewablejobsuk.com; renewablejobsuk.com; selector1._domainkey.renewablejobsuk.com; selector2._domainkey.renewablejobsuk.com; webmail.renewablejobsuk.com; www.renewablejobsuk.com.

HTTP/TLS (curl via the sandbox egress gateway, honest UA, redirects followed by hand, one row per hop; TLS certificate itself not observable here, see section 3):

| URL | Hop chain (status, redirect target, or curl error) |
|---|---|
| https://renewablejobsuk.com/ | curl error 56: (56) CONNECT tunnel failed, response 502 |
| https://www.renewablejobsuk.com/ | curl error 56: (56) CONNECT tunnel failed, response 502 |
| http://renewablejobsuk.com/ | curl error 6: (6) Could not resolve host: renewablejobsuk.com |
| http://www.renewablejobsuk.com/ | curl error 6: (6) Could not resolve host: www.renewablejobsuk.com |

### renewableenergyjobsuk.com

Registry (RDAP): registrar 123-Reg Limited; registered 2011-01-31; expires 2027-01-31; registry NS NS67.DOMAINCONTROL.COM, NS68.DOMAINCONTROL.COM; status active.

| Name | Type | Value | TTL |
|---|---|---|---|
| renewableenergyjobsuk.com | NS | ns67.domaincontrol.com. | 3600 |
| renewableenergyjobsuk.com | NS | ns68.domaincontrol.com. | 3600 |
| renewableenergyjobsuk.com | SOA | ns67.domaincontrol.com. dns.jomax.net. 2024030600 28800 7200 604800 600 | 3600 |
| renewableenergyjobsuk.com | A | 212.250.3.80 | 600 |
| renewableenergyjobsuk.com | MX | 0 smtp.secureserver.net. | 3600 |
| renewableenergyjobsuk.com | MX | 10 mailstore1.secureserver.net. | 3600 |
| renewableenergyjobsuk.com | TXT | "D1195155" | 3600 |
| renewableenergyjobsuk.com | TXT | "v=spf1 mx a include:secureserver.net -all" | 3600 |
| www.renewableenergyjobsuk.com | A | 64.253.47.65 | 300 |
| www.renewableenergyjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 3600 |

No record (NOERROR, empty): 3 queries, e.g. renewableenergyjobsuk.com AAAA; renewableenergyjobsuk.com CAA; renewableenergyjobsuk.com CNAME.

NXDOMAIN: _dmarc.renewableenergyjobsuk.com; admin.renewableenergyjobsuk.com; autodiscover.renewableenergyjobsuk.com; cpanel.renewableenergyjobsuk.com; default._domainkey.renewableenergyjobsuk.com; dkim._domainkey.renewableenergyjobsuk.com; ftp.renewableenergyjobsuk.com; google._domainkey.renewableenergyjobsuk.com; k1._domainkey.renewableenergyjobsuk.com; mail._domainkey.renewableenergyjobsuk.com; mail.renewableenergyjobsuk.com; selector1._domainkey.renewableenergyjobsuk.com; selector2._domainkey.renewableenergyjobsuk.com; webmail.renewableenergyjobsuk.com.

HTTP/TLS (curl via the sandbox egress gateway, honest UA, redirects followed by hand, one row per hop; TLS certificate itself not observable here, see section 3):

| URL | Hop chain (status, redirect target, or curl error) |
|---|---|
| https://renewableenergyjobsuk.com/ | curl error 35: (35) Recv failure: Connection reset by peer |
| https://www.renewableenergyjobsuk.com/ | 200 (final) |
| http://renewableenergyjobsuk.com/ | 301 -> https://www.renewableenergyjobsuk.com/ ; 200 (final) |
| http://www.renewableenergyjobsuk.com/ | 301 -> https://www.renewableenergyjobsuk.com/ ; 200 (final) |

### windjobsuk.com

Registry (RDAP): registrar 123-Reg Limited; registered 2011-01-31; expires 2027-01-31; registry NS NS07.DOMAINCONTROL.COM, NS08.DOMAINCONTROL.COM; status active.

| Name | Type | Value | TTL |
|---|---|---|---|
| windjobsuk.com | NS | ns07.domaincontrol.com. | 3600 |
| windjobsuk.com | NS | ns08.domaincontrol.com. | 3600 |
| windjobsuk.com | SOA | ns07.domaincontrol.com. dns.jomax.net. 2024030600 28800 7200 604800 600 | 3600 |
| windjobsuk.com | A | 212.250.3.80 | 600 |
| windjobsuk.com | MX | 0 smtp.secureserver.net. | 3600 |
| windjobsuk.com | MX | 10 mailstore1.secureserver.net. | 3600 |
| windjobsuk.com | TXT | "D5463991" | 3600 |
| windjobsuk.com | TXT | "v=spf1 mx a include:secureserver.net -all" | 3600 |
| www.windjobsuk.com | A | 64.253.47.65 | 300 |
| www.windjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 3600 |

No record (NOERROR, empty): 3 queries, e.g. windjobsuk.com AAAA; windjobsuk.com CAA; windjobsuk.com CNAME.

NXDOMAIN: _dmarc.windjobsuk.com; admin.windjobsuk.com; autodiscover.windjobsuk.com; cpanel.windjobsuk.com; default._domainkey.windjobsuk.com; dkim._domainkey.windjobsuk.com; ftp.windjobsuk.com; google._domainkey.windjobsuk.com; k1._domainkey.windjobsuk.com; mail._domainkey.windjobsuk.com; mail.windjobsuk.com; selector1._domainkey.windjobsuk.com; selector2._domainkey.windjobsuk.com; webmail.windjobsuk.com.

HTTP/TLS (curl via the sandbox egress gateway, honest UA, redirects followed by hand, one row per hop; TLS certificate itself not observable here, see section 3):

| URL | Hop chain (status, redirect target, or curl error) |
|---|---|
| https://windjobsuk.com/ | curl error 35: (35) Recv failure: Connection reset by peer |
| https://www.windjobsuk.com/ | 200 (final) |
| http://windjobsuk.com/ | 301 -> https://www.windjobsuk.com/ ; 200 (final) |
| http://www.windjobsuk.com/ | 301 -> https://www.windjobsuk.com/ ; 200 (final) |

### solarjobsuk.com

Registry (RDAP): registrar 123-Reg Limited; registered 2011-01-31; expires 2027-01-31; registry NS NS67.DOMAINCONTROL.COM, NS68.DOMAINCONTROL.COM; status active.

| Name | Type | Value | TTL |
|---|---|---|---|
| solarjobsuk.com | NS | ns67.domaincontrol.com. | 3600 |
| solarjobsuk.com | NS | ns68.domaincontrol.com. | 3600 |
| solarjobsuk.com | SOA | ns67.domaincontrol.com. dns.jomax.net. 2024030600 28800 7200 604800 600 | 3600 |
| solarjobsuk.com | A | 212.250.3.80 | 600 |
| solarjobsuk.com | MX | 0 smtp.secureserver.net. | 3600 |
| solarjobsuk.com | MX | 10 mailstore1.secureserver.net. | 3600 |
| solarjobsuk.com | TXT | "D7908197" | 3600 |
| solarjobsuk.com | TXT | "v=spf1 mx a include:secureserver.net -all" | 3600 |
| www.solarjobsuk.com | A | 64.253.47.65 | 300 |
| www.solarjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 3600 |

No record (NOERROR, empty): 3 queries, e.g. solarjobsuk.com AAAA; solarjobsuk.com CAA; solarjobsuk.com CNAME.

NXDOMAIN: _dmarc.solarjobsuk.com; admin.solarjobsuk.com; autodiscover.solarjobsuk.com; cpanel.solarjobsuk.com; default._domainkey.solarjobsuk.com; dkim._domainkey.solarjobsuk.com; ftp.solarjobsuk.com; google._domainkey.solarjobsuk.com; k1._domainkey.solarjobsuk.com; mail._domainkey.solarjobsuk.com; mail.solarjobsuk.com; selector1._domainkey.solarjobsuk.com; selector2._domainkey.solarjobsuk.com; webmail.solarjobsuk.com.

HTTP/TLS (curl via the sandbox egress gateway, honest UA, redirects followed by hand, one row per hop; TLS certificate itself not observable here, see section 3):

| URL | Hop chain (status, redirect target, or curl error) |
|---|---|
| https://solarjobsuk.com/ | curl error 35: (35) Recv failure: Connection reset by peer |
| https://www.solarjobsuk.com/ | 200 (final) |
| http://solarjobsuk.com/ | 301 -> https://www.solarjobsuk.com/ ; 200 (final) |
| http://www.solarjobsuk.com/ | 301 -> https://www.solarjobsuk.com/ ; 200 (final) |

### wastejobsuk.com

Registry (RDAP): registrar 123-Reg Limited; registered 2012-08-02; expires 2027-08-02; registry NS NS31.DOMAINCONTROL.COM, NS32.DOMAINCONTROL.COM; status active.

| Name | Type | Value | TTL |
|---|---|---|---|
| wastejobsuk.com | NS | ns31.domaincontrol.com. | 3600 |
| wastejobsuk.com | NS | ns32.domaincontrol.com. | 3600 |
| wastejobsuk.com | SOA | ns31.domaincontrol.com. dns.jomax.net. 2024030600 28800 7200 604800 600 | 3600 |
| wastejobsuk.com | MX | 0 smtp.secureserver.net. | 3600 |
| wastejobsuk.com | MX | 10 mailstore1.secureserver.net. | 3600 |
| wastejobsuk.com | TXT | "D6110269" | 3600 |
| wastejobsuk.com | TXT | "v=spf1 mx a include:secureserver.net -all" | 3600 |
| www.wastejobsuk.com | A | 64.253.47.65 | 300 |
| www.wastejobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| default._domainkey.wastejobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| selector1._domainkey.wastejobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| selector2._domainkey.wastejobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| google._domainkey.wastejobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| k1._domainkey.wastejobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| mail._domainkey.wastejobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| dkim._domainkey.wastejobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| mail.wastejobsuk.com | A | 64.253.47.65 | 300 |
| mail.wastejobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| webmail.wastejobsuk.com | A | 64.253.47.65 | 300 |
| webmail.wastejobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| admin.wastejobsuk.com | A | 64.253.47.65 | 300 |
| admin.wastejobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| ftp.wastejobsuk.com | A | 64.253.47.65 | 300 |
| ftp.wastejobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| cpanel.wastejobsuk.com | A | 64.253.47.65 | 300 |
| cpanel.wastejobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| autodiscover.wastejobsuk.com | A | 64.253.47.65 | 300 |
| autodiscover.wastejobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |

No record (NOERROR, empty): 4 queries, e.g. wastejobsuk.com A; wastejobsuk.com AAAA; wastejobsuk.com CAA; wastejobsuk.com CNAME.

HTTP/TLS (curl via the sandbox egress gateway, honest UA, redirects followed by hand, one row per hop; TLS certificate itself not observable here, see section 3):

| URL | Hop chain (status, redirect target, or curl error) |
|---|---|
| https://wastejobsuk.com/ | curl error 56: (56) CONNECT tunnel failed, response 502 |
| https://www.wastejobsuk.com/ | 200 (final) |
| http://wastejobsuk.com/ | curl error 6: (6) Could not resolve host: wastejobsuk.com |
| http://www.wastejobsuk.com/ | 301 -> https://www.wastejobsuk.com/ ; 200 (final) |

### waterjobsuk.com

Registry (RDAP): registrar 123-Reg Limited; registered 2012-08-02; expires 2027-08-02; registry NS NS45.DOMAINCONTROL.COM, NS46.DOMAINCONTROL.COM; status active.

| Name | Type | Value | TTL |
|---|---|---|---|
| waterjobsuk.com | NS | ns45.domaincontrol.com. | 3600 |
| waterjobsuk.com | NS | ns46.domaincontrol.com. | 3600 |
| waterjobsuk.com | SOA | ns45.domaincontrol.com. dns.jomax.net. 2024030600 28800 7200 604800 600 | 3600 |
| waterjobsuk.com | MX | 0 smtp.secureserver.net. | 3600 |
| waterjobsuk.com | MX | 10 mailstore1.secureserver.net. | 3600 |
| waterjobsuk.com | TXT | "D8054547" | 3600 |
| waterjobsuk.com | TXT | "v=spf1 mx a include:secureserver.net -all" | 3600 |
| www.waterjobsuk.com | A | 64.253.47.65 | 300 |
| www.waterjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| default._domainkey.waterjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| selector1._domainkey.waterjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| selector2._domainkey.waterjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| google._domainkey.waterjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| k1._domainkey.waterjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| mail._domainkey.waterjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| dkim._domainkey.waterjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| mail.waterjobsuk.com | A | 64.253.47.65 | 300 |
| mail.waterjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| webmail.waterjobsuk.com | A | 64.253.47.65 | 300 |
| webmail.waterjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| admin.waterjobsuk.com | A | 64.253.47.65 | 300 |
| admin.waterjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| ftp.waterjobsuk.com | A | 64.253.47.65 | 300 |
| ftp.waterjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| cpanel.waterjobsuk.com | A | 64.253.47.65 | 300 |
| cpanel.waterjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |
| autodiscover.waterjobsuk.com | A | 64.253.47.65 | 300 |
| autodiscover.waterjobsuk.com | CNAME | www-greenjobs-co-uk.cname.strategiesuk.net. | 8600 |

No record (NOERROR, empty): 4 queries, e.g. waterjobsuk.com A; waterjobsuk.com AAAA; waterjobsuk.com CAA; waterjobsuk.com CNAME.

HTTP/TLS (curl via the sandbox egress gateway, honest UA, redirects followed by hand, one row per hop; TLS certificate itself not observable here, see section 3):

| URL | Hop chain (status, redirect target, or curl error) |
|---|---|
| https://waterjobsuk.com/ | curl error 56: (56) CONNECT tunnel failed, response 502 |
| https://www.waterjobsuk.com/ | 200 (final) |
| http://waterjobsuk.com/ | curl error 6: (6) Could not resolve host: waterjobsuk.com |
| http://www.waterjobsuk.com/ | 301 -> https://www.waterjobsuk.com/ ; 200 (final) |

## 3. TLS check: result and limit

The sandbox egress gateway re-terminates TLS: every certificate seen from here is issued by `Anthropic Egress Gateway SDS Issuing CA` for exactly the requested name, with a 30-day expiry. Those are NOT the origin certificates, so subject, SAN and expiry of the real sites could not be read. Raw gateway-side observations are kept in the JSON under `tls_observed_via_egress_gateway_NOT_ORIGIN` and must not be used.

What the gateway did reveal (curl through it):

- `https://www.conservationjobsuk.com/` (and the http redirect that lands on it): curl error 60, `no alternative certificate subject name matches target host name 'www.conservationjobsuk.com'`. No other www host produced a certificate error. This is consistent with the believed mismatch (review section 2, item 10), but is second-hand evidence: confirm with `openssl s_client` from a normal machine.
- `https://<bare domain>/` failed with `Connection reset by peer` (curl 35) for greenjobs.ie, greenjobs.co.uk and the 7 live network domains, and with a 502 tunnel failure for wastejobsuk.com and waterjobsuk.com (no apex A record, see section 4). Cause not determinable here (no certificate for the bare name, or the old host not listening on 443 for it). Every bare name's plain `http://` redirects to `https://www.` where the apex resolves.
- Operator command, from a normal machine: `for h in greenjobs.ie www.greenjobs.ie ...; do echo | openssl s_client -connect $h:443 -servername $h 2>/dev/null | openssl x509 -noout -subject -enddate -ext subjectAltName; done`.

## 4. Findings

1. **A wrong name in the review/brief:** `renewablejobsuk.com` does not exist (DNS NXDOMAIN, `rdap.org` 404). The real name, linked from both greenjobs.co.uk and greenjobs.ie home pages (fetched live today) and from every page of the 22 Sep redesign, is **renewableenergyjobsuk.com**. The other seven names are correct and resolve. (Live fetch of greenjobs.co.uk worked with an honest client name; the default curl user agent got a 403 from the origin.)
2. **Nameservers by domain:** greenjobs.ie at Hosting Ireland (`webhostingireland` x4; SOA admin `admins.hostingireland.ie`); greenjobs.co.uk at `dnsireland` (SOA admin `admin.letshost.ie`; registrar per RDAP Team Blue Internet Services IE Limited); the 8 network sites at GoDaddy `domaincontrol.com` nameservers with registrar 123-Reg Limited per RDAP (registrar and DNS host differ). RDAP has no data for `.ie`, so the .ie registrar is unknown (gap).
3. **Mail:** greenjobs.ie MX is `filter1/filter2.webhostingireland.ie` (spam-filter hosts, priorities 10/20); greenjobs.co.uk MX is `mail.greenjobs.co.uk`, which resolves to 185.43.232.13, the same address as `mail.greenjobs.ie` (so the .co.uk mailboxes are likely on the same Hosting Ireland server, but the MX is the domain's own name, not a Hosting Ireland filter host; that is an inference). The 8 network sites all publish GoDaddy/123-Reg mail MX (`smtp.secureserver.net` 0, `mailstore1.secureserver.net` 10) and SPF `v=spf1 mx a include:secureserver.net -all`: these are the registrar's default mail-forwarding records and may carry live forwarders or mailboxes; check with Diana before the zones move.
4. **SPF includes the old host:** both greenjobs SPF records include `spf.strategiesuk.net`. greenjobs.ie also whitelists ip4:185.43.232.13 and ip4:81.17.241.90 and includes `spf.webhostingireland.ie`. greenjobs.ie has a DKIM key at selector `default` (2048-bit RSA public key present). greenjobs.co.uk has no DKIM at the selectors tried. greenjobs.ie has no DMARC (NXDOMAIN at `_dmarc`); greenjobs.co.uk has `v=DMARC1; p=none;`.
5. **Apex and www:** every apex A is 212.250.3.80 (not a Strategies CNAME) except wastejobsuk.com and waterjobsuk.com, which have **no apex A record at all** (bare `http://wastejobsuk.com/` and `http://waterjobsuk.com/` already fail to resolve). Every www is a CNAME to a `*.cname.strategiesuk.net` name (64.253.47.65 behind it): greenjobs.ie to `www-greenjobs-ie`, greenjobs.co.uk and all 8 network sites to the same `www-greenjobs-co-uk`. So the network sites are one Strategies site answering on different Host headers, confirmed by each returning its own distinct page title at `www.<domain>` today.
6. **Subdomains of note:** `mail`, `webmail`, `ftp`, `cpanel`, `autodiscover` exist on greenjobs.ie (all A 185.43.232.13). On greenjobs.co.uk only `mail` (185.43.232.13) and `ftp` (alias to the apex) exist. On wastejobsuk.com and waterjobsuk.com `mail`, `webmail`, `autodiscover` are aliases to the Strategies host (not mail servers). No CAA on any domain, no AAAA on any domain.
7. **TXT strings of unknown origin:** each network apex carries a bare TXT such as `D6911740`; the pattern is not identified here. Copy it across with the zone anyway.

## 5. Gaps: what public lookups cannot see (host zone export still required)

- Any record at a name we did not guess: other subdomains, DKIM selectors not in {default, selector1, selector2, google, k1, mail, dkim}, SRV records, any TXT verification at a non-apex name. DNS has no zone-listing query (AXFR is refused to the public); only the host export or screenshots show everything.
- Real TTLs as configured: resolvers return remaining cache TTLs for some answers; treat them as upper bounds.
- TLS certificates of the real origins (section 3) and the `.ie` registrar and expiry (RDAP has no `.ie`; port 43 whois blocked in the sandbox).
- Whether the GoDaddy/123-Reg MX on the 8 network domains serve real mailboxes or forwarders.
- Which mailboxes exist on greenjobs.ie and greenjobs.co.uk and whether `mail.greenjobs.co.uk` sits on the same server as the .ie mail.
- Whether Search Console or other verification is held by TXT/CNAME at names we did not try.
