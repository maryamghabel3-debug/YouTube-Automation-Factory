"""
Algorithm Hacker Agent
Acts as a reverse-engineer for social media algorithms (YouTube, Instagram Reels, TikTok).
Constantly "researches" what is working right now (retention rates, hooks, pacing) 
and feeds these rules into the VideoFactory.
"""

class AlgorithmHacker:
    def __init__(self):
        self.name = "AlgorithmHacker"

    def get_latest_rules(self, platform="youtube_shorts"):
        print(f"🕵️‍♂️ [{self.name}] Decoding latest algorithm secrets for {platform}...")
        
        # In a real scenario, this agent scrapes SEO blogs, creator forums, and tracks analytics
        rules = {
            "youtube_shorts": {
                "hook_duration": "First 3 seconds must have high visual movement.",
                "pacing": "Change visual frame or B-Roll every 2.5 seconds to retain attention.",
                "loop_strategy": "The end of the video must seamlessly connect to the beginning sentence.",
                "subtitles": "Bold, dynamic word-by-word subtitles (Hormozi style) in the center of the screen."
            },
            "instagram_reels": {
                "hook_duration": "First 1 second is critical. Use text overlay before audio starts.",
                "audio": "Must use a trending audio track in the background, even at 5% volume.",
                "caption_strategy": "Short caption, highly encouraging users to check the 'Link in Bio' or 'Read Caption'.",
                "subtitles": "Aesthetic, minimal subtitles. Avoid covering the middle-right area (where UI buttons are)."
            }
        }
        
        selected_rules = rules.get(platform, rules["youtube_shorts"])
        print(f"   🔥 Algorithm Rules injected: B-Roll every {selected_rules['pacing']}, Loop strategy active.")
        return selected_rules
