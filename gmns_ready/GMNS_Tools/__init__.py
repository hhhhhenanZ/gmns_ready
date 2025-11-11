"""
GMNS Tools - Validation tools and reference data
"""
import os

# Get the directory where this file is located
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))

# Helper function to get paths to data files
def get_tool_path(filename):
    """Get the full path to a tool file"""
    return os.path.join(TOOLS_DIR, filename)
