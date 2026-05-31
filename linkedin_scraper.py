import os
import requests
import feedparser
import json
import re

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# 1. SPECIALIZED HIGH-SIGNAL SOURCES (No generic news aggregators)
# 1. SPECIALIZED HIGH-SIGNAL SOURCES (Targeting your elite power stack directly)
FEEDS = [
    "https://news.google.com/rss/search?q=Claude+AI+OR+Anthropic+productivity+workplace&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=ChatGPT+OR+OpenAI+automation+features&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=Perplexity+AI+research+search+engine&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=Notion+AI+productivity+workspace&hl=en-IN&gl=IN&ceid=IN:en"
]

# 2. THE STRICT LINKEDIN BRAND CRINGE BLOCKLIST
BLOCKLIST_KEYWORDS = [
    r"salesforce", r"agentforce", r"crm", r"b2b", r"enterprise funding", r"seed round", r"raised \$", 
    r"valuation", r"stock price", r"shares tumble", r"ceo drama", r"boardroom", r"acquisition",
    r"resume", r"ats", r"job hunt", r"job seeker", r"portfolio", r"how to write an email", r"basic prompt",
    r"sora", r"runway", r"kling", r"pika", r"video generation", r"video model", r"text-to-video", r"luma"
]

def contains_blocked_content(text):
    """Checks if a headline or summary contains elements from the strict blocklist."""
    text_lower = text.lower()
    for pattern in BLOCKLIST_KEYWORDS:
        if re.search(pattern, text_lower):
            print(f"🚫 Auto-Rejected based on blocklist match: '{pattern}'")
            return True
    return False

def generate_linkedin_post(title, link, snippet=""):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    headers = {"Content-Type": "application/json"}
    
    prompt = f"""
    Write a short, engaging, highly conversational LinkedIn post breaking down this cutting-edge AI capability/drop: "{title}".
    Additional context: {snippet}
    
    You are a world-class personal branding copywriter specializing in highly actionable LinkedIn content for working professionals, job holders, and corporate generalists. Your tone is direct, high-energy, and completely professional—inspired by growth leaders like Vaibhav Sisinty.

    You are writing exclusively for an advanced audience that already uses AI daily. Focus on advanced workflows, tactical implementation, and structural shifts.

    PRIORITIZE AND EXALT updates regarding these core tools if present in the text: Claude, ChatGPT, Gemini, Perplexity, Automated Agents, or Notion AI.

    Strictly follow this structure:

    [THE HOOK]: A sharp 1-2 line opening addressing a workplace hyper-efficiency shift, complex reasoning breakthrough, or professional execution edge. Never start with "In today's news..." or generic greetings. Use 2 separate short lines.

    [THE TACTICAL VALUE]: Translate the raw update into immediate workplace utility. Explain exactly how an operations manager, executive, or professional can use this specific advancement to automate multi-step tasks, execute strategic research, or bypass hours of administrative overhead. Use clear, un-bulleted, short sentences.

    [3 CALLS TO ACTION/STEPS]: Use a conversational bridge like "Think about it:" followed by 3 short, practical bullet points showcasing real-world workflow integration:
    * Bullet 1: An immediate setting, feature toggle, or deployment strategy a professional can try tomorrow.
    * Bullet 2: A practical framework adjustment for orchestrating tasks rather than just typing prompts.
    * Bullet 3: The exact tool configuration or agent parameter to practice with.

    [ENGAGEMENT LESSON & QUESTION]: End with a personal reflection lesson ("I recently noticed..." or "What I am learning is...") featuring a single simple emoji at the end of the reflection line. Then close with a thought-provoking, high-level professional question that encourages industry experts to comment using the pointing finger emoji (👉).

    At the absolute bottom, add the source link on its own line:
    Link to source: {link}

    CRITICAL ARCHITECTURAL RULES:
    1. ZERO TOLERANCE FOR ENTRY-LEVEL CONTENT. Never explain "how to draft an email", "how to summarize text", or basic chat commands. Assume the reader is already an advanced user.
    2. Never use corporate, hype-heavy AI words like: "delve", "testament", "revolutionize", "landscape", "paradigm shift", "leverage", "furthermore", "moreover", "cutting-edge", "game-changer".
    3. Keep vocabulary incredibly simple, clear, and direct. Use short, crisp sentences.
    4. Break your ideas up with plenty of line spaces so it is highly readable on mobile screens. No dense blocks of text.
    5. Absolutely eliminate all mentions of enterprise sales pitches, corporate funding, stocks, B2B software vendor jargon, or executive quotes. Focus 100% on execution utility.

    Generate ONLY the final post text. Do not include introductory notes, markdown backticks, or labels.
    """
    
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"AI generation failed: {e}")
    return None

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

print("Running Premium Career-AI Filter Engine...")
processed_an_article = False

for feed_url in FEEDS:
    print(f"Scanning source stream: {feed_url}")
    feed = feedparser.parse(feed_url)
    
    if not feed.entries:
        continue
        
    for entry in feed.entries:
        title = entry.get("title", "")
        link = entry.get("link", "")
        summary = entry.get("summary", "") or entry.get("description", "")
        clean_title = title.split(" - ")[0].strip()

        # Run our strict pre-flight filtration engine
        if contains_blocked_content(clean_title):
            continue

        print(f"🔥 High-signal match confirmed: {clean_title}")
        print("Crafting advanced workflow narrative copy...")
        
        custom_post_content = generate_linkedin_post(clean_title, link, summary)
        
        if not custom_post_content:
            print("Skipping due to generation empty state.")
            continue

        payload = {
            "parent": { "database_id": DATABASE_ID },
            "properties": {
                "Name": { "title": [ { "text": { "content": clean_title } } ] }
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            { "type": "text", "text": { "content": custom_post_content } }
                        ]
                    }
                }
            ]
        }

        response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload)
        if response.status_code == 200:
            print("Successfully injected a top-tier premium draft into Notion!")
            processed_an_article = True
            break
        else:
            print(f"Notion integration error: {response.status_code}")
            
    if processed_an_article:
        break

if not processed_an_article:
    print("Execution complete. Stream analyzed, but no articles cleared the premium quality thresholds today.")
