#!/usr/bin/env python3
"""
Script to retrieve the last conversation details from MongoDB.
"""

import os
import json
import sys
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List, Tuple
import html

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "enatega")
MONGO_COL = os.getenv("MONGO_COL", "chat_sessions")

if not MONGO_URI:
    print("Error: MONGO_URI environment variable is not set")
    exit(1)


def format_timestamp(ts: Any) -> str:
    """Format timestamp to readable string."""
    if isinstance(ts, datetime):
        return ts.strftime("%Y-%m-%d %H:%M:%S UTC")
    elif isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except:
            return str(ts)
    return str(ts)


def strip_html_tags(html_text: str) -> str:
    """Remove HTML tags from text for cleaner display."""
    import re
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', html_text)
    # Decode HTML entities
    text = html.unescape(text)
    return text.strip()


def get_last_conversation() -> Optional[Dict]:
    """Retrieve the most recent conversation from MongoDB."""
    try:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        collection = db[MONGO_COL]
        
        # Find the most recent conversation (sorted by last_active descending)
        last_session = collection.find_one(
            {},
            sort=[("last_active", -1)]
        )
        
        client.close()
        return last_session
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return None


def extract_all_user_details(session: Dict) -> List[Tuple[str, Dict]]:
    """Extract all user details from session and messages."""
    all_user_details = []
    
    # Session-level user details
    session_user_details = session.get('user_details')
    if session_user_details:
        all_user_details.append(("Session Level", session_user_details))
    
    # Message-level user details
    messages = session.get('messages', [])
    for i, msg in enumerate(messages, 1):
        msg_user_details = msg.get('user_details')
        if msg_user_details:
            all_user_details.append((f"Message {i} ({msg.get('role', 'unknown')})", msg_user_details))
    
    return all_user_details


def display_user_details_only(session: Dict):
    """Display only user details in a clean format."""
    if not session:
        print("No conversation found.")
        return
    
    print("=" * 80)
    print("USER DETAILS - LAST CONVERSATION")
    print("=" * 80)
    print()
    
    print(f"Session ID: {session.get('session_id', 'N/A')}")
    print(f"Last Active: {format_timestamp(session.get('last_active', 'N/A'))}")
    print()
    
    all_user_details = extract_all_user_details(session)
    
    if not all_user_details:
        print("⚠️  No user details found in this conversation.")
        return
    
    for source, user_details in all_user_details:
        print(f"[{source}]")
        print("-" * 80)
        if isinstance(user_details, dict):
            for key, value in user_details.items():
                if isinstance(value, dict):
                    print(f"  {key}:")
                    for sub_key, sub_value in value.items():
                        print(f"    {sub_key}: {sub_value}")
                elif isinstance(value, list):
                    print(f"  {key}: {', '.join(str(v) for v in value)}")
                else:
                    print(f"  {key}: {value}")
        else:
            print(f"  {user_details}")
        print()
    
    print("=" * 80)


