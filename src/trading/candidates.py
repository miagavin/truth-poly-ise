"""
Candidate → Polymarket Token ID Registry

Maps candidate names (lowercase) to their YES/NO token IDs on Polymarket.
Used by the trade router to convert Claude's response into executable trades.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateTokens:
    """YES and NO token IDs for a candidate's market."""
    yes: str
    no: str


# Candidate name (lowercase) → Polymarket token IDs
# These are CLOB token IDs for the "Next Fed Chair" market
CANDIDATES: dict[str, CandidateTokens] = {
    "kevin warsh": CandidateTokens(
        yes="51338236787729560681434534660841415073585974762690814047670810862722808070955",
        no="18289842382539867639079362738467334752951741961393928566628307174343542320349",
    ),
    "rick rieder": CandidateTokens(
        yes="16206267440377108972343351482425564384973031696941663558076310969498822538172",
        no="97278843093518170983116788293559302501059038797143772070255096806379425818363",
    ),
    "kevin hassett": CandidateTokens(
        yes="34551606549875928972193520396544368029176529083448203019529657908155427866742",
        no="22802130763821766047382314926654345322953005062130920361011056163048911488589",
    ),
    "christopher waller": CandidateTokens(
        yes="114421380098084026753773605667430150755820287180340356465450569515479471185603",
        no="31167532153450638526564509379216016814499874840833154348394853115050097836415",
    ),
}

# Default trade size in USD
DEFAULT_BUY_AMOUNT = 1000
DEFAULT_NO_AMOUNT = 500