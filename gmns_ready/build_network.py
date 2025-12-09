# -*- coding: utf-8 -*-
"""
Updated connector generation script
Activities always connect to nearest zone
Zones without activities connect to lower-level network links
@author: hnzhu
"""
import pandas as pd
import numpy as np
from geopy.distance import geodesic
import time
import os
from shapely import wkt
from shapely.geometry import Point, box
import geopandas as gpd


def process_node_data(node_df, node_taz_df, output_path):
    """Add new_node_id and separate activity nodes"""
    print("\nProcessing node data...")
    max_taz_id = node_taz_df['node_id'].max()
    min_node_id = node_df['node_id'].min()
    
    node_df['new_node_id'] = node_df['node_id'] + max_taz_id - min_node_id + 1
    activity_node_df = node_df[node_df['zone_id'].notnull()]
    common_node_df = node_df[node_df['zone_id'].isnull()]
    
    print(f"  Activity nodes: {len(activity_node_df)}")
    print(f"  Regular nodes: {len(common_node_df)}")
    
    activity_node_df.to_csv(os.path.join(output_path, "activity_node.csv"), index=False)
    return node_df, activity_node_df, common_node_df


def update_link_node_ids(link_df, node_df):
    """Update link node IDs with new_node_id mapping"""
    print("\nUpdating link node IDs...")
    updated_link = link_df.copy()
    node_map = node_df.set_index('node_id')['new_node_id'].to_dict()
    updated_link['from_node_id'] = updated_link['from_node_id'].map(node_map)
    updated_link['to_node_id'] = updated_link['to_node_id'].map(node_map)
    
    missing = updated_link[['from_node_id', 'to_node_id']].isnull().sum()
    if missing.any():
        print(f"  Warning: {missing['from_node_id']} from_node_ids, {missing['to_node_id']} to_node_ids unmapped")
    
    return updated_link


