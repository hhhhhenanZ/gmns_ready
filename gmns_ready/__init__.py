"""
GMNS Ready - Professional toolkit for GMNS transportation networks
"""

__version__ = '0.0.6'
__author__ = 'Henan Zhu, Xuesong Zhou, Han Zheng'
__email__ = 'henanzhu@asu.edu'

import os
import sys
import subprocess

def _run_script(script_name):
    """Helper function to run a script and show its output in real-time"""
    current_dir = os.path.dirname(__file__)
    script_path = os.path.join(current_dir, script_name)
    
    # Run script WITHOUT capturing - output shows immediately
    result = subprocess.run(
        [sys.executable, script_path],
        cwd=os.getcwd(),
        # Don't capture anything - let it print directly!
    )
    
    # Check if script failed
    if result.returncode != 0:
        raise RuntimeError(f"{script_name} failed with exit code {result.returncode}")
    
    return result

def extract_zones():
    """
    Extract zone centroids and boundaries from shapefile.
    
    Auto-detects .shp file in data/ folder.
    
    Example
    -------
    >>> import gmns_ready as gr
    >>> gr.extract_zones()
    """
    _run_script('extract_zones.py')

def extract_zones_pop():
    """
    Extract zones and fetch population data (US only).
    
    Auto-detects .shp file in data/ folder and adds population column.
    
    Example
    -------
    >>> import gmns_ready as gr
    >>> gr.extract_zones_pop()
    """
    _run_script('extract_zones_pop.py')

def clean_network():
    """
    Remove disconnected components from OSM networks.
    
    Cleans node.csv and link.csv from osm2gmns.
    
    Example
    -------
    >>> import gmns_ready as gr
    >>> gr.clean_network()
    """
    _run_script('clean_network.py')

def build_network():
    """
    Generate zone-connected network with connectors.
    
    Uses zone.csv, node.csv, link.csv to create connected_network/ folder.
    
    Example
    -------
    >>> import gmns_ready as gr
    >>> gr.build_network()
    """
    _run_script('build_network.py')

def validate_basemap():
    """
    Verify spatial alignment of input files.
    
    Checks that node.csv, link.csv, and zone shapefile are in same area.
    
    Example
    -------
    >>> import gmns_ready as gr
    >>> gr.validate_basemap()
    """
    _run_script('validate_basemap.py')

def validate_network():
    """
    Check network structure and topology.
    
    Validates connected_network/ folder.
    
    Example
    -------
    >>> import gmns_ready as gr
    >>> gr.validate_network()
    """
    _run_script('validate_network.py')

def validate_accessibility():
    """
    Analyze zone-to-zone connectivity.
    
    Uses TAPLite to compute accessibility matrix.
    Requires: connected_network/ folder with node.csv and link.csv
    
    Example
    -------
    >>> import gmns_ready as gr
    >>> gr.validate_accessibility()
    """
    _run_script('validate_accessibility.py')

def validate_assignment():
    """
    Verify traffic assignment readiness.
    
    Checks VDF parameters in connected_network/ folder.
    
    Example
    -------
    >>> import gmns_ready as gr
    >>> gr.validate_assignment()
    """
    from .validate_assignment import run_validation
    run_validation()

def enhance_connectors():
    """
    Add connectors for poorly connected zones.
    
    Adds 10 connectors per zone with low accessibility.
    Requires: connected_network/ folder with accessibility results
    
    Example
    -------
    >>> import gmns_ready as gr
    >>> gr.enhance_connectors()
    """
    _run_script('enhance_connectors.py')

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
