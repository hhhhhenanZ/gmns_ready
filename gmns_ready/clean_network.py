# -*- coding: utf-8 -*-
"""
@author: hnzhu
"""
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import os
from collections import Counter

# Create output folder
output_folder = 'osm_network_connectivity_check'
os.makedirs(output_folder, exist_ok=True)

print("="*70)
print("NETWORK CONNECTIVITY ANALYSIS")
print("="*70)

# Step 1: Read input files
print("\nStep 1: Reading input files...")
nodes_df = pd.read_csv('node.csv')
links_df = pd.read_csv('link.csv')

print(f"Original nodes: {len(nodes_df)}")
print(f"Original links: {len(links_df)}")
print(f"\nNode columns: {nodes_df.columns.tolist()}")
print(f"Link columns: {links_df.columns.tolist()}")

# Identify node_id column
node_id_col = None
for col in ['node_id', 'id', 'node', 'osm_node_id']:
    if col in nodes_df.columns:
        node_id_col = col
        break

if node_id_col is None:
    raise ValueError("Could not find node_id column in node_osm.csv")

# Identify from_node_id and to_node_id columns
from_node_col = None
to_node_col = None

for col in ['from_node_id', 'from_node', 'a_node', 'start_node', 'source']:
    if col in links_df.columns:
        from_node_col = col
        break

for col in ['to_node_id', 'to_node', 'b_node', 'end_node', 'target']:
    if col in links_df.columns:
        to_node_col = col
        break

if from_node_col is None or to_node_col is None:
    raise ValueError("Could not find from_node_id/to_node_id columns in link_osm.csv")

print(f"\nUsing columns:")
print(f"  Node ID: {node_id_col}")
print(f"  From Node: {from_node_col}")
print(f"  To Node: {to_node_col}")

# Step 2: Build network graph
print("\nStep 2: Building network graph...")
G = nx.Graph()

# Add all nodes
for node_id in nodes_df[node_id_col]:
    G.add_node(node_id)

# Add all edges (links)
for _, row in links_df.iterrows():
    from_node = row[from_node_col]
    to_node = row[to_node_col]
    G.add_edge(from_node, to_node)

print(f"Graph created with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")

# Step 3: Find connected components
print("\nStep 3: Analyzing connected components...")
connected_components = list(nx.connected_components(G))
num_components = len(connected_components)

print(f"Number of connected components: {num_components}")

# Sort components by size (largest first)
components_sorted = sorted(connected_components, key=len, reverse=True)

print("\nComponent sizes:")
for i, comp in enumerate(components_sorted[:10], 1):  # Show top 10
    print(f"  Component {i}: {len(comp)} nodes ({len(comp)/len(nodes_df)*100:.2f}%)")

if num_components > 10:
    print(f"  ... and {num_components - 10} more smaller components")

# Step 4: Identify main component and isolated parts
main_component = components_sorted[0]
isolated_nodes = set()
for comp in components_sorted[1:]:
    isolated_nodes.update(comp)

print(f"\nMain component: {len(main_component)} nodes ({len(main_component)/len(nodes_df)*100:.2f}%)")
print(f"Isolated parts: {len(isolated_nodes)} nodes ({len(isolated_nodes)/len(nodes_df)*100:.2f}%)")

# Step 5: Visualize the network
print("\nStep 4: Creating visualization...")

# Check if nodes have coordinates
coord_cols = nodes_df.columns.tolist()
x_col = None
y_col = None

for col in ['x_coord', 'x', 'longitude', 'lon']:
    if col in coord_cols:
        x_col = col
        break

for col in ['y_coord', 'y', 'latitude', 'lat']:
    if col in coord_cols:
        y_col = col
        break

if x_col and y_col:
    print(f"Using coordinates: X={x_col}, Y={y_col}")
    
    # Create position dictionary
    pos = {}
    for _, row in nodes_df.iterrows():
        node_id = row[node_id_col]
        if node_id in G.nodes():
            pos[node_id] = (row[x_col], row[y_col])
    
    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8))
    
    # Plot 1: Original network with components highlighted
    ax1.set_title('Original Network - All Components', fontsize=14, fontweight='bold')
    
    # Draw main component in blue
    main_nodes = [n for n in main_component if n in pos]
    nx.draw_networkx_nodes(G, pos, nodelist=main_nodes, 
                          node_color='blue', node_size=10, 
                          alpha=0.6, ax=ax1, label='Main Component')
    
    # Draw isolated components in red
    isolated_nodes_in_pos = [n for n in isolated_nodes if n in pos]
    nx.draw_networkx_nodes(G, pos, nodelist=isolated_nodes_in_pos, 
                          node_color='red', node_size=15, 
                          alpha=0.8, ax=ax1, label='Isolated Parts')
    
    # Draw edges
    nx.draw_networkx_edges(G, pos, alpha=0.2, width=0.5, ax=ax1)
    
    ax1.legend(loc='upper right', fontsize=10)
    ax1.set_xlabel('Longitude')
    ax1.set_ylabel('Latitude')
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Filtered network (main component only)
    ax2.set_title('Filtered Network - Main Component Only', fontsize=14, fontweight='bold')
    
    # Create subgraph of main component
    G_main = G.subgraph(main_component)
    
    nx.draw_networkx_nodes(G_main, pos, nodelist=main_nodes,
                          node_color='green', node_size=10, 
                          alpha=0.6, ax=ax2, label='Kept Nodes')
    nx.draw_networkx_edges(G_main, pos, alpha=0.2, width=0.5, ax=ax2)
    
    ax2.legend(loc='upper right', fontsize=10)
    ax2.set_xlabel('Longitude')
    ax2.set_ylabel('Latitude')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save figure
    fig_path = os.path.join(output_folder, 'network_connectivity_analysis.png')
    plt.savefig(fig_path, dpi=300, bbox_inches='tight')
    print(f"Saved visualization: {fig_path}")
    
    # Also create a detailed view of isolated components
    if len(isolated_nodes) > 0:
        fig2, ax = plt.subplots(figsize=(12, 10))
        ax.set_title('Isolated Components (To Be Removed)', fontsize=14, fontweight='bold')
        
        # Draw all nodes in light gray
        nx.draw_networkx_nodes(G, pos, nodelist=main_nodes,
                              node_color='lightgray', node_size=5, 
                              alpha=0.3, ax=ax, label='Main Component')
        
        # Color each isolated component differently
        colors = plt.cm.Set3(range(len(components_sorted[1:])))
        for i, comp in enumerate(components_sorted[1:]):
            comp_nodes = [n for n in comp if n in pos]
            if len(comp_nodes) > 0:
                nx.draw_networkx_nodes(G, pos, nodelist=comp_nodes,
                                      node_color=[colors[i]], node_size=20,
                                      alpha=0.8, ax=ax, 
                                      label=f'Isolated {i+1} ({len(comp)} nodes)')
        
        # Draw all edges
        nx.draw_networkx_edges(G, pos, alpha=0.1, width=0.3, ax=ax)
        
        ax.legend(loc='upper right', fontsize=8, ncol=2)
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        ax.grid(True, alpha=0.3)
        
        fig2_path = os.path.join(output_folder, 'isolated_components_detail.png')
        plt.savefig(fig2_path, dpi=300, bbox_inches='tight')
        print(f"Saved detailed view: {fig2_path}")
        
    plt.close('all')
