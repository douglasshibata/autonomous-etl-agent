from typing import Annotated, Sequence, TypedDict, Optional, List, Dict, Any
from langchain_core.messages import BaseMessage
import operator

class DataProfile(TypedDict):
    total_rows: int
    total_columns: int
    columns: Dict[str, str]  # Coluna -> Dtype
    missing_percentages: Dict[str, float]
    sample_data: List[Dict[str, Any]]
    inconsistencies_detected: List[str]

class ETLState(TypedDict):
    session_id: str
    input_file_path: str
    current_checkpoint_path: str  # Caminho para o .parquet atual
    data_profile: Optional[DataProfile]
    transformation_history: List[str]  # Código executado com sucesso
    last_error: Optional[str]          # Se houver erro, alimenta o reflection
    retry_count: int                   # Limite de tentativas de autorreparo
    max_retries: int
    exported_artifacts: Dict[str, str] # Formato -> Caminho
    messages: Annotated[Sequence[BaseMessage], operator.add]
    execution_complete: bool
