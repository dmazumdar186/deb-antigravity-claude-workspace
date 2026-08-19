"""
X Search Research Tool
Uses xAI's Grok API to research topics on X (Twitter).
Two modes:
  - "broad": Uses chat completions (cheap) for topic discovery
  - "deep": Uses Responses API with x_search (costlier) for actual tweets
"""

import os
import json
import time
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

XAI_API_KEY = os.getenv("XAI_API_KEY")
if not XAI_API_KEY:
    raise ValueError("XAI_API_KEY not found in .env")

# Use requests
import requests

CHAT_URL = "https://api.x.ai/v1/chat/completions"
RESPONSES_URL = "https://api.x.ai/v1/responses"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {XAI_API_KEY}",
}


def broad_research(prompt: str, model: str = "grok-4-latest", temperature: float = 0.7) -> str:
    """Cheap chat completions call - Grok synthesizes from its X knowledge."""
    payload = {
        "messages": [
            {"role": "system", "content": "You have deep knowledge of X/Twitter discussions. When asked about topics, draw on your knowledge of real posts, threads, and discussions. Be specific - cite real accounts and paraphrase real posts where possible."},
            {"role": "user", "content": prompt},
        ],
        "model": model,
        "stream": False,
        "temperature": temperature,
    }
    resp = requests.post(CHAT_URL, headers=HEADERS, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def deep_research(query: str, model: str = "grok-4-1-fast", from_date: str = None, to_date: str = None, handles: list = None) -> dict:
    """Responses API with x_search - returns actual tweets with citations."""
    tool_config = {"type": "x_search"}
    if from_date:
        tool_config["from_date"] = from_date
    if to_date:
        tool_config["to_date"] = to_date
    if handles:
        tool_config["allowed_x_handles"] = handles[:10]

    payload = {
        "model": model,
        "input": [{"role": "user", "content": query}],
        "tools": [tool_config],
    }
    resp = requests.post(RESPONSES_URL, headers=HEADERS, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    # Extract text and citations
    result = {"raw": data, "text": "", "citations": [], "cost_usd": 0}
    for output in data.get("output", []):
        if output.get("type") == "message":
            for content in output.get("content", []):
                if content.get("type") == "output_text":
                    result["text"] = content["text"]
                    result["citations"] = [
                        {"url": a["url"], "title": a.get("title", "")}
                        for a in content.get("annotations", [])
                        if a.get("type") == "url_citation"
                    ]

    usage = data.get("usage", {})
    cost_ticks = usage.get("cost_in_usd_ticks", 0)
    result["cost_usd"] = cost_ticks / 10_000_000_000  # 1 tick = 1/10B USD
    result["sources_used"] = usage.get("num_sources_used", 0)
    return result


def batch_broad_research(queries: list[str], output_file: str = None, delay: float = 1.0) -> list[dict]:
    """Run multiple broad research queries with rate limiting."""
    results = []
    for i, q in enumerate(queries):
        print(f"[{i+1}/{len(queries)}] {q[:80]}...")
        try:
            text = broad_research(q)
            results.append({"query": q, "response": text, "error": None})
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"query": q, "response": None, "error": str(e)})
        if i < len(queries) - 1:
            time.sleep(delay)

    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved {len(results)} results to {output_file}")

    return results


def batch_deep_research(queries: list[str], output_file: str = None, delay: float = 2.0, **kwargs) -> list[dict]:
    """Run multiple x_search queries with rate limiting."""
    results = []
    total_cost = 0
    for i, q in enumerate(queries):
        print(f"[{i+1}/{len(queries)}] {q[:80]}...")
        try:
            result = deep_research(q, **kwargs)
            total_cost += result["cost_usd"]
            results.append({"query": q, "text": result["text"], "citations": result["citations"], "cost_usd": result["cost_usd"], "error": None})
            print(f"  ${result['cost_usd']:.4f} | {len(result['citations'])} citations")
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"query": q, "text": None, "citations": [], "cost_usd": 0, "error": str(e)})
        if i < len(queries) - 1:
            time.sleep(delay)

    print(f"\nTotal cost: ${total_cost:.4f}")

    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Saved {len(results)} results to {output_file}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="X Search Research Tool")
    parser.add_argument("mode", choices=["broad", "deep", "test"], help="Research mode")
    parser.add_argument("--query", "-q", type=str, help="Single query")
    parser.add_argument("--queries-file", "-f", type=str, help="JSON file with list of queries")
    parser.add_argument("--output", "-o", type=str, help="Output file path")
    parser.add_argument("--from-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--handles", type=str, nargs="+", help="Filter to specific X handles")
    args = parser.parse_args()

    if args.mode == "test":
        print("Testing chat completions (broad)...")
        text = broad_research("What are the top 3 things people on X are discussing about AI agents today? Be specific.")
        print(f"\n{text}\n")

        print("\nTesting x_search (deep)...")
        result = deep_research("AI agent strategies and frameworks trending on X", from_date="2026-02-20", to_date="2026-02-27")
        print(f"\n{result['text']}\n")
        print(f"Citations: {len(result['citations'])}")
        for c in result["citations"]:
            print(f"  - {c['url']}")
        print(f"Cost: ${result['cost_usd']:.4f}")

    elif args.query:
        if args.mode == "broad":
            text = broad_research(args.query)
            print(text)
        else:
            result = deep_research(args.query, from_date=args.from_date, to_date=args.to_date, handles=args.handles)
            print(result["text"])
            for c in result["citations"]:
                print(f"  [{c['title']}] {c['url']}")
            print(f"\nCost: ${result['cost_usd']:.4f}")

    elif args.queries_file:
        with open(args.queries_file) as f:
            queries = json.load(f)
        if args.mode == "broad":
            batch_broad_research(queries, output_file=args.output)
        else:
            batch_deep_research(queries, output_file=args.output, from_date=args.from_date, to_date=args.to_date)

    else:
        parser.error("Provide --query or --queries-file")
