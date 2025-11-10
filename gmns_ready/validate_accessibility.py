"""
Accessibility Validator for GMNS Networks
Runs traffic assignment and validates accessibility metrics
@author: hnzhu
"""

import os
import sys
import json
import subprocess
import shutil
import pandas as pd
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


class AccessibilityValidator:
    """Validates network accessibility using DTALite traffic assignment"""
    
    def __init__(self, network_dir='connected_network', gmns_tools_dir=None):
        """
        Args:
            network_dir: Directory containing node.csv and link.csv
            gmns_tools_dir: Directory containing DTALite executable and settings.csv
        """
        self.network_dir = network_dir
        self.gmns_tools_dir = gmns_tools_dir
        self.taplite_exe = None
        self.settings_file = None
        
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'network_dir': network_dir,
            'accessibility_check': {},
            'issues': [],
            'summary': {'status': 'PASS', 'errors': 0, 'warnings': 0}
        }
        
    def validate(self):
        """Run accessibility validation"""
        print("GMNS Accessibility Validator")
        print("=" * 60)
        print(f"Network: {self.network_dir}\n")
        
        all_passed = True
        
        try:
            # Check prerequisites (silently unless there's an issue)
            prereq_ok = self._check_prerequisites()
            if not prereq_ok:
                all_passed = False
            
            if not prereq_ok:
                self._save_results()
                self._print_final_summary()
                return self.results
            
            # Prepare network (silently unless there's an issue)
            prep_ok = self._prepare_network()
            if not prep_ok:
                all_passed = False
                self._save_results()
                self._print_final_summary()
                return self.results
            
            # Run traffic assignment
            print("Running DTALite traffic assignment...")
            assignment_ok = self._run_assignment()
            if not assignment_ok:
                all_passed = False
                self._save_results()
                self._print_final_summary()
                return self.results
            
            # Validate accessibility results
            print("\nValidating results...")
            self._validate_accessibility_results()
            
        except Exception as e:
            self._add_issue('ERROR', f'Unexpected error: {str(e)}', 'system')
            import traceback
            traceback.print_exc()
        
        finally:
            self._save_results()
        
        self._print_final_summary()
        return self.results
    
    def _check_prerequisites(self):
        """Check if all required files and tools are available"""
        check_result = {
            'name': 'Prerequisites Check',
            'checks': [],
            'passed': True
        }
        
        issues = []
        
        # Check network files
        node_file = self._find_file("node", "node.csv")
        link_file = self._find_file("link", "link.csv")
        
        if not node_file:
            self._add_issue('ERROR', 'node.csv not found in network directory', 'prereq_files')
            check_result['passed'] = False
            issues.append("✗ node.csv - NOT FOUND")
        
        if not link_file:
            self._add_issue('ERROR', 'link.csv not found in network directory', 'prereq_files')
            check_result['passed'] = False
            issues.append("✗ link.csv - NOT FOUND")
        
        # Check GMNS Tools
        if not self.gmns_tools_dir:
            self.gmns_tools_dir = self._find_gmns_tools()
        
        if not self.gmns_tools_dir:
            self._add_issue('ERROR', 'GMNS_Tools directory not found. Suggestion: Create GMNS_Tools folder with DTALite executable and settings.csv', 'prereq_tools')
            check_result['passed'] = False
            issues.append("✗ GMNS_Tools directory - NOT FOUND")
        else:
            # Check DTALite executable
            self.taplite_exe = self._find_taplite_exe()
            if not self.taplite_exe:
                self._add_issue('ERROR', 'DTALite executable not found in GMNS_Tools. Suggestion: Add TAPLite*.exe to GMNS_Tools folder', 'prereq_tools')
                check_result['passed'] = False
                issues.append("✗ DTALite executable - NOT FOUND")
            
            # Check settings.csv
            self.settings_file = self._find_settings_file()
            if not self.settings_file:
                self._add_issue('ERROR', 'settings.csv not found in GMNS_Tools. Suggestion: Add settings.csv to GMNS_Tools folder', 'prereq_tools')
                check_result['passed'] = False
                issues.append("✗ settings.csv - NOT FOUND")
        
        # Only print details if there are issues
        if issues:
            print("Prerequisites check:")
            for issue in issues:
                print(f"  {issue}")
            print()
        
        self.results['accessibility_check']['prerequisites'] = check_result
        return check_result['passed']
    
    def _prepare_network(self):
        """Copy settings.csv to network directory"""
        prep_result = {
            'name': 'Network Preparation',
            'checks': [],
            'passed': True
        }
        
        try:
            # Copy settings.csv to network directory
            dest_settings = os.path.join(self.network_dir, 'settings.csv')
            
            if not os.path.exists(dest_settings):
                shutil.copy2(self.settings_file, dest_settings)
            
        except Exception as e:
            self._add_issue('ERROR', f'Failed to copy settings.csv: {str(e)}', 'preparation')
            prep_result['passed'] = False
            print(f"Preparation error: {str(e)}\n")
        
        self.results['accessibility_check']['preparation'] = prep_result
        return prep_result['passed']
    
    def _run_assignment(self):
        """Execute DTALite traffic assignment"""
        assignment_result = {
            'name': 'Traffic Assignment',
            'checks': [],
            'passed': True
        }
        
        try:
            # Change to network directory
            original_dir = os.getcwd()
            os.chdir(self.network_dir)
            
            # Run DTALite executable
            result = subprocess.run(
                [self.taplite_exe],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            # Change back to original directory
            os.chdir(original_dir)
            
            # Check if assignment completed successfully
            if result.returncode != 0:
                self._add_issue('ERROR', 
                              f'DTALite execution failed (exit code {result.returncode}). Check network files for errors.',
                              'assignment_execution')
                assignment_result['passed'] = False
                print(f"✗ DTALite failed (exit code {result.returncode})")
                if result.stderr:
                    print(f"  Error: {result.stderr[-200:]}")
            else:
                # Check for output files
                output_files = ['link_performance.csv', 'zone_accessibility.csv']
                missing_files = []
                
                for output_file in output_files:
                    output_path = os.path.join(self.network_dir, output_file)
                    if not os.path.exists(output_path):
                        missing_files.append(output_file)
                
                if missing_files:
                    self._add_issue('WARNING', 
                                  f'Expected output files not generated: {", ".join(missing_files)}',
                                  'assignment_outputs')
                    print(f"⚠ Missing output files: {', '.join(missing_files)}")
                else:
                    print(f"✓ DTALite completed successfully")
            
        except subprocess.TimeoutExpired:
            self._add_issue('ERROR', 'DTALite execution timed out (>5 minutes). Network may be too large or have issues.', 'assignment_timeout')
            assignment_result['passed'] = False
            print(f"✗ DTALite timed out")
            os.chdir(original_dir)
        except Exception as e:
            self._add_issue('ERROR', f'Error running DTALite: {str(e)}', 'assignment_error')
            assignment_result['passed'] = False
            print(f"✗ Error: {str(e)}")
            try:
                os.chdir(original_dir)
            except:
                pass
        
        self.results['accessibility_check']['assignment'] = assignment_result
        return assignment_result['passed']
    
    def _validate_accessibility_results(self):
        """Validate accessibility calculation results"""
        validation_result = {
            'name': 'Accessibility Results Validation',
            'checks': [],
            'passed': True
        }
        
        issues = []
        
        # Check zone_accessibility.csv
        accessibility_file = os.path.join(self.network_dir, 'zone_accessibility.csv')
        
        if not os.path.exists(accessibility_file):
            self._add_issue('ERROR', 
                          'zone_accessibility.csv not generated. Check if traffic assignment completed successfully.',
                          'accessibility_output')
            validation_result['passed'] = False
            issues.append("✗ zone_accessibility.csv - NOT FOUND")
        else:
            try:
                # Read accessibility results
                accessibility_df = pd.read_csv(accessibility_file)
                total_zones = len(accessibility_df)
                
                print(f"Zone accessibility results ({total_zones} zones):")
                
                # Check origin_count and destination_count
                if 'origin_count' in accessibility_df.columns and 'destination_count' in accessibility_df.columns:
                    origin_counts = accessibility_df['origin_count'].dropna()
                    dest_counts = accessibility_df['destination_count'].dropna()
                    
                    if len(origin_counts) > 0 and len(dest_counts) > 0:
                        # Print statistics
                        print(f"  origin_count:      min={origin_counts.min():.0f}, avg={origin_counts.mean():.0f}, max={origin_counts.max():.0f}")
                        print(f"  destination_count: min={dest_counts.min():.0f}, avg={dest_counts.mean():.0f}, max={dest_counts.max():.0f}")
                        
                        # Check for zones with 0 origin_count
                        if 'zone_id' in accessibility_df.columns or 'o_zone_id' in accessibility_df.columns:
                            zone_id_col = 'zone_id' if 'zone_id' in accessibility_df.columns else 'o_zone_id'
                            
                            zero_origin = accessibility_df[accessibility_df['origin_count'] == 0]
                            if len(zero_origin) > 0:
                                zero_origin_ids = zero_origin[zone_id_col].tolist()
                                self._add_issue('WARNING', 
                                              f'{len(zero_origin_ids)} zones have 0 origin_count (cannot reach any zones). Zone IDs: {zero_origin_ids[:20]}',
                                              'zero_origin_count')
                                print(f"  ⚠ Zones with 0 origin_count: {zero_origin_ids[:20]}")
                                if len(zero_origin_ids) > 20:
                                    print(f"     ... and {len(zero_origin_ids) - 20} more")
                            
                            zero_dest = accessibility_df[accessibility_df['destination_count'] == 0]
                            if len(zero_dest) > 0:
                                zero_dest_ids = zero_dest[zone_id_col].tolist()
                                self._add_issue('WARNING', 
                                              f'{len(zero_dest_ids)} zones have 0 destination_count (cannot be reached). Zone IDs: {zero_dest_ids[:20]}',
                                              'zero_destination_count')
                                print(f"  ⚠ Zones with 0 destination_count: {zero_dest_ids[:20]}")
                                if len(zero_dest_ids) > 20:
                                    print(f"     ... and {len(zero_dest_ids) - 20} more")
                        
                        # Check if all zones are reachable
                        avg_origin = origin_counts.mean()
                        avg_dest = dest_counts.mean()
                        
                        if avg_origin < total_zones * 0.9 or avg_dest < total_zones * 0.9:
                            self._add_issue('WARNING', 
                                          f'Low connectivity: avg origin_count={avg_origin:.0f}, avg destination_count={avg_dest:.0f} (total zones={total_zones}). Suggestion: Add more connectors to improve zone accessibility.',
                                          'accessibility_connectivity')
                            print(f"  ⚠ Low connectivity detected - consider adding more connectors")
                        else:
                            print(f"  ✓ Good connectivity ({avg_origin:.0f}/{total_zones} zones reachable)")
                    else:
                        issues.append("⚠ No valid origin_count or destination_count values")
                else:
                    issues.append("⚠ origin_count or destination_count columns not found")
                
                # Check accessibility values if present
                if 'accessibility' in accessibility_df.columns:
                    access_values = accessibility_df['accessibility'].dropna()
                    
                    if len(access_values) > 0:
                        min_access = access_values.min()
                        max_access = access_values.max()
                        mean_access = access_values.mean()
                        print(f"  accessibility:     min={min_access:.1f}, avg={mean_access:.1f}, max={max_access:.1f}")
                        
                        # Check for unrealistic values
                        if min_access < 0:
                            self._add_issue('ERROR', 'zone_accessibility.csv contains negative accessibility values', 'accessibility_values')
                            validation_result['passed'] = False
                            issues.append("✗ Negative accessibility values found")
                
            except Exception as e:
                self._add_issue('ERROR', f'Error reading zone_accessibility.csv: {str(e)}', 'accessibility_read')
                validation_result['passed'] = False
                issues.append(f"✗ Error reading file: {str(e)}")
        
        # Check link_performance.csv (brief check)
        link_perf_file = os.path.join(self.network_dir, 'link_performance.csv')
        
        if not os.path.exists(link_perf_file):
            issues.append("⚠ link_performance.csv - NOT FOUND")
        else:
            try:
                link_perf_df = pd.read_csv(link_perf_file)
                
                # Check for volume column
                volume_cols = ['volume', 'vol', 'total_volume']
                volume_col = None
                for col in volume_cols:
                    if col in link_perf_df.columns:
                        volume_col = col
                        break
                
                if volume_col:
                    volumes = link_perf_df[volume_col].dropna()
                    if len(volumes) > 0:
                        total_volume = volumes.sum()
                        
                        # Check if volumes are reasonable
                        if total_volume == 0:
                            self._add_issue('WARNING', 'Total traffic volume is zero. Check network connectivity.', 'traffic_volume')
                            issues.append("⚠ No traffic assigned")
                        else:
                            print(f"  ✓ Traffic assigned: {total_volume:.0f} total volume")
                
            except Exception as e:
                # Silently continue if link_performance can't be read
                pass
        
        # Print issues if any
        if issues:
            print("\nIssues found:")
            for issue in issues:
                print(f"  {issue}")
        
        self.results['accessibility_check']['validation'] = validation_result
    
    def _find_file(self, pattern, default_name):
        """Find exact file in network directory"""
        if not os.path.exists(self.network_dir):
            return None
        
        # Look for exact filename only
        exact_path = os.path.join(self.network_dir, default_name)
        if os.path.exists(exact_path):
            return exact_path
        
        return None
    
    def _find_gmns_tools(self):
        """Find GMNS_Tools folder in current or parent directory"""
        search_locations = [
            'GMNS_Tools',
            'gmns_tools',
            os.path.join('..', 'GMNS_Tools'),
            os.path.join('..', 'gmns_tools'),
            os.path.join(self.network_dir, 'GMNS_Tools'),
            os.path.join(self.network_dir, '..', 'GMNS_Tools')
        ]
        
        for location in search_locations:
            abs_path = os.path.abspath(location)
            if os.path.exists(abs_path) and os.path.isdir(abs_path):
                return abs_path
        
        return None
    
    def _find_taplite_exe(self):
        """Find TAPLite executable in GMNS_Tools folder"""
        if not self.gmns_tools_dir or not os.path.exists(self.gmns_tools_dir):
            return None
        
        for filename in os.listdir(self.gmns_tools_dir):
            if filename.lower().endswith('.exe') and 'taplite' in filename.lower():
                return os.path.abspath(os.path.join(self.gmns_tools_dir, filename))
        
        return None
    
    def _find_settings_file(self):
        """Find settings.csv in GMNS_Tools folder"""
        if not self.gmns_tools_dir or not os.path.exists(self.gmns_tools_dir):
            return None
        
        settings_path = os.path.join(self.gmns_tools_dir, 'settings.csv')
        return os.path.abspath(settings_path) if os.path.exists(settings_path) else None
    
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
        print("ACCESSIBILITY VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Status: {self.results['summary']['status']}")
        print(f"Errors: {self.results['summary']['errors']}")
        print(f"Warnings: {self.results['summary']['warnings']}")
        print("-" * 60)
        
        if self.results['summary']['errors'] == 0 and self.results['summary']['warnings'] == 0:
            print("\n✓ ACCESSIBILITY CHECK PASSED")
        elif self.results['summary']['errors'] == 0:
            print("\n⚠ ACCESSIBILITY CHECK PASSED WITH WARNINGS")
            # Show warnings
            warnings = [i for i in self.results['issues'] if i['severity'] == 'WARNING']
            if warnings:
                print("\nWarnings:")
                for w in warnings[:5]:
                    print(f"  - {w['message']}")
        else:
            print("\n✗ ACCESSIBILITY CHECK FAILED")
            # Show errors
            errors = [i for i in self.results['issues'] if i['severity'] == 'ERROR']
            if errors:
                print("\nErrors:")
                for e in errors[:5]:
                    print(f"  - {e['message']}")
    
    def _save_results(self):
        """Save validation results to JSON"""
        try:
            output_file = os.path.join(self.network_dir, 'accessibility_validation_report.json')
            with open(output_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            print(f"\nReport saved to: {output_file}")
        except Exception as e:
            print(f"\nWarning: Could not save report - {str(e)}")


def main(network_dir='connected_network', gmns_tools_dir=None):
    """
    Run accessibility validation
    
    Usage:
        python accessibility_validator.py [network_dir] [gmns_tools_dir]
        
    Args:
        network_dir: Directory containing node.csv and link.csv (default: connected_network)
        gmns_tools_dir: Optional path to GMNS_Tools folder with DTALite (auto-detected if not provided)
    """
    validator = AccessibilityValidator(network_dir, gmns_tools_dir)
    results = validator.validate()
    
    return results['summary']['errors'] == 0


if __name__ == '__main__':
    network_dir = sys.argv[1] if len(sys.argv) > 1 else 'connected_network'
    gmns_tools_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = main(network_dir, gmns_tools_dir)
    sys.exit(0 if success else 1)