from __future__ import annotations
import os, sys, time
import unittest.mock as mock
from pathlib import Path

WORKSPACE = Path(r'C:/Users/deban/OneDrive/Documents/AntiGravity Project Space')
sys.path.insert(0, str(WORKSPACE / 'execution' / 'video'))
sys.path.insert(0, str(WORKSPACE / 'execution' / 'modules'))

from dotenv import load_dotenv
load_dotenv(str(WORKSPACE / '.env'))

from youtube_video_analyzer import (
    extract_video_id, slugify, _auto_detect_provider,
    _to_openai_tool_format, TOOL_SCHEMA, render_breakdown_markdown,
)
from model_registry import (
    ALLOWED_FAMILIES, LAST_KNOWN_GOOD, resolve_model, _resolve_openrouter,
)

PASS_COUNT = 0; FAIL_COUNT = 0; FAILURES = []

def run(name, fn):
    global PASS_COUNT, FAIL_COUNT
    try:
        fn()
        print(f'PASS  {name}')
        PASS_COUNT += 1
    except Exception as exc:
        print(f'FAIL  {name}')
        print(f'      {exc}')
        FAIL_COUNT += 1
        FAILURES.append((name, str(exc)))

def _ep(or_key=None, ak=None, gk=None):
    keys = {'OPENROUTER_API_KEY': or_key, 'ANTHROPIC_API_KEY': ak, 'GEMINI_API_KEY': gk}
    saved = {k: os.environ.get(k) for k in keys}
    for k, v in keys.items():
        if v: os.environ[k] = v
        else: os.environ.pop(k, None)
    return saved

def _er(saved):
    for k, v in saved.items():
        if v is None: os.environ.pop(k, None)
        else: os.environ[k] = v

def t_watch(): assert extract_video_id('https://www.youtube.com/watch?v=BedAaB1RKgE') == 'BedAaB1RKgE'
def t_youtu_be(): assert extract_video_id('https://youtu.be/BedAaB1RKgE') == 'BedAaB1RKgE'
def t_shorts(): assert extract_video_id('https://www.youtube.com/shorts/BedAaB1RKgE') == 'BedAaB1RKgE'
def t_embed(): assert extract_video_id('https://www.youtube.com/embed/BedAaB1RKgE') == 'BedAaB1RKgE'
def t_m_youtube(): assert extract_video_id('https://m.youtube.com/watch?v=BedAaB1RKgE') == 'BedAaB1RKgE'

def t_invalid():
    raised = False
    try: extract_video_id('https://vimeo.com/123456')
    except ValueError: raised = True
    assert raised, 'expected ValueError'

def t_slug_empty(): assert slugify('') == 'video'
def t_slug_unicode():
    r = slugify('Cafe au lait')
    assert isinstance(r, str) and len(r) > 0
def t_slug_cap(): assert len(slugify('a' * 200, max_len=60)) <= 60
def t_slug_normal(): assert slugify('Hello World Test') == 'hello-world-test'

def t_auto_or_default():
    s = _ep(or_key='fake')
    try: assert _auto_detect_provider('default') == 'openrouter'
    finally: _er(s)

def t_auto_anthropic():
    s = _ep(ak='fake')
    try: assert _auto_detect_provider('default') == 'anthropic'
    finally: _er(s)

def t_auto_gemini_direct():
    s = _ep(gk='fake')
    try: assert _auto_detect_provider('gemini') == 'gemini-direct'
    finally: _er(s)

def t_auto_gemini_or():
    s = _ep(or_key='fake')
    try: assert _auto_detect_provider('gemini') == 'openrouter'
    finally: _er(s)

def t_auto_no_key():
    s = _ep(); raised = False
    try: _auto_detect_provider('default')
    except SystemExit: raised = True
    finally: _er(s)
    assert raised

def t_auto_gemini_no_key():
    s = _ep(); raised = False
    try: _auto_detect_provider('gemini')
    except SystemExit: raised = True
    finally: _er(s)
    assert raised

def t_auto_or_beats_anth():
    s = _ep(or_key='k1', ak='k2')
    try: assert _auto_detect_provider('default') == 'openrouter'
    finally: _er(s)

