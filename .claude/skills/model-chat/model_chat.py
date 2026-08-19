#!/usr/bin/env python3
"""
Model Chat — Multi-agent debate orchestrator.

Spawns N Claude instances into a shared conversation room where they debate,
disagree, and converge on solutions using round-robin turns.
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

# Load .env from workspace root
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

# ── Config ──────────────────────────────────────────────────────────────────

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2048

AGENT_FRAMINGS = [
    {
        "id": "systems-thinker",
        "framing": (
            "You tend to think in systems and architecture. You reason about "
            "structure, dependencies, second-order effects, and how pieces fit "
            "together. You look for leverage points and compounding mechanisms."
        ),
    },
    {
        "id": "pragmatist",
        "framing": (
            "You tend to think practically and focus on what ships fast. You're "
            "skeptical of overengineering and prefer simple, proven approaches. "
            "You ask 'does this actually work in practice?' before anything else."
        ),
    },
    {
        "id": "edge-case-finder",
        "framing": (
            "You tend to find edge cases, failure modes, and hidden assumptions. "
            "You stress-test ideas by asking 'what happens when X goes wrong?' "
            "You're the one who prevents catastrophic oversights."
        ),
    },
    {
        "id": "user-advocate",
        "framing": (
            "You tend to think about user experience and how things feel in "
            "practice. You optimize for clarity, simplicity, and delight. You "
            "ask 'would a real person actually use this?' and 'is this intuitive?'"
        ),
    },
    {
        "id": "contrarian",
        "framing": (
            "You tend to challenge assumptions and propose unconventional "
            "alternatives. You play devil's advocate not to be difficult, but "
            "because the best ideas survive strong opposition. You ask 'what if "
            "the opposite were true?'"
        ),
    },
    {
        "id": "first-principles",
        "framing": (
            "You reason from first principles. You strip away conventions and "
            "ask 'why does it have to be this way?' You're willing to propose "
            "radical simplifications that others overlook."
        ),
    },
    {
        "id": "risk-analyst",
        "framing": (
            "You think in terms of risk, probability, and downside protection. "
            "You weigh the cost of being wrong against the cost of being slow. "
            "You look for irreversible decisions and flag them."
        ),
    },
    {
        "id": "integrator",
        "framing": (
            "You look for synthesis and common ground. You find the 80% that "
            "everyone agrees on and surface the 20% that actually matters. You "
            "bridge different perspectives into coherent plans."
        ),
    },
]

SYSTEM_PROMPT_TEMPLATE = """\
You are one of {agent_count} AI participants in a collaborative debate room. \
Your role is to help solve a problem through genuine intellectual discourse.

{framing}

## Rules of engagement
- Read all previous messages carefully before responding.
- Build on, challenge, or refine what others have said — don't just repeat your own position.
- If you agree with someone, say so briefly and add something new.
- If you disagree, explain WHY with concrete reasoning.
- Be concise. 150-300 words max per response. No filler.
- Use your unique perspective — that's why you're here.
- Address other participants directly when responding to their points.
- It's fine to change your mind if someone makes a compelling argument.

## Format
Start your response with **[{agent_id}]:** then your contribution. No preamble.\
"""

SYNTHESIZER_PROMPT = """\
You are a senior synthesizer. You've just observed a {round_count}-round debate \
between {agent_count} AI participants on the following topic:

**{topic}**

Read the full debate transcript below, then produce a structured synthesis.

## Your output format

### Consensus
What did most or all participants agree on? List the 3-5 strongest points of agreement.

### Key Disagreements
Where did participants genuinely disagree? For each disagreement:
- State the tension clearly
- Summarize each side's strongest argument
- Give your assessment of which side is stronger and why

### Surprising Insights
Any unexpected ideas, edge cases, or reframings that emerged from the debate?

### Final Recommendation
Based on the full debate, what is the best path forward? Be specific and actionable.

