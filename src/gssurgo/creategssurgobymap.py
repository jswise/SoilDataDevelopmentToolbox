import os
import sys
import traceback

import arcpy

from gssurgo.core.pyttool import PYTTool
from gssurgo.ssurgoconverter import SSURGOConverter

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

        converter = SSURGOConverter(self.helpers)
        if arcpy.Exists(ssaLayer):
            # Sort_management (in_dataset, out_dataset, sort_field, {spatial_sort_method})
            areasymbolList = converter.SortSurveyAreaLayer(ssaLayer, surveyList)

        else:
            areasymbolList = list()
        converter.gSSURGO(inputFolder, surveyList, outputWS, AOI, aliasName, useTextFiles, False, areasymbolList)
    
    def init_parameter_info(self):
        """Set the parameters for the tool."""

        regions = [
            'Alaska',
            'American Samoa',
            'Hawaii',
            'Lower 48 States',
            'Pacific Islands Area',
            'Puerto Rico and U.S. Virgin Islands',
            'World'
        ]

        self.add_param('inputFolder', 'SSURGO Downloads', datatype='DEFolder')
        self.add_param('ssaLayer', 'Survey Boundary Layer', datatype='GPFeatureLayer')
        self.add_param('surveyList', 'Input SSURGO Datasets', datatype='GPString', multiValue=True)
        self.add_param('outputWS', 'Output Geodatabase', datatype='DEWorkspace')
        self.add_param('AOI', 'Geographic Region', datatype='GPString', valueList=regions)
        self.add_param('aliasName', 'Featureclass Identifier', datatype='GPString', parameterType='Optional')
        self.add_param('useTextFiles', 'Use Text Files', datatype='GPBoolean', defaultValue=True)

    def updateParameters(self, parameters):
        # Modify the values and properties of parameters before internal
        # validation is performed.  This method is called whenever a parameter
        # has been changed.

        try:
            # Query the database (param 1) to get a list of AREASYMBOLS
            # Get a list of valid SSURGO subfolders within (param 0) and make
            # sure there is a shapefile available for each AREASYMBOL.

            # Handle choice list according to the first two parameter values
            clearChoices = False
            refreshChoices = False

            if parameters[0].value is None or parameters[1].value is None:
                # One or more required parameters is missing, clear everything
                clearChoices = True
                refreshChoices = False

            else:
                # param 0 or param 1 has just been changed to a new value
                if (parameters[0].altered and not parameters[0].hasBeenValidated) or (parameters[1].altered and not parameters[1].hasBeenValidated):
                    clearChoices = True
                    refreshChoices = True

            if clearChoices:
                # Clear the choice list
                parameters[2].filter.list = []
                parameters[2].values = []

            if refreshChoices:
                # Clear the choice list and create a new one
                parameters[2].filter.list = []
                parameters[2].values = []

                # use searchcursor on survey boundary layer to generate list of Areasymbol values
                inputFolder = parameters[0].value.value
                surveyLayer = parameters[1].value
                queryList = list()
                surveyList = list()
                arcpy.env.workspace = inputFolder

                with arcpy.da.SearchCursor(surveyLayer, ["AREASYMBOL"]) as cursor: # pylint: disable=no-member
                    for row in cursor:
                        if not row[0].upper() in queryList:
                            queryList.append(row[0].upper())  # for uppercase match with folder names

                selCnt = len(queryList) # number of selected surveys in the map

                # get a list of all folders under the input folder, assuming 'soil_' naming convention
                folderList = arcpy.ListWorkspaces("soil_*", "Folder")

                # check each subfolder to make sure it is a valid SSURGO dataset
                # validation: has 'soil_' prefix and contains a spatial folder and a soilsmu_a shapefile
                # and matches one of the AREASYMBOL values in the legend table

                for subFolder in folderList:
                    shpAS = os.path.basename(subFolder)[5:].upper()  # uppercase match

                    if shpAS in queryList:
                        # this should be one of the target SSURGO dataset folder
                        # add it to the choice list
                        shpName = "soilmu_a_" + shpAS.lower() + ".shp"
                        shpPath = os.path.join( os.path.join( inputFolder, os.path.join( subFolder, "spatial")), shpName)

                        if arcpy.Exists(shpPath):
                            surveyList.append(os.path.basename(subFolder))

                            if len(surveyList) == selCnt:
                                # found all we need, stop looking
                                break

                if len(surveyList)  > 0:
                    parameters[2].filter.list = surveyList
                    parameters[2].values = surveyList

            if parameters[3].value:
                if not parameters[3].hasBeenValidated:
                    db = parameters[3].value.value
                    path = os.path.dirname(db)
                    dbName = os.path.basename(db)
                    fn, ext = os.path.splitext(dbName)

                    if ext == "":
                        ext = ".gdb"

                    elif ext != ".gdb":
                        ext = ".gdb"

                    dbName = fn + ext
                    db = os.path.join(path, dbName)
                    parameters[3].value = db
        except:
            pass
            # exc_type, exc_value, traceback = sys.exc_info()
            # tbinfo = traceback.format_tb(traceback)
            # theMsg = tbinfo + " \n" + str(exc_type)+ ": " + str(exc_value) + " \n"

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""

        try:
            _ = arcpy.mp.ArcGISProject("CURRENT")

        except:
            parameters[1].value = "ArcMap layers only"
            parameters[1].setErrorMessage("This ArcTool should only be run from ArcMap")
            return

        try:
            if parameters[0].value:
                if parameters[0].hasBeenValidated:

                    if parameters[1].value:
                        surveyLayer = parameters[1].value

                        if not parameters[1].hasBeenValidated:
                            if not parameters[2].filter.list:
                                parameters[0].setErrorMessage("No soil survey datasets matching the boundary layer were found under the " + parameters[0].value.value + " folder")

                            else:
                                # warn the user if the number of surveys selected in the input layer does not match the
                                # number in the choice list. This would mean that some SSURGO downloads are missing.
                                queryList = list()

                                with arcpy.da.SearchCursor(surveyLayer, ["AREASYMBOL"]) as cursor: # pylint: disable=no-member
                                    for row in cursor:
                                        if not row[0] in queryList:
                                            queryList.append(row[0])


                                # compare the number in the choice list with the queryList
                                if len(queryList) != len(parameters[2].filter.list):
                                    missingList = list()

                                    for f in queryList:
                                        folder = "soil_" + f.lower()

                                        if not folder in parameters[2].filter.list:
                                            missingList.append(f.upper())

                                    if len(missingList) == 1:
                                        parameters[2].setWarningMessage("One selected survey area has no matching dataset within the downloaded SSURGO (" + ", ".join(missingList)+ ")")

                                    else:
                                        parameters[2].setWarningMessage(str(len(missingList)) + " selected survey areas have no matching dataset within the downloaded SSURGO (" + ", ".join(missingList)+ ")")

            if parameters[3].value:
                # determine what type of output workspace is being specified
                outputWS = parameters[3].value.value

                if not outputWS.endswith('.gdb'):
                    parameters[3].setErrorMessage("Output workspace must be a file geodatabase (.gdb)")

                if (os.path.basename(outputWS).find(" ") >= 0):
                    parameters[3].setErrorMessage("Illegal geodatabase name (contains a space)")

                if (os.path.basename(outputWS).find("-") >= 0):
                    parameters[3].setErrorMessage("Illegal geodatabase name (contains a dash)")

                firstChar = os.path.basename(outputWS)[0:1]

                if firstChar in "1234567890":
                    parameters[3].setErrorMessage("Illegal geodatabase name begins with a number (" + str(firstChar) + ")")

                if os.path.dirname(outputWS).find("-") >= 0:
                    parameters[3].setErrorMessage("Illegal path contains a dash (-)")
        except:
            pass
            # exc_type, exc_value, traceback = sys.exc_info()
            # tbinfo = traceback.format_tb(traceback)
            # theMsg = tbinfo + " \n" + str(exc_type)+ ": " + str(exc_value) + " \n"
