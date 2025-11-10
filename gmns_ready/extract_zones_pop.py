# -*- coding: utf-8 -*-
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
import requests
import time
import warnings

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


def is_us_shapefile(gdf):
    """Detect if shapefile contains US census data."""
    us_indicators = 0
    total_checks = 0
    
    # Check 1: US-specific columns
    us_columns = ['STATEFP', 'COUNTYFP', 'TRACTCE', 'GEOID', 'GEOID20', 'GEOID10', 
                  'TRACTCE20', 'COUNTYFP20', 'STATEFP20']
    if any(col in gdf.columns for col in us_columns):
        us_indicators += 2
        total_checks += 2
    else:
        total_checks += 2
    
    # Check 2: GEOID format validation
    geoid_col = next((col for col in ['GEOID', 'GEOID20', 'GEOID10'] if col in gdf.columns), None)
    if geoid_col:
        sample_geoids = gdf[geoid_col].dropna().head(5).astype(str).tolist()
        valid_count = sum(1 for g in sample_geoids 
                         if len(g.strip()) == 11 and g.isdigit() and 1 <= int(g[:2]) <= 56)
        if valid_count >= 3:
            us_indicators += 2
        total_checks += 2
    
    # Check 3: Geographic bounds
    try:
        if gdf.crs is None:
            gdf_wgs84 = gdf.set_crs(epsg=4326)
        elif gdf.crs.to_epsg() != 4326:
            gdf_wgs84 = gdf.to_crs(epsg=4326)
        else:
            gdf_wgs84 = gdf
            
        bounds = gdf_wgs84.total_bounds
        minx, miny, maxx, maxy = bounds
        
        # Handle projected coordinates
        if abs(minx) > 180 or abs(maxx) > 180:
            try:
                gdf_wgs84 = gdf.set_crs(epsg=4269).to_crs(epsg=4326)
                bounds = gdf_wgs84.total_bounds
                minx, miny, maxx, maxy = bounds
            except:
                pass
        
        center_lon = (minx + maxx) / 2
        center_lat = (miny + maxy) / 2
        
        # US bounds (including Alaska, Hawaii, territories)
        us_lon_range = (-180, -60)
        us_lat_range = (15, 72)
        
        if (us_lon_range[0] <= center_lon <= us_lon_range[1] and 
            us_lat_range[0] <= center_lat <= us_lat_range[1]):
            us_indicators += 1
            
        # Continental US bonus
        if -125 <= center_lon <= -66 and 24 <= center_lat <= 50:
            us_indicators += 1
        
        total_checks += 2
    except:
        total_checks += 2
    
    # Check 4: Filename hints
    filename = os.path.basename(shapefile_path).lower()
    us_keywords = ['usa', 'census', 'tract', 'fips', 'chicago', 'illinois', 
                   'texas', 'california', 'florida', 'new york', 'los angeles',
                   'houston', 'phoenix', 'philadelphia', 'san', 'seattle']
    if any(keyword in filename for keyword in us_keywords):
        us_indicators += 1
    total_checks += 1
    
    confidence_ratio = us_indicators / total_checks if total_checks > 0 else 0
    return confidence_ratio >= 0.35


