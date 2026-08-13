"""Frozen, domain-separated SHA-256 seed hierarchy."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .errors import ContractError

MASTER_SEED = 6001412985720209409
MASTER_SEED_HEX = "0x53494D504C450001"
DOMAIN = "simple-synthetic-eeg-generator/v1"


@dataclass(frozen=True)
class DerivedSeed:
    subject_id: str
    stream: str
    sha256: str
    seed128: int
    seed32: int


STREAMS = frozenset(
    {
        "background",
        "chi",
        "sigma",
        "response_scale",
        "response_latency",
        "response_width",
        "burst_amplitude",
        "burst_frequency",
        "burst_phase",
    }
)


def derive_seed(subject_id: str, stream: str) -> DerivedSeed:
    """Derive one seed exactly as documented in README.md."""

    if len(subject_id) != 3 or not subject_id.isascii() or not subject_id.isdigit():
        raise ContractError("subject_id must be exactly three ASCII digits")
    if stream not in STREAMS:
        raise ContractError(f"stream must be one of the frozen names, got {stream!r}")
    canonical = (
        f"{DOMAIN}\n"
        f"master={MASTER_SEED}\n"
        f"subject={subject_id}\n"
        f"stream={stream}\n"
    )
    payload = canonical.encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return DerivedSeed(
        subject_id=subject_id,
        stream=stream,
        sha256=digest.hex(),
        seed128=int.from_bytes(digest[:16], "big", signed=False),
        seed32=int.from_bytes(digest[:4], "big", signed=False),
    )
