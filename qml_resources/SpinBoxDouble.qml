import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material

SpinBox {
    id: root

    property real realValue: 0.0
    property real realFrom: 0.0
    property real realTo: 100.0
    property real realStepSize: 1.0
    property int decimals: 2

    readonly property int scaleFactor: Math.pow(10, decimals)

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

    // Enter/Return commits the edit by dropping focus
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            root.focus = false
            event.accepted = true
        }
    }

    onValueChanged: {
        var newRealValue = value / scaleFactor
        if (Math.abs(newRealValue - realValue) > Number.EPSILON) {
            realValue = newRealValue
        }
    }

    onRealValueChanged: {
        var newValue = Math.round(realValue * scaleFactor)
        if (newValue !== value) {
            value = newValue
        }
    }

    valueFromText: function(text, locale) {
        return Math.round(Number.fromLocaleString(locale, text) * scaleFactor)
    }

    textFromValue: function(value, locale) {
        return Number(value / scaleFactor).toLocaleString(locale, 'f', decimals)
    }
}
