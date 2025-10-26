# [This is your new main.py]

import uvicorn
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from models import (
    ChatMessageRequest, VoteRequest, ChatMessageInDB, Poll, NewChatRequest,
    DecisionSession, ChatDocument, NewMemberRequest  # Import our new models
)
from ai_service import analyze_message_for_poll, analyze_chat_for_preferences # Import both AI functions
import uuid
import datetime

# --- 1. Initialization ---

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
app = FastAPI()

# --- 2. Background Task Orchestration ---

# This is our new "main brain" for background tasks
async def process_new_message_tasks(
    chat_id: str, 
    message: ChatMessageInDB, 
    current_message_count: int
):
    """
    Orchestrates all background AI tasks after a message is posted.
    """
    
    # --- Task 1: Check for User-Triggered Suggestion (e.g., "/find") ---
    if message.text.strip().lower() == "/find-food":
        print("User trigger '/find-food' detected. Running suggestion task.")
        await run_suggestion_trigger(chat_id)
        return # Stop other processing, the user wants action now
    
    # --- Task 2: Run Poll Analysis (Your existing logic) ---
    # We still check every message for a potential poll
    # await run_poll_analysis(chat_id, message)
    
    # --- Task 3: Run Rolling Preference Analysis (Mini-Batch) ---
    # We run this every 4 messages to update the rolling preferences
    if current_message_count % 4 == 0:
        print(f"Message count {current_message_count}. Running rolling preference analysis.")
        await run_preference_analysis(chat_id)

async def run_poll_analysis(chat_id: str, message: ChatMessageInDB):
    """
    Analyzes a SINGLE message for a poll and saves it.
    (This is your original 'run_ai_analysis' function)
    """
    print(f"Running Poll Analysis on: '{message.text}'")
    poll = await analyze_message_for_poll(message.text)
    
    if poll:
        print(f"AI generated poll: {poll.title}")
        try:
            poll_doc = poll.model_dump(mode="json")
            db.collection("chats").document(chat_id).collection("polls").add(poll_doc)
            print("Poll saved to Firestore.")
        except Exception as e:
            print(f"Error saving poll to Firestore: {e}")

async def run_preference_analysis(chat_id: str):
    """
    Analyzes the chat history for rolling preferences and saves them.
    """
    chat_log = await get_chat_log(chat_id, limit=20)
    if not chat_log:
        print("No chat log found, skipping preference analysis.")
        return

    # Call our new Tier 2 AI function
    decision_session = await analyze_chat_for_preferences(chat_log)
    
    # Save the result to the *main* chat document
    try:
        db.collection("chats").document(chat_id).update({
            "current_decision": decision_session.model_dump(mode="json")
        })
        print(f"Rolling preferences updated for chat {chat_id}.")
    except Exception as e:
        print(f"Error updating preferences in Firestore: {e}")

async def run_suggestion_trigger(chat_id: str):
    """
    Triggered by '/find-food'. Reads the current preferences and
    posts a summary message back to the chat.
    """
    try:
        # 1. Get the most recent preferences
        doc_ref = db.collection("chats").document(chat_id)
        doc = doc_ref.get()
        if not doc.exists:
            print("Chat doc not found for suggestion trigger.")
            return

        chat_data = ChatDocument(**doc.to_dict())
        summary = chat_data.current_decision.summary
        
        # 2. Post a message back to the chat as the "assistant"
        ai_message_text = f"Okay group, I'm on it! 🤖\nBased on our chat, I'm looking for: \"{summary}\""
        
        await post_message_to_chat(
            chat_id=chat_id,
            user_id="ai-assistant",
            user_name="FoodieBot",
            text=ai_message_text
        )
        
        # (FUTURE: This is where you would also trigger the Google Places API search)

    except Exception as e:
        print(f"Error running suggestion trigger: {e}")

# --- 3. Helper Functions ---

async def get_chat_log(chat_id: str, limit: int = 20) -> str:
    """
    Fetches the last N messages from Firestore and formats them
    into a simple string log for the AI.
    """
    messages_ref = db.collection("chats").document(chat_id).collection("messages")
    query = messages_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
    docs = query.stream()
    
    chat_lines = []
    for doc in docs:
        msg = ChatMessageInDB(**doc.to_dict())
        chat_lines.append(f"{msg.user_name}: {msg.text}")
    
    # Reverse to get chronological order for the AI
    chat_lines.reverse()
    return "\n".join(chat_lines)

async def post_message_to_chat(chat_id: str, user_id: str, user_name: str, text: str):
    """
    A helper function for the AI to send a message to the chat.
    """
    try:
        ai_message = ChatMessageInDB(
            user_id=user_id,
            user_name=user_name,
            text=text
        )
        db_doc = ai_message.model_dump(mode="json")
        db.collection("chats").document(chat_id).collection("messages").add(db_doc)
        print(f"Posted AI message to chat {chat_id}")
    except Exception as e:
        print(f"Error posting AI message to chat: {e}")


# --- 4. API Endpoints ---

