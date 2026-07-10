import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

GroupBox {

    id: root

    Layout.fillWidth: true

    title: qsTr("Image Stack Origin")

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

                TextField {

                    id: directoryPathTextField
                    Layout.fillWidth: true
                    placeholderText: qsTr("iFLM TFS File Path")
                    text: main_operator_backend.tfs_file_path_property
                    selectByMouse: true
                    readOnly: true
                    Keys.onPressed: event => {
                                        if (event.key === Qt.Key_Enter) { directoryPathTextField.focus = false }
                                        if (event.key === Qt.Key_Return) { directoryPathTextField.focus = false }
                                    }
                }

                Item {
                    Layout.fillWidth: true
                }

                Button {

                    id: directoryBrowseButton
                    Layout.alignment: Qt.AlignRight
                    text: qsTr("Browse")
                    enabled: !main_operator_backend.processing_running_property
                    onClicked: {
                        directoryPathTextField.placeholderText = qsTr("Loading path...")
                        pathDialog.open()
                    }

                }

            }

        }

    }

    FileDialog {

        id: pathDialog
        acceptLabel: qsTr("Select")
        nameFilters: ["TFS XML File (*.tfs.xml)", "XML files (*.xml)", "All files (*)"]
        onAccepted: {
            // Pass the URL string as-is - the Python side converts it with
            // QUrl.toLocalFile(), which handles percent-encoding and UNC
            // shares correctly (hand-stripping the file:// prefix does not)
            main_operator_backend.set_tfs_file_path(selectedFile.toString())
            // Update TextField
            directoryPathTextField.placeholderText = "iFLM TFS File Path"
        }
        onRejected: {
            directoryPathTextField.placeholderText = "iFLM TFS File Path"
        }

    }

}