def generate_connectors(activity_node_df, node_taz_df, updated_link_df, updated_node_df, 
                        zone_search_radius, output_path):
    """
    Generate bi-directional connector links
    - Activity nodes: Always connect to nearest zone
    - Zones without activities: Connect to last two link_types within search radius
    
    Parameters:
    -----------
    zone_search_radius : float or None
        Search radius in meters for zone-to-network connections
        None = unlimited (always find nearest link)
        Recommended: 500, 1000, etc.
    """
    connector_links = []
    zones_with_activities = set()
    
    print("\n" + "="*80)
    print("CONNECTOR GENERATION")
    print("="*80)
    print(f"Configuration:")
    print(f"  - Activity nodes: Always connect to nearest zone")
    if zone_search_radius is None:
        print(f"  - Zone nodes: Always connect to nearest network link (no limit)")
    else:
        print(f"  - Zone nodes: Connect to network within {zone_search_radius}m radius")
    
    # Prepare geometries
    has_boundary = 'boundary_geometry' in node_taz_df.columns
    
    if has_boundary:
        print("  - Using boundary-based matching")
        if node_taz_df["boundary_geometry"].dtype == object:
            node_taz_df["boundary_geometry"] = node_taz_df["boundary_geometry"].apply(wkt.loads)
        node_taz_df["boundary_geometry"] = node_taz_df["boundary_geometry"].apply(lambda g: g.buffer(0.0001))
    
    # Convert to GeoDataFrames (FIXED: Proper assignment)
    if node_taz_df["geometry"].dtype == object:
        node_taz_df["geometry"] = node_taz_df["geometry"].apply(wkt.loads)
    if not isinstance(node_taz_df, gpd.GeoDataFrame):
        node_taz_df = gpd.GeoDataFrame(node_taz_df, geometry="geometry", crs="EPSG:4326")
    
    if updated_link_df["geometry"].dtype == object:
        updated_link_df["geometry"] = updated_link_df["geometry"].apply(wkt.loads)
    if not isinstance(updated_link_df, gpd.GeoDataFrame):
        updated_link_df = gpd.GeoDataFrame(updated_link_df, geometry="geometry", crs="EPSG:4326")
    
    # Build spatial index and node coordinate lookup
    print("\n" + "="*80)
    print("STEP 1: Building spatial index...")
    print("="*80)
    link_sindex = updated_link_df.sindex
    node_coords = {row["new_node_id"]: (row["x_coord"], row["y_coord"]) 
                   for _, row in updated_node_df.iterrows()}
    
    # Determine lower-level link types (last two types)
    all_link_types = sorted(updated_link_df['link_type'].unique())
    lower_level_types = all_link_types[-2:] if len(all_link_types) >= 2 else all_link_types
    print(f"  Available link_types: {all_link_types}")
    print(f"  Lower-level types for zone connections: {lower_level_types}")
    
    # STEP 2: Connect activity nodes to zones
    print("\n" + "="*80)
    print("STEP 2: Connecting activity nodes to zones...")
    print("="*80)
    
    for _, activity in activity_node_df.iterrows():
        act_id = activity["new_node_id"]
        act_point = Point(activity["x_coord"], activity["y_coord"])
        
        matched_zone = None
        
        # Try boundary matching first
        if has_boundary:
            for _, zone in node_taz_df.iterrows():
                if zone["boundary_geometry"].contains(act_point):
                    matched_zone = zone
                    break
        
        # Find nearest zone if no boundary match
        if matched_zone is None:
            distances = node_taz_df.apply(
                lambda z: geodesic((act_point.y, act_point.x), 
                                  (z["geometry"].y, z["geometry"].x)).meters, axis=1)
            matched_zone = node_taz_df.loc[distances.idxmin()]
        
        taz_id = matched_zone["node_id"]
        taz_point = matched_zone["geometry"]
        zones_with_activities.add(taz_id)
        
        # Create bi-directional connectors
        for from_id, to_id, from_pt, to_pt in [
            (taz_id, act_id, taz_point, act_point),
            (act_id, taz_id, act_point, taz_point)
        ]:
            connector_links.append({
                "link_id": len(connector_links) + 1,
                "from_node_id": from_id,
                "to_node_id": to_id,
                "dir_flag": 1,
                "length": round(geodesic((from_pt.y, from_pt.x), (to_pt.y, to_pt.x)).meters, 2),
                "lanes": 1,
                "free_speed": 90,
                "capacity": 99999,
                "link_type_name": "connector",
                "link_type": 0,
                "geometry": f"LINESTRING ({from_pt.x} {from_pt.y}, {to_pt.x} {to_pt.y})",
                "from_biway": 1,
                "is_link": 0
            })
    
    print(f"  [OK] Connected {len(activity_node_df)} activity nodes to zones")
    print(f"  [OK] {len(zones_with_activities)} zones have activity connectors")
    
    # STEP 3: Connect zones without activities to road network
    print("\n" + "="*80)
    print("STEP 3: Connecting zones to physical road network...")
    print("="*80)
    
    zones_without_activities = [z for _, z in node_taz_df.iterrows() 
                                if z["node_id"] not in zones_with_activities]
    print(f"  Zones to connect: {len(zones_without_activities)}")
    
    zones_beyond_radius = []
    
    def find_best_link(zone_centroid, search_radius, prefer_types):
        """Find nearest link preferring specified types within radius"""
        if search_radius is None:
            possible = updated_link_df
        else:
            # Spatial search
            deg_radius = search_radius / 111320.0
            search_box = box(zone_centroid.x - deg_radius, zone_centroid.y - deg_radius,
                           zone_centroid.x + deg_radius, zone_centroid.y + deg_radius)
            possible_idx = list(link_sindex.intersection(search_box.bounds))
            possible = updated_link_df.iloc[possible_idx]
        
        if possible.empty:
            return None
        
        best = None
        best_dist = float('inf')
        
        for idx, link in possible.iterrows():
            if link["from_node_id"] not in node_coords:
                continue
            
            origin = Point(*node_coords[link["from_node_id"]])
            dist = geodesic((zone_centroid.y, zone_centroid.x), (origin.y, origin.x)).meters
            
            if search_radius and dist > search_radius:
                continue
            
            # Prefer lower-level types, then nearest (FIXED: Clear logic)
            is_preferred = link["link_type"] in prefer_types
            is_best_preferred = (best is not None) and (best["link_type"] in prefer_types)
            
            # Selection logic:
            # 1. If no best yet, select this link
            # 2. If this is preferred and best is not, select this
            # 3. If both preferred or both not preferred, select nearest
            if best is None:
                best = link
                best_dist = dist
            elif is_preferred and not is_best_preferred:
                best = link
                best_dist = dist
            elif is_preferred == is_best_preferred and dist < best_dist:
                best = link
                best_dist = dist
        
        return best
    
    for zone in zones_without_activities:
        taz_id = zone["node_id"]
        zone_centroid = zone["geometry"]
        best_link = None
        
        # Try boundary-based matching first
        if has_boundary:
            zone_boundary = zone["boundary_geometry"]
            possible_idx = list(link_sindex.intersection(zone_boundary.bounds))
            boundary_links = updated_link_df.iloc[possible_idx]
            boundary_links = boundary_links[boundary_links.intersects(zone_boundary)]
            
            if not boundary_links.empty:
                # Prefer lower-level types
                lower_links = boundary_links[boundary_links["link_type"].isin(lower_level_types)]
                best_link = (lower_links if not lower_links.empty else boundary_links).loc[
                    (lower_links if not lower_links.empty else boundary_links)["link_type"].idxmax()]
        
        # Radius search if no boundary match
        if best_link is None:
            best_link = find_best_link(zone_centroid, zone_search_radius, lower_level_types)
            
            if best_link is None:
                zones_beyond_radius.append(taz_id)
                continue
        
        origin_node_id = best_link["from_node_id"]
        if origin_node_id not in node_coords:
            print(f"  [WARNING] Missing origin node {origin_node_id}. Skipping zone {taz_id}.")
            continue
        
        origin_point = Point(*node_coords[origin_node_id])
        
        # Create bi-directional connectors
        for from_id, to_id, from_pt, to_pt in [
            (taz_id, origin_node_id, zone_centroid, origin_point),
            (origin_node_id, taz_id, origin_point, zone_centroid)
        ]:
            connector_links.append({
                "link_id": len(connector_links) + 1,
                "from_node_id": from_id,
                "to_node_id": to_id,
                "dir_flag": 1,
                "length": round(geodesic((from_pt.y, from_pt.x), (to_pt.y, to_pt.x)).meters, 2),
                "lanes": 1,
                "free_speed": 90,
                "capacity": 99999,
                "link_type_name": "connector",
                "link_type": 0,
                "geometry": f"LINESTRING ({from_pt.x} {from_pt.y}, {to_pt.x} {to_pt.y})",
                "from_biway": 1,
                "is_link": 0
            })
    
    connected = len(zones_without_activities) - len(zones_beyond_radius)
    print(f"  [OK] Connected {connected}/{len(zones_without_activities)} zones to network")
    
    if zones_beyond_radius:
        msg = "could not be connected" if zone_search_radius is None else f"beyond {zone_search_radius}m radius"
        print(f"  [{len(zones_beyond_radius)} zones {msg}]")
        print(f"     Zone IDs: {zones_beyond_radius}")
    
    # Create connector DataFrame
    connector_df = pd.DataFrame(connector_links)
    
    # Add VDF columns
    connector_df["vdf_toll"] = 0
    connector_df["allowed_uses"] = None
    connector_df["vdf_alpha"] = 0.15
    connector_df["vdf_beta"] = 4
    connector_df["vdf_plf"] = 1
    connector_df["vdf_length_mi"] = (connector_df["length"] / 1609).round(2)
    connector_df["vdf_free_speed_mph"] = (((connector_df["free_speed"] / 1.60934) / 5).round() * 5)
    connector_df["free_speed_in_mph_raw"] = round(connector_df["vdf_free_speed_mph"] / 5) * 5
    connector_df["vdf_fftt"] = ((connector_df["length"] / connector_df["free_speed"]) * 0.06).round(2)
    
    for col in ['ref_volume', 'base_volume', 'base_vol_auto', 'restricted_turn_nodes']:
        connector_df[col] = None
    
    print(f"\n[OK] Total connector links: {len(connector_df)}")
    
    output_file = os.path.join(output_path, "connector_links.csv")
    connector_df.to_csv(output_file, index=False)
    print(f"  Saved: {output_file}")
    
    return connector_df


