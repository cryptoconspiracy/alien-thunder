import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PC
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5Support

PlasmoidItem {
    id: root
    readonly property color downColor: "#ff6a00"
    readonly property color upColor: "#ffad32"
    property bool sharedAnalog: false
    property var overlayItems: ({})
    readonly property bool analog: Plasmoid.configuration.gaugeStyle === "analog"
        || (Plasmoid.configuration.gaugeStyle !== "digital" && sharedAnalog)

    // Follow the shared style unless this widget has its own preference.
    P5Support.DataSource {
        engine: "executable"
        connectedSources: ['cat "${XDG_CONFIG_HOME:-$HOME/.config}/alien-thunder/overlay.json"']
        interval: 2000
        onNewData: (source, data) => {
            try {
                const config = JSON.parse(data.stdout)
                root.sharedAnalog = config.style === "analog"
                root.overlayItems = config.items || {}
            }
            catch (e) { root.sharedAnalog = false }
        }
    }

    P5Support.DataSource {
        id: overlayCommands
        engine: "executable"
        onNewData: (source, data) => disconnectSource(source)
        function toggle(key, checked) {
            connectSource('PATH="$HOME/.local/bin:$PATH"; alien-thunder overlay '
                          + (checked ? "show " : "hide ") + key
                          + (checked ? " && alien-thunder overlay on" : ""))
        }
    }

    function rate(value) {
        if (value < 1024) return Math.round(value) + " B/s"
        if (value < 1048576) return (value / 1024).toFixed(1) + " KiB/s"
        return (value / 1048576).toFixed(1) + " MiB/s"
    }

    function gaugeMaximum(key) {
        const peak = Math.max(1024, traffic[key + "Average"], ...traffic.gaugeHistory.map(p => p[key]))
        return Math.pow(2, Math.ceil(Math.log2(peak)))
    }

    // Compare against observed traffic, not the rounded dial scale or link capacity.
    function nearPeak(key) {
        const peak = Math.max(0, ...traffic.gaugeHistory.map(p => p[key]))
        return traffic.gaugeHistory.length >= 2 && peak > 0 && traffic[key + "Average"] > 0
            && traffic[key + "Average"] >= peak * 0.9
    }

    NetworkData {
        id: traffic
        sortBy: Plasmoid.configuration.sortBy === "download" ? "download" : "upload"
        showIdle: Plasmoid.configuration.showIdle
    }

    Plasmoid.icon: "network-transmit-receive"
    preferredRepresentation: fullRepresentation
    toolTipMainText: i18n("Alien Thunder · Network")
    toolTipSubText: i18n("Download: %1 · Upload: %2", rate(traffic.download), rate(traffic.upload))

    fullRepresentation: Item {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 20
        Layout.minimumHeight: Kirigami.Units.gridUnit * (root.analog ? 28 : 18)
        Layout.preferredWidth: Kirigami.Units.gridUnit * 25
        Layout.preferredHeight: Kirigami.Units.gridUnit * (root.analog ? 30 : 25)

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.smallSpacing * 2

            RowLayout {
                spacing: Kirigami.Units.smallSpacing * 2
                Kirigami.Icon {
                    source: "alien-thunder"
                    fallback: "network-transmit-receive"
                    Layout.preferredWidth: 28
                    Layout.preferredHeight: 28
                }
                ColumnLayout {
                    spacing: 0
                    PC.Label { text: "ALIEN THUNDER"; font.letterSpacing: 2; font.pixelSize: 10; opacity: 0.65 }
                    PC.Label { text: i18n("Network activity"); font.bold: true; font.pointSize: 13 }
                }
                Item { Layout.fillWidth: true }
                Rectangle { width: 7; height: 7; radius: 4; color: traffic.available ? root.upColor : Kirigami.Theme.negativeTextColor }
                PC.Label { text: i18n("Live"); opacity: 0.65; font.pointSize: 9 }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.largeSpacing
                Repeater {
                    model: ["download", "upload"]
                    delegate: SpeedGauge {
                        required property var modelData
                        Layout.fillWidth: true
                        analog: root.analog
                        title: modelData === "download" ? i18n("↓ Download") : i18n("↑ Upload")
                        tint: modelData === "download" ? root.downColor : root.upColor
                        value: traffic[modelData + "Average"]
                        maximum: root.gaugeMaximum(modelData)
                        ready: traffic.ready && traffic.available
                        alert: Plasmoid.configuration.showAlerts && root.nearPeak(modelData)
                        reading: ready ? root.rate(value) : "—"
                        scaleLabel: i18n("10 s average · Auto: 0 – %1", root.rate(maximum))
                    }
                }
            }

            RowLayout {
                PC.Label { text: i18n("Show in the overlay:"); Layout.fillWidth: true }
                Repeater {
                    model: ["download", "upload"]
                    delegate: PC.CheckBox {
                        required property string modelData
                        text: modelData === "download" ? i18n("Download") : i18n("Upload")
                        checked: !!root.overlayItems[modelData]
                        onToggled: overlayCommands.toggle(modelData, checked)
                    }
                }
            }

            RowLayout {
                PC.Label { text: i18n("Applications"); font.bold: true; Layout.fillWidth: true }
                PC.ToolButton {
                    text: "↓"
                    checkable: true
                    checked: traffic.sortBy === "download"
                    onClicked: Plasmoid.configuration.sortBy = "download"
                    Accessible.name: i18n("Sort by download")
                    QQC2.ToolTip.text: Accessible.name
                    QQC2.ToolTip.visible: hovered
                }
                PC.ToolButton {
                    text: "↑"
                    checkable: true
                    checked: traffic.sortBy === "upload"
                    onClicked: Plasmoid.configuration.sortBy = "upload"
                    Accessible.name: i18n("Sort by upload")
                    QQC2.ToolTip.text: Accessible.name
                    QQC2.ToolTip.visible: hovered
                }
            }

            RowLayout {
                Layout.fillWidth: true
                PC.Label { text: i18n("Application"); opacity: 0.5; Layout.fillWidth: true; font.pointSize: 9 }
                PC.Label { text: i18n("Download"); color: root.downColor; Layout.preferredWidth: 92; horizontalAlignment: Text.AlignRight; font.pointSize: 9 }
                PC.Label { text: i18n("Upload"); color: root.upColor; Layout.preferredWidth: 92; horizontalAlignment: Text.AlignRight; font.pointSize: 9 }
            }

            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                Canvas {
                    id: graph
                    visible: Plasmoid.configuration.showGraph
                    anchors.fill: parent
                    opacity: 0.3
                    onWidthChanged: requestPaint()
                    onHeightChanged: requestPaint()
                    Connections {
                        target: traffic
                        function onHistoryChanged() { graph.requestPaint() }
                    }
                    onPaint: {
                        const ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)
                        const points = traffic.history
                        if (points.length < 2) return
                        const peak = Math.max(1024, ...points.map(p => Math.max(p.download, p.upload)))
                        for (const key of ["download", "upload"]) {
                            const tint = key === "download" ? root.downColor : root.upColor
                            ctx.strokeStyle = tint
                            ctx.lineWidth = key === "download" ? 2 : 1
                            ctx.beginPath()
                            const firstX = (45 - points.length) * width / 44
                            for (let n = 0; n < points.length; ++n) {
                                const x = (45 - points.length + n) * width / 44
                                const y = height - 2 - points[n][key] / peak * (height - 4)
                                if (n === 0) ctx.moveTo(x, y)
                                else ctx.lineTo(x, y)
                            }
                            ctx.stroke()
                            ctx.lineTo(width, height)
                            ctx.lineTo(firstX, height)
                            ctx.closePath()
                            ctx.fillStyle = Qt.alpha(tint, 0.18)
                            ctx.fill()
                        }
                    }
                }
                ListView {
                    id: appList
                    anchors.fill: parent
                    clip: true
                    model: traffic.applications
                    spacing: 3
                    QQC2.ScrollBar.vertical: QQC2.ScrollBar { }
                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        width: appList.width
                        height: 38
                        radius: 5
                        color: index % 2 === 0 ? Qt.alpha(Kirigami.Theme.textColor, 0.035) : "transparent"
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 5
                            anchors.rightMargin: 5
                            spacing: 7
                            Kirigami.Icon { source: modelData.icon; Layout.preferredWidth: 22; Layout.preferredHeight: 22 }
                            PC.Label {
                                text: modelData.name
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                                QQC2.ToolTip.text: text
                                QQC2.ToolTip.visible: nameHover.hovered
                                HoverHandler { id: nameHover }
                            }
                            PC.Label { text: root.rate(modelData.download); color: modelData.download > 0 ? root.downColor : Kirigami.Theme.disabledTextColor; Layout.preferredWidth: 87; horizontalAlignment: Text.AlignRight; font.pointSize: 9 }
                            PC.Label { text: root.rate(modelData.upload); color: modelData.upload > 0 ? root.upColor : Kirigami.Theme.disabledTextColor; Layout.preferredWidth: 87; horizontalAlignment: Text.AlignRight; font.pointSize: 9 }
                        }
                    }
                    PC.Label {
                        anchors.centerIn: parent
                        width: parent.width - 20
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        opacity: 0.65
                        visible: !traffic.available || !traffic.ready || appList.count === 0
                        text: !traffic.available ? i18n("Network monitoring is unavailable. Check the KDE System Monitor installation.")
                              : !traffic.ready ? i18n("Measuring network activity…") : i18n("No applications transferring data")
                    }
                }
            }

            RowLayout {
                PC.Label {
                    text: i18n("Application traffic · 2 s")
                    font.pointSize: 8
                    opacity: 0.5
                    Layout.fillWidth: true
                }
                PC.CheckBox {
                    text: i18n("Show idle")
                    checked: traffic.showIdle
                    onToggled: Plasmoid.configuration.showIdle = checked
                    font.pointSize: 9
                }
            }
        }
    }
}
