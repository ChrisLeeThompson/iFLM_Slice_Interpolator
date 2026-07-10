pragma Singleton
import QtQuick
import QtQuick.Controls.Material

QtObject {

    // Main window
    readonly property string mainWindowBackgroundColor: Material.primary
    readonly property string mainWindowTitle: qsTr("iFLM Slice Interpolator")

    // Group Box
    readonly property string groupBoxColor: "lightgrey"
    readonly property int groupBoxRadius: 8

    // Column Layout
    readonly property int columnLayoutSpacing: 10

    // Row Layout
    readonly property int rowLayoutTopMargin: 16
    readonly property int rowLayoutLeftMargin: 16
    readonly property int rowLayoutRightMargin: 16
    readonly property int rowLayoutBottomMargin: 16

    // Tool Tip
    readonly property int toolTipDelay: 1500
    readonly property int toolTipTimeout: 8000
    readonly property string fromTFSFileRadioButtonToolTip: qsTr("Images are processed from an iFLM TFS XML file.")
    readonly property string globalBackgroundNormalizationLabelToolTip: qsTr("If checked, background is normalized globally for each stack (rather than for each image individually).")
    readonly property string unsharpKernelSizeToolTip: qsTr("Set the kernel size for the gaussian blur.\n") +
                                                       qsTr("0: the method automatically calculates the kernel size with the sigma value.\n")
    readonly property string unsharpLabelToolTip: qsTr("Controls sharpening strength.\n\n") +
                                                  qsTr("Disable: 0\n") +
                                                  qsTr("Moderate: 7\n") +
                                                  qsTr("Strong: 15+ (may introduce artifacts)")
    readonly property string unsharpGaussianSigmaLabelToolTip: qsTr("Controls the width of the gaussian blur.\n")
    readonly property string gaussianFilterLabelToolTip: qsTr("Blur strength for background estimation.\n") +
                                                         qsTr("Larger values remove more broad background variations.")
    readonly property string deleteDataButtonToolTip: qsTr("Deletes the processed_images directory and interpolated TFS file.")

}
