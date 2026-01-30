from google import genai
from google.genai import types
from models import Poll, PollOption
from models import DecisionSession, PreferenceGroup, PreferenceEntry
from models import PlacesAPIFilterRequest
import os
import json
import dotenv
import datetime
import aiohttp
from pydantic import BaseModel, Field
from typing import List, Optional


# Load environment variables from .env file
dotenv.load_dotenv()

# Set your API key for Google Generative AI
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

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
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"User message: '{message_text}'",
            config={
                "response_mime_type": "application/json",
                "system_instruction":
                [
                    SYSTEM_PROMPT
                ],

                "response_json_schema": POLL_SCHEMA,
            }        
        )
        
        # Check for empty or blocked response
        if not response.parts:
            print("AI had no response (likely not a suggestion).")
            return None
        
        if not response.text:
            print("AI returned empty text (likely not a suggestion).")
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

# --- Preference Extraction System Prompt (NEW FLEXIBLE VERSION) ---

PREFERENCE_SYSTEM_PROMPT = """
The following is a chat log between multiple users discussing food preferences.
Your task is to extract individual user preferences regarding food, cuisine types, distance, price ranges, and dining options.
**CRITICAL RULES:**
- You must return a JSON object that contains a list of all individual user preferences
- Return an empty list if no preferences are found
- Return an empty list if the chat log contains no relevant information
- Each preference entry must include the user, the specific preference, and the object of the preference
"""

# --- analyze_chat_for_preferences Function ---

# This function's code REMAINS EXACTLY THE SAME.
# It already parses the JSON and passes it to the DecisionSession model,
# which will now correctly handle the new structure.

async def analyze_chat_for_preferences(chat_log: str) -> DecisionSession:
    """
    Analyzes past 10 messages and returns a DecisionSession object.
    """
    print("Running Tier 2 Preference Analysis...")
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Chat log: '''{chat_log}'''",
            config={
                "response_mime_type": "application/json",
                "system_instruction":
                [
                    PREFERENCE_SYSTEM_PROMPT
                ],
                "response_json_schema": PreferenceGroup.model_json_schema(),
            }
        )
        
        if not response.parts:
            print("AI had no response for preference analysis.")
            return DecisionSession() # Return empty default
        
        if not response.text:
            print("AI returned empty text for preference analysis.")
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

# --- current_decision to Places API converter ---
PLACES_API_FORMATING_PROMPT = """
You are a data formatter. Convert the following structured preferences into a Google Places API (New) v1 Text Search request body.

Structured Preferences:
{structured_preferences_json}

Generate a JSON object that will be sent as the request body to the Places API v1 searchText endpoint.

**CRITICAL RULES:**
1. **textQuery** (required): Create a natural language search query from cuisines_positive. Example: "Hot Pot restaurant" or "Italian restaurant"
   - **DO NOT include any location information in textQuery** (no city names, neighborhoods, "near me", etc.)
   - Location will be handled separately via locationBias
   - Good: "Italian restaurant", "Spicy vegetarian food", "Sushi"
   - Bad: "Italian restaurant in St Louis", "Sushi near downtown", "Pizza in Missouri"
2. **priceLevels** (optional): Array of price level strings. Map price_range to:
   - "cheap" or "inexpensive" or "affordable" or "$" → ["PRICE_LEVEL_INEXPENSIVE"]
   - "moderate" or "$$" → ["PRICE_LEVEL_MODERATE"] 
   - "expensive" or "$$$" → ["PRICE_LEVEL_EXPENSIVE"]
   - "very expensive" or "$$$$" → ["PRICE_LEVEL_VERY_EXPENSIVE"]
   If multiple ranges mentioned, include all applicable levels. Never use PRICE_LEVEL_FREE.
3. **includedType** (optional): Set to "restaurant" for restaurant searches
4. Incorporate negative preferences (cuisines_negative) into the textQuery by adding exclusions like "not spicy" or "no Thai"

**Output ONLY the required fields: textQuery, and optionally priceLevels and includedType. Do NOT include locationBias.**
"""

PLACES_API_REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "textQuery": {
            "type": "string",
            "description": "Natural language search query"
        },
        "priceLevels": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["PRICE_LEVEL_INEXPENSIVE", "PRICE_LEVEL_MODERATE", "PRICE_LEVEL_EXPENSIVE", "PRICE_LEVEL_VERY_EXPENSIVE"]
            }
        },
        "includedType": {
            "type": "string",
            "description": "Type filter, usually 'restaurant'"
        }
    },
    "required": ["textQuery"]
}

async def convert_decision_to_places_api_request(decision: DecisionSession) -> dict:
    """
    Converts a DecisionSession into Places API (New) v1 request body.
    """
    structured_preferences_json = json.dumps(decision.structured_preferences.model_dump())
    prompt = PLACES_API_FORMATING_PROMPT.format(structured_preferences_json=structured_preferences_json)
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": PLACES_API_REQUEST_SCHEMA,
            }
        )
        if not response.parts:
            print("AI had no response for Places API formatting.")
            return {
                "body": {"textQuery": "restaurant", "pageSize": 4},
                "api_key": os.environ.get("GOOGLE_PLACES_API_KEY")
            }
        if not response.text:
            print("AI returned empty text for Places API formatting.")
            return {
                "body": {"textQuery": "restaurant", "pageSize": 4},
                "api_key": os.environ.get("GOOGLE_PLACES_API_KEY")
            }
        
        print(f"Gemini response for Places API: {response.text}")
        places_api_request_body = json.loads(response.text)
        
        # Add pageSize for limiting results
        places_api_request_body["pageSize"] = 4
        
        # Add default location bias (St. Louis area)
        places_api_request_body["locationRestriction"] = {
            "rectangle": {
                "low": {
                    "latitude": 38.585,
                    "longitude": -90.394
                },
                "high": {
                    "latitude": 38.711,
                    "longitude": -90.216
                }
            }
        }

        # Get API key from environment
        PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")

        return {
            "body": places_api_request_body,
            "api_key": PLACES_API_KEY
        }
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print(f"Raw response text: {response.text if 'response' in locals() else 'No response'}")
        return {
            "body": {"textQuery": "restaurant", "pageSize": 4},
            "api_key": os.environ.get("GOOGLE_PLACES_API_KEY")
        }
    except Exception as e:
        print(f"Error converting decision to Places API params: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return {
            "body": {"textQuery": "restaurant", "pageSize": 4},
            "api_key": os.environ.get("GOOGLE_PLACES_API_KEY")
        }

# --- Places API Request ---
async def search_restaurants(places_api_request: dict) -> dict:
    """
    Searches for restaurants using the Google Places API (New) v1.
    """
    PLACES_API_URL = "https://places.googleapis.com/v1/places:searchText"
    
    # Extract the request body and API key
    request_body = places_api_request.get("body", {})
    api_key = places_api_request.get("api_key")
    
    # Set up headers
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.priceLevel,places.types,places.websiteUri"
    }
    
    print(f"Places API request body: {json.dumps(request_body, indent=2)}")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(PLACES_API_URL, json=request_body, headers=headers) as resp:
            response_text = await resp.text()
            if resp.status == 200:
                results = json.loads(response_text)
                print(f"Places API response: {json.dumps(results, indent=2)}")
                return results
            else:
                print(f"Places API request failed with status {resp.status}")
                print(f"Error response: {response_text}")
                return {}