def geocode_to_census_tract(lat, lon, year=2020):
    """
    Use Census Geocoding API to get GEOID from lat/lon coordinates.
    Returns GEOID (11 digits) or None if not found.
    """
    base_url = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
    
    params = {
        'x': lon,
        'y': lat,
        'benchmark': 'Public_AR_Current',
        'vintage': f'Census{year}_Current',
        'format': 'json'
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'result' in data and 'geographies' in data['result']:
            geographies = data['result']['geographies']
            if 'Census Tracts' in geographies and len(geographies['Census Tracts']) > 0:
                tract_info = geographies['Census Tracts'][0]
                
                # Build GEOID from components
                state = tract_info.get('STATE', '')
                county = tract_info.get('COUNTY', '')
                tract = tract_info.get('TRACT', '')
                geoid = f"{state}{county}{tract}"
                
                if len(geoid) == 11 and geoid.isdigit():
                    return geoid
        
        return None
    except:
        return None


def add_geoids_via_geocoding(gdf, verbose=True):
    """
    Add GEOID column to GeoDataFrame by geocoding centroid coordinates.
    This enables population lookup for shapefiles without GEOID.
    """
    if verbose:
        print("No GEOID column found. Using Census Geocoding API to match geometries...")
    
    # Ensure we're in WGS84
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    
    # Calculate centroids for geocoding
    gdf_projected = gdf.to_crs(epsg=3857)
    centroids = gdf_projected.geometry.centroid
    centroids_wgs84 = gpd.GeoSeries(centroids, crs=3857).to_crs(epsg=4326)
    
    geoids = []
    total = len(gdf)
    
    if verbose:
        print(f"Geocoding {total} features (this may take a few minutes)...")
    
    for idx, centroid in enumerate(centroids_wgs84):
        if idx % 50 == 0 and verbose:
            print(f"  Progress: {idx}/{total} ({100*idx/total:.1f}%)")
        
        geoid = geocode_to_census_tract(centroid.y, centroid.x)
        geoids.append(geoid if geoid else '')
        
        # Be polite to the API - rate limiting
        time.sleep(0.2)  # 5 requests per second max
    
    gdf['GEOID_GEOCODED'] = geoids
    
    # Count successful matches
    matched = sum(1 for g in geoids if g)
    
    if verbose:
        print(f"  Geocoding complete: {matched}/{total} features matched ({100*matched/total:.1f}%)")
    
    return gdf, 'GEOID_GEOCODED'


def fetch_population_data(state_fips, county_fips=None, year=2022):
    """Fetch population from US Census Bureau API."""
    base_url = f"https://api.census.gov/data/{year}/acs/acs5"
    
    params = {
        "get": "B01003_001E,NAME",
        "for": "tract:*",
        "in": f"state:{state_fips}" + (f" county:{county_fips}" if county_fips else "")
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        headers = data[0]
        rows = data[1:]
        
        population_dict = {}
        for row in rows:
            state = row[headers.index('state')]
            county = row[headers.index('county')]
            tract = row[headers.index('tract')]
            geoid = f"{state}{county}{tract}"
            
            pop_value = row[headers.index('B01003_001E')]
            population = int(pop_value) if pop_value not in [None, '', '-666666666'] else 0
            population_dict[geoid] = population
        
        return population_dict
    except:
        return {}


def extract_geoid_components(geoid_str):
    """Extract state and county FIPS from GEOID."""
    geoid_str = str(geoid_str).strip()
    if len(geoid_str) >= 11:
        return geoid_str[:2], geoid_str[2:5]
    elif len(geoid_str) >= 5:
        return geoid_str[:2], geoid_str[2:5] if len(geoid_str) >= 5 else None
    return None, None


def get_population_for_tracts(gdf, geoid_column, year=2022, verbose=True):
    """Fetch population for all tracts."""
    state_counties = set()
    for idx, row in gdf.iterrows():
        geoid = str(row[geoid_column]).strip()
        if not geoid:  # Skip empty GEOIDs
            continue
        state_fips, county_fips = extract_geoid_components(geoid)
        if state_fips and county_fips:
            state_counties.add((state_fips, county_fips))
    
    if not state_counties:
        return {}
    
    if verbose:
        print(f"Fetching population data for {len(state_counties)} counties...")
    
    all_population_data = {}
    for i, (state_fips, county_fips) in enumerate(state_counties, 1):
        if verbose and len(state_counties) > 1:
            print(f"  County {i}/{len(state_counties)}")
        pop_data = fetch_population_data(state_fips, county_fips, year)
        all_population_data.update(pop_data)
        time.sleep(0.5)
    
    return all_population_data


def add_population_to_gdf(gdf, taz_column, year=2022, verbose=True):
    """Add population data to GeoDataFrame - FULLY AUTOMATED."""
    # Detect if US data
    is_us = is_us_shapefile(gdf)
    
    if not is_us:
        if verbose:
            warnings.warn(
                "Non-US region detected. Population data unavailable via US Census API. "
                "Setting population=0. For international data, consider: "
                "(1) Country-specific APIs (Statistics Canada, Eurostat, etc.), "
                "(2) Global datasets (WorldPop, GHSL), or "
                "(3) Manual CSV matching with local census data.",
                UserWarning
            )
        gdf['population'] = 0
        return gdf
    
    if verbose:
        print("✓ US region detected")
    
    # Find GEOID column
    geoid_column = next((col for col in ['GEOID', 'GEOID20', 'GEOID10', 'GEOID_TRACT', 'GEOID_GEOCODED'] 
                        if col in gdf.columns), None)
    
    # If no GEOID, check if taz_column looks like GEOID
    if geoid_column is None and taz_column:
        sample = str(gdf[taz_column].iloc[0])
        if len(sample) >= 11 and sample.isdigit():
            geoid_column = taz_column
    
    # If still no GEOID, use geocoding to get it
    if geoid_column is None:
        if verbose:
            print("No GEOID column found. Using Census Geocoding API...")
        try:
            gdf, geoid_column = add_geoids_via_geocoding(gdf, verbose=verbose)
        except Exception as e:
            if verbose:
                warnings.warn(f"Geocoding failed: {e}. Setting population=0.", UserWarning)
            gdf['population'] = 0
            return gdf
    
    # Check if we have valid GEOIDs
    valid_geoids = gdf[geoid_column].apply(lambda x: len(str(x).strip()) == 11).sum()
    if valid_geoids == 0:
        if verbose:
            warnings.warn("No valid GEOIDs found. Setting population=0.", UserWarning)
        gdf['population'] = 0
        return gdf
    
    # Fetch population
    if verbose:
        print("Fetching population data from US Census Bureau API...")
    
    population_dict = get_population_for_tracts(gdf, geoid_column, year, verbose=verbose)
    gdf['population'] = gdf[geoid_column].apply(lambda x: population_dict.get(str(x).strip(), 0))
    
    if verbose:
        matched = (gdf['population'] > 0).sum()
        total = len(gdf)
        total_pop = gdf['population'].sum()
        print(f"✓ Population data: {matched}/{total} zones matched ({100*matched/total:.1f}%)")
        if total_pop > 0:
            print(f"✓ Total population: {total_pop:,}")
    
    return gdf


def calculate_centroids(gdf):
    """Calculate centroids while preserving original geometry."""
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    
    if gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    
    gdf_projected = gdf.to_crs(epsg=3857)
    centroids = gdf_projected.geometry.centroid
    centroids_latlon = gpd.GeoSeries(centroids, crs=3857).to_crs(epsg=4326)
    
    gdf = gdf.copy()
    gdf['x_coord'] = centroids_latlon.x
    gdf['y_coord'] = centroids_latlon.y
    gdf['boundary_geometry'] = gdf['geometry']
    gdf['geometry'] = gdf.apply(lambda row: Point(row['x_coord'], row['y_coord']), axis=1)
    gdf = gpd.GeoDataFrame(gdf, geometry='geometry', crs='EPSG:4326')
    
    return gdf


def save_centroids_to_csv(gdf, output_csv_path, taz_column):
    """Save centroids, boundaries, and population to CSV."""
    nodes = []
    node_id_counter = 1
    
    for idx, row in gdf.iterrows():
        if row['geometry'] is None:
            continue
        
        geometry_wkt = row['geometry'].wkt.replace("\n", " ")
        boundary_wkt = row['boundary_geometry'].wkt.replace("\n", " ")
        
        if taz_column and taz_column in gdf.columns:
            TAZ_id = str(row[taz_column])
        else:
            TAZ_id = str(node_id_counter)
        
        nodes.append({
            "name": TAZ_id,
            "node_id": node_id_counter,
            "osm_node_id": "",
            "x_coord": row['x_coord'],
            "y_coord": row['y_coord'],
            "zone_id": node_id_counter,
            "TAZ_ID": TAZ_id,
            "population": int(row.get('population', 0)),
            "geometry": geometry_wkt,
            "boundary_geometry": boundary_wkt,
            "notes": " "
        })
        node_id_counter += 1
    
    nodes_df = pd.DataFrame(nodes)
    nodes_df = nodes_df.dropna()
    nodes_df.to_csv(output_csv_path, index=False, quoting=csv.QUOTE_ALL, encoding='utf-8')


def detect_taz_column(gdf):
    """Automatically detect zone identifier column."""
    columns = gdf.columns.tolist()
    
    patterns = [
        'TRACTCE', 'TRACTCE20', 'TRACTCE10', 'TRACT', 'TRACT_ID',
        'GEOID', 'GEOID20', 'GEOID10', 'GEOID_TRACT', 'GEOID_GEOCODED',
        'TAZ', 'TAZ_ID', 'TAZID', 'TAZ_NUM', 'TAZ_CODE',
        'BLKGRPCE', 'BLKGRP', 'BG', 'BLOCKGROUP',
        'ZONE', 'ZONE_ID', 'ZONEID', 'ZONE_NUM', 'ZONE_CODE',
        'FIPS', 'FIPSCODE', 'STATEFP', 'COUNTYFP',
        'ID', 'OBJECTID', 'FID', 'AREA_ID', 'REGION_ID'
    ]
    
    for pattern in patterns:
        if pattern in columns:
            return pattern
    
    for pattern in patterns:
        for col in columns:
            if pattern.lower() in col.upper():
                return col
    
    candidates = []
    for col in columns:
        try:
            if col == 'geometry':
                continue
            
            unique_count = gdf[col].nunique()
            total_count = len(gdf)
            uniqueness_ratio = unique_count / total_count
            
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
        candidates.sort(key=lambda x: x['uniqueness'], reverse=True)
        return candidates[0]['column']
    
    return None


# Main execution
os.environ['SHAPE_RESTORE_SHX'] = 'YES'

print("="*70)
print("AUTOMATED ZONE CENTROID & POPULATION EXTRACTION")
print("="*70 + "\n")

try:
    gdf = gpd.read_file(shapefile_path)
    print(f"✓ Loaded shapefile: {os.path.basename(shapefile_path)}")
    print(f"  Features: {len(gdf)}")
except Exception as e:
    print(f"✗ Error loading shapefile: {e}")
    sys.exit()

if gdf.crs is None:
    gdf.set_crs(epsg=4326, inplace=True)

if gdf.crs.to_epsg() != 4326:
    gdf = gdf.to_crs(epsg=4326)

# Detect zone column
taz_column = detect_taz_column(gdf)
if taz_column is None:
    print("  No zone identifier found, creating sequential IDs...")
    gdf['ZONE_ID'] = range(1, len(gdf) + 1)
    taz_column = 'ZONE_ID'
else:
    print(f"  Zone identifier: '{taz_column}' ({gdf[taz_column].nunique()} unique zones)")

print()

# Add population data (FULLY AUTOMATED)
gdf = add_population_to_gdf(gdf, taz_column, year=2022, verbose=True)

print("\nCalculating centroids...")
gdf = calculate_centroids(gdf)


output_csv_path = "zone.csv"
save_centroids_to_csv(gdf, output_csv_path, taz_column)

print(f"\n{'='*70}")
print("✓ PROCESSING COMPLETE")
print(f"{'='*70}")
print(f"Output: {output_csv_path}")
if gdf['population'].sum() > 0:
    print(f"Total population: {gdf['population'].sum():,}")
print(f"{'='*70}\n")