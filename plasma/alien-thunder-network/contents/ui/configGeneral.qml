import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    id: page
    property string cfg_gaugeStyle: "inherit"
    property string cfg_gaugeStyleDefault
    property string cfg_sortBy: "upload"
    property string cfg_sortByDefault
    property alias cfg_showIdle: idle.checked
    property bool cfg_showIdleDefault
    property alias cfg_showGraph: graph.checked
    property bool cfg_showGraphDefault
    property alias cfg_showAlerts: alerts.checked
    property bool cfg_showAlertsDefault

    Kirigami.FormLayout {
        QQC2.ComboBox {
            Kirigami.FormData.label: i18n("Gauge style:")
            model: [i18n("Follow Alien Thunder"), i18n("Digital"), i18n("Analog · Audi style")]
            implicitContentWidthPolicy: QQC2.ComboBox.WidestText
            currentIndex: page.cfg_gaugeStyle === "analog" ? 2 : page.cfg_gaugeStyle === "digital" ? 1 : 0
            onActivated: page.cfg_gaugeStyle = ["inherit", "digital", "analog"][currentIndex]
        }
        QQC2.ComboBox {
            Kirigami.FormData.label: i18n("Sort applications by:")
            model: [i18n("Download"), i18n("Upload")]
            implicitContentWidthPolicy: QQC2.ComboBox.WidestText
            currentIndex: page.cfg_sortBy === "download" ? 0 : 1
            onActivated: page.cfg_sortBy = currentIndex === 0 ? "download" : "upload"
        }
        QQC2.CheckBox {
            id: idle
            text: i18n("Show idle applications")
        }
        Item { Kirigami.FormData.isSection: true }
        QQC2.CheckBox {
            id: graph
            text: i18n("Show graph behind the application list")
        }
        QQC2.CheckBox {
            id: alerts
            text: i18n("Blink red LED near the observed peak")
        }
        QQC2.Label {
            text: i18n("The alert starts at 90% of each direction's peak over the last 90 seconds, not the connection's capacity.")
            wrapMode: Text.WordWrap
            Kirigami.FormData.isSection: true
        }
    }
}
