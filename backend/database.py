import firebase_admin
from firebase_admin import credentials, firestore
import dotenv
import os

dotenv.load_dotenv()

# Initialize Firebase Admin SDK
# Check if already initialized to avoid errors during hot reload or multiple imports
if not firebase_admin._apps:
    # Ensure the path is correct relative to where the script is run
    # Assuming main.py is run from backend/ or root
    cred_path = "serviceAccountKey.json"
    if not os.path.exists(cred_path):
        # Try looking one level up or down if needed, but standardizing on running from backend/ is best
        pass
        
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()
