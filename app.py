"""
HuggingFace Spaces entry point.
Spaces requires app.py at the root level.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import and launch the Gradio app
from frontend.app import demo

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
