"""
Tier 1+2+4 tests for the Nick Saraev transcript-mirror update (2026-06-08).

Covers:
- New directives exist with required structural sections
- security_audit_prompt.md has all 14 categories
- bootstrap_mobile_app.py registry entry includes new fields
- SKILL.md has new sub-commands
- Template repo has {{APP_SLUG}} placeholders
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DIRECTIVES_DIR = PROJECT_ROOT / "directives" / "mobile_apps"
SKILL_PATH = PROJECT_ROOT / ".claude" / "skills" / "mobile-app" / "SKILL.md"
TEMPLATE_DIR = Path(r"C:/Users/deban/dev/mobile-apps/_template")

REQUIRED_DIRECTIVE_SECTIONS = [
    "## Goal",
    "## Inputs",
    "## Tools/Scripts",
    "## Outputs",
    "## Steps",
    "## Edge Cases",
]

NEW_DIRECTIVES = [
    "app_design.md",
    "security_audit.md",
    "security_audit_prompt.md",
    "phase4c_supabase_setup.md",
    "phase4d_supabase_auth.md",
    "phase5b_supabase_ai.md",
]

MODIFIED_DIRECTIVES = [
    "phase1_local_standalone.md",
    "ios_deploy.md",
    "android_deploy.md",
]


# ─── TIER 1: UNIT ─────────────────────────────────────────────────────────

class TestNewDirectivesExist:
    @pytest.mark.parametrize("name", NEW_DIRECTIVES)
    def test_directive_file_exists(self, name):
        path = DIRECTIVES_DIR / name
        assert path.exists(), f"missing new directive: {path}"
        assert path.stat().st_size > 0, f"empty directive: {path}"


class TestDirectiveStructure:
    # security_audit_prompt.md is a prompt-only file, not a directive — exempt.
    STRUCTURED = [d for d in NEW_DIRECTIVES if d != "security_audit_prompt.md"]

    @pytest.mark.parametrize("name", STRUCTURED)
    @pytest.mark.parametrize("section", REQUIRED_DIRECTIVE_SECTIONS)
    def test_directive_has_required_section(self, name, section):
        text = (DIRECTIVES_DIR / name).read_text(encoding="utf-8")
        assert section in text, f"{name} missing section: {section}"


class TestSecurityAuditPrompt:
    def setup_method(self):
        self.text = (DIRECTIVES_DIR / "security_audit_prompt.md").read_text(
            encoding="utf-8"
        )

    def test_all_14_categories_present(self):
        for i in range(1, 15):
            marker = f"## Category {i}"
            assert marker in self.text, f"missing {marker}"

    def test_paste_verbatim_instruction(self):
        assert "Paste this prompt verbatim" in self.text
        assert "/clear" in self.text

    def test_no_anthropic_typo(self):
        # Nick's transcript voice-renders ANTHROPIC_API_KEY as "enthropic" — flagged.
        # The canonical prompt itself should NOT contain that typo.
        assert "enthropic" not in self.text.lower(), (
            "security_audit_prompt.md contains 'enthropic' typo — should be ANTHROPIC"
        )

    def test_ranked_findings_table_in_output_spec(self):
        assert "Ranked findings" in self.text
        assert "CRITICAL" in self.text
        assert "CWE" in self.text


class TestModifiedPhase1:
    def setup_method(self):
        self.text = (DIRECTIVES_DIR / "phase1_local_standalone.md").read_text(
            encoding="utf-8"
        )

    def test_three_tier_testing_documented(self):
        assert "3-tier test protocol" in self.text or "3-tier testing" in self.text.lower()
        assert "Chrome web" in self.text
        assert "Expo Go" in self.text

    def test_init_step_present(self):
        assert "/init" in self.text

    def test_github_push_step_present(self):
        assert "GitHub" in self.text

    def test_web_preview_command(self):
        assert "expo start --web" in self.text

    def test_app_spec_input(self):
        # Phase 1 must reference APP_SPEC.md from the design directive
        assert "APP_SPEC.md" in self.text


class TestModifiedShipDirectives:
    @pytest.mark.parametrize("name", ["ios_deploy.md", "android_deploy.md"])
    def test_pre_submission_checklist(self, name):
        text = (DIRECTIVES_DIR / name).read_text(encoding="utf-8")
        assert "Pre-submission content checklist" in text
        assert "privacy policy" in text.lower()

    def test_android_adaptive_icons_listed(self):
        text = (DIRECTIVES_DIR / "android_deploy.md").read_text(encoding="utf-8")
        for asset in [
            "android-icon-foreground.png",
            "android-icon-background.png",
            "android-icon-monochrome.png",
        ]:
            assert asset in text, f"android_deploy.md missing {asset}"

    def test_ios_icon_dimensions(self):
        text = (DIRECTIVES_DIR / "ios_deploy.md").read_text(encoding="utf-8")
        assert "1024x1024" in text


class TestBootstrapRegistryShape:
    """Verify new fields are written by bootstrap_mobile_app.py's new_entry block."""

    def setup_method(self):
        self.source = (
            PROJECT_ROOT / "execution" / "mobile_apps" / "bootstrap_mobile_app.py"
        ).read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        "field",
        [
            "backend_stack",
            "spec_summary",
            "last_security_audit_at",
            "audit_passes_run",
        ],
    )
    def test_registry_entry_includes_new_field(self, field):
        assert f'"{field}"' in self.source, (
            f"bootstrap_mobile_app.py new_entry missing {field}"
        )


