import sys
import os
import uuid
import json
import argparse
import logging
from pathlib import Path
from typing import Optional

# Garantir PYTHONPATH correto
base_dir = Path(__file__).resolve().parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from config.settings import settings
from src.core.state import ETLState
from src.graph.builder import build_etl_graph
from src.tools.runner import SafeSubprocessRunner

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("AutonomousETLAgent")

def run_pipeline(
    input_file: Path,
    session_id: Optional[str] = None,
    max_retries: int = 3,
    dispatch_script: Optional[str] = None,
    dispatch_args: Optional[list] = None
) -> dict:
    sess_id = session_id or str(uuid.uuid4())
    session_dir = settings.sessions_root_dir / sess_id
    session_dir.mkdir(parents=True, exist_ok=True)

    input_path = Path(input_file).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Arquivo de entrada não encontrado: {input_path}")

    logger.info(f"Iniciando sessão isolada ETL: {sess_id} em {session_dir}")

    # Copiar arquivo de entrada para a sessão isolada
    staged_input = session_dir / input_path.name
    with open(input_path, "rb") as f_in, open(staged_input, "wb") as f_out:
        f_out.write(f_in.read())

    initial_state: ETLState = {
        "session_id": sess_id,
        "input_file_path": str(staged_input),
        "current_checkpoint_path": str(staged_input),
        "data_profile": None,
        "transformation_history": [],
        "last_error": None,
        "retry_count": 0,
        "max_retries": max_retries,
        "exported_artifacts": {},
        "messages": [],
        "execution_complete": False
    }

    graph = build_etl_graph()
    final_state = graph.invoke(initial_state)

    # Disparar script de automação secundário se solicitado
    dispatch_result = None
    if dispatch_script:
        logger.info(f"Disparando script de automação: {dispatch_script}")
        runner = SafeSubprocessRunner(
            allowed_directory=base_dir / "scripts",
            timeout_seconds=settings.subprocess_timeout_seconds
        )

        args = dispatch_args or []
        # Se nenhum argumento passado, passar o JSON exportado se existir
        if not args and "json" in final_state.get("exported_artifacts", {}):
            args = [final_state["exported_artifacts"]["json"]]

        ret_code, stdout, stderr = runner.run_script(dispatch_script, args)
        dispatch_result = {
            "script": dispatch_script,
            "returncode": ret_code,
            "stdout": stdout,
            "stderr": stderr
        }

    # Gerar log de auditoria estruturado em JSON
    audit_trail = {
        "session_id": sess_id,
        "input_file": str(input_path),
        "execution_complete": final_state.get("execution_complete", False),
        "total_transformations": len(final_state.get("transformation_history", [])),
        "retry_count": final_state.get("retry_count", 0),
        "last_error": final_state.get("last_error"),
        "exported_artifacts": final_state.get("exported_artifacts", {}),
        "dispatch_result": dispatch_result
    }

    audit_path = session_dir / "audit_trail.json"
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audit_trail, f, indent=2)

    logger.info(f"Trilha de auditoria gerada com sucesso em: {audit_path}")
    return audit_trail


def main():
    parser = argparse.ArgumentParser(description="Autonomous ETL Agent Platform CLI")
    parser.add_argument("--input", "-i", type=str, required=True, help="Caminho do arquivo de dados (.csv, .xlsx, .parquet)")
    parser.add_argument("--session", "-s", type=str, default=None, help="ID de sessão customizado (UUID)")
    parser.add_argument("--retries", "-r", type=int, default=3, help="Tentativas máximas de autorreparo")
    parser.add_argument("--dispatch", "-d", type=str, default=None, help="Nome do script para despachar (ex: upload_to_api.py)")
    parser.add_argument("--dispatch-args", nargs="*", default=None, help="Argumentos para o script despachado")

    args = parser.parse_args()

    try:
        trail = run_pipeline(
            input_file=Path(args.input),
            session_id=args.session,
            max_retries=args.retries,
            dispatch_script=args.dispatch,
            dispatch_args=args.dispatch_args
        )
        print("\n" + "="*50)
        print("PIPELINE ETL CONCLUÍDO COM SUCESSO!")
        print(f"Sessão: {trail['session_id']}")
        print(f"Artefatos gerados:")
        for fmt, path in trail['exported_artifacts'].items():
            print(f" - {fmt.upper()}: {path}")
        if trail.get("dispatch_result"):
            print(f"Script despachado status: {trail['dispatch_result']['returncode']}")
        print("="*50)
    except Exception as e:
        logger.error(f"Erro fatal durante execução do pipeline: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
