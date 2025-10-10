# quick_check.py
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

uri = os.getenv("MONGO_URI")
if not uri:
    raise SystemExit("MONGO_URI not set. Put it in your .env")

client = MongoClient(uri, serverSelectionTimeoutMS=20000)

try:
    print("Ping:", client.admin.command("ping"))
    print("DBs:", client.list_database_names())
except Exception as e:
    raise SystemExit(f"Connection failed: {e}")
finally:
    client.close()