def merge_links(updated_link_df, connector_df, output_path):
    """Merge network and connector links"""
    print("\n" + "="*80)
    print("Merging links...")
    print("="*80)
    
    # Add VDF columns to network links
    updated_link_df["vdf_toll"] = 0
    updated_link_df["allowed_uses"] = None
    updated_link_df["vdf_alpha"] = 0.15
    updated_link_df["vdf_beta"] = 4
    updated_link_df["vdf_plf"] = 1
    updated_link_df["vdf_length_mi"] = (updated_link_df["length"] / 1609).round(2)
    updated_link_df["vdf_free_speed_mph"] = (((updated_link_df["free_speed"] / 1.60934) / 5).round() * 5)
    updated_link_df["free_speed_in_mph_raw"] = round(updated_link_df["vdf_free_speed_mph"] / 5) * 5
    updated_link_df["vdf_fftt"] = ((updated_link_df["length"] / updated_link_df["free_speed"]) * 0.06).round(2)
    
    for col in ['ref_volume', 'base_volume', 'base_vol_auto', 'restricted_turn_nodes']:
        updated_link_df[col] = None
    
    # Align columns
    all_cols = set(updated_link_df.columns).union(connector_df.columns)
    for col in all_cols:
        if col not in updated_link_df.columns:
            updated_link_df[col] = None
        if col not in connector_df.columns:
            connector_df[col] = None
    
    connector_df = connector_df[updated_link_df.columns]
    
    # Merge and sort
    final_link = pd.concat([updated_link_df, connector_df], ignore_index=True)
    final_link = final_link.sort_values(by=['from_node_id', 'to_node_id']).reset_index(drop=True)
    final_link['link_id'] = range(1, len(final_link) + 1)
    
    # Cleanup
    final_link.drop(columns=[c for c in ["VDF_fftt", "VDF_toll_auto", "notes", "toll"] 
                            if c in final_link.columns], inplace=True)
    final_link['allowed_uses'] = 'drive'
    
    output_file = os.path.join(output_path, "link.csv")
    final_link.to_csv(output_file, index=False)
    print(f"  [OK] Saved: {output_file}")
    
    return final_link


