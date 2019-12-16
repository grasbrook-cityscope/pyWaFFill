import json
import math
import requests
from pyproj import Transformer
from time import sleep
import argparse
from sortedcontainers import SortedList

class Table:
    cellSize = 0
    ncols = 0
    nrows = 0

    @staticmethod
    def fromCityIO(data):
        ret = Table()
        ret.cellSize = data["spatial"]["cellSize"]
        ret.ncols = data["spatial"]["ncols"]
        ret.nrows = data["spatial"]["nrows"]
        ret.mapping = data["mapping"]["type"]
        ret.typeidx = data["block"].index("type")
        ret.tablerotation = data["spatial"]["rotation"]

        proj = Transformer.from_crs(getFromCfg("input_crs"), getFromCfg("compute_crs"))
        ret.origin = proj.transform(data["spatial"]["latitude"], data["spatial"]["longitude"])

        return ret

    def updateGrid(self,endpoint=-1, token=None):
        self.grid = getCurrentState("grid", endpoint, token)

    def Local2Geo(self, x, y):
        bearing = self.tablerotation

        x *= self.cellSize
        y *= -self.cellSize # flip y axis (for northern hemisphere)

        # rotate and scale
        new_x = x * math.cos(math.radians(bearing)) - y * math.sin(math.radians(bearing))
        new_y = x * math.sin(math.radians(bearing)) + y * math.cos(math.radians(bearing))

        # convert to geo coords
        return (new_x + self.origin[0], new_y + self.origin[1])

def getFromCfg(key: str) -> str:
    #import os#os.path.dirname(os.path.realpath(__file__)+
    with open("config.json") as file:
        js = json.load(file)
        return js[key]

