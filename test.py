import main
from pyproj import Transformer

def mock():
    ret = main.Table()
    ret.cellSize = 16
    ret.ncols = ret.nrows = 3
    ret.mapping = [{"type":"empty"}]
    ret.typeidx = 0
    ret.tablerotation = 0

    proj = Transformer.from_crs(main.getFromCfg("input_crs"), main.getFromCfg("compute_crs"))
    ret.origin = proj.transform(53, 10)

    ret.grid = [[0,0]]*ret.nrows*ret.ncols

    return ret

def test_floodfill_empty():
    mocktable = mock()
    seedpoints = [0]
    filledgrid = main.floodFill(seedpoints,mocktable)
    assert(str(filledgrid)==str([0, 0.48, 0.96, 0.48, 0.96, 1.44, 0.96, 1.44, 1.92]))