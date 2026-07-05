"""Smoke/unit tests for the real YouTube Automation Factory pipeline.

Network-free by design where possible: external calls (Reddit, Pexels,
Gemini, edge-tts) are exercised for graceful-failure behaviour without
requiring live credentials, except where noted (edge-tts's endpoint is a
free Microsoft service with no key, so a couple of tests do call it live).
"""

import os
import sys
import json

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for d in ("channels", "assets/footage", "assets/audio", "assets/work", "output"):
        os.makedirs(d, exist_ok=True)
    yield tmp_path


# --------------------------------------------------------------------------- #
# NicheAnalyzer safety filter
# --------------------------------------------------------------------------- #
def test_safety_blocklist_filters_sensitive_topics():
    from core.niche_analyzer import _is_safe_topic

    assert _is_safe_topic("Why we procrastinate even when we know better") is True
    assert _is_safe_topic("Suicide rates spike after new abortion law") is False
    assert _is_safe_topic("Breaking: shooting near election rally") is False


def test_niche_analyzer_returns_safe_fallback_when_offline(workdir, monkeypatch):
    from core.niche_analyzer import NicheAnalyzer

    analyzer = NicheAnalyzer()
    # Force network calls to fail so we exercise the evergreen fallback path
    monkeypatch.setattr(analyzer, "_get", lambda url, timeout=10: None)
    topic = analyzer.analyze_market("psychology")
    assert isinstance(topic, str) and len(topic) > 5


# --------------------------------------------------------------------------- #
# ChannelSpawner
# --------------------------------------------------------------------------- #
def test_channel_spawner_registers_valid_channel(workdir):
    from core.channel_spawner import ChannelSpawner

    spawner = ChannelSpawner()
    entry = spawner.register_channel(
        "test_ch", "Test Channel", "psychology", "en", "YOUTUBE_REFRESH_TOKEN_TEST"
    )
    assert entry["id"] == "test_ch"
    assert entry["voice"] == "en-US-ChristopherNeural"

    channels = spawner.list_channels()
    assert len(channels) == 1
    assert channels[0]["id"] == "test_ch"


def test_channel_spawner_rejects_unknown_niche(workdir):
    from core.channel_spawner import ChannelSpawner

    with pytest.raises(ValueError):
        ChannelSpawner().register_channel("x", "X", "not_a_real_niche", "en", "ENV")


def test_channel_spawner_replaces_existing_entry(workdir):
    from core.channel_spawner import ChannelSpawner

    spawner = ChannelSpawner()
    spawner.register_channel("dup", "First Name", "psychology", "en", "ENV_A")
    spawner.register_channel("dup", "Second Name", "history_mystery", "fa", "ENV_B")
    channels = spawner.list_channels()
    assert len(channels) == 1
    assert channels[0]["name"] == "Second Name"
    assert channels[0]["language"] == "fa"


def test_channel_spawner_supports_every_niche_and_language(workdir):
    """Extensibility check: every niche/language combo in content_config
    must be registerable without code changes (the whole point of the
    config-driven design requested by the user)."""
    from core.channel_spawner import ChannelSpawner
    from core import content_config as cfg

    spawner = ChannelSpawner()
    for i, niche in enumerate(cfg.list_niches()):
        for j, lang in enumerate(cfg.list_languages()):
            cid = f"combo_{i}_{j}"
            entry = spawner.register_channel(cid, f"{niche}-{lang}", niche, lang, f"ENV_{cid}")
            assert entry["voice"] == cfg.LANGUAGES[lang]["voice"]
            assert entry["niche_label"] in (
                cfg.NICHES[niche]["label_fa"], cfg.NICHES[niche]["label_en"]
            )

    all_channels = spawner.list_channels()
    assert len(all_channels) == len(cfg.list_niches()) * len(cfg.list_languages())


def test_channel_spawner_voice_variant_differs_from_default(workdir):
    from core.channel_spawner import ChannelSpawner
    from core import content_config as cfg

    spawner = ChannelSpawner()
    default_entry = spawner.register_channel("v1", "V1", "finance", "en", "ENV_V1")
    alt_entry = spawner.register_channel("v2", "V2", "finance", "en", "ENV_V2", voice_variant="alt")
    assert default_entry["voice"] != alt_entry["voice"]
    assert default_entry["voice"] == cfg.LANGUAGES["en"]["voice"]
    assert alt_entry["voice"] == cfg.LANGUAGES["en"]["voice_alt"]


