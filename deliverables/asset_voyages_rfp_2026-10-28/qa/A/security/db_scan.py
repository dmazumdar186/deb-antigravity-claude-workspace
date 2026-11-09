"""Scan a copy of the Playground SQLite DB: plaintext GM&E codes anywhere, nonce uniqueness, log contents."""
import base64, re, shutil, sqlite3, sys, glob, os
src = glob.glob(os.path.join(sys.argv[1], ".ht.*", ".ht.sqlite"))
dst = "/tmp/asset_sec_db.sqlite"; shutil.copy(src[0], dst)
raw = open(dst, "rb").read()
print("plaintext DEMO-GME hits in raw file:", sorted(set(re.findall(rb"DEMO-GME-[A-Z0-9]{2,}", raw))))
c = sqlite3.connect(dst)
rows = c.execute("select congres_id, code_enc from wp_asset_gme_codes").fetchall()
nonces = [base64.b64decode(e)[:24] for _, e in rows]
print("code rows", len(rows), "distinct nonces", len(set(nonces)), "distinct ciphertexts", len({e for _, e in rows}))
print("log actions", c.execute("select action, count(*) from wp_asset_gme_log group by action").fetchall())
print("log details containing DEMO:", c.execute("select count(*) from wp_asset_gme_log where detail like '%DEMO-GME%'").fetchone())
print("access rows", c.execute("select id,user_id,congres_id,status,expires_at from wp_asset_gme_access").fetchall())
print("meta/options with gme:", c.execute("select count(*) from wp_postmeta where meta_value like '%GME%'").fetchone(), c.execute("select option_name from wp_options where option_value like '%DEMO-GME%'").fetchall())
