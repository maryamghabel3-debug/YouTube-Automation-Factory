#!/usr/bin/env python3
"""
Master Controller (The CEO)
Runs the entire factory operation. It loops through all active channels, 
finds topics, produces videos, and uploads them.
"""
import json
import os
from core.niche_analyzer import NicheAnalyzer
from core.video_factory import VideoFactory
from core.auto_publisher import AutoPublisher
from core.channel_spawner import ChannelSpawner

def load_channels():
    with open("channels/database.json", "r") as f:
        return json.load(f)["channels"]

def run_factory():
    print("==================================================")
    print("🏭 STARTING YOUTUBE AUTOMATION FACTORY (MCN) 🏭")
    print("==================================================")
    
    channels = load_channels()
    analyzer = NicheAnalyzer()
    factory = VideoFactory()
    publisher = AutoPublisher()
    
    for ch in channels:
        if not ch["active"]:
            print(f"⏸️ Skipping inactive channel: {ch['name']}")
            continue
            
        print(f"\n📺 Processing Channel: {ch['name']} (Niche: {ch['niche']})")
        print("-" * 50)
        
        # Step 1: Find Topic
        topic = analyzer.analyze_market(ch['niche'])
        
        # Step 2: Build Video
        video_path = factory.build_video(topic, ch)
        
        # Step 3: Upload and Engage
        metadata = publisher.generate_metadata(topic, ch['niche'])
        publish_url = publisher.upload_to_youtube(ch['id'], video_path, metadata)
        
        print(f"🎉 Channel {ch['name']} updated successfully!")

if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    run_factory()
