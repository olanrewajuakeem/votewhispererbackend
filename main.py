"""
VoteWhisperer — Beatvote Strategist & Prediction Agent
Audiera Agent-Native Challenge 2026

Usage:
  python main.py analyze          # Trend analysis + prediction
  python main.py vote             # Full stake + vote cycle
  python main.py earn             # Claim weekly rewards
  python main.py onboard          # Web2→Web3 onboarding demo
  python main.py loop             # Full weekly loop (analyze→vote→post)
  python main.py chat             # Interactive chat with the agent
  python main.py status           # Show current wallet + agent state
  python main.py post-guide       # Post onboarding thread to X
"""

import argparse
import sys

import config
from utils.logger import agent_say, panel, mock_badge, divider, console, ok, info
from agent import brain, state as agent_state
from skills import prediction, onchain, social, onboarding
from rich.prompt import Prompt


# ─────────────────────────────────────────────────────────────────────────────
# Mode handlers
# ─────────────────────────────────────────────────────────────────────────────

def cmd_analyze(args):
    """Scan Beatvote and print ranked predictions."""
    result = brain.run(
        "Fetch the current Beatvote songs from the Audiera leaderboard. "
        "Score and rank the top songs by vote probability. "
        "Explain your reasoning for the top 3 picks in your persona voice. "
        "Show me the full ranked prediction board."
    )
    # Also show the song table directly
    raw = prediction.analyze_trends()
    if raw.get("ranked_songs"):
        from utils.logger import song_table
        song_table(raw["ranked_songs"][:8])


def cmd_vote(args):
    """Full stake → analyze → vote → post cycle."""
    brain.run(
        "Run the full vote cycle:\n"
        "1. Check my wallet balances.\n"
        "2. If veBEAT is low (< 1000), stake 500 BEAT to top it up.\n"
        "3. Analyze X trends to get ranked song predictions.\n"
        "4. Cast votes on the top 3 songs using my veBEAT, "
        "   allocating weight proportional to their confidence scores.\n"
        "5. Post a vote confirmation tweet in your persona voice.\n"
        "Narrate each step as you go."
    )


def cmd_earn(args):
    """Claim weekly rewards and optionally restake."""
    brain.run(
        "Claim my weekly voter rewards from the Beatvote reward pool. "
        "After claiming, restake 80% of the rewards to compound my veBEAT for next week. "
        "Post a reward claim tweet. "
        "Tell me the net BEAT earned and my updated wallet state."
    )


def cmd_onboard(args):
    """Run the interactive Web2→Web3 onboarding guide."""
    level = args.level if hasattr(args, "level") and args.level else "complete_beginner"
    interactive = not (hasattr(args, "no_interactive") and args.no_interactive)

    agent_say("Running Web2 → Web3 onboarding guide...")
    divider()
    result = onboarding.run_guide(user_level=level, interactive=interactive)

    # Also ask the AI to summarize it in persona voice
    brain.run(
        f"A new {result['level'].replace('_', ' ')} user just asked how to start "
        f"earning on Audiera. Give them a warm, encouraging summary in your VoteWhisperer "
        f"persona voice. Keep it concise and actionable. "
        f"Mention the staking URL, the 2× first-time bonus, and the weekly reward pool."
    )


def cmd_loop(args):
    """Full weekly loop — the full Create→Participate→Earn demo."""
    console.rule("[bold magenta]VoteWhisperer — Weekly Loop[/bold magenta]")
    brain.run(
        "Run the full VoteWhisperer weekly loop. Do each step in order and narrate:\n\n"
        "STEP 1 — ANALYZE:\n"
        "  Fetch the Audiera weekly leaderboard and current Beatvote songs. "
        "  Score and rank songs. Share your top 3 picks with confidence scores and reasoning.\n\n"
        "STEP 2 — STAKE:\n"
        "  Check wallet. If veBEAT is below 2000, stake 500 BEAT. "
        "  Note whether the 2× acceleration is active.\n\n"
        "STEP 3 — VOTE:\n"
        "  Cast votes on the top 3 songs from your analysis. "
        "  Allocate weights proportionally to scores (not all-in on one track — diversify like a pro).\n\n"
        "STEP 4 — POST:\n"
        "  Post a prediction tweet with your picks. "
        "  Post a separate vote confirmation tweet with the tx hash.\n\n"
        "STEP 5 — EARN (if rewards pending):\n"
        "  Check and claim any pending rewards. "
        "  Mention the total earned and the weekly pool mechanics.\n\n"
        "STEP 6 — ONBOARD:\n"
        "  Give a one-paragraph Web2-friendly explanation of what you just did and "
        "  how a newcomer can do the same thing.\n\n"
        "Use your full VoteWhisperer voice throughout. "
        "Disclaim predictions clearly. Show on-chain data transparently."
    )


