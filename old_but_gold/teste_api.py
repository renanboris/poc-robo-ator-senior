from google import genai

client = genai.Client(api_key="xxx")

for m in client.models.list():
    print(m.name)


from pinecone import Pinecone
import os

pc = Pinecone(api_key="xxx")

print(pc.list_indexes())

from pinecone import Pinecone

pc = Pinecone(api_key="xxx")
print("Import funcionando")