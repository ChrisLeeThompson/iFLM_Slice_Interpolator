import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

GroupBox {

    property alias imageFilterMethodCurrentIndex: imageFilterMethodComboBox.currentIndex
    property alias gaussianBackgroundSigmaValue: gaussianBackgroundSigmaSB.realValue
    property alias globalBackgroundNormalizationChecked: globalBackgroundNormalizationCheckBox.checked

    id: root

    Layout.fillWidth: true

    title: qsTr("Background Subtraction")

    background: Rectangle {
        id: mainRectangle
        implicitHeight: mainColumnLayout.implicitHeight
        color: AppConfig.groupBoxColor
        radius: AppConfig.groupBoxRadius
    }
    focusPolicy: Qt.StrongFocus

    contentItem: Item {

        // Item has no implicit size of its own - without these the GroupBox
        // reserves less room than the column needs and rows get compressed
        implicitWidth: mainColumnLayout.implicitWidth
        implicitHeight: mainColumnLayout.implicitHeight

        ColumnLayout {

            id: mainColumnLayout
            anchors.fill: parent
            spacing: 10

            RowLayout {

                Layout.fillWidth: true
                spacing: 20

                Label {

                    id: imageFilterMethodComboBoxLabel
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignLeft
                    text: qsTr("Method")

                }

                ComboBox {

                    id: imageFilterMethodComboBox
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignRight
                    model: image_filter_methods
                    currentIndex: 0

                }

            }

            // Page 0: Minimum value background subtraction
            RowLayout {

                id: minValueRowLayout
                Layout.fillWidth: true
                Layout.topMargin: AppConfig.rowLayoutTopMargin
                Layout.preferredHeight: gaussianBackgroundRowLayout.height
                visible: imageFilterMethodComboBox.currentIndex === 0

                Label {

                    id: minValueFilterLabel
                    Layout.fillWidth: true
                    text: qsTr("No adjustable parameters")

                }

            }

            // Pages 1 and 2: Gaussian and Rolling background share the one
            // scale spinbox — the label, tooltip, and meaning follow the
            // selected method (sigma for Gaussian, radius for Rolling).
            RowLayout {

                id: gaussianBackgroundRowLayout
                Layout.fillWidth: true
                Layout.topMargin: AppConfig.rowLayoutTopMargin
                visible: imageFilterMethodComboBox.currentIndex >= 1

                Label {

                    property bool _rolling: imageFilterMethodComboBox.currentIndex === 2
                    property string _toolTipText: _rolling ? AppConfig.rollingFilterLabelToolTip
                                                           : AppConfig.gaussianFilterLabelToolTip

                    id: gaussianFilterLabel
                    Layout.fillWidth: true
                    text: _rolling ? qsTr("Background Radius") : qsTr("Gaussian Sigma")
                    ToolTip.text: _toolTipText
                    ToolTip.delay: AppConfig.toolTipDelay
                    ToolTip.timeout: AppConfig.toolTipTimeout
                    ToolTip.visible: _toolTipText ? gaussianFilterLabelMA.containsMouse : false
                    MouseArea {
                        id: gaussianFilterLabelMA
                        anchors.fill: parent
                        hoverEnabled: true
                    }

                }

                SpinBoxDouble {

                    id: gaussianBackgroundSigmaSB
                    Layout.alignment: Qt.AlignRight
                    decimals: 0
                    realValue: 50
                    realFrom: 1
                    realTo: 500
                    realStepSize: 1

                }

            }

            RowLayout {

                Label {

                    property string _toolTipText: AppConfig.globalBackgroundNormalizationLabelToolTip

                    id: globalBackgroundNormalizationLabel
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignLeft
                    text: qsTr("Global Background Normalization")
                    ToolTip.text: _toolTipText
                    ToolTip.delay: AppConfig.toolTipDelay
                    ToolTip.timeout: AppConfig.toolTipTimeout
                    ToolTip.visible: _toolTipText ? globalBackgroundNormalizationLabelMA.containsMouse : false
                    MouseArea {
                        id: globalBackgroundNormalizationLabelMA
                        anchors.fill: parent
                        hoverEnabled: true
                    }

                }

                CheckBox {

                    id: globalBackgroundNormalizationCheckBox
                    Layout.alignment: Qt.AlignRight

                }

            }

        }

    }

}
