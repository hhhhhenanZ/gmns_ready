# GMNS Ready

**Professional toolkit for preparing and validating GMNS transportation networks with complete zone connectivity.**

[![Python Version](https://img.shields.io/badge/python-3.7%2B-blue)](https://www.python.org/downloads/)
[![Tutorial](https://img.shields.io/badge/tutorial-Google%20Colab-yellow)](https://colab.research.google.com/drive/1sSdlliVKIBt7-Uke2DnbJ3oZgDF8P289?usp=drive_link)


## Overview

`gmns-ready` is a comprehensive Python package that prepares, validates, and enhances GMNS (General Modeling Network Specification) transportation networks. It automates the critical but often manual process of connecting traffic analysis zones to road networks, ensuring your data is ready for traffic assignment and travel demand modeling.

**Key Capabilities:**
- ✅ Validate spatial alignment before processing
- ✅ Extract and process zone data from shapefiles with automatic detection
- ✅ Generate zone-to-network connectors following Forward Star structure
- ✅ Validate network integrity and accessibility using DTALite
- ✅ Enhance connectivity for zones with limited network access
- ✅ Prepare networks for traffic assignment with VDF parameter validation
- ✅ Cross-platform support (Windows, Linux, macOS)

## Installation

```bash
pip install gmns-ready
```

This will automatically install all required dependencies including [DTALite](https://pypi.org/project/DTALite/) for accessibility validation.

**New to gmns-ready?** Check out our [interactive tutorial on Google Colab](https://colab.research.google.com/drive/1sSdlliVKIBt7-Uke2DnbJ3oZgDF8P289?usp=drive_link) - no installation required!

Or install from source:
```bash
git clone https://github.com/hhhhhenanZ/gmns_ready.git
cd gmns_ready
pip install -e .
```

## Quick Start

```python
import gmns_ready as gr

# Step 1: Validate inputs are spatially aligned
gr.validate_basemap()

# Step 2: Extract zones from shapefile (auto-detects .shp in data/ folder)
gr.extract_zones()

# Step 3: Build zone-connected network
gr.build_network()

# Step 4: Validate everything
gr.validate_network()
gr.validate_accessibility()  # Uses DTALite for traffic assignment
gr.validate_assignment()
```

---

## Tutorial

**Interactive Tutorial:** Try our hands-on [Google Colab tutorial](https://colab.research.google.com/drive/1sSdlliVKIBt7-Uke2DnbJ3oZgDF8P289?usp=drive_link) to learn how to use gmns-ready with real examples.

---

## Core Functions

### 1. Input Validation

**`validate_basemap()`** - Verify spatial alignment of input files

Checks that node.csv, link.csv, and zone shapefiles are in the same geographic area before processing. This prevents common errors from misaligned data sources and saves troubleshooting time.

```python
import gmns_ready as gr

gr.validate_basemap()  # Checks files in current directory
```

**When to use:** FIRST step before any processing

**Inputs:**
- `node.csv` and `link.csv` in current directory
- Any `.shp` file in `data/` folder

**Output:** `data/base_map_validation_report.json`

**What it checks:**
- Coordinate system consistency
- Geographic overlap of all datasets
- Bounding box alignment

---

### 2. Zone Data Processing

**`extract_zones()`** - Extract zone centroids and boundaries from shapefile

Automatically detects and processes zone shapefiles (census tracts, TAZs, etc.) from the `data/` folder. Calculates centroids, preserves boundaries, and generates GMNS-compliant zone.csv with automatic coordinate projection to EPSG:4326.

```python
import gmns_ready as gr

gr.extract_zones()  # Auto-detects .shp file in data/ folder
```

**Inputs:**
- Any `.shp` file in `data/` folder (auto-detected)
- Supports multiple shapefile types: census tracts, TAZ, custom zones

**Outputs:**
- `zone.csv` with zone_id, x_coord, y_coord, boundary_geometry (WKT)

**Features:**
- Auto-detects zone ID column (TRACTCE, GEOID, TAZ, etc.)
- Reprojects to EPSG:4326 automatically
- Preserves both centroid points and boundary polygons

---

**`extract_zones_pop()`** - Add population data to zones (US only)

Fetches and adds demographic data from ACS 2022 API for US zones. Outputs the same zone.csv with an additional population column.

```python
import gmns_ready as gr

gr.extract_zones_pop()  # Uses .shp from data/, adds population column
```

**Inputs:**
- Any `.shp` file in `data/` folder (auto-detected)

**Outputs:**
- `zone.csv` with all zone data + population column

**Note:** Only works for US locations. Population data does not affect network connectivity.

---

### 3. Network Building

**`build_network()`** - Generate zone-connected network with connectors

The core function that creates a complete zone-connected network following [Forward Star Network Structure](https://github.com/asu-trans-ai-lab/TAPLite/wiki/Forward-Star-Network-Structure:-Centroid-Nodes-and-Connectors). Connects each zone to the nearest road network nodes and creates activity nodes for demand generation.

```python
import gmns_ready as gr

gr.build_network()  # Uses zone.csv, node.csv, link.csv from current directory
```

**Prerequisites:**
- `zone.csv` from `extract_zones()`
- `node.csv` and `link.csv` from [osm2gmns](https://github.com/asu-trans-ai-lab/osm2gmns)

**Outputs:** `connected_network/` folder containing:
- `node.csv` - Network nodes + activity nodes + zone centroids
- `link.csv` - Road links + connector links
- `activity_node.csv` - Activity nodes (trip generation points)
- `connector_links.csv` - Connector links only

**What it does:**
- Connects each zone centroid to nearest network nodes
- Creates activity nodes from OSM POIs (residential, commercial, educational, transit locations)
- Ensures bidirectional connectivity between zones and network
- Maintains GMNS format compliance

**Key concept:** Activity nodes are OSM-derived points of interest that represent where trips begin or end in GMNS-based demand modeling.

---

### 4. Network Validation

**`validate_network()`** - Check network structure and topology

Validates network topology, node-link consistency, connectivity, and GMNS format compliance for the zone-connected network.

```python
import gmns_ready as gr

gr.validate_network()  # Checks connected_network/ folder
```

**Output:** `connected_network/network_validation_report.json`

**What it checks:**
- Node-link topology consistency
- Network connectivity (all zones reachable)
- GMNS format compliance
- Data integrity

---

**`validate_accessibility()`** - Analyze zone-to-zone connectivity using DTALite

Runs traffic assignment using [DTALite](https://pypi.org/project/DTALite/) to compute zone-to-zone accessibility matrix and identify connectivity issues. This validation uses the DTALite Python package for cross-platform support (Windows, Linux, macOS).

```python
import gmns_ready as gr

gr.validate_accessibility()  # Checks connected_network/ folder
```

**Requirements:**
- DTALite package (auto-installed with gmns-ready)
- `settings.csv` in GMNS_Tools folder or network directory
- `connected_network/node.csv` and `link.csv`

**Outputs:**
- `connected_network/zone_accessibility.csv` - Zone-to-zone connectivity metrics
- `connected_network/link_performance.csv` - Traffic assignment results
- `connected_network/accessibility_validation_report.json` - Validation summary

**What it computes:**
- Zone-to-zone reachability matrix
- Origin/destination connectivity for each zone
- Identifies zones with poor accessibility (<10% of total zones)

**Check results:** Review the report to identify zones that may need additional connectors.

**DTALite:** [DTALite](https://pypi.org/project/DTALite/) is a fast, open-source traffic assignment engine that performs dynamic traffic assignment to compute realistic travel patterns and accessibility metrics.

---

**`validate_assignment()`** - Verify traffic assignment readiness

Validates VDF (Volume-Delay Function) parameters and link attributes required for traffic assignment by link type.

```python
import gmns_ready as gr

gr.validate_assignment()  # Checks connected_network/ folder
```

**Output:** `connected_network/assignment_validation_summary.json`

**What it checks:**
- VDF parameters: `vdf_alpha`, `vdf_beta`, `vdf_plf`, `vdf_fftt`
- Link capacity by link_type
- Parameter value ranges and consistency
- Excludes connectors (link_type=0) from validation

---

### 5. Connectivity Enhancement

**`enhance_connectors()`** - Add connectors for poorly connected zones

Adds 10 additional connectors per zone to improve accessibility for zones with poor network connectivity (<10% of total zones). Distributes connectors across road hierarchy: 3 to highways, 3 to arterials, 2 to collectors, 2 to local roads.

```python
import gmns_ready as gr

gr.enhance_connectors()  # Enhances connected_network/ folder
```

**When to use:**
- After running `validate_accessibility()`
- When zones show low connectivity scores (<10% of total zones)
- To improve network coverage for isolated zones

**Outputs:**
- `connected_network/link_updated.csv` - Enhanced link file with additional connectors
- `connected_network/connector_editor_report.txt` - Detailed report of added connectors

**Workflow:**
1. Run `enhance_connectors()`
2. Review `link_updated.csv` and report
3. Replace `connected_network/link.csv` with `link_updated.csv`
4. Re-run `validate_accessibility()` to verify improvements
5. Repeat if needed until accessibility requirements are met

---

## Network Preparation

### `clean_network()` - Remove disconnected components from OSM networks

OSM networks extracted via osm2gmns may contain disconnected islands or isolated segments due to data quality issues. This function identifies the main connected component and removes isolated parts, ensuring your network is fully traversable.

```python
import gmns_ready as gr

gr.clean_network()  # Cleans node.csv and link.csv from osm2gmns
```

**When to use:**
- **BEFORE** building zone-connected network
- After extracting network from osm2gmns
- When you suspect OSM data quality issues
- To ensure complete network traversability

**Inputs:**
- `node.csv` and `link.csv` (from osm2gmns in current directory)

**Outputs:** `osm_network_connectivity_check/` folder containing:
- Cleaned `node.csv` and `link.csv` (main connected component only)
- `network_connectivity_analysis.png` - Before/after visualization
- `isolated_components_detail.png` - Detailed view of removed components

**After running:**
Replace your original `node.csv` and `link.csv` with the cleaned versions from `osm_network_connectivity_check/` folder, then proceed to `build_network()`.

---

## Complete Workflow Example

```python
import gmns_ready as gr
import osm2gmns as og

# ============================================================================
# STEP 0: Generate base network from OSM (using osm2gmns)
# ============================================================================
# net = og.getNetFromFile('map.osm')
# og.outputNetToCSV(net)  # Creates node.csv and link.csv

# ============================================================================
# STEP 0.5: Clean OSM network (recommended)
# ============================================================================
gr.clean_network()
# Copy cleaned files from osm_network_connectivity_check/ to project root

# ============================================================================
# STEP 1: Validate spatial alignment
# ============================================================================
gr.validate_basemap()
# Check: data/base_map_validation_report.json

# ============================================================================
# STEP 2: Extract zones
# ============================================================================
gr.extract_zones()
# Output: zone.csv

# Optional: Add population data (US only)
# gr.extract_zones_pop()
# Output: zone.csv with population column

# ============================================================================
# STEP 3: Build zone-connected network
# ============================================================================
gr.build_network()
# Output: connected_network/ folder with all network files

# ============================================================================
# STEP 4: Validate network
# ============================================================================
gr.validate_network()
# Check: connected_network/network_validation_report.json

gr.validate_accessibility()  # Uses DTALite for traffic assignment
# Check: connected_network/accessibility_validation_report.json

gr.validate_assignment()
# Check: connected_network/assignment_validation_summary.json

# ============================================================================
# STEP 5: Enhance connectivity if needed
# ============================================================================
# If accessibility report shows poorly connected zones:
gr.enhance_connectors()
# Output: connected_network/link_updated.csv

# Replace link.csv with link_updated.csv
# import shutil
# shutil.copy('connected_network/link_updated.csv', 'connected_network/link.csv')

# Re-validate
gr.validate_accessibility()

# Repeat enhancement if needed until all zones meet requirements
```

---

## Project Structure

```
your_project/
├── data/
│   ├── zones.shp                    # Input: Zone shapefile (any name)
│   └── base_map_validation_report.json
├── GMNS_Tools/                      
│   └── settings.csv                 # DTALite configuration
├── node.csv                         # From osm2gmns
├── link.csv                         # From osm2gmns
├── zone.csv                         # Generated by extract_zones()
├── osm_network_connectivity_check/  # Optional: cleaned network
│   ├── node.csv
│   ├── link.csv
│   ├── network_connectivity_analysis.png
│   └── isolated_components_detail.png
└── connected_network/               # Final output
    ├── node.csv
    ├── link.csv
    ├── settings.csv                 # Copied from GMNS_Tools
    ├── activity_node.csv
    ├── connector_links.csv
    ├── zone_accessibility.csv       # From DTALite
    ├── link_performance.csv         # From DTALite
    ├── network_validation_report.json
    ├── accessibility_validation_report.json
    ├── assignment_validation_summary.json
    ├── link_updated.csv             # If enhanced
    └── connector_editor_report.txt  # If enhanced
```

---

## Function Reference

### Import Style

```python
# Recommended: Import once, use all functions
import gmns_ready as gr

# Then call any function:
gr.validate_basemap()
gr.extract_zones()
gr.build_network()
gr.validate_network()
gr.validate_accessibility()
gr.validate_assignment()
gr.enhance_connectors()
gr.extract_zones_pop()
gr.clean_network()
```

### Function Summary

| Function | Purpose | When to Use |
|----------|---------|-------------|
| `validate_basemap()` | Check spatial alignment | **FIRST** - before any processing |
| `extract_zones()` | Extract zones from shapefile | After basemap validation |
| `extract_zones_pop()` | Add population to zones | Optional, US only |
| `build_network()` | Create zone-connected network | After zone extraction |
| `validate_network()` | Check network structure | After network building |
| `validate_accessibility()` | Analyze zone connectivity with DTALite | After network building |
| `validate_assignment()` | Check assignment readiness | After network building |
| `enhance_connectors()` | Add more connectors | When accessibility is poor |
| `clean_network()` | Remove isolated components | Before network building (optional) |

---

## Integration with osm2gmns

This package is designed to work seamlessly with [osm2gmns](https://github.com/asu-trans-ai-lab/osm2gmns) for base network generation.

---

## Requirements

```
python >= 3.7
pandas >= 1.3.0
geopandas >= 0.10.0
shapely >= 1.8.0
matplotlib >= 3.3.0
networkx >= 2.6.0
DTALite >= 0.8.1
```

All dependencies are automatically installed with `pip install gmns-ready`.

---

## GMNS Compliance

This package follows the [General Modeling Network Specification (GMNS)](https://github.com/zephyr-data-specs/GMNS) standard, ensuring compatibility with:
- Traffic assignment tools (e.g., [DTALite](https://pypi.org/project/DTALite/))
- Travel demand models
- Network visualization tools
- Other GMNS-compliant software

---

## Citation

If you use this package in your research, please cite:

```bibtex
@software{gmns_ready,
  author = {Zhu, Henan and Zhou, Xuesong and Zheng, Han},
  title  = {GMNS Ready: Professional Toolkit for GMNS Transportation Networks},
  year   = {2025},
  url    = {https://github.com/hhhhhenanZ/gmns_ready}
}
```

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Authors

**Henan Zhu**, **Xuesong Zhou**, **Han Zheng**  
Arizona State University

**Contact:**
- Issues: [GitHub Issues](https://github.com/hhhhhenanZ/gmns_ready/issues)
- Email: henanzhu@asu.edu, xzhou74@asu.edu

## Acknowledgments

- Zephyr Foundation for GMNS standards
- [ASU Transportation + AI Lab](https://github.com/asu-trans-ai-lab) for developing [osm2gmns](https://github.com/asu-trans-ai-lab/osm2gmns) and [DTALite](https://pypi.org/project/DTALite/)
