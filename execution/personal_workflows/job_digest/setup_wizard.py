"""
description: Interactive terminal wizard that produces a valid job_digest
    profile.yaml for a non-developer friend. Every question maps directly to
    a profile_schema.Profile field; the wizard never invents a shape of its
    own — it builds the exact nested dict Profile.model_validate() expects,
    section by section, and re-asks only the sections that fail validation.
inputs:
    - Interactive: terminal input() prompts.
    - Non-interactive: --answers a JSON file shaped like profile.yaml (top-level
      keys: candidate, roles, locations, contracts, screening, digest, sheet —
      same shape profile_schema.Profile validates), for tests and scripting.
outputs: writes a commented profile.yaml (path from --out, default ./profile.yaml)
    that passes profile_schema.load_profile(); prints onboarding next steps
    (which GitHub secrets to create, with exact links).

Never imports from the operator's internal job pipeline. Only reads profile_schema.py / registry.py —
does not modify either.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from . import registry
from .profile_schema import Candidate, Digest, Locations, Profile, Role, Screening

_ANSWERS_KEYS = ("candidate", "roles", "locations", "contracts", "screening", "digest", "sheet")

_GMAIL_APP_PASSWORD_URL = "https://myaccount.google.com/apppasswords"
_GEMINI_KEY_URL = "https://aistudio.google.com/apikey"


def _ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    return raw or (default or "")


def _ask_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    raw = input(f"{prompt} [{suffix}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def _ask_list(prompt: str, default: str = "") -> list[str]:
    raw = _ask(prompt, default)
    return [p.strip() for p in raw.split(",") if p.strip()]


def _ask_int(prompt: str, default: int) -> int:
    while True:
        raw = _ask(prompt, str(default))
        try:
            return int(raw)
        except ValueError:
            print(f"  '{raw}' is not a whole number — try again.")


def _format_errors(exc: ValidationError) -> str:
    lines = [f"  - {'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}" for e in exc.errors()]
    return "profile has {} problem(s):\n{}".format(len(lines), "\n".join(lines))


# ----- section collectors (interactive) -----


def _ask_candidate() -> dict:
    while True:
        name = _ask("Your name")
        email = _ask("Your email address")
        try:
            Candidate.model_validate({"name": name, "email": email})
        except ValidationError as exc:
            print(_format_errors(exc))
            continue
        return {"name": name, "email": email}


def _ask_roles() -> list[dict]:
    print("\nWhat job title(s) are you looking for? (1 to 3)")
    roles: list[dict] = []
    seniority = _ask("Seniority level (any/junior/mid/senior/lead)", "any")
    while len(roles) < 3:
        while True:
            title = _ask(f"Role {len(roles) + 1} title (e.g. 'Sales Manager')")
            synonyms = _ask_list("  Other titles that mean the same job (comma-separated, optional)")
            role_raw = {"title": title, "synonyms": synonyms, "seniority": seniority}
            try:
                Role.model_validate(role_raw)
            except ValidationError as exc:
                print(_format_errors(exc))
                continue
            roles.append(role_raw)
            break
        if len(roles) >= 1 and not _ask_yes_no("Add another role?", False):
            break
    return roles


def _ask_locations() -> dict:
    print("\nSupported countries:")
    for iso2, country in registry.COUNTRIES.items():
        print(f"  {iso2}  {country.name}")
    while True:
        countries = [c.upper() for c in _ask_list("Countries to search, comma-separated ISO2 codes (1 to 5)")]
        cities = _ask_list("Cities to prefer, comma-separated (optional — leave blank for any city)")
        remote_ok = _ask_yes_no("Include remote jobs?", True)
        loc_raw = {"countries": countries, "cities": cities, "remote_ok": remote_ok}
        try:
            Locations.model_validate(loc_raw)
        except ValidationError as exc:
            print(_format_errors(exc))
            continue
        return loc_raw


def _ask_contracts() -> list[str]:
    print("\nContract types to include: permanent, fixed_term, freelance")
    while True:
        raw = _ask_list("Comma-separated", "permanent,fixed_term")
        valid = {"permanent", "fixed_term", "freelance"}
        bad = [c for c in raw if c not in valid]
        if bad:
            print(f"  unrecognized contract type(s) {bad}; choose from {sorted(valid)}")
            continue
        return raw


def _ask_screening() -> dict:
    while True:
        print("\nDescribe yourself in 3-10 sentences: what you do, years of experience,")
        print("domains, and what you want next. This goes straight into the ranker.")
        summary = _ask("Summary")
        skills = _ask_list("Your key skills, comma-separated")
        raw = {"summary": summary, "skills": skills}
        try:
            Screening.model_validate(raw)
        except ValidationError as exc:
            print(_format_errors(exc))
            continue
        return raw


def _ask_digest(default_timezone: str | None) -> dict:
    while True:
        hour = _ask_int("Hour to receive your digest (local time, 0-23)", 9)
        timezone = _ask("Timezone (IANA, e.g. Europe/Paris)", default_timezone or "UTC")
        raw = {"hour_local": hour, "timezone": timezone}
        try:
            Digest.model_validate(raw)
        except ValidationError as exc:
            print(_format_errors(exc))
            continue
        return raw


def _ask_sheet() -> dict:
    enabled = _ask_yes_no("Also log jobs to a Google Sheet?", True)
    return {"enabled": enabled}


def _collect_interactive(raw: dict) -> dict:
    if "candidate" not in raw:
        raw["candidate"] = _ask_candidate()
    if "roles" not in raw:
        raw["roles"] = _ask_roles()
    if "locations" not in raw:
        raw["locations"] = _ask_locations()
    if "contracts" not in raw:
        raw["contracts"] = _ask_contracts()
    if "screening" not in raw:
        raw["screening"] = _ask_screening()
    if "digest" not in raw:
        default_tz = None
        countries = raw.get("locations", {}).get("countries") or []
        if countries:
            try:
                default_tz = registry.get(countries[0]).timezone
            except KeyError:
                default_tz = None
        raw["digest"] = _ask_digest(default_tz)
    if "sheet" not in raw:
        raw["sheet"] = _ask_sheet()
    raw["version"] = 1
    return raw


def _build_from_answers(path: str | Path) -> dict:
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{p} must contain a JSON object at the top level")
    raw = dict(raw)
    raw["version"] = 1
    return raw


def _write_profile_yaml(profile: Profile, out_path: str | Path) -> Path:
    out = Path(out_path)
    data = profile.model_dump(mode="json")
    header = (
        "# job_digest profile — generated by setup_wizard.py\n"
        "# Edit freely; validate with: /job-digest validate  (or the python command in README)\n"
        "#\n"
        "# roles: 1-3 job titles you want alerts for (+ optional synonyms).\n"
        "# locations.countries: ISO2 codes from the registry (1-5).\n"
        "# digest.hour_local / digest.timezone: when the daily email goes out.\n"
        "# sheet.enabled: also log matches to your own Google Sheet.\n"
    )
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    out.write_text(header + "\n" + body, encoding="utf-8")
    return out


def _print_next_steps(profile: Profile) -> None:
    print("\nProfile written. Next steps:")
    print("  1. Create a private GitHub repo and push this profile.yaml to it.")
    print("  2. Create these repo secrets (Settings > Secrets and variables > Actions):")
    print("       GMAIL_SMTP_USER            — your Gmail address")
    print("       GMAIL_SMTP_APP_PASSWORD    — an App Password (needs 2-Step Verification on):")
    print(f"           {_GMAIL_APP_PASSWORD_URL}")
    if profile.sheet.enabled:
        print("       GOOGLE_SERVICE_ACCOUNT_JSON_B64 — base64 of a Google service account JSON key")
        print("       SHEETS_SPREADSHEET_ID           — the target spreadsheet's ID")
        print("       (create a service account + key in Google Cloud Console, share your")
        print("        sheet with its email address as Editor, then base64-encode the JSON key)")
    print("     Optional (free tier, better ranking):")
    print(f"       GEMINI_API_KEY — {_GEMINI_KEY_URL}")
    print("     Optional (metered API spend — a Claude.ai SUBSCRIPTION does NOT provide this key):")
    print("       ANTHROPIC_API_KEY — https://console.anthropic.com/settings/keys")
    print("  3. Run `PYTHONPATH=engine python -m job_digest.cli render-workflow profile.yaml`")
    print("     to generate .github/workflows/job_digest.yml, then commit and push it.")
    print("  4. Trigger the workflow once by hand (Actions tab > job-digest > Run workflow) to check email delivery.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Interactive setup wizard for job_digest.")
    parser.add_argument("--out", default="profile.yaml", help="Where to write profile.yaml")
    parser.add_argument(
        "--answers",
        default=None,
        help="Path to a JSON file with pre-filled answers (profile.yaml-shaped), for non-interactive use.",
    )
    args = parser.parse_args(argv)

    if args.answers:
        try:
            raw = _build_from_answers(args.answers)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"error reading --answers: {exc}", file=sys.stderr)
            return 1
        try:
            profile = Profile.model_validate(raw)
        except ValidationError as exc:
            print(_format_errors(exc), file=sys.stderr)
            return 1
        _write_profile_yaml(profile, args.out)
        _print_next_steps(profile)
        return 0

    raw: dict = {}
    while True:
        raw = _collect_interactive(raw)
        try:
            profile = Profile.model_validate(raw)
            break
        except ValidationError as exc:
            print(_format_errors(exc))
            bad_sections = {e["loc"][0] for e in exc.errors() if e["loc"] and e["loc"][0] in _ANSWERS_KEYS}
            if not bad_sections:
                # Cross-field problem (e.g. digest.timezone default) we can't
                # attribute to one section — drop everything and start over
                # rather than loop forever re-asking nothing.
                raw = {}
                continue
            for section in bad_sections:
                raw.pop(section, None)

    _write_profile_yaml(profile, args.out)
    _print_next_steps(profile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