def getCurrentState(topic="", endpoint=-1, token=None):
    if endpoint == -1 or endpoint == None:
        get_address = getFromCfg("input_url")+topic # default endpoint
    else:
        get_address = getFromCfg("input_urls")[endpoint]+topic # user endpoint

    if token is None:
        r = requests.get(get_address, headers={'Content-Type': 'application/json'})
    else: # with authentication
        r = requests.get(get_address, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer '+token})
    
    if not r.status_code == 200:
        print("could not get from cityIO")
        print("Error code", r.status_code)
        return {} 

    return r.json()

def sendToCityIO(data, endpoint=-1, token=None):
    if endpoint == -1 or endpoint == None:
        post_address = getFromCfg("output_url") # default endpoint
    else:
        post_address = getFromCfg("output_urls")[endpoint] # user endpoint

    if token is None:
        r = requests.post(post_address, json=data, headers={'Content-Type': 'application/json'})
    else: # with authentication
        r = requests.post(post_address, json=data, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer '+token})
    print(r)
    if not r.status_code == 200:
        print("could not post result to cityIO", post_address)
        print("Error code", r.status_code)
    else:
        print("Successfully posted to cityIO", post_address, r.status_code)

def PolyToGeoJSON(points, id, properties):
    ret = "{\"type\": \"Feature\",\"id\": \"" 
    ret += str(id) 
    ret += "\",\"geometry\": {\"type\": \"Polygon\",\"coordinates\": [["

    # lat,lon order
    for p in points:
        ret+="["+str(p[1])+","+str(p[0])+"],"
    ret+="["+str(points[0][1])+","+str(points[0][0])+"]" # closed ring, last one without trailing comma

    ret += "]]},"
    ret += "\"properties\": {"
    for key in properties: # properties to string
        ret += "\""+key+"\""
        ret += ":"
        ret += str(properties[key])
        ret += ","
    if len(properties) > 0:
        ret=ret[:-1] # delete trailing comma after properties
    ret += "}}"
    return ret

def writeFile(filepath, data):
    f= open(filepath,"w+")
    f.write(data)
    
def appendPolyFeatures(filledGrids, cityio):
    filledGrid = list(filledGrids.values())[0]
    resultjson = ""

    proj = Transformer.from_crs(getFromCfg("compute_crs"), getFromCfg("output_crs"))
    for idx in range(len(filledGrid)):
        x = idx % cityio.ncols
        y = idx // cityio.ncols

        properties = {}
        for blduse in filledGrids:
            if filledGrids[blduse][idx] is None:
                print("Warning: Grid cell", str(idx), "is None!")
                continue # non-initialised cell, skip
            value = filledGrids[blduse][idx].timeTo
            if(value == float("inf")):
                print("Warning: Grid cell", str(idx), "is inf!")
                continue # inf can't be parsed as geojson, skip this type
            properties[blduse] = value
        if len(properties) == 0:
            continue # no properties, so don't create a feature

        pointlist = []

        fromPoint = cityio.Local2Geo(x,y) # upper left
        fromPoint = proj.transform(fromPoint[0],fromPoint[1])
        pointlist.append(fromPoint)

        toPoint = cityio.Local2Geo(x+1,y) # upper right
        toPoint = proj.transform(toPoint[0],toPoint[1])
        pointlist.append(toPoint)
        toPoint = cityio.Local2Geo(x+1,y+1) # bottom right
        toPoint = proj.transform(toPoint[0],toPoint[1])
        pointlist.append(toPoint)
        toPoint = cityio.Local2Geo(x,y+1) # bottom left
        toPoint = proj.transform(toPoint[0],toPoint[1])
        pointlist.append(toPoint)

        resultjson += PolyToGeoJSON(pointlist, idx, properties) # append feature, closes loop
        resultjson +=","

    resultjson = resultjson[:-1] # trim trailing comma
    return resultjson

def getSeedPoints(blduse, cityio: Table):
    seedPoints = []

    for index,cell in enumerate(cityio.grid):
        
        if not "type" in cityio.mapping[cell[cityio.typeidx]]: continue

        if cityio.mapping[cell[cityio.typeidx]]["type"] == "building":
            celltype =cityio.mapping[cell[cityio.typeidx]]["type"]

            if not ("bld_useGround" in cityio.mapping[cell[cityio.typeidx]]): continue
            celluse = cityio.mapping[cell[cityio.typeidx]]["bld_useGround"]

            if cityio.mapping[cell[cityio.typeidx]]["bld_useGround"] == blduse or \
                cityio.mapping[cell[cityio.typeidx]]["bld_useUpper"] == blduse:
                seedPoints.append(index)

    # don't add multiple seedpoints for touching buildings
    seedPoints = mergeSeedpoints(seedPoints,cityio)

    return seedPoints

def mergeSeedpoints(seedpoints, cityio):
    groups = []

    # find out, which seedpoints are adjacent, and joined in lines or groups
    for seedpoint in seedpoints:
        alreadyseen = False
        for group in groups:
            if seedpoint in group:
                alreadyseen = True
        if alreadyseen:
            continue

        newgroup = set()
        recursiveFindConnected(seedpoint, seedpoints, cityio, newgroup)
        groups.append(newgroup)

    print(groups)

    # remove all but one per disconnected group
    newSeedPoints = []
    for group in groups:
        seed = group.pop()
        newSeedPoints.append(seed)
    return newSeedPoints

def recursiveFindConnected(currentCell, seedpoints, cityio, newgroup):
    newgroup.add(currentCell)
    for neighbourCell in getNeighbouringGridCells(currentCell, cityio.ncols, cityio.nrows):
        if neighbourCell in seedpoints and neighbourCell not in newgroup:
            recursiveFindConnected(neighbourCell, seedpoints, cityio, newgroup)

class ResultCell:
    timeTo = float("inf")

    def __init__(self, index):
        self.index = index

    def __repr__(self): # required for list to str
        return str(self.timeTo)
    def __str__(self): # required for printing
        return str(self.timeTo)
    def __gt__(self, cell2): # required for sorting
        return float(self.timeTo) > float(cell2.timeTo)
    def __eq__(self, cell2): # required for sorting
        return float(self.timeTo) == cell2.timeTo

def getNeighbouringGridCells(index, gridcols, gridrows, neighbourhood=4):
    x = index % gridcols
    y = index // gridcols
    assert((index - x) / gridcols == index // gridcols)

    if gridcols < 2 or gridrows < 2:
        raise ValueError("grid too small!")

    neighboursIndexList = []

    #check left
    if x > 0:
        neighboursIndexList.append(index - 1)
    #check right
    if x < gridcols - 1:
        neighboursIndexList.append(index + 1)
    #check top
    if y > 0:
        neighboursIndexList.append(index - gridcols)
    #check bottom
    if y < gridrows - 1:
        neighboursIndexList.append(index + gridcols)

    if neighbourhood == 8:
        raise NotImplementedError("8-neighbourhood not yet implemented!")

    for idx in neighboursIndexList:
        assert(idx < gridrows * gridcols)

    return neighboursIndexList

def getTimeForCell(cellindex, useofinterest, cityio: Table):
    """ calculate the walking time it takes to get to the cell with index cellindex from any of it's direct neighbours
        returns float, if the requested cell is impassable, returns inf """

    cell = cityio.grid[cellindex]
    if not "type" in cityio.mapping[cell[cityio.typeidx]]: return float("inf")

    celltype = cityio.mapping[cell[cityio.typeidx]]["type"]

    # calculate time via distance and type factor and move speed
    walkspeed_metersperminute = getFromCfg("walking_speed_kph") / 60 * 1000
    distance = cityio.cellSize # TODO: only valid for 4-neighbourhoods!
    walktime_minutes= 1/walkspeed_metersperminute * distance

    # TODO: get speed factors from typedefs.json
    if celltype == "street":
        return 1.0 * walktime_minutes

    elif celltype == "open_space":
        if cityio.mapping[cell[cityio.typeidx]]["os_type"] == "water":
            return float("inf") # water is impassable
        else:
            return 1.0 * walktime_minutes

    elif celltype == "building":
        cellUseGround = cityio.mapping[cell[cityio.typeidx]]["bld_useGround"]
        cellUseUpper = cityio.mapping[cell[cityio.typeidx]]["bld_useUpper"]

        if cellUseGround == useofinterest or cellUseUpper == useofinterest:
            return 0.0
        else:
            return float("inf") # buildings are impassable

    elif  celltype == "empty":
        return float("inf") # empty space is impassable, users should set something

    else:
        raise ValueError("what is "+celltype)

def floodFill(seedpoints, useofinterest, cityio: Table):
    filledGrid = [None]*len(cityio.grid)

    neighbourhood = 4 # orthognal, alternative: 8 including diagonal NOT IMPLEMENTED

    # start from each seedpoint
    for seedIndex in seedpoints:
        if filledGrid[seedIndex] is None:
            filledGrid[seedIndex] = ResultCell(seedIndex)
        seedCell = filledGrid[seedIndex]
        seedCell.timeTo = 0

        dijkstra(filledGrid, seedIndex, useofinterest, cityio, neighbourhood)

    return filledGrid

def dijkstra(filledGrid, startindex, useofinterest, cityio: Table, neighbourhood):
    print("finding paths from seedcell", startindex)
    
    openlist = SortedList() # sort cells increasing by time needed
    openlist.add(filledGrid[startindex])

    while len(openlist) > 0: # more cells to process
        curCell = openlist.pop(0) # always pick cell with lowest time first

        neighboursIndices = getNeighbouringGridCells(curCell.index, cityio.ncols, cityio.nrows, neighbourhood)

        for neighbourIndex in neighboursIndices:
            if filledGrid[neighbourIndex] is None:
                filledGrid[neighbourIndex] = ResultCell(neighbourIndex)
            neighbourCell = filledGrid[neighbourIndex]
            
            # calculate time needed to go to neighbour
            newTime = curCell.timeTo + getTimeForCell(neighbourIndex, useofinterest, cityio) # consider types of neighbours 
            if newTime < neighbourCell.timeTo:
                if neighbourCell in openlist:
                    openlist.remove(neighbourCell) # remove first then add again, to resort
                neighbourCell.timeTo = float(newTime) # set value for neighbours into gridcell
                openlist.add(neighbourCell) # cell was cahnged, it can propagate change

def makeGeoJSON(filledGrids, cityio):
    resultjson = "{\"type\": \"FeatureCollection\",\"features\": [" # geojson front matter

    # append features for all grid cells
    resultjson += appendPolyFeatures(filledGrids, cityio)

    resultjson += "]}" # geojson end matter
    return resultjson

def makeCSV(filledGrid, filepath, cityio):
    with open(filepath,"w") as file:
        for i in range(cityio.nrows):
            for j in range(cityio.ncols):
                file.write(str(filledGrid[j + i * cityio.ncols]))
                file.write(",")
            file.write("\n")
            
def run(endpoint=-1, token=None):
    cityio = Table.fromCityIO(getCurrentState("header",endpoint, token))
    if not cityio:
        print("couldn't load input_url!")
        exit()

    cityio.updateGrid(endpoint, token)

    filledGrids = {}
    for useofinterest in getFromCfg("usesOfInterest"):
        seedpoints = getSeedPoints(useofinterest, cityio)
        filledGrid = floodFill(seedpoints, useofinterest, cityio)
        filledGrids[useofinterest]=filledGrid
        # makeCSV(filledGrid,"test"+useofinterest+".csv",cityio)
    
    resultjson = makeGeoJSON(filledGrids,cityio)
    # writeFile("output.geojson", resultjson)

    # Also post result to cityIO
    data = json.loads(resultjson)
    gridHash = getCurrentState("meta/hashes/grid",endpoint, token)
    data["grid_hash"] = gridHash # state of grid, the results are based on

    sendToCityIO(data)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='calculate walkability from cityIO.')
    parser.add_argument('--endpoint', type=int, default=-1,help="endpoint url to choose from config.json/input_urls")
    args = parser.parse_args()
    print("endpoint",args.endpoint)
    oldHash = ""

    try:
        with open("token.txt") as f:
            token=f.readline()
        if token=="": token = None # happens with empty file
    except IOError:
        token=None

    while True:
        gridHash = getCurrentState("meta/hashes/grid", int(args.endpoint), token)
        if gridHash != {} and gridHash != oldHash:
            run(int(args.endpoint))
            oldHash = gridHash
        else:
            print("waiting for grid change")
            sleep(5)