## Debate Transcript
{transcript}\
"""


# ── Helpers ─────────────────────────────────────────────────────────────────

def get_width() -> int:
    try:
        return min(os.get_terminal_size().columns, 80)
    except OSError:
        return 80


def color(text: str, code: str) -> str:
    """ANSI color wrapper."""
    return f"\033[{code}m{text}\033[0m"


AGENT_COLORS = ["36", "33", "35", "32", "31", "34", "96", "93"]


def agent_color(agent_idx: int, text: str) -> str:
    return color(text, AGENT_COLORS[agent_idx % len(AGENT_COLORS)])


def print_header(text: str) -> None:
    w = get_width()
    print(color(f"\n{'=' * w}", "1;37"))
    print(color(f"  {text}", "1;37"))
    print(color(f"{'=' * w}\n", "1;37"))


def print_round_header(round_num: int, total: int) -> None:
    w = get_width()
    print(color(f"\n{'-' * w}", "90"))
    print(color(f"  ROUND {round_num}/{total}", "1;97"))
    print(color(f"{'-' * w}", "90"))


# ── Core ────────────────────────────────────────────────────────────────────

async def get_agent_response(
    client: anthropic.AsyncAnthropic,
    agent_id: str,
    system_prompt: str,
    conversation_history: list[dict],
    topic: str,
) -> str:
    """Get a single agent's response (collected, not streamed to stdout)."""
    messages = []

    # First message: the topic
    messages.append({"role": "user", "content": f"**Topic for debate:** {topic}"})

    # Build alternating messages from conversation history
    for entry in conversation_history:
        messages.append({"role": "assistant", "content": entry["content"]})
        messages.append({
            "role": "user",
            "content": "Continue the debate. Respond to the points made above."
        })

    if conversation_history:
        # Replace the last generic prompt with a more specific one
        messages.pop()
        messages.append({
            "role": "user",
            "content": (
                "It's your turn. Respond to the discussion above. "
                "Build on, challenge, or refine what's been said."
            ),
        })

    # Use streaming + get_final_message for timeout protection, but collect silently
    async with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=messages,
    ) as stream:
        response = await stream.get_final_message()

    return response.content[0].text


def print_agent_response(agent_idx: int, agent_id: str, text: str) -> None:
    """Print an agent's response with color and formatting."""
    prefix = agent_color(agent_idx, f"\n[{agent_id}]")
    # Print prefix, then the response text colored
    sys.stdout.write(prefix + " ")
    sys.stdout.write(agent_color(agent_idx, text))
    sys.stdout.write("\n")
    sys.stdout.flush()


