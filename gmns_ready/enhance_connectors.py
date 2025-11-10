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

# ============================================================================
# CONFIGURATION
# ============================================================================
CONNECTED_NETWORK_DIR = os.path.join(os.getcwd(), "connected_network")
ACCESSIBILITY_THRESHOLD = 0.10  # 10% of total zones
MAX_SEARCH_RADIUS_METERS = 8000  # Search within 8km

# Connector targets by link type (total = 10)
CONNECTOR_TARGETS = {
    1: 3,  # Add 3 connectors to Type 1 (Highways/Freeways)
    2: 3,  # Add 3 connectors to Type 2 (Arterials)
    3: 2,  # Add 2 connectors to Type 3 (Collectors)
    4: 2   # Add 2 connectors to Type 4+ (Local roads)
}
MIN_TOTAL_CONNECTORS = 10

print("="*70)
print("CONNECTOR EDITOR - IMPROVING ZONE ACCESSIBILITY")
print("="*70)
print(f"Working directory: {CONNECTED_NETWORK_DIR}")
print(f"Threshold: {ACCESSIBILITY_THRESHOLD*100}% of total zones")
print(f"Search radius: {MAX_SEARCH_RADIUS_METERS}m")
print(f"Connectors per zone: {MIN_TOTAL_CONNECTORS}")
print("="*70)

# ============================================================================
# LOAD DATA
# ============================================================================
print("\n[1/5] Loading data...")

accessibility_file = os.path.join(CONNECTED_NETWORK_DIR, "zone_accessibility.csv")
link_file = os.path.join(CONNECTED_NETWORK_DIR, "link.csv")
node_file = os.path.join(CONNECTED_NETWORK_DIR, "node.csv")

accessibility_df = pd.read_csv(accessibility_file)
link_df = pd.read_csv(link_file)
node_df = pd.read_csv(node_file)

print(f"  Loaded {len(accessibility_df)} zones")
print(f"  Loaded {len(link_df)} links")
print(f"  Loaded {len(node_df)} nodes")

# ============================================================================
# IDENTIFY PROBLEMATIC ZONES
# ============================================================================
print("\n[2/5] Identifying poorly connected zones...")

total_zones = len(accessibility_df)
threshold_count = int(total_zones * ACCESSIBILITY_THRESHOLD)

problematic_zones = accessibility_df[
    (accessibility_df['origin_count'] < threshold_count) | 
    (accessibility_df['destination_count'] < threshold_count)
]['zone_id'].tolist()

print(f"  Threshold: {threshold_count} zones ({ACCESSIBILITY_THRESHOLD*100}%)")
print(f"  Found {len(problematic_zones)} poorly connected zones")
print(f"  Zone IDs: {problematic_zones}")

# ============================================================================
# PREPARE GEOMETRIES AND SPATIAL INDEX
# ============================================================================
print("\n[3/5] Preparing spatial data...")

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
        print(f"  ⚠️ Warning: Zone {zone_id} not found in node.csv")

print(f"  Built spatial index")
print(f"  Found {len(zone_coords)}/{len(problematic_zones)} zone coordinates")

# ============================================================================
# FIND EXISTING CONNECTORS TO AVOID DUPLICATES
# ============================================================================
print("\n[4/5] Analyzing existing connectors...")

# Connectors have link_type = 0
existing_connectors = link_df[link_df['link_type'] == 0].copy()
existing_connections = set()

for _, conn in existing_connectors.iterrows():
    # Store both directions
    existing_connections.add((conn['from_node_id'], conn['to_node_id']))
    existing_connections.add((conn['to_node_id'], conn['from_node_id']))

print(f"  Found {len(existing_connectors)} existing connectors")
print(f"  Unique connections: {len(existing_connections)}")

# ============================================================================
# GENERATE NEW CONNECTORS
# ============================================================================
print("\n[5/5] Generating new connectors...")

new_connectors = []
zone_connector_report = {}

for idx, zone_id in enumerate(problematic_zones, 1):
    if zone_id not in zone_coords:
        print(f"  ⚠️ Zone {zone_id} not found in node coordinates, skipping")
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
    search_radius_deg = MAX_SEARCH_RADIUS_METERS / 111320.0
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
        if distance > MAX_SEARCH_RADIUS_METERS:
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
    if connectors_added < MIN_TOTAL_CONNECTORS:
        needed = MIN_TOTAL_CONNECTORS - connectors_added
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

