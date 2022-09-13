#!/usr/bin/python3

"""
MODULE DESCRIPTION
Collection of tools for running caculations on Google Earth .kml files
output by uBlox UConnect software. Parsing handled by pyKML library,
based on lxml library.

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
# start debugging
import pdb

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
                lat.append(float(cordinates[0]))
                long.append(float(cordinates[1]))
                alt.append(float(cordinates[2]))

        #remove the first 30 seconds
        lat = lat[30:]
        long = long[30:]
        alt = alt[30:]

        #create pandas dataframe
        names = ['Longitude', 'Latitude', 'Altitude']
        cordf = pandas.DataFrame(list(zip(lat,long,alt)), columns=names)

        return cordf

def position_diff(testcord, targetcord):
    """
    FUNCTION DESCRIPTION
    compares test and target points and caculates distance in meters between them

    INPUTS
    testcord, float tuple, latitude and longitude of test point in that order in decimal degrees
    targetcord, float tuple, latitude and longitude of target point in that order in decimal degrees

    OUTPUTS
    delta, string, distance in meters from given point
    """
    return geopy.distance.distance(testcord, targetcord).m

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

    #pdb.set_trace()

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
        error.iloc[i,1] = math.pow(ideal_line.iloc[i,1] - cordf.iloc[i,1], 2)
        error.iloc[i,0] = math.pow(ideal_line.iloc[i,0] - cordf.iloc[i,0], 2)

    #caculate mean of the squared residuals
    mse = error.sum()
    mse_lat = mse.loc["Latitude"] / len(error)
    mse_long = mse.loc["Longitude"] / len(error)

    #approximatly convert decimal degrees to meters
    #http://wiki.gis.com/wiki/index.php/Decimal_degrees
    earth_radius = geopy.distance.ELLIPSOIDS['WGS-84'][0] * 1000
    earth_circumfrence = 2 * math.pi * earth_radius
    deg_to_meter = earth_circumfrence / 360
    mse_lat = mse_lat * deg_to_meter
    mse_long = mse_long * deg_to_meter

    #combine mse of latitude and longitude
    combined_mse = (mse_lat + mse_long) / 2

    #caculate square root of the mean
    rmse = math.sqrt(combined_mse)

    plt.figure();
    plt.scatter(cordf.iloc[:,0].tolist(), cordf.iloc[:,1].tolist(), color='blue', label="Measured Points");
    plt.plot(ideal_line.iloc[:,0].tolist(), ideal_line.iloc[:,1].tolist(), color='green', label="Ideal Line")
    plt.legend()
    plt.title("Measured line vs Ideal");
    plt.xlabel("Longitude in Decimal Degrees");
    plt.ylabel("Latitude in Decimal Degrees");
    #plt.ylim(lat_start, lat_stop)
    #plt.xlim(long_start, long_stop)
    yaxis = plt.gca().get_yticks()
    plt.gca().yaxis.set_major_locator(mticker.FixedLocator(yaxis))
    plt.gca().set_yticklabels(['{:.6f}'.format(x) for x in yaxis])
    xaxis = plt.gca().get_xticks()
    plt.gca().xaxis.set_major_locator(mticker.FixedLocator(xaxis))
    plt.gca().set_xticklabels(['{:.6f}'.format(x) for x in xaxis])
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
    print("T0030 KML Analysis by Steve")
    print()
    print("*********")
    print("PRECISION")
    print("*********")

    #Report the precision at a static point in +/- meters
    precision = []

    #get the first 60 seconds of data
    lat = file.iloc[:60,1].tolist()
    long = file.iloc[:60,0].tolist()
    cords = zip(lat, long)

    #plot scatter graph of first 60 seconds of data
    plt.figure();
    plt.scatter(long, lat, color='green');
    plt.title("Plot of readings 0:30 to 1:30");
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
    length = position_diff( (file.iloc[0,1], file.iloc[0,0]), \
                            (file.iloc[len(file)-1,1], file.iloc[len(file)-1,0]))

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
