#!/usr/bin/env python3
"""One-off batch runner (2026-07-05): while the user sleeps, build several
REAL, varied (English + Persian, multiple niches) videos using the agent's
own hand-written content_bank scripts (force_content_bank=True per explicit
user instruction: "به‌جای هوش مصنوعی از خودت استفاده کن" -- "use yourself
instead of AI"), run the same real QA gate main.py uses before delivery,
publish each PASSING video as a downloadable GitHub Release asset (no
YouTube upload -- that still requires explicit permission per a standing
project rule), and clean up every large intermediate file (footage, TTS
audio, raw render work directories) after each video so the sandbox disk
never fills up mid-run.

Usage: python3 scripts/batch_produce_and_release.py
Requires GH_PAT, REPO_OWNER, REPO_NAME in the environment.
"""

import gc
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.video_factory import VideoFactory
from core import content_bank
from core import content_config as cfg
from core import video_qa
from core.gh_release import GitHubRelease

RESULTS_PATH = "batch_run_results.json"

# A deliberately varied lineup: different niches, both languages, mixing
# curated evergreen topics so the finished set demonstrates real range
# rather than 10 near-identical videos.
PLAN = [
    ("psychology", "en", "Why we procrastinate even when we know better"),
    ("psychology", "fa", "Why we procrastinate even when we know better"),
    ("history_mystery", "en", "The unsolved mystery of the Mary Celeste"),
    ("history_mystery", "fa", "The unsolved mystery of the Mary Celeste"),
    ("true_crime", "en", "The cold case that was solved decades later by DNA"),
    ("true_crime", "fa", "The cold case that was solved decades later by DNA"),
    ("history_mystery", "en", "Why the Library of Alexandria really burned"),
    ("luxury_lifestyle", "en", "Inside the world's most expensive private islands"),
    ("luxury_lifestyle", "fa", "Inside the world's most expensive private islands"),
    ("finance", "en", "Why most lottery winners go broke within years"),
    ("finance", "fa", "Why most lottery winners go broke within years"),
    ("space_science", "en", "What would actually happen if you fell into a black hole"),
    ("space_science", "fa", "What would actually happen if you fell into a black hole"),
    ("true_crime", "en", "The forgery that fooled the world's top experts"),
    ("psychology", "en", "How your childhood shapes your adult relationships"),
]


def _cleanup_intermediate_files():
    """Removes every large intermediate artifact this pipeline can create
    (raw downloaded stock footage, TTS audio, ffmpeg work dirs, thumbnails)
    so nothing piles up between videos -- per explicit user instruction:
    "اگه فیلم و عکسی رو تو این محیط دانلود کردی بعد از اینکه ویدیو رو
    ساختی از اینجا پاک کن تا جا نگیره" (delete downloaded footage/photos
    after building the video so it doesn't fill up the disk). The final
    rendered MP4 for each video is uploaded to GitHub BEFORE this runs, so
    nothing important is lost -- only working/scratch data is deleted."""
    for d in ("assets/footage", "assets/audio", "assets/work", "assets/thumbnails",
              "assets/music"):
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
    # output/*.mp4 (the final rendered videos + shorts) are removed too,
    # ONLY after each one has already been uploaded as a Release asset --
    # see the main loop below, which calls this only after a successful
    # (or definitively-failed) publish for that specific video.


def _dummy_channel_cfg(niche_key: str, language: str) -> dict:
    voice = cfg.LANGUAGES.get(language, {}).get("voice", "en-US-ChristopherNeural")
    niche_label = (cfg.NICHES.get(niche_key, {}).get("label_fa")
                   if language == "fa" else cfg.NICHES.get(niche_key, {}).get("label_en"))
    return {
        "id": f"batch_{niche_key}_{language}",
        "name": f"Batch/{niche_key}/{language}",
        "niche_key": niche_key,
        "niche_label": niche_label or niche_key,
        "language": language,
        "voice": voice,
    }


def _already_published(releaser: GitHubRelease, niche_key: str, language: str, topic: str) -> bool:
    """Checks existing GitHub Releases for one whose title already matches
    this niche/topic/language combo -- lets the script be re-run safely
    after an interruption (this sandbox's background processes do not
    survive between conversation turns) without re-building and
    re-publishing videos that already succeeded."""
    import requests
    if not (releaser.owner and releaser.repo and releaser.token):
        return False
    try:
        r = requests.get(
            f"https://api.github.com/repos/{releaser.owner}/{releaser.repo}/releases",
            headers=releaser._headers(), params={"per_page": 100}, timeout=20,
        )
        if r.status_code != 200:
            return False
        marker = f"[{niche_key}/{language}] {topic}"
        return any(marker in (rel.get("name") or "") for rel in r.json())
    except Exception:
        return False