def cmd_chat(args):
    """Interactive chat with the agent."""
    agent_say("VoteWhisperer is online. Ask me anything about Beatvote strategy, staking, predictions, or onboarding.")
    agent_say("Type 'exit' or Ctrl+C to quit.\n")
    divider()

    history: list[dict] = []

    while True:
        try:
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            agent_say("Signing off. Stay alpha. 🎵")
            break

        if user_input.strip().lower() in ("exit", "quit", "bye"):
            agent_say("Signing off. Stay alpha. 🎵")
            break

        if not user_input.strip():
            continue

        # For chat, pass conversation history inline
        history.append({"role": "user", "content": user_input})
        response = brain.run(user_input)
        history.append({"role": "assistant", "content": response})
        divider()


def cmd_status(args):
    """Show current wallet + agent state."""
    wallet = onchain.get_wallet_info()
    state  = agent_state.summary()

    panel(
        "VoteWhisperer Status",
        f"Wallet:  {wallet.get('address', 'not set')}\n"
        f"BNB:     {wallet.get('bnb_balance', 0):.4f}\n"
        f"$BEAT:   {wallet.get('beat_balance', 0):.2f}\n"
        f"veBEAT:  {wallet.get('vebeat_balance', 0):.2f}\n"
        f"2× Accel Active: {wallet.get('first_stake_acceleration_active', '?')}\n\n"
        f"Total Staked:          {state.get('total_staked', 0):.2f} BEAT\n"
        f"Total Rewards Claimed: {state.get('total_rewards_claimed', 0):.2f} BEAT\n"
        f"Votes This Week:       {state.get('votes_this_week_count', 0)}\n"
        f"Tweets Posted:         {state.get('posts_count', 0)}\n\n"
        f"Mode: {'🟡 MOCK' if config.MOCK_MODE else '🟢 LIVE'}",
        style="magenta",
    )


def cmd_post_guide(args):
    """Post the full onboarding thread to X."""
    agent_say("Posting Web2→Web3 onboarding thread to X...")
    result = social.tweet_onboarding_guide()
    if result.get("status") == "ok":
        ok(f"Posted {result['count']} tweets. IDs: {result['tweet_ids']}")
    else:
        from utils.logger import err
        err(f"Failed: {result.get('error', 'unknown')}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI setup
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="votewhisperer",
        description="VoteWhisperer — Beatvote Strategist & Prediction Agent for Audiera",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("analyze",    help="Scan trends + print ranked predictions")
    sub.add_parser("vote",       help="Full stake → analyze → vote → post cycle")
    sub.add_parser("earn",       help="Claim weekly rewards + restake")
    sub.add_parser("loop",       help="Full weekly loop (analyze→stake→vote→post→earn)")
    sub.add_parser("status",     help="Show wallet + agent state")
    sub.add_parser("post-guide", help="Post onboarding thread to X")
    sub.add_parser("chat",       help="Interactive chat with the agent")

    onboard_p = sub.add_parser("onboard", help="Web2→Web3 onboarding demo")
    onboard_p.add_argument(
        "--level",
        choices=["complete_beginner", "crypto_curious", "defi_familiar"],
        default="complete_beginner",
        help="User knowledge level (default: complete_beginner)",
    )
    onboard_p.add_argument(
        "--no-interactive",
        action="store_true",
        help="Print all steps at once without pausing",
    )

    return p


HANDLERS = {
    "analyze":    cmd_analyze,
    "vote":       cmd_vote,
    "earn":       cmd_earn,
    "onboard":    cmd_onboard,
    "loop":       cmd_loop,
    "chat":       cmd_chat,
    "status":     cmd_status,
    "post-guide": cmd_post_guide,
}


def main():
    parser = build_parser()
    args   = parser.parse_args()

    # Header
    console.rule("[bold magenta]🎵  VoteWhisperer  ·  Beatvote Strategist  ·  Audiera AI  🎵[/bold magenta]")
    if config.MOCK_MODE:
        mock_badge()
    divider()

    # Validate Claude API key exists
    if not config.ANTHROPIC_API_KEY:
        console.print("[bold red]ERROR:[/bold red] ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    handler = HANDLERS.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
