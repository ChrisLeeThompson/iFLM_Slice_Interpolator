import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

GroupBox {

    property alias statusText: statusLabel.text
    property alias catbugIconSource: catbugIcon.source
    property alias progressBarValue: progressBar.value
    property alias progressBarFrom: progressBar.from
    property alias progressBarTo: progressBar.to
    property alias progressBarVisible: progressBar.visible

    id: root

    Layout.fillWidth: true

    title: qsTr("Status")

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

                    id: statusLabel
                    Layout.fillWidth: true
                    // Keep the full text width out of the layout's implicit width:
                    // otherwise a long status/error message would grow the window's
                    // minimumWidth instead of eliding
                    Layout.preferredWidth: 0
                    text: ""
                    elide: Text.ElideRight

                }

                Item {
                    Layout.fillWidth: true
                }

                Image {

                    id: catbugIcon
                    Layout.alignment: Qt.AlignVCenter
                    source: "../script_assets/catbug_grayscale_2.png"
                    fillMode: Image.PreserveAspectFit
                    sourceSize.height: statusLabel.height + 50
                    antialiasing: true

                    DropArea {

                        id: catbugDropArea
                        anchors.fill: parent
                        onEntered: (drag) => {
                                       // Quick extension check for drag feedback; the
                                       // Python side does the real validation on drop
                                       var url_string = drag.urls.length > 0 ? drag.urls[0].toString() : ""
                                       if (url_string.toLowerCase().endsWith(".xml")) {
                                           drag.accept(Qt.CopyAction)
                                           // Change to color icon
                                           catbugIcon.source = "../script_assets/catbug_color_2.png"
                                       } else {
                                           drag.accept(Qt.IgnoreAction)
                                       }
                                   }
                        onDropped: (drop) => {
                                       // Pass the URL string as-is - the Python side
                                       // converts it with QUrl.toLocalFile(), which handles
                                       // percent-encoding and UNC shares correctly
                                       var url_string = drop.urls.length > 0 ? drop.urls[0].toString() : ""
                                       main_operator_backend.set_tfs_file_path(url_string)
                                       updateCatbugIcon()
                                   }
                        onExited: {
                            updateCatbugIcon()
                        }
                    }

                }

            }

            RowLayout {

                Layout.fillWidth: true

                ProgressBar {

                    id: progressBar
                    Layout.fillWidth: true

                }

            }

        }

    }

    // React to backend state changes
    Connections {
        target: main_operator_backend

        function onTfs_file_path_valid_signal() {
            updateCatbugIcon()
        }

        function onProcessing_running_signal() {
            updateCatbugIcon()
        }
    }

    // Centralized icon update logic
    function updateCatbugIcon() {
        // Color if: processing is running
        // Grayscale if: not processing
        if (main_operator_backend.processing_running_property) {
            catbugIcon.source = "../script_assets/catbug_color_2.png"
        } else {
            catbugIcon.source = "../script_assets/catbug_grayscale_2.png"
        }
    }

}
