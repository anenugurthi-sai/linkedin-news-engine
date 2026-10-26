import os
import re
import requests
import feedparser
from html.parser import HTMLParser

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
POST_TARGET_MIN_WORDS = 100
POST_TARGET_MAX_WORDS = 150
POST_HARD_MAX_WORDS = 160
REQUEST_TIMEOUT = 45

FEEDS = [
    "https://news.google.com/rss/search?q=Claude+AI+OR+Anthropic+productivity+workplace&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=ChatGPT+OR+OpenAI+automation+features&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=Perplexity+AI+research+search+engine&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=Notion+AI+productivity+workspace&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=AI+agents+OR+autonomous+workflows+OR+CrewAI+productivity&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=browser+use+AI+OR+desktop+automation+OR+computer+use+Anthropic&hl=en-IN&gl=IN&ceid=IN:en",
    "https://www.reddit.com/r/ArtificialIntelligence/search.rss?q=productivity+OR+workflow+OR+automate+AND+Claude+OR+ChatGPT&sort=top&t=week",
    "https://www.reddit.com/r/Automate/search.rss?q=agents+OR+autonomous+OR+crewai&sort=top&t=week",
]

BLOCKLIST_KEYWORDS = [
    r"salesforce", r"agentforce", r"\bcrm\b", r"\bb2b\b",
    r"enterprise funding", r"seed round", r"raised \$", r"valuation",
    r"stock price", r"shares tumble", r"ceo drama", r"boardroom",
    r"acquisition", r"resume", r"\bats\b", r"job hunt", r"job seeker",
    r"portfolio", r"how to write an email", r"basic prompt", r"\bsora\b",
    r"\brunway\b", r"\bkling\b", r"\bpika\b", r"video generation",
    r"video model", r"text-to-video", r"\bluma\b",
]


def contains_blocked_content(text):
    """Return True when a headline matches an excluded topic."""
    for pattern in BLOCKLIST_KEYWORDS:
        if re.search(pattern, text.lower()):
            print(f"Auto-rejected by topic filter: {pattern}")
            return True
    return False


def count_words(text):
    """Count words consistently for the post-length guard."""
    return len(re.findall(r"\b[\w]+(?:['’.-][\w]+)*\b", text))


def call_gemini(prompt):
    """Call Gemini with a timeout; return text or an empty string on failure."""
    if not GEMINI_KEY:
        print("GEMINI_API_KEY is not configured.")
        return ""
    try:
        response = requests.post(
            GEMINI_URL,
            params={"key": GEMINI_KEY},
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            print(f"Gemini API error: HTTP {response.status_code}")
            return ""
        try:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError, ValueError):
            print("Gemini response did not contain generated text.")
            return ""
    except requests.RequestException as exc:
        print(f"Gemini request failed: {exc}")
        return ""


class ArticleTextExtractor(HTMLParser):
    """Extract title, description, and paragraph text from a linked article."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.in_paragraph = False
        self.title_parts = []
        self.paragraphs = []
        self.meta_description = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "p":
            self.in_paragraph = True
        elif tag == "meta" and attrs.get("name", "").lower() in ("description", "og:description"):
            self.meta_description = attrs.get("content", "")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "p":
            self.in_paragraph = False

    def handle_data(self, data):
        text = " ".join(data.split())
        if not text:
            return
        if self.in_title:
            self.title_parts.append(text)
        if self.in_paragraph and len(text) > 35:
            self.paragraphs.append(text)


def fetch_source_context(link, snippet=""):
    """Try to enrich the RSS summary with the linked article's title and paragraph text."""
    if not link:
        return snippet
    try:
        response = requests.get(
            link,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AINewsLinkedInEngine/2.1)"},
            timeout=15,
        )
        if response.status_code != 200 or "html" not in response.headers.get("Content-Type", "").lower():
            return snippet
        parser = ArticleTextExtractor()
        parser.feed(response.text[:1_500_000])
        parts = []
        if parser.title_parts:
            parts.append("Page title: " + " ".join(parser.title_parts))
        if parser.meta_description:
            parts.append("Page description: " + parser.meta_description)
        # Limit article text to avoid sending navigation/footer content or excessive tokens.
        parts.extend(parser.paragraphs[:12])
        extracted = "\n".join(parts)[:9000]
        return "\n\n".join(part for part in (snippet, extracted) if part)
    except (requests.RequestException, ValueError) as exc:
        print(f"Could not fetch source article; using RSS summary only: {exc}")
        return snippet


