"""In-memory mesh for testing — implements Transport with zero network."""
from __future__ import annotations

import itertools
from typing import List

from meshquiz.transport import MeshMessage, Transport


class MockTransport(Transport):
    def __init__(self, node_names=None):
        self.sent: List[MeshMessage] = []     # messages the bot sent
        self.inbox: List[MeshMessage] = []     # all messages "on the channel"
        self._ids = itertools.count(1000)
        self._clock_ms = 0
        self.node_names = node_names or {}

    def set_clock_ms(self, ms: int):
        self._clock_ms = ms

    # --- Transport API ---
    def send_message(self, text: str, channel: int) -> int:
        pkt = next(self._ids)
        m = MeshMessage(packet_id=pkt, from_node_id="!bot00000", text=text,
                        channel=channel, timestamp_ms=self._clock_ms, is_reaction=False)
        self.sent.append(m)
        self.inbox.append(m)
        return pkt

    def fetch_messages(self, channel: int, since_ms: int, limit: int = 200) -> List[MeshMessage]:
        return [m for m in self.inbox
                if m.channel == channel and m.timestamp_ms >= since_ms][:limit]

    def list_node_names(self) -> dict:
        return dict(self.node_names)

    # --- test helpers: inject inbound traffic ---
    def inject_text(self, from_node_id: str, text: str, channel: int, ts_ms: int) -> int:
        pkt = next(self._ids)
        self.inbox.append(MeshMessage(packet_id=pkt, from_node_id=from_node_id, text=text,
                                      channel=channel, timestamp_ms=ts_ms, is_reaction=False))
        return pkt

    def inject_reaction(self, from_node_id: str, emoji: str, reply_to: int,
                        channel: int, ts_ms: int) -> int:
        pkt = next(self._ids)
        self.inbox.append(MeshMessage(packet_id=pkt, from_node_id=from_node_id, text=emoji,
                                      channel=channel, timestamp_ms=ts_ms,
                                      reply_to=reply_to, is_reaction=True))
        return pkt
