import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import QtQuick.Controls
import "."

ApplicationWindow {

	id: app_window
	minimumWidth: mainColumnLayout.implicitWidth + 100
	height: mainColumnLayout.implicitHeight
	title: AppConfig.mainWindowTitle + " " + app_version
	color: AppConfig.mainWindowBackgroundColor
	visible: true

	ScrollView {

		id: mainScrollView
		anchors.fill: parent

		// Show scrollbars when needed
		ScrollBar.vertical.policy: contentHeight > height ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
		// Clip content to viewport
		clip: true

		ColumnLayout {

			id: mainColumnLayout

			width: mainScrollView.availableWidth
			spacing: AppConfig.columnLayoutSpacing

			RowLayout {

				Layout.topMargin: AppConfig.rowLayoutTopMargin
				Layout.leftMargin: AppConfig.rowLayoutLeftMargin
				Layout.rightMargin: AppConfig.rowLayoutRightMargin

				ImageStackOriginGB {

					id: imageStackOriginGB

				}

			}

			RowLayout {

				Layout.leftMargin: AppConfig.rowLayoutLeftMargin
				Layout.rightMargin: AppConfig.rowLayoutRightMargin

				ImageFilterGB {

					id: imageFilterGB

					onImageFilterMethodCurrentIndexChanged: {
						main_operator_backend._set_image_filter_method_index(imageFilterMethodCurrentIndex)
					}
					onGaussianBackgroundSigmaValueChanged: {
						main_operator_backend._set_gaussian_background_sigma(gaussianBackgroundSigmaValue)
					}
					onGlobalBackgroundNormalizationCheckedChanged: {
						main_operator_backend._set_global_background_normalization(globalBackgroundNormalizationChecked)
					}
					onUnsharpKernelSizeChanged: {
						main_operator_backend._set_unsharp_kernel_size(unsharpKernelSize)
					}
					onUnsharpValueChanged: {
						main_operator_backend._set_unsharp_amount(unsharpValue)
					}
					onUnsharpGaussianSigmaValueChanged: {
						main_operator_backend._set_unsharp_gaussian_sigma(unsharpGaussianSigmaValue)
					}

					// Send initial parameters to Python
					Component.onCompleted: {
						main_operator_backend._set_image_filter_method_index(imageFilterMethodCurrentIndex)
						main_operator_backend._set_gaussian_background_sigma(gaussianBackgroundSigmaValue)
						main_operator_backend._set_global_background_normalization(globalBackgroundNormalizationChecked)
						main_operator_backend._set_unsharp_kernel_size(unsharpKernelSize)
						main_operator_backend._set_unsharp_amount(unsharpValue)
						main_operator_backend._set_unsharp_gaussian_sigma(unsharpGaussianSigmaValue)
					}

				}

			}

			RowLayout {

				Layout.leftMargin: AppConfig.rowLayoutLeftMargin
				Layout.rightMargin: AppConfig.rowLayoutRightMargin

				InterpolationGB {

					id: interpolationGB

					onInterpolationMethodCurrentIndexChanged: {
						main_operator_backend._set_interpolation_method_index(interpolationMethodCurrentIndex)
					}
					onInterpolationFactorValueChanged: {
						main_operator_backend._set_interpolation_factor(interpolationFactorValue)
					}

					// Send initial parameters to Python
					Component.onCompleted: {
						main_operator_backend._set_interpolation_method_index(interpolationMethodCurrentIndex)
						main_operator_backend._set_interpolation_factor(interpolationFactorValue)
					}

				}

			}

			RowLayout {

				// Layout.bottomMargin: AppConfig.rowLayoutBottomMargin
				Layout.leftMargin: AppConfig.rowLayoutLeftMargin
				Layout.rightMargin: AppConfig.rowLayoutRightMargin

				StatusGB {

					id: statusGB
					statusText: main_operator_backend.operator_to_statusGB_property
					// Catbug icon state is managed inside StatusGB (updateCatbugIcon):
					// binding it here as well would be silently broken by the first
					// imperative assignment during drag-and-drop
					progressBarValue: main_operator_backend.operator_to_progressBar_value_property
					progressBarVisible: main_operator_backend.operator_to_progressBar_visible_property
					progressBarFrom: 0
					progressBarTo: 100

				}

			}

			RowLayout {

				// Layout.topMargin: AppConfig.rowLayoutTopMargin
				Layout.leftMargin: AppConfig.rowLayoutLeftMargin
				Layout.rightMargin: AppConfig.rowLayoutRightMargin
				Layout.bottomMargin: AppConfig.rowLayoutBottomMargin
				spacing: 8

				Button {

					property string _toolTipText: AppConfig.deleteDataButtonToolTip

					id: deleteDataButton
					Layout.alignment: Qt.AlignLeft
					text: qsTr("Delete Data")
					enabled: main_operator_backend.processed_data_exists_property && !main_operator_backend.processing_running_property
					ToolTip.text: _toolTipText
					ToolTip.delay: AppConfig.toolTipDelay
					ToolTip.timeout: AppConfig.toolTipTimeout
					ToolTip.visible: _toolTipText ? deleteDataButton.hovered : false
					onClicked: {
						deleteConfirmDialog.open()
					}

				}

				Item {
					Layout.fillWidth: true
				}

				Button {

					id: startButton
					text: qsTr("Start")
					enabled: main_operator_backend.tfs_file_valid_property && !main_operator_backend.processing_running_property
					onClicked: {
						main_operator_backend.start_processing()
					}

				}

				Button {

					id: stopButton
					text: qsTr("Stop")
					enabled: main_operator_backend.processing_running_property
					onClicked: {
						main_operator_backend.stop_processing()
					}

				}

			}

		}

	}

	// Confirmation before recursively deleting processed output
	Dialog {

		id: deleteConfirmDialog
		title: qsTr("Delete processed data?")
		modal: true
		parent: Overlay.overlay
		anchors.centerIn: parent
		standardButtons: Dialog.Yes | Dialog.No

		onAccepted: {
			main_operator_backend.delete_processed_data()
		}

		Label {
			text: qsTr("This will permanently delete the processed_images directory\nand the interpolated TFS file next to the selected TFS file.")
		}

	}

}
