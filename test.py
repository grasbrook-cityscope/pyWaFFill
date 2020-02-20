import main
from pyproj import Transformer
import unittest

class test_pywaffill(unittest.TestCase):
    def mock(self):
        ret = main.Table()
        ret.cellSize = 1
        ret.ncols = ret.nrows = 3
        ret.mapping = [{"type":"empty"}]
        ret.typeidx = 0
        ret.tablerotation = 0

        proj = Transformer.from_crs(main.getFromCfg("input_crs"), main.getFromCfg("compute_crs"))
        ret.origin = proj.transform(53, 10)

        ret.grid = [[0,0]]*ret.nrows*ret.ncols

        return ret


    def test_floodfill_empty(self):
        mocktable = self.mock()
        seedpoints = [0]

        walkspeed_metersperminute = main.getFromCfg("walking_speed_kph") / 60 * 1000
        useOfInterest = main.getFromCfg("usesOfInterest")[0]
        distance = mocktable.cellSize
        t = 2 * 1 / walkspeed_metersperminute * distance
        print(t)
        expected_result = [0, t, 2 * t,
                           t, 2 * t, 3 * t,
                           2 * t, 3 * t, 4 * t]

        filledgrid = main.floodFill(seedpoints, useOfInterest, mocktable)
        assert (str(filledgrid) == str(expected_result))



class test_error_handling(unittest.TestCase):

    def test_error_posting(self):
        with self.assertRaises(TimeoutError) as context:
            main.postToSlack("hallo", "test")

        self.assertTrue('This is broken' in context.exception)



if __name__ == '__main__':
    unittest.main()