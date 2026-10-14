import QtQuick

Item {
    id: led
    property bool active: false
    implicitWidth: 12
    implicitHeight: 12
    Accessible.role: Accessible.Indicator
    Accessible.name: qsTr("High usage alert")
    Accessible.ignored: !active

    Rectangle {
        anchors.centerIn: parent
        width: 12
        height: 12
        radius: 6
        color: "#44ff2534"
        visible: led.active
    }
    Rectangle {
        anchors.centerIn: parent
        width: 8
        height: 8
        radius: 4
        color: "#ff2534"
        visible: led.active
        SequentialAnimation on opacity {
            running: led.active && led.visible
            loops: Animation.Infinite
            NumberAnimation { from: 1; to: 0.2; duration: 500 }
            NumberAnimation { from: 0.2; to: 1; duration: 500 }
        }
    }
}
