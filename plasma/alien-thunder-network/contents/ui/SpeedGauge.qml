import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PC

Rectangle {
    id: gauge
    required property string title
    required property string reading
    required property string scaleLabel
    required property color tint
    property real value: 0
    property real maximum: 1024
    property bool ready: false
    property bool analog: true
    property bool alert: false

    implicitHeight: analog ? 236 : 80
    implicitWidth: 180
    radius: 8
    color: "#101216"
    border.color: "#30343b"
    Accessible.role: Accessible.Indicator
    Accessible.name: title + ": " + reading

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 4
        RowLayout {
            PC.Label { text: gauge.title; color: gauge.tint; font.pointSize: 9; Layout.fillWidth: true }
            AlertLed { active: gauge.ready && gauge.alert }
        }
        AnalogDial {
            visible: gauge.analog
            Layout.fillWidth: true
            Layout.fillHeight: true
            value: gauge.value
            maximum: gauge.maximum
            divisor: maximum >= 1048576 ? 1048576 : 1024
            unit: maximum >= 1048576 ? "MiB/s" : "KiB/s"
            tint: gauge.tint
            ready: gauge.ready
        }
        PC.Label {
            text: gauge.reading
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            font.bold: true
            font.pointSize: 16
            color: "#f4f5f7"
            elide: Text.ElideRight
        }
        PC.Label {
            text: gauge.scaleLabel
            visible: gauge.analog
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            font.pointSize: 8
            color: "#aeb4bd"
            elide: Text.ElideRight
        }
    }
}
