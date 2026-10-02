"""应用上下文：把配置、数据库、记录引擎和 API 服务串起来。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .agent_api import AgentAPI
from .config import Config
from .db import Database
from .recorder import RecorderEngine


@dataclass
class AppContext:
    cfg: Config
    db: Database
    engine: RecorderEngine
    api: AgentAPI | None = None
    extra: dict = field(default_factory=dict)