class TestSkillSubcommands:
    def setup_method(self):
        self.text = SKILL_PATH.read_text(encoding="utf-8")

    def test_design_subcommand_documented(self):
        assert "### `design {slug}`" in self.text
        assert "APP_SPEC.md" in self.text

    def test_audit_subcommand_documented(self):
        assert "### `audit {slug}`" in self.text
        assert "security_audit" in self.text.lower()

    @pytest.mark.parametrize("phase", ["4c", "4d", "5b_supabase"])
    def test_supabase_phases_in_routing_table(self, phase):
        # phase identifier must appear in the routing table
        assert phase in self.text, f"SKILL.md missing phase {phase}"

    def test_backend_stack_routing(self):
        assert "backend_stack" in self.text
        assert "cf_modal" in self.text
        assert "supabase" in self.text


# ─── TIER 2: INTEGRATION ──────────────────────────────────────────────────

class TestTemplateRepo:
    """Integration: verify the actual template repo on disk has placeholders + web deps.
    Skips if the template dir is missing (CI environments without local template)."""

    def setup_method(self):
        if not TEMPLATE_DIR.exists():
            pytest.skip(f"template repo not present at {TEMPLATE_DIR}")
        self.app_json = json.loads((TEMPLATE_DIR / "app.json").read_text(encoding="utf-8"))
        self.pkg_json = json.loads(
            (TEMPLATE_DIR / "package.json").read_text(encoding="utf-8")
        )
        self.claude_md = (TEMPLATE_DIR / "CLAUDE.md").read_text(encoding="utf-8")

    def test_app_json_uses_placeholder(self):
        assert self.app_json["expo"]["name"] == "{{APP_SLUG}}"
        assert self.app_json["expo"]["slug"] == "{{APP_SLUG}}"

    def test_package_json_uses_placeholder(self):
        assert self.pkg_json["name"] == "{{APP_SLUG}}"

    def test_claude_md_uses_placeholder(self):
        assert "{{APP_SLUG}}" in self.claude_md

    @pytest.mark.parametrize(
        "dep",
        ["react-native-web", "react-dom", "@expo/metro-runtime"],
    )
    def test_web_preview_deps_declared(self, dep):
        assert dep in self.pkg_json["dependencies"], (
            f"template package.json missing {dep}"
        )


# ─── TIER 4: SANITY ───────────────────────────────────────────────────────

class TestDirectiveMarkdown:
    """All directive files must be UTF-8 readable and non-empty."""

    @pytest.mark.parametrize("name", NEW_DIRECTIVES + MODIFIED_DIRECTIVES)
    def test_directive_readable(self, name):
        path = DIRECTIVES_DIR / name
        text = path.read_text(encoding="utf-8")
        assert len(text) > 100, f"{name} suspiciously short: {len(text)} chars"

    @pytest.mark.parametrize("name", NEW_DIRECTIVES + MODIFIED_DIRECTIVES)
    def test_directive_has_h1(self, name):
        text = (DIRECTIVES_DIR / name).read_text(encoding="utf-8")
        assert re.search(r"^#\s+\S", text, re.MULTILINE), (
            f"{name} missing top-level H1 heading"
        )


