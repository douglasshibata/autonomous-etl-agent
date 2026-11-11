from pathlib import Path
from typing import Tuple, Dict, Any
from src.core.sandbox import IsolatedDataEngine

class DataTransformer:
    """Gerencia aplicação transacional de transformações com engine isolada e snapshots."""

    def __init__(self, memory_limit_mb: int = 512):
        self.engine = IsolatedDataEngine(memory_limit_mb=memory_limit_mb)

    def apply_transformation(
        self,
        code_str: str,
        current_parquet: Path,
        output_parquet: Path
    ) -> Tuple[bool, str, Dict[str, Any]]:
        return self.engine.execute_transform(
            code_str=code_str,
            current_parquet=current_parquet,
            output_parquet=output_parquet
        )
