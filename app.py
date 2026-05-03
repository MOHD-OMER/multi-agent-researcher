"""
HuggingFace Spaces entry point.
Handles environment setup and launches the Gradio frontend.
"""
import sys
import os
from pathlib import Path

# Add project root to Python path
root = Path(__file__).parent
sys.path.insert(0, str(root))

# On Spaces, secrets are env vars — dotenv is a no-op but harmless
from dotenv import load_dotenv
load_dotenv()

# Verify API keys are present
groq_key   = os.getenv("GROQ_API_KEY", "")
tavily_key = os.getenv("TAVILY_API_KEY", "")

if not groq_key:
    print("WARNING: GROQ_API_KEY not set — add it in Space Settings → Variables and Secrets")
if not tavily_key:
    print("WARNING: TAVILY_API_KEY not set — add it in Space Settings → Variables and Secrets")

# Ensure data directory exists for history
(root / "data").mkdir(exist_ok=True)

# Import and launch
from frontend.app import demo

demo.launch(
    server_name="0.0.0.0",
    server_port=7860,
    show_error=True,
)