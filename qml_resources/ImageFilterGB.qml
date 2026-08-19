import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

GroupBox {

    property alias hotPixelFilterChecked: hotPixelFilterCheckBox.checked
    property alias hotPixelSensitivityValue: hotPixelSensitivitySB.realValue
    property alias unsharpKernelSize: unsharpKernelComboBox.kernelSize
    property alias unsharpValue: unsharpSB.realValue
    property alias unsharpGaussianSigmaValue: unsharpGaussianSigmaSB.realValue

    id: root

    Layout.fillWidth: true

    title: qsTr("Image Filter Settings")

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

                Label {

                    property string _toolTipText: AppConfig.hotPixelFilterLabelToolTip

                    id: hotPixelFilterLabel
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignLeft
                    text: qsTr("Hot Pixel Filter")
                    ToolTip.text: _toolTipText
                    ToolTip.delay: AppConfig.toolTipDelay
                    ToolTip.timeout: AppConfig.toolTipTimeout
                    ToolTip.visible: _toolTipText ? hotPixelFilterLabelMA.containsMouse : false
                    MouseArea {
                        id: hotPixelFilterLabelMA
                        anchors.fill: parent
                        hoverEnabled: true
                    }

                }

                CheckBox {

                    id: hotPixelFilterCheckBox
                    Layout.alignment: Qt.AlignRight

                }

            }

            RowLayout {

                // Greyed out rather than hidden: hiding reflows the whole group
                // box on every toggle.  Item.enabled propagates to children, so
                // this one binding greys the label and the spin box together.
                enabled: hotPixelFilterCheckBox.checked

                Label {

                    property string _toolTipText: AppConfig.hotPixelSensitivityLabelToolTip

                    id: hotPixelSensitivityLabel
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignLeft
                    text: qsTr("Hot Pixel Sensitivity")
                    ToolTip.text: _toolTipText
                    ToolTip.delay: AppConfig.toolTipDelay
                    ToolTip.timeout: AppConfig.toolTipTimeout
                    ToolTip.visible: _toolTipText ? hotPixelSensitivityLabelMA.containsMouse : false
                    MouseArea {
                        id: hotPixelSensitivityLabelMA
                        anchors.fill: parent
                        hoverEnabled: true
                    }

                }

                SpinBoxDouble {

                    // decimals: 0 on purpose.  On integer image data the local
                    // scale is only a few ADU, so half-sigma steps would land
                    // below the quantization step and one step in two would be
                    // a literal no-op.
                    id: hotPixelSensitivitySB
                    Layout.alignment: Qt.AlignRight
                    decimals: 0
                    realValue: 6
                    realFrom: 2
                    realTo: 15
                    realStepSize: 1

                }

            }

            RowLayout {

                Layout.topMargin: AppConfig.rowLayoutTopMargin

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

                    id: unsharpGaussianSigmaLabel
                    Layout.alignment: Qt.AlignLeft
                    Layout.fillWidth: true
                    text: qsTr("Unsharp Gaussian Sigma")
                    ToolTip.text: _toolTipText
                    ToolTip.delay: AppConfig.toolTipDelay
                    ToolTip.timeout: AppConfig.toolTipTimeout
                    ToolTip.visible: _toolTipText ? unsharpGaussianSigmaLabelMA.containsMouse : false
                    MouseArea {
                        id: unsharpGaussianSigmaLabelMA
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
