import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

GroupBox {

    property alias imageFilterMethodCurrentIndex: imageFilterMethodComboBox.currentIndex
    property alias gaussianBackgroundSigmaValue: gaussianBackgroundSigmaSB.realValue
    property alias globalBackgroundNormalizationChecked: globalBackgroundNormalizationCheckBox.checked
    property alias unsharpKernelSize: unsharpKernelComboBox.kernelSize
    property alias unsharpValue: unsharpSB.realValue
    property alias unsharpGaussianSigmaValue: unsharpGaussianSigmaSB.realValue

    id: root

    Layout.fillWidth: true

    title: qsTr("Background Subtraction Settings")

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

            // Page 0: Minimum value background substraction
            RowLayout {

                id: minValueRowLayout
                Layout.fillWidth: true
                Layout.topMargin: AppConfig.rowLayoutTopMargin
                Layout.preferredHeight: gaussianBackgroundRowLayout.height
                visible: imageFilterMethodComboBox.currentIndex === 0

                Label {

                    id: minValueFilterLabel
                    Layout.fillWidth: true
                    text: qsTr("Auto parameters")

                }

            }

            // Page 1: Guassian background
            RowLayout {

                id: gaussianBackgroundRowLayout
                Layout.fillWidth: true
                Layout.topMargin: AppConfig.rowLayoutTopMargin
                visible: imageFilterMethodComboBox.currentIndex === 1

                Label {

                    property string _toolTipText: AppConfig.gaussianFilterLabelToolTip

                    id: gaussianFilterLabel
                    Layout.fillWidth: true
                    text: qsTr("Gaussian Sigma")
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
                    realTo: 100
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

            RowLayout {

                Label {

                    property string _toolTipText: AppConfig.unsharpKernelSizeToolTip

                    id: unsharpKernelLabel
                    Layout.alignment: Qt.AlignLeft
                    Layout.fillWidth: true
                    text: qsTr("Unsharp Kernel Size")
                    ToolTip.text: _toolTipText
                    ToolTip.delay: AppConfig.toolTipDelay
                    ToolTip.timeout: AppConfig.toolTipTimeout
                    ToolTip.visible: _toolTipText ? unsharpKernelLabelMA.containsMouse : false
                    MouseArea {
                        id: unsharpKernelLabelMA
                        anchors.fill: parent
                        hoverEnabled: true
                    }

                }

                ComboBox {

                    // No 1×1 option: a 1×1 Gaussian blur is the identity, which
                    // makes the unsharp mask zero and silently disables sharpening
                    property int kernelSize: [0, 3, 5, 7, 9, 11][currentIndex]

                    id: unsharpKernelComboBox
                    Layout.alignment: Qt.AlignRight
                    Layout.preferredWidth: unsharpGaussianSigmaSB.width
                    model: ["0 (auto)", "3×3", "5×5", "7×7", "9×9", "11×11"]
                    currentIndex: 1

                }

            }

            RowLayout {

                Label {

                    property string _toolTipText: AppConfig.unsharpLabelToolTip

                    id: unsharpLabel
                    Layout.alignment: Qt.AlignLeft
                    Layout.fillWidth: true
                    text: qsTr("Unsharp Amount")
                    ToolTip.text: _toolTipText
                    ToolTip.delay: AppConfig.toolTipDelay
                    ToolTip.timeout: AppConfig.toolTipTimeout
                    ToolTip.visible: _toolTipText ? unsharpLabelMA.containsMouse : false
                    MouseArea {
                        id: unsharpLabelMA
                        anchors.fill: parent
                        hoverEnabled: true
                    }

                }

                SpinBoxDouble {

                    id: unsharpSB
                    Layout.alignment: Qt.AlignRight
                    decimals: 1
                    realValue: 7.0
                    realFrom: 0.0
                    realTo: 50.0
                    realStepSize: 0.1

                }

            }

            RowLayout {

                Label {

                    property string _toolTipText: AppConfig.unsharpGaussianSigmaLabelToolTip

                    id: unsharpGuassianSigmaLabel
                    Layout.alignment: Qt.AlignLeft
                    Layout.fillWidth: true
                    text: qsTr("Unsharp Gaussian Sigma")
                    ToolTip.text: _toolTipText
                    ToolTip.delay: AppConfig.toolTipDelay
                    ToolTip.timeout: AppConfig.toolTipTimeout
                    ToolTip.visible: _toolTipText ? unsharpGuassianSigmaLabelMA.containsMouse : false
                    MouseArea {
                        id: unsharpGuassianSigmaLabelMA
                        anchors.fill: parent
                        hoverEnabled: true
                    }

                }

                SpinBoxDouble {

                    id: unsharpGaussianSigmaSB
                    Layout.alignment: Qt.AlignRight
                    decimals: 1
                    realValue: 0.5
                    realFrom: 0.1
                    realTo: 50.0
                    realStepSize: 0.1

                }

            }

        }

    }

}
