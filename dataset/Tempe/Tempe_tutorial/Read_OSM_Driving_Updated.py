# -*- coding: utf-8 -*-
"""
@author: hnzhu
"""
# Pls install osm2gmns 1.0.1 package
# Use this pip command: pip install osm2gmns==1.0.1
# Reference: https://pypi.org/project/osm2gmns/1.0.1/
import csv
import os
import osm2gmns as og

# Get current directory
current_dir = os.getcwd()
# Path to the 'data' folder
data_folder = os.path.join(current_dir, "data")

# Automatically find the first .osm or .pbf file in the data folder
input_file = None
file_type = None

for file in os.listdir(data_folder):
    if file.endswith(".osm"):
        input_file = os.path.join(data_folder, file)
        file_type = "OSM"
        break
    elif file.endswith(".pbf"):
        input_file = os.path.join(data_folder, file)
        file_type = "PBF"
        break

# Raise error if no .osm or .pbf file is found
if input_file is None:
    raise FileNotFoundError("No .osm or .pbf file found in the 'data' folder.")

print(f"Found {file_type} file: {os.path.basename(input_file)}")



def osm2gmns_network():

    #input_file = r"data/Tempe.osm" # Update this file name to match your osm
    # option 1: for urban networks
    net = og.getNetFromFile(input_file, link_types=('motorway','trunk','primary','secondary','tertiary'))
    #net = og.getNetFromFile(input_file, link_types=('motorway','trunk','primary'))
    #option 1+poi:
    #net = og.getNetFromFile(input_file, link_types=('motorway','trunk','primary','secondary','tertiary'),POI=True)   
    # option 2: for rural networks
    #net = og.getNetFromFile(input_file, link_types=('motorway','trunk','primary','secondary','residential','tertiary'))

    # Consolidate intersections and fill default values
    og.consolidateComplexIntersections(net, auto_identify=True)
    og.fillLinkAttributesWithDefaultValues(net, default_lanes=True, default_speed=True, default_capacity=True)
    og.generateNodeActivityInfo(net)

    # Output the processed network
    og.outputNetToCSV(net)
    
#main program
osm2gmns_network()
