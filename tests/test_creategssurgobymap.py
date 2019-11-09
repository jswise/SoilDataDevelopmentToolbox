import logging
import os

import pytest

from gssurgo.core.gsworkspace import GSWorkspace
from gssurgo.creategssurgobymap import CreategSSURGOByMap

REGION = 'Pacific Islands Area'
SELECTOR_NAME = 'AreaSymSelector.shp'
STATES = ['Marshall Islands']
SURVEY_LIST = ['soil_mh936']

@pytest.fixture
def input_folder():
    src = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(src, 'data')

@pytest.fixture
def output_folder():
    gsws = GSWorkspace()
    return gsws.get_path()

@pytest.fixture
def victim():
    return CreategSSURGOByMap(log_level=logging.INFO)

def test_execute(victim, input_folder, output_folder):
    selector_shp = os.path.join(input_folder, SELECTOR_NAME)
    output_gdb = os.path.join(output_folder, 'Output.gdb')

    params = victim.getParameterInfo()
    params[0].value = input_folder
    params[1].value = selector_shp
    params[2].value = SURVEY_LIST
    params[3].value = output_gdb
    params[4].value = REGION
    params[6].value = True

    victim.execute(params, None)

if __name__ == '__main__':
    pytest.main([__file__])