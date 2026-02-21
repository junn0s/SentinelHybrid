import logging

from src.edge.config import EdgeConfig
from src.edge.orchestrator import EdgeOrchestrator


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def run() -> None:
    cfg = EdgeConfig.from_env()
    _setup_logging(cfg.log_level)
    orchestrator = EdgeOrchestrator(cfg=cfg)
    orchestrator.run()


if __name__ == "__main__":
    run()
