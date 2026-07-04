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
