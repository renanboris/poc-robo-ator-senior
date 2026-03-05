from google import genai

client = genai.Client(api_key="AIzaSyBcfTwLZeC50dDUuYZDgzxS2Dlto5v6JGs")

for m in client.models.list():
    print(m.name)


from pinecone import Pinecone
import os

pc = Pinecone(api_key="pcsk_6H489E_Rkmse6WFhFicxEYwXceQbfKjwrcNokgV5n6vybSFk5ugydrySrHY9Yjb7kUUkCP")

print(pc.list_indexes())

from pinecone import Pinecone

pc = Pinecone(api_key="pcsk_6H489E_Rkmse6WFhFicxEYwXceQbfKjwrcNokgV5n6vybSFk5ugydrySrHY9Yjb7kUUkCP")
print("Import funcionando")