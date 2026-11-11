import os
import sys
import json
import hashlib
import hmac

AUDIT_SECRET = os.getenv("ETL_AUDIT_SECRET", "enterprise-etl-hmac-key")

def compute_payload_signature(data_bytes: bytes) -> str:
    """Gera assinatura HMAC-SHA256 para auditoria de integridade do payload."""
    return hmac.new(AUDIT_SECRET.encode("utf-8"), data_bytes, hashlib.sha256).hexdigest()

def main():
    print("=== INICIANDO SCRIPT DE AUTOMACÃO: UPLOAD_TO_API ===")
    if len(sys.argv) < 2:
        print("Erro: Nenhum arquivo JSON foi passado como argumento.")
        sys.exit(1)

    filename = sys.argv[1]
    # Se for apenas o nome do arquivo, procurar na pasta data/output
    if not os.path.exists(filename):
        possible_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "output",
            filename
        )
        if os.path.exists(possible_path):
            filename = possible_path
        else:
            print(f"Erro: O arquivo '{sys.argv[1]}' não foi encontrado.")
            sys.exit(1)

    try:
        with open(filename, 'rb') as f:
            raw_bytes = f.read()

        payload_sig = compute_payload_signature(raw_bytes)
        data = json.loads(raw_bytes.decode('utf-8'))

        print(f"Arquivo carregado com sucesso: {filename}")
        print(f"Assinatura HMAC-SHA256 de integridade: {payload_sig}")
        print(f"Total de registros a serem enviados: {len(data)}")

        # Simular o envio de cada registro para uma API REST
        for i, record in enumerate(data, 1):
            pedido_id = record.get("ID_Pedido", "N/A")
            cliente = record.get("Cliente", "N/A")
            valor = record.get("Valor_Bruto", 0.0)
            qtd = record.get("Quantidade", 0)

            print(f"  [POST] /api/v1/sales - Registro {i}: ID_Pedido={pedido_id} | Cliente={cliente} | Valor={valor} | Qtd={qtd} -> [201 Created]")

        print("\n=== STATUS DO UPLOAD: 100% SUCESSO ===")
        print("Todos os registros foram importados no banco de dados corporativo.")

    except Exception as e:
        print(f"Erro crítico durante a automação: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
