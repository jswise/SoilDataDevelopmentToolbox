import logging
import os

import arcpy
import pytest

from gssurgo.core.gsworkspace import GSWorkspace
from gssurgo.ssurgoconverter import SSURGOConverter

AREA_SYMBOL_LIST = ['MH936']
REGION = 'Pacific Islands Area'
SELECTOR_NAME = 'AreaSymSelector.shp'
STATES = ['Marshall Islands']
SURVEY_LIST = ['soil_mh936']

def get_data_folder():
    src = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(src, 'data')
@pytest.fixture
def data_folder():
    return get_data_folder()

@pytest.fixture
def spatial_folder(data_folder):
    return os.path.join(data_folder, 'soil_mh936', 'spatial')

@pytest.fixture
def tabular_folder(data_folder):
    return os.path.join(data_folder, 'soil_mh936', 'tabular')

def get_output_folder():
    gsws = GSWorkspace()
    return gsws.get_path()
@pytest.fixture
def output_folder():
    return get_output_folder()

@pytest.fixture
def output_gdb(output_folder):
    return os.path.join(output_folder, 'Output.gdb')

@pytest.fixture
def victim():
    return SSURGOConverter(log_level=logging.INFO)

def test_AppendFeatures(victim, spatial_folder, output_gdb):
    mupolygon = os.path.join(output_gdb, 'MUPOLYGON')
    arcpy.management.DeleteFeatures(mupolygon)
    area_sym = 'mh936'
    mupolyList = [os.path.join(spatial_folder, 'soilmu_a_{}.shp'.format(area_sym))]
    mulineList = [os.path.join(spatial_folder, 'soilmu_l_{}.shp'.format(area_sym))]
    mupointList = [os.path.join(spatial_folder, 'soilmu_p_{}.shp'.format(area_sym))]
    sflineList= [os.path.join(spatial_folder, 'soilsf_l_{}.shp'.format(area_sym))]
    sfpointList= [os.path.join(spatial_folder, 'soilsf_p_{}.shp'.format(area_sym))]
    sapolyList= [os.path.join(spatial_folder, 'soilsa_a_{}.shp'.format(area_sym))]
    featCnt = (67, 0, 0, 0, 0, 7)
    assert victim.AppendFeatures(output_gdb, REGION, mupolyList, mulineList, mupointList, sflineList, sfpointList, sapolyList, featCnt)

def test_CreateSSURGO_DB(victim, output_gdb):
    xml_path = victim.GetXML(REGION)
    if arcpy.Exists(output_gdb):
        arcpy.management.Delete(output_gdb)
    assert victim.CreateSSURGO_DB(output_gdb, xml_path, AREA_SYMBOL_LIST, '')
    assert arcpy.Exists(output_gdb)
    assert arcpy.Exists(os.path.join(output_gdb, 'mupolygon'))
    
def test_GetXML(victim):
    xml_path = victim.GetXML(REGION)
    assert 'PACBasin' in xml_path

def test_gSSURGO(victim, data_folder, output_gdb):
    selector_shp = os.path.join(data_folder, SELECTOR_NAME)
    selector_fl = arcpy.management.MakeFeatureLayer(selector_shp, 'selector_fl')
    if arcpy.Exists(selector_fl):
        # Sort_management (in_dataset, out_dataset, sort_field, {spatial_sort_method})
        areasymbolList = victim.SortSurveyAreaLayer(selector_fl, SURVEY_LIST)
    assert victim.gSSURGO(data_folder, SURVEY_LIST, output_gdb, REGION, None, True, False, areasymbolList)

def test_ImportMDTabular(victim, output_gdb, tabular_folder):
    assert victim.ImportMDTabular(output_gdb, tabular_folder)