#!/usr/bin/env python3
"""
MIT License

Copyright (c) 2023 Chris Sinclair

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import csv
import argparse
import json
import sys
from math import cos, asin, radians, degrees, atan2, pi

bucket_distance = 0.08
walking_distance = 5 #km

def hav(theta):
    theta = radians(theta)
    return (1-cos(theta))/2

def hdist(lat1, lon1, lat2, lon2):

    earth_radius = 6371 #km
    dy = lat1 - lat2
    dx = lon1 - lon2
    
    h = hav(dy) + cos(radians(lat1)) * cos(radians(lat2)) * hav(dx)
    return 2*earth_radius*asin(h**0.5)

def hangle(lat1, lon1, lat2, lon2):
    dy = lat1 - lat2
    dx = lon1 - lon2

    angle = atan2(dy, cos(pi/180*lat1)*dx)
    return degrees(angle)

def read_gb_ni_stops(stop_file,has_status,global_id):

    stops = dict()
    stop_reader = csv.DictReader(stop_file, delimiter=",", quotechar="\"")

    for stop in stop_reader:
        if has_status and (stop["Latitude"] == "" or stop["Status"] == "inactive"):
            continue
    
        lat = float(stop["Latitude"])
        lon = float(stop["Longitude"])
        lat = round(lat / bucket_distance)
        lon = round(lon / bucket_distance)
        if lat not in stops:
            stops[lat] = dict()
        if lon not in stops[lat]:
            stops[lat][lon] = []

        stops[lat][lon].append({"id":stop[global_id], "name":stop["CommonName"], "lat":float(stop["Latitude"]), "lon":float(stop["Longitude"])})

    return stops

def read_gb_stops(stop_file):
    return read_gb_ni_stops(stop_file, True, "ATCOCode")

def read_ni_stops(stop_file):
    return read_gb_ni_stops(stop_file, False, "AtcoCode")

def read_ie_stops(stop_file):

    stop_reader = json.load(stop_file)
    stops = dict()

    for stop in stop_reader["features"]:
        if "isActive" in stop["properties"] and not stop["properties"]["isActive"]:
            continue

        lat = round(stop["geometry"]["coordinates"][1] / bucket_distance)
        lon = round(stop["geometry"]["coordinates"][0] / bucket_distance)

        if lat not in stops:
            stops[lat] = dict()
        if lon not in stops[lat]:
            stops[lat][lon] = []
        stops[lat][lon].append({"id":stop["properties"]["AtcoCode"], "name":stop["properties"]["CommonName"], "lat":float(stop["geometry"]["coordinates"][1]), "lon":float(stop["geometry"]["coordinates"][0])})

    return stops

stops_parsers = {'gb':read_gb_stops, 'ni':read_ni_stops, 'ie':read_ie_stops}

def print_csv_results(stations, args):

    print("SummitCode, SummitLatitude, SummitLongitude, StationCode, StationName, StationLatitude, StationLongitude")
    stations = sorted(stations.items(), key=lambda x:x[1]["origin_dist"])
    for summit, data in stations:
        stops = sorted(data["stops"], key=lambda x:x[0])
        for stop in stops:
            print(f"{summit}, {data['lat']}, {data['lon']}, {stop[1][0]}, {stop[1][1]}, {stop[1][2]}, {stop[1][3]}")

def print_json_results(stations, args):
    results = []
 
    for summit in stations:
        tmp = {"id": summit, "name": stations[summit]["name"], "coordinates":[stations[summit]["lat"], stations[summit]["lon"]], "stops":[]}

        angles = {}
        for stop in stations[summit]["stops"]:
            dist = stop[0]
            stop = stop[1]

            angle = hangle(stations[summit]["lat"], stations[summit]["lon"], stop["lat"], stop["lon"])/10
            angle = round(angle)

            if angle not in angles:
                angles[angle] = []

            angles[angle].append((dist, {"name": stop["name"], "coordinates":[stop["lat"], stop["lon"]]}))

        for k, v in angles.items():
            v = sorted(v, key=lambda x:x[0])
            tmp["stops"].append(v[0][1])
        results.append(tmp)

    print(json.dumps({"origin":[args.user_latitude, args.user_longitude], "features":results}))
    
results_printers = {'csv':print_csv_results, 'json':print_json_results}

def main(args):

    stops = stops_parsers[args.stop_file_type](args.stop_file)

    args.summit_file.readline()
    summit_reader = csv.DictReader(args.summit_file, delimiter=",", quotechar="\"")

    stations = dict()

    for summit in summit_reader:

        lat,lon = float(summit["Latitude"]), float(summit["Longitude"])

        origin_dist = hdist(lat, lon, args.user_latitude, args.user_longitude)

        if args.r != None and origin_dist > args.r:
            continue

        b_lat, b_lon = round(lat/bucket_distance), round(lon/bucket_distance)

        for i in range(b_lat-1, b_lat+2):
            for j in range(b_lon-1, b_lon+2):
                if i in stops and j in stops[i]:
                    for stop in stops[i][j]:

                        dist = hdist(lat, lon, stop["lat"], stop["lon"])

                        if dist <= walking_distance:
                            if summit["SummitCode"] not in stations:
                                stations[summit["SummitCode"]] = {"name": summit["SummitName"], "lat":lat, "lon":lon, "origin_dist":origin_dist, "stops":[]}
                            stations[summit["SummitCode"]]["stops"].append((dist, stop))
    results_printers[args.f](stations, args)

def get_arguments():
    parser = argparse.ArgumentParser(
                    prog = "SOTAfilter",
                    description = "Return a list of SOTA summits near public transport sites ordered by distance to the user",
                    epilog = "Text at the bottom of help")

    parser.add_argument("stop_file_type", choices=["gb","ni","ie"], help="gb for Great Britain. ni for Northern Ireland. ie for Republic of Ireland")
    parser.add_argument("stop_file", type=argparse.FileType("r", encoding="latin-1"))
    parser.add_argument("summit_file", type=argparse.FileType("r", encoding="latin-1"))
    parser.add_argument("-r", type=float, default=None, help="Results range in distance from user lat/long in km")
    parser.add_argument("user_latitude", type=float)
    parser.add_argument("user_longitude", type=float)
    parser.add_argument("-f", choices=["json", "csv"], default="csv", help="Output format. Either csv or geoJSON")

    return parser.parse_args()


if __name__ == "__main__":
    args = get_arguments()
    main(args)

