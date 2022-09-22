#!/usr/bin/python3

"""
MODULE DESCRIPTION
Collection of tools for running caculations on Google Earth .kml files
output by uBlox UConnect software. Parsing handled by pyKML library,
based on lxml library.
Note that KML cordinates format is decimal degrees:
longitude, latitude, altitude in that order
with negative values for west, south and below sea level
the functions in this file all follow the same convention

MODULE FEATURES
read_ublox, parses a klm file output by ublox uconnect software
position_diff, caculates distance in meters between two points
line_straightness, compares cordinates list to the ideal straight line
"""

import sys
from pykml import parser
import pandas
import geopy.distance
import math
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pprint

def read_ublox(file):
    """
    FUNCTION DEFINITION
    parses a klm file exported by ublox uconnect software

    INPUTS
    file, string, path to .kml file

    OUTPUTS
    cordf, dataframe, latitude & longitude in decimal degrees & altitude in meters
    """
    with open(file) as kmlfile:
        tree = parser.parse(kmlfile)
        root = tree.getroot()

        #find all <cordinates> xml tags and join together
        cordinates = ""
        for tag in root.findall(".//{*}coordinates"):
            cordinates = cordinates.join(str(tag))

        #split cordinates into latitude, longitude and altitude lists of floats
        cordinates = cordinates.split('\n')
        lat = []
        long = []
        alt = []
        for line in cordinates:
            cordinates = line.strip().split(',')
            if len(cordinates) == 3:
                long.append(float(cordinates[0]))
                lat.append(float(cordinates[1]))
                alt.append(float(cordinates[2]))

        #remove the first 20 seconds
        lat = lat[20:]
        long = long[20:]
        alt = alt[20:]

        #create pandas dataframe
        names = ['Longitude', 'Latitude', 'Altitude']
        cordf = pandas.DataFrame(list(zip(long,lat,alt)), columns=names)

        return cordf

def position_diff(testcord, targetcord):
    """
    FUNCTION DESCRIPTION
    compares test and target points and caculates distance in meters between them

    INPUTS
    testcord, float tuple, longitude, latitude of test point in that order in decimal degrees
    targetcord, float tuple, longitude, latitude of target point in that order in decimal degrees

    OUTPUTS
    delta, string, distance in meters from given point
    """
    return geopy.distance.distance((testcord[1], testcord[0]), (targetcord[1], targetcord[0])).m

def line_straightness(cordf):
    """
    FUNCTION DESCRIPTION
    compares cordinates describing a line to the ideal straight line
    ideal straight line defined by the first and last point of the cordiantes
    reports the root-mean-squared-error between the two lines in meters
    plots a graph showing both lines

    INPUTS
    cordf, dataframe, including columns named 'Latitude' and 'Longitude'

    OUTPUTS
    mae, float, root-mean-squared-error in meters
    """
    #pull out start and end points
    lat_start = cordf.iloc[0,1]
    lat_stop = cordf.iloc[-1,1]
    long_start = cordf.iloc[0,0]
    long_stop = cordf.iloc[-1,0]

    #find direction of movement
    if lat_start > lat_stop:
        lat_dir = 'DOWN'
    else:
        lat_dir = 'UP'
    if long_start > long_stop:
        long_dir = 'DOWN'
    else:
        long_dir = 'UP'

    #caculate range
    lat_range = max(lat_start, lat_stop) - min(lat_start, lat_stop)
    long_range = max(long_start, long_stop) - min(long_start, long_stop)

    #create ideal line dataframe
    ideal_line = cordf.copy()
    for i, row in ideal_line.iterrows():
        if i != 0 and i != len(ideal_line-1):
            if lat_dir == 'UP':
                ideal_line.iloc[i,1] = ideal_line.iloc[i-1,1] + lat_range / len(ideal_line)
            else:
                ideal_line.iloc[i,1] = ideal_line.iloc[i-1,1] - lat_range / len(ideal_line)
            if long_dir == 'UP':
                ideal_line.iloc[i,0] = ideal_line.iloc[i-1,0] + long_range / len(ideal_line)
            else:
                ideal_line.iloc[i,0] = ideal_line.iloc[i-1,0] - long_range / len(ideal_line)

    #caculate the squared residule between each point in the lines
    error = cordf.copy()
    for i, row in cordf.iterrows():
        error.iloc[i,0] = math.pow(ideal_line.iloc[i,0] - cordf.iloc[i,0], 2)
        error.iloc[i,1] = math.pow(ideal_line.iloc[i,1] - cordf.iloc[i,1], 2)

    #caculate mean of the squared residuals
    mse = error.sum()
    mse_long = mse.loc["Longitude"] / len(error)
    mse_lat = mse.loc["Latitude"] / len(error)

    #approximatly convert decimal degrees to meters
    #http://wiki.gis.com/wiki/index.php/Decimal_degrees
    earth_radius = geopy.distance.ELLIPSOIDS['WGS-84'][0] * 1000
    earth_circumfrence = 2 * math.pi * earth_radius
    deg_to_meter = earth_circumfrence / 360
    mse_long = mse_long * deg_to_meter
    mse_lat = mse_lat * deg_to_meter

    #combine mse of latitude and longitude
    combined_mse = (mse_lat + mse_long) / 2

    #caculate square root of the mean
    rmse = math.sqrt(combined_mse)

    #convert long, lat axis to approx change in meters from starting point
    display_ax = cordf.copy()
    for i, row in display_ax.iterrows():
        if i == 0:
            display_ax.iloc[0,0] = 0   #longitude start zeroed
            display_ax.iloc[0,1] = 0   #latitude start zeroed
        else:                       #swap long and lat to distance from start in meters
            display_ax.iloc[i,0] = abs(position_diff( (cordf.iloc[0,0],0), (cordf.iloc[i,0],0) ))
            display_ax.iloc[i,1] = abs(position_diff( (0,cordf.iloc[0,1]), (0,cordf.iloc[i,1]) ))

    display_ln = ideal_line.copy()
    for i, row in display_ln.iterrows():
        if i == 0:
            display_ln.iloc[0,0] = 0
            display_ln.iloc[0,1] = 0
        else:
            display_ln.iloc[i,0] = abs(position_diff( (ideal_line.iloc[0,0],0), (ideal_line.iloc[i,0],0) ))
            display_ln.iloc[i,1] = abs(position_diff( (0,ideal_line.iloc[0,1]), (0,ideal_line.iloc[i,1]) ))

    #display graph
    plt.figure();
    plt.scatter(display_ax.iloc[:,0].tolist(), display_ax.iloc[:,1].tolist(), color='blue', label="Measured Points");
    plt.plot(display_ln.iloc[:,0].tolist(), display_ln.iloc[:,1].tolist(), color='green', label="Ideal Line")
    plt.legend()
    plt.title("Measured line vs Ideal");
    plt.xlabel("Distance along line of longitude in meters");
    plt.ylabel("Distance along line of latitude in meters");
    plt.ylim(bottom=0, top=max(display_ax.iloc[-1,1], display_ln.iloc[-1,1], display_ax.iloc[-1,0], display_ln.iloc[-1,0]))
    plt.xlim(left=0, right=max(display_ax.iloc[-1,1], display_ln.iloc[-1,1], display_ax.iloc[-1,0], display_ln.iloc[-1,0]))
    yaxis = plt.gca().get_yticks()
    plt.gca().yaxis.set_major_locator(mticker.FixedLocator(yaxis))
    plt.gca().set_yticklabels(['{:.2}'.format(x) for x in yaxis])
    xaxis = plt.gca().get_xticks()
    plt.gca().xaxis.set_major_locator(mticker.FixedLocator(xaxis))
    plt.gca().set_xticklabels(['{:.2f}'.format(x) for x in xaxis])
    plt.grid(True);
    plt.show()

    return rmse