def display_conversation(session: Dict):
    """Display conversation details in a readable format."""
    if not session:
        print("No conversation found.")
        return
    
    print("=" * 80)
    print("LAST CONVERSATION DETAILS")
    print("=" * 80)
    print()
    
    # Session metadata
    print(f"Session ID: {session.get('session_id', 'N/A')}")
    print(f"Started At: {format_timestamp(session.get('started_at', 'N/A'))}")
    print(f"Last Active: {format_timestamp(session.get('last_active', 'N/A'))}")
    
    # User details - prominently displayed at the top
    session_user_details = session.get('user_details')
    messages = session.get('messages', [])
    
    # Collect all user details from session and messages
    all_user_details = []
    if session_user_details:
        all_user_details.append(("Session Level", session_user_details))
    
    # Collect user details from messages
    for i, msg in enumerate(messages, 1):
        msg_user_details = msg.get('user_details')
        if msg_user_details:
            all_user_details.append((f"Message {i}", msg_user_details))
    
    # Display user details section prominently
    print("\n" + "=" * 80)
    print("USER DETAILS (Decoded from JWT Token)")
    print("=" * 80)
    if all_user_details:
        for source, user_details in all_user_details:
            print(f"\n[{source}]")
            print("-" * 80)
            if isinstance(user_details, dict):
                # Display user details according to database schema format
                # Map decoded token fields to schema fields
                user_id = user_details.get("id") or user_details.get("ID") or user_details.get("user_id") or user_details.get("userId")
                user_login = user_details.get("user_login") or user_details.get("username") or user_details.get("login")
                user_nicename = user_details.get("user_nicename") or user_details.get("nicename")
                user_email = user_details.get("user_email") or user_details.get("email")
                user_url = user_details.get("user_url") or user_details.get("url") or user_details.get("website")
                user_registered = user_details.get("user_registered") or user_details.get("registered") or user_details.get("created_at")
                display_name = user_details.get("display_name") or user_details.get("name") or user_details.get("full_name")
                
                # Display in schema order
                if user_id:
                    print(f"  ID (bigint): {user_id}")
                if user_login:
                    print(f"  user_login (varchar): {user_login}")
                if user_nicename:
                    print(f"  user_nicename (varchar): {user_nicename}")
                if user_email:
                    print(f"  user_email (varchar): {user_email}")
                if user_url:
                    print(f"  user_url (varchar): {user_url}")
                if user_registered:
                    print(f"  user_registered (datetime): {format_timestamp(user_registered)}")
                if display_name:
                    print(f"  display_name (varchar): {display_name}")
                
                # Display any other fields from the token
                other_fields = {k: v for k, v in user_details.items() 
                               if k not in ["id", "ID", "user_id", "userId", "user_login", "username", "login",
                                           "user_nicename", "nicename", "user_email", "email", "user_url", "url", "website",
                                           "user_registered", "registered", "created_at", "display_name", "name", "full_name"]}
                if other_fields:
                    print("\n  Additional Token Fields:")
                    for key, value in other_fields.items():
                        if isinstance(value, dict):
                            print(f"    {key}:")
                            for sub_key, sub_value in value.items():
                                print(f"      {sub_key}: {sub_value}")
                        elif isinstance(value, list):
                            print(f"    {key}: {', '.join(str(v) for v in value)}")
                        else:
                            print(f"    {key}: {value}")
            else:
                print(f"  {user_details}")
    else:
        print("\n⚠️  No user details found in this conversation.")
        print("   (User token may not have been provided or token decoding failed)")
    print("=" * 80)
    
    # Page URLs if available
    page_urls = session.get('page_urls', [])
    if page_urls:
        print(f"\nPage URLs ({len(page_urls)}):")
        print("-" * 80)
        for url in page_urls:
            print(f"  - {url}")
    
    # Messages
    print(f"\nMessages ({len(messages)}):")
    print("=" * 80)
    
    if not messages:
        print("No messages in this conversation.")
        return
    
    for i, msg in enumerate(messages, 1):
        role = msg.get('role', 'unknown').upper()
        timestamp = format_timestamp(msg.get('ts', 'N/A'))
        html_content = msg.get('html', '')
        text_content = strip_html_tags(html_content)
        
        # Message user details if available
        msg_user_details = msg.get('user_details')
        
        print(f"\n[{i}] {role} - {timestamp}")
        if msg_user_details:
            print(f"\n    👤 User Details (from JWT token):")
            if isinstance(msg_user_details, dict):
                # Display according to schema
                user_id = msg_user_details.get("id") or msg_user_details.get("ID") or msg_user_details.get("user_id")
                user_login = msg_user_details.get("user_login") or msg_user_details.get("username")
                user_email = msg_user_details.get("user_email") or msg_user_details.get("email")
                display_name = msg_user_details.get("display_name") or msg_user_details.get("name")
                
                if user_id:
                    print(f"      ID: {user_id}")
                if user_login:
                    print(f"      Username: {user_login}")
                if user_email:
                    print(f"      Email: {user_email}")
                if display_name:
                    print(f"      Display Name: {display_name}")
                
                # Show other fields
                other_fields = {k: v for k, v in msg_user_details.items() 
                               if k not in ["id", "ID", "user_id", "user_login", "username",
                                           "user_email", "email", "display_name", "name"]}
                if other_fields:
                    for key, value in other_fields.items():
                        if isinstance(value, dict):
                            print(f"      {key}:")
                            for sub_key, sub_value in value.items():
                                print(f"        {sub_key}: {sub_value}")
                        elif isinstance(value, list):
                            print(f"      {key}: {', '.join(str(v) for v in value)}")
                        else:
                            print(f"      {key}: {value}")
            else:
                print(f"      {msg_user_details}")
        print("-" * 80)
        
        # Display text content (truncate if too long)
        if len(text_content) > 500:
            print(text_content[:500])
            print(f"\n... (truncated, {len(text_content)} total characters)")
        else:
            print(text_content)
        
        print()
    
    print("=" * 80)


def main():
    """Main function."""
    # Check for command-line arguments
    show_user_details_only = "--user-details-only" in sys.argv or "-u" in sys.argv
    
    print("Retrieving last conversation from MongoDB...")
    print()
    
    session = get_last_conversation()
    
    if session:
        if show_user_details_only:
            display_user_details_only(session)
        else:
            display_conversation(session)
        
        # Optionally save to JSON file
        save_json = os.getenv("SAVE_JSON", "false").lower() == "true"
        if save_json:
            output_file = "last_conversation.json"
            # Convert datetime objects to ISO strings for JSON serialization
            def json_serial(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(session, f, indent=2, default=json_serial, ensure_ascii=False)
            print(f"\nConversation saved to {output_file}")
    else:
        print("No conversation found in the database.")


if __name__ == "__main__":
    main()
