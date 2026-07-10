import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material

SpinBox {
    id: root

    // Public properties for double precision
    property real realValue: 0.0
    property real realFrom: 0.0
    property real realTo: 100.0
    property real realStepSize: 1.0
    property int decimals: 2

    // Internal scale factor based on decimals
    readonly property int scaleFactor: Math.pow(10, decimals)

    // Configure SpinBox based on real values
    from: Math.round(realFrom * scaleFactor)
    to: Math.round(realTo * scaleFactor)
    stepSize: Math.round(realStepSize * scaleFactor)
    value: Math.round(realValue * scaleFactor)

    editable: true
    // Wheel stays disabled: with the whole UI in a ScrollView, wheel-scrolling
    // the page over a spinbox would silently change processing parameters
    wheelEnabled: false
    hoverEnabled: true

    validator: DoubleValidator {
        bottom: root.realFrom
        top: root.realTo
        decimals: root.decimals
        notation: DoubleValidator.StandardNotation
    }

    // Handle Enter/Return key to remove focus
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            root.focus = false
            event.accepted = true
        }
    }

    // Hide the up/down buttons
    // up.indicator: Item {}
    // down.indicator: Item {}

    // Material-styled background
    // background: Rectangle {
    //     implicitWidth: 100
    //     implicitHeight: 48
    //     color: root.enabled ? root.Material.dialogColor : root.Material.backgroundColor
    //     border.color: {
    //         if (!root.enabled) return root.Material.hintTextColor
    //         if (root.activeFocus) return root.Material.accentColor
    //         if (root.hovered) return root.Material.primaryTextColor
    //         return root.Material.hintTextColor
    //     }
    //     border.width: root.activeFocus ? 2 : 1
    //     radius: 4

    //     // Material ripple effect on bottom border when focused
    //     Rectangle {
    //         width: parent.width
    //         height: 2
    //         anchors.bottom: parent.bottom
    //         color: root.Material.accentColor
    //         visible: root.activeFocus
    //     }
    // }

    // // Material-styled text input
    // contentItem: TextInput {
    //     z: 2
    //     text: root.textFromValue(root.value, root.locale)
    //     font: root.font
    //     color: root.enabled ? root.Material.foreground : root.Material.hintTextColor
    //     selectionColor: root.Material.accentColor
    //     selectedTextColor: root.Material.background
    //     horizontalAlignment: Qt.AlignHCenter
    //     verticalAlignment: Qt.AlignVCenter
    //     leftPadding: 12
    //     rightPadding: 12

    //     readOnly: !root.editable
    //     validator: root.validator
    //     inputMethodHints: Qt.ImhFormattedNumbersOnly
    // }

    // Sync internal value changes back to realValue
    onValueChanged: {
        var newRealValue = value / scaleFactor
        if (Math.abs(newRealValue - realValue) > Number.EPSILON) {
            realValue = newRealValue
        }
    }

    // Sync external realValue changes to internal value
    onRealValueChanged: {
        var newValue = Math.round(realValue * scaleFactor)
        if (newValue !== value) {
            value = newValue
        }
    }

    // Convert displayed text to internal integer value
    valueFromText: function(text, locale) {
        return Math.round(Number.fromLocaleString(locale, text) * scaleFactor)
    }

    // Convert internal integer value to displayed text
    textFromValue: function(value, locale) {
        return Number(value / scaleFactor).toLocaleString(locale, 'f', decimals)
    }
}
