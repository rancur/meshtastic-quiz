"""Entry point: ``python -m meshquiz``.

Loads config from the environment (see .env.example), constructs the MeshMonitor
transport + bot, and runs the poll loop.
"""
import logging
import os

from .bot import TriviaBot
from .config import Config
from .meshmonitor import MeshMonitorTransport


def main():
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    cfg = Config()
    cfg.validate()
    transport = MeshMonitorTransport(
        base_url=cfg.meshmonitor_url,
        token=cfg.meshmonitor_token,
        timeout_s=cfg.http_timeout_s,
        source_id=cfg.source_id,
    )
    bot = TriviaBot(transport, cfg)
    bot.run()


if __name__ == "__main__":
    main()
