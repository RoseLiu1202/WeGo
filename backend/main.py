# [This is your new main.py]

import uvicorn
import asyncio
from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from models import (
    ChatMessageRequest, VoteRequest, ChatMessageInDB, NewChatRequest,
    DecisionSession, ChatDocument, NewMemberRequest
)
from database import db
from chat_logic import process_new_message_tasks
from listeners import start_listeners
import datetime
from firebase_admin import firestore

app = FastAPI()

# --- Startup Event ---
@app.on_event("startup")
async def startup_event():
    # Get the current event loop
    loop = asyncio.get_running_loop()
    # Start the Firestore listener
    # We store the watch object in app.state to keep it alive
    app.state.chat_listener = start_listeners(loop)


# --- 4. CORS Middleware ---
# --- CORS Configuration ---
# This is the crucial part for your friend's Vercel frontend.

# 1. Get your friend's Vercel production URL (e.g., https://my-friends-app.vercel.app)
# 2. Get their custom domain if they have one (e.g., https://www.their-cool-site.com)
# 3. Add their local development URL (e.g., http://localhost:3000 for React/Next.js)

origins = [
    "https://we-go-snowy.vercel.app",  # Your friend's production Vercel URL
]
# If your friend uses Vercel's dynamic preview URLs (e.g., my-app-git-branch.vercel.app),
# you might want to use a regex instead of listing all origins:
# allow_origin_regex = r"https://.*\.vercel\.app"
# If you use the regex, set allow_origins=[] or remove it.

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # The list of allowed origins
    # allow_origin_regex=allow_origin_regex, # Uncomment this to use regex for Vercel previews
    allow_credentials=True,  # Allow cookies and auth headers
    allow_methods=["*"],  # Allow all methods (GET, POST, PUT, etc.)
    allow_headers=["*"],  # Allow all headers
)


# --- 4. API Endpoints ---

@app.get("/")
async def root():
    """
    Root endpoint to check if the API is running.
    """
    return {"message": "CORS-enabled chat API is running!"}

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




# --- 5. Run the Server ---
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)