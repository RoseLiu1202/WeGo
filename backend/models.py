# [This is your new, corrected models.py]

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

class NewChatRequest(BaseModel):
    chat_name: str
    user_ids: List[str] # A list of user IDs to add to the chat

class NewMemberRequest(BaseModel):
    user_id: str
    
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

# --- AI Preference Extraction Models (Corrected Flexible Version) ---

class StructuredPreferences(BaseModel):
    """
    Preferences that map directly to common API filters.
    """
    cuisines_positive: List[str] = Field(default_factory=list, description="Cuisines the group wants (e.g., 'Sushi', 'Vietnamese')")
    cuisines_negative: List[str] = Field(default_factory=list, description="Cuisines the group rejected (e.g., 'Thai')")
    price_range: List[str] = Field(default_factory=list, description="Price ranges, e.g., '$$', 'cheap'")
    dietary_restrictions: List[str] = Field(default_factory=list)

class DecisionSession(BaseModel):
    """
    Represents the group's current, rolling preferences.
    This will be stored as a single map in the main chat document.
    """
    structured_preferences: StructuredPreferences = Field(default_factory=StructuredPreferences)
    
    # This is the new flexible map you wanted.
    # Example: {"ambience": ["cozy", "quiet"], "food_quality": ["light", "refreshing"]}
    # dynamic_attributes: dict[str, List[str]] = Field(
    #     default_factory=dict, 
    #     description="A flexible map of categorized preference tags."
    # )
    
    # 'summary' is now correctly placed at the top level
    summary: str = Field(
        default="No preferences found yet.", 
        description="A 1-sentence summary of what the group wants."
    )
    
    last_updated: datetime.datetime = Field(default_factory=datetime.datetime.now)


# --- Firestore Document Models ---

class ChatDocument(BaseModel):
    """
    Represents the main document at /chats/{chat_id}
    """
    chat_id: str
    chat_name: str
    members: List[str]
    created_at: datetime.datetime
    message_count: int = 0
    current_decision: DecisionSession = Field(default_factory=DecisionSession)