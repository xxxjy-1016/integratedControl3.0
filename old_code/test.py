import brain
import leg
from dataStructures import *

if __name__ == "__main__":
    test = brain.masterController()
    #test.init()
    test.moveTo(coordinate(80,80,0,0))
    #test.moveTo(test.coordinate_bottle_one_hand)
    test.relax_thorough()
    #test.openBottleOne()
    test.moveTo(test.coordinate_origin)
    test.relax()
    test.close()