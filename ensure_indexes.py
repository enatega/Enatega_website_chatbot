# ensure_indexes.py
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION = os.getenv("COLLECTION_NAME", "enatega_home")

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Create keyword index for 'domain'
try:
    client.create_payload_index(
        collection_name=COLLECTION,
        field_name="domain",
        field_schema=qm.PayloadSchemaType.KEYWORD,
    )
    print("Created index: domain (KEYWORD)")
except Exception as e:
    print("domain index:", e)

# Create bool index for 'is_active'
try:
    client.create_payload_index(
        collection_name=COLLECTION,
        field_name="is_active",
        field_schema=qm.PayloadSchemaType.BOOL,
    )
    print("Created index: is_active (BOOL)")
except Exception as e:
    print("is_active index:", e)
