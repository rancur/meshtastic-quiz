#!/usr/bin/env python3
"""Patch meshtastic-quiz so sends are scoped to a specific MeshMonitor source.

Without this, meshquiz POSTs to the UNSCOPED /api/v1/messages, which
resolveSourceManager() resolves to the primary source (the physical radio).
The post succeeds with 201 and no error but goes on air under the WRONG node
identity. Uses the path-scoped route (/api/v1/sources/<id>/messages) rather
than body.sourceId so the scope is unambiguous.
"""
import io, sys, os

ROOT = "/home/rak/meshtastic-quiz"

def patch(path, old, new, label):
    p = os.path.join(ROOT, path)
    s = io.open(p, encoding="utf-8").read()
    if new in s:
        print(f"SKIP (already applied): {label}")
        return
    if old not in s:
        print(f"FAIL (anchor not found): {label}")
        sys.exit(1)
    if s.count(old) != 1:
        print(f"FAIL (anchor not unique, {s.count(old)}x): {label}")
        sys.exit(1)
    io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
    print(f"OK: {label}")

# --- 1. config.py: new send_source_id field -------------------------------
patch(
    "meshquiz/config.py",
    '    source_id: str = field(default_factory=lambda: _env("MESHMONITOR_SOURCE_ID", ""))\n',
    '    source_id: str = field(default_factory=lambda: _env("MESHMONITOR_SOURCE_ID", ""))\n'
    '    # IDENTITY SCOPE FOR SENDS. On a multi-source MeshMonitor the UNSCOPED\n'
    '    # POST /api/v1/messages resolves to the PRIMARY source (the physical radio),\n'
    '    # returning 201 with no error while transmitting under the wrong node id.\n'
    '    # Set this to the source id of the identity this bot must post as (e.g. the\n'
    '    # Buzz Trivia virtual node). Blank = legacy unscoped behaviour.\n'
    '    send_source_id: str = field(default_factory=lambda: _env("MESHMONITOR_SEND_SOURCE_ID", ""))\n',
    "config.py send_source_id field",
)

# --- 2. meshmonitor.py: ctor arg ------------------------------------------
patch(
    "meshquiz/meshmonitor.py",
    "    def __init__(self, base_url: str, token: str, timeout_s: float = 15.0,\n"
    "                 source_id: str = \"\", session: Optional[requests.Session] = None):\n",
    "    def __init__(self, base_url: str, token: str, timeout_s: float = 15.0,\n"
    "                 source_id: str = \"\", session: Optional[requests.Session] = None,\n"
    "                 send_source_id: str = \"\"):\n",
    "meshmonitor.py __init__ signature",
)
patch(
    "meshquiz/meshmonitor.py",
    "        self._source_id = source_id or None\n",
    "        self._source_id = source_id or None\n"
    "        self._send_source_id = send_source_id or None\n",
    "meshmonitor.py __init__ body",
)

# --- 3. meshmonitor.py: scoped send ---------------------------------------
patch(
    "meshquiz/meshmonitor.py",
    "    def send_message(self, text: str, channel: int) -> int:\n"
    "        r = self.s.post(f\"{self.api}/messages\",\n"
    "                        json={\"text\": text, \"channel\": channel},\n"
    "                        timeout=self.timeout)\n",
    "    def send_message(self, text: str, channel: int) -> int:\n"
    "        # IDENTITY SCOPE: post to the path-scoped source route when configured.\n"
    "        # The unscoped /api/v1/messages silently falls back to MeshMonitor's\n"
    "        # PRIMARY source (the physical radio) -> wrong sender on air, 201 and no\n"
    "        # error. Path scope beats body.sourceId: it cannot be ignored.\n"
    "        url = (f\"{self.api}/sources/{self._send_source_id}/messages\"\n"
    "               if self._send_source_id else f\"{self.api}/messages\")\n"
    "        r = self.s.post(url,\n"
    "                        json={\"text\": text, \"channel\": channel},\n"
    "                        timeout=self.timeout)\n",
    "meshmonitor.py send_message path scope",
)

# --- 4. __main__.py: wire it through --------------------------------------
patch(
    "meshquiz/__main__.py",
    "        source_id=cfg.source_id,\n    )\n",
    "        source_id=cfg.source_id,\n        send_source_id=cfg.send_source_id,\n    )\n",
    "__main__.py wiring",
)

print("PATCH COMPLETE")
