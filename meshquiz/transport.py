"""Transport abstraction.

The game engine never talks to the mesh directly. It talks to a ``Transport``. This lets
us run a full game against an in-memory ``MockTransport`` in tests, with no live mesh.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class MeshMessage:
    """A normalized message as seen on a channel.

    A *reaction* (tapback) is a message with ``is_reaction == True``; its ``reply_to`` is
    the packet id of the message being reacted to, and ``text`` is the emoji character.
    A *plain* message has ``is_reaction == False``.
    """

    packet_id: int          # the Meshtastic packet id of THIS message
    from_node_id: str       # reactor / sender hex id, e.g. "!a1b2c3d4"
    text: str               # message text or emoji char
    channel: int
    timestamp_ms: int
    reply_to: Optional[int] = None   # packet id this message replies/reacts to
    is_reaction: bool = False


class Transport(ABC):
    """Interface every transport must implement."""

    @abstractmethod
    def send_message(self, text: str, channel: int) -> int:
        """Send ``text`` to ``channel``. Return the packet id of the sent message.

        Implementations MUST keep the message a single packet (caller guarantees the
        text is within the byte budget).
        """

    @abstractmethod
    def fetch_messages(self, channel: int, since_ms: int, limit: int = 200) -> List[MeshMessage]:
        """Return messages on ``channel`` with ``timestamp_ms >= since_ms``, oldest first."""

    @abstractmethod
    def list_node_names(self) -> dict:
        """Return {hex_node_id: long_name} for known nodes (best-effort, may be partial)."""
