from pydantic import BaseModel, Field
from typing import List, Optional
import datetime

# --- API Request Models (What the iOS app sends you) ---

class ChatMessageRequest(BaseModel):
    """A message sent from a user."""
    user_id: str
    user_name: str
    text: str

class VoteRequest(BaseModel):
    """A vote cast by a user."""
    user_id: str
    option_text: str # e.g., "Yes, let's go!"

# --- Database Models (What you save in Firestore) ---

class PollOption(BaseModel):
    """A single option in a poll."""
    text: str
    votes: int = 0

class Poll(BaseModel):
    """The poll object saved in Firestore."""
    title: str
    options: List[PollOption]
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    created_by_message: str # The text of the message that triggered this poll

class ChatMessageInDB(ChatMessageRequest):
    """A message object as saved in Firestore."""
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now)

class NewChatRequest(BaseModel):
    chat_name: str
    user_ids: List[str] # A list of user IDs to add to the chat