async def run_debate(
    topic: str,
    agent_count: int = 5,
    round_count: int = 5,
    interactive: bool = False,
) -> dict:
    """Run a multi-agent debate."""
    client = anthropic.AsyncAnthropic()

    # Select agents (cycle if more than available framings)
    agents = []
    for i in range(agent_count):
        framing = AGENT_FRAMINGS[i % len(AGENT_FRAMINGS)]
        agents.append({
            "idx": i,
            "id": framing["id"],
            "system_prompt": SYSTEM_PROMPT_TEMPLATE.format(
                agent_count=agent_count,
                framing=framing["framing"],
                agent_id=framing["id"],
            ),
        })

    # Conversation log
    conversation: list[dict] = []

    print_header(f"MODEL CHAT — {agent_count} agents, {round_count} rounds")
    print(color(f"  Topic: {topic}\n", "97"))
    print(color("  Agents:", "90"))
    for a in agents:
        print(agent_color(a["idx"], f"    - {a['id']}"))
    print()

    # ── Debate rounds ───────────────────────────────────────────────────
    for round_num in range(1, round_count + 1):
        print_round_header(round_num, round_count)

        # Fire all API calls in parallel (responses collected silently)
        tasks = [
            get_agent_response(
                client=client,
                agent_id=agent["id"],
                system_prompt=agent["system_prompt"],
                conversation_history=conversation.copy(),
                topic=topic,
            )
            for agent in agents
        ]

        print(color("  (all agents thinking...)", "90"))
        responses = await asyncio.gather(*tasks)

        # Print responses sequentially (no interleaving)
        for agent, response_text in zip(agents, responses):
            print_agent_response(agent["idx"], agent["id"], response_text)

            conversation.append({
                "round": round_num,
                "agent_id": agent["id"],
                "content": f"**[{agent['id']}]:** {response_text}",
                "timestamp": datetime.now().isoformat(),
            })

        # Interactive mode: prompt for user input between rounds
        if interactive and round_num < round_count:
            print(color(
                "\n  [Interactive] Press Enter to continue, or type to inject a message:",
                "90",
            ))
            try:
                user_input = input(color("  > ", "97")).strip()
                if user_input:
                    print(color(f"\n  [User]: {user_input}", "1;97"))
                    conversation.append({
                        "round": round_num,
                        "agent_id": "user",
                        "content": f"**[User (moderator)]:** {user_input}",
                        "timestamp": datetime.now().isoformat(),
                    })
            except EOFError:
                pass

    # ── Synthesis ───────────────────────────────────────────────────────
    print_header("SYNTHESIS")

    transcript = "\n\n".join(entry["content"] for entry in conversation)

    synth_prompt = SYNTHESIZER_PROMPT.format(
        round_count=round_count,
        agent_count=agent_count,
        topic=topic,
        transcript=transcript,
    )

    # Stream synthesis to stdout for real-time feel
    synthesis_parts = []
    async with client.messages.stream(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": synth_prompt}],
    ) as stream:
        async for text in stream.text_stream:
            sys.stdout.write(color(text, "97"))
            sys.stdout.flush()
            synthesis_parts.append(text)

    synthesis = "".join(synthesis_parts)
    print("\n")

    # ── Save outputs ────────────────────────────────────────────────────
    base_dir = Path(__file__).resolve().parents[3] / "active" / "model-chat"
    run_ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = base_dir / run_ts
    output_dir.mkdir(parents=True, exist_ok=True)

    conv_data = {
        "topic": topic,
        "agent_count": agent_count,
        "round_count": round_count,
        "model": MODEL,
        "timestamp": datetime.now().isoformat(),
        "agents": [{"id": a["id"], "idx": a["idx"]} for a in agents],
        "conversation": conversation,
        "synthesis": synthesis,
    }
    conv_path = output_dir / "conversation.json"
    conv_path.write_text(json.dumps(conv_data, indent=2))

    synth_path = output_dir / "synthesis.md"
    synth_path.write_text(
        f"# Model Chat Synthesis\n\n"
        f"**Topic:** {topic}\n"
        f"**Agents:** {agent_count} | **Rounds:** {round_count} | "
        f"**Model:** {MODEL}\n"
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"---\n\n{synthesis}\n"
    )

    # Update 'latest' symlink for easy access
    latest_link = base_dir / "latest"
    latest_link.unlink(missing_ok=True)
    latest_link.symlink_to(output_dir)

    print(color(f"  Saved: {conv_path}", "90"))
    print(color(f"  Saved: {synth_path}", "90"))

    return conv_data


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Model Chat — Multi-agent debate")
    parser.add_argument("topic", help="Topic or problem to debate")
    parser.add_argument("--agents", type=int, default=5, help="Number of agents (default: 5)")
    parser.add_argument("--rounds", type=int, default=5, help="Number of rounds (default: 5)")
    parser.add_argument("--interactive", action="store_true", help="Enable interactive mode")
    args = parser.parse_args()

    asyncio.run(run_debate(
        topic=args.topic,
        agent_count=args.agents,
        round_count=args.rounds,
        interactive=args.interactive,
    ))


if __name__ == "__main__":
    main()
