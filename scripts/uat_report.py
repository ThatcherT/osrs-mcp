#!/usr/bin/env python3
"""Generate UAT coverage report from Reddit questions and test results.

Usage:
    # Run UATs and generate report
    uv run python scripts/uat_report.py

    # Just show report from last run (if results exist)
    uv run python scripts/uat_report.py --report-only
"""
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
QUESTIONS_FILE = PROJECT_ROOT / "data" / "reddit_questions_filtered.json"
RESULTS_FILE = PROJECT_ROOT / "data" / "uat_results.json"

# Map Reddit question categories to the UAT test classes and tools exercised
CATEGORY_MAP = {
    "bossing": {
        "test_class": "TestUATBossing",
        "tools": ["monster_info", "boss_requirements", "player_stats", "calc_dps", "monster_drops"],
        "description": "Boss recommendations based on player stats",
    },
    "gear": {
        "test_class": "TestUATGear",
        "tools": ["item_info", "search_items", "item_price", "compare_weapons"],
        "description": "Gear upgrade and equipment recommendations",
    },
    "dps": {
        "test_class": "TestUATDps",
        "tools": ["calc_dps", "compare_weapons"],
        "description": "DPS calculations and weapon comparisons",
    },
    "drops": {
        "test_class": "TestUATDrops",
        "tools": ["drop_sources", "monster_drops"],
        "description": "Item drop sources and monster loot tables",
    },
    "money_making": {
        "test_class": "TestUATMoneyMaking",
        "tools": ["money_making_methods", "item_price"],
        "description": "Money making method suggestions",
    },
    "prices": {
        "test_class": "TestUATPrices",
        "tools": ["item_price", "search_items"],
        "description": "GE price lookups and value checks",
    },
    "progression": {
        "test_class": "TestUATProgression",
        "tools": ["player_stats", "player_gains", "item_price"],
        "description": "Account progression advice",
    },
    "quests": {
        "test_class": "TestUATQuests",
        "tools": ["quest_info", "search_wiki"],
        "description": "Quest information and ordering",
    },
    "slayer": {
        "test_class": "TestUATSlayer",
        "tools": ["monster_info", "search_monsters", "calc_dps"],
        "description": "Slayer task gear and setup advice",
    },
}


def run_uats() -> dict:
    """Run UAT tests and parse results."""
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_uat_reddit.py",
        "--tb=short", "-v", "--no-header",
        f"--junitxml={RESULTS_FILE.with_suffix('.xml')}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    stdout = result.stdout

    # Parse test results from verbose output
    results = {"passed": [], "failed": [], "errors": [], "skipped": []}
    for line in stdout.splitlines():
        if " PASSED" in line:
            results["passed"].append(line.split(" PASSED")[0].strip())
        elif " FAILED" in line:
            results["failed"].append(line.split(" FAILED")[0].strip())
        elif " ERROR" in line:
            results["errors"].append(line.split(" ERROR")[0].strip())
        elif " SKIPPED" in line:
            results["skipped"].append(line.split(" SKIPPED")[0].strip())

    results["raw_stdout"] = stdout
    results["raw_stderr"] = result.stderr
    results["returncode"] = result.returncode
    return results


def load_questions() -> dict:
    """Load Reddit questions and count by category."""
    if not QUESTIONS_FILE.exists():
        return {}
    with open(QUESTIONS_FILE) as f:
        questions = json.load(f)
    cats = {}
    for q in questions:
        cat = q["category"]
        cats[cat] = cats.get(cat, 0) + 1
    return cats


def classify_test(test_name: str) -> str | None:
    """Map a test function name to its category."""
    for cat, info in CATEGORY_MAP.items():
        if info["test_class"] in test_name:
            return cat
    if "TestUATMultiToolWorkflows" in test_name:
        return "workflow"
    if "TestUATWikiSearch" in test_name:
        return "wiki_search"
    return None