def t_auto_or_beats_anth_premium():
    s = _ep(or_key='k1', ak='k2')
    try: assert _auto_detect_provider('premium') == 'openrouter'
    finally: _er(s)

def t_tool_type(): assert _to_openai_tool_format(TOOL_SCHEMA)['type'] == 'function'
def t_tool_name(): assert _to_openai_tool_format(TOOL_SCHEMA)['function']['name'] == TOOL_SCHEMA['name']
def t_tool_params(): assert _to_openai_tool_format(TOOL_SCHEMA)['function']['parameters'] == TOOL_SCHEMA['input_schema']

def t_reg_anth_default():
    s = _ep()
    try:
        r = resolve_model('anthropic', 'default', refresh=False)
        assert r == LAST_KNOWN_GOOD['anthropic']['default'], f'got {r!r}'
    finally: _er(s)

def t_reg_anth_premium():
    s = _ep()
    try:
        r = resolve_model('anthropic', 'premium', refresh=False)
        assert r == LAST_KNOWN_GOOD['anthropic']['premium'], f'got {r!r}'
    finally: _er(s)

def t_reg_or_live():
    r = resolve_model('openrouter', 'default', refresh=False)
    assert any(r.startswith(f) for f in ALLOWED_FAMILIES), f'{r!r} not in allowlist'

def t_reg_refresh_cache():
    from model_registry import _CACHE_PATH
    before = _CACHE_PATH.stat().st_mtime if _CACHE_PATH.exists() else 0.0
    time.sleep(0.1)
    resolve_model('openrouter', 'default', refresh=True)
    assert _CACHE_PATH.exists()
    assert _CACHE_PATH.stat().st_mtime >= before

def t_allowed_families():
    assert ALLOWED_FAMILIES == ('anthropic/', 'openai/', 'google/'), f'got {ALLOWED_FAMILIES}'

def t_allowlist_blocks_llama():
    fake = {'data': [
        {'id': 'meta-llama/llama-4', 'architecture': {'input_modalities': ['image', 'text']}, 'supported_parameters': ['tools'], 'created': 1700000000},
        {'id': 'anthropic/claude-sonnet-4-6', 'architecture': {'input_modalities': ['image', 'text']}, 'supported_parameters': ['tools'], 'created': 1700000001},
    ]}
    class FR:
        def raise_for_status(self): pass
        def json(self): return fake
    with mock.patch('requests.get', return_value=FR()):
        mid, _ = _resolve_openrouter('default')
    assert 'llama' not in mid.lower(), f'llama leaked: {mid!r}'
    assert mid == 'anthropic/claude-sonnet-4-6', f'got {mid!r}'

