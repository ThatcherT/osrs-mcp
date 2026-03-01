#!/usr/bin/env python3
"""Scrape OSRS Reddit for genuine player questions, filtering out memes/discussion."""
import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright

OUTPUT = Path(__file__).parent.parent / "data" / "reddit_questions_filtered.json"

# More targeted searches for actual help-seeking posts
SEARCHES = [
    # Account progression
    ("2007scape", "flair:question what boss stats", "bossing"),
    ("2007scape", "flair:question gear recommendation", "gear"),
    ("2007scape", "flair:question money making method", "money_making"),
    ("2007scape", "what should I kill with these stats", "bossing"),
    ("2007scape", "what boss can I do with my stats", "bossing"),
    ("2007scape", "best melee weapon for", "gear"),
    ("2007scape", "best ranged weapon for", "gear"),
    ("2007scape", "best in slot for", "gear"),
    ("2007scape", "what drops maple seed", "drops"),
    ("2007scape", "where do I get item drop", "drops"),
    ("2007scape", "is it worth buying", "prices"),
    ("2007scape", "how much gp per hour", "money_making"),
    ("2007scape", "quest order guide what quest", "quests"),
    ("2007scape", "slayer task best gear setup", "slayer"),
    ("2007scape", "DPS comparison weapon", "dps"),
    ("2007scape", "what to upgrade next gear", "gear"),
    ("2007scape", "mid game account progression", "progression"),
    ("2007scape", "late game money making boss", "money_making"),
    ("2007scape", "dragon hunter lance vs crossbow", "dps"),
    ("2007scape", "vorkath setup guide gear", "bossing"),
    ("2007scape", "zulrah gear requirements stats", "bossing"),
    # Ironscape
    ("ironscape", "what boss should I do next", "bossing"),
    ("ironscape", "gear progression mid game", "gear"),
    ("ironscape", "money making ironman", "money_making"),
    ("ironscape", "what to do with these stats", "progression"),
]


def is_genuine_question(title: str) -> bool:
    """Filter for genuine player questions vs memes/discussion."""
    lower = title.lower()
    # Must contain question indicators
    question_markers = [
        "?", "what ", "how ", "where ", "which ", "should i",
        "best ", "help", "advice", "recommend", "suggest",
        "worth", "can i", "is it", "tips for", "guide",
        "need help", "looking for", "trying to", "setup for",
    ]
    has_question = any(m in lower for m in question_markers)
    if not has_question:
        return False

    # Filter out meme/rant/meta posts
    noise_markers = [
        "jagex", "vote", "poll", "nerf", "buff", "meme", "lol",
        "pvp", "pker", "bot", "rwt", "mtx", "change my mind",
        "unpopular opinion", "hot take", "petition", "rant",
        "toxic", "community", "suggestion/discussion", "blog",
        "dead man", "dmm", "sailing", "mod ash", "conspiracy",
        "mental health", "anxiety", "insurance", "liberty mutual",
        "parenting", "dream about",
    ]
    has_noise = any(m in lower for m in noise_markers)
    if has_noise:
        return False

    # Must be long enough to be a real question
    return len(title) > 20


async def scrape_search(page, subreddit: str, query: str, category: str) -> list[dict]:
    """Scrape a single search query."""
    url = f"https://old.reddit.com/r/{subreddit}/search?q={query.replace(' ', '+')}&restrict_sr=on&sort=relevance&t=all"
    posts = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(1500)

        links = await page.query_selector_all(".search-result-header a")
        if not links:
            links = await page.query_selector_all("a.search-title, a.may-blank")

        for link in links[:20]:
            title = (await link.inner_text()).strip()
            href = await link.get_attribute("href")
            if is_genuine_question(title):
                posts.append({
                    "title": title,
                    "url": href if href and href.startswith("http") else f"https://old.reddit.com{href}" if href else "",
                    "category": category,
                    "subreddit": subreddit,
                })
    except Exception as e:
        print(f"  Error: {e}")
    return posts


async def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    all_posts = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        for i, (sub, query, cat) in enumerate(SEARCHES):
            print(f"[{i+1}/{len(SEARCHES)}] r/{sub}: {query} ({cat})")
            posts = await scrape_search(page, sub, query, cat)
            all_posts.extend(posts)
            print(f"  -> {len(posts)} questions")
            await page.wait_for_timeout(1500)

        await browser.close()

    # Deduplicate
    seen = set()
    unique = []
    for p in all_posts:
        key = p["title"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(p)

    with open(OUTPUT, "w") as f:
        json.dump(unique, f, indent=2)

    print(f"\nTotal unique questions: {len(unique)}")
    cats = {}
    for p in unique:
        cats[p["category"]] = cats.get(p["category"], 0) + 1
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