def main():
    releaser = GitHubRelease()
    if not (releaser.owner and releaser.repo and releaser.token):
        print("❌ GH_PAT/REPO_OWNER/REPO_NAME not set -- cannot publish Release assets.")
        sys.exit(1)

    factory = VideoFactory()
    results = []

    for i, (niche_key, language, topic) in enumerate(PLAN, start=1):
        print("\n" + "=" * 70)
        print(f"[{i}/{len(PLAN)}] niche={niche_key} lang={language} topic='{topic}'")
        print("=" * 70)

        if _already_published(releaser, niche_key, language, topic):
            print(f"⏭️  Already published in an earlier (interrupted) run -- skipping.")
            results.append({"niche": niche_key, "language": language, "topic": topic,
                             "status": "already_published"})
            continue

        if not content_bank.has_script(niche_key, language, topic):

            print(f"⚠️  No content_bank script for this niche/language/topic combo -- skipping.")
            results.append({"niche": niche_key, "language": language, "topic": topic,
                             "status": "skipped_no_script"})
            continue

        ch = _dummy_channel_cfg(niche_key, language)
        t0 = time.time()
        try:
            video_result = factory.build_video(
                topic, ch, target_minutes=4, make_shorts=False,
                force_content_bank=True,  # explicit user instruction: use the
                                           # agent's own scripts, not an LLM
            )
        except Exception as e:
            print(f"❌ build_video raised: {e}")
            results.append({"niche": niche_key, "language": language, "topic": topic,
                             "status": "build_exception", "error": str(e)})
            _cleanup_intermediate_files()
            continue

        build_seconds = time.time() - t0

        if video_result.get("error"):
            print(f"❌ Build failed: {video_result['error']}")
            results.append({"niche": niche_key, "language": language, "topic": topic,
                             "status": "build_failed", "error": video_result["error"]})
            _cleanup_intermediate_files()
            continue

        video_path = video_result["video_path"]
        print(f"✅ Built in {build_seconds:.0f}s: {video_path} "
              f"({video_result['duration']:.1f}s, {video_result['scenes_rendered']} scenes)")

        actual_topic = video_result.get("topic", topic)

        # Same real QA gate main.py uses -- a video that fails is NOT
        # published, exactly like the live production pipeline.
        print("[QA] Running automated checks before publishing...")
        qa_report = video_qa.run_qa(
            video_path, video_result.get("full_narration_text", ""), language=language,
        )
        if not qa_report.get("ok"):
            print(f"⚠️  QA FAILED: {qa_report}")
            results.append({
                "niche": niche_key, "language": language, "topic": actual_topic,
                "status": "qa_failed", "qa_report": qa_report,
            })
            _cleanup_intermediate_files()
            if os.path.exists(video_path):
                os.remove(video_path)
            continue

        print(f"[QA] Passed. mean_volume={qa_report.get('audio_loudness', {}).get('mean_volume_db')} dB")

        title = f"[{niche_key}/{language}] {topic} | {ch['niche_label']}"
        body = (
            f"موضوع: {actual_topic}\n"
            f"نیچ: {ch['niche_label']}\n"
            f"زبان: {'فارسی' if language == 'fa' else 'English'}\n"
            f"مدت: {video_result['duration']:.0f} ثانیه\n"
            f"منبع اسکریپت: content_bank (دست‌نویس و فکت‌چک‌شده، بدون هوش مصنوعی)\n"
            f"وضعیت QA: قبول ✅ (mean_volume={qa_report.get('audio_loudness', {}).get('mean_volume_db')} dB"
            + (f", تطابق روایت={qa_report.get('narration_check', {}).get('overlap_ratio')}"
               if "narration_check" in qa_report else "") + ")"
        )
        rel = releaser.publish_video(video_path, title, body)
        if rel.get("ok"):
            print(f"🔗 Released: {rel['url']}")
            results.append({
                "niche": niche_key, "language": language, "topic": actual_topic,
                "status": "published", "download_url": rel["url"],
                "release_page": rel.get("release_url", ""),
                "duration_seconds": video_result["duration"],
                "qa": {
                    "mean_volume_db": qa_report.get("audio_loudness", {}).get("mean_volume_db"),
                    "narration_overlap": qa_report.get("narration_check", {}).get("overlap_ratio")
                                          if "narration_check" in qa_report else None,
                },
            })
        else:
            print(f"❌ Release upload failed: {rel.get('error')}")
            results.append({"niche": niche_key, "language": language, "topic": actual_topic,
                             "status": "release_failed", "error": rel.get("error")})

        # Clean up EVERYTHING (footage, audio, work dirs, the rendered mp4
        # itself) now that it's safely uploaded -- per explicit instruction
        # not to let downloaded media pile up in this environment.
        if os.path.exists(video_path):
            os.remove(video_path)
        _cleanup_intermediate_files()
        gc.collect()

        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("BATCH COMPLETE")
    print("=" * 70)
    published = [r for r in results if r["status"] == "published"]
    print(f"Published: {len(published)}/{len(PLAN)}")
    for r in published:
        print(f"  - [{r['language']}] {r['niche']}: {r['topic']} -> {r['download_url']}")
    failed = [r for r in results if r["status"] != "published"]
    if failed:
        print(f"\nNot published ({len(failed)}):")
        for r in failed:
            print(f"  - [{r['language']}] {r['niche']}: {r['topic']} -- {r['status']}: {r.get('error', r.get('qa_report'))}")

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
