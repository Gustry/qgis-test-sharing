
from qgis.PyQt.QtCore import (
    QCoreApplication,
    QVariant
)
from qgis.core import (
    QgsProcessing,
    QgsProcessingException,
    QgsProcessingAlgorithm,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterField,
    QgsField,
    QgsFeatureRequest,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsExpressionContextScope
)


class SetFeatureMainColor(QgsProcessingAlgorithm):
    """
    Try to determine the main symbol color of each feature
    And create a new mcolor field with it
    """

    INPUT_LAYER = 'INPUT_LAYER'
    SYMBOL_LEVEL = 'SYMBOL_LEVEL'
    COLOR_FIELD = 'COLOR_FIELD'
    VIRTUAL_COLOR_FIELD = 'VIRTUAL_COLOR_FIELD'
    LABEL_FIELD = 'LABEL_FIELD'
    VIRTUAL_LABEL_FIELD = 'VIRTUAL_LABEL_FIELD'
    OUTPUT = 'OUTPUT'

    layer = None
    symbol_level = None

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return SetFeatureMainColor()

    def name(self):
        return 'set_feature_main_colour'

    def displayName(self):
        return self.tr('Set color field value with feature symbol main colour')

    def group(self):
        return self.tr('Lizmap')

    def groupId(self):
        return 'lizmap'

    def shortHelpString(self):
        help_string = self.tr('''
        This algorithm tries to get each feature main colour by reading the symbol parameters.
        If a color has been found, the given color field will be updated with this colour.
        ''')
        return help_string

    def initAlgorithm(self, config=None):

        # We add the input vector features source. It can have any kind of
        # geometry.
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_LAYER,
                self.tr('Input layer'),
                [QgsProcessing.TypeVectorAnyGeometry]
            )
        )
        # Symbol level
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SYMBOL_LEVEL,
                self.tr('Symbol level number. If -1 given, try QGIS best guess'),
                minValue=-1,
                maxValue=5,
                defaultValue=0,
                optional=False
            )
        )
        # Color fields
        self.addParameter(
            QgsProcessingParameterField(
                self.COLOR_FIELD,
                self.tr('Color field - Choose the field to update'),
                type=1,
                optional=True,
                parentLayerParameterName=self.INPUT_LAYER
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.VIRTUAL_COLOR_FIELD,
                self.tr('Virtual color field name - Give any to create a virtual field and not update an existing one'),
                defaultValue='',
                optional=True
            )
        )

        # Label fields
        self.addParameter(
            QgsProcessingParameterField(
                self.LABEL_FIELD,
                self.tr('Label field - Choose the field to update'),
                type=1,
                optional=True,
                parentLayerParameterName=self.INPUT_LAYER
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.VIRTUAL_LABEL_FIELD,
                self.tr('Virtual label field name - Give any to create a virtual field and not update an existing one'),
                defaultValue='',
                optional=True
            )
        )

    def checkParameterValues(self, parameters, context):

        # Check that one color field has been given
        color_field = parameters[self.COLOR_FIELD]
        virtual_color_field = parameters[self.VIRTUAL_COLOR_FIELD]
        if (not color_field and not virtual_color_field) or (color_field and virtual_color_field):
            return False, self.tr('Color : you need to choose between an existing field to edit OR the name of the virtual field to create')

        # Check that one label field has been given
        label_field = parameters[self.LABEL_FIELD]
        virtual_label_field = parameters[self.VIRTUAL_LABEL_FIELD]
        if (not label_field and not virtual_label_field) and (label_field and virtual_label_field):
            return False, self.tr('Label : you need to choose between an existing field to edit OR the name of the virtual field to create')

        return super(SetFeatureMainColor, self).checkParameterValues(parameters, context)

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """

        # Get input vector layer
        vlayer = self.parameterAsVectorLayer(
            parameters,
            self.INPUT_LAYER,
            context
        )
        self.layer = vlayer
        symbol_level = parameters[self.SYMBOL_LEVEL]
        self.symbol_level = symbol_level

        color_field = parameters[self.COLOR_FIELD]
        virtual_color_field = parameters[self.VIRTUAL_COLOR_FIELD]
        label_field = parameters[self.LABEL_FIELD]
        virtual_label_field = parameters[self.VIRTUAL_LABEL_FIELD]

        # Send some information to the user
        feedback.pushInfo('Layer is {}'.format(vlayer.name()))

        # Compute symbol based expressions
        color_expression = self.getColorExpressionFromSymbology()
        label_expression = self.getLabelExpressionFromSymbology()

        if not color_expression or not label_expression:
            raise QgsProcessingException(self.tr('Color expression or label expression cannot be generated'))

        # Modify features
        # Start an undo block
        if color_field and label_field:

            # Compute the number of steps to display within the progress bar and
            # get features from source
            total = 100.0 / vlayer.featureCount() if vlayer.featureCount() else 0

            # prepare expression
            exp_context = QgsExpressionContext()
            exp_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(vlayer))

            # color_expression = "concat('hop ', pcolor)"
            color_exp = QgsExpression(color_expression)

            color_idx = vlayer.fields().indexFromName(color_field)
            label_exp = QgsExpression(label_expression)
            label_idx = vlayer.fields().indexFromName(label_field)

            vlayer.beginEditCommand('Translating all features')
            features = vlayer.getFeatures(QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry))
            # .setSubsetOfAttributes([color_idx, label_idx]) )
            for current, feature in enumerate(features):
                # Stop the algorithm if cancel button has been clicked
                if feedback.isCanceled():
                    break

                # Edit feature
                exp_context.setFeature(feature)

                # color
                color_val = color_exp.evaluate(exp_context)
                print(color_val)
                vlayer.changeAttributeValue(
                    feature.id(),
                    color_idx,
                    color_val
                )

                # label
                label_val = label_exp.evaluate(exp_context)
                print(label_val)
                vlayer.changeAttributeValue(
                    feature.id(),
                    label_idx,
                    label_val
                )

                # Update the progress bar
                feedback.setProgress(int(current * total))

        if virtual_color_field:
            self.createOrUpdateLayerExpressionField(
                virtual_color_field,
                color_expression
            )
        if virtual_label_field:
            self.createOrUpdateLayerExpressionField(
                virtual_label_field,
                label_expression
            )

        # End the undo block
        vlayer.endEditCommand()

        return {self.OUTPUT: 'ok'}

    def getLayerLegendConfig(self):
        config = []
        renderer = self.layer.renderer()
        type = renderer.type()
        if type == 'singleSymbol':
            print(self.layer.name())
            color = self.getSymbolMainColor(renderer.symbol())
            item = {
                'label': self.layer.name(),
                'expression': 'True',
                'color': color
            }
            config.append(item)
        elif type == 'categorizedSymbol':
            for a in renderer.categories():
                print(a.label())
                color = self.getSymbolMainColor(a.symbol())
                item = {
                    'label': a.label(),
                    'expression': "{} = '{}'".format(
                        renderer.classAttribute(),
                        a.value().replace("'", "\\'")
                    ),
                    'color': color
                }
                config.append(item)
        elif type == 'graduatedSymbol':
            for a in renderer.ranges():
                print(a.label())
                color = self.getSymbolMainColor(a.symbol())
                item = {
                    'label': a.label(),
                    'expression': '{0} <= ( {1} ) AND ( {1} ) < {2}'.format(
                        a.lowerValue(),
                        renderer.classAttribute(),
                        a.upperValue()
                    ),
                    'color': color
                }
                config.append(item)
        elif type == 'RuleRenderer':
            for a in renderer.rootRule().descendants():
                print(a.label())
                color = self.getSymbolMainColor(a.symbol())
                item = {
                    'label': a.label(),
                    'expression': a.filterExpression(),
                    'color': color
                }
                config.append(item)
        return config

    def getSymbolMainColor(self, symbol):
        '''
        Guess main symbol color
        '''
        color = None
        symbol_layers = symbol.symbolLayers()
        if self.symbol_level > -1 and self.symbol_level <= len(symbol_layers) - 1:
            print(
                self.tr('Get main color from the symbol layer') + ' %s' % self.symbol_level
            )
            # Try to find better color (not easy)
            prop = symbol_layers[self.symbol_level].properties()
            # print(prop)
            if 'style' in prop:
                if prop['style'] == 'no':
                    color = prop['outline_color']
                if prop['style'] == 'solid':
                    color = prop['color']
            if 'rampType' in prop:
                stops = prop['stops']
                lstops = stops.split(':')
                idx = int(len(lstops) / 2)
                color = lstops[idx].split(';')[1]
            if not color and 'color' in prop:
                color = prop['color']

        if not color:
            print(self.tr('Get main color from QGIS internal method (best guess)'))
            # Main color given by QGIS (not always good)
            qcolor = symbol.color()
            color = "{},{},{}".format(qcolor.red(), qcolor.green(), qcolor.blue())

        # Get color list
        rgb = color.split(',')[0:3]

        # Get opacity
        opacity = symbol.opacity() * self.layer.opacity() * 255
        a = rgb + [str(int(opacity))]

        main_color = ','.join(a)

        return main_color

    def createOrUpdateLayerExpressionField(self, field_name, field_expression):
        field_index = self.layer.fields().indexFromName(field_name)
        if field_index >= 0:
            self.layer.updateExpressionField(field_index, field_expression)
        else:
            field = QgsField(field_name, QVariant.String)
            field_index = self.layer.addExpressionField(field_expression, field)

    def getColorExpressionFromSymbology(self):
        # Get symbology items config
        items = self.getLayerLegendConfig()
        exp = None
        expression = ' CASE '
        for item in items:
            expression += " WHEN {} THEN 'rgba({})'".format(
                item['expression'],
                item['color']
            )
        expression += " ELSE 'rgba(255,255,255,0.0)'"
        expression += ' END'
        if expression:
            exp = expression
        return exp

    def getLabelExpressionFromSymbology(self):
        # Get symbology items config
        items = self.getLayerLegendConfig()
        exp = None
        expression = ' CASE '
        for item in items:
            expression += " WHEN {} THEN '{}'".format(
                item['expression'],
                item['label'].replace("'", "\\'")
            )
        expression += " ELSE NULL"
        expression += ' END'
        if expression:
            exp = expression
        return exp