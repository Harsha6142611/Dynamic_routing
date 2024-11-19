import os
import sys
from sumolib import net
import traci
from sumolib.xml import create_document
import subprocess
import random

def find_route(net_file, start_edge, end_edge):
    # Initialize SUMO with TraCI
    if 'SUMO_HOME' in os.environ:
        tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
        sys.path.append(tools)
    else:
        sys.exit("Please declare environment variable 'SUMO_HOME'")
    
    # Start SUMO in simulation mode
    sumo_binary = "sumo"
    sumo_cmd = [sumo_binary, "-n", net_file, "--no-step-log", "--no-warnings"]
    traci.start(sumo_cmd)
    
    try:
        route = traci.simulation.findRoute(start_edge, end_edge, vType="DEFAULT_VEHTYPE")
        
        if route.edges:
            return route.edges
        return None
            
    finally:
        traci.close()

def save_route_to_file(edges, valid_edges, net_file, output_file="../data/route.rou.xml"):
    print(f"Creating routes with {len(valid_edges)} valid edges")
    routes = create_document("routes")
    
    # Add vType definitions
    routes.addChild("vType", attrs={
        "id": "car",
        "accel": "2.6",
        "decel": "4.5",
        "sigma": "0.5",
        "length": "5",
        "maxSpeed": "70",
        "color": "0,0,1"  # Blue color
    })
    
    routes.addChild("vType", attrs={
        "id": "highlighted_car",
        "accel": "2.6",
        "decel": "4.5",
        "sigma": "0.5",
        "length": "5",
        "maxSpeed": "70",
        "color": "1,0,0"  # Red color
    })
    
    # Store vehicles in a list to sort them later
    vehicles = []
    
    # Add highlighted route vehicle with a later departure time
    vehicles.append({
        "id": "route_highlight",
        "type": "highlighted_car",
        "depart": "2",  # Start at 2 seconds
        "edges": edges
    })
    
    # Add random vehicles with valid routes
    num_random_vehicles = 50  # Increased number of vehicles
    added_vehicles = 0
    max_attempts = 1000
    attempts = 0
    
    while added_vehicles < num_random_vehicles and attempts < max_attempts:
        start_edge = random.choice(valid_edges)
        end_edge = random.choice(valid_edges)
        
        # Find a valid route between the random edges
        random_route = find_route(net_file, start_edge, end_edge)
        
        if random_route:
            # Spread departure times from 0 to 200 seconds
            depart_time = random.uniform(0, 200)
            vehicles.append({
                "id": f"random_vehicle_{added_vehicles}",
                "type": "car",
                "depart": f"{depart_time:.1f}",
                "edges": random_route
            })
            print(f"Added random vehicle {added_vehicles}: {' '.join(random_route)}")
            added_vehicles += 1
        
        attempts += 1
    
    print(f"Successfully added {added_vehicles} random vehicles after {attempts} attempts")
    
    # Sort vehicles by departure time
    vehicles.sort(key=lambda x: float(x["depart"]))
    
    # Add sorted vehicles to the routes document
    for v in vehicles:
        vehicle = routes.addChild("vehicle", attrs={
            "id": v["id"],
            "type": v["type"],
            "depart": v["depart"]
        })
        vehicle.addChild("route", attrs={"edges": " ".join(v["edges"])})
    
    with open(output_file, "w") as f:
        f.write(routes.toXML())

def is_valid_vehicle_edge(network, edge_id):
    edge = network.getEdge(edge_id)
    if edge is None:
        return False
    
    # Check each lane's allowed vehicles
    for lane in edge.getLanes():
        # Get the allowed vehicle classes for this lane
        # Check if passenger vehicles are explicitly allowed
        # or if the lane allows all vehicles (empty allowed set)
        if lane.allows('passenger'):
            return True
    return False

