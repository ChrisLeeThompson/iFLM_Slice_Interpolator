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
    readonly property string globalBackgroundNormalizationLabelToolTip: qsTr("If checked, the background is normalized globally for each stack (rather than for each image individually).")
    readonly property string hotPixelFilterLabelToolTip: qsTr("Removes hot pixels: single pixels that read brighter than all eight of their neighbours by more than the local noise.\n\n") +
                                                         qsTr("Persistent defects are repaired in every slice; transient events are repaired only in the slices where they occur.\n") +
                                                         qsTr("Corrected pixels are replaced with the median of their neighbours and can only ever get darker; no other pixel is changed.\n") +
                                                         qsTr("A hotpixel_votes_<wavelength>.tif (per-pixel detection counts) and, when persistent defects are found, a hotpixel_mask_<wavelength>.tif are written beside the processed images so the result can be checked.\n\n") +
                                                         qsTr("Leave unchecked if the iFLM hot pixel filter was enabled during acquisition.")
    readonly property string hotPixelSensitivityLabelToolTip: qsTr("Detection threshold, in local noise sigma above the brightest neighbour. Applies to both persistent and transient detection.\n\n") +
                                                              qsTr("Aggressive: 3 (may replace real single-pixel detail)\n") +
                                                              qsTr("Recommended: 6\n") +
                                                              qsTr("Conservative: 8+ (strongest defects only)\n\n") +
                                                              qsTr("A pixel hidden under a bright specimen region in a given slice cannot be detected in that slice; persistent defects are still repaired there via the stack-wide map.\n") +
                                                              qsTr("The pixel counts for every channel appear in the status line.")
    readonly property string unsharpKernelSizeToolTip: qsTr("Set the kernel size for the Gaussian blur.\n") +
                                                       qsTr("0: the kernel size is calculated automatically from the sigma value.")
    readonly property string unsharpLabelToolTip: qsTr("Controls sharpening strength.\n\n") +
                                                  qsTr("Disable: 0\n") +
                                                  qsTr("Moderate: 7\n") +
                                                  qsTr("Strong: 15+ (may introduce artifacts)")
    readonly property string unsharpGaussianSigmaLabelToolTip: qsTr("Controls the width of the Gaussian blur.")
    readonly property string gaussianFilterLabelToolTip: qsTr("Blur strength for background estimation.\n") +
                                                         qsTr("Larger values remove broader background variations.")
    readonly property string rollingFilterLabelToolTip: qsTr("Scale of the background estimate, in pixels.\n\n") +
                                                        qsTr("The background is taken from the local dim floor (lower envelope), so bright features keep their intensity.\n") +
                                                        qsTr("Choose a radius larger than your biggest real feature. Recommended starting point: 200.")
    readonly property string deleteDataButtonToolTip: qsTr("Deletes the processed_images directory and interpolated TFS file.")

}
