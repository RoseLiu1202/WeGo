from models import (
    ChatMessageInDB, ChatDocument
)
from ai_service import analyze_message_for_poll, analyze_chat_for_preferences, convert_decision_to_places_api_request, search_restaurants
from database import db
from firebase_admin import firestore
import datetime

# --- Helper Functions ---

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

# --- Core Logic ---

async def run_poll_analysis(chat_id: str, message: ChatMessageInDB):
    """
    Analyzes a SINGLE message for a poll and saves it.
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
            user_name="WeGoGo",
            text=ai_message_text
        )

        # Send current_decision to Gemini to convert to Places API parameters
        decision_data = chat_data.current_decision.model_dump(mode="json")
        print(f"Current decision data for Places API: {decision_data}")
        places_api_params = await convert_decision_to_places_api_request(chat_data.current_decision)
        print(f"Converted Places API parameters: {places_api_params}")
        
        # Trigger the Google Places API search here
        response = await search_restaurants(places_api_params)

        # Process the Places API response and post results back to the chat
        if response and "places" in response:
            for place in response["places"]:
                place_name = place.get("displayName", {}).get("text", "Unknown")
                place_address = place.get("formattedAddress", "No address")
                place_rating = place.get("rating", "N/A")
                place_website = place.get("websiteUri", "")
                
                ai_message_text = f"🍽️ {place_name}\n📍 {place_address}\n⭐ Rating: {place_rating}"
                if place_website:
                    ai_message_text += f"\n🔗 {place_website}"
                    
                await post_message_to_chat(
                    chat_id=chat_id,
                    user_id="ai-assistant",
                    user_name="WeGoGo",
                    text=ai_message_text
                )
        else:
            await post_message_to_chat(
                chat_id=chat_id,
                user_id="ai-assistant",
                user_name="WeGoGo",
                text="Sorry, I couldn't find any places matching our preferences."
            )

    except Exception as e:
        print(f"Error running suggestion trigger: {e}")

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
    # REMOVED: Now handled by on_snapshot listener in listeners.py
    # if current_message_count % 4 == 0:
    #     print(f"Message count {current_message_count}. Running rolling preference analysis.")
    #     await run_preference_analysis(chat_id)
