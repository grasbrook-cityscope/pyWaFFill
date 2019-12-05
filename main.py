import json
import math
import requests
from pyproj import Transformer
from time import sleep
import argparse

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

    def RoadAt(self, gridData, typejs, x, y):
        cell = gridData[x + y * self.ncols] # content of cell at (x,y)
        if not "type" in self.mapping[cell[self.typeidx]]: return False
        return self.mapping[cell[self.typeidx]]["type"] in typejs["type"]

    def Local2Geo(self, x, y):
        bearing = self.tablerotation

        x *= self.cellSize
        y *= -self.cellSize # flip y axis (for northern hemisphere)

        # rotate and scale
        new_x = x * math.cos(math.radians(bearing)) - y * math.sin(math.radians(bearing))
        new_y = x * math.sin(math.radians(bearing)) + y * math.cos(math.radians(bearing))

        # convert to geo coords
        return (new_x + self.origin[0], new_y + self.origin[1])

def getFromCfg(key : str) -> str:
    #import os#os.path.dirname(os.path.realpath(__file__)+
    with open("config.json") as file:
        js = json.load(file)
        return js[key]

def getCurrentState(topic="", endpoint=-1, token=None):
    if endpoint == -1 or endpoint == None:
        get_address = getFromCfg("input_url")+topic
    else:
        get_address = getFromCfg("input_urls")[endpoint]+topic

    if token is None:
        r = requests.get(get_address, headers={'Content-Type': 'application/json'})
    else:
        r = requests.get(get_address, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer '+token})
    
    if not r.status_code == 200:
        print("could not get from cityIO")
        print("Error code", r.status_code)

    return r.json()

def sendToCityIO(data, endpoint=-1, token=None):
    if endpoint == -1 or endpoint == None:
        post_address = getFromCfg("output_url")
    else:
        post_address = getFromCfg("output_urls")[endpoint]

    if token is None:
        r = requests.post(post_address, json=data, headers={'Content-Type': 'application/json'})
    else:
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
    for key in properties:
        ret += "\""+key+"\""
        ret += ":"
        ret += str(properties[key])
        ret += ","
    ret=ret[:-1] # delete trailing comma after properties
    #ret += str(properties)
    ret += "}}"
    return ret

def writeFile(filepath, data):
    f= open(filepath,"w+")
    f.write(data)
    
def appendPolyFeatures(filledGrid, cityio):
    gridData = cityio.grid
    idit= 0
    resultjson = ""


    proj = Transformer.from_crs(getFromCfg("compute_crs"), getFromCfg("output_crs"))
    for idx in range(len(gridData)):
        x = idx % cityio.ncols
        y = idx // cityio.ncols

        if x >= cityio.ncols-1:    # don't consider last row
            continue
        if y >= cityio.nrows-1:    # don't consider last column
            break

        pointlist = []

        fromPoint = cityio.Local2Geo(x,y)
        fromPoint = proj.transform(fromPoint[0],fromPoint[1])
        pointlist.append(fromPoint)

        toPoint = cityio.Local2Geo(x+1,y)
        toPoint = proj.transform(toPoint[0],toPoint[1])
        pointlist.append(toPoint)
        toPoint = cityio.Local2Geo(x+1,y+1)
        toPoint = proj.transform(toPoint[0],toPoint[1])
        pointlist.append(toPoint)
        toPoint = cityio.Local2Geo(x,y+1)
        toPoint = proj.transform(toPoint[0],toPoint[1])
        pointlist.append(toPoint)

        if filledGrid[idx] is None:
            print("Warning: Grid cell"+str(idx)+"is None!")
            value = 1000
        else:
            value = filledGrid[idx].timeTo

        resultjson += PolyToGeoJSON(pointlist, idit, {"walktime":value}) # append feature
        resultjson +=","

        idit+=1

    return resultjson

def getSeedPoints(blduse, cityio: Table):
    seedPoints = []

    # TODO: don't add multiple seedpoints for touching buildings
    for index,cell in enumerate(cityio.grid):
        
        if not "type" in cityio.mapping[cell[cityio.typeidx]]: continue

        if cityio.mapping[cell[cityio.typeidx]]["type"] == "building":
            celltype =cityio.mapping[cell[cityio.typeidx]]["type"]

            if not ("bld_useGround" in cityio.mapping[cell[cityio.typeidx]]): continue
            celluse = cityio.mapping[cell[cityio.typeidx]]["bld_useGround"]

            if cityio.mapping[cell[cityio.typeidx]]["bld_useGround"] == blduse or \
                cityio.mapping[cell[cityio.typeidx]]["bld_useUpper"] == blduse:
                seedPoints.append(index)

    return seedPoints

class ResultCell:
    beenThere = False
    timeTo = float("inf")
    # typeTo = None

    # def __init__(self, typeTo):
    #     self.typeTo = typeTo
    def __repr__(self):
        return str(self.timeTo)
    def __str__(self):
        return str(self.timeTo)

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

def getTimeForCell(cellindex,cityio: Table):
    cell = cityio.grid[cellindex]
    if not "type" in cityio.mapping[cell[cityio.typeidx]]: return float("inf")

    celltype = cityio.mapping[cell[cityio.typeidx]]["type"]

    # calculate time via distance and type factor and move speed
    walkspeed_metersperminute = getFromCfg("walking_speed_kph") / 60 * 1000
    distance = cityio.cellSize # TODO: only valid for 4-neighbourhoods!
    walktime_minutes= 1/walkspeed_metersperminute * distance

    if celltype == "street":
        return 1.0 * walktime_minutes
    elif celltype == "open_space":
        return 1.0 * walktime_minutes
    elif celltype == "building":
        return 10.0 * walktime_minutes#float("inf")

    elif  celltype == "empty":
        return 2.0 * walktime_minutes

    else:
        raise ValueError("what is "+celltype)

def floodFill(seedpoints, cityio: Table):
    filledGrid = [None]*len(cityio.grid)

    neighbourhood = 4 # orthognal, alternative: 8 including diagonal

    # start from each seedpoint
    for seedIndex in seedpoints:
        if filledGrid[seedIndex] is None:
            filledGrid[seedIndex] = ResultCell()
        seedCell = filledGrid[seedIndex]
        seedCell.beenThere = True
        seedCell.timeTo = 0

        dijkstra(filledGrid, seedIndex, cityio, neighbourhood)

        for cell in filledGrid:
            cell.beenThere = False

    return filledGrid

def dijkstra(filledGrid, startindex, cityio, neighbourhood):
    openlist = []    
    openlist.append(startindex)

    while len(openlist) > 0:
        # more cells to process

        print(len(openlist))
        curCellIndex = openlist.pop()

        if filledGrid[curCellIndex] is None:
            filledGrid[curCellIndex] = ResultCell()
        curCell = filledGrid[curCellIndex]
        curCell.beenThere = True

        neighboursIndices = getNeighbouringGridCells(curCellIndex, cityio.ncols, cityio.nrows, neighbourhood)

        for neighbourIndex in neighboursIndices:
            if filledGrid[neighbourIndex] is None:
                filledGrid[neighbourIndex] = ResultCell()
            neighbourCell = filledGrid[neighbourIndex]

            if not neighbourIndex in openlist and not neighbourCell.beenThere:
                openlist.append(neighbourIndex)
            
            # calculate time needed to go to neighbour
            newTime = curCell.timeTo + getTimeForCell(neighbourIndex, cityio) # consider types of neighbours 
            if newTime < neighbourCell.timeTo:
                neighbourCell.timeTo = newTime # set value for neighbours into gridcell
            
            # neighbourCell.beenThere = True

def recursiveNeighbourset(curCellIndex, filledGrid, neighbourhood, cityio: Table):
    if filledGrid[curCellIndex] is None:
        filledGrid[curCellIndex] = ResultCell()
    curCell = filledGrid[curCellIndex]
    
    # iterate over neighbours
    neighboursIndices = getNeighbouringGridCells(curCellIndex, cityio.ncols, cityio.nrows, neighbourhood)

    madeChangeinNeighbours = False

    for neighbourIndex in neighboursIndices:
        if filledGrid[neighbourIndex] is None:
            filledGrid[neighbourIndex] = ResultCell()
        neighbourCell = filledGrid[neighbourIndex]
        if neighbourCell.beenThere:
            continue

        # calculate time needed to go there
        newTime = curCell.timeTo + getTimeForCell(neighbourIndex,cityio) # consider types of neighbours 
        if newTime < neighbourCell.timeTo:
            neighbourCell.timeTo = newTime # set value for neighbours into gridcell
            madeChangeinNeighbours = True
            

        # start from each neighbour
        recursiveNeighbourset(neighbourIndex, filledGrid, neighbourhood, cityio)
        
    if not madeChangeinNeighbours:
        #this cell is done
        curCell.beenThere = True

def makeGeoJSON(filledGrid, cityio):
    resultjson = "{\"type\": \"FeatureCollection\",\"features\": [" # geojson front matter

    # find all grid cells with type as in typejs
    resultjson += appendPolyFeatures(filledGrid, cityio)

    resultjson = resultjson[:-1] # trim trailing comma
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

    seedpoints = getSeedPoints("educational",cityio)
    filledGrid = floodFill(seedpoints, cityio)
    # print(filledGrid)
    makeCSV(filledGrid,"test.csv",cityio)
    resultjson = makeGeoJSON(filledGrid,cityio)
    # writeFile("output.geojson", resultjson)

    # Also post result to cityIO
    data = json.loads(resultjson)
    gridHash = getCurrentState("meta/hashes/grid",endpoint, token)
    data["grid_hash"] = gridHash # state of grid, the results are based on

    sendToCityIO(data)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='calculate storm water amounts from cityIO.')
    parser.add_argument('--endpoint', type=int, default=-1,help="endpoint url to choose from config.ini/input_urls")
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
        if gridHash != oldHash:
            run(int(args.endpoint))
            oldHash = gridHash
        else:
            print("waiting for grid change")
            sleep(5)