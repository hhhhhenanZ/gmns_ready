"""
Base Map Validator for GMNS Networks
Checks spatial consistency between shapefiles, nodes, and links
@author: hnzhu
"""

import os
import json
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point, LineString, box
from shapely.ops import unary_union
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class BaseMapValidator:
    """Validates spatial consistency of GMNS network files"""
    
    def __init__(self, network_dir='.', data_folder='data'):
        """
        Args:
            network_dir: Directory containing node.csv and link.csv
            data_folder: Subfolder containing shapefiles
        """
        self.network_dir = network_dir
        self.data_folder = os.path.join(network_dir, data_folder)
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'location_info': {},
            'spatial_checks': {},
            'data_quality': {},
            'issues': [],
            'summary': {'status': 'PASS', 'errors': 0, 'warnings': 0}
        }
        
    def validate(self):
        """Run all base map validation checks"""
        print("GMNS Base Map Validator")
        print("=" * 60)
        
        try:
            # Step 1: Check folder structure
            print("\nStep 1: Checking folder structure...")
            folder_ok = self._check_folder_structure()
            
            # Step 2: Load files
            print("\nStep 2: Loading network files...")
            files_loaded = self._load_files()
            
            # Only continue with advanced checks if basic files exist
            if files_loaded and folder_ok:
                # Step 3: Location detection
                print("\nStep 3: Detecting location...")
                self._detect_location()
                
                # Step 4: Check node-link topology
                print("\nStep 4: Checking node-link topology...")
                self._check_node_link_topology()
                
                # Step 5: Check spatial consistency with shapefiles
                print("\nStep 5: Checking spatial consistency with shapefiles...")
                self._check_spatial_overlap()
                
                # Step 6: Data quality checks (duplicates)
                print("\nStep 6: Validating data quality...")
                self._check_data_quality()
                
                # Step 7: Visualization
                print("\nStep 7: Generating visualization...")
                self._create_visualization()
            else:
                print("\nWarning: Skipping advanced checks due to missing required files.")
            
        except Exception as e:
            self._add_issue('ERROR', f'Unexpected error during validation: {str(e)}', 'system_error')
            import traceback
            traceback.print_exc()
        
        finally:
            # Always save results, even if validation failed
            self._save_results()
        
        # Print final summary
        self._print_final_summary()
        
        return self.results
    
    def _print_final_summary(self):
        """Print clear final summary for user"""
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Status: {self.results['summary']['status']}")
        print(f"Total Errors: {self.results['summary']['errors']}")
        print(f"Total Warnings: {self.results['summary']['warnings']}")
        print("-" * 60)
        
        if self.results['summary']['errors'] == 0 and self.results['summary']['warnings'] == 0:
            print("\n✓ BASE MAP CHECK PASSED")
            print("  All checks completed successfully.")
            print("  Your network is ready for further validation.")
        elif self.results['summary']['errors'] == 0 and self.results['summary']['warnings'] > 0:
            print("\n⚠ BASE MAP CHECK PASSED WITH WARNINGS")
            
            # Categorize issues by file
            file_issues = {'node.csv': [], 'link.csv': [], 'shapefiles': [], 'other': []}
            for issue in self.results['issues']:
                if issue['severity'] != 'WARNING':
                    continue
                msg = issue['message'].lower()
                if 'node' in msg and 'link' not in msg:
                    file_issues['node.csv'].append(issue['message'])
                elif 'link' in msg and 'node' not in msg:
                    file_issues['link.csv'].append(issue['message'])
                elif 'shapefile' in msg or 'spatial' in msg or '.shp' in msg:
                    file_issues['shapefiles'].append(issue['message'])
                elif 'node' in msg and 'link' in msg:
                    file_issues['other'].append(issue['message'])
                else:
                    file_issues['other'].append(issue['message'])
            
            # Print specific guidance
            print("  Review the following warnings:")
            print("")
            for file, issues in file_issues.items():
                if issues:
                    print(f"  {file}:")
                    for issue in issues[:3]:  # Show first 3 issues per file
                        print(f"    - {issue}")
                    if len(issues) > 3:
                        print(f"    ... and {len(issues) - 3} more issue(s)")
                    print("")
        else:
            print("\n✗ BASE MAP CHECK FAILED")
            print(f"  {self.results['summary']['errors']} error(s) must be fixed before proceeding.")
            
            # Categorize issues by file
            file_issues = {'node.csv': [], 'link.csv': [], 'shapefiles': [], 'network mismatch': [], 'folder': []}
            for issue in self.results['issues']:
                if issue['severity'] != 'ERROR':
                    continue
                    
                msg = issue['message']
                cat = issue.get('category', '')
                
                if 'folder' in cat or 'missing' in cat.lower():
                    file_issues['folder'].append(msg)
                elif 'geographic_mismatch' in cat or 'geometry_mismatch' in cat or ('node' in msg.lower() and 'link' in msg.lower() and 'different' in msg.lower()):
                    file_issues['network mismatch'].append(msg)
                elif 'duplicate_nodes' in cat or ('duplicate' in msg.lower() and 'node' in msg.lower()):
                    file_issues['node.csv'].append(msg)
                elif 'duplicate_links' in cat or ('duplicate' in msg.lower() and 'link' in msg.lower()):
                    file_issues['link.csv'].append(msg)
                elif 'dangling' in cat or 'dangling' in msg.lower():
                    file_issues['link.csv'].append(msg)
                elif 'shapefile' in msg.lower() or 'spatial' in msg.lower() or '.shp' in msg.lower():
                    file_issues['shapefiles'].append(msg)
                else:
                    file_issues['folder'].append(msg)
            
            # Print specific guidance
            print("\n  Files to check:")
            print("")
            
            if file_issues['network mismatch']:
                print("  ⚠ CRITICAL: node.csv and link.csv mismatch")
                print("     These files appear to be from DIFFERENT networks!")
                for issue in file_issues['network mismatch'][:2]:
                    print(f"     - {issue}")
                print("")
            
            if file_issues['folder']:
                print("  📁 Folder/File structure:")
                for issue in file_issues['folder'][:3]:
                    print(f"     - {issue}")
                if len(file_issues['folder']) > 3:
                    print(f"     ... and {len(file_issues['folder']) - 3} more issue(s)")
                print("")
                    
            if file_issues['node.csv']:
                print("  📄 node.csv:")
                for issue in file_issues['node.csv'][:3]:
                    print(f"     - {issue}")
                if len(file_issues['node.csv']) > 3:
                    print(f"     ... and {len(file_issues['node.csv']) - 3} more issue(s)")
                print("")
                    
            if file_issues['link.csv']:
                print("  📄 link.csv:")
                for issue in file_issues['link.csv'][:3]:
                    print(f"     - {issue}")
                if len(file_issues['link.csv']) > 3:
                    print(f"     ... and {len(file_issues['link.csv']) - 3} more issue(s)")
                print("")
                    
            if file_issues['shapefiles']:
                print("  🗺️  Shapefiles:")
                for issue in file_issues['shapefiles'][:3]:
                    print(f"     - {issue}")
                if len(file_issues['shapefiles']) > 3:
                    print(f"     ... and {len(file_issues['shapefiles']) - 3} more issue(s)")
                print("")
        
        print("=" * 60)
    
    def _check_folder_structure(self):
        """Check if required folders and files exist"""
        all_ok = True
        
        # Check if data folder exists
        if not os.path.exists(self.data_folder):
            self._add_issue('ERROR', 
                f'Data folder not found: {self.data_folder}. Please create a "data" folder for shapefiles.',
                'missing_data_folder')
            print(f"  Error: Data folder missing: {self.data_folder}")
            all_ok = False
        else:
            print(f"  Data folder found: {self.data_folder}")
            
            # Check if data folder has any .shp files
            shp_files = [f for f in os.listdir(self.data_folder) if f.endswith('.shp')]
            if not shp_files:
                self._add_issue('ERROR',
                    f'No shapefile (.shp) found in data folder: {self.data_folder}',
                    'no_shapefiles')
                print(f"  Error: No .shp files found in data folder")
                all_ok = False
            else:
                print(f"  Found {len(shp_files)} shapefile(s) in data folder")
        
        # Check if node.csv exists
        node_file = os.path.join(self.network_dir, 'node.csv')
        if not os.path.exists(node_file):
            self._add_issue('ERROR',
                'node.csv not found in network directory. This file is required.',
                'missing_node_file')
            print(f"  Error: node.csv not found")
            all_ok = False
        else:
            print(f"  Using node file: node.csv")
        
        # Check if link.csv exists
        link_file = os.path.join(self.network_dir, 'link.csv')
        if not os.path.exists(link_file):
            self._add_issue('ERROR',
                'link.csv not found in network directory. This file is required.',
                'missing_link_file')
            print(f"  Error: link.csv not found")
            all_ok = False
        else:
            print(f"  Using link file: link.csv")
        
        self.results['folder_structure'] = {
            'data_folder_exists': os.path.exists(self.data_folder),
            'node_csv_exists': os.path.exists(node_file),
            'link_csv_exists': os.path.exists(link_file),
            'shapefiles_found': len(shp_files) if os.path.exists(self.data_folder) else 0,
            'status': 'OK' if all_ok else 'ERROR'
        }
        
        return all_ok
    
    def _load_files(self):
        """Load shapefiles, node.csv, and link.csv"""
        files_loaded = False
        
        try:
            # Load nodes
            node_file = os.path.join(self.network_dir, 'node.csv')
            if os.path.exists(node_file):
                self.nodes_df = pd.read_csv(node_file)
                self.nodes_gdf = gpd.GeoDataFrame(
                    self.nodes_df,
                    geometry=gpd.points_from_xy(self.nodes_df.x_coord, self.nodes_df.y_coord),
                    crs='EPSG:4326'
                )
                print(f"  Loaded {len(self.nodes_df)} nodes from node.csv")
                files_loaded = True
            else:
                print(f"  Warning: node.csv not found")
                self.nodes_df = None
                self.nodes_gdf = None
            
            # Load links
            link_file = os.path.join(self.network_dir, 'link.csv')
            if os.path.exists(link_file):
                self.links_df = pd.read_csv(link_file)
                print(f"  Loaded {len(self.links_df)} links from link.csv")
                files_loaded = True
            else:
                print(f"  Warning: link.csv not found")
                self.links_df = None
            
            # Load shapefiles from data folder
            self.shapefiles = {}
            if os.path.exists(self.data_folder):
                shp_files = [f for f in os.listdir(self.data_folder) if f.endswith('.shp')]
                
                if shp_files:
                    for file in shp_files:
                        try:
                            shp_path = os.path.join(self.data_folder, file)
                            gdf = gpd.read_file(shp_path)
                            if gdf.crs is None:
                                gdf.set_crs('EPSG:4326', inplace=True)
                            elif gdf.crs != 'EPSG:4326':
                                gdf = gdf.to_crs('EPSG:4326')
                            self.shapefiles[file] = gdf
                            print(f"  Loaded shapefile: {file} ({len(gdf)} features)")
                            files_loaded = True
                        except Exception as e:
                            self._add_issue('WARNING', f'Could not load {file}: {str(e)}', 'shapefile_load')
                            print(f"  Warning: Failed to load {file}")
                else:
                    print(f"  Warning: No .shp files found in data folder")
            else:
                print(f"  Warning: Data folder not found")
                
            return files_loaded
            
        except Exception as e:
            self._add_issue('ERROR', f'Failed to load files: {str(e)}', 'file_load')
            print(f"  Error loading files: {str(e)}")
            return False
    
    def _detect_location(self):
        """Detect location name from coordinates"""
        if self.nodes_df is None or len(self.nodes_df) == 0:
            self.results['location_info'] = {
                'status': 'ERROR',
                'message': 'Cannot detect location - node.csv not loaded'
            }
            return
            
        try:
            # Get center of nodes
            center_x = self.nodes_df['x_coord'].mean()
            center_y = self.nodes_df['y_coord'].mean()
            
            # Detect coordinate system
            if -180 <= center_x <= 180 and -90 <= center_y <= 90:
                coord_system = "WGS84 (Lat/Lon)"
            else:
                coord_system = "Projected (likely State Plane or UTM)"
            
            self.results['location_info'] = {
                'center_longitude': float(center_x),
                'center_latitude': float(center_y),
                'coordinate_system': coord_system,
                'node_bounds': {
                    'min_x': float(self.nodes_df['x_coord'].min()),
                    'max_x': float(self.nodes_df['x_coord'].max()),
                    'min_y': float(self.nodes_df['y_coord'].min()),
                    'max_y': float(self.nodes_df['y_coord'].max())
                }
            }
            
            # Try reverse geocoding for WGS84
            if coord_system == "WGS84 (Lat/Lon)":
                try:
                    from geopy.geocoders import Nominatim
                    geolocator = Nominatim(user_agent="gmns_validator")
                    location = geolocator.reverse(f"{center_y}, {center_x}", language='en', timeout=10)
                    if location:
                        address = location.raw.get('address', {})
                        location_name = f"{address.get('city', address.get('town', address.get('county', 'Unknown')))}, {address.get('state', '')} {address.get('country', '')}"
                        self.results['location_info']['suggested_location'] = location_name.strip()
                        print(f"  Detected location: {location_name}")
                except Exception as e:
                    self.results['location_info']['suggested_location'] = 'Unable to detect (install geopy for location detection)'
                    print(f"  Warning: Location detection unavailable (install geopy)")
            else:
                self.results['location_info']['suggested_location'] = 'Projected coordinates - location detection not available'
                
        except Exception as e:
            self._add_issue('WARNING', f'Could not detect location: {str(e)}', 'location_detection')
    
    def _check_node_link_topology(self):
        """Check node-link topology: do links connect to nodes properly?"""
        if self.nodes_df is None or self.links_df is None:
            print("  Cannot check topology - node.csv or link.csv not loaded")
            return
            
        try:
            print("  Checking if links connect to valid nodes...")
            
            # Get node IDs
            node_ids = set(self.nodes_df['node_id'])
            total_links = len(self.links_df)
            
            # Check from_node_id
            missing_from = self.links_df[~self.links_df['from_node_id'].isin(node_ids)]
            
            # Check to_node_id
            missing_to = self.links_df[~self.links_df['to_node_id'].isin(node_ids)]
            
            if len(missing_from) == 0 and len(missing_to) == 0:
                print(f"  ✓ All {total_links} links connect to valid nodes")
                print(f"    - All from_node_ids exist in node.csv")
                print(f"    - All to_node_ids exist in node.csv")
                
                self.results['topology_check'] = {
                    'status': 'OK',
                    'total_links': int(total_links),
                    'missing_from_nodes': 0,
                    'missing_to_nodes': 0
                }
            else:
                if len(missing_from) > 0:
                    print(f"  ✗ ERROR: {len(missing_from)} links have from_node_id not in node.csv")
                    self._add_issue('ERROR',
                        f'{len(missing_from)} links have from_node_id not in node file. These are dangling links.',
                        'dangling_links')
                else:
                    print(f"  ✓ All from_node_ids are valid")
                    
                if len(missing_to) > 0:
                    print(f"  ✗ ERROR: {len(missing_to)} links have to_node_id not in node.csv")
                    self._add_issue('ERROR',
                        f'{len(missing_to)} links have to_node_id not in node file. These are dangling links.',
                        'dangling_links')
                else:
                    print(f"  ✓ All to_node_ids are valid")
                
                self.results['topology_check'] = {
                    'status': 'ERROR',
                    'total_links': int(total_links),
                    'missing_from_nodes': int(len(missing_from)),
                    'missing_to_nodes': int(len(missing_to))
                }
            
            # Check if links are in the same geographic area as nodes
            print(f"\n  Checking if links are in same geographic area as nodes...")
            node_coords = dict(zip(self.nodes_df['node_id'], 
                                  zip(self.nodes_df['x_coord'], self.nodes_df['y_coord'])))
            
            # Get link coordinates from endpoint nodes
            link_from_coords = []
            link_to_coords = []
            for _, link in self.links_df.iterrows():
                if link['from_node_id'] in node_coords:
                    link_from_coords.append(node_coords[link['from_node_id']])
                if link['to_node_id'] in node_coords:
                    link_to_coords.append(node_coords[link['to_node_id']])
            
            if link_from_coords and link_to_coords:
                # Get node extent
                node_bounds = self.nodes_gdf.total_bounds
                node_bbox = box(node_bounds[0], node_bounds[1], node_bounds[2], node_bounds[3])
                
                # Get link extent from endpoint coordinates
                link_x = [coord[0] for coord in link_from_coords] + [coord[0] for coord in link_to_coords]
                link_y = [coord[1] for coord in link_from_coords] + [coord[1] for coord in link_to_coords]
                link_bounds = [min(link_x), min(link_y), max(link_x), max(link_y)]
                link_bbox = box(link_bounds[0], link_bounds[1], link_bounds[2], link_bounds[3])
                
                print(f"  Node extent: [{node_bounds[0]:.4f}, {node_bounds[1]:.4f}] to [{node_bounds[2]:.4f}, {node_bounds[3]:.4f}]")
                print(f"  Link extent: [{link_bounds[0]:.4f}, {link_bounds[1]:.4f}] to [{link_bounds[2]:.4f}, {link_bounds[3]:.4f}]")
                
                # Check if link and node extents are similar (with 20% tolerance)
                node_width = node_bounds[2] - node_bounds[0]
                node_height = node_bounds[3] - node_bounds[1]
                link_width = link_bounds[2] - link_bounds[0]
                link_height = link_bounds[3] - link_bounds[1]
                
                # Calculate overlap
                overlap = node_bbox.intersection(link_bbox).area / node_bbox.area if node_bbox.intersects(link_bbox) else 0
                
                if overlap < 0.5:  # Less than 50% overlap
                    print(f"  ✗ ERROR: Links and nodes are in DIFFERENT geographic areas!")
                    print(f"    Overlap: {overlap*100:.1f}%")
                    print(f"    This suggests node.csv and link.csv are from different networks.")
                    self._add_issue('ERROR',
                        f'Links and nodes are in different geographic areas (overlap: {overlap*100:.1f}%). node.csv and link.csv appear to be from different networks or cities.',
                        'geographic_mismatch')
                    if 'topology_check' in self.results:
                        self.results['topology_check']['status'] = 'ERROR'
                        self.results['topology_check']['geographic_overlap'] = f"{overlap*100:.1f}%"
                elif overlap < 0.8:  # Between 50-80% overlap
                    print(f"  ⚠ WARNING: Links and nodes have limited geographic overlap ({overlap*100:.1f}%)")
                    print(f"    Please verify node.csv and link.csv are from the same network.")
                    self._add_issue('WARNING',
                        f'Links and nodes have limited geographic overlap ({overlap*100:.1f}%). Verify they are from the same network.',
                        'geographic_warning')
                    if 'topology_check' in self.results:
                        self.results['topology_check']['geographic_overlap'] = f"{overlap*100:.1f}%"
                else:
                    print(f"  ✓ Links and nodes are in the same geographic area (overlap: {overlap*100:.1f}%)")
                    if 'topology_check' in self.results:
                        self.results['topology_check']['geographic_overlap'] = f"{overlap*100:.1f}%"
            
            # Check if link geometry endpoints match node locations (if geometry exists)
            if 'geometry' in self.links_df.columns:
                links_with_geom = self.links_df[self.links_df['geometry'].notna()]
                if len(links_with_geom) > 0:
                    print(f"\n  Checking link geometry consistency...")
                    mismatched = self._check_link_geometry_consistency(links_with_geom)
                    mismatch_percent = (mismatched / min(100, len(links_with_geom))) * 100
                    
                    if mismatched > 50 or mismatch_percent > 50:  # More than 50 links or 50% mismatched
                        print(f"  ✗ ERROR: {mismatched} links have geometry not matching node locations")
                        print(f"    This strongly suggests node.csv and link.csv are from different networks.")
                        self._add_issue('ERROR',
                            f'{mismatched} links have geometry inconsistent with node locations. This indicates node.csv and link.csv are likely from different networks.',
                            'geometry_mismatch')
                        if 'topology_check' in self.results:
                            self.results['topology_check']['status'] = 'ERROR'
                    elif mismatched > 0:
                        print(f"  ⚠ WARNING: {mismatched} links have geometry not matching node locations")
                        self._add_issue('WARNING',
                            f'{mismatched} links have geometry inconsistent with node locations.',
                            'geometry_mismatch')
                    else:
                        print(f"  ✓ Link geometries match node locations")
                        
        except Exception as e:
            self._add_issue('ERROR', f'Topology check failed: {str(e)}', 'topology_check')
    
    def _check_spatial_overlap(self):
        """Check if shapefiles and network (nodes) are in the same geographic area"""
        if self.nodes_gdf is None:
            self.results['spatial_checks'] = {
                'status': 'ERROR',
                'message': 'Cannot check spatial overlap - nodes not loaded'
            }
            return
            
        try:
            print("  Comparing shapefile extent with network extent...")
            
            # Calculate bounds with 10% padding
            node_bounds = self.nodes_gdf.total_bounds
            padding = max(node_bounds[2] - node_bounds[0], node_bounds[3] - node_bounds[1]) * 0.1
            node_bbox = box(
                node_bounds[0] - padding, node_bounds[1] - padding,
                node_bounds[2] + padding, node_bounds[3] + padding
            )
            
            print(f"\n  Network extent: [{node_bounds[0]:.4f}, {node_bounds[1]:.4f}] to [{node_bounds[2]:.4f}, {node_bounds[3]:.4f}]")
            
            self.results['spatial_checks']['nodes'] = {
                'status': 'OK',
                'feature_count': len(self.nodes_df),
                'bounds': [float(x) for x in node_bounds]
            }
            
            # Check each shapefile
            if not self.shapefiles:
                self.results['spatial_checks']['shapefiles'] = {
                    'status': 'WARNING',
                    'message': 'No shapefiles to compare'
                }
                print(f"\n  ⚠ WARNING: No shapefiles found to verify spatial alignment")
                return
            
            print(f"\n  Checking spatial alignment with {len(self.shapefiles)} shapefile(s)...")
                
            for shp_name, shp_gdf in self.shapefiles.items():
                shp_bounds = shp_gdf.total_bounds
                shp_bbox = box(*shp_bounds)
                
                print(f"\n  Shapefile: {shp_name}")
                print(f"    Extent: [{shp_bounds[0]:.4f}, {shp_bounds[1]:.4f}] to [{shp_bounds[2]:.4f}, {shp_bounds[3]:.4f}]")
                
                # Check overlap
                overlap = node_bbox.intersects(shp_bbox)
                overlap_area = node_bbox.intersection(shp_bbox).area / node_bbox.area if overlap else 0
                
                status = 'OK' if overlap_area > 0.5 else ('WARNING' if overlap_area > 0.1 else 'ERROR')
                
                self.results['spatial_checks'][shp_name] = {
                    'status': status,
                    'feature_count': len(shp_gdf),
                    'bounds': [float(x) for x in shp_bounds],
                    'overlap_with_nodes': f"{overlap_area*100:.1f}%"
                }
                
                if status == 'ERROR':
                    self._add_issue('ERROR', 
                        f'{shp_name} and network nodes are NOT in the same geographic area (overlap: {overlap_area*100:.1f}%). Check if you are using the correct shapefile.',
                        'spatial_mismatch')
                    print(f"    ✗ ERROR: NOT in same area as network (overlap: {overlap_area*100:.1f}%)")
                    print(f"      This shapefile appears to cover a different geographic region.")
                elif status == 'WARNING':
                    self._add_issue('WARNING',
                        f'{shp_name} has limited overlap with network nodes ({overlap_area*100:.1f}%). Verify spatial alignment.',
                        'spatial_warning')
                    print(f"    ⚠ WARNING: Limited overlap with network (overlap: {overlap_area*100:.1f}%)")
                else:
                    print(f"    ✓ Spatial alignment OK (overlap: {overlap_area*100:.1f}%)")
                
        except Exception as e:
            self._add_issue('ERROR', f'Spatial overlap check failed: {str(e)}', 'spatial_check')
    
    def _check_data_quality(self):
        """Check for duplicate IDs in node and link files"""
        if self.nodes_df is None or self.links_df is None:
            self.results['data_quality'] = {
                'status': 'ERROR',
                'message': 'Cannot check data quality - node.csv or link.csv not loaded'
            }
            return
            
        checks = {}
        
        print("  Checking for duplicate IDs...")
        
        # 1. Check duplicate node_ids
        dup_nodes = self.nodes_df['node_id'].duplicated().sum()
        checks['duplicate_nodes'] = {
            'count': int(dup_nodes),
            'status': 'ERROR' if dup_nodes > 0 else 'OK'
        }
        if dup_nodes > 0:
            dup_ids = self.nodes_df[self.nodes_df['node_id'].duplicated(keep=False)]['node_id'].unique()
            self._add_issue('ERROR', 
                f'Found {dup_nodes} duplicate node_ids: {list(dup_ids)[:5]}{"..." if len(dup_ids) > 5 else ""}',
                'duplicate_nodes')
            print(f"  ✗ ERROR: Found {dup_nodes} duplicate node_ids")
            if len(dup_ids) <= 10:
                print(f"    Duplicate IDs: {list(dup_ids)}")
        else:
            print(f"  ✓ No duplicate node_ids")
        
        # 2. Check duplicate link_ids
        dup_links = self.links_df['link_id'].duplicated().sum()
        checks['duplicate_links'] = {
            'count': int(dup_links),
            'status': 'ERROR' if dup_links > 0 else 'OK'
        }
        if dup_links > 0:
            dup_ids = self.links_df[self.links_df['link_id'].duplicated(keep=False)]['link_id'].unique()
            self._add_issue('ERROR',
                f'Found {dup_links} duplicate link_ids: {list(dup_ids)[:5]}{"..." if len(dup_ids) > 5 else ""}',
                'duplicate_links')
            print(f"  ✗ ERROR: Found {dup_links} duplicate link_ids")
            if len(dup_ids) <= 10:
                print(f"    Duplicate IDs: {list(dup_ids)}")
        else:
            print(f"  ✓ No duplicate link_ids")
        
        self.results['data_quality'] = checks
    
    def _check_link_geometry_consistency(self, links_with_geom, tolerance=0.001):
        """Check if link geometry endpoints match node coordinates"""
        mismatched = 0
        node_coords = dict(zip(self.nodes_df['node_id'], 
                               zip(self.nodes_df['x_coord'], self.nodes_df['y_coord'])))
        
        for _, link in links_with_geom.head(100).iterrows():  # Sample first 100 for performance
            try:
                geom = link['geometry']
                if isinstance(geom, str):
                    # Parse LINESTRING from WKT
                    if 'LINESTRING' in geom:
                        coords = geom.replace('LINESTRING', '').replace('(', '').replace(')', '').strip()
                        points = [tuple(map(float, p.strip().split())) for p in coords.split(',')]
                        geom_start = points[0]
                        geom_end = points[-1]
                    else:
                        continue
                else:
                    continue
                
                from_node = link['from_node_id']
                to_node = link['to_node_id']
                
                if from_node in node_coords and to_node in node_coords:
                    from_coord = node_coords[from_node]
                    to_coord = node_coords[to_node]
                    
                    # Check if geometry endpoints match node coordinates
                    from_dist = ((geom_start[0] - from_coord[0])**2 + (geom_start[1] - from_coord[1])**2)**0.5
                    to_dist = ((geom_end[0] - to_coord[0])**2 + (geom_end[1] - to_coord[1])**2)**0.5
                    
                    if from_dist > tolerance or to_dist > tolerance:
                        mismatched += 1
                        
            except Exception:
                continue
                
        return mismatched
    
    def _create_visualization(self):
        """Create visualization of shapefiles, nodes, and links"""
        if self.nodes_gdf is None:
            print(f"  Skipping visualization - nodes not loaded")
            return
            
        try:
            fig, ax = plt.subplots(figsize=(14, 10))
            
            # Plot shapefiles
            colors = ['lightgray', 'lightblue', 'lightgreen', 'lightyellow']
            for i, (shp_name, shp_gdf) in enumerate(self.shapefiles.items()):
                shp_gdf.plot(ax=ax, color=colors[i % len(colors)], 
                            alpha=0.5, edgecolor='gray', linewidth=0.5,
                            label=shp_name.replace('.shp', ''))
            
            # Plot nodes
            self.nodes_gdf.plot(ax=ax, color='red', markersize=5, 
                               alpha=0.6, label='Nodes', zorder=3)
            
            # Plot links (sample if too many)
            if self.links_df is not None and len(self.links_df) > 0:
                # Create simple lines between from/to nodes
                node_coords = dict(zip(self.nodes_df['node_id'], 
                                      zip(self.nodes_df['x_coord'], self.nodes_df['y_coord'])))
                
                sample_size = min(1000, len(self.links_df))
                for _, link in self.links_df.sample(n=sample_size).iterrows():
                    if link['from_node_id'] in node_coords and link['to_node_id'] in node_coords:
                        from_coord = node_coords[link['from_node_id']]
                        to_coord = node_coords[link['to_node_id']]
                        ax.plot([from_coord[0], to_coord[0]], 
                               [from_coord[1], to_coord[1]], 
                               'b-', alpha=0.3, linewidth=0.5, zorder=2)
            
            # Styling
            ax.set_xlabel('Longitude', fontsize=12)
            ax.set_ylabel('Latitude', fontsize=12)
            location_str = self.results.get('location_info', {}).get('suggested_location', 'Unknown')
            ax.set_title('GMNS Network Base Map Validation\n' + 
                        f"Location: {location_str}", 
                        fontsize=14, fontweight='bold')
            ax.legend(loc='upper right', frameon=True, fancybox=True, shadow=True)
            ax.grid(True, alpha=0.3)
            
            # Add status text
            status_text = f"Status: {self.results['summary']['status']}\n"
            status_text += f"Errors: {self.results['summary']['errors']}, "
            status_text += f"Warnings: {self.results['summary']['warnings']}"
            ax.text(0.02, 0.98, status_text, transform=ax.transAxes,
                   fontsize=10, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            
            plt.tight_layout()
            
            # Create data folder if it doesn't exist
            os.makedirs(self.data_folder, exist_ok=True)
            
            # Save figure
            output_file = os.path.join(self.data_folder, 'base_map_validation.png')
            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            plt.close()
            
            print(f"  Visualization saved to: {output_file}")
            self.results['visualization_file'] = output_file
            
        except Exception as e:
            self._add_issue('WARNING', f'Could not create visualization: {str(e)}', 'visualization')
            print(f"  Warning: Visualization failed - {str(e)}")
    
    def _save_results(self):
        """Save validation results to JSON"""
        try:
            # Create data folder if it doesn't exist
            os.makedirs(self.data_folder, exist_ok=True)
            
            output_file = os.path.join(self.data_folder, 'base_map_validation_report.json')
            with open(output_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            print(f"\nReport saved to: {output_file}")
        except Exception as e:
            # If data folder can't be created, save in network directory
            try:
                output_file = os.path.join(self.network_dir, 'base_map_validation_report.json')
                with open(output_file, 'w') as f:
                    json.dump(self.results, f, indent=2)
                print(f"\nReport saved to: {output_file}")
            except Exception as e2:
                print(f"\nError: Could not save report - {str(e2)}")
                # At least print the summary
                print("\nValidation Results:")
                print(json.dumps(self.results, indent=2))
    
    def _add_issue(self, severity, message, category):
        """Add an issue to results"""
        self.results['issues'].append({
            'severity': severity,
            'category': category,
            'message': message
        })
        
        if severity == 'ERROR':
            self.results['summary']['errors'] += 1
            self.results['summary']['status'] = 'FAIL'
        elif severity == 'WARNING':
            self.results['summary']['warnings'] += 1
            if self.results['summary']['status'] == 'PASS':
                self.results['summary']['status'] = 'WARNING'


def main(network_dir='.', data_folder='data'):
    """
    Run base map validation
    
    Usage:
        python base_map_validator.py
        
    Expected structure:
        network_dir/
            node.csv
            link.csv
            data/
                zone.shp
                *.shp
    """
    validator = BaseMapValidator(network_dir, data_folder)
    results = validator.validate()
    
    return results


if __name__ == '__main__':
    import sys
    network_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
    main(network_dir)