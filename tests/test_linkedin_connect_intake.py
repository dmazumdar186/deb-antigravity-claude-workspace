"""Gmail list intake for the LinkedIn connect job (linkedin_connect_queue.intake_gmail), offline.

description: Proves intake merges leaders, is idempotent, holds unknown files, reads localised folders.
inputs: none (fake IMAP server, tmp_path data dir)
outputs: pytest results
"""

from __future__ import annotations

import sys
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "execution" / "personal_workflows")
)
import linkedin_connect_queue as Q  # noqa: E402

HEAD = "First Name,Last Name,Company Name,LinkedIn,Title,Seniority\n"


def _csv(rows: list[tuple]) -> bytes:
    return (HEAD + "".join(",".join(r) + "\n" for r in rows)).encode()


def _mail(subject: str, attachments: list[tuple[str, bytes]]) -> bytes:
    m = EmailMessage()
    m["Subject"], m["From"], m["To"] = subject, "me@example.com", "me@example.com"
    m.set_content("list")
    for name, data in attachments:
        m.add_attachment(data, maintype="text", subtype="csv", filename=name)
    return m.as_bytes()


class FakeIMAP:
    """Gmail-like: French special-use folder names; the same draft shows in All Mail and Drafts."""

    def __init__(self, messages: list[bytes]):
        self.messages, self.selected, self.searches = messages, None, []

    def login(self, u, p):
        return "OK", [b"ok"]

    def list(self):
        return "OK", [
            b'(\\HasNoChildren \\All) "/" "[Gmail]/Tous les messages"',
            b'(\\HasNoChildren \\Drafts) "/" "[Gmail]/Brouillons"',
            b'(\\HasNoChildren) "/" "INBOX"',
        ]

    def select(self, folder, readonly=False):
        assert readonly, "intake must never write to the mailbox"
        self.selected = folder
        return "OK", [str(len(self.messages)).encode()]

    def search(self, charset, *crit):
        self.searches.append((self.selected, crit))
        hits = [
            str(i + 1).encode() for i, m in enumerate(self.messages) if b"LC list" in m
        ]
        return "OK", [b" ".join(hits)]

    def fetch(self, mid, what):
        assert "PEEK" in what, "fetch must not mark messages read"
        return "OK", [(b"1 (BODY[] {n}", self.messages[int(mid) - 1]), b")"]

    def logout(self):
        return "BYE", []


LEADERS = [
    ("Ann", "Lee", "Acme", "http://www.linkedin.com/in/ann-lee", "President", "Owner"),
    (
        "Bob",
        "Ray",
        "Beta",
        "https://linkedin.com/in/bob-ray/",
        "Chief Executive Officer",
        "C_suite",
    ),
    (
        "Cy",
        "Do",
        "Gamma",
        "http://www.linkedin.com/in/cy-do",
        "Vice President Operations",
        "Vp",
    ),
]
NOT_LEADERS = [
    (
        "Di",
        "Ek",
        "Acme",
        "http://www.linkedin.com/in/di-ek",
        "Executive Assistant To CEO",
        "Entry",
    ),
    (
        "Ed",
        "Fo",
        "Beta",
        "http://www.linkedin.com/in/ed-fo",
        "Marketing Director",
        "Director",
    ),
    (
        "Fa",
        "Gu",
        "Gamma",
        "http://www.linkedin.com/in/fa-gu",
        "Assistant Vice President",
        "Vp",
    ),
]


def _run(store, msgs, **kw):
    fake = FakeIMAP(msgs)
    rows = Q.intake_gmail(
        store, "u", "p", log=lambda s: None, imap_factory=lambda: fake, **kw
    )
    return rows, fake


def test_merges_leaders_only_then_is_idempotent(tmp_path):
    store = Q.Store(tmp_path)
    Q.write_csv(
        store.master,
        [
            {
                "slug": "ann-lee",
                "name": "Ann Lee",
                "company": "Acme",
                "position": "President",
                "linkedin_url": "https://www.linkedin.com/in/ann-lee/",
                "source_file": "old.csv",
            }
        ],
        Q.FIELDS,
    )
    msg = _mail("LC list: JT construction", [("jt.csv", _csv(LEADERS + NOT_LEADERS))])
    rows, fake = _run(store, [msg, _mail("unrelated", [("x.csv", _csv(LEADERS))])])
    assert (
        len(rows) == 1
    )  # same draft in both folders = one ingest (sha dedupe within a run)
    assert {f for f, _ in fake.searches} == {
        "\"[Gmail]/Tous les messages\"",
        "\"[Gmail]/Brouillons\"",
    }
    assert (
        rows[0]["rows_in"] == 6 and rows[0]["rows_kept"] == 3 and rows[0]["added"] == 2
    )  # ann-lee already there
    slugs = {r["slug"] for r in store.load_master()}
    assert slugs == {"ann-lee", "bob-ray", "cy-do"}
    # second run: nothing new, master unchanged, no new intake row
    rows2, _ = _run(store, [msg])
    assert (
        rows2 == [] and len(store.load_intake()) == 1 and len(store.load_master()) == 3
    )


def test_unknown_seniority_vocabulary_is_held(tmp_path):
    store = Q.Store(tmp_path)
    odd = [
        (f"N{i}", "X", "Co", f"http://www.linkedin.com/in/p{i}", "Boss", "Level-9")
        for i in range(60)
    ]
    rows, _ = _run(store, [_mail("LC list odd", [("odd.csv", _csv(odd))])])
    assert rows[0]["note"].startswith("held") and not store.master.exists()
    assert Q.leaders_only([]) == []


def test_file_without_seniority_column_keeps_all_but_vetoed_titles(tmp_path):
    store = Q.Store(tmp_path)
    data = (
        b"Name,Company,Position,Profile\n"
        b"Gil Ha,Acme,Founder,https://www.linkedin.com/in/gil-ha\n"
        b"Hu Io,Acme,Executive Assistant,https://www.linkedin.com/in/hu-io\n"
    )
    rows, _ = _run(store, [_mail("LC list sales nav", [("sn.csv", data)])])
    assert rows[0]["added"] == 1 and {r["slug"] for r in store.load_master()} == {
        "gil-ha"
    }


def test_dry_run_writes_nothing(tmp_path):
    store = Q.Store(tmp_path)
    rows, _ = _run(store, [_mail("LC list", [("jt.csv", _csv(LEADERS))])], dry_run=True)
    assert (
        rows[0]["note"] == "dry-run"
        and not store.master.exists()
        and not store.intake.exists()
    )
    assert not any(store.lists.glob("*")) if store.lists.exists() else True


def test_gzipped_csv_attachment(tmp_path):
    import gzip
    store = Q.Store(tmp_path)
    m = EmailMessage()
    m["Subject"] = "LC list: gz"
    m.set_content("list")
    m.add_attachment(gzip.compress(_csv(LEADERS)), maintype="application", subtype="gzip", filename="jt.csv.gz")
    rows, _ = _run(store, [m.as_bytes()])
    assert rows[0]["filename"] == "jt.csv" and rows[0]["added"] == 3