def generate_report(test_results: dict, question_counts: dict) -> str:
    """Generate the tracking report."""
    lines = []
    lines.append("=" * 70)
    lines.append("  OSRS MCP - User Acceptance Test Report")
    lines.append("  Based on 241 real Reddit player questions")
    lines.append("=" * 70)

    total_passed = len(test_results["passed"])
    total_failed = len(test_results["failed"])
    total_errors = len(test_results["errors"])
    total_skipped = len(test_results["skipped"])
    total = total_passed + total_failed + total_errors

    lines.append(f"\n  Overall: {total_passed}/{total} passed"
                 f" ({total_passed/total*100:.0f}%)" if total > 0 else "\n  No tests found")
    if total_failed:
        lines.append(f"  Failed: {total_failed}")
    if total_errors:
        lines.append(f"  Errors: {total_errors}")
    if total_skipped:
        lines.append(f"  Skipped: {total_skipped}")

    lines.append(f"\n{'Category':<16} {'Questions':>9} {'Tests':>7} {'Pass':>6} {'Fail':>6} {'Status'}")
    lines.append("-" * 70)

    # Classify results by category
    cat_results = {}
    for test_name in test_results["passed"]:
        cat = classify_test(test_name)
        if cat not in cat_results:
            cat_results[cat] = {"passed": 0, "failed": 0}
        cat_results[cat]["passed"] += 1
    for test_name in test_results["failed"] + test_results["errors"]:
        cat = classify_test(test_name)
        if cat not in cat_results:
            cat_results[cat] = {"passed": 0, "failed": 0}
        cat_results[cat]["failed"] += 1

    all_cats = sorted(set(list(CATEGORY_MAP.keys()) + list(cat_results.keys())))
    for cat in all_cats:
        if cat is None:
            continue
        q_count = question_counts.get(cat, 0)
        cr = cat_results.get(cat, {"passed": 0, "failed": 0})
        test_count = cr["passed"] + cr["failed"]
        status = "PASS" if cr["failed"] == 0 and cr["passed"] > 0 else "FAIL" if cr["failed"] > 0 else "N/A"
        icon = "[+]" if status == "PASS" else "[X]" if status == "FAIL" else "[ ]"
        lines.append(f"  {icon} {cat:<13} {q_count:>6}     {test_count:>5}  {cr['passed']:>5}  {cr['failed']:>5}")

    lines.append("-" * 70)

    # Tool coverage
    lines.append("\n  Tool Coverage:")
    all_tools_tested = set()
    for cat, info in CATEGORY_MAP.items():
        cr = cat_results.get(cat, {"passed": 0, "failed": 0})
        if cr["passed"] > 0:
            all_tools_tested.update(info["tools"])

    all_tools = {
        "player_stats", "player_gains",
        "item_info", "search_items", "item_price",
        "monster_info", "monster_drops", "drop_sources", "search_monsters",
        "calc_dps", "compare_weapons",
        "quest_info", "search_wiki", "money_making_methods", "boss_requirements",
    }
    for tool in sorted(all_tools):
        icon = "[+]" if tool in all_tools_tested else "[ ]"
        lines.append(f"    {icon} {tool}")

    lines.append(f"\n  Tools covered: {len(all_tools_tested)}/{len(all_tools)}"
                 f" ({len(all_tools_tested)/len(all_tools)*100:.0f}%)")

    # Show failures
    if test_results["failed"] or test_results["errors"]:
        lines.append("\n  Failures:")
        for name in test_results["failed"]:
            lines.append(f"    FAIL: {name}")
        for name in test_results["errors"]:
            lines.append(f"    ERROR: {name}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def main():
    report_only = "--report-only" in sys.argv

    if not report_only:
        print("Running UAT tests...\n")
        test_results = run_uats()

        # Save results
        RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        serializable = {k: v for k, v in test_results.items() if k != "raw_stdout" and k != "raw_stderr"}
        with open(RESULTS_FILE, "w") as f:
            json.dump(serializable, f, indent=2)
    else:
        if not RESULTS_FILE.exists():
            print("No previous results found. Run without --report-only first.")
            return
        with open(RESULTS_FILE) as f:
            test_results = json.load(f)

    question_counts = load_questions()
    report = generate_report(test_results, question_counts)
    print(report)

    # Also save report to file
    report_file = PROJECT_ROOT / "data" / "uat_report.txt"
    with open(report_file, "w") as f:
        f.write(report)
    print(f"\n  Report saved to: {report_file}")


if __name__ == "__main__":
    main()