GENERIC_PHRASES = (
    "the evolving landscape", "valuable insights", "important shifts",
    "monitoring these internal changes", "the industry's direction",
    "keeping an eye on", "in today's fast-paced world", "this is a game changer",
    "deeper expertise", "strategic thinking", "complex problem-solving",
    "nuanced judgment", "paramount", "evolving workforce needs",
    "complement ai", "competing directly with ai", "reshaping workforce needs",
    "offers a glimpse into", "the practical takeaway is to focus on developing",
)

CORPORATE_PHRASES = (
    "leverage", "synergy", "paradigm", "robust", "transformative",
    "landscape", "navigate", "unlock", "seamlessly", "optimize",
    "strategic imperative", "value proposition", "at scale",
)


def has_complex_or_corporate_language(post):
    """Catch common corporate language that does not fit the user's plain-English style."""
    lowered = post.lower()
    return any(phrase in lowered for phrase in CORPORATE_PHRASES)


def has_generic_filler(post):
    """Flag common vague phrases that add little specific information."""
    lowered = post.lower()
    return any(phrase in lowered for phrase in GENERIC_PHRASES)


def build_post_prompt(title, link, snippet):
    return f"""
Write one short, specific LinkedIn post about AI or technology. Write in the user's style: basic, natural English, direct and practical, like a working professional explaining something clearly to a colleague.

SOURCE HEADLINE:
{title}

SOURCE URL:
{link}

SOURCE MATERIAL (RSS summary and any article text retrieved):
{snippet}

EDITORIAL REQUIREMENTS:
- Prefer 60-110 words. A post can be shorter when the story is simple. Never exceed {POST_HARD_MAX_WORDS} words. Do not add words just to reach a target.
- Start with the actual reported event in the first sentence. Name the company, product, or change and include a concrete detail from the source.
- Explain only what the source confirms. Do not turn a reported change into a claim about why it happened unless the source explicitly says why.
- If the source does not provide a clear event and at least one concrete detail, return exactly SKIP: INSUFFICIENT SOURCE DETAIL.
- Add one short "why it matters" point only when it follows directly from the facts. Clearly separate fact from possible implication.
- Do not force a lesson, career advice, prediction, or practical takeaway. If there is no useful takeaway supported by the story, leave it out.
- Write like the user: basic everyday English, direct and natural, short sentences, short paragraphs. Use words people commonly use in normal conversation.
- Avoid corporate jargon, complex vocabulary, grand claims, formal report language, and phrases that sound like a company announcement.
- Do not use words or phrases such as "paramount", "nuanced judgment", "strategic thinking", "evolving landscape", "valuable insights", "leverage", "synergy", "transformative", or "offers a glimpse into".
- Do not invent numbers, dates, motives, workforce changes, features, settings, outcomes, quotes, or steps.
- Do not claim personal experience or write "I" as if the user personally did something.
- No forced bullets, emojis, hashtags, or closing questions.
- Return only the post text. No title, labels, analysis, word count, or code fence.
""".strip()


def verify_post_against_source(post, title, link, source_context):
    """Use a separate model pass to reject claims that the supplied source does not support."""
    verification_prompt = f"""
You are a strict fact checker for a LinkedIn post. Compare the draft only with the source material below.
Do not use outside knowledge or guess what probably happened.

SOURCE HEADLINE:
{title}

SOURCE URL:
{link}

SOURCE MATERIAL:
{source_context}

DRAFT TO CHECK:
{post}

Return PASS only if all these conditions are met:
- Every factual claim is directly supported by the source material.
- Any claim explaining why something happened is explicitly stated by the source, not guessed from timing or context.
- Any prediction or interpretation is clearly marked as a possibility and follows reasonably from the source.
- The draft does not add general career advice just to fill space.
- The draft is written in basic everyday English and does not use corporate jargon.

If any condition fails, or if the source material is too thin to check the claims, return exactly SKIP.
Return only PASS or SKIP.
""".strip()
    result = call_gemini(verification_prompt).strip().upper()
    if result == "PASS":
        print("Source verification passed.")
        return True
    print("Skipping draft: source verification failed or evidence was insufficient.")
    return False


