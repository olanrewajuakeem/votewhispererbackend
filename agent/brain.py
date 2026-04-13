"""
VoteWhisperer agent brain — orchestrates Claude with tool use.

Claude reasons about what to do next and calls skill functions
as tools. The loop continues until Claude signals it is done.
"""

import json
from typing import Any

import anthropic

import config
from agent.persona import SYSTEM_PROMPT
from agent import state as agent_state
from skills import prediction, onchain, social, onboarding, audiera_music
from skills.audiera_music import get_weekly_leaderboard, get_chain_stats
from utils.logger import agent_say, action, ok, err, divider

client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

# ─────────────────────────────────────────────────────────────────────────────
# Tool definitions (Claude sees these)
# ─────────────────────────────────────────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "get_beatvote_songs",
        "description": (
            "Fetch the current week's songs from the Beatvote on-chain contract. "
            "Returns song IDs, titles, artists, and live vote counts. "
            "This is the PRIMARY data source — always call this before analyzing or voting."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "analyze_beatvote",
        "description": (
            "Score and rank the current week's Beatvote songs by vote count, "
            "dance-mat potential, meme energy, and chart history. "
            "Returns a ranked prediction board with confidence scores and reasoning. "
            "Call get_beatvote_songs first, or this will fetch them automatically."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Unused — kept for compatibility. Songs come from Beatvote contract.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_wallet_info",
        "description": (
            "Fetch the agent's current wallet balances on BNB Chain: "
            "$BEAT token balance, veBEAT voting power, and BNB gas balance. "
            "Also shows whether the 2× first-stake acceleration is active."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "stake_beat",
        "description": (
            "Stake $BEAT tokens to acquire veBEAT voting power on Audiera. "
            "First-time stakers get a 2× veBEAT bonus (resets every 15 days). "
            "More veBEAT = stronger votes + larger share of the weekly 5,000 BEAT reward pool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "Amount of $BEAT to stake (e.g. 500).",
                }
            },
            "required": ["amount"],
        },
    },
    {
        "name": "cast_votes",
        "description": (
            "Cast veBEAT votes on-chain for songs in the current Beatvote week. "
            "Use song_id values from get_beatvote_songs. "
            "Weights should sum to 1.0 — diversify like a pro (e.g. 0.5 / 0.3 / 0.2)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "votes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "song_id":   {"type": "string", "description": "Song ID from Beatvote contract"},
                            "song_name": {"type": "string", "description": "Song title"},
                            "weight":    {"type": "number", "description": "Allocation 0.0–1.0"},
                        },
                        "required": ["song_id", "song_name", "weight"],
                    },
                }
            },
            "required": ["votes"],
        },
    },
    {
        "name": "claim_rewards",
        "description": (
            "Claim this week's voter rewards from the shared 5,000 BEAT pool. "
            "Call after the voting window closes. Returns BEAT claimed and tx hash."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "generate_lyrics",
        "description": (
            "Generate song lyrics via the Audiera Lyrics Skill API. "
            "Required for the contest — shows the Create part of Create→Participate→Earn."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "theme": {
                    "type": "string",
                    "description": "Theme or inspiration for the lyrics (e.g. 'neon city dance vibes').",
                },
                "styles": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Music styles e.g. ['Dance', 'Electronic']. Max 3.",
                },
            },
            "required": ["theme"],
        },
    },
    {
        "name": "generate_music",
        "description": (
            "Generate a full AI song with vocals via the Audiera Music Skill API. "
            "Required for the contest — shows the Create part of Create→Participate→Earn. "
            "Provide either lyrics (from generate_lyrics) or an inspiration string."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "styles": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Music styles e.g. ['Dance', 'Electronic']. Max 3.",
                },
                "artist_id": {
                    "type": "string",
                    "description": "Audiera artist ID. Use 'default' if unknown.",
                    "default": "default",
                },
                "lyrics": {
                    "type": "string",
                    "description": "Lyrics text (from generate_lyrics tool).",
                },
                "inspiration": {
                    "type": "string",
                    "description": "Inspiration prompt if no lyrics provided.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "post_to_x",
        "description": (
            "Post a tweet (or thread) on X/Twitter in VoteWhisperer persona voice. "
            "For a single tweet set is_thread=false. "
            "For a thread pass is_thread=true and include thread_tweets list."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Main tweet (≤280 chars)."},
                "is_thread": {"type": "boolean", "default": False},
                "thread_tweets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional thread tweets (≤280 chars each).",
                },
            },
            "required": ["message"],
        },
    },
    {
        "name": "post_prediction_tweet",
        "description": "Compose and post a formatted prediction tweet from the latest analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ranked_songs": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Ranked song list from analyze_beatvote.",
                }
            },
            "required": ["ranked_songs"],
        },
    },
    {
        "name": "post_vote_tweet",
        "description": "Post a vote confirmation tweet after casting on-chain votes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "votes":   {"type": "array", "items": {"type": "object"}},
                "tx_hash": {"type": "string"},
            },
            "required": ["votes", "tx_hash"],
        },
    },
    {
        "name": "post_reward_tweet",
        "description": "Post a reward claim announcement tweet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount":  {"type": "number"},
                "tx_hash": {"type": "string"},
            },
            "required": ["amount", "tx_hash"],
        },
    },
    {
        "name": "post_onboarding_thread",
        "description": "Post the full Web2-to-Web3 onboarding thread on X.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "run_onboarding",
        "description": (
            "Run the interactive Web2→Web3 onboarding guide for a new user. "
            "Explains staking, veBEAT, Beatvote, and earning in plain language."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_level": {
                    "type": "string",
                    "enum": ["complete_beginner", "crypto_curious", "defi_familiar"],
                },
                "interactive": {"type": "boolean", "default": True},
            },
            "required": ["user_level"],
        },
    },
    {
        "name": "get_agent_state",
        "description": "Get a summary of the agent's current on-chain and activity state.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_weekly_leaderboard",
        "description": (
            "Fetch this week's real Audiera song leaderboard: top played songs, "
            "community favourite, and rising track with live play counts and likes. "
            "Use this for up-to-date song data before analyzing or voting."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_chain_stats",
        "description": (
            "Fetch live Audiera platform stats: total users, active users last week, "
            "NFT supply, BEAT burned this week and all time. Good for context when onboarding users."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Tool dispatcher
# ─────────────────────────────────────────────────────────────────────────────

def _dispatch(tool_name: str, tool_input: dict) -> Any:
    action(f"Tool: {tool_name}", _short(tool_input))

    if tool_name == "get_beatvote_songs":
        return onchain.get_voting_songs()

    elif tool_name == "analyze_beatvote":
        return prediction.analyze_trends(tool_input.get("queries"))

    elif tool_name == "get_wallet_info":
        return onchain.get_wallet_info()

    elif tool_name == "stake_beat":
        return onchain.stake_beat(tool_input["amount"])

    elif tool_name == "cast_votes":
        return onchain.cast_votes(tool_input["votes"])

    elif tool_name == "claim_rewards":
        return onchain.claim_rewards()

    elif tool_name == "generate_lyrics":
        return audiera_music.generate_lyrics(
            theme=tool_input["theme"],
            styles=tool_input.get("styles"),
        )

    elif tool_name == "generate_music":
        return audiera_music.generate_music(
            styles=tool_input.get("styles"),
            artist_id=tool_input.get("artist_id", "default"),
            lyrics=tool_input.get("lyrics"),
            inspiration=tool_input.get("inspiration"),
        )

    elif tool_name == "post_to_x":
        return social.post_tweet(
            tool_input["message"],
            is_thread=tool_input.get("is_thread", False),
            thread_tweets=tool_input.get("thread_tweets", []),
        )

    elif tool_name == "post_prediction_tweet":
        return social.tweet_prediction(tool_input.get("ranked_songs", []))

    elif tool_name == "post_vote_tweet":
        return social.tweet_vote_confirmation(tool_input["votes"], tool_input["tx_hash"])

    elif tool_name == "post_reward_tweet":
        return social.tweet_reward_claim(tool_input["amount"], tool_input["tx_hash"])

    elif tool_name == "post_onboarding_thread":
        return social.tweet_onboarding_guide()

    elif tool_name == "run_onboarding":
        return onboarding.run_guide(
            user_level=tool_input.get("user_level", "complete_beginner"),
            interactive=tool_input.get("interactive", True),
        )

    elif tool_name == "get_agent_state":
        return agent_state.summary()

    elif tool_name == "get_weekly_leaderboard":
        return get_weekly_leaderboard()

    elif tool_name == "get_chain_stats":
        return get_chain_stats()

    else:
        return {"error": f"Unknown tool: {tool_name}"}


def _short(d: dict) -> str:
    s = json.dumps(d)
    return s[:80] + "..." if len(s) > 80 else s


# ─────────────────────────────────────────────────────────────────────────────
# Main agent loop
# ─────────────────────────────────────────────────────────────────────────────

def run(command: str, context: dict | None = None, max_iterations: int = 15) -> str:
    """
    Run the VoteWhisperer agent for a given command string.
    Uses Claude tool-use loop until the model signals end_turn.
    Returns the final text response.
    """
    user_content = command
    if context:
        user_content += f"\n\nContext:\n{json.dumps(context, indent=2)}"

    messages: list[dict] = [{"role": "user", "content": user_content}]
    agent_say(f'"{command[:72]}{"..." if len(command) > 72 else ""}"')
    divider()

    for iteration in range(max_iterations):
        response = client.messages.create(
            model=config.MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    divider()
                    agent_say(block.text)
                    return block.text
            return ""

        elif response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = _dispatch(block.name, block.input)
                    ok(f"→ {block.name} done")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    })
            messages.append({"role": "user", "content": tool_results})

        else:
            err(f"Unexpected stop reason: {response.stop_reason}")
            break

    return "Max iterations reached."
