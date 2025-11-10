"""
GMNS Networks Validator
Validates network data structure, zones, and attribute units
@author: hnzhu
"""

import os
import sys
import json
import csv
import pandas as pd
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


class ReadinessValidator:
    """Validates GMNS network readiness across multiple levels"""
    
    def __init__(self, network_dir='connected_network'):
        """
        Args:
            network_dir: Directory containing node.csv and link.csv
        """
        self.network_dir = network_dir
        self.node_file = None
        self.link_file = None
        self.nodes_df = None
        self.links_df = None
        
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'network_dir': network_dir,
            'levels': {},
            'issues': [],
            'summary': {'status': 'PASS', 'errors': 0, 'warnings': 0}
        }
        
    def validate(self, max_level=3):
        """Run readiness validation checks up to specified level"""
        print("GMNS Readiness Validator")
        print("=" * 60)
        print(f"Network: {self.network_dir}")
        print(f"Validation levels: 1-{max_level}\n")
        
        try:
            # Level 1: Basic Data File Validation
            print("Level 1: Basic Data File Validation")
            print("-" * 60)
            level1_passed = self._level1_basic_validation()
            
            if not level1_passed:
                print("\n✗ Level 1 FAILED - Cannot proceed to higher levels")
                self._save_results()
                self._print_final_summary()
                return self.results
            
            print("✓ Level 1 PASSED\n")
            
            if max_level >= 2:
                # Level 2: Zone Consistency
                print("Level 2: Zone Consistency")
                print("-" * 60)
                self._level2_zone_validation()
                print(f"{'✓ Level 2 PASSED' if self.results['levels']['level2']['passed'] else '✗ Level 2 FAILED'}\n")
            
            if max_level >= 3:
                # Level 3: Attribute Unit Check
                print("Level 3: Attribute Unit Check")
                print("-" * 60)
                self._level3_attribute_validation()
                print(f"{'✓ Level 3 PASSED' if self.results['levels']['level3']['passed'] else '✗ Level 3 FAILED'}\n")
            
        except Exception as e:
            self._add_issue('ERROR', f'Unexpected error: {str(e)}', 'system')
            import traceback
            traceback.print_exc()
        
        finally:
            self._save_results()
        
        self._print_final_summary()
        return self.results
    
    def _level1_basic_validation(self):
        """Level 1: File existence, required fields, data structure, link endpoints"""
        level_result = {
            'name': 'Basic Data File Validation',
            'checks': [],
            'passed': True
        }
        
        # Check 1.1: File Existence
        print("  Check 1.1: File existence...")
        
        # Look for exact filenames only
        self.node_file = os.path.join(self.network_dir, 'node.csv')
        self.link_file = os.path.join(self.network_dir, 'link.csv')
        
        if not os.path.exists(self.node_file):
            self._add_issue('ERROR', 'node.csv not found', 'level1_file_existence')
            level_result['passed'] = False
            print("    ✗ node.csv - NOT FOUND")
        else:
            print(f"    ✓ node.csv - Found")
            
        if not os.path.exists(self.link_file):
            self._add_issue('ERROR', 'link.csv not found', 'level1_file_existence')
            level_result['passed'] = False
            print("    ✗ link.csv - NOT FOUND")
        else:
            print(f"    ✓ link.csv - Found")
        
        if not level_result['passed']:
            self.results['levels']['level1'] = level_result
            return False
        
        # Check 1.2: Required Fields & Data Types
        print("  Check 1.2: Required fields and data types...")
        try:
            self.nodes_df = pd.read_csv(self.node_file, encoding='utf-8-sig')
            
            # Check node required fields
            required_node_fields = ['node_id']
            missing_node = [f for f in required_node_fields if f not in self.nodes_df.columns]
            
            if missing_node:
                self._add_issue('ERROR', f'node.csv missing required fields: {", ".join(missing_node)}', 'level1_required_fields')
                level_result['passed'] = False
                print(f"    ✗ node.csv - Missing fields: {', '.join(missing_node)}")
            else:
                print(f"    ✓ node.csv - All required fields present")
                
                # Check data types
                if not pd.api.types.is_integer_dtype(self.nodes_df['node_id']):
                    self._add_issue('WARNING', 'node_id should be integer type in node.csv', 'level1_data_types')
                    print(f"    ⚠ node.csv - node_id is not integer type")
                
        except Exception as e:
            self._add_issue('ERROR', f'Cannot read node.csv: {str(e)}', 'level1_file_read')
            level_result['passed'] = False
            print(f"    ✗ node.csv - Read error: {str(e)}")
        
        try:
            self.links_df = pd.read_csv(self.link_file, encoding='utf-8-sig')
            
            # Check link required fields
            required_link_fields = ['link_id', 'from_node_id', 'to_node_id']
            missing_link = [f for f in required_link_fields if f not in self.links_df.columns]
            
            if missing_link:
                self._add_issue('ERROR', f'link.csv missing required fields: {", ".join(missing_link)}', 'level1_required_fields')
                level_result['passed'] = False
                print(f"    ✗ link.csv - Missing fields: {', '.join(missing_link)}")
            else:
                print(f"    ✓ link.csv - All required fields present")
                
                # Check data types
                for field in required_link_fields:
                    if not pd.api.types.is_integer_dtype(self.links_df[field]):
                        self._add_issue('WARNING', f'{field} should be integer type in link.csv', 'level1_data_types')
                        print(f"    ⚠ link.csv - {field} is not integer type")
                
        except Exception as e:
            self._add_issue('ERROR', f'Cannot read link.csv: {str(e)}', 'level1_file_read')
            level_result['passed'] = False
            print(f"    ✗ link.csv - Read error: {str(e)}")
        
        if not level_result['passed']:
            self.results['levels']['level1'] = level_result
            return False
        
        # Check 1.3: Sorted Data Structure
        print("  Check 1.3: Data structure (sorted order)...")
        
        # Check if nodes are sorted by node_id
        if not self.nodes_df['node_id'].is_monotonic_increasing:
            self._add_issue('WARNING', 'Nodes are not sorted by node_id in node.csv', 'level1_sorting')
            print("    ⚠ node.csv - Not sorted by node_id")
        else:
            print("    ✓ node.csv - Sorted by node_id")
        
        # Check if links are sorted
        if 'from_node_id' in self.links_df.columns and 'to_node_id' in self.links_df.columns:
            links_sorted = (self.links_df['from_node_id'].diff().fillna(1) >= 0).all()
            if not links_sorted:
                self._add_issue('WARNING', 'Links are not sorted by from_node_id in link.csv', 'level1_sorting')
                print("    ⚠ link.csv - Not sorted by from_node_id")
            else:
                print("    ✓ link.csv - Sorted by from_node_id")
        
        # Check 1.4: Link Endpoints Validation
        print("  Check 1.4: Link endpoint validation...")
        
        # Debug: Show file paths
        print(f"       Reading from: {self.node_file}")
        print(f"       Reading from: {self.link_file}")
        
        # Ensure all IDs are integers for comparison
        try:
            node_ids = set(int(x) for x in self.nodes_df['node_id'].dropna())
            from_nodes = set(int(x) for x in self.links_df['from_node_id'].dropna())
            to_nodes = set(int(x) for x in self.links_df['to_node_id'].dropna())
        except (ValueError, TypeError) as e:
            self._add_issue('ERROR', f'Cannot convert node IDs to integers: {str(e)}', 'level1_data_types')
            level_result['passed'] = False
            print(f"    ✗ Node ID type conversion failed: {str(e)}")
            self.results['levels']['level1'] = level_result
            return False
        
        # Debug info
        print(f"       node.csv has {len(node_ids)} unique node IDs")
        print(f"       link.csv references {len(from_nodes | to_nodes)} unique node IDs")
        if node_ids:
            print(f"       node.csv range: {min(node_ids)} to {max(node_ids)}")
            print(f"       node.csv first 10: {sorted(list(node_ids))[:10]}")
        if from_nodes or to_nodes:
            all_link = from_nodes | to_nodes
            print(f"       link.csv range: {min(all_link)} to {max(all_link)}")
            print(f"       link.csv first 10: {sorted(list(all_link))[:10]}")
        
        # Check for invalid from_nodes
        invalid_from = from_nodes - node_ids
        if invalid_from:
            examples = sorted(invalid_from)[:5]
            print(f"       DEBUG: First 5 invalid from_node_ids: {examples}")
            print(f"       DEBUG: Are these in node_ids? {[x in node_ids for x in examples]}")
            self._add_issue('ERROR', 
                          f'link.csv has {len(invalid_from)} invalid from_node_id values not in node.csv. Examples: {examples}',
                          'level1_link_endpoints')
            level_result['passed'] = False
            print(f"    ✗ {len(invalid_from)} invalid from_node_id values")
        else:
            print("    ✓ All from_node_id values valid")
        
        # Check for invalid to_nodes
        invalid_to = to_nodes - node_ids
        if invalid_to:
            examples = sorted(invalid_to)[:5]
            print(f"       DEBUG: First 5 invalid to_node_ids: {examples}")
            self._add_issue('ERROR', 
                          f'link.csv has {len(invalid_to)} invalid to_node_id values not in node.csv. Examples: {examples}',
                          'level1_link_endpoints')
            level_result['passed'] = False
            print(f"    ✗ {len(invalid_to)} invalid to_node_id values")
        else:
            print("    ✓ All to_node_id values valid")
        
        self.results['levels']['level1'] = level_result
        return level_result['passed']
    
    def _level2_zone_validation(self):
        """Level 2: Zone centroids and connector links"""
        level_result = {
            'name': 'Zone Consistency',
            'checks': [],
            'passed': True
        }
        
        # Check 2.1: Zone Centroids
        print("  Check 2.1: Zone centroid validation...")
        
        # Check if zone_id column exists in nodes
        if 'zone_id' not in self.nodes_df.columns:
            self._add_issue('ERROR', 'zone_id column not found in node.csv - zone validation failed', 'level2_zone_centroids')
            level_result['passed'] = False
            print("    ✗ node.csv - No zone_id column found")
        else:
            # Find centroids (where node_id == zone_id)
            centroids = self.nodes_df[self.nodes_df['node_id'] == self.nodes_df['zone_id']]
            
            if len(centroids) == 0:
                self._add_issue('ERROR', 'No centroid nodes found in node.csv (where node_id == zone_id)', 'level2_zone_centroids')
                level_result['passed'] = False
                print("    ✗ node.csv - No centroid nodes found")
            else:
                print(f"    ✓ node.csv - Found {len(centroids)} centroid nodes")
                
                # Check if centroids are at the top
                zone_nodes = self.nodes_df[self.nodes_df['zone_id'].notna()]
                if len(zone_nodes) > 0:
                    first_n = min(len(centroids) * 2, len(self.nodes_df))
                    top_nodes = self.nodes_df.head(first_n)
                    centroids_at_top = len(top_nodes[top_nodes['node_id'] == top_nodes['zone_id']])
                    
                    if centroids_at_top < len(centroids):
                        self._add_issue('WARNING', 
                                      f'Only {centroids_at_top}/{len(centroids)} centroid nodes grouped at top of node.csv',
                                      'level2_zone_centroids')
                        print(f"    ⚠ node.csv - Centroids not grouped at top")
                    else:
                        print(f"    ✓ node.csv - Centroids properly grouped at top")
        
        # Check 2.2: Connector Links
        print("  Check 2.2: Connector link validation...")
        
        if 'zone_id' not in self.nodes_df.columns:
            print("    ✗ Skipping connector check - no zone_id in node.csv")
        else:
            centroids = self.nodes_df[self.nodes_df['node_id'] == self.nodes_df['zone_id']]
            centroid_ids = set(centroids['node_id'].values)
            
            if len(centroid_ids) == 0:
                print("    ✗ Skipping connector check - no centroids found")
            else:
                # Find connector links (links connected to centroids)
                connector_links = self.links_df[
                    (self.links_df['from_node_id'].isin(centroid_ids)) | 
                    (self.links_df['to_node_id'].isin(centroid_ids))
                ]
                
                if len(connector_links) == 0:
                    self._add_issue('ERROR', 
                                  'No connector links found in link.csv between centroids and network',
                                  'level2_connector_links')
                    level_result['passed'] = False
                    print(f"    ✗ link.csv - No connector links found")
                else:
                    print(f"    ✓ link.csv - Found {len(connector_links)} connector links")
        
        self.results['levels']['level2'] = level_result
    
    def _level3_attribute_validation(self):
        """Level 3: Dual unit system validation (metric & imperial)"""
        level_result = {
            'name': 'Attribute Unit Check (Dual Systems)',
            'checks': [],
            'passed': True
        }
        
        # Check 3.1: Unit System Existence
        print("  Check 3.1: Unit system attributes...")
        
        # Metric system: length (meters), free_speed (km/h)
        has_metric = 'length' in self.links_df.columns and 'free_speed' in self.links_df.columns
        # Imperial system: vdf_length_mi (miles), vdf_free_speed_mph (mph)
        has_imperial = 'vdf_length_mi' in self.links_df.columns and 'vdf_free_speed_mph' in self.links_df.columns
        
        if has_metric:
            print("    ✓ Metric system: length (meters), free_speed (km/h)")
        else:
            missing = []
            if 'length' not in self.links_df.columns:
                missing.append('length')
            if 'free_speed' not in self.links_df.columns:
                missing.append('free_speed')
            self._add_issue('ERROR', f'Metric system incomplete in link.csv. Missing: {", ".join(missing)}', 'level3_unit_system')
            level_result['passed'] = False
            print(f"    ✗ Metric system incomplete. Missing: {', '.join(missing)}")
        
        if has_imperial:
            print("    ✓ Imperial system: vdf_length_mi (miles), vdf_free_speed_mph (mph)")
        else:
            missing = []
            if 'vdf_length_mi' not in self.links_df.columns:
                missing.append('vdf_length_mi')
            if 'vdf_free_speed_mph' not in self.links_df.columns:
                missing.append('vdf_free_speed_mph')
            self._add_issue('ERROR', f'Imperial system incomplete in link.csv. Missing: {", ".join(missing)}', 'level3_unit_system')
            level_result['passed'] = False
            print(f"    ✗ Imperial system incomplete. Missing: {', '.join(missing)}")
        
        # Check 3.2: Metric System Validation
        if has_metric:
            print("  Check 3.2: Metric system validation...")
            
            lengths = self.links_df['length'].dropna()
            speeds = self.links_df['free_speed'].dropna()
            
            if len(lengths) == 0:
                self._add_issue('ERROR', 'length column in link.csv has no valid values', 'level3_metric')
                level_result['passed'] = False
                print("    ✗ length has no values")
            else:
                min_len = lengths.min()
                max_len = lengths.max()
                
                if min_len < 0:
                    self._add_issue('ERROR', 'length in link.csv contains negative values', 'level3_metric')
                    level_result['passed'] = False
                    print(f"    ✗ length has negative values")
                elif max_len > 50000:
                    self._add_issue('ERROR', f'length in link.csv unrealistic (max={max_len:.1f}m)', 'level3_metric')
                    level_result['passed'] = False
                    print(f"    ✗ length unrealistic (max={max_len:.1f}m)")
                else:
                    print(f"    ✓ length (meters): {min_len:.1f} - {max_len:.1f}")
            
            if len(speeds) == 0:
                self._add_issue('ERROR', 'free_speed column in link.csv has no valid values', 'level3_metric')
                level_result['passed'] = False
                print("    ✗ free_speed has no values")
            else:
                min_speed = speeds.min()
                max_speed = speeds.max()
                
                if max_speed > 200:
                    self._add_issue('ERROR', f'free_speed in link.csv unrealistic (max={max_speed:.1f} km/h)', 'level3_metric')
                    level_result['passed'] = False
                    print(f"    ✗ free_speed unrealistic (max={max_speed:.1f} km/h)")
                elif max_speed < 5:
                    self._add_issue('ERROR', f'free_speed in link.csv too low (max={max_speed:.1f} km/h)', 'level3_metric')
                    level_result['passed'] = False
                    print(f"    ✗ free_speed too low (max={max_speed:.1f} km/h)")
                else:
                    print(f"    ✓ free_speed (km/h): {min_speed:.1f} - {max_speed:.1f}")
        
        # Check 3.3: Imperial System Validation
        if has_imperial:
            print("  Check 3.3: Imperial system validation...")
            
            lengths_mi = self.links_df['vdf_length_mi'].dropna()
            speeds_mph = self.links_df['vdf_free_speed_mph'].dropna()
            
            if len(lengths_mi) == 0:
                self._add_issue('ERROR', 'vdf_length_mi column in link.csv has no valid values', 'level3_imperial')
                level_result['passed'] = False
                print("    ✗ vdf_length_mi has no values")
            else:
                min_len = lengths_mi.min()
                max_len = lengths_mi.max()
                
                if min_len < 0:
                    self._add_issue('ERROR', 'vdf_length_mi in link.csv contains negative values', 'level3_imperial')
                    level_result['passed'] = False
                    print(f"    ✗ vdf_length_mi has negative values")
                elif max_len > 50:
                    self._add_issue('ERROR', f'vdf_length_mi in link.csv unrealistic (max={max_len:.1f} miles)', 'level3_imperial')
                    level_result['passed'] = False
                    print(f"    ✗ vdf_length_mi unrealistic (max={max_len:.1f} miles)")
                else:
                    print(f"    ✓ vdf_length_mi (miles): {min_len:.3f} - {max_len:.1f}")
            
            if len(speeds_mph) == 0:
                self._add_issue('ERROR', 'vdf_free_speed_mph column in link.csv has no valid values', 'level3_imperial')
                level_result['passed'] = False
                print("    ✗ vdf_free_speed_mph has no values")
            else:
                min_speed = speeds_mph.min()
                max_speed = speeds_mph.max()
                
                if max_speed > 120:
                    self._add_issue('ERROR', f'vdf_free_speed_mph in link.csv unrealistic (max={max_speed:.1f} mph)', 'level3_imperial')
                    level_result['passed'] = False
                    print(f"    ✗ vdf_free_speed_mph unrealistic (max={max_speed:.1f} mph)")
                elif max_speed < 5:
                    self._add_issue('ERROR', f'vdf_free_speed_mph in link.csv too low (max={max_speed:.1f} mph)', 'level3_imperial')
                    level_result['passed'] = False
                    print(f"    ✗ vdf_free_speed_mph too low (max={max_speed:.1f} mph)")
                else:
                    print(f"    ✓ vdf_free_speed_mph (mph): {min_speed:.1f} - {max_speed:.1f}")
        
        # Check 3.4: Unit Conversion Correlation
        if has_metric and has_imperial:
            print("  Check 3.4: Unit conversion correlation...")
            
            # Check correlation between metric and imperial
            valid_data = self.links_df[
                (self.links_df['length'].notna()) & 
                (self.links_df['vdf_length_mi'].notna()) &
                (self.links_df['length'] > 0) &
                (self.links_df['vdf_length_mi'] > 0)
            ]
            
            if len(valid_data) > 0:
                # Calculate conversion ratio (should be ~1609.34 m/mile)
                sample = valid_data.head(100)
                sample['calc_ratio'] = sample['length'] / sample['vdf_length_mi']
                avg_ratio = sample['calc_ratio'].mean()
                
                expected_ratio = 1609.34
                ratio_error = abs(avg_ratio - expected_ratio) / expected_ratio
                
                if ratio_error > 0.05:  # More than 5% error
                    self._add_issue('WARNING', 
                                  f'Length conversion may be incorrect: avg ratio={avg_ratio:.1f} m/mi (expected ~1609.3)',
                                  'level3_conversion')
                    print(f"    ⚠ Length conversion: ratio={avg_ratio:.1f} m/mi (expected ~1609.3)")
                else:
                    print(f"    ✓ Length conversion correct: {avg_ratio:.1f} m/mi")
            
            # Check speed conversion
            valid_speed = self.links_df[
                (self.links_df['free_speed'].notna()) & 
                (self.links_df['vdf_free_speed_mph'].notna()) &
                (self.links_df['free_speed'] > 0) &
                (self.links_df['vdf_free_speed_mph'] > 0)
            ]
            
            if len(valid_speed) > 0:
                sample = valid_speed.head(100)
                sample['calc_ratio'] = sample['free_speed'] / sample['vdf_free_speed_mph']
                avg_ratio = sample['calc_ratio'].mean()
                
                expected_ratio = 1.60934  # km/h to mph
                ratio_error = abs(avg_ratio - expected_ratio) / expected_ratio
                
                if ratio_error > 0.05:
                    self._add_issue('WARNING', 
                                  f'Speed conversion may be incorrect: avg ratio={avg_ratio:.2f} (expected ~1.609)',
                                  'level3_conversion')
                    print(f"    ⚠ Speed conversion: ratio={avg_ratio:.2f} (expected ~1.609)")
                else:
                    print(f"    ✓ Speed conversion correct: {avg_ratio:.2f}")
        
        # Check 3.5: Capacity Validation
        print("  Check 3.5: Capacity validation...")
        
        if 'capacity' not in self.links_df.columns:
            self._add_issue('WARNING', 'capacity column not found in link.csv', 'level3_capacity')
            print("    ⚠ capacity column not found")
        else:
            capacities = self.links_df['capacity'].dropna()
            if len(capacities) == 0:
                self._add_issue('WARNING', 'capacity column in link.csv has no valid values', 'level3_capacity')
                print("    ⚠ capacity has no values")
            else:
                min_cap = capacities.min()
                max_cap = capacities.max()
                
                # Check for unrealistic capacity values - now WARNING instead of ERROR
                if max_cap > 10000:
                    self._add_issue('WARNING', 
                                  f'capacity in link.csv very high (max={max_cap:.0f}). Typical range: 500-3000 per lane',
                                  'level3_capacity')
                    print(f"    ⚠ capacity very high (max={max_cap:.0f})")
                elif min_cap < 0:
                    self._add_issue('ERROR', 'capacity in link.csv contains negative values', 'level3_capacity')
                    level_result['passed'] = False
                    print(f"    ✗ capacity has negative values")
                elif min_cap < 100:
                    self._add_issue('WARNING', f'capacity in link.csv low (min={min_cap:.0f})', 'level3_capacity')
                    print(f"    ⚠ capacity low (min={min_cap:.0f})")
                else:
                    print(f"    ✓ capacity: {min_cap:.0f} - {max_cap:.0f}")
                
                # Check per-lane capacity - now WARNING instead of ERROR
                if 'lanes' in self.links_df.columns:
                    links_with_lanes = self.links_df[
                        (self.links_df['capacity'].notna()) & 
                        (self.links_df['lanes'].notna()) & 
                        (self.links_df['lanes'] > 0)
                    ]
                    if len(links_with_lanes) > 0:
                        links_with_lanes['cap_per_lane'] = links_with_lanes['capacity'] / links_with_lanes['lanes']
                        avg_cap = links_with_lanes['cap_per_lane'].mean()
                        
                        if avg_cap < 800 or avg_cap > 3000:
                            self._add_issue('WARNING', 
                                          f'capacity/lane in link.csv unusual ({avg_cap:.0f} veh/hr). Typical: 1500-2200',
                                          'level3_capacity')
                            print(f"    ⚠ capacity/lane unusual ({avg_cap:.0f} veh/hr)")
                        else:
                            print(f"    ✓ capacity/lane: {avg_cap:.0f} veh/hr")
        
        self.results['levels']['level3'] = level_result
    
    def _find_file(self, pattern, default_name):
        """Find a file matching pattern in network directory"""
        if not os.path.exists(self.network_dir):
            return None
        
        # First, check for exact match
        exact_path = os.path.join(self.network_dir, default_name)
        if os.path.exists(exact_path):
            return exact_path
        
        # If exact match not found, look for pattern
        # But prioritize files that match more closely
        candidates = []
        for filename in os.listdir(self.network_dir):
            if pattern in filename.lower() and filename.lower().endswith('.csv'):
                candidates.append(filename)
        
        # Sort candidates to prefer shorter names (more likely to be the right file)
        # e.g., "node.csv" over "activity_node.csv"
        if candidates:
            candidates.sort(key=len)
            return os.path.join(self.network_dir, candidates[0])
        
        return None
    
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
    
    def _print_final_summary(self):
        """Print clear final summary"""
        print("\n" + "=" * 60)
        print("NETWORK VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Status: {self.results['summary']['status']}")
        print(f"Errors: {self.results['summary']['errors']}")
        print(f"Warnings: {self.results['summary']['warnings']}")
        print("-" * 60)
        
        # Print level results with descriptive names
        print("\nLevel Results:")
        level_descriptions = {
            'level1': 'Basic Data File Validation',
            'level2': 'Zone Consistency',
            'level3': 'Attribute Unit Check (Dual Systems)'
        }
        
        for level_key, description in level_descriptions.items():
            if level_key in self.results['levels']:
                level_data = self.results['levels'][level_key]
                status = 'PASSED' if level_data.get('passed', False) else 'FAILED'
                status_icon = '✓' if status == 'PASSED' else '✗'
                print(f"  {status_icon} Level {level_key[-1]}: {description} - {status}")
        
        print()
        
        if self.results['summary']['errors'] == 0 and self.results['summary']['warnings'] == 0:
            print("✓ NETWORK VALIDATION CHECK PASSED")
            print("  All validation levels completed successfully.")
            print("  Your network is ready for traffic assignment.")
        elif self.results['summary']['errors'] == 0:
            print("⚠ NETWORK VALIDATION CHECK PASSED WITH WARNINGS")
            print("  Review the following warnings:\n")
            
            # Group by file
            node_issues = [i for i in self.results['issues'] if 'node.csv' in i['message'] and i['severity'] == 'WARNING']
            link_issues = [i for i in self.results['issues'] if 'link.csv' in i['message'] and i['severity'] == 'WARNING']
            
            if node_issues:
                print("  node.csv:")
                for issue in node_issues[:3]:
                    print(f"    - {issue['message']}")
                if len(node_issues) > 3:
                    print(f"    ... and {len(node_issues)-3} more")
                print()
            
            if link_issues:
                print("  link.csv:")
                for issue in link_issues[:3]:
                    print(f"    - {issue['message']}")
                if len(link_issues) > 3:
                    print(f"    ... and {len(link_issues)-3} more")
        else:
            print("✗ NETWORK VALIDATION CHECK FAILED")
            print(f"  {self.results['summary']['errors']} error(s) must be fixed.\n")
            
            # Group errors by file with better categorization
            node_errors = []
            link_errors = []
            
            for i in self.results['issues']:
                if i['severity'] != 'ERROR':
                    continue
                
                msg = i['message']
                cat = i.get('category', '')
                
                # Link endpoint errors go to link.csv
                if 'level1_link_endpoints' in cat or 'from_node_id' in msg or 'to_node_id' in msg:
                    link_errors.append(msg)
                # Other node-related errors
                elif 'node.csv' in msg and 'link.csv' not in msg:
                    node_errors.append(msg)
                # Other link-related errors
                elif 'link.csv' in msg:
                    link_errors.append(msg)
                else:
                    # Default to link errors if unclear
                    link_errors.append(msg)
            
            print("  Files to fix:\n")
            
            if node_errors:
                print("  node.csv:")
                for error in node_errors[:3]:
                    print(f"    - {error}")
                if len(node_errors) > 3:
                    print(f"    ... and {len(node_errors)-3} more")
                print()
            
            if link_errors:
                print("  link.csv:")
                for error in link_errors[:3]:
                    print(f"    - {error}")
                if len(link_errors) > 3:
                    print(f"    ... and {len(link_errors)-3} more")
    
    def _save_results(self):
        """Save validation results to JSON"""
        try:
            output_file = os.path.join(self.network_dir, 'network_validation_report.json')
            with open(output_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            print(f"\nReport saved to: {output_file}")
        except Exception as e:
            print(f"\nWarning: Could not save report - {str(e)}")


def main(network_dir='connected_network', max_level=3):
    """
    Run readiness validation
    
    Usage:
        python readiness_validator.py [network_dir] [max_level]
        
    Args:
        network_dir: Directory containing node.csv and link.csv (default: connected_network)
        max_level: Maximum validation level (1-3), default=3
    """
    validator = ReadinessValidator(network_dir)
    results = validator.validate(max_level)
    
    return results['summary']['errors'] == 0


if __name__ == '__main__':
    network_dir = sys.argv[1] if len(sys.argv) > 1 else 'connected_network'
    max_level = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    
    success = main(network_dir, max_level)
    sys.exit(0 if success else 1)