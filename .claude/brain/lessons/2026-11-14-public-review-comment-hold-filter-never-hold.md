---
id: 2026-11-14-public-review-comment-hold-filter-never-hold
triggers: reviews, moderation, blocklist, profanity filter, hold words, comments, jeevana
scope: all
strength: 2
status: active
created: 2026-11-14
confirmed: 2026-11-14
source: 82f3e6067b60 jeevana reviews red-team round 1: hold filter stops holding accusations and FR false positives
supersedes:
---
In a public review/comment hold-filter, never hold accusation or negative words (scam, arnaque, escroc) and run every blocklist word against everyday text in each site language (FR 'en retard', 'pique-nique') before shipping.

Why: Jeevana reviews 2026-11-14: the hold list held honest 1-star reviews ('arnaque') and ordinary French ('en retard' matched the EN slur 'retard'); 4/4 red-team lenses flagged it as hidden filtering of negative reviews.
