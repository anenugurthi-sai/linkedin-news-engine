import os
import requests
import feedparser
import json

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# Pivoted directly away from Salesforce to target ChatGPT, Gemini, Claude, and career productivity
FEEDS = [
    "https://news.google.com/rss/search?q=ChatGPT+OR+Gemini+OR+Claude+AI+productivity+tools+job+seekers+workplace&hl=en-IN&gl=IN&ceid=IN:en"
]

def generate_linkedin_post(title, link):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    headers = {"Content-Type": "application/json"}
    
    prompt = f"""
    Write a short, engaging, highly conversational LinkedIn post breaking down this news topic: "{title}".
    
    You are a world-class personal branding copywriter specializing in highly actionable LinkedIn content for working professionals, job seekers, and interns. Your tone is direct, high-energy, and completely professional—inspired by growth leaders like Vaibhav Sisinty.

    Strictly follow this structure:

    [THE HOOK]: A sharp 1-2 line opening addressing a workplace pain point, career growth, or interview edge. Never start with "In today's news..." or generic corporate greetings. Use 2 separate short lines.

    [THE CAREER VALUE]: Translate the raw technical update into human utility. Explain exactly how a job holder, seeker, or intern can leverage this specific tool or update to save 5 hours a week, stand out to automated systems (ATS), or impress senior leadership. Use clear, un-bulleted, short sentences.

    [3 CALLS TO ACTION/STEPS]: Use a conversational bridge like "Think about it:" followed by 3 short, practical bullet points showcasing real-world impact:
    * Bullet 1: A specific way a job seeker or worker can apply this concept tomorrow.
    * Bullet 2: A practical mindset shift for corporate efficiency.
    * Bullet 3: The exact tool or prompt layout to practice with.

    [ENGAGEMENT LESSON & QUESTION]: End with a personal reflection lesson ("I recently noticed..." or "What I am learning is...") featuring a single simple emoji at the end of the reflection line. Then close with a thought-provoking, professional question that encourages industry experts and job seekers to comment using the pointing finger emoji (👉).

    At the absolute bottom, add the source link on its own line:
    Link to source: {link}

    CRITICAL ARCHITECTURAL RULES:
    1. Never use corporate, hype-heavy AI words like: "delve", "testament", "revolutionize", "landscape", "paradigm shift", "leverage", "furthermore", "moreover", "cutting-edge", "game-changer".
    2. Keep vocabulary incredibly simple, clear, and direct. Use short, crisp sentences.
    3. Break your ideas up with plenty of line spaces so it is highly readable on mobile screens. No dense blocks of text.
    4. Absolutely eliminate all mentions of enterprise funding, stock updates, B2B corporate sales jargon, or executive quotes. Focus 100% on the individual professional's career journey.

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
    return f"Fresh update on: {title}\n\nSource: {link}"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

print("Running premium voice generation...")
for url in FEEDS:
    feed = feedparser.parse(url)
    if feed.entries:
        entry = feed.entries[0] # Focus intensely on the #1 single best article of the day
        title = entry.get("title", "")
        link = entry.get("link", "")
        clean_title = title.split(" - ")[0]

        print(f"Crafting premium narrative copy for: {clean_title}")
        custom_post_content = generate_linkedin_post(clean_title, link)

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
            print("Successfully updated Notion with an authentic premium draft!")
        else:
            print(f"Error: {response.status_code}")
        break
