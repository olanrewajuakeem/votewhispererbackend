# VoteWhisperer

Autonomous AI agent for Audiera Beatvote. Analyzes the weekly music chart, stakes $BEAT, casts on-chain votes, and earns from the 5,000 BEAT weekly reward pool — all autonomously on BNB Chain.

Built for the Audiera Agent-Native Contest 2026.

---

## What it does

VoteWhisperer runs the full Create → Participate → Earn loop every week:

1. **Create** — generates original AI music via Audiera's Lyrics and Music Skill APIs
2. **Analyze** — fetches the live Audiera leaderboard, scores every song by play count, likes, engagement velocity, and trend signals, then ranks them with confidence scores
3. **Stake** — stakes $BEAT to acquire veBEAT voting power (optimizes for the 2x first-time bonus window)
4. **Vote** — casts weighted on-chain votes on the highest-signal tracks via the Beatvote contract on BSC
5. **Earn** — claims the weekly voter rewards from the shared 5,000 BEAT pool
6. **Compound** — restakes 80% of rewards to grow voting power for the next week
7. **Onboard** — explains the full system in plain English for Web2 users new to crypto

The agent runs its own wallet. Every transaction is real, verifiable on BSCScan, and fully autonomous.

---

## Live demo

- **API**: https://votewhispererbackend.onrender.com/docs
- **Frontend**: https://votewhisperer.vercel.app
- **Telegram**: @VoteWhispererBot

---

## Stack

- Python 3.11+
- FastAPI — REST API backend
- Claude claude-sonnet-4-6 — agent brain via tool-use loop
- Audiera API — lyrics generation, music generation, weekly leaderboard, chain stats
- web3.py — BNB Chain interactions (staking, voting, reward claiming)
- python-telegram-bot — Telegram bot interface

---

## Contracts (BNB Chain)

| Contract | Address |
|----------|---------|
| BEAT Token | `0xcf3232b85b43bca90e51d38cc06cc8bb8c8a3e36` |
| Voting | `0xe554229ba6ec7ceeacd13a9bb48d812bf705c292` |
| Staking | `0x0d956565253b74b84c4daa51e026bbb4c215020e` |

---

## Setup

**1. Clone the repo**
```
git clone https://github.com/olanrewajuakeem/votewhispererbackend.git
cd votewhispererbackend
```

**2. Install dependencies**
```
pip install -r requirements.txt
```

**3. Configure environment**
```
cp .env.example .env
```

Edit `.env` and fill in your keys:

```
ANTHROPIC_API_KEY=        # Claude API key — console.anthropic.com
AUDIERA_API_KEY=          # Audiera API key
AUDIERA_ARTIST_ID=        # Your Audiera artist ID
WALLET_PRIVATE_KEY=       # BNB Chain wallet private key
WALLET_ADDRESS=           # BNB Chain wallet address
TELEGRAM_BOT_TOKEN=       # Telegram bot token from @BotFather
```

The contract addresses and RPC URL are pre-filled in `.env.example`. Do not change them.

**4. Run the API**
```
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at `http://localhost:8000/docs`

**5. Run the Telegram bot**
```
python telegram_bot.py
```

---

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/status` | Agent status, wallet, last action |
| GET | `/leaderboard` | Live Audiera weekly leaderboard |
| GET | `/chain-stats` | Platform stats — users, BEAT burned |
| POST | `/agent/analyze` | Claude analyzes and ranks this week's songs |
| POST | `/agent/vote` | Full stake + analyze + vote cycle |
| POST | `/agent/earn` | Claim rewards + restake |
| POST | `/agent/loop` | Full weekly Create→Participate→Earn loop |
| POST | `/agent/chat` | Chat with the agent |
| POST | `/agent/onboard` | Web2→Web3 onboarding guide |
| POST | `/connect` | Connect a wallet address (read-only balance check) |
| GET | `/wallet` | Live wallet balances |
| POST | `/lyrics` | Generate song lyrics via Audiera |
| POST | `/music` | Generate a full song via Audiera |

---

## Telegram bot commands

```
/analyze  — ranked Beatvote predictions with confidence scores
/vote     — stake BEAT and cast weighted on-chain votes
/earn     — claim weekly rewards and restake
/loop     — full weekly Create→Participate→Earn loop
/wallet   — check agent wallet balances
/onboard  — plain English guide to staking and voting
```

---

## How users interact with it

VoteWhisperer is not a user wallet app. It is a live autonomous agent with its own wallet and on-chain position.

Users come to VoteWhisperer for two things:

**Intelligence** — see which songs the agent is backing this week, the confidence scores, and the reasoning behind each pick. Use those signals to vote smarter on Audiera with their own BEAT.

**Education** — ask the agent anything about staking, veBEAT, the reward pool, or how Beatvote works. The agent explains everything in plain English with no crypto jargon.

Users can also paste their own wallet address into the connect field to see their personal BEAT, veBEAT, and BNB balances without leaving the app.

---

## Audiera Agent-Native Contest 2026

This project was built for the Audiera Agent-Native Contest. The contest challenges developers to build autonomous agents that participate in the Audiera ecosystem using the platform's own agent skill APIs.

VoteWhisperer demonstrates the full Create → Participate → Earn loop:
- Creates original music using Audiera's Lyrics and Music Skill APIs
- Participates in Beatvote governance with real on-chain votes
- Earns from the weekly 5,000 BEAT voter reward pool

#AudieraAI #BEAT #BinanceAI
