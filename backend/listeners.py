from database import db
from chat_logic import run_preference_analysis
import asyncio
import threading

# Cache to prevent infinite loops and duplicate processing
# Maps chat_id -> last_seen_message_count
_processed_counts = {}

def on_chat_snapshot(col_snapshot, changes, read_time, loop):
    """
    Callback for Firestore on_snapshot.
    Triggered when any document in the 'chats' collection changes.
    """
    for change in changes:
        # We only care about Modified or Added documents
        if change.type.name == 'MODIFIED' or change.type.name == 'ADDED':
            doc = change.document
            chat_id = doc.id
            data = doc.to_dict()
            
            message_count = data.get("message_count", 0)
            
            # Get the last count we processed for this chat
            last_count = _processed_counts.get(chat_id, -1)
            
            # Only proceed if the message count has CHANGED (or is new to us)
            # This prevents infinite loops when we update the 'current_decision' field
            if message_count != last_count:
                _processed_counts[chat_id] = message_count
                
                # Check our business logic condition
                if message_count > 0 and message_count % 4 == 0:
                    print(f"Listener: Chat {chat_id} reached {message_count} messages. Triggering preference analysis.")
                    
                    # Schedule the async task on the main event loop
                    if loop and loop.is_running():
                        asyncio.run_coroutine_threadsafe(run_preference_analysis(chat_id), loop)
                    else:
                        print("Error: Main event loop is not running.")

def start_listeners(loop):
    """
    Starts the Firestore listener.
    """
    print("Starting Firestore listeners...")
    chat_ref = db.collection("chats")
    
    # Create a partial function or wrapper to pass the loop
    def callback_wrapper(col_snapshot, changes, read_time):
        on_chat_snapshot(col_snapshot, changes, read_time, loop)

    # Watch the collection
    # Note: This returns a Watch object which can be used to unsubscribe
    # We keep it in a global or return it to keep it alive
    return chat_ref.on_snapshot(callback_wrapper)
