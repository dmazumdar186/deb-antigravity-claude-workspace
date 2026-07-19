# CNIL Response Playbook — self_outbound_v2

**Trigger**: any of the following:
1. Direct email from CNIL (`sanction@cnil.fr` or `plainte@cnil.fr`)
2. Formal complaint forwarded from a recipient citing GDPR / LCEN
3. Data-subject request under Art. 12-22 GDPR
4. Notification of investigation from any French DPA

**Response window**: 30 days for standard DSR (Art. 12); 72h for a formal CNIL investigation notice.

---

## Step 1 — acknowledge within 24h

Send acknowledgement email to complaining party (and CNIL if in copy):

```
Bonjour,

J'accuse réception de votre courrier / signalement du [date].
Je m'engage à traiter votre demande dans les meilleurs délais et à vous répondre sous [X] jours.

Cordialement,
Debanjan Mazumdar
ProdCraft AI Studio
[address]
```

---

## Step 2 — gather evidence within 72h

Pull from local logs (retained per LIA §6):

### Evidence pack per complaint

- [ ] **Original send log** (timestamp, mailbox, personalization variables) from `.tmp/self_outbound/send_log_*.jsonl`
- [ ] **Source of email address** (Apify LinkedIn scrape or AnymailFinder lookup) from `.tmp/self_outbound/sourced_leads_batch_*.json` — proves lead was collected from a public professional source
- [ ] **Unsubscribe link screenshot** proving 1-click opt-out is functional at the URL sent
- [ ] **Suppression list evidence** — if recipient previously opted out, show entry in `config/suppression.json` and cross-check no send occurred after that timestamp
- [ ] **LIA current version** (`docs/legal/lia_paris_founders.md`) as signed and dated
- [ ] **Vendor DPAs**: Instantly, Primeforge, Litemail terms accepted
- [ ] **Privacy notice** at `prodcraft.fyi/privacy` as of send date (Wayback Machine snapshot if URL changed)
- [ ] **Copy of the offending email** as actually sent (not a template)

Package all as `docs/legal/cnil_case_[date]_[complainant_hash]/` — one folder per case. Encrypt if it contains PII.

---

## Step 3 — respond within 30 days (standard DSR)

Template response:

```
Bonjour [Nom du plaignant],

Suite à votre demande du [date], je vous confirme les éléments suivants concernant le traitement de vos données personnelles :

1. **Base légale du traitement** : intérêt légitime (article 6.1.f RGPD), en conformité avec l'article L.34-5 LCEN pour le B2B professionnel.

2. **Source de vos données** : votre adresse email professionnelle a été collectée depuis [LinkedIn / site professionnel public / etc.] le [date de collecte].

3. **Finalité** : proposition unique de services de conseil produit-AI fractionnés (ProdCraft AI Studio) à des acteurs de la scène tech française.

4. **Vos droits** :
   - Droit d'accès, rectification, effacement : [confirmé, exécuté sous 30 jours]
   - Droit d'opposition : votre adresse est maintenant sur ma liste de suppression permanente et ne recevra plus jamais de communication commerciale de ma part
   - Droit de saisir la CNIL : www.cnil.fr

5. **Actions concrètes prises** :
   - Votre adresse a été ajoutée à la liste de suppression le [date]
   - Vos données brutes (source, timestamps, journaux d'envoi) ont été [supprimées / conservées selon §6 LIA — préciser]
   - Aucune nouvelle communication ne vous sera envoyée

Cordialement,
Debanjan Mazumdar
ProdCraft AI Studio
[postal address]
```

---

## Step 4 — CNIL formal investigation response

Additional steps:

1. **Legal counsel** — Contact a French GDPR-specialist lawyer BEFORE responding. Available options in Paris:
   - CNIL's own guidance page: https://www.cnil.fr/fr/notifier-une-violation-de-donnees-personnelles
   - Barreau de Paris list of GDPR specialists

2. **Full DPO-style response** with:
   - Copy of signed LIA
   - Vendor DPA chain
   - Retention proof
   - Evidence of unsubscribe pipeline working
   - Statistics: how many opt-outs honored in the last 12 months
   - Screenshot of `config/suppression.json` size + last-modified date

3. **Do not admit fault before consulting counsel.** Facts only.

---

## Step 5 — post-incident review (mandatory)

After resolution, update `docs/legal/lia_paris_founders.md`:
- [ ] Increment version + changelog entry with case-hash reference
- [ ] Update Section 4 (Safeguards) if a gap was identified
- [ ] Update Section 5 (Review triggers) if this incident revealed a new class of trigger
- [ ] Update this playbook with the specific gap that let the incident happen

---

## Preventive checks (weekly)

To reduce complaint likelihood:

- [ ] Verify unsubscribe link works from a real email (not the campaign UI)
- [ ] Verify suppression list is being written to (recent entries in `config/suppression.json`)
- [ ] Verify bounce-back auto-suppression is functional
- [ ] Verify no send occurs to any email in the suppression list (front-door synthetic gate)
- [ ] Verify LIA is signed and dated (not "pending")

---

## Emergency scorched-earth pause

If a complaint escalates to a formal CNIL warning or the operator judges the risk unacceptable:

```bash
# Pause all sending immediately
export PAUSE_ALL=1
# Additionally: log into Instantly UI, pause the self_outbound_v2 campaign
# Additionally: revoke the Cloudflare Worker's webhook token if suppression pipeline is suspected of leaking
```

Then: notify CNIL of the pause + timeline for remediation.

---

## Sources
- CNIL guide on B2B cold email: https://www.cnil.fr/fr/spam-b2b
- CNIL sanction procedure: https://www.cnil.fr/fr/comment-la-cnil-decide-des-sanctions
- LCEN L34-5: French Post & Electronic Communications Code
- GDPR Art. 12-22
