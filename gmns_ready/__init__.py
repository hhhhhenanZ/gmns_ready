"""
GMNS Ready - Professional toolkit for GMNS transportation networks
"""

__version__ = '0.1.0'
__author__ = 'Henan Zhu, Xuesong Zhou, Han Zheng'
__email__ = 'henanzhu@asu.edu, xzhou74@asu.edu'

import os
import sys
import subprocess
import io


def _run_script(script_name):
    """Helper function to run a script and show its output (works in all environments)"""
    current_dir = os.path.dirname(__file__)
    script_path = os.path.join(current_dir, script_name)

    # Check if we're in an interactive environment (Jupyter/Spyder/IPython)
    # These environments have special stdout that doesn't support fileno()
    is_interactive = (
            hasattr(sys.stdout, 'fileno') and
            callable(getattr(sys.stdout, 'fileno', None))
    )

    try:
        if is_interactive:
            # Try direct streaming (works in terminal)
            result = subprocess.run(
                [sys.executable, script_path],
                cwd=os.getcwd(),
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
        else:
            raise io.UnsupportedOperation("stdout doesn't support fileno")
    except (io.UnsupportedOperation, AttributeError, OSError):
        # Fall back to capture and print (works in Jupyter/Spyder)
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
        )

        # Print captured output
        if result.stdout:
            print(result.stdout, end='')
        if result.stderr:
            print(result.stderr, end='', file=sys.stderr)

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


def build_network(zone_search_radius=1000, link_df=None, node_df=None, node_taz_df=None,
                  input_path=None, output_path=None):
    """
    Generate zone-connected network with connectors.

    Requirements:
        - zone.csv (from extract_zones)
        - node.csv (from osm2gmns or clean_network)
        - link.csv (from osm2gmns or clean_network)

    Parameters:
    -----------
    zone_search_radius : float or None, default=1000
        Search radius in meters for connecting zones to road network.
        - Set to 500, 1000, 1500, etc. for limited search radius
        - Set to None for unlimited search (always find nearest link)
        - Recommended: 1000 for urban areas, 1500 for suburban

    link_df : pd.DataFrame, optional
        Link dataframe. If None, reads from input_path/link.csv

    node_df : pd.DataFrame, optional
        Node dataframe. If None, reads from input_path/node.csv

    node_taz_df : pd.DataFrame, optional
        Zone dataframe. If None, reads from input_path/zone.csv

    input_path : str, optional
        Path to input CSV files. Default is current directory

    output_path : str, optional
        Path for output files. Default is current_dir/connected_network

    Outputs:
        - connected_network/ folder with:
          - node.csv (network + zones + activity nodes)
          - link.csv (roads + connectors)
          - activity_node.csv
          - connector_links.csv

    Returns:
    --------
    tuple : (final_link_df, final_node_df, connector_df)
        Generated network dataframes

    Examples:
    ---------
    >>> import gmns_ready as gr

    >>> # Default 1000m search radius
    >>> gr.build_network()

    >>> # Custom search radius
    >>> gr.build_network(zone_search_radius=500)

    >>> # Unlimited search (always find nearest link)
    >>> gr.build_network(zone_search_radius=None)

    >>> # With dataframes (for programmatic use)
    >>> link_df, node_df, connector_df = gr.build_network(
    ...     zone_search_radius=1000,
    ...     link_df=link_df,
    ...     node_df=node_df,
    ...     node_taz_df=zone_df
    ... )
    """
    from .build_network import build_network as _build_network
    return _build_network(zone_search_radius, link_df, node_df, node_taz_df,
                          input_path, output_path)


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
    Analyze zone-to-zone connectivity using DTALite.

    Requirements:
        - DTALite package (pip install DTALite)
        - connected_network/node.csv
        - connected_network/link.csv
        - settings.csv

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


def enhance_connectors(search_radius=1000, accessibility_threshold=0.10,
                       min_connectors=6, input_path=None, output_path=None):
    """
    Add connectors for poorly connected zones.

    Requirements:
        - connected_network/node.csv
        - connected_network/link.csv
        - connected_network/zone_accessibility.csv (from validate_accessibility)

    Parameters:
    -----------
    search_radius : int, default=1000
        Maximum search radius in meters for finding candidate links.
        - Recommended: 500, 1000, 1500
        - Larger radius = more connection options but less precise

    accessibility_threshold : float, default=0.10
        Connectivity threshold as percentage of total zones (e.g., 0.10 = 10%).
        Zones connecting to fewer than this percentage are enhanced.

    min_connectors : int, default=6
        Minimum total connectors to add per problematic zone.
        Distributed across different link types (highways, arterials, collectors, local).

    input_path : str, optional
        Path containing connected_network directory. Default is current directory.

    output_path : str, optional
        Output directory for enhanced files. Default is input_path/connected_network.

    Outputs:
        - connected_network/link_updated.csv (enhanced link file)
        - connected_network/connector_editor_report.txt (enhancement details)

    Returns:
    --------
    tuple : (final_link_df, report_dict)
        - final_link_df: Enhanced link dataframe
        - report_dict: Dictionary with enhancement details

    Examples:
    ---------
    >>> import gmns_ready as gr

    >>> # Default: 1000m search radius, 10% threshold
    >>> gr.enhance_connectors()

    >>> # Smaller search radius for dense urban areas
    >>> gr.enhance_connectors(search_radius=500)

    >>> # More aggressive enhancement (15% threshold, 8 min connectors)
    >>> gr.enhance_connectors(
    ...     search_radius=1500,
    ...     accessibility_threshold=0.15,
    ...     min_connectors=8
    ... )
    """
    from .enhance_connectors import enhance_connectors as _enhance_connectors
    return _enhance_connectors(search_radius, accessibility_threshold,
                               min_connectors, input_path, output_path)


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