@app.post("/api/v1/chats/{chat_id}/messages", status_code=status.HTTP_202_ACCEPTED)
async def post_message(
    chat_id: str, 
    message: ChatMessageRequest, 
    background_tasks: BackgroundTasks
):
    """
    Receives a new message, saves it, and triggers all AI background tasks.
    """
    try:
        # 1. Create the full message object
        message_in_db = ChatMessageInDB(**message.model_dump())
        
        # 2. Save the message to Firestore
        db_doc = message_in_db.model_dump(mode="json")
        db.collection("chats").document(chat_id).collection("messages").add(db_doc)
        
        # 3. Atomically increment the message count for this chat
        chat_ref = db.collection("chats").document(chat_id)
        update_result = chat_ref.update({"message_count": firestore.Increment(1)})
        
        # Get the new count. We need a 'get' after 'update' if we use Increment
        # A transaction would be safer, but this is simpler for now.
        # Let's assume the count is "good enough" for batching.
        # A more robust way is to use a transaction to get the count *after* increment.
        
        # For simplicity, let's just trigger the background task.
        # We will fetch the count inside the task if needed, or just run on every message.
        # Let's re-think: We need the count *now* to decide to run the batch.
        
        # --- Let's use a transaction for safety ---
        transaction = db.transaction()
        chat_ref = db.collection("chats").document(chat_id)

        @firestore.transactional
        def increment_counter_in_transaction(tx, doc_ref):
            snapshot = doc_ref.get(transaction=tx)
            if not snapshot.exists:
                raise HTTPException(status_code=404, detail="Chat not found")
            
            new_count = snapshot.to_dict().get("message_count", 0) + 1
            tx.update(doc_ref, {"message_count": new_count})
            return new_count

        new_message_count = increment_counter_in_transaction(transaction, chat_ref)
        
        # 4. Add the *one* orchestrator task
        background_tasks.add_task(
            process_new_message_tasks, 
            chat_id, 
            message_in_db, 
            new_message_count
        )
        
        # 5. Respond immediately
        return {"status": "pending_analysis", "message_id": message_in_db.timestamp.isoformat()}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/chats", status_code=status.HTTP_201_CREATED)
async def create_new_chat(chat_request: NewChatRequest):
    """
    Creates a new chat document in Firestore, initializing the
    message count and decision state.
    """
    try:
        new_chat_ref = db.collection("chats").document()
        new_chat_id = new_chat_ref.id
        
        # Use our new ChatDocument model to create the initial data
        chat_data = ChatDocument(
            chat_id=new_chat_id,
            chat_name=chat_request.chat_name,
            members=chat_request.user_ids,
            created_at=datetime.datetime.now(),
            message_count=0,
            current_decision=DecisionSession() # Initialize with empty defaults
        )
        
        new_chat_ref.set(chat_data.model_dump(mode="json"))
        
        return chat_data.model_dump(mode="json")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/chats/{chat_id}/add_member", status_code=status.HTTP_200_OK)
async def add_member_to_chat(chat_id: str, user_id: NewMemberRequest):
    """
    Adds a new member to an existing chat.
    """
    try:
        chat_ref = db.collection("chats").document(chat_id)
        chat_ref.update({
            "members": firestore.ArrayUnion([user_id.user_id])
        })
        return {"status": "member_added", "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# [Your /vote endpoint stays exactly the same]
@app.post("/api/v1/chats/{chat_id}/polls/{poll_id}/vote")
async def vote_on_poll(chat_id: str, poll_id: str, vote: VoteRequest):
    # [ ... all your existing vote logic ... ]
    # 1. Get a reference to the specific poll document
    poll_ref = db.collection("chats").document(chat_id).collection("polls").document(poll_id)
    
    # 2. Use a transaction to safely update the vote
    transaction = db.transaction()
    
    @firestore.transactional
    def update_in_transaction(tx, doc_ref):
        snapshot = doc_ref.get(transaction=tx)
        if not snapshot.exists:
            raise HTTPException(status_code=404, detail="Poll not found")
            
        poll_data = snapshot.to_dict()
        
        # Find the option and increment its vote count
        new_options = poll_data.get("options", [])
        found_option = False
        for option in new_options:
            if option.get("text") == vote.option_text:
                option["votes"] = option.get("votes", 0) + 1
                found_option = True
                break
        
        if not found_option:
            raise HTTPException(status_code=400, detail="Invalid poll option")

        # (Optional: Add logic here to track user_id to prevent double-voting)
        
        # Commit the change back to Firestore
        tx.update(doc_ref, {"options": new_options})
        poll_data["options"] = new_options # Return the updated data
        return poll_data

    try:
        # 3. Execute the transaction
        updated_poll = update_in_transaction(transaction, poll_ref)
        return updated_poll
    except Exception as e:
        # Re-raise HTTPExceptions, handle others
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/chats/{chat_id}/messages")
async def get_chat_messages(chat_id: str):
    """
    Fetch all messages for a chat room from Firestore
    """
    try:
        # Reference to the messages collection for this chat
        messages_ref = db.collection("chats").document(chat_id).collection("messages")
        
        # Get all messages, ordered by timestamp
        messages_query = messages_ref.order_by("timestamp").stream()
        
        # Convert to list of dicts
        message_list = []
        for msg_doc in messages_query:
            msg_data = msg_doc.to_dict()
            message_list.append({
                "message_id": msg_doc.id,  # Document ID from Firestore
                "user_id": msg_data.get("user_id", ""),
                "user_name": msg_data.get("user_name", ""),
                "text": msg_data.get("text", ""),
                "timestamp": msg_data.get("timestamp", datetime.datetime.now().isoformat())
            })
        
        print(f"✅ Fetched {len(message_list)} messages for chat {chat_id}")
        return {"messages": message_list}
    
    except Exception as e:
        print(f"❌ Error fetching messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 5. Run the Server ---
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)