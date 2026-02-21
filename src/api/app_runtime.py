from dataclasses import dataclass
from pathlib import Path

from src.api.config import ApiConfig
from src.api.repositories.event_repository import EventRepository
from src.api.services.mcp_ops import MCPOperationsPublisher
from src.api.services.pipeline import DangerProcessingPipeline


@dataclass
class ApiRuntime:
    config: ApiConfig
    pipeline: DangerProcessingPipeline
    ops_publisher: MCPOperationsPublisher
    repository: EventRepository
    admin_dir: Path
