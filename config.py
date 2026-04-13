import os
from dotenv import load_dotenv

load_dotenv()

# ── Claude API ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# ── Audiera API ──────────────────────────────────────────────────────────────
AUDIERA_API_KEY: str    = os.getenv("AUDIERA_API_KEY", "")
AUDIERA_ARTIST_ID: str  = os.getenv("AUDIERA_ARTIST_ID", "")  # your artist ID from Audiera profile

# ── Telegram Bot (optional) ──────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ── X / Twitter (optional — only needed for posting tweets) ─────────────────
X_API_KEY: str = os.getenv("X_API_KEY", "")
X_API_SECRET: str = os.getenv("X_API_SECRET", "")
X_ACCESS_TOKEN: str = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_TOKEN_SECRET: str = os.getenv("X_ACCESS_TOKEN_SECRET", "")
X_BEARER_TOKEN: str = os.getenv("X_BEARER_TOKEN", "")

# ── Wallet ───────────────────────────────────────────────────────────────────
WALLET_PRIVATE_KEY: str = os.getenv("WALLET_PRIVATE_KEY", "")
WALLET_ADDRESS: str = os.getenv("WALLET_ADDRESS", "")

# ── BNB Chain ────────────────────────────────────────────────────────────────
BSC_RPC_URL: str = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")
BSC_CHAIN_ID: int = 56

# ── Audiera Contracts (real, verified on BSC) ────────────────────────────────
BEAT_TOKEN_ADDRESS: str    = "0xcf3232b85b43bca90e51d38cc06cc8bb8c8a3e36"
VOTING_CONTRACT_ADDRESS: str  = os.getenv(
    "VOTING_CONTRACT_ADDRESS", "0xe554229ba6ec7ceeacd13a9bb48d812bf705c292"
)
STAKING_CONTRACT_ADDRESS: str = os.getenv(
    "STAKING_CONTRACT_ADDRESS", "0x0d956565253b74b84c4daa51e026bbb4c215020e"
)

# ── Audiera URLs ─────────────────────────────────────────────────────────────
AUDIERA_STAKE_URL: str     = "https://audiera.fi/stake"
AUDIERA_BEATVOTE_URL: str  = "https://ai.audiera.fi/"
AUDIERA_API_BASE: str      = "https://ai.audiera.fi/api"
AUDIERA_X_HANDLE: str      = "@Audiera_web3"

# ── Agent config ─────────────────────────────────────────────────────────────
MOCK_MODE: bool = os.getenv("MOCK_MODE", "true").lower() == "true"
AGENT_NAME: str = "VoteWhisperer"
MODEL: str      = "claude-sonnet-4-6"
STATE_FILE: str = "data/state.json"

# ── FastAPI ───────────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))

# ── Prediction score weights (tune these) ────────────────────────────────────
SCORE_WEIGHTS = {
    "vote_count":      0.40,   # on-chain votes already cast this week
    "dance_potential": 0.25,   # BPM / dance-mat keyword signals
    "meme_energy":     0.20,   # viral / trend language signals
    "recency":         0.05,   # how recently the song was submitted
    "past_performance":0.10,   # previous Beatvote chart history
}

# Weekly voter reward pool cap
WEEKLY_REWARD_POOL: int = 5_000  # BEAT
