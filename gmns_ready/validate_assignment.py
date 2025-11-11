"""
Assignment-Ready Validator for GMNS Networks
Validates VDF parameters and network attributes for traffic assignment
@author: hnzhu
"""

import os
import json
import pandas as pd
from datetime import datetime

class AssignmentValidator:
    """Validates network readiness for traffic assignment"""
    
    LINK_TYPES = {1: "Motorway/Freeway", 2: "Trunk", 3: "Primary", 4: "Secondary", 
                  5: "Tertiary", 6: "Residential", 7: "Service/Local", 8: "Other"}
    
    VDF_PARAMS = {
        'vdf_alpha': {'unit': 'dimensionless', 'min': 0.0, 'max': 2.0, 'typical': 0.15},
        'vdf_beta': {'unit': 'dimensionless', 'min': 0.0, 'max': 10.0, 'typical': 4.0},
        'vdf_plf': {'unit': 'dimensionless', 'min': 0.0, 'max': 1.0, 'typical': 0.25},
        'vdf_fftt': {'unit': 'minutes', 'min': 0.0, 'typical': None},
        'capacity': {'unit': 'vehicles/hour', 'min': 0.0, 'typical': None}
    }
    
    def __init__(self, network_dir='connected_network'):
        self.network_dir = network_dir
        self.node_file = os.path.join(network_dir, 'node.csv')
        self.link_file = os.path.join(network_dir, 'link.csv')
        self.errors = []
        self.warnings = []
        self.stats = {}
        
    def validate(self):
        """Run validation"""
        print("="*70)
        print("ASSIGNMENT-READY VALIDATOR")
        print("="*70)
        print(f"Network Directory: {self.network_dir}\n")
        
        # Check files exist
        if not self._check_files():
            self._save_and_print_summary()
            return False
        
        # Validate node.csv
        print("CHECKING NODE.CSV")
        print("-"*70)
        self._validate_nodes()
        
        # Validate link.csv
        print("\nCHECKING LINK.CSV")
        print("-"*70)
        self._validate_links()
        
        # Save and print summary
        self._save_and_print_summary()
        
        return len(self.errors) == 0
    
    def _check_files(self):
        """Check if required files exist"""
        if not os.path.exists(self.node_file):
            self.errors.append(f"node.csv not found in {self.network_dir}")
            print(f"[ERROR] ERROR: node.csv not found\n")
            return False
        if not os.path.exists(self.link_file):
            self.errors.append(f"link.csv not found in {self.network_dir}")
            print(f"[ERROR] ERROR: link.csv not found\n")
            return False
        return True
    
    def _validate_nodes(self):
        """Validate node.csv"""
        try:
            node_df = pd.read_csv(self.node_file)
            node_count = len(node_df)
            
            required_cols = ['node_id', 'x_coord', 'y_coord']
            missing_cols = [col for col in required_cols if col not in node_df.columns]
            
            if missing_cols:
                self.errors.append(f"node.csv missing columns: {', '.join(missing_cols)}")
                print(f"[ERROR] Missing required columns: {', '.join(missing_cols)}")
            else:
                print(f"[OK] Total nodes: {node_count}")
                print(f"[OK] Required columns present: {', '.join(required_cols)}")
            
            # Check for zone_id
            if 'zone_id' in node_df.columns:
                zone_count = len(node_df[node_df['node_id'] == node_df['zone_id']])
                print(f"[OK] Centroid nodes (zone_id = node_id): {zone_count}")
                self.stats['zone_count'] = zone_count
            else:
                self.warnings.append("zone_id column not found in node.csv")
                print(f"[WARNING] zone_id column not found")
            
            self.stats['node_count'] = node_count
            
        except Exception as e:
            self.errors.append(f"Error reading node.csv: {str(e)}")
            print(f"[ERROR] Error reading node.csv: {str(e)}")
    
    def _validate_links(self):
        """Validate link.csv VDF parameters"""
        try:
            link_df = pd.read_csv(self.link_file)
            total_links = len(link_df)
            
            print(f"[OK] Total links: {total_links}")
            
            # Check link_type
            if 'link_type' not in link_df.columns:
                self.warnings.append("link_type column not found - assuming all links are type 1")
                link_df['link_type'] = 1
                print(f"[WARNING] link_type column not found, assuming type 1")
            
            # Filter out connectors (type 0)
            link_df_filtered = link_df[link_df['link_type'] != 0].copy()
            connector_count = total_links - len(link_df_filtered)
            
            if connector_count > 0:
                print(f"  Excluding {connector_count} connector links (type 0)")
            
            analysis_links = len(link_df_filtered)
            print(f"  Analyzing {analysis_links} non-connector links\n")
            self.stats['total_links'] = total_links
            self.stats['analysis_links'] = analysis_links
            
            # Check each VDF parameter
            self.stats['parameters'] = {}
            
            for param_name, param_info in self.VDF_PARAMS.items():
                print(f"Parameter: {param_name} ({param_info['unit']})")
                
                if param_name not in link_df_filtered.columns:
                    self.errors.append(f"Required parameter '{param_name}' not found")
                    print(f"  [ERROR] NOT FOUND\n")
                    
                    # Store missing parameter info in stats
                    self.stats['parameters'][param_name] = {
                        'status': 'missing',
                        'overall_avg': None,
                        'by_type': {},
                        'is_constant_across_types': False
                    }
                    continue
                
                param_values = link_df_filtered[param_name].dropna()
                
                if len(param_values) == 0:
                    self.errors.append(f"Parameter '{param_name}' has no valid values")
                    print(f"  [ERROR] No valid values\n")
                    
                    # Store empty parameter info in stats
                    self.stats['parameters'][param_name] = {
                        'status': 'no_valid_values',
                        'overall_avg': None,
                        'by_type': {},
                        'is_constant_across_types': False
                    }
                    continue
                
                # Check for negative values
                negative_count = (param_values < 0).sum()
                if negative_count > 0:
                    self.errors.append(f"Parameter '{param_name}' has {negative_count} negative values")
                    print(f"  [ERROR] {negative_count} negative values found")
                
                # Check ranges
                if 'max' in param_info and param_info['max'] is not None:
                    above_max = (param_values > param_info['max']).sum()
                    if above_max > 0:
                        self.warnings.append(f"{param_name}: {above_max} values above max {param_info['max']}")
                
                # Overall statistics
                overall_avg = float(param_values.mean())
                print(f"  Overall average: {overall_avg:.3f}")
                
                # Statistics by link type
                by_type = {}
                type_averages = []
                
                for link_type in sorted(link_df_filtered['link_type'].unique()):
                    if link_type == 0:
                        continue
                    
                    type_data = link_df_filtered[link_df_filtered['link_type'] == link_type]
                    type_values = type_data[param_name].dropna()
                    
                    if len(type_values) > 0:
                        type_avg = float(type_values.mean())
                        type_averages.append(type_avg)
                        by_type[int(link_type)] = {
                            'count': len(type_values),
                            'avg': type_avg
                        }
                
                # Check if all link types have the same constant value
                if type_averages and all(abs(avg - type_averages[0]) < 0.001 for avg in type_averages):
                    print(f"  → All non-connector link types use constant value: {type_averages[0]:.3f}")
                else:
                    print(f"  By Link Type:")
                    print(f"    {'Type':<4} {'Name':<20} {'Count':<8} {'Average':<12}")
                    for link_type, stats in sorted(by_type.items()):
                        type_name = self.LINK_TYPES.get(link_type, f"Type {link_type}")
                        print(f"    {link_type:<4} {type_name:<20} {stats['count']:<8} {stats['avg']:<12.3f}")
                
                self.stats['parameters'][param_name] = {
                    'status': 'ok',
                    'overall_avg': overall_avg,
                    'by_type': by_type,
                    'is_constant_across_types': len(type_averages) > 0 and all(abs(avg - type_averages[0]) < 0.001 for avg in type_averages)
                }
                print()
            
            # Print parameter check summary
            print("\nPARAMETER CHECK SUMMARY")
            print("-"*70)
            found_params = [p for p, info in self.stats['parameters'].items() if info.get('status') == 'ok']
            missing_params = [p for p, info in self.stats['parameters'].items() if info.get('status') == 'missing']
            no_value_params = [p for p, info in self.stats['parameters'].items() if info.get('status') == 'no_valid_values']
            
            if found_params:
                print(f"[OK] Found and validated: {', '.join(found_params)}")
            if missing_params:
                print(f"[ERROR] Missing columns: {', '.join(missing_params)}")
            if no_value_params:
                print(f"[ERROR] No valid values: {', '.join(no_value_params)}")
            print()
            
        except Exception as e:
            self.errors.append(f"Error reading link.csv: {str(e)}")
            print(f"[ERROR] Error reading link.csv: {str(e)}")
    
    def _save_and_print_summary(self):
        """Save results and print summary"""
        # Prepare results
        results = {
            'timestamp': datetime.now().isoformat(),
            'network_dir': self.network_dir,
            'statistics': self.stats,
            'errors': self.errors,
            'warnings': self.warnings,
            'summary': {
                'status': 'FAIL' if self.errors else ('WARNING' if self.warnings else 'PASS'),
                'error_count': len(self.errors),
                'warning_count': len(self.warnings)
            }
        }
        
        # Save to JSON
        output_file = os.path.join(self.network_dir, 'assignment_validation_summary.json')
        try:
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Results saved to: {output_file}\n")
        except Exception as e:
            print(f"Warning: Could not save results: {e}\n")
        
        # Print summary
        print("="*70)
        print("VALIDATION SUMMARY")
        print("="*70)
        print(f"Status: {results['summary']['status']}")
        print(f"Errors: {results['summary']['error_count']}")
        print(f"Warnings: {results['summary']['warning_count']}")
        print("-"*70)
        
        if self.errors:
            print("\nERRORS:")
            for i, error in enumerate(self.errors, 1):
                print(f"{i}. {error}")
        
        if self.warnings:
            print("\nWARNINGS:")
            for i, warning in enumerate(self.warnings, 1):
                print(f"{i}. {warning}")
        
        if not self.errors and not self.warnings:
            print("\n[OK] ALL CHECKS PASSED")
            print("  Network is ready for traffic assignment")
        elif not self.errors:
            print("\n[WARNING] PASSED WITH WARNINGS")
        else:
            print("\n[ERROR] VALIDATION FAILED")
            print("  Fix errors before running traffic assignment")
            
            # Add specific suggestions for missing parameters
            missing_params = [p for p, info in self.stats.get('parameters', {}).items() 
                            if info.get('status') == 'missing']
            if missing_params:
                print("\n  Suggestions:")
                print(f"  → Add these columns to link.csv: {', '.join(missing_params)}")
                print(f"  → Make sure column names match exactly (case-sensitive)")
        
        print("="*70)


def run_validation(network_dir='connected_network'):
    """
    Run validation without sys.exit (for interactive use)
    Returns True if validation passed, False otherwise
    """
    validator = AssignmentValidator(network_dir)
    return validator.validate()


def main():
    """Main entry point"""
    import sys
    
    network_dir = sys.argv[1] if len(sys.argv) > 1 else 'connected_network'
    
    validator = AssignmentValidator(network_dir)
    success = validator.validate()
    
    # Only exit with status code if running as script (not in interactive mode)
    if hasattr(sys, 'ps1') or 'IPython' in sys.modules:
        # Running in interactive mode (Jupyter/IPython) - just return
        return success
    else:
        # Running as script - exit with status code
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()