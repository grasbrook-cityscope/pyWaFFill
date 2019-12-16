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

```./run.sh [endpoint]``` (docker)

```python main.py [--endpoint ENDPOINT]``` (without docker)

with endpoint being the index of input_urls and output_urls from the config.json respectively.


### Description

Reads grid from CityIO (define table-URL in config.json) and parses all cells with types as in typedef.json.
Stores and posts (define output URL in config.json) FeatureCollection of isochrone polys to CityIO.

### Configuration

"usesOfInterest" is a list of targets for the walkability analyses. Each element will be checked against a cityIO types "bls_useGround" and "bld_useUpper" strin. E.g.: ```["educational","culture"]```
"walking_speed_kph" : is the assumed average walking speed in kilometers per hour

### Open Questions
* connect 4-neighbourhoods only or also 8-neighbourhoods?