import QtQuick
import org.kde.ksysguard.process as Process

// Use the same per-process collector as Plasma System Monitor, including UDP.
// ApplicationDataModel combines an application's child processes using cgroups.
Item {
    id: root
    property string sortBy: "upload"
    property bool showIdle: false
    property var applications: []
    property real download: 0
    property real upload: 0
    property var history: []
    property real downloadAverage: 0
    property real uploadAverage: 0
    property var gaugeHistory: []
    property bool ready: false
    readonly property bool available: source.available
        && source.availableAttributes.includes("netInbound")
        && source.availableAttributes.includes("netOutbound")

    function refresh() {
        if (!available) {
            ready = false
            applications = []
            download = 0
            upload = 0
            history = []
            gaugeHistory = []
            downloadAverage = 0
            uploadAverage = 0
            return
        }
        let rows = []
        let received = 0
        let sent = 0
        for (let r = 0; r < source.rowCount(); ++r) {
            const value = c => source.data(source.index(r, c), Process.ProcessDataModel.Value)
            const down = Math.max(0, Number(value(2)) || 0)
            const up = Math.max(0, Number(value(3)) || 0)
            received += down
            sent += up
            if (showIdle || down > 0 || up > 0) {
                rows.push({name: String(value(0) || "?"), icon: String(value(1) || "application-x-executable"),
                           download: down, upload: up})
            }
        }
        rows.sort((a, b) => b[sortBy] - a[sortBy]
                  || (b.download + b.upload) - (a.download + a.upload)
                  || a.name.localeCompare(b.name))
        applications = rows
        download = received
        upload = sent
        ready = true
    }

    onSortByChanged: refresh()
    onShowIdleChanged: refresh()

    // Five 2-second samples. Only the timer adds samples: sorting the application
    // list must not shorten the smoothing window or add duplicate observations.
    function recordSample() {
        if (!available || !ready) return
        history = history.concat([{download: download, upload: upload}]).slice(-45)
        const recent = history.slice(-5)
        downloadAverage = recent.reduce((sum, p) => sum + p.download, 0) / recent.length
        uploadAverage = recent.reduce((sum, p) => sum + p.upload, 0) / recent.length
        gaugeHistory = gaugeHistory.concat([{download: downloadAverage, upload: uploadAverage}]).slice(-45)
    }

    Process.ApplicationDataModel {
        id: source
        enabled: true
        enabledAttributes: ["appName", "iconName", "netInbound", "netOutbound"]
    }

    Timer {
        interval: 2000
        running: true
        repeat: true
        onTriggered: {
            root.refresh()
            root.recordSample()
        }
    }
}
