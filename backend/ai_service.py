import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from models import Poll, PollOption
from models import DecisionSession
import os
import json
import dotenv
import datetime

# Load environment variables from .env file
dotenv.load_dotenv()

# Set your API key for Google Generative AI
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Define the JSON schema for the poll
# This FORCES Gemini to return JSON in this exact structure
POLL_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "A short, engaging question for the poll. e.g., 'Pizza Tonight?'"
        },
        "options": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "A poll option. e.g., 'Yes!' or 'No'"}
                },
                "required": ["text"]
            }
        }
    },
    "required": ["title", "options"]
}

# The system prompt to guide the AI
SYSTEM_PROMPT = """
You are a helpful assistant inside a group chat where friends are making plans.
Your job is to listen to the chat. You MUST ONLY generate a poll when a user 
suggests a concrete, actionable plan that the group can vote on.

Your default action is to return null. Be very critical and avoid creating polls 
unless you are highly confident it is a real plan.

**CRITICAL RULES:**
1.  **DO NOT** generate a poll for colloquialisms, jokes, or exclamations, 
    even if they contain nouns.
2.  **DO NOT** generate a poll for simple statements of fact or feelings.
3.  **ONLY** generate a poll if the suggestion is a *specific* food, place, time,
    or activity that the group can make a decision on.

---
**EXAMPLES OF WHAT *NOT* TO POLL (Return null):**
- "Hi, how are you?"
- "This is crazy!"
- "I am going BANANAS"
- "That's nuts"
- "I'm so hungry"
- "It's late"
- "That's a good idea"
- "I like pizza"

**EXAMPLES OF WHAT *TO* POLL (Generate JSON):**
- "Should we get pizza tonight?"
- "Let's go to the park at 3."
- "What about a movie?"
- "Anyone want to go to Top Golf?"
---

- If the message is NOT a concrete suggestion (like the examples above), return null.
- If it IS a concrete suggestion, return a JSON object that matches the provided schema.
- The poll title should be a simple question.
- The poll should have at least two simple options, e.g., a "Yes" and a "No".
"""

# This is the "brain" function
async def analyze_message_for_poll(message_text: str) -> Poll | None:
    """Analyzes a message and returns a Poll object or None."""
    
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT,
        generation_config=GenerationConfig(
            response_mime_type="application/json",
            response_schema=POLL_SCHEMA
        )
    )
    
    try:
        response = await model.generate_content_async(f"User message: '{message_text}'")
        
        # Check for empty or blocked response
        if not response.parts:
            print("AI had no response (likely not a suggestion).")
            return None

        # Parse the JSON response
        print(f"AI response text: {response.text}")
        response_json = json.loads(response.text)
        
        # Create the Poll object
        poll_data = {
            "title": response_json.get("title"),
            "options": [PollOption(text=opt.get("text"), votes=0) for opt in response_json.get("options", [])],
            "created_by_message": message_text
        }
        
        return Poll(**poll_data)

    except Exception as e:
        print(f"Error analyzing message with AI: {e}")
        return None

# --- Preference Extraction Schema (NEW FLEXIBLE VERSION) ---

PREFERENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "structured_preferences": {
            "type": "object",
            "properties": {
                "cuisines_positive": {"type": "array", "items": {"type": "string"}},
                "cuisines_negative": {"type": "array", "items": {"type": "string"}},
                "price_range": {"type": "array", "items": {"type": "string"}},
                "dietary_restrictions": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["cuisines_positive", "cuisines_negative", "price_range", "dietary_restrictions"]
        },
        "summary": {
            "type": "string",
            "description": "A 1-sentence summary of what the group wants."
        }
    },
    "required": ["structured_preferences", "summary"]
}

# --- Preference Extraction System Prompt (NEW FLEXIBLE VERSION) ---

PREFERENCE_SYSTEM_PROMPT = """
You are a group chat assistant. Your job is to analyze the following chat log and
extract all food and restaurant preferences into a single, structured JSON object.

The goal is to find a restaurant. Aggregate all preferences, resolving conflicts 
by favoring the most recent or agreed-upon consensus.

**RULES:**
1.  **Structured Preferences**: Fill 'cuisines_positive', 'cuisines_negative',
    'price_range', and 'dietary_restrictions'.

2.  **Summary**: Provide a 1-sentence summary of the group's final consensus.
3.  **Empty fields**: If no preference is found for a field, return an empty
    list `[]` or an empty object `{}`.
4.  **YOUR RESPONSE MUST BE A SINGLE, VALID JSON OBJECT** matching the schema.
    Do not include any other text, markdown, or explanations.
"""

# --- analyze_chat_for_preferences Function ---

# This function's code REMAINS EXACTLY THE SAME.
# It already parses the JSON and passes it to the DecisionSession model,
# which will now correctly handle the new structure.

async def analyze_chat_for_preferences(chat_log: str) -> DecisionSession:
    """
    Analyzes a full chat log and returns a DecisionSession object.
    This is our "Tier 2" preference extractor.
    """
    print("Running Tier 2 Preference Analysis...")
    
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=PREFERENCE_SYSTEM_PROMPT,
        generation_config=GenerationConfig(
            response_mime_type="application/json",
            response_schema=PREFERENCE_SCHEMA
        )
    )
    
    try:
        response = await model.generate_content_async(f"Chat Log:\n{chat_log}")
        
        if not response.parts:
            print("AI had no response for preference analysis.")
            return DecisionSession() # Return empty default

        response_json = json.loads(response.text)
        
        # Pydantic will correctly parse the new structure
        session_data = DecisionSession(**response_json)
        session_data.last_updated = datetime.datetime.now()
        
        print(f"AI preference summary: {session_data.summary}")
        return session_data

    except Exception as e:
        print(f"Error analyzing chat for preferences: {e}")
        return DecisionSession() # Return an empty, default session