def create_node_file(updated_node_df, node_taz_df, output_path):
    """Create final node file"""
    print("\n" + "="*80)
    print("Creating node file...")
    print("="*80)
    
    # Prepare node DataFrame
    node_copy = updated_node_df.copy()
    node_copy = node_copy.rename(columns={'node_id': 'old_node_id', 'new_node_id': 'node_id'})
    node_copy['zone_id'] = None
    
    # Prepare zone DataFrame
    zone_copy = node_taz_df.copy()
    if 'boundary_geometry' in zone_copy.columns:
        zone_copy = zone_copy.drop(columns=['boundary_geometry'])
    
    # Merge
    final_node = pd.concat([zone_copy, node_copy], ignore_index=True)
    final_node = final_node.sort_values(by=['node_id']).reset_index(drop=True)
    
    if 'ctrl_type' in final_node.columns:
        final_node = final_node.drop(columns=['ctrl_type'])
    
    # Fix geometry
    for i in range(len(final_node)):
        geom = final_node.loc[i, 'geometry']
        needs_fix = pd.isna(geom) or \
                   (isinstance(geom, str) and geom.strip() == '') or \
                   (hasattr(geom, 'is_empty') and geom.is_empty)
        
        if needs_fix:
            x, y = final_node.loc[i, 'x_coord'], final_node.loc[i, 'y_coord']
            final_node.loc[i, 'geometry'] = f"POINT ({x} {y})"
    
    output_file = os.path.join(output_path, "node.csv")
    final_node.to_csv(output_file, index=False)
    print(f"  [OK] Saved: {output_file}")
    
    return final_node


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def build_network(zone_search_radius=1000, link_df=None, node_df=None, node_taz_df=None, 
                  input_path=None, output_path=None):
    """
    Build connected transportation network with activity nodes and zone connectors.
    
    Parameters:
    -----------
    zone_search_radius : float or None, default=1000
        Search radius in meters for connecting zones without activities to road network.
        - Set to 500, 1000, 1500, etc. for limited search radius
        - Set to None for unlimited search (always find nearest link)
    
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
        
    Returns:
    --------
    tuple : (final_link_df, final_node_df, connector_df)
        Generated network dataframes
        
    Examples:
    ---------
    >>> # Using dataframes (package usage)
    >>> import gmns_ready as gr
    >>> link_df, node_df, connector_df = gr.build_network(
    ...     zone_search_radius=500, 
    ...     link_df=link_df, 
    ...     node_df=node_df, 
    ...     node_taz_df=zone_df
    ... )
    
    >>> # Using file paths (script usage)
    >>> link_df, node_df, connector_df = gr.build_network(
    ...     zone_search_radius=1000,
    ...     input_path="./data",
    ...     output_path="./output"
    ... )
    
    >>> # Default: reads from current directory
    >>> link_df, node_df, connector_df = gr.build_network()
    """
    start = time.time()
    
    # Set paths
    if input_path is None:
        input_path = os.getcwd()
    if output_path is None:
        output_path = os.path.join(input_path, "connected_network")
    os.makedirs(output_path, exist_ok=True)
    
    # Load data if not provided
    if link_df is None:
        link_df = pd.read_csv(os.path.join(input_path, "link.csv"))
    if node_df is None:
        node_df = pd.read_csv(os.path.join(input_path, "node.csv"))
    if node_taz_df is None:
        node_taz_df = pd.read_csv(os.path.join(input_path, "zone.csv"))
    
    # Process data
    updated_node_df, activity_node_df, common_node_df = process_node_data(
        node_df, node_taz_df, output_path
    )
    updated_link_df = update_link_node_ids(link_df, updated_node_df)
    
    # Generate connectors
    connector_df = generate_connectors(
        activity_node_df, node_taz_df, updated_link_df, updated_node_df,
        zone_search_radius, output_path
    )
    
    # Merge and create final files
    final_link_df = merge_links(updated_link_df, connector_df, output_path)
    final_node_df = create_node_file(updated_node_df, node_taz_df, output_path)
    
    # Summary
    elapsed = time.time() - start
    print("\n" + "="*80)
    print("COMPLETION SUMMARY")
    print("="*80)
    print(f"Execution time: {elapsed:.2f} seconds")
    print(f"Output directory: {output_path}")
    print(f"Files created: node.csv, link.csv, activity_node.csv, connector_links.csv")
    print("="*80)
    
    return final_link_df, final_node_df, connector_df


# ============================================================================
# SCRIPT EXECUTION (when run directly)
# ============================================================================

if __name__ == "__main__":
    # Run with default settings when executed as a script
    # Files will be read from current directory
    # Output will be saved to ./connected_network/
    build_network(zone_search_radius=1000)