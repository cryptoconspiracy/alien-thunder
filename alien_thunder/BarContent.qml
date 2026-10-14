import QtQuick

// What the bar shows: the readings side by side, and the ✕ when showClose is set.
Item {
    id: content

    required property var backend
    property bool showClose: true
    property bool showHandle: true
    property bool vertical: false
    readonly property bool analog: backend.config.style === "analog"
    signal closeClicked()

    // Load the optional KDE collector only when a network reading is selected.
    Loader {
        id: network
        objectName: "networkCollector"
        active: !!(content.backend.config.items.download || content.backend.config.items.upload)
        source: "NetworkData.qml"
    }

    function isNetwork(key) { return key === "download" || key === "upload" }
    function value(key) {
        if (isNetwork(key))
            return network.item && network.item.available && network.item.ready ? network.item[key + "Average"] : null
        return backend.values[key]
    }
    function divisor(key) {
        if (isNetwork(key)) return maximum(key) >= 1048576 ? 1048576 : 1024
        return key.endsWith("_fan") ? 1000 : 1
    }
    function reading(key) {
        const v = value(key)
        if (v === undefined || v === null) return "--"
        return isNetwork(key) ? (v / divisor(key)).toFixed(1) : String(v)
    }

    function usageAlert(key) {
        if (isNetwork(key)) {
            if (!network.item || value(key) === null) return false
            const history = network.item.gaugeHistory
            const peak = Math.max(0, ...history.map(p => p[key]))
            return history.length >= 2 && value(key) > 0 && value(key) >= peak * 0.9
        }
        if (key === "ram_gb") key = "ram"
        return ["cpu_load", "gpu_mem", "ram"].includes(key) && backend.values[key] > 90
    }

    implicitWidth: row.implicitWidth
    implicitHeight: row.implicitHeight

    function maximum(key) {
        if (isNetwork(key)) {
            const history = network.item ? network.item.gaugeHistory : []
            const peak = Math.max(1024, value(key) || 0, ...history.map(p => p[key]))
            return Math.pow(2, Math.ceil(Math.log2(peak)))
        }
        if (key.endsWith("_temp")) return 120
        if (key.endsWith("_fan")) return Math.max(8000, Math.ceil((backend.values[key] || 0) / 2000) * 2000)
        if (key === "ram_gb") return backend.values.ram_total_gb || 32
        return 100
    }

    function unit(key) {
        if (isNetwork(key)) return divisor(key) === 1048576 ? "MiB/s" : "KiB/s"
        if (key.endsWith("_temp")) return "°C"
        if (key.endsWith("_fan")) return "rpm"
        if (key === "ram_gb") return "GB / " + (backend.values.ram_total_gb || "?")
        return "%"
    }

    function severity(key) {
        const v = backend.values[key]
        if (v === undefined || v === null) return 0
        if (key.endsWith("_temp")) return v >= 90 ? 2 : v >= 75 ? 1 : 0
        if (key === "ram" || key === "gpu_mem") return v >= 95 ? 2 : v >= 85 ? 1 : 0
        return 0
    }

    Rectangle {
        anchors.fill: parent
        radius: 10
        color: "#e00b0d10"
        border.width: 1
        border.color: "#33ff6a00"
    }

    Grid {
        id: row
        columns: content.vertical ? 1 : content.backend.items.length + 2
        leftPadding: 6
        rightPadding: content.showClose ? 4 : 12

        Text {
            visible: content.showHandle
            width: 14
            height: content.analog ? 198 : 56
            text: "⋮"
            font.pixelSize: 22
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            color: "#5c6b77"
        }

        Repeater {
            model: content.backend.items.filter(k => content.backend.config.items[k])
            delegate: Row {
                required property string modelData
                required property int index
                height: content.analog ? 198 : 56

                Rectangle {
                    visible: index > 0 && !content.vertical
                    width: 1
                    height: parent.height - 20
                    anchors.verticalCenter: parent.verticalCenter
                    color: "#2a3a44"
                }

                Item {
                    width: content.analog ? 148 : readout.implicitWidth + 24
                    height: parent.height

                    Column {
                        visible: content.analog
                        anchors.centerIn: parent
                        spacing: 3
                        Item {
                            width: 140
                            height: 14
                            Row {
                                anchors.centerIn: parent
                                spacing: 5
                                Text {
                                    text: content.backend.labels[modelData].toUpperCase()
                                    color: "#aeb4bd"
                                    font.pixelSize: 11
                                    font.bold: true
                                    font.letterSpacing: 1
                                }
                                AlertLed { anchors.verticalCenter: parent.verticalCenter; active: content.usageAlert(modelData) }
                            }
                        }
                        AnalogDial {
                            width: 140
                            height: 140
                            ready: content.value(modelData) !== undefined && content.value(modelData) !== null
                            value: content.value(modelData) || 0
                            maximum: content.maximum(modelData)
                            divisor: content.divisor(modelData)
                            unit: modelData.endsWith("_fan") ? "×1000 rpm" : modelData === "ram_gb" ? "GB" : content.unit(modelData)
                            tint: ["#ff6a00", "#ffb020", "#ff3b30"][content.severity(modelData)]
                        }
                        Text {
                            width: 140
                            text: content.reading(modelData) + " " + content.unit(modelData)
                            horizontalAlignment: Text.AlignHCenter
                            color: ["#e8f7ff", "#ffb020", "#ff3b30"][content.severity(modelData)]
                            font.pixelSize: 14
                            font.bold: true
                        }
                    }

                    Row {
                        id: readout
                        visible: !content.analog
                        anchors.centerIn: parent
                        spacing: 8

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 1
                            Row {
                                spacing: 5
                                Text {
                                    text: content.backend.labels[modelData].toUpperCase()
                                    color: "#8a9ba8"
                                    font.pixelSize: 11
                                    font.bold: true
                                    font.letterSpacing: 1
                                }
                                AlertLed { anchors.verticalCenter: parent.verticalCenter; active: content.usageAlert(modelData) }
                            }
                            Text {
                                text: content.unit(modelData)
                                color: "#5c6b77"
                                font.pixelSize: 10
                            }
                        }

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            // Room for the widest reading, so a new digit never resizes the
                            // window: resizing a layer surface crashed Qt (no screen for a moment).
                            width: widest.advanceWidth
                            horizontalAlignment: Text.AlignRight
                            TextMetrics {
                                id: widest
                                font.family: "monospace"
                                font.pixelSize: 28
                                font.bold: true
                                text: content.isNetwork(modelData) ? "88888.8" : modelData.endsWith("_fan") ? "8888" : modelData === "ram_gb" ? "88.8" : "888"
                            }
                            text: content.reading(modelData)
                            color: ["#e8f7ff", "#ffb020", "#ff3b30"][content.severity(modelData)]
                            font.family: "monospace"
                            font.pixelSize: 28
                            font.bold: true
                        }
                    }
                }
            }
        }

        Item {
            visible: content.showClose
            width: 30
            height: content.analog ? 198 : 56

            Rectangle {
                anchors.centerIn: parent
                width: 22
                height: 22
                radius: 11
                color: closeArea.containsMouse ? "#ff3b30" : "transparent"
            }
            Text {
                anchors.centerIn: parent
                text: "✕"
                font.pixelSize: 13
                color: closeArea.containsMouse ? "white" : "#8a9ba8"
            }
            MouseArea {
                id: closeArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: content.closeClicked()
            }
        }
    }
}
