#!/usr/bin/env python3
"""
Quick MongoDB connection test script
"""
import os
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "enatega")
MONGO_COL = os.getenv("MONGO_COL", "chat_sessions")

def test_connection():
    if not MONGO_URI:
        print("❌ MONGO_URI not found in .env file")
        return False
    
    try:
        print(f"🔗 Connecting to MongoDB...")
        client = MongoClient(MONGO_URI)
        
        # Test connection
        client.admin.command('ping')
        print("✅ MongoDB connection successful!")
        
        # Test database access
        db = client[MONGO_DB]
        collection = db[MONGO_COL]
        
        # Insert test document
        test_doc = {
            "session_id": "test_connection",
            "started_at": datetime.now(timezone.utc),
            "messages": [
                {
                    "role": "user",
                    "html": "Test message",
                    "ts": datetime.now(timezone.utc)
                }
            ],
            "test": True
        }
        
        result = collection.insert_one(test_doc)
        print(f"✅ Test document inserted with ID: {result.inserted_id}")
        
        # Count documents
        count = collection.count_documents({})
        print(f"📊 Total documents in collection: {count}")
        
        # Clean up test document
        collection.delete_one({"_id": result.inserted_id})
        print("🧹 Test document cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()