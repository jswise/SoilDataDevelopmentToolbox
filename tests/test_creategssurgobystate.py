import logging
import os

import pytest

from gssurgo.core.gsworkspace import GSWorkspace
from gssurgo.creategssurgobystate import CreategSSURGOByState

STATES = ['Marshall Islands']

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
    return CreategSSURGOByState(log_level=logging.INFO)

def test_execute(victim, input_folder, output_folder):
    params = victim.getParameterInfo()
    params[0].value = input_folder
    params[1].value = output_folder
    params[2].value = STATES
    victim.execute(params, None)

if __name__ == '__main__':
    pytest.main([__file__])