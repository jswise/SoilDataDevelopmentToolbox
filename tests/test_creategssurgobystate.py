import logging
import pytest

from gssurgo.creategssurgobystate import CreateGSSURGOByState

INPUT_FOLDER = r'c:\temp\SSURGO'
OUTPUT_FOLDER = r'c:\temp\ssurgo3'
STATES = ['Marshall Islands']

@pytest.fixture
def victim():
    return CreateGSSURGOByState(log_level=logging.INFO)

def test_execute(victim):
    params = victim.getParameterInfo()
    params[0].value = INPUT_FOLDER
    params[1].value = OUTPUT_FOLDER
    params[2].value = STATES
    victim.execute(params, None)

if __name__ == '__main__':
    pytest.main([__file__])