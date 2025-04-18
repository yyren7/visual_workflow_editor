import sys
import os

# Add the project root directory (parent of 'backend') to the Python path
# This allows tests inside 'backend' to import modules from the root ('database' etc.)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    print(f"Added {project_root} to sys.path") # Optional: for debugging

# You can also define fixtures here if needed later 