# pyWaFFill
## The python flood fill walkability calculator

Input: CityIO-compatible grid

Output: GeoJSON with isochrones

### Installation

Requires
* python3
* pyproj
* requests
* docker optional

```./install.sh``` (docker)

```pip install -r requirements.txt``` (without docker)

### Usage

```./run.sh``` (docker)

```python main.py``` (without docker)


### Description

Reads grid from CityIO (define table-URL in config.json) and parses all cells with types as in typedef.json.
Stores and posts (define output URL in config.json) FeatureCollection of isochrone polys to CityIO.

### Open Questions
* connect 4-neighbourhoods only or also 8-neighbourhoods?