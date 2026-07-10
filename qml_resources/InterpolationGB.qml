import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

GroupBox {

    property alias interpolationMethodCurrentIndex: interpolationMethodComboBox.currentIndex
    property alias interpolationFactorValue: interpolationFactorSB.realValue

    id: root

    Layout.fillWidth: true

    title: qsTr("Interpolation Settings")

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

                    id: interpolationMethodComboBoxLabel
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignLeft
                    text: qsTr("Method")

                }

                ComboBox {

                    id: interpolationMethodComboBox
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignRight
                    model: interpolation_methods
                    currentIndex: 0

                }

            }

            RowLayout {

                Layout.fillWidth: true
                Layout.topMargin: AppConfig.rowLayoutTopMargin

                Label {

                    id: interpolationMethodLabel
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignLeft
                    text: interpolationMethodComboBox.currentText

                }

                Label {

                    id: interpolationMethodDescriptionLabel
                    Layout.alignment: Qt.AlignRight
                    // Descriptions come from the Python method registry, so a new
                    // method added there shows up here without touching the QML
                    text: (interpolationMethodComboBox.currentIndex >= 0 &&
                           interpolationMethodComboBox.currentIndex < interpolation_method_descriptions.length)
                          ? interpolation_method_descriptions[interpolationMethodComboBox.currentIndex]
                          : ""

                }

            }

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 10
            }

            RowLayout {

                Layout.fillWidth: true

                Label {

                    id: interpolationFactorLabel
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignLeft
                    text: qsTr("Interpolation Factor")

                }

                SpinBoxDouble {

                    id: interpolationFactorSB
                    Layout.alignment: Qt.AlignRight
                    decimals: 0
                    realValue: 2
                    realFrom: 2
                    realTo: 4
                    realStepSize: 2
                    editable: false

                }

            }

        }

    }

}