def save_visualization_settings(edges, output_file="../data/settings.xml"):
    settings = create_document("viewsettings")
    
    # Add global settings
    settings.addChild("viewport", attrs={
        "x": "0",
        "y": "0",
        "zoom": "100"
    })
    
    # Add scheme for edges
    scheme = settings.addChild("scheme", attrs={"name": "real world"})
    
    # Add edges settings
    edges_scheme = scheme.addChild("edges", attrs={
        "laneWidth": "2",
        "showLinkDecals": "true",
        "showRails": "true",
        "hideConnectors": "false"
    })
    
    # Default edge appearance
    edges_scheme.addChild("colorScheme", attrs={
        "name": "selection",
        "value": "0.7,0.7,0.7"  # Default gray color
    })
    
    # Specifically color the selected edges
    selections = edges_scheme.addChild("selections", attrs={
        "friendlyPos": "true"
    })
    
    # Add each edge of the route to the selection with bright red color
    for edge in edges:
        selections.addChild("selection", attrs={
            "id": edge,
            "color": "255,0,0",  # Bright red
            "width": "4"  # Make the edges wider
        })
    
    with open(output_file, "w") as f:
        f.write(settings.toXML())

def find_nearest_edge(net, x, y):
    radius = 0.1  # 100 meters initial search radius
    max_radius = 1000  # maximum search radius in meters
    
    while radius < max_radius:
        edges = net.getNeighboringEdges(x, y, radius)
        if edges:
            # Sort by distance and return the closest edge
            edges.sort(key=lambda x: x[1])  # x[1] is the distance
            return edges[0][0].getID()  # x[0] is the edge object
        radius *= 2
    return None

def main():
    net_file = "../data/test.net.xml"
    network = net.readNet(net_file)
    
    # Get and display valid edges
    valid_edges = []
    print("\nAvailable edges and their coordinates:")
    print("ID\t\tStart(x,y)\t\tEnd(x,y)")
    print("-" * 50)
    for edge in network.getEdges():
        if is_valid_vehicle_edge(network, edge.getID()):
            valid_edges.append(edge.getID())
            # Get edge geometry
            start_pos = edge.getFromNode().getCoord()
            end_pos = edge.getToNode().getCoord()
            print(f"{edge.getID():<15} ({start_pos[0]:.1f},{start_pos[1]:.1f})\t\t({end_pos[0]:.1f},{end_pos[1]:.1f})")
    
    print(f"\nFound {len(valid_edges)} valid edges for routing")
    
    print("\nPlease enter coordinates (or edge IDs):")
    # Get start location
    start_input = input("Enter start X coordinate (or edge ID): ")
    try:
        # Try parsing as coordinates
        start_x = float(start_input)
        start_y = float(input("Enter start Y coordinate: "))
        start_edge = find_nearest_edge(network, start_x, start_y)
    except ValueError:
        # If parsing fails, treat input as edge ID
        start_edge = start_input if start_input in valid_edges else None
    
    if not start_edge:
        print("Error: Invalid start location")
        return
    print(f"Selected start edge: {start_edge}")
    
    # Get end location
    end_input = input("Enter destination X coordinate (or edge ID): ")
    try:
        # Try parsing as coordinates
        end_x = float(end_input)
        end_y = float(input("Enter destination Y coordinate: "))
        end_edge = find_nearest_edge(network, end_x, end_y)
    except ValueError:
        # If parsing fails, treat input as edge ID
        end_edge = end_input if end_input in valid_edges else None

    if not end_edge:
        print("Error: Invalid destination location")
        return
    print(f"Selected destination edge: {end_edge}")
    
    # Find and validate route
    route = find_route(net_file, start_edge, end_edge)
    
    if route:
        print(f"\nRoute found! Edges: {' -> '.join(route)}")
        save_route_to_file(route, valid_edges, net_file)
        save_visualization_settings(route)
        
        print("\nStarting simulation...")
        sumo_gui_cmd = [
            "sumo-gui",
            "-n", net_file,
            "-r", "../data/route.rou.xml",
            "--gui-settings-file", "../data/settings.xml",
            "--start",
            "--delay", "50",  # Reduced delay
            "--step-length", "0.1",
            "--begin", "0",  # Start at 0 seconds
            "--end", "3600",  # Run for 1 hour
            "--window-size", "800,600",
            "--window-pos", "50,50",
            "--no-warnings"
        ]
        subprocess.run(sumo_gui_cmd)
    else:
        print(f"\nNo route found between selected locations")

if __name__ == "__main__":
    main()