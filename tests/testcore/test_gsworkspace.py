import logging
import os
import pytest

from gssurgo.core.gsworkspace import GSWorkspace

@pytest.fixture
def victim():
    return GSWorkspace(log_level=logging.DEBUG)

def test_get_path(victim):
    ws_folder = victim.get_path()
    assert 'Workspace' in ws_folder
    assert os.path.exists(ws_folder)