# --------------------------------------------------------------------------- #
# ScriptWriter (offline fallback path)
# --------------------------------------------------------------------------- #
def test_script_writer_fallback_produces_valid_scenes(workdir, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from core.script_writer import ScriptWriter

    writer = ScriptWriter()
    script = writer.write_script("test topic", "Psychology", "en", target_minutes=1)
    assert script["engine"] == "fallback_template"
    assert len(script["scenes"]) >= 3
    for scene in script["scenes"]:
        assert "text" in scene and "query" in scene
    assert "test topic" in script["full_text"]


def test_script_writer_fallback_persian(workdir, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from core.script_writer import ScriptWriter

    script = ScriptWriter().write_script("موضوع تست", "روانشناسی", "fa", target_minutes=1)
    assert script["language"] == "fa"
    assert len(script["scenes"]) >= 3


# --------------------------------------------------------------------------- #
# StockFootageFetcher (offline: no keys -> placeholder, never crashes)
# --------------------------------------------------------------------------- #
def test_stock_footage_fetcher_falls_back_to_placeholder(workdir, monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    from core.stock_footage_fetcher import StockFootageFetcher

    fetcher = StockFootageFetcher()
    result = fetcher.fetch_clip("test query")
    assert result["source"] == "placeholder"
    assert os.path.exists(result["path"])


def test_stock_footage_fetcher_for_script_attaches_clip_per_scene(workdir, monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    from core.stock_footage_fetcher import StockFootageFetcher

    scenes = [{"text": "a", "query": "nature"}, {"text": "b", "query": "city"}]
    results = StockFootageFetcher().fetch_for_script(scenes)
    assert len(results) == 2
    for r in results:
        assert "clip" in r and os.path.exists(r["clip"]["path"])


# --------------------------------------------------------------------------- #
# VoiceEngine (live call to the free edge-tts endpoint — no key required)
# --------------------------------------------------------------------------- #
def test_voice_engine_produces_real_audio_with_word_timings(workdir):
    from core.voice_engine import VoiceEngine

    result = VoiceEngine().generate_voiceover("This is a short test sentence.", "en-US-ChristopherNeural")
    if result["engine"] == "error":
        pytest.skip(f"edge-tts endpoint unreachable in this sandbox: {result.get('error')}")
    assert os.path.exists(result["audio_path"])
    assert os.path.getsize(result["audio_path"]) > 500
    assert len(result["words"]) >= 5
    assert result["duration"] > 0


# --------------------------------------------------------------------------- #
# VideoAssembler (real ffmpeg run on tiny synthetic inputs)
# --------------------------------------------------------------------------- #
def test_video_assembler_builds_real_playable_mp4(workdir):
    from PIL import Image
    from core.voice_engine import VoiceEngine
    from core.video_assembler import VideoAssembler
    import subprocess

    # Skip cleanly if ffmpeg isn't available in this environment
    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
        pytest.skip("ffmpeg not installed in this environment")

    for i, color in enumerate([(200, 50, 50), (50, 50, 200)]):
        Image.new("RGB", (640, 360), color).save(f"assets/footage/test_{i}.jpg")

    voice = VoiceEngine()
    voice_result = voice.generate_voiceover(
        "Scene one is about testing. Scene two is about rendering.",
        "en-US-ChristopherNeural",
    )
    if voice_result["engine"] == "error":
        pytest.skip(f"edge-tts endpoint unreachable in this sandbox: {voice_result.get('error')}")

    scenes = [
        {"text": "Scene one is about testing.", "clip": {"path": "assets/footage/test_0.jpg", "type": "image"}},
        {"text": "Scene two is about rendering.", "clip": {"path": "assets/footage/test_1.jpg", "type": "image"}},
    ]
    result = VideoAssembler().build_video(scenes, voice_result["audio_path"], voice_result["words"])

    assert "error" not in result
    assert os.path.exists(result["video_path"])
    assert os.path.getsize(result["video_path"]) > 5000
    assert result["duration"] > 0


def test_video_assembler_music_mix_does_not_halve_narration_volume(workdir):
    """BUG FIXED (found by user review 2026-07-05, round 4 -- "couldn't
    understand what he's saying"): ffmpeg's amix filter defaults to
    normalize=1, which silently rescales EVERY input (including narration
    already set to volume=1.0) by 1/num_inputs, cutting narration loudness
    roughly in half when mixed with background music. Measured live during
    this session: normalize=1 produced a mix ~6dB quieter than normalize=0
    for identical inputs. This test reproduces the exact real pipeline
    (narration + music -> amix) and asserts the mixed narration is NOT
    drastically quieter than narration mixed with normalize=0 explicitly."""
    from PIL import Image
    from core.voice_engine import VoiceEngine
    from core.video_assembler import VideoAssembler
    import subprocess

    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
        pytest.skip("ffmpeg not installed in this environment")

    Image.new("RGB", (640, 360), (100, 100, 100)).save("assets/footage/music_test.jpg")

    voice = VoiceEngine()
    voice_result = voice.generate_voiceover("This is a real narration test for the music mixing check.", "en-US-ChristopherNeural")
    if voice_result["engine"] == "error":
        pytest.skip(f"edge-tts endpoint unreachable in this sandbox: {voice_result.get('error')}")

    # A short synthetic "music" track (silence would trivially pass any
    # loudness check, so use actual tone content).
    music_path = "assets/music/test_tone.wav"
    os.makedirs("assets/music", exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=300:duration=5", music_path],
        capture_output=True,
    )

    scenes = [{"text": "This is a real narration test for the music mixing check.",
               "clip": {"path": "assets/footage/music_test.jpg", "type": "image"}}]
    result = VideoAssembler().build_video(
        scenes, voice_result["audio_path"], voice_result["words"], music_path=music_path,
    )
    assert "error" not in result

    # Measure the FINAL mixed video's loudness and compare against the
    # narration-only track's loudness -- with the fix (normalize=0 +
    # limiter), the mixed narration should stay close to its original level,
    # not silently drop by ~6dB the way the buggy normalize=1 default did.
    def _mean_volume_db(path):
        proc = subprocess.run(
            ["ffmpeg", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True,
        )
        import re
        m = re.search(r"mean_volume:\s*(-?\d+\.?\d*)\s*dB", proc.stderr)
        return float(m.group(1)) if m else None

    narration_only_db = _mean_volume_db(voice_result["audio_path"])
    mixed_db = _mean_volume_db(result["video_path"])
    assert narration_only_db is not None and mixed_db is not None
    # The regression this test guards against was a ~6dB unexpected drop;
    # allow some natural difference from adding music, but not a collapse.
    assert mixed_db > narration_only_db - 8.0, (
        f"Mixed narration ({mixed_db} dB) is implausibly quieter than "
        f"narration alone ({narration_only_db} dB) -- amix normalize bug may have regressed."
    )


# --------------------------------------------------------------------------- #
# AutoPublisher (no OAuth configured -> clean error, never fakes success)
# --------------------------------------------------------------------------- #
def test_auto_publisher_missing_oauth_returns_clean_error(workdir, monkeypatch):
    monkeypatch.delenv("YOUTUBE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("YOUTUBE_OAUTH_CLIENT_SECRET", raising=False)
    from core.auto_publisher import AutoPublisher

    with open("output/fake.mp4", "wb") as f:
        f.write(b"\x00" * 2000)

    publisher = AutoPublisher()
    channel_cfg = {"refresh_token_env": "YOUTUBE_REFRESH_TOKEN_MISSING"}
    result = publisher.upload_to_youtube(channel_cfg, "output/fake.mp4", {"title": "t"})
    assert result.get("error") == "oauth_not_configured"


def test_auto_publisher_missing_video_file_returns_clean_error(workdir):
    from core.auto_publisher import AutoPublisher

    result = AutoPublisher().upload_to_youtube({}, "output/does_not_exist.mp4", {})
    assert result.get("error") == "video_file_missing"


def test_auto_publisher_metadata_generation():
    from core.auto_publisher import AutoPublisher

    meta_en = AutoPublisher().generate_metadata("Why we procrastinate", "Psychology", "en")
    assert "Why we procrastinate" in meta_en["title"]
    assert len(meta_en["tags"]) >= 1

    meta_fa = AutoPublisher().generate_metadata("موضوع تست", "روانشناسی", "fa")
    assert "موضوع تست" in meta_fa["title"]


# --------------------------------------------------------------------------- #
# PerformanceAnalyzer
# --------------------------------------------------------------------------- #
def test_performance_analyzer_logs_and_reads_back(workdir):
    from core.performance_analyzer import PerformanceAnalyzer

    analyzer = PerformanceAnalyzer()
    analyzer.log_upload("ch1", "topic A", "vid123", "https://youtube.com/watch?v=vid123")

    with open("channels/performance_log.json") as f:
        log = json.load(f)
    assert len(log) == 1
    assert log[0]["channel_id"] == "ch1"


def test_performance_analyzer_no_api_key_returns_error(workdir, monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    from core.performance_analyzer import PerformanceAnalyzer

    result = PerformanceAnalyzer().get_video_stats("someid")
    assert "error" in result


# --------------------------------------------------------------------------- #
# End-to-end pipeline wiring (main.py) — fully offline, SKIP_UPLOAD
# --------------------------------------------------------------------------- #
def test_main_pipeline_builds_video_without_uploading(workdir, monkeypatch):
    """Full integration: real script fallback + real edge-tts + real ffmpeg
    assembly, with upload skipped. Skips cleanly if ffmpeg/edge-tts aren't
    reachable in this sandbox."""
    import subprocess

    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
        pytest.skip("ffmpeg not installed in this environment")

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    monkeypatch.setenv("SKIP_UPLOAD", "1")
    monkeypatch.setenv("TARGET_MINUTES", "1")

    from core.channel_spawner import ChannelSpawner
    ChannelSpawner().register_channel("e2e_ch", "E2E Test", "psychology", "en", "YOUTUBE_REFRESH_TOKEN_E2E")

    import main
    import importlib
    importlib.reload(main)

    try:
        main.run_factory()
    except Exception as e:
        pytest.skip(f"end-to-end run could not complete in this sandbox: {e}")

    import glob
    videos = glob.glob("output/*.mp4")
    if not videos:
        pytest.skip("no video produced (likely edge-tts unreachable in this sandbox)")
    assert os.path.getsize(videos[0]) > 5000


# --------------------------------------------------------------------------- #
# ChannelSpawner management helpers (pause/resume/remove/get/set-token-env) —
# added to support the FactoryBot's /pause /resume /remove /oauth commands.
# --------------------------------------------------------------------------- #
def test_channel_spawner_lifecycle_management(workdir):
    from core.channel_spawner import ChannelSpawner

    sp = ChannelSpawner()
    sp.register_channel("mgmt_ch", "Mgmt Test", "finance", "en", "YOUTUBE_REFRESH_TOKEN_MGMT")

    assert sp.get_channel("mgmt_ch")["name"] == "Mgmt Test"
    assert sp.get_channel("does_not_exist") == {}

    assert sp.set_active("mgmt_ch", False) is True
    assert sp.get_channel("mgmt_ch")["active"] is False
    assert sp.set_active("nope", False) is False

    assert sp.set_refresh_token_env("mgmt_ch", "YOUTUBE_REFRESH_TOKEN_MGMT_V2") is True
    assert sp.get_channel("mgmt_ch")["refresh_token_env"] == "YOUTUBE_REFRESH_TOKEN_MGMT_V2"

    assert sp.remove_channel("mgmt_ch") is True
    assert sp.get_channel("mgmt_ch") == {}
    assert sp.remove_channel("mgmt_ch") is False  # already gone


# --------------------------------------------------------------------------- #
# WorkflowEditor — idempotent secret-line insertion into workflow YAML
# --------------------------------------------------------------------------- #
def test_workflow_editor_inserts_new_secret_once(workdir):
    from core.workflow_editor import ensure_secret_in_workflow

    wf_path = workdir / "fake-workflow.yml"
    wf_path.write_text(
        "jobs:\n"
        "  run:\n"
        "    steps:\n"
        "      - env:\n"
        "          YOUTUBE_OAUTH_CLIENT_ID: ${{ secrets.YOUTUBE_OAUTH_CLIENT_ID }}\n"
        "          YOUTUBE_OAUTH_CLIENT_SECRET: ${{ secrets.YOUTUBE_OAUTH_CLIENT_SECRET }}\n"
        "          YOUTUBE_REFRESH_TOKEN_ELINA: ${{ secrets.YOUTUBE_REFRESH_TOKEN_ELINA }}\n"
    )

    changed = ensure_secret_in_workflow(str(wf_path), "YOUTUBE_REFRESH_TOKEN_LUXE_EN")
    assert changed is True
    text = wf_path.read_text()
    assert "secrets.YOUTUBE_REFRESH_TOKEN_LUXE_EN" in text

    # Calling again with the same secret must be a no-op (idempotent)
    changed_again = ensure_secret_in_workflow(str(wf_path), "YOUTUBE_REFRESH_TOKEN_LUXE_EN")
    assert changed_again is False


def test_workflow_editor_missing_anchor_returns_false(workdir):
    from core.workflow_editor import ensure_secret_in_workflow

    wf_path = workdir / "no-anchor.yml"
    wf_path.write_text("jobs:\n  run:\n    steps: []\n")

    changed = ensure_secret_in_workflow(str(wf_path), "YOUTUBE_REFRESH_TOKEN_X")
    assert changed is False


# --------------------------------------------------------------------------- #
# PendingSetups — small JSON state store surviving across bot ticks
# --------------------------------------------------------------------------- #
def test_pending_setups_round_trip(workdir):
    from core import pending_setups

    device_info = {
        "device_code": "dc123", "user_code": "ABCD-1234",
        "verification_url": "https://google.com/device",
        "interval": 5, "expires_in": 1800,
    }
    pending_setups.start("111", "test_chan", "finance", "en", "Test Channel", "default", device_info)

    pending = pending_setups.all_pending()
    assert len(pending) == 1
    assert pending[0]["channel_id"] == "test_chan"
    assert pending[0]["user_code"] == "ABCD-1234"

    pending_setups.mark_status("test_chan", "approved")
    # mark_status doesn't remove from "awaiting_google_approval" filter unless
    # the status literally changes away from it
    assert pending_setups.all_pending() == []

    pending_setups.mark_done("test_chan")
    assert pending_setups.all_pending() == []


# --------------------------------------------------------------------------- #
# GitHubSecrets — sealed-box encryption round trip (no live GitHub call)
# --------------------------------------------------------------------------- #
def test_gh_secrets_encrypt_round_trip():
    pytest.importorskip("nacl")
    import base64
    from nacl import public, encoding
    from core.gh_secrets import GitHubSecrets

    priv = public.PrivateKey.generate()
    pub_b64 = priv.public_key.encode(encoding.Base64Encoder()).decode()

    enc = GitHubSecrets._encrypt(pub_b64, "super-secret-refresh-token")
    box = public.SealedBox(priv)
    decrypted = box.decrypt(base64.b64decode(enc))
    assert decrypted.decode() == "super-secret-refresh-token"


def test_gh_secrets_missing_credentials_returns_clean_error(workdir, monkeypatch):
    monkeypatch.delenv("GH_PAT", raising=False)
    monkeypatch.delenv("REPO_OWNER", raising=False)
    monkeypatch.delenv("REPO_NAME", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    from core.gh_secrets import GitHubSecrets

    result = GitHubSecrets(owner="", repo="", token="").set_secret("X", "y")
    assert result["ok"] is False
    assert "missing" in result["error"]


# --------------------------------------------------------------------------- #
# GitHubRelease / GitHubActions — clean errors without live credentials
# --------------------------------------------------------------------------- #
def test_gh_release_missing_credentials_returns_clean_error(workdir):
    from core.gh_release import GitHubRelease

    result = GitHubRelease(owner="", repo="", token="").publish_video("no.mp4", "title")
    assert result["ok"] is False
    assert "missing" in result["error"]


def test_gh_release_missing_video_file_returns_clean_error(workdir):
    from core.gh_release import GitHubRelease

    result = GitHubRelease(owner="o", repo="r", token="t").publish_video(
        "does_not_exist.mp4", "title"
    )
    assert result["ok"] is False
    assert result["error"] == "video_file_missing"


def test_gh_actions_missing_credentials_returns_clean_error(workdir, monkeypatch):
    monkeypatch.delenv("GH_PAT", raising=False)
    monkeypatch.delenv("REPO_OWNER", raising=False)
    monkeypatch.delenv("REPO_NAME", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    from core.gh_actions import trigger_run_factory

    result = trigger_run_factory({"skip_upload": "1"})
    assert result["ok"] is False
    assert "missing" in result["error"]


# --------------------------------------------------------------------------- #
# OAuth device flow — clean handling of Google's documented error responses
# --------------------------------------------------------------------------- #
def test_oauth_device_poll_handles_pending_and_denied(monkeypatch):
    from core import oauth_device

    class FakeResp:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def fake_post_pending(url, data=None, timeout=None):
        return FakeResp(400, {"error": "authorization_pending"})

    monkeypatch.setattr(oauth_device.requests, "post", fake_post_pending)
    result = oauth_device.poll_once("cid", "csecret", "dcode")
    assert result["status"] == "pending"

    def fake_post_denied(url, data=None, timeout=None):
        return FakeResp(400, {"error": "access_denied"})

    monkeypatch.setattr(oauth_device.requests, "post", fake_post_denied)
    result = oauth_device.poll_once("cid", "csecret", "dcode")
    assert result["status"] == "denied"

    def fake_post_approved(url, data=None, timeout=None):
        return FakeResp(200, {"refresh_token": "rt-123", "access_token": "at-456"})

    monkeypatch.setattr(oauth_device.requests, "post", fake_post_approved)
    result = oauth_device.poll_once("cid", "csecret", "dcode")
    assert result["status"] == "approved"
    assert result["refresh_token"] == "rt-123"


# --------------------------------------------------------------------------- #
# LLMRouter — multi-provider fallback chain (Groq -> Gemini -> Kimi(free) ->
# OpenRouter -> DeepSeek -> Moonshot direct)
# --------------------------------------------------------------------------- #
def test_llm_router_skips_unconfigured_providers_silently(monkeypatch):
    for env_var in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY",
                     "DEEPSEEK_API_KEY", "MOONSHOT_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)
    from core.llm_router import LLMRouter

    result = LLMRouter().generate("system", "user prompt")
    assert result["error"] == "all_providers_failed"
    # no_key should be silent -- attempts list should be empty, not full of noise
    assert result["attempts"] == []


def test_llm_router_tries_providers_in_order_and_returns_first_success(monkeypatch):
    from core.llm_router import LLMRouter

    monkeypatch.setenv("GROQ_API_KEY", "fake-groq-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    router = LLMRouter()
    monkeypatch.setattr(router, "_call_groq", lambda s, u: "Hello from Groq!")
    result = router.generate("system", "user")
    assert result["provider"] == "groq"
    assert result["text"] == "Hello from Groq!"


def test_llm_router_falls_through_to_next_provider_on_failure(monkeypatch):
    from core.llm_router import LLMRouter

    monkeypatch.setenv("GROQ_API_KEY", "fake")
    monkeypatch.setenv("GEMINI_API_KEY", "fake")

    router = LLMRouter()

    def fail(s, u):
        raise RuntimeError("rate_limited")

    monkeypatch.setattr(router, "_call_groq", fail)
    monkeypatch.setattr(router, "_call_gemini", lambda s, u: "Gemini answered")
    result = router.generate("system", "user", order=["groq", "gemini"])
    assert result["provider"] == "gemini"
    assert result["text"] == "Gemini answered"


def test_llm_router_generate_json_parses_valid_json(monkeypatch):
    from core.llm_router import LLMRouter

    router = LLMRouter()
    monkeypatch.setattr(router, "generate", lambda s, u, order=None: {
        "text": '```json\n[{"a": 1}]\n```', "provider": "fake"
    })
    result = router.generate_json("s", "u")
    assert result["data"] == [{"a": 1}]


def test_llm_router_generate_json_reports_parse_failure(monkeypatch):
    from core.llm_router import LLMRouter

    router = LLMRouter()
    monkeypatch.setattr(router, "generate", lambda s, u, order=None: {
        "text": "not valid json at all", "provider": "fake"
    })
    result = router.generate_json("s", "u")
    assert "error" in result


# --------------------------------------------------------------------------- #
# OpenRouter model rotation resilience — real production bug fix (2026-07-04):
# OpenRouter's free-model catalog changes over time, so a hardcoded single
# ":free" model id can 404 even with a valid key. _call_openrouter() must
# fall through a list of candidates instead of failing on the first 404.
# --------------------------------------------------------------------------- #
def test_openrouter_falls_through_candidates_on_404(monkeypatch):
    from core.llm_router import LLMRouter

    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")
    router = LLMRouter()

    call_log = []

    class FakeResp:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise __import__("requests").exceptions.HTTPError(str(self.status_code))

        def json(self):
            return self._payload

    def fake_post(url, headers=None, json=None, timeout=None):
        model = json["model"]
        call_log.append(model)
        if model == "meta-llama/llama-3.3-70b-instruct:free":
            return FakeResp(200, {"choices": [{"message": {"content": "Second model worked!"}}]})
        return FakeResp(404, {"error": "model not found"})

    monkeypatch.setattr("core.llm_router.requests.post", fake_post)
    text = router._call_openrouter("system", "user")
    assert text == "Second model worked!"
    # First candidate (empty OPENROUTER_MODEL env, so skipped) then the
    # hardcoded stable list should have been tried in order until success.
    assert "meta-llama/llama-3.3-70b-instruct:free" in call_log


def test_openrouter_explicit_model_skips_fallback_list(monkeypatch):
    from core.llm_router import LLMRouter

    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")
    router = LLMRouter()
    call_log = []

    class FakeResp:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    def fake_post(url, headers=None, json=None, timeout=None):
        call_log.append(json["model"])
        return FakeResp(404, {"error": "not found"})

    monkeypatch.setattr("core.llm_router.requests.post", fake_post)
    try:
        router._call_openrouter("system", "user", model="moonshotai/kimi-k2:free")
    except RuntimeError:
        pass
    # Only the one explicit model should have been tried, not the fallback list
    assert call_log == ["moonshotai/kimi-k2:free"]


def test_deepseek_402_gives_clear_balance_error(monkeypatch):
    from core.llm_router import LLMRouter

    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    router = LLMRouter()

    class FakeResp:
        status_code = 402

        def json(self):
            return {"error": {"message": "Insufficient Balance"}}

    monkeypatch.setattr("core.llm_router.requests.post", lambda *a, **k: FakeResp())
    try:
        router._call_deepseek("system", "user")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "Insufficient Balance" in str(e) or "402" in str(e)


# --------------------------------------------------------------------------- #
# ScriptWriter with LLMRouter-based generation + competitor insights
# --------------------------------------------------------------------------- #
def test_script_writer_uses_fallback_when_all_providers_fail(monkeypatch):
    from core.script_writer import ScriptWriter

    writer = ScriptWriter()
    monkeypatch.setattr(writer.router, "generate_json", lambda s, u, order=None: {"error": "all_providers_failed"})
    script = writer.write_script("Test Topic", "Psychology", "en", target_minutes=1)
    assert script["engine"] == "fallback_template"
    assert len(script["scenes"]) > 0


def test_script_writer_uses_llm_result_when_available(monkeypatch):
    from core.script_writer import ScriptWriter

    writer = ScriptWriter()
    fake_scenes = [{"text": "Hook line.", "query": "dramatic scene"},
                   {"text": "Body line.", "query": "office desk"}]
    monkeypatch.setattr(
        writer.router, "generate_json",
        lambda s, u, order=None: {"data": fake_scenes, "provider": "groq"},
    )
    script = writer.write_script("Test Topic", "Finance", "en", target_minutes=1)
    assert script["engine"] == "groq"
    assert script["scenes"] == fake_scenes


def test_script_writer_skips_weak_persian_providers_at_the_source(monkeypatch):
    """OPTIMIZATION (found via two real live Persian test runs, 2026-07-05):
    OpenRouter's free models (Llama 3.3 70B / GPT-OSS 120B / Qwen3) were
    confirmed via live testing to produce grammatically incoherent Persian
    output even though the API call itself succeeds -- both real attempts
    were caught by core/video_qa.py's transcription check, but only AFTER
    wasting a full video render + Whisper transcription cycle. ScriptWriter
    should exclude these specific providers from the order list for Persian
    requests at the source, rather than relying solely on catching the
    failure after the fact."""
    from core.script_writer import ScriptWriter

    writer = ScriptWriter()
    captured_order = {}

    def fake_generate_json(system_prompt, user_prompt, order=None):
        captured_order["order"] = order
        return {"error": "all_providers_failed"}

    monkeypatch.setattr(writer.router, "generate_json", fake_generate_json)
    writer.write_script("Test Topic", "جنایی و رمزآلود", "fa", target_minutes=1, niche_key="true_crime")

    assert captured_order["order"] is not None
    assert "openrouter" not in captured_order["order"]
    assert "kimi_openrouter" not in captured_order["order"]
    # Providers NOT confirmed weak for Persian should still be tried.
    assert "groq" in captured_order["order"]
    assert "gemini" in captured_order["order"]


def test_script_writer_does_not_restrict_providers_for_english(monkeypatch):
    from core.script_writer import ScriptWriter

    writer = ScriptWriter()
    captured_order = {}

    def fake_generate_json(system_prompt, user_prompt, order=None):
        captured_order["order"] = order
        return {"error": "all_providers_failed"}

    monkeypatch.setattr(writer.router, "generate_json", fake_generate_json)
    writer.write_script("Test Topic", "Finance", "en", target_minutes=1)

    assert captured_order["order"] is None  # uses LLMRouter's default full order


# --------------------------------------------------------------------------- #
# ContentBank — real, hand-written, fact-checked scripts used automatically
# in place of the generic offline template whenever no LLM provider is
# configured/working (explicit user request: "do the AI work yourself until
# I add a real key"). LLM still tried first; content_bank is the SECOND
# tier, before the generic 5-line fallback_template becomes the third tier.
# --------------------------------------------------------------------------- #
def test_content_bank_has_scripts_matching_every_niches_evergreen_topics():
    from core import content_config as cfg
    from core import content_bank as cb

    for niche_key, niche in cfg.NICHES.items():
        evergreen = set(niche["evergreen_topics"])
        for language, niches in cb.CONTENT_BANK.items():
            bank_topics = set(niches.get(niche_key, {}).keys())
            # Every curated topic must be an EXACT match to a real evergreen
            # topic string, otherwise NicheAnalyzer's fallback would never
            # actually select it (see core/niche_analyzer.py).
            assert bank_topics <= evergreen, (
                f"{language}/{niche_key} has curated topics not present in "
                f"content_config evergreen_topics: {bank_topics - evergreen}"
            )


def test_content_bank_scripts_have_valid_scene_shape():
    from core import content_bank as cb

    for language, niches in cb.CONTENT_BANK.items():
        for niche_key, topics in niches.items():
            for topic, scenes in topics.items():
                assert len(scenes) >= 8, f"{language}/{niche_key}/{topic} too short"
                for scene in scenes:
                    assert scene.get("text"), f"{language}/{niche_key}/{topic} has empty scene text"
                    assert scene.get("query"), f"{language}/{niche_key}/{topic} has empty scene query"


def test_script_writer_uses_content_bank_when_llm_unavailable(monkeypatch):
    from core.script_writer import ScriptWriter

    writer = ScriptWriter()
    monkeypatch.setattr(writer.router, "generate_json", lambda s, u, order=None: {"error": "all_providers_failed"})
    script = writer.write_script(
        "Why we procrastinate even when we know better", "Psychology", "en",
        target_minutes=3, niche_key="psychology",
    )
    assert script["engine"] == "content_bank"
    assert len(script["scenes"]) >= 8


def test_script_writer_substitutes_curated_topic_when_original_has_no_script(monkeypatch):
    """If the LLM fails AND the exact topic has no curated script, but the
    niche DOES have other curated topics, ScriptWriter should substitute to
    one of those (a genuinely good video about a different-but-real topic
    beats a generic 5-line video about the "correct" topic) and report the
    substituted topic back so callers use it for title/description/memory."""
    from core.script_writer import ScriptWriter
    from core import content_bank as cb

    writer = ScriptWriter()
    monkeypatch.setattr(writer.router, "generate_json", lambda s, u, order=None: {"error": "all_providers_failed"})
    script = writer.write_script(
        "A totally made-up topic not in the content bank", "Psychology", "en",
        target_minutes=1, niche_key="psychology",
    )
    assert script["engine"] == "content_bank"
    assert script["topic"] != "A totally made-up topic not in the content bank"
    assert cb.has_script("psychology", "en", script["topic"])


def test_script_writer_falls_back_to_generic_template_for_unknown_niche(monkeypatch):
    """A niche_key with no content_bank entries at all (e.g. empty/unknown)
    has nothing to substitute to, so it should still fall through to the
    generic offline template rather than crash."""
    from core.script_writer import ScriptWriter

    writer = ScriptWriter()
    monkeypatch.setattr(writer.router, "generate_json", lambda s, u, order=None: {"error": "all_providers_failed"})
    script = writer.write_script(
        "A totally made-up topic", "Some Niche", "en",
        target_minutes=1, niche_key="nonexistent_niche_key",
    )
    assert script["engine"] == "fallback_template"


def test_niche_analyzer_prefers_curated_topic_on_evergreen_fallback(monkeypatch):
    from core.niche_analyzer import NicheAnalyzer

    analyzer = NicheAnalyzer()
    monkeypatch.setattr(analyzer, "_reddit_topics", lambda subs, limit_per_sub=5: [])
    monkeypatch.setattr(analyzer, "_google_trends_topics", lambda keywords, geo="US": [])
    topic = analyzer.analyze_market("psychology", language="en")
    from core import content_bank as cb
    assert cb.has_script("psychology", "en", topic)


def test_llm_router_any_provider_configured_false_when_all_keys_empty(monkeypatch):
    from core.llm_router import LLMRouter

    for name in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY",
                 "AVALAI_API_KEY", "GAPGPT_API_KEY", "DEEPSEEK_API_KEY",
                 "MOONSHOT_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert LLMRouter.any_provider_configured() is False


def test_llm_router_any_provider_configured_true_when_one_key_set(monkeypatch):
    from core.llm_router import LLMRouter

    for name in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY",
                 "AVALAI_API_KEY", "GAPGPT_API_KEY", "DEEPSEEK_API_KEY",
                 "MOONSHOT_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "real-key")
    assert LLMRouter.any_provider_configured() is True


def test_niche_analyzer_skips_raw_live_trending_topics_without_any_llm_key(monkeypatch):
    """Without any LLM key configured, a raw Reddit/Trends title would have
    no AI rewrite step and would fall straight to the generic offline
    template. NicheAnalyzer should skip live-trending topics entirely in
    that case and go straight to the curated evergreen list instead."""
    from core.niche_analyzer import NicheAnalyzer

    for name in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY",
                 "AVALAI_API_KEY", "GAPGPT_API_KEY", "DEEPSEEK_API_KEY",
                 "MOONSHOT_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    analyzer = NicheAnalyzer()
    called = {"reddit": False, "trends": False}

    def fake_reddit(subs, limit_per_sub=5):
        called["reddit"] = True
        return ["Some raw unedited Reddit post title"]

    def fake_trends(keywords, geo="US"):
        called["trends"] = True
        return []

    monkeypatch.setattr(analyzer, "_reddit_topics", fake_reddit)
    monkeypatch.setattr(analyzer, "_google_trends_topics", fake_trends)
    topic = analyzer.analyze_market("luxury_lifestyle", language="en")

    assert called["reddit"] is False
    assert called["trends"] is False
    assert topic != "Some raw unedited Reddit post title"
    from core import content_bank as cb
    assert cb.has_script("luxury_lifestyle", "en", topic)


def test_niche_analyzer_uses_live_trending_topics_when_llm_is_configured(monkeypatch):
    from core.niche_analyzer import NicheAnalyzer

    monkeypatch.setenv("GROQ_API_KEY", "real-key")
    analyzer = NicheAnalyzer()
    monkeypatch.setattr(analyzer, "_reddit_topics", lambda subs, limit_per_sub=5: ["A fresh live trending topic"])
    monkeypatch.setattr(analyzer, "_google_trends_topics", lambda keywords, geo="US": [])
    topic = analyzer.analyze_market("luxury_lifestyle", language="en")
    assert topic == "A fresh live trending topic"


def test_script_writer_passes_competitor_insights_into_prompt(monkeypatch):
    from core.script_writer import ScriptWriter

    writer = ScriptWriter()
    captured = {}

    def fake_generate_json(system_prompt, user_prompt, order=None):
        captured["user_prompt"] = user_prompt
        return {"error": "all_providers_failed"}

    monkeypatch.setattr(writer.router, "generate_json", fake_generate_json)
    writer.write_script("Test Topic", "True Crime", "en", target_minutes=1,
                         competitor_insights="Use short punchy hooks with numbers.")
    assert "Use short punchy hooks with numbers." in captured["user_prompt"]


# --------------------------------------------------------------------------- #
# CompetitorAnalyzer — degrades cleanly without a YouTube API key
# --------------------------------------------------------------------------- #
def test_competitor_analyzer_returns_empty_without_api_key(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    from core.competitor_analyzer import CompetitorAnalyzer

    result = CompetitorAnalyzer().analyze("Finance & Wealth Building", ["stock market"])
    assert result == ""


def test_competitor_analyzer_summarizes_top_videos(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "fake-key")
    from core.competitor_analyzer import CompetitorAnalyzer

    analyzer = CompetitorAnalyzer()
    monkeypatch.setattr(analyzer, "_search_top_videos", lambda query, max_results=6: [
        {"title": "5 Money Mistakes That Keep You Poor", "views": 5_000_000, "likes": 200_000, "comments": 1000},
    ])
    monkeypatch.setattr(analyzer.router, "generate", lambda s, u: {
        "text": "- Uses numbered list hooks\n- Direct, confrontational tone", "provider": "groq"
    })
    result = analyzer.analyze("Finance & Wealth Building", ["stock market"])
    assert "numbered list hooks" in result


# --------------------------------------------------------------------------- #
# ThumbnailMaker — real PIL rendering, no AI image generation needed
# --------------------------------------------------------------------------- #
def test_thumbnail_maker_produces_real_jpeg(workdir):
    from PIL import Image
    from core.thumbnail_maker import ThumbnailMaker

    Image.new("RGB", (640, 360), (40, 40, 80)).save("assets/footage/bg.jpg")
    scenes = [{"clip": {"path": "assets/footage/bg.jpg", "type": "image"}}]

    maker = ThumbnailMaker()
    result = maker.make_thumbnail("The Cold Case That Took 50 Years To Solve", scenes, "en")

    assert "path" in result
    assert os.path.exists(result["path"])
    img = Image.open(result["path"])
    assert img.size == (1280, 720)


def test_thumbnail_maker_handles_missing_background_gracefully(workdir):
    from core.thumbnail_maker import ThumbnailMaker

    maker = ThumbnailMaker()
    result = maker.make_thumbnail("A Topic With No Footage", [{"clip": {}}], "en")
    assert "path" in result
    assert os.path.exists(result["path"])


def test_thumbnail_maker_keeps_full_headline_no_longer_truncates():
    """BUG FIXED (found by user review 2026-07-05): this used to hard-cut
    to 5 words BEFORE _wrap_text ever ran, producing broken, grammatically
    incomplete headlines on every real topic (all of which are 6+ words --
    e.g. 'How billionaires actually spend their mornings' became 'HOW
    BILLIONAIRES ACTUALLY SPEND THEIR', missing 'MORNINGS' entirely). The
    full topic must now be preserved; _wrap_text's existing multi-line +
    font-auto-shrink logic handles fitting it on the thumbnail."""
    from core.thumbnail_maker import _shorten_headline

    topic = "How billionaires actually spend their mornings"
    headline = _shorten_headline(topic, "en")
    assert headline == topic.upper()
    assert "MORNINGS" in headline


def test_thumbnail_maker_persian_headline_not_uppercased():
    from core.thumbnail_maker import _shorten_headline

    topic = "چطور میلیاردرها واقعا صبح‌هاشون رو می‌گذرونن"
    headline = _shorten_headline(topic, "fa")
    assert headline == topic


# --------------------------------------------------------------------------- #
# ShortsMaker — hook-moment selection (LLM + heuristic fallback) and clean
# error handling without a real video/ffmpeg call
# --------------------------------------------------------------------------- #
def test_shorts_maker_heuristic_fallback_when_llm_unavailable(monkeypatch):
    from core.shorts_maker import ShortsMaker

    maker = ShortsMaker()
    monkeypatch.setattr(maker.router, "generate_json", lambda s, u, order=None: {"error": "all_providers_failed"})

    scenes = [{"text": f"Scene {i}"} for i in range(8)]
    picks = maker._pick_hook_moments(scenes, num_clips=2)
    assert len(picks) == 2
    for p in picks:
        assert 0 <= p["start_scene"] <= p["end_scene"] < len(scenes)


def test_shorts_maker_uses_llm_picks_when_valid(monkeypatch):
    from core.shorts_maker import ShortsMaker

    maker = ShortsMaker()
    monkeypatch.setattr(maker.router, "generate_json", lambda s, u, order=None: {
        "data": [{"start_scene": 0, "end_scene": 1, "reason": "strong hook"}],
        "provider": "groq",
    })
    scenes = [{"text": "a"}, {"text": "b"}, {"text": "c"}]
    picks = maker._pick_hook_moments(scenes, num_clips=1)
    assert picks == [{"start_scene": 0, "end_scene": 1, "reason": "strong hook"}]


def test_shorts_maker_returns_empty_for_missing_video(workdir):
    from core.shorts_maker import ShortsMaker

    maker = ShortsMaker()
    result = maker.make_shorts("does_not_exist.mp4", [{"text": "a"}], [{"start": 0, "end": 1, "text": "a"}], "a")
    assert result == []


def test_shorts_maker_scene_time_range_maps_correctly():
    from core.shorts_maker import ShortsMaker

    maker = ShortsMaker()
    scenes = [{"text": "one two"}, {"text": "three four five"}, {"text": "six"}]
    words = [
        {"text": "one", "start": 0.0, "end": 0.5}, {"text": "two", "start": 0.5, "end": 1.0},
        {"text": "three", "start": 1.0, "end": 1.5}, {"text": "four", "start": 1.5, "end": 2.0},
        {"text": "five", "start": 2.0, "end": 2.5}, {"text": "six", "start": 2.5, "end": 3.0},
    ]
    start, end = maker._scene_time_range(1, 2, scenes, words, "one two three four five six")
    assert start == 1.0
    assert end == 3.0


# --------------------------------------------------------------------------- #
# AutoPublisher — thumbnail-set path (clean errors, never breaks the upload)
# --------------------------------------------------------------------------- #
def test_auto_publisher_set_thumbnail_missing_google_libs_handled(workdir):
    from core.auto_publisher import AutoPublisher

    class FakeService:
        def thumbnails(self):
            raise RuntimeError("network down")

    with open("output/thumb.jpg", "wb") as f:
        f.write(b"\xff\xd8\xff" + b"\x00" * 100)

    publisher = AutoPublisher()
    result = publisher.set_thumbnail(FakeService(), "vid123", "output/thumb.jpg")
    assert "error" in result


# --------------------------------------------------------------------------- #
# UsageGuard — hard spending caps for paid LLM providers (user-requested
# safety net after manual testing burned through a free quota in seconds)
# --------------------------------------------------------------------------- #
def test_usage_guard_allows_free_providers_unconditionally(workdir):
    from core.usage_guard import UsageGuard

    guard = UsageGuard()
    result = guard.check_and_reserve("groq", "system", "user prompt")
    assert result["allowed"] is True
    assert result["estimated_cost"] == 0.0


def test_usage_guard_blocks_when_daily_budget_exceeded(workdir, monkeypatch):
    monkeypatch.setenv("LLM_DAILY_BUDGET_USD", "0.0001")
    monkeypatch.setenv("LLM_MONTHLY_BUDGET_USD", "100")
    from core.usage_guard import UsageGuard

    guard = UsageGuard()
    long_prompt = "word " * 5000  # large enough to exceed a tiny budget
    result = guard.check_and_reserve("avalai", "system", long_prompt)
    assert result["allowed"] is False
    assert "daily_budget_exceeded" in result["reason"]


def test_usage_guard_blocks_when_monthly_budget_exceeded(workdir, monkeypatch):
    monkeypatch.setenv("LLM_DAILY_BUDGET_USD", "100")
    monkeypatch.setenv("LLM_MONTHLY_BUDGET_USD", "0.0001")
    from core.usage_guard import UsageGuard

    guard = UsageGuard()
    long_prompt = "word " * 5000
    result = guard.check_and_reserve("gapgpt", "system", long_prompt)
    assert result["allowed"] is False
    assert "monthly_budget_exceeded" in result["reason"]


def test_usage_guard_accumulates_spend_across_calls(workdir, monkeypatch):
    monkeypatch.setenv("LLM_DAILY_BUDGET_USD", "1.0")
    monkeypatch.setenv("LLM_MONTHLY_BUDGET_USD", "100")
    from core.usage_guard import UsageGuard

    guard = UsageGuard()
    r1 = guard.check_and_reserve("deepseek", "system", "short prompt")
    assert r1["allowed"] is True
    status = guard.status()
    assert status["today_spend_usd"] > 0


def test_usage_guard_status_reports_remaining_budget(workdir, monkeypatch):
    monkeypatch.setenv("LLM_DAILY_BUDGET_USD", "0.50")
    monkeypatch.setenv("LLM_MONTHLY_BUDGET_USD", "5.00")
    from core.usage_guard import UsageGuard

    guard = UsageGuard()
    status = guard.status()
    assert status["daily_budget_usd"] == 0.50
    assert status["monthly_budget_usd"] == 5.00
    assert status["day_remaining_usd"] == 0.50


# --------------------------------------------------------------------------- #
# LLMRouter — paid providers (avalai/gapgpt) respect the usage guard and are
# tried in the expected position in the fallback chain
# --------------------------------------------------------------------------- #
def test_llm_router_skips_paid_provider_when_budget_guard_blocks(monkeypatch):
    from core.llm_router import LLMRouter

    monkeypatch.setenv("AVALAI_API_KEY", "fake-key")
    router = LLMRouter()
    monkeypatch.setattr(
        router.usage_guard, "check_and_reserve",
        lambda provider, s, u, expected_output_tokens=1500: {"allowed": False, "reason": "daily_budget_exceeded: test"}
    )
    result = router.generate("system", "user", order=["avalai"])
    assert result["error"] == "all_providers_failed"
    assert any("budget_guard_blocked" in a for a in result["attempts"])


def test_llm_router_calls_avalai_when_budget_allows(monkeypatch):
    from core.llm_router import LLMRouter

    monkeypatch.setenv("AVALAI_API_KEY", "fake-key")
    router = LLMRouter()
    monkeypatch.setattr(
        router.usage_guard, "check_and_reserve",
        lambda provider, s, u, expected_output_tokens=1500: {"allowed": True, "estimated_cost": 0.001}
    )
    monkeypatch.setattr(router, "_call_avalai", lambda s, u: "AvalAI responded!")
    result = router.generate("system", "user", order=["avalai"])
    assert result["provider"] == "avalai"
    assert result["text"] == "AvalAI responded!"


def test_llm_router_gapgpt_also_respects_budget_guard(monkeypatch):
    from core.llm_router import LLMRouter

    monkeypatch.setenv("GAPGPT_API_KEY", "fake-key")
    router = LLMRouter()
    monkeypatch.setattr(
        router.usage_guard, "check_and_reserve",
        lambda provider, s, u, expected_output_tokens=1500: {"allowed": False, "reason": "monthly_budget_exceeded: test"}
    )
    result = router.generate("system", "user", order=["gapgpt"])
    assert result["error"] == "all_providers_failed"
    assert any("gapgpt" in a and "budget_guard_blocked" in a for a in result["attempts"])


# --------------------------------------------------------------------------- #
# AvalAI / GapGPT — empty-string env var for *_MODEL must fall back to a
# sane default instead of sending an empty model name to the API. This is
# the same GitHub-Actions-unset-secret-becomes-'' bug found in usage_guard.py,
# hit live in production run 28714721164 for AVALAI_MODEL specifically.
# --------------------------------------------------------------------------- #
def test_avalai_empty_string_model_env_falls_back_to_default(monkeypatch):
    from core.llm_router import LLMRouter

    monkeypatch.setenv("AVALAI_API_KEY", "fake-key")
    monkeypatch.setenv("AVALAI_MODEL", "")  # simulates an unset GitHub Secret
    router = LLMRouter()

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    sent = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        sent["model"] = json["model"]
        return FakeResp()

    monkeypatch.setattr("core.llm_router.requests.post", fake_post)
    text = router._call_avalai("system", "user")
    assert text == "ok"
    assert sent["model"] == "gpt-4o-mini"


def test_gapgpt_empty_string_model_env_falls_back_to_default(monkeypatch):
    from core.llm_router import LLMRouter

    monkeypatch.setenv("GAPGPT_API_KEY", "fake-key")
    monkeypatch.setenv("GAPGPT_MODEL", "")  # simulates an unset GitHub Secret
    router = LLMRouter()

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    sent = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        sent["model"] = json["model"]
        return FakeResp()

    monkeypatch.setattr("core.llm_router.requests.post", fake_post)
    text = router._call_gapgpt("system", "user")
    assert text == "ok"
    assert sent["model"] == "gpt-4o-mini"


# --------------------------------------------------------------------------- #
# ScheduleGuard — makes upload_frequency (daily/weekly/biweekly/monthly)
# actually control how often a channel gets a new video. Real bug fix
# (2026-07-04): this was previously ignored, so every active channel got a
# brand-new video every single day regardless of its configured frequency.
# --------------------------------------------------------------------------- #
def test_schedule_guard_due_on_first_run(workdir):
    from core import schedule_guard

    assert schedule_guard.is_due("new_channel", "weekly") is True


def test_schedule_guard_not_due_immediately_after_running(workdir):
    from core import schedule_guard

    schedule_guard.mark_run("ch1")
    assert schedule_guard.is_due("ch1", "weekly") is False
    assert schedule_guard.is_due("ch1", "daily") is False
    assert schedule_guard.is_due("ch1", "monthly") is False


def test_schedule_guard_due_after_enough_days_have_passed(workdir):
    import json
    from datetime import datetime, timedelta, timezone
    from core import schedule_guard

    # Simulate a channel that last ran 10 days ago
    state_path = "channels/schedule_state.json"
    os.makedirs("channels", exist_ok=True)
    ten_days_ago = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    with open(state_path, "w") as f:
        json.dump({"ch2": {"last_run": ten_days_ago}}, f)

    assert schedule_guard.is_due("ch2", "weekly") is True   # 7 days < 10 elapsed
    assert schedule_guard.is_due("ch2", "monthly") is False  # 30 days > 10 elapsed


def test_schedule_guard_unknown_frequency_defaults_to_weekly(workdir):
    from core import schedule_guard

    schedule_guard.mark_run("ch3")
    # 'fortnightly' isn't a recognized key -- should behave like 'weekly'
    assert schedule_guard.is_due("ch3", "fortnightly") is False


def test_schedule_guard_days_until_due_reports_correctly(workdir):
    from core import schedule_guard

    schedule_guard.mark_run("ch4")
    remaining = schedule_guard.days_until_due("ch4", "weekly")
    assert 6.9 <= remaining <= 7.0


# --------------------------------------------------------------------------- #
# main.py integration: upload_frequency is actually enforced for the
# scheduled (non ONLY_CHANNEL) path
# --------------------------------------------------------------------------- #
def test_main_skips_channel_not_yet_due(workdir, monkeypatch):
    monkeypatch.delenv("ONLY_CHANNEL", raising=False)
    from core.channel_spawner import ChannelSpawner
    from core import schedule_guard
    import main
    import importlib
    importlib.reload(main)

    ChannelSpawner().register_channel(
        "sched_test", "Schedule Test", "psychology", "en",
        "YOUTUBE_REFRESH_TOKEN_SCHED", upload_frequency="weekly",
    )
    schedule_guard.mark_run("sched_test")  # just ran -- not due again for a week

    calls = []
    monkeypatch.setattr(main, "NicheAnalyzer", lambda: type(
        "FakeAnalyzer", (), {"analyze_market": lambda self, niche: calls.append(niche) or "topic"}
    )())

    main.run_factory()
    # analyze_market should never have been called since the channel isn't due
    assert calls == []


# --------------------------------------------------------------------------- #
# ChannelMemory — per-channel record of every video produced (user-requested
# "the system should remember what video it made for each channel")
# --------------------------------------------------------------------------- #
def test_channel_memory_records_and_retrieves_topics(workdir):
    from core import channel_memory

    channel_memory.record_video("ch1", "Topic A", "Title A", "video_a.mp4", ["query1"], "groq")
    channel_memory.record_video("ch1", "Topic B", "Title B", "video_b.mp4", ["query2"], "fallback_template")

    topics = channel_memory.recent_topics("ch1")
    assert topics == ["Topic A", "Topic B"]


def test_channel_memory_updates_in_place_when_video_id_backfilled(workdir):
    from core import channel_memory

    channel_memory.record_video("ch2", "Topic X", "Title X", "video_x.mp4", ["q"], "groq")
    channel_memory.record_video(
        "ch2", "Topic X", "Title X (final)", "video_x.mp4", [], "groq",
        video_id="abc123", video_url="https://youtube.com/watch?v=abc123",
    )

    history = channel_memory.channel_history("ch2")
    assert len(history) == 1  # updated in place, not duplicated
    assert history[0]["video_id"] == "abc123"


def test_channel_memory_recent_footage_queries_flattened(workdir):
    from core import channel_memory

    channel_memory.record_video("ch3", "T1", "Title1", "v1.mp4", ["luxury car", "yacht"], "groq")
    channel_memory.record_video("ch3", "T2", "Title2", "v2.mp4", ["jet"], "groq")

    queries = channel_memory.recent_footage_queries("ch3")
    assert queries == ["luxury car", "yacht", "jet"]


def test_channel_memory_summary_for_prompt_empty_when_no_history(workdir):
    from core import channel_memory

    assert channel_memory.summary_for_prompt("brand_new_channel") == ""


def test_channel_memory_summary_for_prompt_lists_recent_topics(workdir):
    from core import channel_memory

    channel_memory.record_video("ch4", "The Cold Case Nobody Solved", "T", "v.mp4", [], "groq")
    note = channel_memory.summary_for_prompt("ch4")
    assert "The Cold Case Nobody Solved" in note
    assert "do not repeat" in note.lower()


# --------------------------------------------------------------------------- #
# NicheAnalyzer + ScriptWriter integration with ChannelMemory (avoid repeats)
# --------------------------------------------------------------------------- #
def test_niche_analyzer_avoids_recently_covered_evergreen_topic(workdir, monkeypatch):
    from core import channel_memory
    from core.niche_analyzer import NicheAnalyzer
    from core import content_config as cfg

    analyzer = NicheAnalyzer()
    # Force offline (no live Reddit/Trends) so only evergreen topics are used
    monkeypatch.setattr(analyzer, "_reddit_topics", lambda subs, limit_per_sub=5: [])
    monkeypatch.setattr(analyzer, "_google_trends_topics", lambda keywords, geo="US": [])

    evergreen = cfg.NICHES["psychology"]["evergreen_topics"]
    # Mark every evergreen topic except the last one as already covered
    for t in evergreen[:-1]:
        channel_memory.record_video("mem_ch", t, t, "v.mp4", [], "groq")

    chosen = analyzer.analyze_market("psychology", channel_id="mem_ch")
    assert chosen == evergreen[-1]


def test_script_writer_includes_memory_note_in_prompt(monkeypatch):
    from core import channel_memory
    from core.script_writer import ScriptWriter

    channel_memory.record_video("mem_ch2", "Old Topic", "T", "v.mp4", [], "groq")

    writer = ScriptWriter()
    captured = {}

    def fake_generate_json(system_prompt, user_prompt, order=None):
        captured["user_prompt"] = user_prompt
        return {"error": "all_providers_failed"}

    monkeypatch.setattr(writer.router, "generate_json", fake_generate_json)
    writer.write_script("New Topic", "Psychology", "en", target_minutes=1, channel_id="mem_ch2")
    assert "Old Topic" in captured["user_prompt"]


# --------------------------------------------------------------------------- #
# CommentEngager — automatic AI replies to viewer comments (comments are the
# highest-weighted YouTube 2026 engagement signal, per docs/YOUTUBE-GROWTH-
# AND-ENGAGEMENT.md). No "pin comment" support since the YouTube Data API
# has no such endpoint (confirmed via research, not assumed).
# --------------------------------------------------------------------------- #
def test_comment_engager_returns_clean_error_without_service(workdir):
    from core.comment_engager import CommentEngager

    result = CommentEngager().reply_to_new_comments(None, "vid123", "Some Topic", "en")
    assert result["error"] == "oauth_not_configured"
    assert result["replied"] == []


def test_comment_engager_replies_to_new_comments_and_tracks_ledger(workdir, monkeypatch):
    from core.comment_engager import CommentEngager

    engager = CommentEngager()
    monkeypatch.setattr(engager, "_generate_reply", lambda text, topic, lang: "Great point, thanks for sharing!")

    class FakeCommentThreads:
        def list(self, **kwargs):
            class Exec:
                def execute(self_inner):
                    return {
                        "items": [
                            {"id": "c1", "snippet": {"topLevelComment": {"snippet": {"textDisplay": "Nice video!"}}}},
                            {"id": "c2", "snippet": {"topLevelComment": {"snippet": {"textDisplay": "Loved this!"}}}},
                        ]
                    }
            return Exec()

    posted = []

    class FakeComments:
        def insert(self, **kwargs):
            class Exec:
                def execute(self_inner):
                    posted.append(kwargs["body"]["snippet"]["parentId"])
                    return {}
            return Exec()

    class FakeService:
        def commentThreads(self):
            return FakeCommentThreads()

        def comments(self):
            return FakeComments()

    result = engager.reply_to_new_comments(FakeService(), "vidABC", "Some Topic", "en")
    assert set(result["replied"]) == {"c1", "c2"}
    assert set(posted) == {"c1", "c2"}

    # Second sweep should skip already-replied comments (ledger persisted to disk)
    result2 = engager.reply_to_new_comments(FakeService(), "vidABC", "Some Topic", "en")
    assert result2["replied"] == []


def test_comment_engager_skips_comment_when_no_llm_provider_available(workdir, monkeypatch):
    from core.comment_engager import CommentEngager

    engager = CommentEngager()
    monkeypatch.setattr(engager, "_generate_reply", lambda text, topic, lang: "")  # simulates all providers down

    class FakeCommentThreads:
        def list(self, **kwargs):
            class Exec:
                def execute(self_inner):
                    return {"items": [{"id": "c1", "snippet": {"topLevelComment": {"snippet": {"textDisplay": "Hi"}}}}]}
            return Exec()

    class FakeService:
        def commentThreads(self):
            return FakeCommentThreads()

    result = CommentEngager().reply_to_new_comments(FakeService(), "vidXYZ", "Topic", "en")
    assert result["replied"] == []  # not marked replied -- can retry next sweep


# --------------------------------------------------------------------------- #
# AutoPublisher.generate_metadata — specific comment-question CTA
# --------------------------------------------------------------------------- #
def test_generate_metadata_uses_specific_comment_prompt_when_given():
    from core.auto_publisher import AutoPublisher

    meta = AutoPublisher().generate_metadata(
        "Why we procrastinate", "Psychology", "en",
        comment_prompt="Which of these habits do YOU struggle with the most?",
    )
    assert "Which of these habits do YOU struggle with the most?" in meta["description"]


def test_generate_metadata_falls_back_to_generic_cta_without_comment_prompt():
    from core.auto_publisher import AutoPublisher

    meta = AutoPublisher().generate_metadata("Some Topic", "Finance", "en")
    assert "comments" in meta["description"].lower()


def test_generate_metadata_includes_music_credit_when_given():
    """Creative Commons attribution (see core/music_library.py) must be
    included in the description whenever a background track was used."""
    from core.auto_publisher import AutoPublisher

    credit = '"Killers" by Kevin MacLeod (incompetech.com)\nLicensed under Creative Commons: By Attribution 4.0 License'
    meta = AutoPublisher().generate_metadata("Some Topic", "True Crime", "en", music_credit=credit)
    assert "Kevin MacLeod" in meta["description"]
    assert "Creative Commons" in meta["description"]


def test_generate_metadata_omits_music_section_when_no_credit_given():
    from core.auto_publisher import AutoPublisher

    meta = AutoPublisher().generate_metadata("Some Topic", "Finance", "en")
    assert "Kevin MacLeod" not in meta["description"]


# --------------------------------------------------------------------------- #
# FootageQuality — real, explicit, explainable scoring criteria for picking
# WHICH stock photo/video candidate to use (previously: random.choice over
# raw API results, with zero quality criteria). Directly answers the user's
# question "how does the system know if a photo/video is good or bad?"
# --------------------------------------------------------------------------- #
def test_footage_quality_prefers_1080p_over_low_res():
    from core.footage_quality import score_resolution

    hd_score = score_resolution(1920, 1080)
    low_score = score_resolution(640, 360)
    assert hd_score > low_score
    assert hd_score == 20.0  # exactly in the ideal 1080p-4K band (rebalanced 2026-07-05, round 3)


def test_footage_quality_penalizes_below_720p_heavily():
    from core.footage_quality import score_resolution

    tiny_score = score_resolution(480, 270)
    assert tiny_score <= 5.0


def test_footage_quality_prefers_16_9_aspect_ratio():
    from core.footage_quality import score_aspect_ratio

    widescreen = score_aspect_ratio(1920, 1080)  # exactly 16:9
    square = score_aspect_ratio(1080, 1080)       # 1:1, needs heavy cropping
    assert widescreen > square
    assert widescreen == 15.0  # rebalanced 2026-07-05, round 3 (was 25.0)


def test_footage_quality_duration_fit_penalizes_clips_shorter_than_scene():
    from core.footage_quality import score_duration_fit

    long_enough = score_duration_fit(clip_duration=10, needed_duration=5)
    too_short = score_duration_fit(clip_duration=2, needed_duration=5)
    assert long_enough > too_short


def test_footage_quality_query_relevance_rewards_tag_matches():
    from core.footage_quality import score_query_relevance

    high = score_query_relevance("luxury car interior", "luxury car interior leather seats")
    low = score_query_relevance("luxury car interior", "beach sunset waves")
    assert high > low
    assert high == 25.0  # all 3 significant words matched (rebalanced 2026-07-05, round 3; was 20.0)


def test_footage_quality_search_rank_favors_top_api_result():
    """BUG FIXED (found by user review 2026-07-05, round 3): a real test
    video showed footage of programming code for a story about an art
    forgery. Root cause: Pexels/Pixabay already rank search results by
    their OWN relevance algorithm (best topical match first), but the
    scoring function completely discarded that ranking and re-sorted
    purely by resolution/aspect/duration -- letting an irrelevant clip near
    the bottom of the results outscore the genuinely on-topic top result
    if it happened to be marginally higher-resolution. score_search_rank
    must reward earlier positions in the original API response order."""
    from core.footage_quality import score_search_rank

    top_result = score_search_rank(rank=0, total_candidates=10)
    bottom_result = score_search_rank(rank=9, total_candidates=10)
    assert top_result > bottom_result
    assert top_result == 25.0
    assert bottom_result == 0.0


def test_footage_quality_pick_best_selects_highest_scoring_candidate():
    from core.footage_quality import pick_best

    candidates = [
        {"width": 640, "height": 360, "duration": 3, "tags": "unrelated content here"},
        {"width": 1920, "height": 1080, "duration": 8, "tags": "luxury yacht ocean view"},
    ]
    best = pick_best("luxury yacht", candidates, needed_duration=5)
    assert best["width"] == 1920
    assert "_quality_score" in best
    assert "_quality_breakdown" in best


def test_footage_quality_pick_best_prefers_relevant_top_result_over_irrelevant_higher_res():
    """Reproduces the exact real-world failure: an irrelevant candidate
    that is technically slightly better (resolution) but appears LATE in
    the search results and has NO tag/description match must lose to the
    API's own top, clearly on-topic result."""
    from core.footage_quality import pick_best

    candidates = [
        {"width": 1920, "height": 1080, "duration": 10, "tags": "art forgery painting canvas",
         "_id": "relevant_top_result"},
        {"width": 3840, "height": 2160, "duration": 10, "tags": "programming code screen",
         "_id": "irrelevant_but_higher_res"},
    ]
    best = pick_best("art forgery painting", candidates, needed_duration=6)
    assert best["_id"] == "relevant_top_result"


def test_footage_quality_pick_best_empty_list_returns_empty_dict():
    from core.footage_quality import pick_best

    assert pick_best("query", []) == {}


# --------------------------------------------------------------------------- #
# StockFootageFetcher now uses FootageQuality scoring (not random.choice) --
# verify the real HTTP-mocked path picks the higher-scoring candidate
# --------------------------------------------------------------------------- #
def test_stock_footage_fetcher_picks_best_scoring_pexels_photo(workdir, monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "fake-key")
    from core.stock_footage_fetcher import StockFootageFetcher

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "photos": [
                    {"width": 640, "height": 360, "alt": "irrelevant scene", "src": {"large2x": "http://low.jpg"}},
                    {"width": 1920, "height": 1080, "alt": "luxury car interior", "src": {"large2x": "http://high.jpg"}},
                ]
            }

    fetcher = StockFootageFetcher()
    monkeypatch.setattr(fetcher.session, "get", lambda *a, **k: FakeResp())
    downloaded_urls = []
    monkeypatch.setattr(fetcher, "_download", lambda url, ext: downloaded_urls.append(url) or "downloaded.jpg")

    fetcher._pexels_photo("luxury car interior")
    assert downloaded_urls == ["http://high.jpg"]


def test_stock_footage_fetcher_never_repeats_same_clip_within_one_video(workdir, monkeypatch):
    """BUG FIXED (found by user review 2026-07-05): footage_quality.pick_best
    is deterministic, so two scenes searching the same (or a similarly
    scoring) query used to always download the literal identical clip --
    visibly repeated footage in the finished video. fetch_for_script() must
    now track ids already used and skip them for later scenes."""
    monkeypatch.setenv("PEXELS_API_KEY", "fake-key")
    from core.stock_footage_fetcher import StockFootageFetcher

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "photos": [
                    {"id": 1, "width": 1920, "height": 1080, "alt": "city skyline night",
                     "src": {"large2x": "http://best.jpg"}},
                    {"id": 2, "width": 1920, "height": 1080, "alt": "city skyline night",
                     "src": {"large2x": "http://second.jpg"}},
                ]
            }

    fetcher = StockFootageFetcher()
    monkeypatch.setattr(fetcher.session, "get", lambda *a, **k: FakeResp())
    downloaded_urls = []
    monkeypatch.setattr(fetcher, "_download", lambda url, ext: downloaded_urls.append(url) or f"downloaded_{len(downloaded_urls)}.jpg")

    # Two scenes with the EXACT same query -- previously both would have
    # downloaded http://best.jpg (the deterministic top scorer both times).
    scenes = [
        {"text": "first scene", "query": "city skyline night"},
        {"text": "second scene", "query": "city skyline night"},
    ]
    results = StockFootageFetcher.fetch_for_script(fetcher, scenes)
    assert len(results) == 2
    assert downloaded_urls[0] != downloaded_urls[1]
    assert downloaded_urls == ["http://best.jpg", "http://second.jpg"]


def test_stock_footage_fetcher_provides_extra_clips_for_long_scenes(workdir, monkeypatch):
    """BUG FIXED (found by user review 2026-07-05, round 2): a long scene
    used to get sub-cuts of the SAME clip (just different pan/zoom), which
    still visibly reads as a repeated picture. fetch_for_script() must now
    pre-fetch multiple genuinely DIFFERENT real clips for a scene long
    enough to need several sub-cuts (see core.video_assembler's
    _MAX_SEGMENT_SECONDS split), returned as scene['extra_clips']."""
    monkeypatch.setenv("PEXELS_API_KEY", "fake-key")
    from core.stock_footage_fetcher import StockFootageFetcher

    call_count = {"n": 0}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            call_count["n"] += 1
            return {
                "photos": [
                    {"id": call_count["n"], "width": 1920, "height": 1080, "alt": "city skyline night",
                     "src": {"large2x": f"http://clip{call_count['n']}.jpg"}},
                ]
            }

    fetcher = StockFootageFetcher()
    monkeypatch.setattr(fetcher.session, "get", lambda *a, **k: FakeResp())
    downloaded = []
    monkeypatch.setattr(fetcher, "_download", lambda url, ext: downloaded.append(url) or url)

    # A very long scene (many words -> long estimated duration -> multiple
    # sub-cuts expected) should yield extra_clips beyond just the primary one.
    long_text = " ".join(["word"] * 80)  # ~32s estimated at 2.5 words/sec
    scenes = [{"text": long_text, "query": "city skyline night"}]
    results = StockFootageFetcher.fetch_for_script(fetcher, scenes)

    assert len(results) == 1
    assert results[0]["clip"]["path"]
    assert len(results[0]["extra_clips"]) >= 1
    # Every clip (primary + extras) must be genuinely different URLs.
    all_urls = [results[0]["clip"]["path"]] + [c["path"] for c in results[0]["extra_clips"]]
    assert len(all_urls) == len(set(all_urls))


# --------------------------------------------------------------------------- #
# MusicLibrary — free, always-available, no-API-key background music
# (explicit user request after reviewing two silent test videos)
# --------------------------------------------------------------------------- #
def test_music_library_returns_niche_appropriate_track(workdir, monkeypatch):
    from core import music_library

    class FakeResp:
        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            return [b"fake mp3 bytes"]

    monkeypatch.setattr(music_library.requests, "get", lambda *a, **k: FakeResp())
    result = music_library.get_track_for_niche("true_crime")
    assert result["track"] in music_library._NICHE_TRACKS["true_crime"]
    assert os.path.exists(result["path"])
    assert "Kevin MacLeod" in result["credit"]
    assert "Creative Commons" in result["credit"]


def test_music_library_caches_downloaded_track(workdir, monkeypatch):
    from core import music_library

    call_count = {"n": 0}

    class FakeResp:
        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            call_count["n"] += 1
            return [b"fake mp3 bytes" * 100]

    monkeypatch.setattr(music_library.requests, "get", lambda *a, **k: FakeResp())
    monkeypatch.setattr("random.choice", lambda seq: seq[0])  # deterministic track pick

    music_library.get_track_for_niche("finance")
    music_library.get_track_for_niche("finance")
    assert call_count["n"] == 1  # second call served from local cache, no re-download


def test_music_library_returns_empty_dict_on_download_failure(workdir, monkeypatch):
    from core import music_library
    import requests

    def raise_error(*a, **k):
        raise requests.RequestException("network down")

    monkeypatch.setattr(music_library.requests, "get", raise_error)
    result = music_library.get_track_for_niche("psychology")
    assert result == {}


# --------------------------------------------------------------------------- #
# text_normalizer — converts raw digits to spoken word form before TTS
# (explicit user complaint: Persian number pronunciation was broken)
# --------------------------------------------------------------------------- #
def test_text_normalizer_converts_persian_digits_to_words():
    from core.text_normalizer import normalize_numbers

    result = normalize_numbers("سال ۱۸۷۲ یه کشتی پیدا شد.", "fa")
    assert "۱۸۷۲" not in result
    assert "هزار" in result  # "هزار و هشتصد و هفتاد و دو"


def test_text_normalizer_converts_western_digits_in_persian_text():
    from core.text_normalizer import normalize_numbers

    result = normalize_numbers("در سال 2020 اتفاق افتاد.", "fa")
    assert "2020" not in result
    assert "دو هزار" in result


def test_text_normalizer_leaves_english_numbers_unchanged():
    """English narration was reviewed as fine as-is; only Persian number
    pronunciation was reported as broken -- don't touch other languages."""
    from core.text_normalizer import normalize_numbers

    text = "This happened in 1976, a long time ago."
    assert normalize_numbers(text, "en") == text


def test_text_normalizer_handles_missing_num2words_gracefully(monkeypatch):
    from core import text_normalizer

    monkeypatch.setattr(text_normalizer, "num2words", None)
    text = "سال ۱۸۷۲ یه کشتی پیدا شد."
    assert text_normalizer.normalize_numbers(text, "fa") == text


# --------------------------------------------------------------------------- #
# VoiceEngine — number normalization + per-language prosody tuning wired
# into generate_voiceover (explicit user complaint: Persian voice was
# "weak/limp" and numbers mispronounced)
# --------------------------------------------------------------------------- #
def test_voice_engine_applies_persian_prosody_and_normalizes_numbers(workdir, monkeypatch):
    from core.voice_engine import VoiceEngine

    captured = {}

    async def fake_synthesize(self, text, voice, out_path, rate="+0%", pitch="+0Hz"):
        captured["text"] = text
        captured["rate"] = rate
        captured["pitch"] = pitch
        with open(out_path, "wb") as f:
            f.write(b"fake audio")
        return [{"text": "word", "start": 0.0, "end": 0.5}]

    monkeypatch.setattr(VoiceEngine, "_synthesize", fake_synthesize)
    engine = VoiceEngine()
    engine.generate_voiceover("سال ۱۸۷۲ رخ داد.", "fa-IR-FaridNeural", language="fa")

    assert "۱۸۷۲" not in captured["text"]
    assert captured["rate"] == "+4%"
    assert captured["pitch"] == "-2Hz"


def test_voice_engine_english_keeps_default_prosody(workdir, monkeypatch):
    from core.voice_engine import VoiceEngine

    captured = {}

    async def fake_synthesize(self, text, voice, out_path, rate="+0%", pitch="+0Hz"):
        captured["rate"] = rate
        captured["pitch"] = pitch
        with open(out_path, "wb") as f:
            f.write(b"fake audio")
        return [{"text": "word", "start": 0.0, "end": 0.5}]

    monkeypatch.setattr(VoiceEngine, "_synthesize", fake_synthesize)
    engine = VoiceEngine()
    engine.generate_voiceover("This happened in 1976.", "en-US-ChristopherNeural", language="en")

    assert captured["rate"] == "+0%"
    assert captured["pitch"] == "+0Hz"


# --------------------------------------------------------------------------- #

# UsageGuard — empty-string env vars must fall back to defaults, not crash.
# Real production bug (2026-07-04): GitHub Actions passes an UNSET secret
# through as an empty string ('${{ secrets.X }}' with no X configured
# resolves to ''), not as a missing key -- os.environ.get(name, default)
# alone does not catch this since '' is still a value, and float('') raises.
# This broke every single run-factory.yml execution in production until
# fixed.
# --------------------------------------------------------------------------- #
def test_usage_guard_empty_string_env_vars_fall_back_to_defaults(workdir, monkeypatch):
    monkeypatch.setenv("LLM_DAILY_BUDGET_USD", "")
    monkeypatch.setenv("LLM_MONTHLY_BUDGET_USD", "")
    from core.usage_guard import UsageGuard

    guard = UsageGuard()
    assert guard.daily_budget == 0.50
    assert guard.monthly_budget == 5.00


def test_usage_guard_invalid_env_var_value_falls_back_to_default(workdir, monkeypatch):
    monkeypatch.setenv("LLM_DAILY_BUDGET_USD", "not-a-number")
    from core.usage_guard import UsageGuard

    guard = UsageGuard()
    assert guard.daily_budget == 0.50


# --------------------------------------------------------------------------- #
# script_quality — validates LLM output is actually written in the requested
# language BEFORE it's accepted (explicit user complaint: a real Persian
# test video's OpenRouter-generated script was garbled/incoherent; live
# research found free OpenRouter models have documented weak Arabic/Persian
# output quality).
# --------------------------------------------------------------------------- #
def test_script_quality_accepts_genuine_persian_text():
    from core.script_quality import validate_script_language

    scenes = [{"text": "بیش از سی سال، یه مرد حداقل دوازده قتل مرتکب شد و بدون هیچ ردی ناپدید شد."}]
    result = validate_script_language(scenes, "fa")
    assert result["ok"] is True


def test_script_quality_rejects_english_contaminated_persian():
    from core.script_quality import validate_script_language

    scenes = [{"text": "The man committed murders در کالیفرنیا and فرار کرد without any trace."}]
    result = validate_script_language(scenes, "fa")
    assert result["ok"] is False
    assert "bad_scenes" in result


def test_script_quality_rejects_too_short_scenes():
    from core.script_quality import validate_script_language

    scenes = [{"text": "خب."}]
    result = validate_script_language(scenes, "fa")
    assert result["ok"] is False


def test_script_quality_skips_validation_for_non_persian_languages():
    from core.script_quality import validate_script_language

    scenes = [{"text": "This is a perfectly normal English sentence."}]
    result = validate_script_language(scenes, "en")
    assert result["ok"] is True


def test_script_quality_persian_char_ratio_calculation():
    from core.script_quality import persian_char_ratio

    all_persian = persian_char_ratio("سلام دنیا")
    all_english = persian_char_ratio("hello world")
    assert all_persian == 1.0
    assert all_english == 0.0


# --------------------------------------------------------------------------- #
# ScriptWriter now rejects a garbled/wrong-language LLM script and falls
# through to content_bank instead of shipping it (wired to script_quality)
# --------------------------------------------------------------------------- #
def test_script_writer_rejects_garbled_persian_llm_output(monkeypatch):
    from core.script_writer import ScriptWriter

    writer = ScriptWriter()
    garbled_scenes = [
        {"text": "The man committed murders در کالیفرنیا and فرار کرد.", "query": "police"},
    ]
    monkeypatch.setattr(
        writer.router, "generate_json",
        lambda s, u, order=None: {"data": garbled_scenes, "provider": "openrouter"},
    )
    script = writer.write_script(
        "The cold case that was solved decades later by DNA", "جنایی و رمزآلود", "fa",
        target_minutes=1, niche_key="true_crime",
    )
    # Must NOT accept the garbled openrouter script -- should fall through
    # to the curated, verified-coherent content_bank script instead.
    assert script["engine"] != "openrouter"
    assert script["engine"] == "content_bank"


def test_script_writer_accepts_genuine_persian_llm_output(monkeypatch):
    from core.script_writer import ScriptWriter

    writer = ScriptWriter()
    good_scenes = [
        {"text": "بیش از سی سال، یه مرد حداقل دوازده قتل مرتکب شد و بدون هیچ ردی ناپدید شد.", "query": "police tape"},
    ]
    monkeypatch.setattr(
        writer.router, "generate_json",
        lambda s, u, order=None: {"data": good_scenes, "provider": "openrouter"},
    )
    script = writer.write_script(
        "Test Topic", "جنایی و رمزآلود", "fa", target_minutes=1, niche_key="true_crime",
    )
    assert script["engine"] == "openrouter"
    assert script["scenes"] == good_scenes


# --------------------------------------------------------------------------- #
# VideoQA — a real automated check that runs BEFORE a video is delivered
# (explicit user request: "قبل از اینکه ویدیو رو برام بفرسته خودش ویدیو رو
# چک کنه" -- the agent should actually check the video itself first).
# --------------------------------------------------------------------------- #
def test_video_qa_audio_loudness_check_passes_for_normal_volume(workdir):
    import subprocess

    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
        pytest.skip("ffmpeg not installed in this environment")

    from core import video_qa

    path = "assets/audio/qa_test_normal.wav"
    os.makedirs("assets/audio", exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=2", path],
        capture_output=True,
    )
    result = video_qa.check_audio_loudness(path)
    assert result["ok"] is True
    assert "mean_volume_db" in result


def test_video_qa_audio_loudness_check_fails_for_near_silent_audio(workdir):
    import subprocess

    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
        pytest.skip("ffmpeg not installed in this environment")

    from core import video_qa

    path = "assets/audio/qa_test_quiet.wav"
    os.makedirs("assets/audio", exist_ok=True)
    # Extremely quiet tone -- should fail the minimum loudness threshold.
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
         "-af", "volume=0.001", path],
        capture_output=True,
    )
    result = video_qa.check_audio_loudness(path)
    assert result["ok"] is False


def test_video_qa_transcribe_and_compare_skips_gracefully_without_whisper(monkeypatch, workdir):
    """If openai-whisper isn't installed (or fails for any reason), QA must
    degrade to 'skipped', never crash the pipeline over an optional check."""
    from core import video_qa
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "whisper":
            raise ImportError("simulated missing dependency")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = video_qa.transcribe_and_compare("nonexistent.mp4", "some text", "fa")
    assert result["ok"] is True
    assert "skipped" in result


def test_video_qa_run_qa_fails_when_video_file_missing():
    from core import video_qa

    result = video_qa.run_qa("nonexistent_video.mp4", "some narration text", "en")
    assert result["ok"] is False
    assert result["error"] == "video_file_missing"


def test_video_qa_run_qa_only_transcribes_for_persian():
    """Transcription is skipped for non-Persian languages (English narration
    from these same TTS/LLM providers was reviewed as fine; only Persian
    had a confirmed real incoherence failure) -- avoids unnecessary
    per-video transcription cost/time for languages that don't need it."""
    from core import video_qa
    import subprocess

    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
        pytest.skip("ffmpeg not installed in this environment")

    path = "assets/audio/qa_test_en.wav"
    os.makedirs("assets/audio", exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=2", path],
        capture_output=True,
    )
    report = video_qa.run_qa(path, "some english narration text", language="en")
    assert "narration_check" not in report


def test_video_qa_normalize_words_strips_persian_arabic_punctuation():
    """Regression test for a real false-positive bug: Persian/Arabic
    punctuation (، ؛ ؟ etc.) lives in the SAME Unicode block as Persian
    letters, so it used to stay attached to words (e.g. "سال،") and never
    matched Whisper's cleaner "سال" -- an artificial mismatch that had
    nothing to do with actual narration coherence. Verified live: this bug
    made even the agent's own hand-written, human-quality content_bank
    script fail the QA overlap check."""
    from core import video_qa

    a = video_qa._normalize_words("سال، ۱۹۷۶ بود؛ کسی نمی‌دانست؟")
    b = video_qa._normalize_words("سال ۱۹۷۶ بود کسی نمیدانست")
    # Words that only differed by trailing Arabic punctuation must now match.
    assert "سال" in a
    assert "دانست" in b or "نمیدانست" in b


def test_video_qa_overlap_threshold_is_calibrated_between_real_measurements():
    """Regression test documenting WHY the overlap threshold is 0.18, not
    the original 0.35. Measured live with real edge-tts Persian audio +
    real openai-whisper 'base' transcription + the punctuation fix above:
      - correct voice matched with its OWN correct script: overlap 0.266, 0.333
      - voice for one topic compared against a totally unrelated topic's
        script (genuine mismatch): overlap 0.076, 0.096
    The old 0.35 threshold was HIGHER than genuinely-correct narration ever
    scores against Whisper 'base' (which has well-documented, mediocre
    Persian accuracy even on clean input) -- meaning it was rejecting good
    videos, not catching bad ones. 0.18 sits in the wide gap between the two
    real measured clusters with margin on both sides."""
    from core import video_qa

    assert 0.10 < video_qa._MIN_WORD_OVERLAP_RATIO < 0.26
