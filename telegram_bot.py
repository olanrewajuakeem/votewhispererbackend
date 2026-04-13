"""
VoteWhisperer Telegram Bot

Commands:
  /start    — welcome + what the bot can do
  /analyze  — get this week's ranked Beatvote predictions
  /vote     — run the full stake + vote cycle
  /earn     — claim weekly rewards + restake
  /loop     — full Create→Participate→Earn weekly loop
  /wallet [0x...]  — check wallet balances (yours or the agent's)
  /onboard  — Web2→Web3 explainer
  /help     — list commands

Any other message → chat with the agent

Run:
  python telegram_bot.py

Requires:
  pip install python-telegram-bot
  TELEGRAM_BOT_TOKEN in .env
"""

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction

import config
from agent import brain

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _thinking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show typing indicator while agent works."""
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )


async def _reply(update: Update, text: str):
    """Send a response, splitting if over Telegram's 4096 char limit."""
    if not text:
        return
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        await update.message.reply_text(chunk)


async def _run_agent(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str):
    """Run the agent brain and send back the response."""
    await _thinking(update, context)
    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None, brain.run, prompt
        )
        await _reply(update, response)
    except Exception as e:
        logger.error(f"Agent error: {e}")
        await update.message.reply_text(
            "Something went wrong on my end. Try again in a moment."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Command handlers
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "VoteWhisperer is online.\n\n"
        "I'm an autonomous AI agent that handles the full Audiera Beatvote cycle "
        "— analyzing songs, staking BEAT, casting on-chain votes, and claiming weekly rewards.\n\n"
        "Here's what you can do:\n\n"
        "/analyze — get this week's ranked predictions\n"
        "/vote — run the full stake and vote cycle\n"
        "/earn — claim weekly rewards\n"
        "/loop — full Create, Participate, Earn loop\n"
        "/wallet — check wallet balances\n"
        "/onboard — explain how everything works\n\n"
        "Or just type any question and I'll answer it."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n\n"
        "/analyze — ranked Beatvote predictions with confidence scores\n"
        "/vote — stake BEAT and cast weighted on-chain votes\n"
        "/earn — claim voter rewards and restake 80%\n"
        "/loop — full weekly loop: create, analyze, stake, vote, earn\n"
        "/wallet — agent wallet balances. Add your address to check your own: /wallet 0x...\n"
        "/onboard — plain English guide to staking and voting\n"
        "/help — this list\n\n"
        "You can also just ask me anything about Beatvote strategy."
    )


async def cmd_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _thinking(update, context)
    await _run_agent(update, context,
        "Fetch the current Beatvote songs from the Audiera leaderboard. "
        "Score and rank them. Give your top 3 picks with confidence scores and reasoning. "
        "Keep it concise."
    )


async def cmd_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Running the vote cycle now. This takes about a minute...")
    await _run_agent(update, context,
        "Run the full vote cycle: "
        "1. Check wallet balances. "
        "2. If veBEAT is below 1000 and BEAT balance is above 0, stake all available BEAT. "
        "3. Fetch current Beatvote songs from the leaderboard. "
        "4. Score and rank them. "
        "5. Cast votes on the top 3, allocating weight by confidence score. "
        "Show the final vote allocation and tx hash."
    )


async def cmd_earn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Checking for claimable rewards...")
    await _run_agent(update, context,
        "Claim my weekly voter rewards from the Beatvote reward pool. "
        "After claiming, restake 80% to compound veBEAT for next week. "
        "Tell me the net BEAT earned, the tx hash, and updated wallet state."
    )


async def cmd_loop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Running the full weekly loop. This takes a few minutes — "
        "creating music, analyzing Beatvote, staking, and voting..."
    )
    await _run_agent(update, context,
        "Run the full VoteWhisperer weekly loop in order:\n\n"
        "STEP 1 — CREATE: Generate lyrics then a full song on Audiera.\n"
        "STEP 2 — ANALYZE: Fetch the leaderboard, score and rank songs, share top 3 picks.\n"
        "STEP 3 — STAKE: Check wallet. If veBEAT below 2000, stake 500 BEAT.\n"
        "STEP 4 — VOTE: Cast weighted votes on the top 3 songs.\n"
        "STEP 5 — EARN: Check and claim any pending rewards.\n"
        "Narrate each step in your VoteWhisperer voice. Show tx hashes and amounts."
    )


async def cmd_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if user passed their own address: /wallet 0x...
    args = context.args
    if args and args[0].startswith("0x") and len(args[0]) == 42:
        user_address = args[0]
        await _run_agent(update, context,
            f"Fetch live BNB, BEAT, and veBEAT balances for wallet address {user_address} on BNB Chain. "
            f"Also check if the 2x first-stake acceleration is active for that address."
        )
    else:
        await _run_agent(update, context,
            "Fetch the agent's current wallet balances. Show BNB, BEAT, veBEAT, "
            "and whether the 2x first-stake acceleration is active. "
            "Mention that users can check their own balance with /wallet 0x...theiraddress"
        )


async def cmd_onboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _run_agent(update, context,
        "A new user wants to understand how Audiera Beatvote works. "
        "Explain staking, veBEAT, voting, and earning in plain language with no jargon. "
        "Mention the 2x first-time bonus and the weekly 5000 BEAT reward pool. "
        "End with a simple action checklist."
    )


async def cmd_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any plain text message as a chat with the agent."""
    message = update.message.text
    if not message:
        return
    await _run_agent(update, context, message)


# ─────────────────────────────────────────────────────────────────────────────
# Bot setup and run
# ─────────────────────────────────────────────────────────────────────────────

async def post_commands(app: Application):
    await app.bot.set_my_commands([
        BotCommand("analyze",  "Ranked Beatvote predictions"),
        BotCommand("vote",     "Stake and cast on-chain votes"),
        BotCommand("earn",     "Claim weekly rewards"),
        BotCommand("loop",     "Full weekly Create→Participate→Earn loop"),
        BotCommand("wallet",   "Check wallet balances"),
        BotCommand("onboard",  "How staking and voting works"),
        BotCommand("help",     "List all commands"),
    ])


async def main():
    if not config.TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN not set in .env — exiting")
        sys.exit(1)

    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_commands)
        .build()
    )

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("vote",    cmd_vote))
    app.add_handler(CommandHandler("earn",    cmd_earn))
    app.add_handler(CommandHandler("loop",    cmd_loop))
    app.add_handler(CommandHandler("wallet",  cmd_wallet))
    app.add_handler(CommandHandler("onboard", cmd_onboard))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, cmd_message))

    print("VoteWhisperer Telegram bot starting...")
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        print("Bot is running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