print(f"\n  ✓ Generated {len(new_connectors)} new connector links")

# ============================================================================
# MERGE AND SAVE
# ============================================================================
print("\n[6/6] Merging and saving...")

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
output_file = os.path.join(CONNECTED_NETWORK_DIR, "link_updated.csv")
final_link_df.to_csv(output_file, index=False)
print(f"  ✓ Saved: {output_file}")

# ============================================================================
# GENERATE REPORT
# ============================================================================
print("\n[7/7] Generating report...")

timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
report_lines = []
report_lines.append("="*70)
report_lines.append("CONNECTOR EDITOR - EXECUTION REPORT")
report_lines.append("="*70)
report_lines.append(f"Execution time: {timestamp}")
report_lines.append(f"Working directory: {CONNECTED_NETWORK_DIR}")
report_lines.append("")
report_lines.append("CONFIGURATION:")
report_lines.append(f"  Accessibility threshold: {ACCESSIBILITY_THRESHOLD*100}% ({threshold_count} zones)")
report_lines.append(f"  Search radius: {MAX_SEARCH_RADIUS_METERS}m")
report_lines.append(f"  Target connectors per zone: {MIN_TOTAL_CONNECTORS}")
report_lines.append(f"    - Type 1: {CONNECTOR_TARGETS[1]} connectors")
report_lines.append(f"    - Type 2: {CONNECTOR_TARGETS[2]} connectors")
report_lines.append(f"    - Type 3: {CONNECTOR_TARGETS[3]} connectors")
report_lines.append(f"    - Type 4+: {CONNECTOR_TARGETS[4]} connectors")
report_lines.append("")
report_lines.append("RESULTS:")
report_lines.append(f"  Problematic zones identified: {len(problematic_zones)}")
report_lines.append(f"  New connector links generated: {len(new_connectors)}")
report_lines.append(f"  Total links in updated file: {len(final_link_df)}")
report_lines.append("")
report_lines.append("="*70)
report_lines.append("NEW CONNECTORS BY ZONE")
report_lines.append("="*70)

for zone_id in sorted(zone_connector_report.keys()):
    report = zone_connector_report[zone_id]
    total = (len(report['type_1']) + len(report['type_2']) + 
             len(report['type_3']) + len(report['type_4_plus']))
    
    report_lines.append(f"\nZone {zone_id}: {total} new connectors")
    report_lines.append("-" * 70)
    
    if report['type_1']:
        report_lines.append(f"  Type 1 (Highway/Freeway): {len(report['type_1'])} connectors")
        for conn in report['type_1']:
            report_lines.append(f"    → Origin Node {conn['origin_node']}: {conn['distance_m']}m")
    
    if report['type_2']:
        report_lines.append(f"  Type 2 (Arterial): {len(report['type_2'])} connectors")
        for conn in report['type_2']:
            report_lines.append(f"    → Origin Node {conn['origin_node']}: {conn['distance_m']}m")
    
    if report['type_3']:
        report_lines.append(f"  Type 3 (Collector): {len(report['type_3'])} connectors")
        for conn in report['type_3']:
            report_lines.append(f"    → Origin Node {conn['origin_node']}: {conn['distance_m']}m")
    
    if report['type_4_plus']:
        report_lines.append(f"  Type 4+ (Local): {len(report['type_4_plus'])} connectors")
        for conn in report['type_4_plus']:
            report_lines.append(f"    → Origin Node {conn['origin_node']} (Type {conn['link_type']}): {conn['distance_m']}m")

report_lines.append("")
report_lines.append("="*70)
report_lines.append("END OF REPORT")
report_lines.append("="*70)

# Save report
report_file = os.path.join(CONNECTED_NETWORK_DIR, "connector_editor_report.txt")
with open(report_file, 'w') as f:
    f.write('\n'.join(report_lines))

print(f"  ✓ Saved: {report_file}")

# Print summary to console
print("\n" + "="*70)
print("EXECUTION SUMMARY")
print("="*70)
print(f"Problematic zones: {len(problematic_zones)}")
print(f"New connectors: {len(new_connectors)}")
print(f"Output file: link_updated.csv")
print(f"Report file: connector_editor_report.txt")
print("="*70)
print("\nDone!")