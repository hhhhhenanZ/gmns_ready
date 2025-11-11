"""
GMNS Ready - Professional toolkit for GMNS transportation networks
"""

__version__ = '0.0.5'
__author__ = 'Henan Zhu, Xuesong Zhou, Han Zheng'
__email__ = 'henanzhu@asu.edu, xzhou74@asu.edu'

import os
import sys
import subprocess


def _run_script(script_name):
    """Helper function to run a script and show its output"""
    current_dir = os.path.dirname(__file__)
    script_path = os.path.join(current_dir, script_name)

    # Run script and show output in real-time
    result = subprocess.run(
        [sys.executable, script_path],
        cwd=os.getcwd(),  # Run in current working directory
        capture_output=False,  # Don't capture - let it print directly
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Script {script_name} failed with exit code {result.returncode}")

    return result


def extract_zones():
    """
    Extract zone centroids and boundaries from shapefile.

    Auto-detects .shp file in data/ folder.
    """
    _run_script('extract_zones.py')


def extract_zones_pop():
    """
    Extract zones and fetch population data (US only).

    Auto-detects .shp file in data/ folder and adds population column.
    """
    _run_script('extract_zones_pop.py')


def clean_network():
    """
    Remove disconnected components from OSM networks.

    Cleans node.csv and link.csv from osm2gmns.
    """
    _run_script('clean_network.py')


def build_network():
    """
    Generate zone-connected network with connectors.

    Uses zone.csv, node.csv, link.csv to create connected_network/ folder.
    """
    _run_script('build_network.py')


def validate_basemap():
    """
    Verify spatial alignment of input files.

    Checks that node.csv, link.csv, and zone shapefile are in same area.
    """
    _run_script('validate_basemap.py')


def validate_network():
    """
    Check network structure and topology.

    Validates connected_network/ folder.
    """
    _run_script('validate_network.py')


def validate_accessibility():
    """
    Analyze zone-to-zone connectivity.

    Uses TAPLite to compute accessibility matrix.
    """
    _run_script('validate_accessibility.py')


def validate_assignment():
    """
    Verify traffic assignment readiness.

    Checks VDF parameters in connected_network/ folder.
    """
    from .validate_assignment import run_validation
    run_validation()


def enhance_connectors():
    """
    Add connectors for poorly connected zones.

    Adds 10 connectors per zone with low accessibility.
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