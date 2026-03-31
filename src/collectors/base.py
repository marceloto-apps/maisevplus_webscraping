from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from enum import Enum

class CollectStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"

@dataclass
class CollectResult:
    source: str
    job_type: str
    job_id: str
    status: CollectStatus
    started_at: datetime
    finished_at: datetime
    records: List[Dict[str, Any]]
    records_collected: int = 0
    records_new: int = 0
    records_skipped: int = 0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

class BaseCollector(ABC):
    def __init__(self, source_name: str):
        self.source_name = source_name

    @abstractmethod
    async def collect(self, **kwargs) -> CollectResult:
        """
        Método principal de coleta. Deve ser implementado por cada collector.
        Retorna um CollectResult padronizado.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verifica se a fonte de dados está acessível/operante.
        """
        pass

    def generate_job_id(self, job_type: str) -> str:
        """Gera um ID único para a execução do job"""
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        return f"{self.source_name}_{job_type}_{timestamp}"
