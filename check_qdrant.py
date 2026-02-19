"""Check Qdrant collection status"""
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()

client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

print("=" * 60)
print("Qdrant Collections Status")
print("=" * 60)

# List all collections
collections = client.get_collections().collections
print(f"\nAvailable collections: {[c.name for c in collections]}")

# Check expected collection
expected = os.getenv("COLLECTION_NAME")
print(f"\nExpected collection name: {expected}")

if any(c.name == expected for c in collections):
    count = client.count(collection_name=expected, exact=True).count
    print(f"✓ Collection '{expected}' exists with {count} points")
    
    if count == 0:
        print("\n⚠️  WARNING: Collection is empty!")
        print("   Run: python ingest_qdrant.py --recreate")
else:
    print(f"\n✗ Collection '{expected}' NOT FOUND!")
    print("\nAvailable collections:")
    for c in collections:
        count = client.count(collection_name=c.name, exact=True).count
        print(f"  - {c.name}: {count} points")
    print("\nFix: Update COLLECTION_NAME in .env to match an existing collection")
    print("Or run: python ingest_qdrant.py --recreate")

print("=" * 60)