else:
    print("Warning: Could not find coordinate columns for visualization")
    print("Skipping visualization step")

# Step 6: Filter nodes to keep only main component
print("\nStep 5: Filtering nodes...")
nodes_filtered = nodes_df[nodes_df[node_id_col].isin(main_component)].copy()
print(f"Nodes after filtering: {len(nodes_filtered)}")

# Step 7: Filter links to keep only those connecting main component nodes
print("\nStep 6: Filtering links...")
links_filtered = links_df[
    (links_df[from_node_col].isin(main_component)) & 
    (links_df[to_node_col].isin(main_component))
].copy()
print(f"Links after filtering: {len(links_filtered)}")

# Step 8: Create mapping for renumbering nodes
print("\nStep 7: Renumbering node IDs...")
# Sort nodes by original ID to maintain some order
nodes_filtered = nodes_filtered.sort_values(node_id_col).reset_index(drop=True)

old_node_ids = nodes_filtered[node_id_col].values
node_id_mapping = {old_id: new_id for new_id, old_id in enumerate(old_node_ids, start=1)}

# Apply new node IDs
nodes_filtered['old_node_id'] = nodes_filtered[node_id_col]
nodes_filtered[node_id_col] = range(1, len(nodes_filtered) + 1)

# Step 9: Update link node references
print("\nStep 8: Updating link node references...")
links_filtered[from_node_col] = links_filtered[from_node_col].map(node_id_mapping)
links_filtered[to_node_col] = links_filtered[to_node_col].map(node_id_mapping)

# Step 10: Sort and renumber links
print("\nStep 9: Sorting and renumbering link IDs...")
# Sort by from_node_id first, then to_node_id
links_filtered = links_filtered.sort_values([from_node_col, to_node_col]).reset_index(drop=True)

# Identify link_id column
link_id_col = None
for col in ['link_id', 'id', 'edge_id', 'osm_way_id']:
    if col in links_filtered.columns:
        link_id_col = col
        break

if link_id_col:
    links_filtered['old_link_id'] = links_filtered[link_id_col]
    links_filtered[link_id_col] = range(1, len(links_filtered) + 1)
else:
    # Create new link_id column if it doesn't exist
    links_filtered.insert(0, 'link_id', range(1, len(links_filtered) + 1))
    link_id_col = 'link_id'

# Step 11: Save output files
print("\nStep 10: Saving output files...")

# Remove temporary columns
nodes_output = nodes_filtered.drop(columns=['old_node_id'], errors='ignore')
links_output = links_filtered.drop(columns=['old_link_id'], errors='ignore')

# Save to output folder
node_output_path = os.path.join(output_folder, 'node.csv')
link_output_path = os.path.join(output_folder, 'link.csv')

nodes_output.to_csv(node_output_path, index=False)
links_output.to_csv(link_output_path, index=False)

print(f"Saved: {node_output_path}")
print(f"Saved: {link_output_path}")

# Summary
print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print(f"Original network:")
print(f"  Nodes: {len(nodes_df)}")
print(f"  Links: {len(links_df)}")
print(f"  Connected components: {num_components}")
print(f"\nFiltered network (main component only):")
print(f"  Nodes: {len(nodes_output)}")
print(f"  Links: {len(links_output)}")
print(f"  Connected components: 1")
print(f"\nRemoved:")
print(f"  Nodes: {len(nodes_df) - len(nodes_output)} ({(len(nodes_df) - len(nodes_output))/len(nodes_df)*100:.2f}%)")
print(f"  Links: {len(links_df) - len(links_output)} ({(len(links_df) - len(links_output))/len(links_df)*100:.2f}%)")
print(f"\nNode IDs renumbered: 1 to {len(nodes_output)}")
print(f"Link IDs renumbered: 1 to {len(links_output)}")
print(f"Links sorted by: {from_node_col}, then {to_node_col}")
print(f"\nOutput files saved in '{output_folder}/' folder:")
print(f"  - node.csv")
print(f"  - link.csv")
if x_col and y_col:
    print(f"  - network_connectivity_analysis.png")
    if len(isolated_nodes) > 0:
        print(f"  - isolated_components_detail.png")
print("="*70)