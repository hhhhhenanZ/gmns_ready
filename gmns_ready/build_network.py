# -*- coding: utf-8 -*-
"""
Updated connector generation script
Activities always connect to nearest zone
Zones without activities connect to physical network
Created on Mon Nov  3 10:50:14 2025
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

# ============================================================================
# CONFIGURATION
# ============================================================================
# For zone → road network connections
# Set to a number (e.g., 5000) to limit search radius in meters
# Set to None for unlimited distance (always connects to nearest link)
#MAX_SEARCH_RADIUS_METERS_ZONES = 5000   # or None for no limit

MAX_SEARCH_RADIUS_METERS_ZONES = None

# Get current directory
current_dir = os.getcwd()
current_path = os.path.join(current_dir)
output_path = os.path.join(current_dir, "connected_network")
os.makedirs(output_path, exist_ok=True)

link_file = os.path.join(current_path, "link.csv")
node_file = os.path.join(current_path, "node.csv")
node_taz_file = os.path.join(current_path, "zone.csv")

# Import CSV files as DataFrames
link_df = pd.read_csv(link_file)
node_df = pd.read_csv(node_file)
node_taz_df = pd.read_csv(node_taz_file)

# Start timing
start_time = time.time()


print("CONNECTOR GENERATION")
print(f"Configuration:")
print(f"  - Activity nodes: Always connect to nearest zone")
if MAX_SEARCH_RADIUS_METERS_ZONES is None:
    print(f"  - Zone nodes: Always connect to nearest network link (no limit)")
else:
    print(f"  - Zone nodes: Connect to network within {MAX_SEARCH_RADIUS_METERS_ZONES}m radius")



# %%
def process_and_save_activity_node_data(node_df, node_taz_df, output_path=None):
    """
    Processes node_df by adding new_node_id and filtering rows with non-null zone_id, 
    then saves the filtered DataFrame (activity_node_df) to a CSV file.
    """
    print("\nProcessing node data...")
    max_node_id_taz = node_taz_df['node_id'].max()
    min_node_id = node_df['node_id'].min()
    
    node_df['new_node_id'] = node_df['node_id'] + max_node_id_taz - min_node_id + 1
    
    activity_node_df = node_df[node_df['zone_id'].notnull()]
    common_node_df = node_df[node_df['zone_id'].isnull()]
    
    print(f"  Activity nodes: {len(activity_node_df)}")
    print(f"  Regular nodes: {len(common_node_df)}")
    
    # Save to output
    activity_node_df.to_csv(os.path.join(output_path, "activity_node.csv"), index=False)
    #common_node_df.to_csv(os.path.join(output_path, "common_node.csv"), index=False)
    
    return node_df, activity_node_df, common_node_df


updated_node_df, activity_node_df, common_node_df = process_and_save_activity_node_data(
    node_df, node_taz_df, output_path
)


#%%
def update_link_df_with_new_node_ids(link_df, updated_node_df):
    """
    Returns a copy of link_df with from_node_id and to_node_id replaced by new_node_id values.
    """
    print("\nUpdating link node IDs...")
    updated_link_df = link_df.copy()
    node_id_map = updated_node_df.set_index('node_id')['new_node_id'].to_dict()
    updated_link_df['from_node_id'] = updated_link_df['from_node_id'].map(node_id_map)
    updated_link_df['to_node_id'] = updated_link_df['to_node_id'].map(node_id_map)
    
    missing_from = updated_link_df['from_node_id'].isna().sum()
    missing_to = updated_link_df['to_node_id'].isna().sum()
    if missing_from > 0 or missing_to > 0:
        print(f"  Warning: {missing_from} from_node_ids and {missing_to} to_node_ids could not be mapped.")
    
    return updated_link_df


updated_link_df = update_link_df_with_new_node_ids(link_df, updated_node_df)


#%%
def generate_connector_links(activity_node_df, node_taz_df, updated_link_df, updated_node_df, 
                             zone_to_network_radius, output_path=None):
    """
    Generate bi-directional connector links.
    - Activity nodes: Always connect to nearest zone
    - Zones without activities: Connect to road network within radius
    """
    connector_links = []
    zones_with_activities = set()
    
    print("\n" + "="*10)
    print("STEP 1: Connecting activity nodes to zones...")
    print("="*10)
    
    # Prepare geometries
    has_boundary_geometry = 'boundary_geometry' in node_taz_df.columns
    
    if has_boundary_geometry:
        print("  Using boundary-based matching")
        if node_taz_df["boundary_geometry"].dtype == object:
            node_taz_df["boundary_geometry"] = node_taz_df["boundary_geometry"].apply(wkt.loads)
        node_taz_df["boundary_geometry"] = node_taz_df["boundary_geometry"].apply(lambda geom: geom.buffer(0.0001))
    
    if node_taz_df["geometry"].dtype == object:
        node_taz_df["geometry"] = node_taz_df["geometry"].apply(wkt.loads)
    if not isinstance(node_taz_df, gpd.GeoDataFrame):
        node_taz_df = gpd.GeoDataFrame(node_taz_df, geometry="geometry", crs="EPSG:4326")
    
    if updated_link_df["geometry"].dtype == object:
        updated_link_df["geometry"] = updated_link_df["geometry"].apply(wkt.loads)
    if not isinstance(updated_link_df, gpd.GeoDataFrame):
        updated_link_df = gpd.GeoDataFrame(updated_link_df, geometry="geometry", crs="EPSG:4326")
    
    # Build spatial index
    print("  Building spatial index...")
    link_sindex = updated_link_df.sindex
    
    # Create node coordinate lookup
    node_coord_dict = {}
    for _, node in updated_node_df.iterrows():
        node_coord_dict[node["new_node_id"]] = (node["x_coord"], node["y_coord"])
    
    # Connect activity nodes to nearest zone (always)
    for _, activity in activity_node_df.iterrows():
        act_id = activity["new_node_id"]
        act_point = Point(activity["x_coord"], activity["y_coord"])
        
        matched_zone = None
        match_distance = None
        
        # Try boundary-based matching if boundary_geometry exists
        if has_boundary_geometry:
            for _, zone in node_taz_df.iterrows():
                if zone["boundary_geometry"].contains(act_point):
                    matched_zone = zone
                    match_distance = geodesic((act_point.y, act_point.x), 
                                             (zone["geometry"].y, zone["geometry"].x)).meters
                    break
        
        # If no boundary match, find nearest zone
        if matched_zone is None:
            min_distance = float('inf')
            nearest_zone = None
            
            for _, zone in node_taz_df.iterrows():
                distance = geodesic((act_point.y, act_point.x), 
                                  (zone["geometry"].y, zone["geometry"].x)).meters
                if distance < min_distance:
                    min_distance = distance
                    nearest_zone = zone
            
            matched_zone = nearest_zone
            match_distance = min_distance
        
        taz_id = matched_zone["node_id"]
        taz_point = matched_zone["geometry"]
        zones_with_activities.add(taz_id)
        
        # Create bi-directional connectors
        for from_id, to_id, from_pt, to_pt in [
            (taz_id, act_id, taz_point, act_point),
            (act_id, taz_id, act_point, taz_point)
        ]:
            geometry = f"LINESTRING ({from_pt.x} {from_pt.y}, {to_pt.x} {to_pt.y})"
            length = round(geodesic((from_pt.y, from_pt.x), (to_pt.y, to_pt.x)).meters, 2)
            connector_links.append({
                "link_id": len(connector_links) + 1,
                "from_node_id": from_id,
                "to_node_id": to_id,
                "dir_flag": 1,
                "length": length,
                "lanes": 1,
                "free_speed": 90,
                "capacity": 99999,
                "link_type_name": "connector",
                "link_type": 0,
                "geometry": geometry,
                "allowed_uses": "auto",
                "from_biway": 1,
                "is_link": 0
            })
    
    print(f"  ✓ Connected {len(activity_node_df)} activity nodes to zones")
    print(f"  ✓ {len(zones_with_activities)} zones have activity connectors")
    
    # Helper function: Find nearest link within search radius
    def find_nearest_link_in_radius(zone_centroid, zone_id, search_radius):
        """Find the nearest high-level link within the search radius using spatial index.
        If search_radius is None, finds nearest link with no distance limit."""
        
        if search_radius is None:
            # No limit - search all links
            possible_matches = updated_link_df
        else:
            # Limited search using spatial index
            search_radius_degrees = search_radius / 111320.0
            
            minx = zone_centroid.x - search_radius_degrees
            maxx = zone_centroid.x + search_radius_degrees
            miny = zone_centroid.y - search_radius_degrees
            maxy = zone_centroid.y + search_radius_degrees
            search_box = box(minx, miny, maxx, maxy)
            
            possible_matches_index = list(link_sindex.intersection(search_box.bounds))
            possible_matches = updated_link_df.iloc[possible_matches_index]
        
        if possible_matches.empty:
            return None
        
        best_link = None
        best_link_distance = float('inf')
        
        for idx, link in possible_matches.iterrows():
            origin_node_id = link["from_node_id"]
            
            if origin_node_id not in node_coord_dict:
                continue
            
            origin_x, origin_y = node_coord_dict[origin_node_id]
            origin_point = Point(origin_x, origin_y)
            
            distance = geodesic((zone_centroid.y, zone_centroid.x), 
                              (origin_point.y, origin_point.x)).meters
            
            # Skip if beyond radius (only when radius is set)
            if search_radius is not None and distance > search_radius:
                continue
            
            # Prefer high-level links (type 1, 2, 3)
            if link["link_type"] in [1, 2, 3]:
                if best_link is None or \
                   link["link_type"] < best_link["link_type"] or \
                   (link["link_type"] == best_link["link_type"] and distance < best_link_distance):
                    best_link = link
                    best_link_distance = distance
            elif best_link is None:
                if distance < best_link_distance:
                    best_link = link
                    best_link_distance = distance
        
        return best_link
    
    # Connect zones WITHOUT activities to physical road network
    print("\n" + "="*10)
    print("STEP 2: Connecting zones to physical road network...")
    print("="*10)
    
    zones_without_activities = [z for _, z in node_taz_df.iterrows() 
                                if z["node_id"] not in zones_with_activities]
    
    print(f"  Zones to connect: {len(zones_without_activities)}")
    
    zones_beyond_search_radius = []
    
    for zone_row in zones_without_activities:
        taz_id = zone_row["node_id"]
        zone_centroid = zone_row["geometry"]
        
        best_link = None
        
        # Try boundary-based matching first
        if has_boundary_geometry:
            zone_boundary = zone_row["boundary_geometry"]
            
            possible_matches_index = list(link_sindex.intersection(zone_boundary.bounds))
            zone_links = updated_link_df.iloc[possible_matches_index]
            zone_links = zone_links[zone_links.intersects(zone_boundary)]
            
            if not zone_links.empty:
                high_level_zone_links = zone_links[zone_links["link_type"].isin([1, 2, 3])]
                
                if high_level_zone_links.empty:
                    best_link = zone_links.loc[zone_links["link_type"].idxmin()]
                else:
                    best_link = high_level_zone_links.loc[high_level_zone_links["link_type"].idxmin()]
        
        # Radius search if no boundary match
        if best_link is None:
            best_link = find_nearest_link_in_radius(zone_centroid, taz_id, zone_to_network_radius)
            
            if best_link is None:
                zones_beyond_search_radius.append(taz_id)
                continue
        
        origin_node_id = best_link["from_node_id"]
        
        if origin_node_id not in node_coord_dict:
            print(f"  ⚠️ Could not find origin node {origin_node_id}. Skipping zone {taz_id}.")
            continue
        
        origin_x, origin_y = node_coord_dict[origin_node_id]
        origin_point = Point(origin_x, origin_y)
        
        # Create bi-directional connectors
        for from_id, to_id, from_pt, to_pt in [
            (taz_id, origin_node_id, zone_centroid, origin_point),
            (origin_node_id, taz_id, origin_point, zone_centroid)
        ]:
            geometry = f"LINESTRING ({from_pt.x} {from_pt.y}, {to_pt.x} {to_pt.y})"
            length = round(geodesic((from_pt.y, from_pt.x), (to_pt.y, to_pt.x)).meters, 2)
            connector_links.append({
                "link_id": len(connector_links) + 1,
                "from_node_id": from_id,
                "to_node_id": to_id,
                "dir_flag": 1,
                "length": length,
                "lanes": 1,
                "free_speed": 90,
                "capacity": 99999,
                "link_type_name": "connector",
                "link_type": 0,
                "geometry": geometry,
                "allowed_uses": "auto",
                "from_biway": 1,
                "is_link": 0
            })
    
    connected = len(zones_without_activities) - len(zones_beyond_search_radius)
    print(f"  ✓ Connected {connected}/{len(zones_without_activities)} zones to network")
    
    if zones_beyond_search_radius:
        if zone_to_network_radius is None:
            print(f"  Warning: {len(zones_beyond_search_radius)} zones could not be connected")
        else:
            print(f"  {len(zones_beyond_search_radius)} zones beyond {zone_to_network_radius}m radius")
        print(f"     Zone IDs: {zones_beyond_search_radius}")
    
    # Create final connector DataFrame
    connector_df = pd.DataFrame(connector_links)
    connector_df["vdf_toll"] = 0
    connector_df["allowed_uses"] = None
    connector_df["vdf_alpha"] = 0.15
    connector_df["vdf_beta"] = 4
    connector_df["vdf_plf"] = 1
    connector_df["vdf_length_mi"] = (connector_df["length"] / 1609).round(2)
    connector_df["vdf_free_speed_mph"] = (((connector_df["free_speed"] / 1.60934) / 5).round() * 5)
    connector_df["free_speed_in_mph_raw"] = round(connector_df["vdf_free_speed_mph"] / 5) * 5
    connector_df["vdf_fftt"] = ((connector_df["length"] / connector_df["free_speed"]) * 0.06).round(2)
    
    other_columns = ['ref_volume', 'base_volume', 'base_vol_auto', 'restricted_turn_nodes']
    for other_column in other_columns:
        connector_df[other_column] = None
    
    print(f"\n✓ Total connector links generated: {len(connector_df)}")
    
    if output_path:
        output_file = os.path.join(output_path, "connector_links.csv")
        connector_df.to_csv(output_file, index=False)
        print(f"  Saved: {output_file}")
    
    return connector_df


# Generate connectors
connector_links_df = generate_connector_links(
    activity_node_df, node_taz_df, updated_link_df, updated_node_df, 
    MAX_SEARCH_RADIUS_METERS_ZONES, output_path
)


#%%
def update_and_merge_links(updated_link_df, connector_links_df, output_path):
    """
    Merges updated_link_df with connector_links_df and saves as link.csv
    """
    print("\n" + "="*10)
    print("Merging links...")
    print("="*10)
    
    if updated_link_df['from_node_id'].isnull().any() or updated_link_df['to_node_id'].isnull().any():
        print("  Warning: Some from_node_id or to_node_id in updated_link_df are null.")
    
    # Add VDF columns
    updated_link_df["vdf_toll"] = 0
    updated_link_df["allowed_uses"] = None
    updated_link_df["vdf_alpha"] = 0.15
    updated_link_df["vdf_beta"] = 4
    updated_link_df["vdf_plf"] = 1
    updated_link_df["vdf_length_mi"] = (updated_link_df["length"] / 1609).round(2)
    updated_link_df["vdf_free_speed_mph"] = (((updated_link_df["free_speed"] / 1.60934) / 5).round() * 5)
    updated_link_df["free_speed_in_mph_raw"] = round(updated_link_df["vdf_free_speed_mph"] / 5) * 5
    updated_link_df["vdf_fftt"] = ((updated_link_df["length"] / updated_link_df["free_speed"]) * 0.06).round(2)
    
    other_columns = ['ref_volume', 'base_volume', 'base_vol_auto', 'restricted_turn_nodes']
    for other_column in other_columns:
        updated_link_df[other_column] = None
    
    # Align columns
    all_columns = set(updated_link_df.columns).union(connector_links_df.columns)
    
    for col in all_columns:
        if col not in updated_link_df.columns:
            updated_link_df[col] = None
        if col not in connector_links_df.columns:
            connector_links_df[col] = None
    
    connector_links_df = connector_links_df[updated_link_df.columns]
    
    # Merge
    final_link_df = pd.concat([updated_link_df, connector_links_df], ignore_index=True)
    final_link_df = final_link_df.sort_values(by=['from_node_id', 'to_node_id']).reset_index(drop=True)
    final_link_df['link_id'] = range(1, len(final_link_df) + 1)
    
    # Clean up
    columns_to_remove = ["VDF_fftt", "VDF_toll_auto", "notes", "toll"]
    final_link_df.drop(columns=[col for col in columns_to_remove if col in final_link_df.columns], inplace=True)
    final_link_df['allowed_uses'] = 'drive'
    
    # Save as link.csv
    output_file = os.path.join(output_path, "link.csv")
    final_link_df.to_csv(output_file, index=False)
    print(f"  ✓ Saved: {output_file}")
    
    return final_link_df


final_link_df = update_and_merge_links(updated_link_df, connector_links_df, output_path)


#%%
def create_updated_node_df(updated_node_df, node_taz_df, output_path):
    """
    Creates updated node DataFrame and saves as node.csv
    """
    print("\n" + "="*10)
    print("Creating updated node file...")
    print("="*10)
    
    updated_node_df_copy = updated_node_df.copy()
    node_taz_df_copy = node_taz_df.copy()
    
    # Rename columns
    updated_node_df_copy = updated_node_df_copy.rename(columns={'node_id': 'old_node_id'})
    updated_node_df_copy = updated_node_df_copy.rename(columns={'new_node_id': 'node_id'})
    updated_node_df_copy['zone_id'] = None
    
    # Remove boundary_geometry if exists
    if 'boundary_geometry' in node_taz_df_copy.columns:
        node_taz_df_copy = node_taz_df_copy.drop(columns=['boundary_geometry'])
    
    # Merge
    Node_Updated_df = pd.concat([node_taz_df_copy, updated_node_df_copy], ignore_index=True)
    Node_Updated_df = Node_Updated_df.sort_values(by=['node_id']).reset_index(drop=True)
    
    if 'ctrl_type' in Node_Updated_df.columns:
        Node_Updated_df = Node_Updated_df.drop(columns=['ctrl_type'])
    
    # Fix geometry column
    for i in range(len(Node_Updated_df)):
        geometry_value = Node_Updated_df.loc[i, 'geometry']
        
        needs_geometry = False
        
        if pd.isna(geometry_value):
            needs_geometry = True
        elif isinstance(geometry_value, str):
            if geometry_value.strip() == '':
                needs_geometry = True
        elif hasattr(geometry_value, 'is_empty'):
            if geometry_value.is_empty:
                needs_geometry = True
        else:
            needs_geometry = True
        
        if needs_geometry:
            x_coord = Node_Updated_df.loc[i, 'x_coord']
            y_coord = Node_Updated_df.loc[i, 'y_coord']
            Node_Updated_df.loc[i, 'geometry'] = f"POINT ({x_coord} {y_coord})"
    
    # Save as node.csv
    output_file = os.path.join(output_path, "node.csv")
    Node_Updated_df.to_csv(output_file, index=False)
    print(f"  ✓ Saved: {output_file}")
    
    return Node_Updated_df


final_node_df = create_updated_node_df(updated_node_df, node_taz_df, output_path)

# Print final summary
end_time = time.time()
elapsed_time = end_time - start_time

print("\n" + "="*10)
print("COMPLETION SUMMARY")
print("="*10)
print(f"Total execution time: {elapsed_time:.2f} seconds")
print(f"Output directory: {output_path}")
print(f"Files created:")
print(f"  - node.csv")
print(f"  - link.csv")
print(f"  - activity_node.csv")
print(f"  - connector_links.csv")
print("="*10)