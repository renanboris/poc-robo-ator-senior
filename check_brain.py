import sqlite3
conn = sqlite3.connect('brain.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("""
    SELECT intencao, seletor, hits, falhas_consecutivas, hitl_corrigido, ultima_atualizacao
    FROM memoria_semantica
    WHERE hitl_corrigido = 1
    ORDER BY ultima_atualizacao DESC
    LIMIT 5
""").fetchall()
for r in rows:
    print(f"intencao:       {r['intencao'][:70]}")
    print(f"seletor:        {r['seletor']}")
    print(f"hits:           {r['hits']}")
    print(f"falhas:         {r['falhas_consecutivas']}")
    print(f"hitl_corrigido: {r['hitl_corrigido']}")
    print(f"atualizado:     {r['ultima_atualizacao']}")
    print("---")
print(f"\nTotal de memorias HITL-corrigidas: {conn.execute('SELECT COUNT(*) FROM memoria_semantica WHERE hitl_corrigido=1').fetchone()[0]}")
conn.close()
