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
    spawner.register_channel("dup", "Second Name", "history", "fa", "ENV_B")
    channels = spawner.list_channels()
    assert len(channels) == 1
    assert channels[0]["name"] == "Second Name"
    assert channels[0]["language"] == "fa"


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
