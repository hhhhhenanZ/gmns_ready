"""
GMNS Ready - Professional toolkit for GMNS transportation networks
"""

__version__ = '0.0.7'
__author__ = 'Henan Zhu, Xuesong Zhou, Han Zheng'
__email__ = 'henanzhu@asu.edu'

import os
import sys
import subprocess


def _run_script(script_name):
    """Helper function to run a script and stream its output in real-time"""
    current_dir = os.path.dirname(__file__)
    script_path = os.path.join(current_dir, script_name)

    # Run script with output streaming to parent process
    # This ensures print statements appear immediately
    result = subprocess.run(
        [sys.executable, script_path],
        cwd=os.getcwd(),
        stdout=sys.stdout,  # Stream directly to console
        stderr=sys.stderr,  # Stream errors directly to console
    )

    # If script failed, show helpful error
    if result.returncode != 0:
        print("\n" + "=" * 70, file=sys.stderr)
        print(f"ERROR: {script_name} failed with exit code {result.returncode}", file=sys.stderr)
        print("=" * 70, file=sys.stderr)

        # Show common issues based on script
        if script_name == 'clean_network.py':
            print("Common causes:", file=sys.stderr)
            print("  - node.csv or link.csv not found in current directory", file=sys.stderr)
            print("  - Run this from directory containing node.csv and link.csv", file=sys.stderr)
        elif script_name == 'extract_zones.py':
            print("Common causes:", file=sys.stderr)
            print("  - data/ folder not found", file=sys.stderr)
            print("  - No .shp file in data/ folder", file=sys.stderr)
            print("  - Run this from directory containing data/ folder", file=sys.stderr)
        elif script_name == 'build_network.py':
            print("Common causes:", file=sys.stderr)
            print("  - zone.csv, node.csv, or link.csv not found", file=sys.stderr)
            print("  - Run this after extract_zones()", file=sys.stderr)
        elif script_name == 'validate_basemap.py':
            print("Common causes:", file=sys.stderr)
            print("  - node.csv, link.csv, or data/*.shp not found", file=sys.stderr)

        print("=" * 70, file=sys.stderr)
        raise RuntimeError(f"{script_name} failed with exit code {result.returncode}")

    return result


def extract_zones():
    """
    Extract zone centroids and boundaries from shapefile.

    Requirements:
        - data/ folder in current directory
        - .shp file in data/ folder

    Outputs:
        - zone.csv with zone centroids and boundaries
        - zone_boundaries_and_centroids.png visualization

    Example
    -------
    >>> import gmns_ready as gr
    >>> gr.extract_zones()
    """
    _run_script('extract_zones.py')


def extract_zones_pop():
    """
    Extract zones and fetch population data (US only).

    Requirements:
        - data/ folder in current directory
        - .shp file in data/ folder (US census tracts)

    Outputs:
        - zone.csv with zone centroids, boundaries, and population

    Example
    -------
    >>> import gmns_ready as gr
    >>> gr.extract_zones_pop()
    """
    _run_script('extract_zones_pop.py')


def clean_network():
    """
    Remove disconnected components from OSM networks.

    Requirements:
        - node.csv in current directory (from osm2gmns)
        - link.csv in current directory (from osm2gmns)

    Outputs:
        - osm_network_connectivity_check/ folder with:
          - node.csv (cleaned)
          - link.csv (cleaned)
          - network_connectivity_analysis.png
          - isolated_components_detail.png

    Example
    -------
    >>> import gmns_ready as gr
    >>> gr.clean_network()
    """
    _run_script('clean_network.py')


def build_network():
    """
    Generate zone-connected network with connectors.

    Requirements:
        - zone.csv (from extract_zones)
        - node.csv (from osm2gmns or clean_network)
        - link.csv (from osm2gmns or clean_network)

    Outputs:
        - connected_network/ folder with:
          - node.csv (network + zones + activity nodes)
          - link.csv (roads + connectors)
          - activity_node.csv
          - connector_links.csv

    Example
    -------
    >>> import gmns_ready as gr
    >>> gr.build_network()
    """
    _run_script('build_network.py')


def validate_basemap():
    """
    Verify spatial alignment of input files.

    Requirements:
        - node.csv in current directory
        - link.csv in current directory
        - data/*.shp (zone shapefile)

    Outputs:
        - data/base_map_validation_report.json

    Example
    -------
    >>> import gmns_ready as gr
    >>> gr.validate_basemap()
    """
    _run_script('validate_basemap.py')


def validate_network():
    """
    Check network structure and topology.

    Requirements:
        - connected_network/node.csv
        - connected_network/link.csv

    Outputs:
        - connected_network/network_validation_report.json

    Example
    -------
    >>> import gmns_ready as gr
    >>> gr.validate_network()
    """
    _run_script('validate_network.py')


def validate_accessibility():
    """
    Analyze zone-to-zone connectivity using TAPLite.

    Requirements:
        - connected_network/node.csv
        - connected_network/link.csv

    Outputs:
        - connected_network/accessibility_validation_report.json
        - connected_network/zone_accessibility.csv

    Example
    -------
    >>> import gmns_ready as gr
    >>> gr.validate_accessibility()
    """
    _run_script('validate_accessibility.py')


def validate_assignment():
    """
    Verify traffic assignment readiness.

    Requirements:
        - connected_network/node.csv
        - connected_network/link.csv

    Outputs:
        - connected_network/assignment_validation_summary.json

    Example
    -------
    >>> import gmns_ready as gr
    >>> gr.validate_assignment()
    """
    from .validate_assignment import run_validation
    success = run_validation()
    if not success:
        raise RuntimeError("Assignment validation failed. Check the report for details.")


def enhance_connectors():
    """
    Add connectors for poorly connected zones.

    Requirements:
        - connected_network/node.csv
        - connected_network/link.csv
        - connected_network/zone_accessibility.csv (from validate_accessibility)

    Outputs:
        - connected_network/link_updated.csv
        - connected_network/connector_editor_report.txt

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