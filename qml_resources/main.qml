import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import QtQuick.Controls
import "."

ApplicationWindow {

	id: app_window
	title: AppConfig.mainWindowTitle + " " + app_version
	color: AppConfig.mainWindowBackgroundColor
	visible: true

	// The input group box, status box, and button row are pinned outside the
	// ScrollView, so the minimum height keeps all of them visible plus a
	// slice of the scrollable settings area.
	Component.onCompleted: {
		var naturalHeight = outerColumnLayout.implicitHeight
		var pinnedHeight  = naturalHeight - mainScrollView.implicitHeight
		minimumWidth  = outerColumnLayout.implicitWidth + 140
		minimumHeight = Math.min(pinnedHeight + 120, naturalHeight)
		height        = Math.min(naturalHeight,
		                         Screen.desktopAvailableHeight - 48)
		maximumHeight = naturalHeight
		y = Screen.desktopAvailableHeight - height
	}

	ColumnLayout {

		id: outerColumnLayout

		anchors.fill: parent
		spacing: AppConfig.columnLayoutSpacing

		// Pinned top: the input group box stays visible at any window height
		RowLayout {

			Layout.fillWidth: true
			Layout.topMargin: AppConfig.rowLayoutTopMargin
			Layout.leftMargin: AppConfig.rowLayoutLeftMargin
			Layout.rightMargin: AppConfig.rowLayoutRightMargin

			ImageStackOriginGB {

				id: imageStackOriginGB

				Layout.fillWidth: true

			}

		}

		// Scrollable middle: the settings group boxes
		ScrollView {

			id: mainScrollView
			Layout.fillWidth: true
			Layout.fillHeight: true

			ScrollBar.vertical.policy: contentHeight > height ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
			clip: true

			ColumnLayout {

				id: scrollColumnLayout

				width: mainScrollView.availableWidth
				spacing: AppConfig.columnLayoutSpacing

				RowLayout {

					Layout.fillWidth: true
					Layout.leftMargin: AppConfig.rowLayoutLeftMargin
					Layout.rightMargin: AppConfig.rowLayoutRightMargin

					BackgroundSubtractionGB {

						id: backgroundSubtractionGB

						Layout.fillWidth: true

						onImageFilterMethodCurrentIndexChanged: {
							main_operator_backend._set_image_filter_method_index(imageFilterMethodCurrentIndex)
						}
						onGaussianBackgroundSigmaValueChanged: {
							main_operator_backend._set_gaussian_background_sigma(gaussianBackgroundSigmaValue)
						}
						onGlobalBackgroundNormalizationCheckedChanged: {
							main_operator_backend._set_global_background_normalization(globalBackgroundNormalizationChecked)
						}

						// Send initial parameters to Python
						Component.onCompleted: {
							main_operator_backend._set_image_filter_method_index(imageFilterMethodCurrentIndex)
							main_operator_backend._set_gaussian_background_sigma(gaussianBackgroundSigmaValue)
							main_operator_backend._set_global_background_normalization(globalBackgroundNormalizationChecked)
						}

					}

				}

				RowLayout {

					Layout.fillWidth: true
					Layout.leftMargin: AppConfig.rowLayoutLeftMargin
					Layout.rightMargin: AppConfig.rowLayoutRightMargin

					ImageFilterGB {

						id: imageFilterGB

						Layout.fillWidth: true

						onHotPixelFilterCheckedChanged: {
							main_operator_backend._set_hot_pixel_filter(hotPixelFilterChecked)
						}
						onHotPixelSensitivityValueChanged: {
							main_operator_backend._set_hot_pixel_sensitivity(hotPixelSensitivityValue)
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
							main_operator_backend._set_hot_pixel_filter(hotPixelFilterChecked)
							main_operator_backend._set_hot_pixel_sensitivity(hotPixelSensitivityValue)
							main_operator_backend._set_unsharp_kernel_size(unsharpKernelSize)
							main_operator_backend._set_unsharp_amount(unsharpValue)
							main_operator_backend._set_unsharp_gaussian_sigma(unsharpGaussianSigmaValue)
						}

					}

				}

				RowLayout {

					Layout.fillWidth: true
					Layout.leftMargin: AppConfig.rowLayoutLeftMargin
					Layout.rightMargin: AppConfig.rowLayoutRightMargin

					InterpolationGB {

						id: interpolationGB

						Layout.fillWidth: true

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

			}

		}

		// Pinned bottom: status and controls stay visible at any window height
		RowLayout {

			Layout.fillWidth: true
			Layout.leftMargin: AppConfig.rowLayoutLeftMargin
			Layout.rightMargin: AppConfig.rowLayoutRightMargin

			StatusGB {

				id: statusGB

				Layout.fillWidth: true

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

			Layout.fillWidth: true
			Layout.leftMargin: AppConfig.rowLayoutLeftMargin
			Layout.rightMargin: AppConfig.rowLayoutRightMargin
			Layout.bottomMargin: AppConfig.rowLayoutBottomMargin
			spacing: 8

			Button {

				property string _toolTipText: AppConfig.deleteDataButtonToolTip

				id: deleteDataButton
				Layout.alignment: Qt.AlignLeft
				text: qsTr("Delete Processed Data")
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

	// Confirmation before recursively deleting processed output
	Dialog {

		id: deleteConfirmDialog
		title: qsTr("Delete Processed Data")
		modal: true
		parent: Overlay.overlay
		anchors.centerIn: parent
		standardButtons: Dialog.Yes | Dialog.No

		onAccepted: {
			main_operator_backend.delete_processed_data()
		}

		Label {
			text: qsTr("Permanently delete the selected stack's processed images\nfolder and its interpolated TFS file?")
		}

	}

}