def main(argv):
    if len(argv) != 4:
        raise ValueError("Expected three arguments: dwell time (min), line length (meters), path to kml file")
    dwell_time_minutes = int(argv[1])
    if dwell_time_minutes < 2:
        raise ValueError("Dwell time cannot be less than 2 minutes")
    line_length_meters = int(argv[2])
    filepath = str(argv[3])

    #read and remove the first 20s of data
    file = read_ublox(filepath)

    #print results
    print("KML Analysis Results")
    print()
    print("*********")
    print("PRECISION")
    print("*********")

    #Report the precision at a static point in +/- meters
    precision = []

    #get the first 60 seconds of data
    long = file.iloc[:60,0].tolist()
    lat = file.iloc[:60,1].tolist()
    cords = zip(long, lat)

    #plot scatter graph of first 60 seconds of data
    plt.figure();
    plt.scatter(long, lat, color='green');
    plt.title("Plot of readings 0:20 to 1:20");
    plt.xlabel("Longitude in Decimal Degrees");
    plt.ylabel("Latitude in Decimal Degrees");
    #plt.xlim(long[0], long[-1])
    #plt.ylim(lat[0], lat[-1])
    yaxis = plt.gca().get_yticks()
    plt.gca().yaxis.set_major_locator(mticker.FixedLocator(yaxis))
    plt.gca().set_yticklabels(['{:.6f}'.format(x) for x in yaxis])
    xaxis = plt.gca().get_xticks()
    plt.gca().xaxis.set_major_locator(mticker.FixedLocator(xaxis))
    plt.gca().set_xticklabels(['{:.6f}'.format(x) for x in xaxis])
    plt.grid(True);
    plt.show()

    #generate list of all cordinate combinations
    all_combos = []
    for i, cord1 in enumerate(cords):
        for j, cord2 in enumerate(cords):
            if j != i: #skip pairing with itself
                all_combos.append([cord1, cord2])

    #find difference in meters between each cordinate combination
    for i, cord in enumerate(all_combos):
        all_combos[i].append(position_diff(cord[0],cord[1]))

    #find max differnce in meters
    maximum = 0
    minimum = 0
    for cord in all_combos:
        if cord[2] > maximum:
            maximum = cord[2]
        elif cord[2] < minimum:
            minimum - cord[2]

    print("Max delta = +/- {}m".format((maximum - minimum) / 2.0))
    print()
    print("********")
    print("ACCURACY")
    print("********")

    #Report the accuracy of a known distance
    length = position_diff( (file.iloc[0,0], file.iloc[0,1]), \
                            (file.iloc[len(file)-1,0], file.iloc[len(file)-1,1]))

    print('Target line length was {}m'.format(line_length_meters))
    print('Measured line length = {}m'.format(length))
    print('Line length delta = {}m'.format(line_length_meters - length))
    print()
    print("************")
    print("STRAIGHTNESS")
    print("************")

    #Report the root mean square error in meters of a straight line
    print('Root Mean Squared Error = {}m'.format(line_straightness(file)))
    print()
    return

# script autorun
if __name__ == "__main__":
    main(sys.argv);
