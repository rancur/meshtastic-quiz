"""MeshMonitor v1 REST transport.

Talks to a MeshMonitor instance (https://github.com/Yeraze/meshmonitor) via its stable
``/api/v1`` API. Verified against MeshMonitor 4.5.x.

Key facts encoded here (see PLAN.md for how they were verified):
- Send:  POST /api/v1/messages {text, channel} -> 201 {data:{requestId, messageId}}
         requestId == the packet id that reactors reference via their replyId.
- Read:  GET /api/v1/messages?channel=N&since=<unix_seconds> -> {data:[...]}
         A reaction row has emoji==1, replyId==<packet id>, text==emoji char,
         fromNodeId==reactor hex.
- Nodes: GET /api/v1/sources/{sourceId}/nodes -> {data:[{nodeId,longName,...}]}
- The message id field is "<source>_<fromNum>_<packetId>" (or "<fromNum>_<packetId>"
  for locally-originated). We extract the trailing integer as the packet id.
"""
from __future__ import annotations

import logging
from typing import List, Optional

import requests

from .transport import MeshMessage, Transport

log = logging.getLogger("meshquiz.meshmonitor")


def _packet_id_from_message_id(message_id: str) -> Optional[int]:
    """Extract the trailing packet id from a MeshMonitor message id string."""
    if message_id is None:
        return None
    tail = str(message_id).rsplit("_", 1)[-1]
    try:
        return int(tail)
    except (TypeError, ValueError):
        return None


class MeshMonitorTransport(Transport):
    def __init__(self, base_url: str, token: str, timeout_s: float = 15.0,
                 source_id: str = "", session: Optional[requests.Session] = None):
        self.base = base_url.rstrip("/")
        self.api = f"{self.base}/api/v1"
        self.token = token
        self.timeout = timeout_s
        self._source_id = source_id or None
        self.s = session or requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}",
                               "Content-Type": "application/json"})

    # ---- helpers ----
    def _resolve_source_id(self) -> Optional[str]:
        if self._source_id:
            return self._source_id
        try:
            r = self.s.get(f"{self.api}/sources", timeout=self.timeout)
            r.raise_for_status()
            data = r.json().get("data", [])
            # prefer the primary source
            for src in data:
                if src.get("isPrimary"):
                    self._source_id = src.get("id")
                    return self._source_id
            if data:
                self._source_id = data[0].get("id")
        except Exception as e:  # pragma: no cover - network failure path
            log.warning("could not resolve source id: %s", e)
        return self._source_id

    # ---- Transport API ----
    def send_message(self, text: str, channel: int) -> int:
        r = self.s.post(f"{self.api}/messages",
                        json={"text": text, "channel": channel},
                        timeout=self.timeout)
        if r.status_code not in (200, 201, 202):
            raise RuntimeError(f"send failed {r.status_code}: {r.text[:200]}")
        body = r.json()
        data = body.get("data", body)
        req = data.get("requestId")
        if req is None:
            req = _packet_id_from_message_id(data.get("messageId", ""))
        if req is None:
            raise RuntimeError(f"send response missing requestId: {body}")
        return int(req)

    def fetch_messages(self, channel: int, since_ms: int, limit: int = 200) -> List[MeshMessage]:
        # The v1 API `since` is unix SECONDS. Floor to seconds and subtract nothing here;
        # the caller manages overlap.
        since_s = int(since_ms // 1000)
        params = {"channel": channel, "since": since_s, "limit": min(limit, 1000)}
        r = self.s.get(f"{self.api}/messages", params=params, timeout=self.timeout)
        r.raise_for_status()
        rows = r.json().get("data", [])
        out: List[MeshMessage] = []
        for row in rows:
            pkt = _packet_id_from_message_id(row.get("id", ""))
            if pkt is None:
                continue
            emoji = row.get("emoji")
            is_reaction = bool(emoji) and emoji not in (0, None)
            ts = row.get("timestamp")
            ts_ms = _to_ms(ts) if ts is not None else (int(row.get("rxTime", 0)) * 1000)
            out.append(MeshMessage(
                packet_id=pkt,
                from_node_id=row.get("fromNodeId", ""),
                text=row.get("text", "") or "",
                channel=row.get("channel", channel),
                timestamp_ms=ts_ms,
                reply_to=row.get("replyId"),
                is_reaction=is_reaction,
            ))
        out.sort(key=lambda m: m.timestamp_ms)
        return out

    def list_node_names(self) -> dict:
        src = self._resolve_source_id()
        names: dict = {}
        try:
            url = f"{self.api}/sources/{src}/nodes" if src else f"{self.api}/nodes"
            r = self.s.get(url, params={"limit": 1000}, timeout=self.timeout)
            r.raise_for_status()
            for n in r.json().get("data", []):
                nid = n.get("nodeId")
                if nid:
                    names[nid] = n.get("longName") or n.get("shortName") or nid
        except Exception as e:  # pragma: no cover
            log.warning("list_node_names failed: %s", e)
        return names


def _to_ms(ts) -> int:
    """Accept ISO-8601 string or epoch (s or ms) and return epoch ms."""
    if isinstance(ts, (int, float)):
        # Heuristic: values < 1e12 are seconds.
        return int(ts if ts > 1e12 else ts * 1000)
    if isinstance(ts, str):
        try:
            from datetime import datetime, timezone
            s = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except ValueError:
            try:
                return int(float(ts))
            except ValueError:
                return 0
    return 0