class TestBootstrapHelpStillWorks:
    """Sanity: the modified bootstrap script's --help still parses."""

    def test_help_runs(self):
        result = subprocess.run(
            [
                sys.executable,
                str(
                    PROJECT_ROOT
                    / "execution"
                    / "mobile_apps"
                    / "bootstrap_mobile_app.py"
                ),
                "--help",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        assert result.returncode == 0, f"--help exited {result.returncode}: {result.stderr}"
        assert "slug" in result.stdout.lower()


# ─── TIER 2 (extended): BOOTSTRAP INTEGRATION ─────────────────────────────

class TestBootstrapDryRun:
    """Integration: a dry-run bootstrap with the new registry shape should not crash,
    should produce the new fields, and should leave no real fs/git side effects."""

    def test_cmd_create_then_remove_roundtrip(self, isolated_registry, isolated_mobile_apps_base):
        """E2E: create → registry has app → remove → registry empty.
        Verifies the new fields survive the round-trip and removal doesn't leak."""
        import bootstrap_mobile_app as bma
        slug = "roundtrip-app"
        assert bma.cmd_create(slug, dry_run=False, force=False) == 0
        reg_after_create = json.loads(isolated_registry.read_text(encoding="utf-8"))
        assert len(reg_after_create["apps"]) == 1
        assert reg_after_create["apps"][0]["backend_stack"] is None  # new field default

        assert bma.cmd_remove(slug, force_remove=True) == 0
        reg_after_remove = json.loads(isolated_registry.read_text(encoding="utf-8"))
        assert reg_after_remove["apps"] == []

    def test_cmd_create_with_backend_stack_supabase(self, isolated_registry, isolated_mobile_apps_base):
        import bootstrap_mobile_app as bma
        assert bma.cmd_create("supabase-app", dry_run=False, force=False, backend_stack="supabase") == 0
        reg = json.loads(isolated_registry.read_text(encoding="utf-8"))
        assert reg["apps"][0]["backend_stack"] == "supabase"

    def test_cmd_create_with_backend_stack_cf_modal(self, isolated_registry, isolated_mobile_apps_base):
        import bootstrap_mobile_app as bma
        assert bma.cmd_create("cf-modal-app", dry_run=False, force=False, backend_stack="cf_modal") == 0
        reg = json.loads(isolated_registry.read_text(encoding="utf-8"))
        assert reg["apps"][0]["backend_stack"] == "cf_modal"

    def test_cmd_create_rejects_invalid_backend_stack(self, isolated_registry, isolated_mobile_apps_base):
        import bootstrap_mobile_app as bma
        with pytest.raises(ValueError, match="invalid --backend-stack"):
            bma.cmd_create("bad-app", dry_run=False, force=False, backend_stack="firebase")

    def test_cli_accepts_backend_stack_flag(self):
        """--help should list --backend-stack as a documented flag."""
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "execution" / "mobile_apps" / "bootstrap_mobile_app.py"), "--help"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
        )
        assert result.returncode == 0
        assert "--backend-stack" in result.stdout
        assert "cf_modal" in result.stdout
        assert "supabase" in result.stdout

    def test_cmd_create_includes_new_fields(self, isolated_registry, isolated_mobile_apps_base):
        import bootstrap_mobile_app as bma
        rc = bma.cmd_create("transcript-mirror-test", dry_run=False, force=False)
        assert rc == 0, f"cmd_create returned {rc}"

        reg = json.loads(isolated_registry.read_text(encoding="utf-8"))
        apps = reg["apps"]
        assert len(apps) == 1, f"expected 1 app entry, got {len(apps)}"
        entry = apps[0]
        for field in [
            "backend_stack",
            "spec_summary",
            "last_security_audit_at",
            "audit_passes_run",
        ]:
            assert field in entry, f"new entry missing {field}"
        # Defaults match the spec
        assert entry["backend_stack"] is None
        assert entry["spec_summary"] is None
        assert entry["last_security_audit_at"] is None
        assert entry["audit_passes_run"] == 0
