"""
Accessibility Validator for GMNS Networks (All Platforms)
Uses DTALite Python package on Windows, Linux, and Mac
@author: hnzhu
"""

import os
import sys
import json
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
            gmns_tools_dir: Optional directory containing settings.csv
        """
        self.network_dir = network_dir
        self.gmns_tools_dir = gmns_tools_dir
        self.settings_file = None
        self.dtalite_available = False
        
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'network_dir': network_dir,
            'method': 'python_package',
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
            # Check prerequisites
            prereq_ok = self._check_prerequisites()
            if not prereq_ok:
                all_passed = False
            
            if not prereq_ok:
                self._save_results()
                self._print_final_summary()
                return self.results
            
            # Prepare network
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
            issues.append("[ERROR] node.csv - NOT FOUND")
        
        if not link_file:
            self._add_issue('ERROR', 'link.csv not found in network directory', 'prereq_files')
            check_result['passed'] = False
            issues.append("[ERROR] link.csv - NOT FOUND")
        
        # Check for DTALite package
        print("Method: DTALite Python package")
        try:
            import DTALite
            self.dtalite_available = True
            print(f"  [OK] DTALite package found (version: {getattr(DTALite, '__version__', 'unknown')})")
        except ImportError:
            self._add_issue('ERROR', 
                          'DTALite package not found. Install with: pip install DTALite', 
                          'prereq_tools')
            check_result['passed'] = False
            issues.append("[ERROR] DTALite package - NOT FOUND")
            issues.append("         Install with: pip install DTALite")
        
        # Check for settings.csv
        if not self.gmns_tools_dir:
            self.gmns_tools_dir = self._find_gmns_tools()
        
        if self.gmns_tools_dir:
            self.settings_file = self._find_settings_file()
        
        if not self.settings_file:
            # Try to find settings.csv in network_dir or current directory
            alt_locations = [
                os.path.join(self.network_dir, 'settings.csv'),
                'settings.csv'
            ]
            for loc in alt_locations:
                if os.path.exists(loc):
                    self.settings_file = os.path.abspath(loc)
                    break
            
            if not self.settings_file:
                self._add_issue('ERROR', 
                              'settings.csv not found. Suggestion: Add settings.csv to GMNS_Tools folder or network directory', 
                              'prereq_tools')
                check_result['passed'] = False
                issues.append("[ERROR] settings.csv - NOT FOUND")
                issues.append("         Create settings.csv with DTALite configuration")
        
        # Only print details if there are issues
        if issues:
            print("\nPrerequisites check:")
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
            # Copy settings.csv to network directory if not already there
            dest_settings = os.path.join(self.network_dir, 'settings.csv')
            
            if not os.path.exists(dest_settings):
                shutil.copy2(self.settings_file, dest_settings)
                print(f"  Copied settings.csv to {self.network_dir}/")
            
        except Exception as e:
            self._add_issue('ERROR', f'Failed to copy settings.csv: {str(e)}', 'preparation')
            prep_result['passed'] = False
            print(f"Preparation error: {str(e)}\n")
        
        self.results['accessibility_check']['preparation'] = prep_result
        return prep_result['passed']
    
    def _run_assignment(self):
        """Execute DTALite traffic assignment using Python package"""
        assignment_result = {
            'name': 'Traffic Assignment',
            'checks': [],
            'passed': True
        }
        
        try:
            # Change to network directory
            original_dir = os.getcwd()
            os.chdir(self.network_dir)
            
            # Import DTALite
            import DTALite as dta
            
            # Run assignment
            print("  Running dta.assignment()...")
            dta.assignment()
            
            # Change back to original directory
            os.chdir(original_dir)
            
            # Check if output files were created
            zone_acc_file = os.path.join(self.network_dir, 'zone_accessibility.csv')
            if not os.path.exists(zone_acc_file):
                self._add_issue('ERROR', 
                              'zone_accessibility.csv not generated. Check network connectivity and demand.',
                              'assignment_output')
                print(f"[ERROR] zone_accessibility.csv not generated")
                assignment_result['passed'] = False
            else:
                print("  [OK] Assignment completed successfully")
            
        except Exception as e:
            # Make sure we return to original directory even if there's an error
            try:
                os.chdir(original_dir)
            except:
                pass
            
            self._add_issue('ERROR', f'Error running DTALite package: {str(e)}', 'assignment_execution')
            print(f"[ERROR] {str(e)}")
            assignment_result['passed'] = False
            
            # Provide helpful message
            error_msg = str(e).lower()
            if 'no module named' in error_msg:
                print("  Suggestion: Install DTALite with: pip install DTALite")
            elif 'settings' in error_msg or 'file not found' in error_msg:
                print("  Suggestion: Ensure settings.csv is in the network directory")
        
        self.results['accessibility_check']['assignment'] = assignment_result
        return assignment_result['passed']
    
    def _validate_accessibility_results(self):
        """Validate accessibility outputs"""
        validation_result = {
            'name': 'Results Validation',
            'checks': [],
            'passed': True
        }
        
        issues = []
        
        # Check zone_accessibility.csv
        zone_acc_file = os.path.join(self.network_dir, 'zone_accessibility.csv')
        
        if not os.path.exists(zone_acc_file):
            self._add_issue('ERROR', 'zone_accessibility.csv not found after assignment', 'accessibility_output')
            validation_result['passed'] = False
            issues.append("[ERROR] zone_accessibility.csv - NOT FOUND")
        else:
            try:
                accessibility_df = pd.read_csv(zone_acc_file)
                
                print(f"  [OK] zone_accessibility.csv generated ({len(accessibility_df)} zones)")
                
                # Check for required columns
                required_cols = ['zone_id']
                missing_cols = [col for col in required_cols if col not in accessibility_df.columns]
                
                if missing_cols:
                    self._add_issue('WARNING', 
                                  f'zone_accessibility.csv missing columns: {", ".join(missing_cols)}',
                                  'accessibility_columns')
                    issues.append(f"[WARNING] Missing columns: {', '.join(missing_cols)}")
                
                # Check connectivity metrics
                if 'origin_count' in accessibility_df.columns and 'destination_count' in accessibility_df.columns:
                    origin_counts = accessibility_df['origin_count'].dropna()
                    dest_counts = accessibility_df['destination_count'].dropna()
                    
                    if len(origin_counts) > 0 and len(dest_counts) > 0:
                        zones_with_no_origins = (accessibility_df['origin_count'] == 0).sum()
                        zones_with_no_dests = (accessibility_df['destination_count'] == 0).sum()
                        
                        total_zones = len(accessibility_df)
                        
                        print(f"  origin_count:      avg={origin_counts.mean():.1f}, max={origin_counts.max():.0f}")
                        print(f"  destination_count: avg={dest_counts.mean():.1f}, max={dest_counts.max():.0f}")
                        
                        # Check for poorly connected zones
                        if zones_with_no_origins > 0 or zones_with_no_dests > 0:
                            self._add_issue('WARNING', 
                                          f'{zones_with_no_origins} zones have no origins, {zones_with_no_dests} have no destinations',
                                          'connectivity')
                            issues.append(f"[WARNING] {zones_with_no_origins} zones with no origins, {zones_with_no_dests} with no destinations")
                        
                        # Check if majority of zones are poorly connected
                        poorly_connected = (
                            (accessibility_df['origin_count'] < 5) | 
                            (accessibility_df['destination_count'] < 5)
                        ).sum()
                        
                        if poorly_connected > total_zones * 0.5:
                            self._add_issue('WARNING', 
                                          f'{poorly_connected}/{total_zones} zones are poorly connected (less than 5 connections)',
                                          'poor_connectivity')
                            issues.append(f"[WARNING] {poorly_connected}/{total_zones} zones poorly connected")
                    else:
                        issues.append("[WARNING] No valid origin_count or destination_count values")
                else:
                    issues.append("[WARNING] origin_count or destination_count columns not found")
                
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
                            issues.append("[ERROR] Negative accessibility values found")
                
            except Exception as e:
                self._add_issue('ERROR', f'Error reading zone_accessibility.csv: {str(e)}', 'accessibility_read')
                validation_result['passed'] = False
                issues.append(f"[ERROR] Error reading file: {str(e)}")
        
        # Check link_performance.csv (brief check)
        link_perf_file = os.path.join(self.network_dir, 'link_performance.csv')
        
        if not os.path.exists(link_perf_file):
            issues.append("[WARNING] link_performance.csv - NOT FOUND")
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
                            issues.append("[WARNING] No traffic assigned")
                        else:
                            print(f"  [OK] Traffic assigned: {total_volume:.0f} total volume")
                
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
        """Find GMNS_Tools folder in current, parent, or package directory"""
        # Get package directory (where this script is located)
        package_dir = os.path.dirname(os.path.abspath(__file__))

        search_locations = [
            # First check package directory (for pip installed package)
            os.path.join(package_dir, 'GMNS_Tools'),
            # Then check current working directory
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
        print(f"Method: DTALite Python package")
        print(f"Status: {self.results['summary']['status']}")
        print(f"Errors: {self.results['summary']['errors']}")
        print(f"Warnings: {self.results['summary']['warnings']}")
        print("-" * 60)
        
        if self.results['summary']['errors'] == 0 and self.results['summary']['warnings'] == 0:
            print("\n[OK] ACCESSIBILITY CHECK PASSED")
        elif self.results['summary']['errors'] == 0:
            print("\n[WARNING] ACCESSIBILITY CHECK PASSED WITH WARNINGS")
            # Show warnings
            warnings = [i for i in self.results['issues'] if i['severity'] == 'WARNING']
            if warnings:
                print("\nWarnings:")
                for w in warnings[:5]:
                    print(f"  - {w['message']}")
        else:
            print("\n[ERROR] ACCESSIBILITY CHECK FAILED")
            # Show errors
            errors = [i for i in self.results['issues'] if i['severity'] == 'ERROR']
            if errors:
                print("\nErrors:")
                for e in errors[:5]:
                    print(f"  - {e['message']}")
                
                # Helpful suggestions
                if any('DTALite package' in e['message'] for e in errors):
                    print("\nSuggestion:")
                    print("  Install DTALite: pip install DTALite")
    
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
    Run accessibility validation using DTALite Python package
    
    Usage:
        python validate_accessibility.py [network_dir] [gmns_tools_dir]
        
    Args:
        network_dir: Directory containing node.csv and link.csv (default: connected_network)
        gmns_tools_dir: Optional path to GMNS_Tools folder (auto-detected if not provided)
        
    Requirements:
        - DTALite package: pip install DTALite
        - settings.csv in GMNS_Tools or network directory
    """
    validator = AccessibilityValidator(network_dir, gmns_tools_dir)
    results = validator.validate()
    
    return results['summary']['errors'] == 0


if __name__ == '__main__':
    network_dir = sys.argv[1] if len(sys.argv) > 1 else 'connected_network'
    gmns_tools_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = main(network_dir, gmns_tools_dir)
    sys.exit(0 if success else 1)