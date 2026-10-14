import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents3
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    // Written every two seconds by the alien-thunder service.
    property var sensors: ({})
    property var overlay: ({ running: false, items: {} })
    property bool serviceDown: false
    property bool networkEnabled: false
    property bool desktopEnabled: false
    property bool syncingStyle: false
    readonly property bool onDesktop: Plasmoid.formFactor === PlasmaCore.Types.Planar
    preferredRepresentation: onDesktop ? fullRepresentation : compactRepresentation
    fullRepresentation: onDesktop ? desktopRepresentation : panelRepresentation
    Plasmoid.backgroundHints: onDesktop ? PlasmaCore.Types.NoBackground : PlasmaCore.Types.DefaultBackground

    readonly property url icon: Qt.resolvedUrl("../images/alien-thunder.png")
    readonly property var metrics: ["cpu_temp", "cpu_load", "gpu_temp", "gpu_mem", "cpu_fan", "gpu_fan", "ram", "ram_gb"]
    readonly property var overlayMetrics: metrics.concat(["download", "upload"])

    Loader {
        id: panelNetwork
        active: !root.onDesktop && (Plasmoid.configuration.panel_download || Plasmoid.configuration.panel_upload)
        source: "NetworkData.qml"
    }
    function isNetwork(key) { return key === "download" || key === "upload" }
    function numericValue(key) {
        if (isNetwork(key))
            return panelNetwork.item && panelNetwork.item.ready && panelNetwork.item.available
                ? panelNetwork.item[key + "Average"] : null
        return serviceDown ? null : sensors[key]
    }

    function label(key) {
        switch (key) {
        case "download": return i18n("Download")
        case "upload": return i18n("Upload")
        case "cpu_temp": return i18n("CPU")
        case "cpu_load": return i18n("CPU load")
        case "gpu_temp": return i18n("GPU")
        case "gpu_mem": return i18n("VRAM")
        case "ram_gb": return i18n("RAM")
        case "cpu_fan": return i18n("CPU fan")
        case "gpu_fan": return i18n("GPU fan")
        case "ram": return i18n("RAM")
        }
        return key
    }

    function unit(key) {
        if (isNetwork(key)) return maximum(key) >= 1048576 ? "MiB/s" : "KiB/s"
        if (key.endsWith("_temp")) return "°C"
        if (key.endsWith("_fan")) return i18nc("revolutions per minute", "rpm")
        if (key === "ram_gb") return i18nc("gigabytes of memory", "GB / %1", sensors.ram_total_gb || "?")
        return "%"
    }

    function value(key) {
        const v = numericValue(key)
        if (v === undefined || v === null) return "--"
        return isNetwork(key) ? (v / (maximum(key) >= 1048576 ? 1048576 : 1024)).toFixed(1) : String(v)
    }

    function color(key) {
        const v = numericValue(key)
        if (v === undefined || v === null) return Kirigami.Theme.disabledTextColor
        if (isNetwork(key)) return "#ff6a00"
        if (key.endsWith("_temp")) {
            if (v >= 90) return Kirigami.Theme.negativeTextColor
            if (v >= 75) return Kirigami.Theme.neutralTextColor
        }
        if (key === "ram" || key === "gpu_mem") {
            if (v >= 95) return Kirigami.Theme.negativeTextColor
            if (v >= 85) return Kirigami.Theme.neutralTextColor
        }
        return Kirigami.Theme.textColor
    }

    function shownOnPanel(key) {
        return Plasmoid.configuration["panel_" + key]
    }

    function usageAlert(key) {
        if (key === "ram_gb") key = "ram"
        return !serviceDown && ["cpu_load", "gpu_mem", "ram"].includes(key) && sensors[key] > 90
    }

    function maximum(key) {
        if (isNetwork(key)) {
            const history = panelNetwork.item ? panelNetwork.item.gaugeHistory : []
            const peak = Math.max(1024, numericValue(key) || 0, ...history.map(p => p[key]))
            return Math.pow(2, Math.ceil(Math.log2(peak)))
        }
        if (key.endsWith("_temp")) return 120
        if (key.endsWith("_fan")) return Math.max(8000, Math.ceil((sensors[key] || 0) / 2000) * 2000)
        if (key === "ram_gb") return sensors.ram_total_gb || 32
        return 100
    }

    function quote(text) {
        return "'" + String(text).replace(/'/g, "'\\''") + "'"
    }

    // alien-thunder lives in ~/.local/bin, which plasmashell doesn't always have on PATH.
    component Shell: P5Support.DataSource {
        engine: "executable"
        function run(command) {
            connectSource("PATH=\"$HOME/.local/bin:$PATH\"; " + command)
        }
    }

    Shell {
        id: sensorSource
        onNewData: (source, data) => {
            disconnectSource(source)
            try {
                root.sensors = JSON.parse(data.stdout)
                root.serviceDown = false
            } catch (e) {
                root.serviceDown = true
            }
        }
    }

    Shell {
        id: overlaySource
        function refresh() { run("alien-thunder overlay status") }
        onNewData: (source, data) => {
            disconnectSource(source)
            try {
                root.overlay = JSON.parse(data.stdout)
                // A desktop instance can change the global style too.
                root.syncingStyle = true
                Plasmoid.configuration.overlay_style = root.overlay.style === "analog" ? "analog" : "digital"
                for (const key of root.overlayMetrics)
                    Plasmoid.configuration["overlay_" + key] = !!root.overlay.items[key]
                root.syncingStyle = false
            } catch (e) { root.syncingStyle = false }
        }
    }

    Shell {
        id: networkSource
        function refresh() { run("alien-thunder network status") }
        onNewData: (source, data) => {
            disconnectSource(source)
            try { root.networkEnabled = JSON.parse(data.stdout).enabled } catch (e) {}
        }
    }

    Shell {
        id: desktopSource
        function refresh() { run("alien-thunder desktop status") }
        onNewData: (source, data) => {
            disconnectSource(source)
            try { root.desktopEnabled = JSON.parse(data.stdout).enabled } catch (e) {}
        }
    }

    Shell {
        id: commands
        // Every change is followed by a fresh read, so the switches show what really happened.
        onNewData: (source) => {
            disconnectSource(source)
            overlaySource.refresh()
            networkSource.refresh()
            desktopSource.refresh()
            sensorSource.run("cat \"$XDG_RUNTIME_DIR/alien-thunder/sensors.json\"")
        }
    }

    Timer {
        interval: 2000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            sensorSource.run("cat \"$XDG_RUNTIME_DIR/alien-thunder/sensors.json\"")
            if (root.onDesktop) overlaySource.refresh()
        }
    }

    onExpandedChanged: () => {
        if (root.expanded) {
            overlaySource.refresh()
            networkSource.refresh()
            desktopSource.refresh()
        }
    }
    Component.onCompleted: {
        overlaySource.refresh()
        networkSource.refresh()
        desktopSource.refresh()
    }

    // The overlay's readings are chosen here (settings or popup) and handed to the bar in
    // one go, after a short pause so ticking several boxes restarts it once.
    Timer {
        id: overlaySync
        interval: 400
        onTriggered: {
            if (root.onDesktop) {
                commands.run("alien-thunder overlay style "
                             + (Plasmoid.configuration.overlay_style === "analog" ? "analog" : "digital"))
                return
            }
            commands.run("alien-thunder overlay items "
                                  + root.quote(root.overlayMetrics.filter(k => Plasmoid.configuration["overlay_" + k]).join(","))
                                  + " " + (Plasmoid.configuration.overlay_style === "analog" ? "analog" : "digital"))
        }
    }

    Connections {
        target: Plasmoid.configuration
        function onValueChanged(key) {
            if (root.syncingStyle) return
            if (key.startsWith("overlay_") && (!root.onDesktop || key === "overlay_style"))
                overlaySync.restart()
        }
    }

    Plasmoid.icon: icon
    toolTipMainText: "Alien Thunder"
    toolTipSubText: {
        if (serviceDown) return i18n("The alien-thunder service isn't running")
        const lines = metrics.map(k => label(k) + ": " + value(k) + " " + unit(k))
        lines.push(sensors.gmode ? i18n("G-Mode is on") : i18n("G-Mode is off"))
        return lines.join("\n")
    }

    compactRepresentation: MouseArea {
        id: panelArea
        hoverEnabled: true
        onClicked: root.expanded = !root.expanded

        Layout.minimumWidth: row.implicitWidth
        Layout.preferredWidth: row.implicitWidth

        RowLayout {
            id: row
            anchors.verticalCenter: parent.verticalCenter
            spacing: Kirigami.Units.smallSpacing * 2

            Item {
                Layout.preferredWidth: panelArea.height
                Layout.preferredHeight: panelArea.height

                Kirigami.Icon {
                    anchors.fill: parent
                    anchors.margins: 2
                    source: root.icon
                    active: panelArea.containsMouse
                }

                // G-Mode badge, white like the F1 key while it's on.
                Rectangle {
                    visible: !!root.sensors.gmode
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    width: Math.round(parent.height * 0.42)
                    height: width
                    radius: width / 2
                    color: "white"
                    border.color: "black"
                    PlasmaComponents3.Label {
                        anchors.centerIn: parent
                        text: "G"
                        color: "black"
                        font.bold: true
                        font.pixelSize: parent.height * 0.7
                    }
                }
            }

            Repeater {
                model: root.overlayMetrics.filter(k => root.shownOnPanel(k))
                delegate: RowLayout {
                    id: panelGauge
                    required property string modelData
                    spacing: 2
                    AnalogDial {
                        visible: Plasmoid.configuration.panel_style === "analog"
                        compact: true
                        Layout.preferredWidth: panelArea.height
                        Layout.preferredHeight: panelArea.height
                        value: root.numericValue(panelGauge.modelData) || 0
                        maximum: root.maximum(panelGauge.modelData)
                        ready: root.numericValue(panelGauge.modelData) !== undefined && root.numericValue(panelGauge.modelData) !== null
                    }
                    ColumnLayout {
                        spacing: -2
                        PlasmaComponents3.Label {
                            text: root.label(panelGauge.modelData).toUpperCase() + " " + root.unit(panelGauge.modelData)
                            font.pixelSize: Math.max(8, panelArea.height * 0.24)
                            opacity: 0.6
                            Layout.alignment: Qt.AlignHCenter
                        }
                        PlasmaComponents3.Label {
                            text: root.value(panelGauge.modelData)
                            color: root.color(panelGauge.modelData)
                            font.family: "monospace"
                            font.bold: true
                            font.pixelSize: Math.max(11, panelArea.height * 0.42)
                            Layout.alignment: Qt.AlignHCenter
                        }
                    }
                }
            }
        }
    }

    Component {
        id: desktopRepresentation
        Item {
            Layout.minimumWidth: 180
            Layout.minimumHeight: 40
            Layout.preferredWidth: Math.max(180, Math.min(desktopBar.implicitWidth, Screen.width * 0.9))
            Layout.preferredHeight: Math.min(desktopBar.implicitHeight, Screen.height * 0.8)
            Layout.maximumWidth: desktopBar.vertical ? Math.max(180, desktopBar.implicitWidth * 2.5) : Infinity
            Layout.maximumHeight: desktopBar.vertical ? Infinity : Math.max(40, desktopBar.implicitHeight * 2.5)
            BarContent {
                id: desktopBar
                width: implicitWidth
                height: implicitHeight
                showClose: false
                showHandle: false
                vertical: Plasmoid.configuration.desktop_orientation === "vertical"
                scale: Math.min(parent.width / width, parent.height / height)
                transformOrigin: Item.TopLeft
                x: (parent.width - width * scale) / 2
                y: (parent.height - height * scale) / 2
                visible: root.overlayMetrics.some(k => Plasmoid.configuration["desktop_" + k])
                backend: {
                    const selected = {}, labels = {}
                    for (const key of root.overlayMetrics) {
                        selected[key] = !!Plasmoid.configuration["desktop_" + key]
                        labels[key] = root.label(key)
                    }
                    return {config: {style: Plasmoid.configuration.desktop_style, items: selected},
                        values: root.serviceDown ? {} : root.sensors,
                        items: root.overlayMetrics, labels: labels}
                }
            }
            PlasmaComponents3.Label {
                anchors.fill: parent
                visible: !desktopBar.visible
                text: i18n("Choose desktop readings in the widget settings.")
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }
    }

    Component {
      id: panelRepresentation
      PlasmaExtras.Representation {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 22
        Layout.minimumWidth: Kirigami.Units.gridUnit * 18
        Layout.preferredHeight: content.implicitHeight + header.implicitHeight + Kirigami.Units.largeSpacing * 2
        collapseMarginsHint: true

        header: PlasmaExtras.PlasmoidHeading {
            RowLayout {
                anchors.fill: parent
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: root.icon
                    Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                    Layout.preferredHeight: Kirigami.Units.iconSizes.medium
                }
                Kirigami.Heading {
                    text: "Alien Thunder"
                    level: 2
                    Layout.fillWidth: true
                }
                PlasmaComponents3.ToolButton {
                    icon.name: "preferences-desktop-color"
                    text: i18n("Lighting")
                    onClicked: {
                        commands.run("setsid -f alien-thunder >/dev/null 2>&1")
                        root.expanded = false
                    }
                    PlasmaComponents3.ToolTip { text: i18n("Open the keyboard lighting editor") }
                }
            }
        }

        ColumnLayout {
            id: content
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.largeSpacing

            PlasmaComponents3.Label {
                visible: root.serviceDown
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                color: Kirigami.Theme.negativeTextColor
                text: i18n("No readings: the alien-thunder service isn't running. Start it with: systemctl --user start alien-thunder")
            }

            GridLayout {
                visible: !root.onDesktop
                columns: 3
                Layout.fillWidth: true
                columnSpacing: Kirigami.Units.largeSpacing
                rowSpacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: root.metrics
                    delegate: ColumnLayout {
                        required property string modelData
                        Layout.fillWidth: true
                        spacing: 0
                        PlasmaComponents3.Label {
                            text: root.label(modelData).toUpperCase() + " " + root.unit(modelData)
                            opacity: 0.6
                            font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                        }
                        PlasmaComponents3.Label {
                            text: root.value(modelData)
                            color: root.color(modelData)
                            font.family: "monospace"
                            font.bold: true
                            font.pixelSize: Kirigami.Units.gridUnit * 1.6
                        }
                    }
                }
            }

            Kirigami.Separator { Layout.fillWidth: true }

            RowLayout {
                visible: !root.onDesktop
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    PlasmaComponents3.Label { text: i18n("G-Mode"); font.bold: true }
                    PlasmaComponents3.Label {
                        text: i18n("Fans at full speed and the performance power profile. Same as Fn+F1.")
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                        Layout.fillWidth: true
                    }
                }
                PlasmaComponents3.Switch {
                    checked: !!root.sensors.gmode
                    onToggled: commands.run("alien-thunder gmode " + (checked ? "on" : "off"))
                }
            }

            RowLayout {
                visible: !root.onDesktop
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    PlasmaComponents3.Label { text: i18n("Overlay"); font.bold: true }
                    PlasmaComponents3.Label {
                        text: i18n("A bar of readouts above every window, games included. Drag it anywhere, on any screen; its ✕ turns it off.")
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                        Layout.fillWidth: true
                    }
                }
                PlasmaComponents3.Switch {
                    checked: !!root.overlay.running
                    onToggled: commands.run("alien-thunder overlay " + (checked ? "on" : "off"))
                }
            }

            ColumnLayout {
                visible: !root.onDesktop
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.largeSpacing
                spacing: 0

                RowLayout {
                    PlasmaComponents3.Label { text: i18n("Gauge style:") }
                    PlasmaComponents3.ComboBox {
                        model: [i18n("Digital"), i18n("Analog · Audi style")]
                        currentIndex: Plasmoid.configuration.overlay_style === "analog" ? 1 : 0
                        onActivated: Plasmoid.configuration.overlay_style = currentIndex === 1 ? "analog" : "digital"
                    }
                }

                PlasmaComponents3.Label { text: i18n("Overlay size:") }
                OverlaySizeControl { Layout.fillWidth: true }

                Flow {
                    visible: !!root.overlay.running
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Repeater {
                        model: root.overlayMetrics
                        delegate: PlasmaComponents3.CheckBox {
                            required property string modelData
                            text: root.label(modelData) + " " + root.unit(modelData).split(" ")[0]
                            checked: !!Plasmoid.configuration["overlay_" + modelData]
                            onToggled: Plasmoid.configuration["overlay_" + modelData] = checked
                        }
                    }
                }
            }

            RowLayout {
                visible: !root.onDesktop
                Layout.fillWidth: true
                PlasmaComponents3.Label {
                    text: i18n("Desktop gauges")
                    font.bold: true
                    Layout.fillWidth: true
                }
                PlasmaComponents3.Switch {
                    checked: root.desktopEnabled
                    onToggled: commands.run("alien-thunder desktop " + (checked ? "on" : "off"))
                }
            }

            RowLayout {
                visible: !root.onDesktop
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    PlasmaComponents3.Label { text: i18n("Network widget"); font.bold: true }
                    PlasmaComponents3.Label {
                        text: i18n("Upload and download by application on your desktop.")
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                        Layout.fillWidth: true
                    }
                }
                PlasmaComponents3.Switch {
                    checked: root.networkEnabled
                    onToggled: commands.run("alien-thunder network " + (checked ? "on" : "off"))
                }
            }

        }
      }
    }
}
