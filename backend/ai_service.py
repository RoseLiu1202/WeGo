import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from models import Poll # Import the Poll model we just defined
import os
import json
import dotenv

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
Your job is to listen to the chat. When a user suggests a concrete plan 
(like a food, place, or time), you must generate a poll for the group.

- If the message is NOT a suggestion (e.g., 'Hi', 'How are you?'), return null.
- If it IS a suggestion, return a JSON object that matches the provided schema.
- The poll title should be a simple question.
- The poll should have at least two options, e.g., a "Yes" and a "No" option.
"""

# This is the "brain" function
async def analyze_message_for_poll(message_text: str) -> Poll | None:
    """Analyzes a message and returns a Poll object or None."""
    
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash-latest",
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