def generate_linkedin_post(title, link, snippet=""):
    """Generate, quality-check, and independently verify a post before publishing."""
    source_context = fetch_source_context(link, snippet)
    prompt = build_post_prompt(title, link, source_context)
    post = call_gemini(prompt)
    if not post:
        return None
    if post.strip().upper().startswith("SKIP: INSUFFICIENT SOURCE DETAIL"):
        print("Skipping candidate: source did not support a specific, useful post.")
        return None

    words = count_words(post)
    needs_revision = (
        words > POST_HARD_MAX_WORDS
        or has_generic_filler(post)
        or has_complex_or_corporate_language(post)
    )
    if needs_revision:
        reasons = []
        if words > POST_HARD_MAX_WORDS:
            reasons.append(f"over the {POST_HARD_MAX_WORDS}-word limit ({words} words)")
        if has_generic_filler(post):
            reasons.append("contains generic filler")
        if has_complex_or_corporate_language(post):
            reasons.append("uses corporate or complex language")
        print("Requesting one revision: " + "; ".join(reasons))
        retry_prompt = (
            prompt
            + f"\n\nREVISION REQUIRED: The previous draft {', '.join(reasons)}. "
            + f"Rewrite in no more than {POST_TARGET_MAX_WORDS} words. Name the concrete source fact, "
            + "use basic everyday English, remove corporate language, vague claims and unsupported inference. "
            + "Do not add a takeaway unless the facts support it. If source evidence is insufficient, "
            + "return exactly SKIP: INSUFFICIENT SOURCE DETAIL. Return only the revised post."
        )
        post = call_gemini(retry_prompt)
        if not post or post.strip().upper().startswith("SKIP: INSUFFICIENT SOURCE DETAIL"):
            return None
        words = count_words(post)

    if words > POST_HARD_MAX_WORDS or has_generic_filler(post) or has_complex_or_corporate_language(post):
        print(
            "Skipping draft: failed quality checks "
            f"(words={words}, generic_filler={has_generic_filler(post)}, "
            f"corporate_language={has_complex_or_corporate_language(post)})."
        )
        return None

    print(f"Draft passed style and length checks: {words} words.")
    if not verify_post_against_source(post, title, link, source_context):
        return None
    return post


def create_notion_page(title, post):
    if not NOTION_TOKEN or not DATABASE_ID:
        print("NOTION_TOKEN or NOTION_DATABASE_ID is not configured.")
        return False
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    payload = {
        "parent": {"database_id": DATABASE_ID},
        "properties": {"Name": {"title": [{"text": {"content": title[:2000]}}]}},
        "children": [{
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": post[:2000]}}]},
        }],
    }
    try:
        response = requests.post(
            "https://api.notion.com/v1/pages",
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code in (200, 201):
            print("Successfully created a LinkedIn draft in Notion.")
            return True
        print(f"Notion API error: HTTP {response.status_code} - {response.text[:300]}")
    except requests.RequestException as exc:
        print(f"Notion request failed: {exc}")
    return False


def main():
    print("Running LinkedIn AI News Engine with concise-post validation.")
    if not NOTION_TOKEN or not DATABASE_ID or not GEMINI_KEY:
        print("One or more required secrets are missing; stopping before feed processing.")
        return

    for feed_url in FEEDS:
        print(f"Scanning source stream: {feed_url}")
        try:
            if "reddit.com" in feed_url:
                feed = feedparser.parse(feed_url, agent="Mozilla/5.0 AI-News-Engine/2.0")
            else:
                feed = feedparser.parse(feed_url)
        except Exception as exc:
            print(f"Feed parsing failed: {exc}")
            continue

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            snippet = entry.get("summary", "") or entry.get("description", "")
            clean_title = title.split(" - ")[0].strip()
            if not clean_title or contains_blocked_content(clean_title):
                continue

            print(f"Candidate headline: {clean_title}")
            post = generate_linkedin_post(clean_title, link, snippet)
            if not post:
                print("Skipping candidate because no acceptable draft was generated.")
                continue
            if create_notion_page(clean_title, post):
                return  # Preserve existing behavior: at most one draft per run.

    print("Run complete: no candidate produced an acceptable Notion draft.")


if __name__ == "__main__":
    main()
