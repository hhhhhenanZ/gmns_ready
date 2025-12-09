# Changelog

All notable changes to gmns-ready will be documented in this file.


## [0.1.0] - 2024-12-09

### Added
- **build_network()**: New `zone_search_radius` parameter for customizable zone-to-network connections
  - Default: 1000 meters (recommended for mixed urban/suburban areas)
  - Urban areas: Set to 500m for tighter connections
  - Suburban areas: Set to 1500m for wider search
  - Unlimited search: Set to `None` to always find nearest link regardless of distance
  - Improves network flexibility and accuracy for different urban contexts

- **enhance_connectors()**: Three new customizable parameters for fine-tuned connector enhancement
  - `search_radius` (default: 1000m): Maximum distance for finding candidate network links
  - `accessibility_threshold` (default: 0.10): Connectivity target as percentage of total zones (10%)
  - `min_connectors` (default: 6): Minimum total connectors to add per problematic zone
  - Distributed across link types: highways, arterials, collectors, local roads
  - Allows users to adapt connector generation to local network characteristics

- **Documentation**: New POI Accessibility Analysis tutorial
  - Interactive Google Colab tutorial for Scenario 2
  - Step-by-step guide for connecting external access points to networks
  - Examples of transit equity studies and facility accessibility analysis

### Changed
- **API Architecture**: Migrated from subprocess-based script execution to direct function imports
  - Users can now pass parameters programmatically instead of editing script files
  - Functions return dataframes for better integration with user workflows
  - Improved IDE autocomplete and type hinting support
  - Better error handling with meaningful return values
  - Maintains backward compatibility: calling functions without parameters uses defaults

- **Documentation**: Enhanced function docstrings with detailed parameter descriptions
  - Added parameter ranges and recommended values
  - Included usage examples for different scenarios (urban, suburban, mixed)
  - Cross-referenced related functions and workflow steps
  - Added comprehensive parameter guidance tables

### Fixed
- Cross-platform compatibility improvements for Windows/Mac/Linux
- Better parameter validation with clear error messages
- Improved progress reporting during long operations

### Technical Details
- `build_network()` now accepts zone_search_radius as first parameter
- `enhance_connectors()` now accepts search_radius, accessibility_threshold, min_connectors
- Both functions maintain full backward compatibility with v0.0.9
- Updated __init__.py to expose new parameters through clean API

### Migration Guide
If you're upgrading from v0.0.9:

**No changes required** - Default behavior is identical:
```python
# v0.0.9 code still works
import gmns_ready as gr
gr.build_network()
gr.enhance_connectors()
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## Links

- **PyPI**: https://pypi.org/project/gmns-ready/
- **GitHub**: https://github.com/hhhhhenanZ/gmns_ready
- **Issues**: https://github.com/hhhhhenanZ/gmns_ready/issues
