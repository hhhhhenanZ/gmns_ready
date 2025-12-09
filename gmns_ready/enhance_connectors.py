# -*- coding: utf-8 -*-
"""
Connector Editor - Improves zone accessibility by adding connectors
Adds connectors to zones with poor accessibility (< 10% of total zones)
@author: hnzhu
"""
import pandas as pd
import numpy as np
from geopy.distance import geodesic
from shapely import wkt
from shapely.geometry import Point, box
import geopandas as gpd
import os
from datetime import datetime


def enhance_connectors(search_radius=1000, accessibility_threshold=0.10, 
                      min_connectors=6, input_path=None, output_path=None):
    """
    Improve zone accessibility by adding connectors to poorly connected zones.
    
    Parameters:
    -----------
    search_radius : int, default=1000
        Maximum search radius in meters for finding candidate links.
        Recommended: 500, 1000, 1500, etc.
    
    accessibility_threshold : float, default=0.10
        Threshold as percentage of total zones (e.g., 0.10 = 10%).
        Zones with connectivity below this threshold are enhanced.
    
    min_connectors : int, default=6
        Minimum total connectors to add per problematic zone.
    
    input_path : str, optional
        Path containing connected_network directory with:
        - zone_accessibility.csv
        - link.csv
        - node.csv
        Default is current directory.
    
    output_path : str, optional
        Output directory for enhanced files.
        Default is input_path/connected_network.
    
    Returns:
    --------
    tuple : (final_link_df, report_dict)
        - final_link_df: Enhanced link dataframe
        - report_dict: Dictionary with enhancement details
    
    Examples:
    ---------
    >>> # Default: 1000m search radius
    >>> link_df, report = gr.enhance_connectors()
    
    >>> # Custom search radius
    >>> link_df, report = gr.enhance_connectors(search_radius=500)
    
    >>> # Custom all parameters
    >>> link_df, report = gr.enhance_connectors(
    ...     search_radius=1500,
    ...     accessibility_threshold=0.15,
    ...     min_connectors=8
    ... )
    """
    
    # Connector targets by link type (distribute min_connectors)
    CONNECTOR_TARGETS = {
        1: 1,  # Type 1 (Highways/Freeways)
        2: 1,  # Type 2 (Arterials)
        3: 2,  # Type 3 (Collectors)
        4: 2   # Type 4+ (Local roads)
    }
    
    # Set paths
    if input_path is None:
        input_path = os.getcwd()
    
    connected_network_dir = os.path.join(input_path, "connected_network")
    
    if output_path is None:
        output_path = connected_network_dir
    
    print("="*80)
    print("CONNECTOR EDITOR - IMPROVING ZONE ACCESSIBILITY")
    print("="*80)
    print(f"Configuration:")
    print(f"  Working directory: {connected_network_dir}")
    print(f"  Accessibility threshold: {accessibility_threshold*100}% of total zones")
    print(f"  Search radius: {search_radius}m")
    print(f"  Min connectors per zone: {min_connectors}")
    print("="*80)
    
    # ========================================================================
    # LOAD DATA
    # ========================================================================
    print("\n[1/7] Loading data...")
    
    accessibility_file = os.path.join(connected_network_dir, "zone_accessibility.csv")
    link_file = os.path.join(connected_network_dir, "link.csv")
    node_file = os.path.join(connected_network_dir, "node.csv")
    
    if not os.path.exists(accessibility_file):
        raise FileNotFoundError(
            f"zone_accessibility.csv not found in {connected_network_dir}. "
            "Please run accessibility analysis first."
        )
    
    accessibility_df = pd.read_csv(accessibility_file)
    link_df = pd.read_csv(link_file)
    node_df = pd.read_csv(node_file)
    
    print(f"  Loaded {len(accessibility_df)} zones")
    print(f"  Loaded {len(link_df)} links")
    print(f"  Loaded {len(node_df)} nodes")
    
    # ========================================================================
    # IDENTIFY PROBLEMATIC ZONES
    # ========================================================================
    print("\n[2/7] Identifying poorly connected zones...")
    
    total_zones = len(accessibility_df)
    threshold_count = int(total_zones * accessibility_threshold)
    
    problematic_zones = accessibility_df[
        (accessibility_df['origin_count'] < threshold_count) | 
        (accessibility_df['destination_count'] < threshold_count)
    ]['zone_id'].tolist()
    
    print(f"  Threshold: {threshold_count} zones ({accessibility_threshold*100}%)")
    print(f"  Found {len(problematic_zones)} poorly connected zones")
    if problematic_zones:
        print(f"  Zone IDs: {problematic_zones}")
    
    if not problematic_zones:
        print("\n[OK] No poorly connected zones found. Network is well connected!")
        return link_df, {'problematic_zones': 0, 'new_connectors': 0}
    
    # ========================================================================
    # PREPARE GEOMETRIES AND SPATIAL INDEX
    # ========================================================================
    print("\n[3/7] Preparing spatial data...")
    
    # Convert geometries
    if link_df["geometry"].dtype == object:
        link_df["geometry"] = link_df["geometry"].apply(wkt.loads)
    if not isinstance(link_df, gpd.GeoDataFrame):
        link_df = gpd.GeoDataFrame(link_df, geometry="geometry", crs="EPSG:4326")
    
    # Build spatial index
    link_sindex = link_df.sindex
    
    # Create node coordinate lookup
    node_coords = {row["node_id"]: (row["x_coord"], row["y_coord"]) 
                   for _, row in node_df.iterrows()}
    
    # Get zone coordinates - zones are nodes where node_id equals zone_id
    zone_coords = {}
    for zone_id in problematic_zones:
        zone_node = node_df[node_df['node_id'] == zone_id]
        if not zone_node.empty:
            row = zone_node.iloc[0]
            zone_coords[zone_id] = Point(row["x_coord"], row["y_coord"])
        else:
            print(f"  [WARNING] Zone {zone_id} not found in node.csv")
    
    print(f"  Built spatial index")
    print(f"  Found {len(zone_coords)}/{len(problematic_zones)} zone coordinates")
    
    # ========================================================================
    # FIND EXISTING CONNECTORS TO AVOID DUPLICATES
    # ========================================================================
    print("\n[4/7] Analyzing existing connectors...")
    
    # Connectors have link_type = 0
    existing_connectors = link_df[link_df['link_type'] == 0].copy()
    existing_connections = set()
    
    for _, conn in existing_connectors.iterrows():
        # Store both directions
        existing_connections.add((conn['from_node_id'], conn['to_node_id']))
        existing_connections.add((conn['to_node_id'], conn['from_node_id']))
    
    print(f"  Found {len(existing_connectors)} existing connectors")
    print(f"  Unique connections: {len(existing_connections)}")
    
    # ========================================================================
    # GENERATE NEW CONNECTORS
    # ========================================================================
    print("\n[5/7] Generating new connectors...")
    
    new_connectors = []
    zone_connector_report = {}
    
    for idx, zone_id in enumerate(problematic_zones, 1):
        if zone_id not in zone_coords:
            print(f"  [WARNING] Zone {zone_id} not found in coordinates, skipping")
            continue
        
        print(f"  Processing zone {zone_id} ({idx}/{len(problematic_zones)})...", end='\r')
        
        zone_point = zone_coords[zone_id]
        zone_connector_report[zone_id] = {
            'type_1': [],
            'type_2': [],
            'type_3': [],
            'type_4_plus': []
        }
        
        # Use spatial index with bounding box for faster search
        search_radius_deg = search_radius / 111320.0
        minx = zone_point.x - search_radius_deg
        maxx = zone_point.x + search_radius_deg
        miny = zone_point.y - search_radius_deg
        maxy = zone_point.y + search_radius_deg
        
        search_box = box(minx, miny, maxx, maxy)
        
        # Get candidate links using spatial index
        possible_idx = list(link_sindex.intersection(search_box.bounds))
        candidate_links = link_df.iloc[possible_idx]
        
        # Find nearest links of each type within radius
        links_by_type = {1: [], 2: [], 3: [], 4: []}
        
        for _, link in candidate_links.iterrows():
            origin_id = link["from_node_id"]
            if origin_id not in node_coords:
                continue
            
            # Skip existing connectors
            if link['link_type'] == 0:
                continue
            
            # Check if connection already exists
            if (zone_id, origin_id) in existing_connections:
                continue
            
            origin_x, origin_y = node_coords[origin_id]
            origin_point = Point(origin_x, origin_y)
            
            distance = geodesic(
                (zone_point.y, zone_point.x),
                (origin_point.y, origin_point.x)
            ).meters
            
            # Skip if beyond search radius
            if distance > search_radius:
                continue
            
            link_type = link["link_type"]
            type_key = link_type if link_type <= 3 else 4
            
            links_by_type[type_key].append({
                'link': link,
                'origin_id': origin_id,
                'origin_point': origin_point,
                'distance': distance
            })
        
        # Sort each type by distance
        for type_key in links_by_type:
            links_by_type[type_key].sort(key=lambda x: x['distance'])
        
        # Add connectors based on targets
        connectors_added = 0
        
        for link_type, target_count in CONNECTOR_TARGETS.items():
            type_key = link_type if link_type <= 3 else 4
            available = links_by_type[type_key]
            
            for i in range(min(target_count, len(available))):
                link_info = available[i]
                origin_id = link_info['origin_id']
                origin_point = link_info['origin_point']
                distance = link_info['distance']
                
                # Create bi-directional connectors
                for from_id, to_id, from_pt, to_pt in [
                    (zone_id, origin_id, zone_point, origin_point),
                    (origin_id, zone_id, origin_point, zone_point)
                ]:
                    length = geodesic((from_pt.y, from_pt.x), (to_pt.y, to_pt.x)).meters
                    new_connectors.append({
                        "from_node_id": from_id,
                        "to_node_id": to_id,
                        "dir_flag": 1,
                        "length": round(length, 2),
                        "lanes": 1,
                        "free_speed": 90,
                        "capacity": 99999,
                        "link_type_name": "connector",
                        "link_type": 0,
                        "geometry": f"LINESTRING ({from_pt.x} {from_pt.y}, {to_pt.x} {to_pt.y})",
                        "allowed_uses": "drive",
                        "from_biway": 1,
                        "is_link": 0,
                        "vdf_toll": 0,
                        "vdf_alpha": 0.15,
                        "vdf_beta": 4,
                        "vdf_plf": 1,
                        "vdf_length_mi": round(length / 1609, 2),
                        "vdf_free_speed_mph": round(((90 / 1.60934) / 5)) * 5,
                        "free_speed_in_mph_raw": round(((90 / 1.60934) / 5)) * 5,
                        "vdf_fftt": round((length / 90) * 0.06, 2),
                        "ref_volume": None,
                        "base_volume": None,
                        "base_vol_auto": None,
                        "restricted_turn_nodes": None
                    })
                
                # Track for report (only outgoing connector)
                type_name = f'type_{link_type}' if link_type <= 3 else 'type_4_plus'
                zone_connector_report[zone_id][type_name].append({
                    'origin_node': origin_id,
                    'link_type': link_info['link']['link_type'],
                    'distance_m': round(distance, 2)
                })
                
                connectors_added += 1
                
                # Mark as used
                existing_connections.add((zone_id, origin_id))
                existing_connections.add((origin_id, zone_id))
        
        # Add more Type 4+ if needed to reach minimum
        if connectors_added < min_connectors:
            needed = min_connectors - connectors_added
            available = [x for x in links_by_type[4] 
                        if (zone_id, x['origin_id']) not in existing_connections]
            
            for i in range(min(needed, len(available))):
                link_info = available[i]
                origin_id = link_info['origin_id']
                origin_point = link_info['origin_point']
                distance = link_info['distance']
                
                for from_id, to_id, from_pt, to_pt in [
                    (zone_id, origin_id, zone_point, origin_point),
                    (origin_id, zone_id, origin_point, zone_point)
                ]:
                    length = geodesic((from_pt.y, from_pt.x), (to_pt.y, to_pt.x)).meters
                    new_connectors.append({
                        "from_node_id": from_id,
                        "to_node_id": to_id,
                        "dir_flag": 1,
                        "length": round(length, 2),
                        "lanes": 1,
                        "free_speed": 90,
                        "capacity": 99999,
                        "link_type_name": "connector",
                        "link_type": 0,
                        "geometry": f"LINESTRING ({from_pt.x} {from_pt.y}, {to_pt.x} {to_pt.y})",
                        "allowed_uses": "drive",
                        "from_biway": 1,
                        "is_link": 0,
                        "vdf_toll": 0,
                        "vdf_alpha": 0.15,
                        "vdf_beta": 4,
                        "vdf_plf": 1,
                        "vdf_length_mi": round(length / 1609, 2),
                        "vdf_free_speed_mph": round(((90 / 1.60934) / 5)) * 5,
                        "free_speed_in_mph_raw": round(((90 / 1.60934) / 5)) * 5,
                        "vdf_fftt": round((length / 90) * 0.06, 2),
                        "ref_volume": None,
                        "base_volume": None,
                        "base_vol_auto": None,
                        "restricted_turn_nodes": None
                    })
                
                zone_connector_report[zone_id]['type_4_plus'].append({
                    'origin_node': origin_id,
                    'link_type': link_info['link']['link_type'],
                    'distance_m': round(distance, 2)
                })
                
                connectors_added += 1
                existing_connections.add((zone_id, origin_id))
                existing_connections.add((origin_id, zone_id))
    
    print(f"\n  [OK] Generated {len(new_connectors)} new connector links")
    
    # ========================================================================
    # MERGE AND SAVE
    # ========================================================================
    print("\n[6/7] Merging and saving...")
    
    # Create DataFrame from new connectors
    new_connector_df = pd.DataFrame(new_connectors)
    
    # Align columns with existing link_df
    for col in link_df.columns:
        if col not in new_connector_df.columns:
            new_connector_df[col] = None
    
    new_connector_df = new_connector_df[link_df.columns]
    
    # Merge with existing links
    final_link_df = pd.concat([link_df, new_connector_df], ignore_index=True)
    
    # Sort and renumber link_id
    final_link_df = final_link_df.sort_values(
        by=['from_node_id', 'to_node_id']
    ).reset_index(drop=True)
    final_link_df['link_id'] = range(1, len(final_link_df) + 1)
    
    # Save updated links
    output_file = os.path.join(output_path, "link_enhanced.csv")
    final_link_df.to_csv(output_file, index=False)
    print(f"  [OK] Saved: {output_file}")
    
    # ========================================================================
    # GENERATE REPORT
    # ========================================================================
    print("\n[7/7] Generating report...")
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_lines = []
    report_lines.append("="*80)
    report_lines.append("CONNECTOR EDITOR - EXECUTION REPORT")
    report_lines.append("="*80)
    report_lines.append(f"Execution time: {timestamp}")
    report_lines.append(f"Working directory: {connected_network_dir}")
    report_lines.append("")
    report_lines.append("CONFIGURATION:")
    report_lines.append(f"  Accessibility threshold: {accessibility_threshold*100}% ({threshold_count} zones)")
    report_lines.append(f"  Search radius: {search_radius}m")
    report_lines.append(f"  Target connectors per zone: {min_connectors}")
    report_lines.append(f"    - Type 1: {CONNECTOR_TARGETS[1]} connectors")
    report_lines.append(f"    - Type 2: {CONNECTOR_TARGETS[2]} connectors")
    report_lines.append(f"    - Type 3: {CONNECTOR_TARGETS[3]} connectors")
    report_lines.append(f"    - Type 4+: {CONNECTOR_TARGETS[4]} connectors")
    report_lines.append("")
    report_lines.append("RESULTS:")
    report_lines.append(f"  Problematic zones identified: {len(problematic_zones)}")
    report_lines.append(f"  New connector links generated: {len(new_connectors)}")
    report_lines.append(f"  Total links in enhanced file: {len(final_link_df)}")
    report_lines.append("")
    report_lines.append("="*80)
    report_lines.append("NEW CONNECTORS BY ZONE")
    report_lines.append("="*80)
    
    for zone_id in sorted(zone_connector_report.keys()):
        report = zone_connector_report[zone_id]
        total = (len(report['type_1']) + len(report['type_2']) + 
                 len(report['type_3']) + len(report['type_4_plus']))
        
        report_lines.append(f"\nZone {zone_id}: {total} new connectors")
        report_lines.append("-" * 80)
        
        if report['type_1']:
            report_lines.append(f"  Type 1 (Highway/Freeway): {len(report['type_1'])} connectors")
            for conn in report['type_1']:
                report_lines.append(f"    -> Origin Node {conn['origin_node']}: {conn['distance_m']}m")
        
        if report['type_2']:
            report_lines.append(f"  Type 2 (Arterial): {len(report['type_2'])} connectors")
            for conn in report['type_2']:
                report_lines.append(f"    -> Origin Node {conn['origin_node']}: {conn['distance_m']}m")
        
        if report['type_3']:
            report_lines.append(f"  Type 3 (Collector): {len(report['type_3'])} connectors")
            for conn in report['type_3']:
                report_lines.append(f"    -> Origin Node {conn['origin_node']}: {conn['distance_m']}m")
        
        if report['type_4_plus']:
            report_lines.append(f"  Type 4+ (Local): {len(report['type_4_plus'])} connectors")
            for conn in report['type_4_plus']:
                report_lines.append(f"    -> Origin Node {conn['origin_node']} (Type {conn['link_type']}): {conn['distance_m']}m")
    
    report_lines.append("")
    report_lines.append("="*80)
    report_lines.append("END OF REPORT")
    report_lines.append("="*80)
    
    # Save report
    report_file = os.path.join(output_path, "connector_enhancement_report.txt")
    with open(report_file, 'w') as f:
        f.write('\n'.join(report_lines))
    
    print(f"  [OK] Saved: {report_file}")
    
    # Print summary to console
    print("\n" + "="*80)
    print("COMPLETION SUMMARY")
    print("="*80)
    print(f"Problematic zones: {len(problematic_zones)}")
    print(f"New connectors: {len(new_connectors)}")
    print(f"Output file: link_enhanced.csv")
    print(f"Report file: connector_enhancement_report.txt")
    print("="*80)
    
    # Create report dictionary
    report_dict = {
        'problematic_zones': len(problematic_zones),
        'new_connectors': len(new_connectors),
        'total_links': len(final_link_df),
        'zone_details': zone_connector_report,
        'output_file': output_file,
        'report_file': report_file
    }
    
    return final_link_df, report_dict


# ============================================================================
# SCRIPT EXECUTION (when run directly)
# ============================================================================

if __name__ == "__main__":
    # Run with default settings when executed as a script
    enhance_connectors(search_radius=1000)