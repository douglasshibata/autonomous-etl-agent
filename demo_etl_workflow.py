import os
import sys
import logging
import pandas as pd
import numpy as np

# Configurar sys.path para garantir que os módulos locais sejam importados corretamente
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, "tools"))

# Configurar logging detalhado para o console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ETL_Demo_Workflow")

from agent_orchestrator import get_agent

def generate_dirty_dataset():
    """
    Gera um conjunto de dados de vendas intencionalmente sujo
    e o salva no formato Excel (.xlsx) na pasta data/input.
    """
    logger.info("Gerando dataset de vendas 'sujo' para demonstração...")

    input_dir = os.path.join(current_dir, "data", "input")
    os.makedirs(input_dir, exist_ok=True)

    # Dados intencionalmente inconsistentes e sujos
    data = {
        'ID_Pedido': [1001, 1002, np.nan, 1004, 1005], # Linha 3 tem ID nulo (deve ser dropada)
        'Cliente': ['Empresa Alfa Ltda', np.nan, 'Empresa Beta S/A', 'Empresa Gama', 'Empresa Delta'], # Linha 2 tem Cliente nulo (preencher)
        'Valor_Bruto': ['R$ 1.250,50', 'R$ 80,00', 'R$ 3.400,00', 'R$ 450,25', 'R$ 9.999,99'], # Moeda no formato brasileiro
        'Quantidade': ['12', '1', '40', np.nan, '5'] # Quantidade como strings com nulo
    }

    df = pd.DataFrame(data)
    file_path = os.path.join(input_dir, "sales_report_dirty.xlsx")
    df.to_excel(file_path, index=False)

    logger.info(f"Dataset sujo gerado e salvo em: {file_path}")
    return file_path

def main():
    logger.info("=== INICIANDO WORKFLOW DEMONSTRATIVO DO AGENTE DE ETL ===")

    # 1. Gerar planilha suja de exemplo
    dirty_file = generate_dirty_dataset()

    # 2. Instanciar o Agente Orquestrador
    agent = get_agent()

    # 3. Formular a solicitação em linguagem natural (conforme caso de uso prático)
    user_query = (
        f"Limpe os dados nulos, converta a moeda para o formato americano na coluna Valor_Bruto, "
        f"garanta que a quantidade seja inteira, exporte como um arquivo JSON "
        f"e rode o script 'upload_to_api.py' para subir os dados. "
        f"O arquivo original está em '{dirty_file}'."
    )

    logger.info(f"Solicitação do usuário: '{user_query}'")
    logger.info("Executando a orquestração do agente LangGraph...")

    # Executar o grafo do agente
    inputs = {"messages": [("user", user_query)]}

    # Stream events para exibir o raciocínio em tempo real
    final_ai_msg = ""
    try:
        for event in agent.stream(inputs, stream_mode="values"):
            messages = event.get("messages", [])
            if messages:
                last_msg = messages[-1]
                # Exibir as respostas do agente AI
                if last_msg.type == "ai" and last_msg.content:
                    logger.info(f"\n[AGENTE COGNITIVO]: {last_msg.content}\n")
                    final_ai_msg = last_msg.content

                    # Exibir chamadas de ferramentas se houver
                    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                        for tc in last_msg.tool_calls:
                            logger.info(f"👉 [Chamada de Ferramenta]: {tc['name']} com args: {tc['args']}")

                elif last_msg.type == "tool":
                    logger.info(f"⏪ [Retorno da Ferramenta '{last_msg.name}']: {last_msg.content[:400]}...\n")

        print("\n" + "="*60)
        print("🎉 WORKFLOW EXECUTADO COM SUCESSO!")
        print("="*60)
        print(f"Resultado Sintetizado do Agente:\n\n{final_ai_msg}")
        print("="*60)

    except Exception as e:
        logger.error(f"Erro na execução da orquestração: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
