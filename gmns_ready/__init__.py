"""
GMNS Ready - Professional toolkit for GMNS transportation networks
"""

__version__ = '0.0.4'
__author__ = 'Henan Zhu, Xuesong Zhou, Han Zheng'
__email__ = 'henanzhu@asu.edu'

# Import validation functions (these have proper function definitions)
from .validate_assignment import run_validation as validate_assignment


# For the script-based files, we need to create wrapper functions
# These files run code directly, so we'll import them as modules

def extract_zones():
    """Extract zone centroids and boundaries from shapefile"""
    import subprocess
    import sys
    import os

    # Get the directory where this file is located
    current_dir = os.path.dirname(__file__)
    script_path = os.path.join(current_dir, 'extract_zones.py')

    # Run the script
    subprocess.run([sys.executable, script_path], check=True)


def extract_zones_pop():
    """Extract zones and fetch population data (US only)"""
    import subprocess
    import sys
    import os

    current_dir = os.path.dirname(__file__)
    script_path = os.path.join(current_dir, 'extract_zones_pop.py')

    subprocess.run([sys.executable, script_path], check=True)


def clean_network():
    """Remove disconnected components from OSM networks"""
    import subprocess
    import sys
    import os

    current_dir = os.path.dirname(__file__)
    script_path = os.path.join(current_dir, 'clean_network.py')

    subprocess.run([sys.executable, script_path], check=True)


def build_network():
    """Generate zone-connected network with connectors"""
    import subprocess
    import sys
    import os

    current_dir = os.path.dirname(__file__)
    script_path = os.path.join(current_dir, 'build_network.py')

    subprocess.run([sys.executable, script_path], check=True)


def validate_basemap():
    """Verify spatial alignment of input files"""
    import subprocess
    import sys
    import os

    current_dir = os.path.dirname(__file__)
    script_path = os.path.join(current_dir, 'validate_basemap.py')

    subprocess.run([sys.executable, script_path], check=True)


def validate_network():
    """Check network structure and topology"""
    import subprocess
    import sys
    import os

    current_dir = os.path.dirname(__file__)
    script_path = os.path.join(current_dir, 'validate_network.py')

    subprocess.run([sys.executable, script_path], check=True)


def validate_accessibility():
    """Analyze zone-to-zone connectivity"""
    import subprocess
    import sys
    import os

    current_dir = os.path.dirname(__file__)
    script_path = os.path.join(current_dir, 'validate_accessibility.py')

    subprocess.run([sys.executable, script_path], check=True)


def enhance_connectors():
    """Add connectors for poorly connected zones"""
    import subprocess
    import sys
    import os

    current_dir = os.path.dirname(__file__)
    script_path = os.path.join(current_dir, 'enhance_connectors.py')

    subprocess.run([sys.executable, script_path], check=True)


# Public API
__all__ = [
    'validate_basemap',
    'extract_zones',
    'extract_zones_pop',
    'build_network',
    'validate_network',
    'validate_accessibility',
    'validate_assignment',
    'enhance_connectors',
    'clean_network',
]