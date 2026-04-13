"""
Web2 → Web3 onboarding flow.

Provides interactive step-by-step guides at three knowledge levels.
Can also output a formatted summary for the agent to include in tweets/responses.
"""

import config
from utils.logger import agent_say, panel, info, ok, divider, console
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown


GUIDES = {
    "complete_beginner": {
        "label": "Complete Beginner",
        "intro": (
            "Hey! Zero crypto experience? Perfect starting point. "
            "I'll walk you through everything — plain language, no jargon. "
            "By the end you'll know how to vote on music and earn $BEAT. 🎵"
        ),
        "steps": [
            {
                "title": "What is $BEAT?",
                "content": (
                    "$BEAT is the token (digital coin) that powers the Audiera music platform on BNB Chain.\n\n"
                    "Think of it like loyalty points — except they're yours, tradeable, and you can earn more "
                    "just by participating in the community."
                ),
                "analogy": "Like frequent flyer miles, but for music lovers — and you can actually trade them.",
            },
            {
                "title": "What is Staking?",
                "content": (
                    f"Staking means locking your $BEAT at {config.AUDIERA_STAKE_URL} to get veBEAT (vote-escrowed BEAT).\n\n"
                    "veBEAT is your voting power. The more you stake (and the longer you lock), "
                    "the more veBEAT you get.\n\n"
                    "Bonus: First-time stakers get a 2× veBEAT boost! This resets every 15 days."
                ),
                "analogy": "Like putting your chips on the table — you get more weight at the vote.",
            },
            {
                "title": "What is Beatvote?",
                "content": (
                    f"Beatvote is Audiera's weekly music chart — but community-driven and on-chain.\n\n"
                    f"Go to {config.AUDIERA_BEATVOTE_URL}, pick songs you think will be hits, "
                    f"and use your veBEAT to vote for them.\n\n"
                    "Songs that reach the Top 10 get featured in Audiera's rhythm game, dance mat, "
                    "and idol performances by Kira and Ray."
                ),
                "analogy": "Like a Billboard chart vote — but it's public, on-chain, and it pays you.",
            },
            {
                "title": "How do I earn?",
                "content": (
                    "Every week, a pool of up to 5,000 $BEAT is shared between all voters.\n\n"
                    "You just need to cast at least one vote. "
                    "The more veBEAT you hold, the bigger your slice of the pool.\n\n"
                    "After the voting window closes, you can claim your rewards directly on-chain."
                ),
                "analogy": "The weekly pot gets split between everyone who voted. Bigger stake = bigger cut.",
            },
            {
                "title": "The Flywheel",
                "content": (
                    "Here's the beautiful part:\n\n"
                    "Stake $BEAT → get veBEAT → vote → earn $BEAT rewards → restake → "
                    "get more veBEAT → vote stronger next week → earn more. 🔄\n\n"
                    "VoteWhisperer does this loop autonomously — but you can do it manually too, "
                    "and it takes about 5 minutes per week."
                ),
                "analogy": "Reinvesting your winnings to play stronger next round.",
            },
        ],
        "cta": (
            f"Ready? Here's your checklist:\n"
            f"1. Get some $BEAT (BNB Chain, token: {config.BEAT_TOKEN_ADDRESS[:20]}...)\n"
            f"2. Stake at {config.AUDIERA_STAKE_URL}\n"
            f"3. Vote at {config.AUDIERA_BEATVOTE_URL}\n"
            f"4. Claim rewards at week end\n"
            f"5. Follow VoteWhisperer for weekly predictions 🎵"
        ),
    },

    "crypto_curious": {
        "label": "Crypto Curious",
        "intro": (
            "You know the basics of crypto — wallets, tokens, maybe some DeFi. "
            "Let me show you how Audiera's voting flywheel works and why it's worth participating."
        ),
        "steps": [
            {
                "title": "$BEAT & veBEAT mechanics",
                "content": (
                    f"$BEAT (CA: `{config.BEAT_TOKEN_ADDRESS}` on BSC) is the platform token.\n\n"
                    f"Stake at {config.AUDIERA_STAKE_URL} → receive veBEAT proportional to "
                    f"amount × lock duration.\n\n"
                    f"First-time staker bonus: **2× veBEAT** acceleration (resets every 15 days).\n"
                    f"veBEAT decays over time — restake to maintain voting power."
                ),
                "analogy": "Similar to Curve's veCRV model — lock tokens, get time-weighted voting power.",
            },
            {
                "title": "Weekly Beatvote cycle",
                "content": (
                    f"Songs submitted via Audiera Creative Studio enter the weekly vote.\n"
                    f"Voting window opens each week at {config.AUDIERA_BEATVOTE_URL}.\n"
                    f"Voters allocate veBEAT across tracks — all on-chain, BSC.\n"
                    f"Top 10 songs get in-game featuring + creator rewards."
                ),
                "analogy": "On-chain governance, but for music charts instead of protocol upgrades.",
            },
            {
                "title": "Voter rewards",
                "content": (
                    f"Up to **{config.WEEKLY_REWARD_POOL:,} $BEAT** distributed to voters weekly.\n"
                    "Distributed proportionally to veBEAT weight.\n"
                    "Minimum: cast at least one vote. Rewards claimable on-chain at week end."
                ),
                "analogy": "Like liquidity mining, but for voting participation instead of LP positions.",
            },
        ],
        "cta": (
            f"Quick start:\n"
            f"1. Stake BEAT → {config.AUDIERA_STAKE_URL} (hit the 2× window)\n"
            f"2. Check VoteWhisperer predictions before voting\n"
            f"3. Cast votes → {config.AUDIERA_BEATVOTE_URL}\n"
            f"4. Claim at week end, restake to compound"
        ),
    },

    "defi_familiar": {
        "label": "DeFi Familiar",
        "intro": (
            "You know vote-escrow, gauge weights, and reward pools. "
            "Here's the Audiera-specific context you need."
        ),
        "steps": [
            {
                "title": "Protocol mechanics",
                "content": (
                    f"$BEAT CA: `{config.BEAT_TOKEN_ADDRESS}` (BNB Chain, Chain ID 56)\n\n"
                    "veBEAT follows a vote-escrow model: amount × time_lock.\n"
                    "First-time staker: 2× veBEAT multiplier, resets every 15 days — "
                    "exploit this window for rapid veBEAT accumulation.\n"
                    "veBEAT decays linearly unless restaked."
                ),
                "analogy": None,
            },
            {
                "title": "Beatvote gauge",
                "content": (
                    "Weekly voting window on songs (music NFTs).\n"
                    "veBEAT allocated as gauge weights across tracks.\n"
                    "Top 10 by weight get creator rewards + in-game featuring.\n"
                    "All vote state is on-chain BSC — transparent, queryable."
                ),
                "analogy": None,
            },
            {
                "title": "Voter reward mechanics",
                "content": (
                    f"Pool: up to {config.WEEKLY_REWARD_POOL:,} BEAT/week.\n"
                    "Distributed pro-rata by veBEAT weight at snapshot.\n"
                    "Minimum qualification: ≥1 vote cast in the window.\n"
                    "Optimal strategy: maximize veBEAT during 2× window, vote on high-probability "
                    "Top 10 tracks, restake rewards to compound."
                ),
                "analogy": None,
            },
        ],
        "cta": (
            f"Contract addresses: BEAT={config.BEAT_TOKEN_ADDRESS}\n"
            f"Staking: {config.AUDIERA_STAKE_URL}\n"
            f"Voting: {config.AUDIERA_BEATVOTE_URL}\n"
            f"VoteWhisperer automates the full stake→vote→claim→restake loop."
        ),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_guide(user_level: str = "complete_beginner", interactive: bool = True) -> dict:
    """
    Run the onboarding guide.
    interactive=True:  step-by-step with pause between each section.
    interactive=False: print everything at once (good for piping to agent response).
    """
    guide = GUIDES.get(user_level, GUIDES["complete_beginner"])

    divider()
    agent_say(guide["intro"])
    divider()

    steps_text = []
    for i, step in enumerate(guide["steps"], 1):
        title   = f"Step {i} — {step['title']}"
        content = step["content"]
        if step.get("analogy"):
            content += f"\n\nSimple version: {step['analogy']}"

        if interactive:
            panel(title, content, style="magenta")
            try:
                if i < len(guide["steps"]):
                    Confirm.ask("[dim]Continue to next step?[/dim]", default=True)
            except (KeyboardInterrupt, EOFError):
                pass
        else:
            info(f"{title}: {content[:120]}...")

        steps_text.append(f"**{title}**\n{content}")

    divider()
    agent_say(guide["cta"])
    divider()

    return {
        "status": "ok",
        "level": user_level,
        "steps_completed": len(guide["steps"]),
        "cta": guide["cta"],
        "full_guide": "\n\n".join(steps_text),
    }


def quick_summary(user_level: str = "complete_beginner") -> str:
    """Return a one-paragraph summary for the agent to include in tweets or chat."""
    summaries = {
        "complete_beginner": (
            f"Stake your $BEAT at {config.AUDIERA_STAKE_URL} → get veBEAT → "
            f"vote on songs at {config.AUDIERA_BEATVOTE_URL} → earn a share of the weekly "
            f"{config.WEEKLY_REWARD_POOL:,} $BEAT pool. First-time stakers get 2× veBEAT. "
            "Takes 5 minutes, earns every week."
        ),
        "crypto_curious": (
            f"Stake $BEAT → veBEAT (2× boost for first-timers, resets every 15 days) → "
            f"vote on Beatvote weekly → share {config.WEEKLY_REWARD_POOL:,} BEAT voter pool. "
            "Restake rewards to compound. All on BSC, cheap gas."
        ),
        "defi_familiar": (
            f"veCRV-style gauge voting on music NFTs. 2× veBEAT multiplier window (15-day reset). "
            f"{config.WEEKLY_REWARD_POOL:,} BEAT/week voter pool distributed pro-rata by veBEAT weight. "
            f"BEAT CA: {config.BEAT_TOKEN_ADDRESS}."
        ),
    }
    return summaries.get(user_level, summaries["complete_beginner"])
