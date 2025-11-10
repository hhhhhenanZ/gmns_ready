"""
@author: hnzhu
"""

import csv
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import sys
from shapely.geometry import Point, Polygon
import os

# Get current directory
current_dir = os.getcwd()
# Path to the 'data' folder
data_folder = os.path.join(current_dir, "data")

# Automatically find the first .shp file in the data folder
shapefile_path = None
for file in os.listdir(data_folder):
    if file.endswith(".shp"):
        shapefile_path = os.path.join(data_folder, file)
        break

# Raise error if no shapefile is found
if shapefile_path is None:
    raise FileNotFoundError("No .shp file found in the 'data' folder.")

# Function to calculate centroids while preserving original geometry
def calculate_centroids(gdf):
    # Reproject to WGS84 (EPSG:4326) for output
    if gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    
    # Project to a metric CRS for accurate centroid calculation
    gdf_projected = gdf.to_crs(epsg=3857)
    
    # Calculate centroids in projected coordinates
    centroids = gdf_projected.geometry.centroid
    
    # Reproject centroids back to EPSG:4326
    centroids_latlon = gpd.GeoSeries(centroids, crs=3857).to_crs(epsg=4326)
    
    # Add centroid coordinates to the original dataframe
    gdf = gdf.copy()
    gdf['x_coord'] = centroids_latlon.x
    gdf['y_coord'] = centroids_latlon.y
    
    # Store original boundary geometry in a separate column
    gdf['boundary_geometry'] = gdf['geometry']
    
    # Create new geometry column from centroid coordinates (Point geometry)
    gdf['geometry'] = gdf.apply(lambda row: Point(row['x_coord'], row['y_coord']), axis=1)
    gdf = gpd.GeoDataFrame(gdf, geometry='geometry', crs='EPSG:4326')
    
    return gdf



# Function to save centroids to CSV
def save_centroids_to_csv(gdf, output_csv_path, taz_column):
    nodes = []
    node_id_counter = 1
    
    for idx, row in gdf.iterrows():
        if row['geometry'] is None:
            continue
        
        # Get the boundary geometry as WKT
        geometry_wkt = row['geometry'].wkt.replace("\n", " ")
        boundary_wkt = row['boundary_geometry'].wkt.replace("\n", " ")
        TAZ_id = str(row[taz_column])
        
        nodes.append({
            "name": TAZ_id,
            "node_id": node_id_counter,
            "osm_node_id": "",
            "x_coord": row['x_coord'],
            "y_coord": row['y_coord'],
            "zone_id": node_id_counter,
            "TAZ_ID": TAZ_id,
            "geometry": geometry_wkt,
            "boundary_geometry": boundary_wkt,
            "notes": " "
        })
        node_id_counter += 1
    
    nodes_df = pd.DataFrame(nodes)
    nodes_df = nodes_df.dropna()
    nodes_df.to_csv(output_csv_path, index=False, quoting=csv.QUOTE_ALL, encoding='utf-8')
    print(f"Centroid and boundary data saved to {output_csv_path}")


# Plot both boundaries and centroids
def plot_taz_with_boundaries_and_centroids(gdf, taz_column):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8))
    
    # Plot boundaries using the boundary_geometry column
    boundary_gdf = gdf.copy()
    boundary_gdf['geometry'] = boundary_gdf['boundary_geometry']
    boundary_gdf = gpd.GeoDataFrame(boundary_gdf, geometry='geometry', crs=gdf.crs)
    
    boundary_gdf.plot(ax=ax1, color='lightblue', edgecolor='black', alpha=0.7)
    ax1.set_title("Zone Boundaries", fontsize=16)
    ax1.set_xlabel("Longitude", fontsize=12)
    ax1.set_ylabel("Latitude", fontsize=12)
    ax1.grid(True)
    
    # Add zone labels to boundary plot
    for idx, row in boundary_gdf.iterrows():
        centroid = row['geometry'].centroid
        ax1.text(centroid.x, centroid.y, str(row[taz_column]),
                fontsize=8, ha='center', color='red', weight='bold')
    
    # Plot centroids using the main geometry column (now points)
    gdf.plot(ax=ax2, color='red', markersize=50)
    ax2.set_title("Zone Centroids", fontsize=16)
    ax2.set_xlabel("Longitude", fontsize=12)
    ax2.set_ylabel("Latitude", fontsize=12)
    ax2.grid(True)
    
    # Add zone labels to centroid plot
    for idx, row in gdf.iterrows():
        ax2.text(row['geometry'].x, row['geometry'].y, str(row[taz_column]),
                fontsize=8, ha='center', color='blue')
    
    plt.tight_layout()
    plt.savefig("zone_boundaries_and_centroids.png", dpi=300)
    plt.show()

