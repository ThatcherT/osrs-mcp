#!/usr/bin/env python3
"""Scrape OSRS Reddit communities for real player questions using Playwright."""
import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright

OUTPUT = Path(__file__).parent.parent / "data" / "reddit_questions.json"

# Subreddits and search queries targeting real player questions
TARGETS = [
    # r/2007scape - main OSRS subreddit
    {"url": "https://old.reddit.com/r/2007scape/search?q=what+boss+should+I+kill&restrict_sr=on&sort=relevance&t=year", "category": "bossing"},
    {"url": "https://old.reddit.com/r/2007scape/search?q=what+gear+for&restrict_sr=on&sort=relevance&t=year", "category": "gear"},
    {"url": "https://old.reddit.com/r/2007scape/search?q=what+should+I+do+with+my+stats&restrict_sr=on&sort=relevance&t=year", "category": "progression"},
    {"url": "https://old.reddit.com/r/2007scape/search?q=how+to+make+money+osrs&restrict_sr=on&sort=relevance&t=year", "category": "money_making"},
    {"url": "https://old.reddit.com/r/2007scape/search?q=best+weapon+for&restrict_sr=on&sort=relevance&t=year", "category": "gear"},
    {"url": "https://old.reddit.com/r/2007scape/search?q=where+do+I+get&restrict_sr=on&sort=relevance&t=year", "category": "items"},
    {"url": "https://old.reddit.com/r/2007scape/search?q=quest+requirements&restrict_sr=on&sort=relevance&t=year", "category": "quests"},
    {"url": "https://old.reddit.com/r/2007scape/search?q=what+drops&restrict_sr=on&sort=relevance&t=year", "category": "drops"},
    {"url": "https://old.reddit.com/r/2007scape/search?q=DPS+calculator&restrict_sr=on&sort=relevance&t=year", "category": "dps"},
    {"url": "https://old.reddit.com/r/2007scape/search?q=slayer+task+what+to+use&restrict_sr=on&sort=relevance&t=year", "category": "slayer"},
    {"url": "https://old.reddit.com/r/2007scape/search?q=how+much+is+worth&restrict_sr=on&sort=relevance&t=year", "category": "prices"},
    {"url": "https://old.reddit.com/r/2007scape/search?q=account+progression+advice&restrict_sr=on&sort=relevance&t=year", "category": "progression"},
    # r/ironscape - ironman specific
    {"url": "https://old.reddit.com/r/ironscape/search?q=what+boss+should+I&restrict_sr=on&sort=relevance&t=year", "category": "bossing"},
    {"url": "https://old.reddit.com/r/ironscape/search?q=best+gear+for&restrict_sr=on&sort=relevance&t=year", "category": "gear"},
    {"url": "https://old.reddit.com/r/ironscape/search?q=progression+guide&restrict_sr=on&sort=relevance&t=year", "category": "progression"},
]


async def scrape_search_page(page, target: dict) -> list[dict]:
    """Scrape post titles from a Reddit search results page."""
    url = target["url"]
    category = target["category"]
    posts = []

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000)

        # old.reddit.com search results have links in .search-result-header a
        links = await page.query_selector_all(".search-result-header a")
        if not links:
            # Try alternate selector for old reddit
            links = await page.query_selector_all("a.search-title")
        if not links:
            # Broad fallback
            links = await page.query_selector_all(".search-result a.search-link, .search-result a.may-blank")

        for link in links[:15]:
            title = (await link.inner_text()).strip()
            href = await link.get_attribute("href")
            if title and len(title) > 10:
                posts.append({
                    "title": title,
                    "url": href if href and href.startswith("http") else f"https://old.reddit.com{href}" if href else "",
                    "category": category,
                    "subreddit": "ironscape" if "ironscape" in url else "2007scape",
                })
    except Exception as e:
        print(f"  Error scraping {url}: {e}")

    return posts


async def scrape_subreddit_hot(page, subreddit: str) -> list[dict]:
    """Scrape question-like posts from hot/top of a subreddit."""
    posts = []
    for sort in ["new", "top/?t=week"]:
        url = f"https://old.reddit.com/r/{subreddit}/{sort}"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)

            entries = await page.query_selector_all("#siteTable .thing .entry")
            for entry in entries[:25]:
                title_el = await entry.query_selector("a.title")
                if not title_el:
                    continue
                title = (await title_el.inner_text()).strip()
                href = await title_el.get_attribute("href")

                # Filter for question-like posts
                title_lower = title.lower()
                is_question = any(kw in title_lower for kw in [
                    "?", "what", "how", "where", "which", "should i",
                    "best", "help", "advice", "recommend", "suggest",
                    "worth", "need", "can i", "tips",
                ])
                if is_question and len(title) > 15:
                    posts.append({
                        "title": title,
                        "url": href if href and href.startswith("http") else f"https://old.reddit.com{href}" if href else "",
                        "category": "general",
                        "subreddit": subreddit,
                    })
        except Exception as e:
            print(f"  Error scraping {subreddit}/{sort}: {e}")

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

        # Scrape search results
        for i, target in enumerate(TARGETS):
            print(f"[{i+1}/{len(TARGETS)}] Scraping: {target['category']} ...")
            posts = await scrape_search_page(page, target)
            all_posts.extend(posts)
            print(f"  Found {len(posts)} posts")
            await page.wait_for_timeout(1500)  # Rate limit

        # Scrape hot/new posts from main subreddits
        for sub in ["2007scape", "ironscape"]:
            print(f"Scraping r/{sub} hot/new/top...")
            posts = await scrape_subreddit_hot(page, sub)
            all_posts.extend(posts)
            print(f"  Found {len(posts)} question posts")
            await page.wait_for_timeout(1500)

        await browser.close()

    # Deduplicate by title
    seen = set()
    unique = []
    for p in all_posts:
        key = p["title"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(p)

    # Categorize more precisely
    for p in unique:
        title_lower = p["title"].lower()
        if p["category"] == "general":
            if any(kw in title_lower for kw in ["boss", "kill count", "kc", "pvm"]):
                p["category"] = "bossing"
            elif any(kw in title_lower for kw in ["gear", "weapon", "armor", "equipment", "bis"]):
                p["category"] = "gear"
            elif any(kw in title_lower for kw in ["money", "gp", "profit", "gold"]):
                p["category"] = "money_making"
            elif any(kw in title_lower for kw in ["quest", "recipe for disaster", "rfd"]):
                p["category"] = "quests"
            elif any(kw in title_lower for kw in ["drop", "loot", "rare"]):
                p["category"] = "drops"
            elif any(kw in title_lower for kw in ["price", "worth", "ge", "buy", "sell"]):
                p["category"] = "prices"
            elif any(kw in title_lower for kw in ["slayer", "task"]):
                p["category"] = "slayer"
            elif any(kw in title_lower for kw in ["level", "train", "xp", "skill", "progress"]):
                p["category"] = "progression"
            elif any(kw in title_lower for kw in ["dps", "max hit", "accuracy"]):
                p["category"] = "dps"

    with open(OUTPUT, "w") as f:
        json.dump(unique, f, indent=2)

    print(f"\nTotal unique posts: {len(unique)}")
    # Print category breakdown
    cats = {}
    for p in unique:
        cats[p["category"]] = cats.get(p["category"], 0) + 1
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
