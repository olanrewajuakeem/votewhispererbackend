"""Pydantic request/response schemas for the VoteWhisperer API."""

from typing import Any
from pydantic import BaseModel, Field


# ── Requests ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message to the agent")

class AnalyzeRequest(BaseModel):
    pass  # no params — songs always come from Beatvote contract

class VoteRequest(BaseModel):
    auto: bool = Field(True, description="Let the agent decide which songs to vote on")
    songs: list[dict] | None = Field(None, description="Manual override: [{song_id, song_name, weight}]")

class StakeRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount of BEAT to stake")

class OnboardRequest(BaseModel):
    level: str = Field("complete_beginner",
                       description="complete_beginner | crypto_curious | defi_familiar")

class LyricsRequest(BaseModel):
    theme: str = Field(..., description="Theme or inspiration for the lyrics")
    styles: list[str] = Field(["Dance", "Electronic"], description="Music styles (max 3)")

class MusicRequest(BaseModel):
    styles: list[str] = Field(["Dance", "Electronic"], description="Music styles (max 3)")
    artist_id: str    = Field("default", description="Audiera artist ID")
    lyrics: str | None = Field(None, description="Lyrics text (optional)")
    inspiration: str | None = Field(None, description="Inspiration prompt (optional)")


# ── Responses ─────────────────────────────────────────────────────────────────

class AgentResponse(BaseModel):
    status: str
    message: str
    data: dict | None = None

class SongsResponse(BaseModel):
    status: str
    week: int | None = None
    songs: list[dict]
    total: int

class WalletResponse(BaseModel):
    status: str
    address: str
    bnb_balance: float
    beat_balance: float
    vebeat_balance: float
    first_stake_acceleration_active: bool
    mode: str = "live"

class StatusResponse(BaseModel):
    agent: str
    mode: str
    wallet: dict
    state: dict
    contracts: dict
