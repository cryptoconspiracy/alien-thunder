import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PC

Rectangle {
    id: gauge
    required property string title
    required property string reading
    required property string unit
    property real value: 0
    property real maximum: 100
    property real divisor: 1
    property bool ready: false
    property bool analog: false
    property bool alert: false
    implicitHeight: analog ? 204 : 78
    implicitWidth: 148
    radius: 8
    color: "#e00b0d10"
    border.color: "#55ff6a00"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 3
        RowLayout {
            Layout.fillWidth: true
            PC.Label {
                text: gauge.title
                color: "#ff6a00"
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
            AlertLed { active: gauge.ready && gauge.alert }
        }
        AnalogDial {
            visible: gauge.analog
            Layout.fillWidth: true
            Layout.fillHeight: true
            value: gauge.value
            maximum: gauge.maximum
            divisor: gauge.divisor
            unit: gauge.unit
            ready: gauge.ready
        }
        PC.Label {
            Layout.fillWidth: true
            text: gauge.reading
            horizontalAlignment: Text.AlignHCenter
            color: "#f4f5f7"
            font.bold: true
            font.pixelSize: gauge.analog ? 16 : 22
            elide: Text.ElideRight
        }
    }
}
