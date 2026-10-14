import QtQuick
import QtTest
import "../../alien_thunder" as Alien

TestCase {
    name: "OverlayReadings"
    when: windowShown
    width: 900
    height: 240

    Component { id: barComponent; Alien.BarContent {} }
    Component { id: networkComponent; Alien.NetworkData {} }
    Component {
        id: trafficComponent
        Item {
            property bool available: true
            property bool ready: true
            property real downloadAverage: 2048
            property real uploadAverage: 1048576
            property var gaugeHistory: [{download: 4096, upload: 1048576}, {download: 2048, upload: 1048576}]
        }
    }
    function createBar(style, items) {
        const bar = createTemporaryObject(barComponent, this, {
            backend: {config: {style: style, items: items},
                values: {cpu_load: 95}, items: ["cpu_load", "download", "upload"],
                labels: {cpu_load: "CPU", download: "Download", upload: "Upload"}}
        })
        verify(bar !== null)
        return bar
    }
    function test_sensorOnlyDoesNotLoadNetwork() {
        const bar = createBar("analog", {cpu_load: true})
        const collector = findChild(bar, "networkCollector")
        compare(collector.active, false)
        compare(collector.item, null)
        compare(bar.reading("cpu_load"), "95")
        verify(bar.usageAlert("cpu_load"))
    }
    function test_desktopUsesOneRowAndIndependentStyle() {
        const bar = createBar("analog", {cpu_load: true, download: true, upload: true})
        bar.showClose = false
        bar.showHandle = false
        compare(bar.implicitHeight, 198)
        verify(bar.implicitWidth > bar.implicitHeight * 2)
        const backend = bar.backend
        bar.backend = {config: {style: "digital", items: {cpu_load: true}},
            values: backend.values, items: backend.items, labels: backend.labels}
        compare(bar.implicitHeight, 56)
        compare(findChild(bar, "networkCollector").active, false)
    }
    function test_networkTenSecondMovingAverage() {
        const traffic = createTemporaryObject(networkComponent, this)
        verify(traffic !== null)
        verify(traffic.available)
        traffic.ready = true
        traffic.download = 1000
        traffic.upload = 500
        traffic.recordSample()
        compare(traffic.downloadAverage, 1000)
        for (let i = 0; i < 4; ++i) {
            traffic.download = 0
            traffic.upload = 0
            traffic.recordSample()
        }
        compare(traffic.downloadAverage, 200)
        compare(traffic.uploadAverage, 100)
        compare(traffic.history[0].download, 1000)
        traffic.recordSample()
        compare(traffic.downloadAverage, 0)
        compare(traffic.uploadAverage, 0)
        traffic.download = 100
        traffic.upload = 50
        for (let i = 0; i < 50; ++i) traffic.recordSample()
        compare(traffic.downloadAverage, 100)
        compare(traffic.uploadAverage, 50)
        compare(traffic.history.length, 45)
        compare(traffic.gaugeHistory.length, 45)
    }
    function test_networkFormatsAndAvailability_data() {
        return [{tag: "digital", style: "digital"}, {tag: "analog", style: "analog"}]
    }
    function test_networkFormatsAndAvailability(data) {
        const bar = createBar(data.style, {download: true, upload: true})
        const collector = findChild(bar, "networkCollector")
        collector.source = ""
        collector.sourceComponent = trafficComponent
        tryCompare(collector, "status", Loader.Ready)
        compare(bar.reading("download"), "2.0")
        compare(bar.unit("download"), "KiB/s")
        compare(bar.maximum("download"), 4096)
        compare(bar.reading("upload"), "1.0")
        compare(bar.unit("upload"), "MiB/s")
        verify(!bar.usageAlert("download"))
        verify(bar.usageAlert("upload"))
        const width = bar.implicitWidth
        collector.item.downloadAverage = 10 * 1048576
        wait(20)
        compare(bar.unit("download"), "MiB/s")
        compare(bar.implicitWidth, width)
        collector.item.available = false
        compare(bar.reading("download"), "--")
        verify(!bar.usageAlert("upload"))
    }
}
