from gssurgo.core.pyttool import PYTTool
import gssurgo.SSURGO_gSSURGO_byState

class CreategSSURGOByState(PYTTool):

    def execute(self, parameters, messages):
        """Extract the data."""

        params = self.get_param_val_dict(parameters)
        inputFolder = params['inputFolder']
        outputFolder = params['outputFolder']
        theTileValues = list(params['theTileValues'])
        bOverwriteOutput = params['bOverwriteOutput']
        bRequired = params['bRequired']
        useTextFiles = params['useTextFiles']
        aoiLayer = params['aoiLayer']
        aoiField = params['aoiField']

        gssurgo.SSURGO_gSSURGO_byState.create_gssurgo(inputFolder, outputFolder, theTileValues, bOverwriteOutput, bRequired, useTextFiles, aoiLayer, aoiField)
    
    def init_parameter_info(self):
        """Set the parameters for the tool."""

        states = ['Alabama','Alaska','Arizona','Arkansas',
            'California','Colorado','Connecticut','Delaware','District of Columbia',
            'Florida','Georgia','Hawaii','Idaho','Illinois','Indiana','Iowa','Kansas',
            'Kentucky','Louisiana','Maine','Maryland','Massachusetts','Michigan',
            'Minnesota','Mississippi','Missouri','Montana','Nebraska','Nevada',
            'New Hampshire','New Jersey','New Mexico','New York','North Carolina',
            'North Dakota','Ohio','Oklahoma','Oregon','Pennsylvania',
            'Puerto Rico and U.S. Virgin Islands','Rhode Island','South Carolina','South Dakota','Tennessee',
            'Texas','Utah','Vermont','Virginia','Washington','West Virginia','Wisconsin','Wyoming',
            'American Samoa', 'Federated States of Micronesia', 'Guam', 'Marshall Islands', 'Northern Mariana Islands', 'Palau']

        self.add_param('inputFolder', 'SSURGO Downloads', datatype='DEFolder')
        self.add_param('outputFolder', 'Output Folder', datatype='DEFolder')
        self.add_param('theTileValues', 'States', datatype='GPString', valueList=states, multiValue=True)
        self.add_param('bOverwriteOutput', 'Overwrite output', datatype='GPBoolean', defaultValue=True)
        self.add_param('bRequired', 'Require All Data', datatype='GPBoolean', defaultValue=True)
        self.add_param('useTextFiles', 'Use Text Files', datatype='GPBoolean', defaultValue=True)
        self.add_param('aoiLayer', 'State Boundary Layer', datatype='GPFeatureLayer', parameterType='Optional')
        self.add_param('aoiField', 'State Name Column', datatype='Field', parameterType='Optional')
