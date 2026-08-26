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
    readonly property string globalBackgroundNormalizationLabelToolTip: qsTr("Normalizes the background across the whole stack rather than per slice.")
    readonly property string hotPixelFilterLabelToolTip: qsTr("Removes single pixels brighter than all eight neighbors by more than the local noise.\n") +
                                                         qsTr("Persistent defects are repaired in every slice, transients only where they occur; repairs never brighten.\n") +
                                                         qsTr("Writes hotpixel_votes and hotpixel_mask TIFFs for review. Leave unchecked if the iFLM hot pixel filter ran during acquisition.")
    readonly property string hotPixelSensitivityLabelToolTip: qsTr("Detection threshold in local noise sigma above the brightest neighbor; a higher value detects fewer pixels.\n\n") +
                                                              qsTr("Aggressive: 3 (may replace real single-pixel detail)\n") +
                                                              qsTr("Recommended: 6\n") +
                                                              qsTr("Conservative: 8+ (strongest defects only)\n\n") +
                                                              qsTr("Per-channel counts appear in the status line.")
    readonly property string unsharpKernelSizeToolTip: qsTr("Kernel size for the Gaussian blur.\n") +
                                                       qsTr("0: calculated automatically from the sigma value.")
    readonly property string unsharpLabelToolTip: qsTr("Sharpening strength.\n\n") +
                                                  qsTr("Off: 0\n") +
                                                  qsTr("Subtle: 3\n") +
                                                  qsTr("Moderate: 7\n") +
                                                  qsTr("Strong: 15+ (may introduce artifacts)")
    readonly property string unsharpGaussianSigmaLabelToolTip: qsTr("Width of the Gaussian blur.")
    readonly property string gaussianFilterLabelToolTip: qsTr("Blur strength for background estimation.\n") +
                                                         qsTr("Larger values remove broader background variations.")
    readonly property string rollingFilterLabelToolTip: qsTr("Scale of the background estimate, in pixels.\n\n") +
                                                        qsTr("The background follows the dim areas between features, so bright features keep their intensity.\n") +
                                                        qsTr("Choose a radius larger than your biggest real feature. Recommended starting point: 200.")
    readonly property string deleteDataButtonToolTip: qsTr("Deletes the selected stack's folder inside processed_images and its interpolated TFS file.")

}
