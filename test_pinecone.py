import sys

import dap_engine

# Ensure utf-8 output for emojis in console
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def testar():
    q = sys.argv[1] if len(sys.argv) > 1 else 'O que é a admissão no HCM?'
    print(f"\n--- BUSCANDO NO PINECONE: '{q}' ---")

    try:
        res = dap_engine.buscar_contexto_multi_namespace(q)
        if res:
            print("\n[SUCESSO] INFORMACOES ENCONTRADAS:")
            print("Namespace:", res.get('namespace'))
            print("Score (Confianca):", res.get('score'))
            print("Titulo:", res.get('titulo'))
            print("URL:", res.get('url'))
            print("-" * 60)
            texto = res.get('texto_rag', '')
            try:
                print(texto)
            except UnicodeEncodeError:
                print(texto.encode('utf-8', 'ignore').decode('utf-8'))
        else:
            print("\n[FALHA] NENHUMA INFORMACAO ENCONTRADA PARA ESTA PERGUNTA.")
            print("O Pinecone nao retornou resultados com score minimo (0.45).")
    except Exception as e:
        print(f"\nErro ao buscar no Pinecone: {e}")

if __name__ == "__main__":
    testar()