# Function to print summary statistics
def print_summary_stats(gdf, taz_column):
    print("\n" + "="*50)
    print("SUMMARY STATISTICS")
    print("="*50)
    print(f"Total number of zones: {len(gdf)}")
    print(f"Zone ID column: {taz_column}")
    print(f"CRS: {gdf.crs}")
    print("Centroid coordinates calculated and boundaries preserved.")

# Main execution
try:
    gdf = gpd.read_file(shapefile_path)
    print("Shapefile loaded successfully.")
except Exception as e:
    print(f"Failed to load shapefile: {e}")
    sys.exit()

if gdf.crs is None:
    print("CRS is missing. Setting default CRS to EPSG:2868.")
    gdf.set_crs(epsg=2868, inplace=True)

print("Current CRS:", gdf.crs)

if gdf.crs.to_epsg() != 4326:
    gdf = gdf.to_crs(epsg=4326)
    print("Reprojected CRS:", gdf.crs)

print("Available columns:", gdf.columns)

# Function to automatically detect TAZ/zone identifier column
def detect_taz_column(gdf):
    """
    Automatically detect the zone identifier column based on common patterns
    """
    columns = gdf.columns.tolist()
    
    # Common patterns for zone identifiers (in order of priority)
    # Start with TRACTCE since it's most common for your use case
    patterns = [
        # Census tract patterns (most common first)
        'TRACTCE', 'TRACTCE20', 'TRACTCE10', 'TRACT', 'TRACT_ID',
        # GEOID patterns  
        'GEOID', 'GEOID20', 'GEOID10', 'GEOID_TRACT',
        # TAZ patterns
        'TAZ', 'TAZ_ID', 'TAZID', 'TAZ_NUM', 'TAZ_CODE',
        # Block group patterns
        'BLKGRPCE', 'BLKGRP', 'BG', 'BLOCKGROUP',
        # General zone patterns
        'ZONE', 'ZONE_ID', 'ZONEID', 'ZONE_NUM', 'ZONE_CODE',
        # FIPS codes
        'FIPS', 'FIPSCODE', 'STATEFP', 'COUNTYFP',
        # Generic ID patterns
        'ID', 'OBJECTID', 'FID', 'AREA_ID', 'REGION_ID'
    ]
    
    # Look for exact matches first
    for pattern in patterns:
        if pattern in columns:
            return pattern
    
    # Look for partial matches (case insensitive)
    for pattern in patterns:
        for col in columns:
            if pattern.lower() in col.upper():
                return col
    
    # If no pattern matches, find columns with unique values that could be IDs
    candidates = []
    for col in columns:
        try:
            if col == 'geometry':
                continue
                
            unique_count = gdf[col].nunique()
            total_count = len(gdf)
            uniqueness_ratio = unique_count / total_count
            
            # Check if values look like IDs
            sample_values = gdf[col].dropna().head(3).astype(str)
            looks_like_id = any(val.replace('.', '').isdigit() or 
                              (val.isalnum() and len(val) <= 20) 
                              for val in sample_values)
            
            if uniqueness_ratio >= 0.8 and looks_like_id:
                candidates.append({
                    'column': col,
                    'uniqueness': uniqueness_ratio,
                    'sample_values': sample_values.tolist()
                })
        except:
            continue
    
    if candidates:
        # Sort by uniqueness ratio
        candidates.sort(key=lambda x: x['uniqueness'], reverse=True)
        return candidates[0]['column']
    
    return None

# Auto-detect TAZ column
taz_column = detect_taz_column(gdf)

if taz_column is None:
    print("\nCould not automatically detect zone identifier column.")
    print("Available columns:", list(gdf.columns))
    sys.exit()
else:
    print(f"Detected zone identifier column: '{taz_column}'")
    
    # Show sample values
    sample_values = gdf[taz_column].head(3).tolist()
    print(f"Sample values: {sample_values}")
    print(f"Total zones: {gdf[taz_column].nunique()}")

# Calculate centroids while preserving boundaries
gdf = calculate_centroids(gdf)

# Print summary statistics
print_summary_stats(gdf, taz_column)

# Plot both boundaries and centroids
plot_taz_with_boundaries_and_centroids(gdf, taz_column)


############# Save outputs ##############
output_csv_path = "zone.csv"
save_centroids_to_csv(gdf, output_csv_path, taz_column)
########################################



print(f"\nFile created: {output_csv_path}")
print(f"\nGeoDataFrame now has two geometries:")
print(f"- 'geometry' column: Point geometries (centroids) from x_coord, y_coord")
print(f"- 'boundary_geometry' column: Original polygon boundaries")
print(f"\nFor subsequent steps, you can:")
print(f"- Use gdf['geometry'] for centroid-based operations")
print(f"- Use gdf['boundary_geometry'] for boundary-based operations")
print(f"- Access both from the CSV via 'boundary_geometry' column (WKT format)")