def t_refresh_transcript_flag_propagates():
    """--refresh-transcript should be accepted by the CLI without error (shallow dry-run),
    and must appear in --help output."""
    import subprocess
    # 1. --help must list --refresh-transcript
    help_result = subprocess.run(
        [sys.executable, str(WORKSPACE / 'execution' / 'video' / 'youtube_video_analyzer.py'), '--help'],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert help_result.returncode == 0, f'--help failed: {help_result.stderr}'
    assert '--refresh-transcript' in help_result.stdout, (
        '--refresh-transcript flag not found in --help output'
    )
    # 2. Passing --refresh-transcript alongside --dry-run must exit 0 (flag accepted, no crash)
    run_result = subprocess.run(
        [sys.executable, str(WORKSPACE / 'execution' / 'video' / 'youtube_video_analyzer.py'),
         'https://youtu.be/jNQXAC9IVRw', '--dry-run', '--refresh-transcript'],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert run_result.returncode == 0, (
        f'--dry-run --refresh-transcript returned non-zero: {run_result.returncode}\n'
        f'stderr: {run_result.stderr[:500]}'
    )

def t_get_or_fetch_transcript_force_refresh_bypasses_cache():
    """force_refresh=True should bypass the transcript.txt cache and trigger live fetch."""
    import tempfile
    # youtube_video_analyzer is already on sys.path via the top-level sys.path.insert
    from youtube_video_analyzer import get_or_fetch_transcript  # noqa: F811

    with tempfile.TemporaryDirectory() as td:
        work_dir = Path(td)
        (work_dir / 'transcript.txt').write_text('[00:00] cached fake entry\n', encoding='utf-8')

        # force_refresh=False -> reads cache, returns 1 entry
        entries = get_or_fetch_transcript('FAKE_ID', work_dir, force_refresh=False)
        assert len(entries) == 1, f'expected 1 cached entry, got {len(entries)}'
        assert 'cached fake entry' in entries[0].get('text', ''), (
            f'cached text not found in entry: {entries[0]}'
        )

        # force_refresh=True -> skips cache, tries live fetch, raises SystemExit for FAKE_ID
        raised = False
        try:
            get_or_fetch_transcript('FAKE_ID', work_dir, force_refresh=True)
        except SystemExit:
            raised = True
        assert raised, 'expected SystemExit when live-fetching invalid video ID FAKE_ID'


# --- v4.1.1 renderer coercion regression guards (Opus XML-tagged-string output) --- #

_FAKE_META = {'title': 'Test', 'channel': 'Ch', 'duration_sec': 60}

def _render(structured):
    return render_breakdown_markdown(
        url='https://youtu.be/x', metadata=_FAKE_META, structured_data=structured,
        transcript_text=None, frame_count=0, tier='premium',
    )

def t_render_key_takeaways_xml_string():
    # Opus 4 returned key_takeaways as a single XML string; renderer must parse <item> blocks
    md = _render({'summary': 'S.', 'key_takeaways': '<item>First takeaway sentence.</item><item>Second one.</item>'})
    assert '- First takeaway sentence.' in md, 'XML <item> blocks must be parsed into list items'
    assert '- Second one.' in md
    assert '- <\n- i\n- t\n- e' not in md, 'must NOT iterate string char-by-char'

def t_render_pacing_xml_string_with_inner_tags():
    raw = '<item><timestamp>00:05</timestamp><what_changes>Opens with face cam</what_changes></item>'
    md = _render({'summary': '', 'pacing_cuts': raw})
    assert '**00:05**' in md and 'Opens with face cam' in md, 'inner <timestamp>/<what_changes> tags must be parsed'

def t_render_transcript_highlights_xml_string_with_quotes():
    raw = '<item><timestamp>01:00</timestamp><quote>Hello world</quote></item>'
    md = _render({'summary': '', 'transcript_highlights': raw})
    assert '**01:00**' in md and 'Hello world' in md, 'inner <timestamp>/<quote> tags must be parsed'

def t_render_proper_lists_unchanged():
    # Gemini path returns proper lists — must pass through unchanged (no double-wrapping)
    md = _render({
        'summary': 'S.',
        'key_takeaways': ['Bullet one.', 'Bullet two.'],
        'content_ideas': ['Idea A', 'Idea B'],
    })
    assert '- Bullet one.' in md and '- Bullet two.' in md
    assert '- Idea A' in md and '- Idea B' in md


# --- v4.1.1 model registry: prefer undated rev IDs over date-stamped legacy IDs --- #

def t_anthropic_sort_prefers_undated_rev_over_dated():
    # Regression: claude-opus-4-7 (rev 7, undated) must beat claude-opus-4-20250514
    # (rev=20250514 looks larger numerically but is an older dated release).
    # Calls the real _resolve_anthropic via a stubbed models.list() to exercise
    # the sort end-to-end without an HTTP call.
    from datetime import datetime, timezone
    import model_registry as mr

    class _M:
        def __init__(self, id_, created):
            self.id = id_
            self.created_at = datetime.fromisoformat(created).replace(tzinfo=timezone.utc) if 'T' not in created else datetime.fromisoformat(created)

    fake_models = [
        _M('claude-opus-4-20250514', '2025-05-22T00:00:00+00:00'),
        _M('claude-opus-4-6',        '2026-02-04T00:00:00+00:00'),
        _M('claude-opus-4-7',        '2026-04-14T00:00:00+00:00'),
    ]

    class _Client:
        class models:
            @staticmethod
            def list(): return iter(fake_models)
    class _Anthropic:
        @staticmethod
        def Anthropic(api_key=''): return _Client()

    saved_env = os.environ.get('ANTHROPIC_API_KEY')
    os.environ['ANTHROPIC_API_KEY'] = 'sk-fake'
    saved_mod = sys.modules.get('anthropic')
    sys.modules['anthropic'] = _Anthropic
    try:
        mid, _ = mr._resolve_anthropic('premium')
        assert mid == 'claude-opus-4-7', f'expected claude-opus-4-7, got {mid!r}'
    finally:
        if saved_mod is not None: sys.modules['anthropic'] = saved_mod
        else: sys.modules.pop('anthropic', None)
        if saved_env is None: os.environ.pop('ANTHROPIC_API_KEY', None)
        else: os.environ['ANTHROPIC_API_KEY'] = saved_env


if __name__ == '__main__':
    print('=== TIER 1: UNIT TESTS ===')
    print()
    run('extract_video_id: watch URL', t_watch)
    run('extract_video_id: youtu.be URL', t_youtu_be)
    run('extract_video_id: shorts URL', t_shorts)
    run('extract_video_id: embed URL', t_embed)
    run('extract_video_id: m.youtube.com URL', t_m_youtube)
    run('extract_video_id: invalid URL raises ValueError', t_invalid)
    run('slugify: empty -> video', t_slug_empty)
    run('slugify: unicode handled', t_slug_unicode)
    run('slugify: length cap 60', t_slug_cap)
    run('slugify: normal text', t_slug_normal)
    run('_auto_detect_provider: OR key -> openrouter (default)', t_auto_or_default)
    run('_auto_detect_provider: anthropic key -> anthropic', t_auto_anthropic)
    run('_auto_detect_provider: gemini key -> gemini-direct', t_auto_gemini_direct)
    run('_auto_detect_provider: gemini tier + OR key -> openrouter', t_auto_gemini_or)
    run('_auto_detect_provider: no keys -> SystemExit', t_auto_no_key)
    run('_auto_detect_provider: gemini tier + no keys -> SystemExit', t_auto_gemini_no_key)
    run('_auto_detect_provider: OR beats anthropic (default)', t_auto_or_beats_anth)
    run('_auto_detect_provider: OR beats anthropic (premium)', t_auto_or_beats_anth_premium)
    run('_to_openai_tool_format: type=function', t_tool_type)
    run('_to_openai_tool_format: function.name matches TOOL_SCHEMA', t_tool_name)
    run('_to_openai_tool_format: function.parameters = input_schema', t_tool_params)
    run('resolve_model: anthropic/default no key -> LAST_KNOWN_GOOD', t_reg_anth_default)
    run('resolve_model: anthropic/premium no key -> LAST_KNOWN_GOOD', t_reg_anth_premium)
    run('resolve_model: openrouter live -> ALLOWED_FAMILIES prefix', t_reg_or_live)
    run('resolve_model: refresh=True writes cache', t_reg_refresh_cache)
    run('ALLOWED_FAMILIES: exact (anthropic/, openai/, google/)', t_allowed_families)
    run('_resolve_openrouter: meta-llama/llama-4 blocked by allowlist', t_allowlist_blocks_llama)
    run('--refresh-transcript: flag in --help + accepted by --dry-run', t_refresh_transcript_flag_propagates)
    run('get_or_fetch_transcript: force_refresh=False reads cache; force_refresh=True bypasses cache', t_get_or_fetch_transcript_force_refresh_bypasses_cache)
    run('v4.1.1: render coerces XML-tagged key_takeaways string -> list (no char-iter)', t_render_key_takeaways_xml_string)
    run('v4.1.1: render parses inner <timestamp>/<what_changes> in pacing_cuts XML', t_render_pacing_xml_string_with_inner_tags)
    run('v4.1.1: render parses inner <timestamp>/<quote> in transcript_highlights XML', t_render_transcript_highlights_xml_string_with_quotes)
    run('v4.1.1: render passes proper lists through unchanged (Gemini path guard)', t_render_proper_lists_unchanged)
    run('v4.1.1: anthropic sort prefers undated rev (4-7) over dated legacy (4-20250514)', t_anthropic_sort_prefers_undated_rev_over_dated)
    print()
    print(f'Unit: {PASS_COUNT} passed, {FAIL_COUNT} failed')
    if FAILURES:
        print('Failed tests:')
        for n, e in FAILURES: print(f'  - {n}: {e}')
    import sys as _s; _s.exit(0 if FAIL_COUNT == 0 else 1)
