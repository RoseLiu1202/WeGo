import uvicorn
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from models import ChatMessageRequest, VoteRequest, ChatMessageInDB, Poll, NewChatRequest
from ai_service import analyze_message_for_poll
from models import Poll # ...and your other models
import uuid # For generating a unique ID
import datetime

# --- 1. Initialization ---

# Initialize Firebase Admin
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Initialize FastAPI app
app = FastAPI()

# --- 2. Background AI Task ---
# We run the AI in the background so the app feels fast.

async def run_ai_analysis(chat_id: str, message: ChatMessageInDB):
    """
    This function runs in the background.
    It analyzes the message and saves a poll if one is generated.
    """
    print(f"Running AI analysis on: '{message.text}'")
    poll = await analyze_message_for_poll(message.text)
    
    if poll:
        print(f"AI generated poll: {poll.title}")
        try:
            # Save the new poll to Firestore
            poll_doc = poll.model_dump(mode="json") # Convert Pydantic model to dict
            db.collection("chats").document(chat_id).collection("polls").add(poll_doc)
            print("Poll saved to Firestore.")
        except Exception as e:
            print(f"Error saving poll to Firestore: {e}")

# --- 3. API Endpoints ---

@app.post("/api/v1/chats/{chat_id}/messages", status_code=status.HTTP_202_ACCEPTED)
async def post_message(
    chat_id: str, 
    message: ChatMessageRequest, 
    background_tasks: BackgroundTasks
):
    """
    Receives a new message, saves it, and triggers AI analysis.
    """
    try:
        # 1. Create the full message object with a server timestamp
        message_in_db = ChatMessageInDB(**message.model_dump())
        
        # 2. Save the message to Firestore
        db_doc = message_in_db.model_dump(mode="json")
        db.collection("chats").document(chat_id).collection("messages").add(db_doc)
        
        # 3. Add the AI analysis as a background task
        background_tasks.add_task(run_ai_analysis, chat_id, message_in_db)
        
        # 4. Respond immediately to the app
        return {"status": "pending_analysis", "message_id": message_in_db.timestamp.isoformat()}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/chats/{chat_id}/polls/{poll_id}/vote")
async def vote_on_poll(chat_id: str, poll_id: str, vote: VoteRequest):
    """
    Receives a vote and updates the poll's vote count in Firestore.
    This uses a transaction to prevent two votes from overwriting each other.
    """
    
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

@app.post("/api/v1/chats", status_code=status.HTTP_201_CREATED)
async def create_new_chat(chat_request: NewChatRequest):
    """
    Creates a new chat document in Firestore and returns its ID.
    """
    try:
        # 1. Let Firestore generate a new, unique document reference
        new_chat_ref = db.collection("chats").document()
        
        # 2. Get the auto-generated ID string from that reference
        new_chat_id = new_chat_ref.id
        
        # 3. Save the initial chat data (like the name and members)
        chat_data = {
            "chat_id": new_chat_id,
            "chat_name": chat_request.chat_name,
            "members": chat_request.user_ids,
            "created_at": datetime.datetime.now()
        }
        new_chat_ref.set(chat_data)
        
        # 4. Return the new chat object (most importantly, the new ID)
        return chat_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- 4. Run the Server (for testing) ---
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)