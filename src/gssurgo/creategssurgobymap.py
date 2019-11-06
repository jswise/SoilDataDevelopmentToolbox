import arcpy

from gssurgo.core.pyttool import PYTTool
import gssurgo.SSURGO_Convert_to_Geodatabase

class CreategSSURGOByMap(PYTTool):

    def execute(self, parameters, messages):
        """Extract the data."""

        params = self.get_param_val_dict(parameters)
        inputFolder = params['inputFolder']
        ssaLayer = params['ssaLayer']
        surveyList = list(params['surveyList'])
        outputWS = params['outputWS']
        AOI = params['AOI']
        aliasName = params['aliasName']
        useTextFiles = params['useTextFiles']

        if arcpy.Exists(ssaLayer):
            # Sort_management (in_dataset, out_dataset, sort_field, {spatial_sort_method})
            areasymbolList = gssurgo.SSURGO_Convert_to_Geodatabase.SortSurveyAreaLayer(ssaLayer, surveyList)

        else:
            areasymbolList = list()
        gssurgo.SSURGO_Convert_to_Geodatabase.gSSURGO(inputFolder, surveyList, outputWS, AOI, aliasName, useTextFiles, False, areasymbolList)
    
    def init_parameter_info(self):
        """Set the parameters for the tool."""

        self.add_param('inputFolder', 'SSURGO Downloads', datatype='DEFolder')
        self.add_param('ssaLayer', 'Survey Boundary Layer', datatype='GPFeatureLayer')
        self.add_param('surveyList', 'Input SSURGO Datasets', datatype='GPString', multiValue=True)
        self.add_param('outputWS', 'Output Geodatabase', datatype='DEWorkspace')
        self.add_param('AOI', 'Geographic Region', datatype='GPString')
        self.add_param('aliasName', 'Featureclass Identifier', datatype='GPString')
        self.add_param('useTextFiles', 'Use Text Files', datatype='GPBoolean')
