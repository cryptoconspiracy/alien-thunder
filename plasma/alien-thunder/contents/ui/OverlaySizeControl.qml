import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.plasma5support as P5Support

ColumnLayout {
    id: control
    property bool loaded: false
    property bool updating: false
    property string errorText: ""

    function refresh() { source.run("status") }
    function apply() {
        updating = true
        source.run("size " + Math.round(sizeSlider.value))
    }

    P5Support.DataSource {
        id: source
        engine: "executable"
        function run(action) {
            connectSource('PATH="$HOME/.local/bin:$PATH"; alien-thunder overlay ' + action)
        }
        onNewData: (command, data) => {
            disconnectSource(command)
            if (data["exit code"] !== 0) {
                control.errorText = i18n("Could not change or read the overlay size.")
                control.updating = false
                return
            }
            control.errorText = ""
            if (command.endsWith(" status")) {
                try {
                    const config = JSON.parse(data.stdout)
                    if (!sizeSlider.pressed && !pending.running)
                        sizeSlider.value = Math.round((config.scale || 1) * 100)
                    control.loaded = true
                } catch (e) { control.errorText = i18n("Could not change or read the overlay size.") }
                control.updating = false
            } else {
                control.refresh()
            }
        }
    }

    Component.onCompleted: refresh()
    Timer {
        interval: 2000
        running: control.visible
        repeat: true
        onTriggered: {
            if (!sizeSlider.pressed && !pending.running && !control.updating)
                control.refresh()
        }
    }
    Timer { id: pending; interval: 250; onTriggered: control.apply() }

    RowLayout {
        Layout.fillWidth: true
        QQC2.Slider {
            id: sizeSlider
            Layout.fillWidth: true
            Layout.minimumWidth: 120
            from: 50
            to: 250
            stepSize: 5
            value: 100
            enabled: control.loaded && !control.updating
            Accessible.name: i18n("Overlay size")
            onMoved: { if (!pressed) pending.restart() }
            onPressedChanged: { if (!pressed) pending.restart() }
        }
        QQC2.Label { text: Math.round(sizeSlider.value) + "%"; Layout.preferredWidth: 44 }
        QQC2.Button {
            text: "100%"
            enabled: control.loaded && !control.updating
            Accessible.name: i18n("Reset overlay size")
            onClicked: { sizeSlider.value = 100; pending.restart() }
        }
    }
    QQC2.Label {
        text: control.errorText || i18n("Applied on release; limited to the screen size.")
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        opacity: 0.7
    }
}
