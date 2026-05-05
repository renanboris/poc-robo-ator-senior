import sys

import dap_engine


def testar():
    q = sys.argv[1] if len(sys.argv) > 1 else 'Como criar uma pasta no GED?'
    print(f"\n--- BUSCANDO NO PINECONE: '{q}' ---")

    try:
        res = dap_engine.buscar_contexto(q)
        if res:
            print("\n[SUCESSO] INFORMACOES ENCONTRADAS:")
            print(res.get('texto_rag').encode('utf-8', 'ignore').decode('utf-8'))
            print("\nScore (Confianca):", res.get('score'))
            print("Seletor Direto:", res.get('seletor_direto'))
        else:
            print("\n[FALHA] NENHUMA INFORMACAO ENCONTRADA PARA ESTA PERGUNTA.")
            print("O Pinecone nao retornou resultados com score minimo (0.45).")
    except Exception as e:
        print(f"\nErro ao buscar no Pinecone: {e}")

if __name__ == "__main__":
    testar()
