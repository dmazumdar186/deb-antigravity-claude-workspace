# Recruitment Cities 30 Sep 26 — bounce fix runbook (2026-10-09)

Campaign f161ac21-c473-4ec2-a25c-827230d38c65 is paused by Instantly Bounce Protect
(status -2). Root cause: the full 2,501-row export was uploaded, including every row the
verifier had already marked not safe. 17 of the 19 bounces are on catch_all / invalid rows.

Files in this folder:
- recruitment_cities_SAFE_upload.csv  (978 leads: status=safe, is_safe_to_send=true, not catch-all, not bounced, deduped)
- recruitment_cities_CATCHALL_hold.csv (842 catch-all leads: do NOT send these in this campaign; SMTP-verify them or run a separate low-volume campaign)
- remove_from_campaign.txt (1,208 emails to remove out of the campaign)

One command does the whole Instantly side (needs INSTANTLY_NOTIFIER_API_KEY in .env or env):

    python3 execution/infrastructure/instantly_campaign_cleanup.py f161ac21-c473-4ec2-a25c-827230d38c65 \
      --keep-csv .tmp/instantly_fix/recruitment_cities_SAFE_upload.csv \
      --also-remove .tmp/instantly_fix/remove_from_campaign.txt \
      --bounces-csv "<path to the bounces export csv>" \
      --resume --no-dry-run

Drop --no-dry-run first to see counts. Then put the guard on a daily cron:

    python3 execution/infrastructure/instantly_guard.py f161ac21-c473-4ec2-a25c-827230d38c65 --no-dry-run
