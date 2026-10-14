import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    property string cfg_desktop_orientation: "horizontal"
    property string cfg_desktop_orientationDefault
    property string cfg_panel_style: "digital"
    property string cfg_panel_styleDefault
    property alias cfg_panel_download: panelDownload.checked
    property alias cfg_panel_upload: panelUpload.checked
    property bool cfg_panel_downloadDefault
    property bool cfg_panel_uploadDefault
    property string cfg_desktop_style: "analog"
    property string cfg_desktop_styleDefault
    property alias cfg_desktop_download: desktopDownload.checked
    property alias cfg_desktop_upload: desktopUpload.checked
    property bool cfg_desktop_downloadDefault
    property bool cfg_desktop_uploadDefault
    property alias cfg_desktop_cpu_temp: desktop0.checked
    property bool cfg_desktop_cpu_tempDefault
    property alias cfg_desktop_cpu_load: desktop1.checked
    property bool cfg_desktop_cpu_loadDefault
    property alias cfg_desktop_gpu_temp: desktop2.checked
    property bool cfg_desktop_gpu_tempDefault
    property alias cfg_desktop_gpu_mem: desktop3.checked
    property bool cfg_desktop_gpu_memDefault
    property alias cfg_desktop_cpu_fan: desktop4.checked
    property bool cfg_desktop_cpu_fanDefault
    property alias cfg_desktop_gpu_fan: desktop5.checked
    property bool cfg_desktop_gpu_fanDefault
    property alias cfg_desktop_ram: desktop6.checked
    property bool cfg_desktop_ramDefault
    property alias cfg_desktop_ram_gb: desktop7.checked
    property bool cfg_desktop_ram_gbDefault
    property string cfg_overlay_style: "digital"
    property string cfg_overlay_styleDefault
    property alias cfg_overlay_download: overlayDownload.checked
    property alias cfg_overlay_upload: overlayUpload.checked
    property bool cfg_overlay_downloadDefault
    property bool cfg_overlay_uploadDefault
    property alias cfg_panel_cpu_temp: panelCpuTemp.checked
    property alias cfg_panel_cpu_load: panelCpuLoad.checked
    property alias cfg_panel_gpu_temp: panelGpuTemp.checked
    property alias cfg_panel_gpu_mem: panelGpuMem.checked
    property alias cfg_panel_cpu_fan: panelCpuFan.checked
    property alias cfg_panel_gpu_fan: panelGpuFan.checked
    property alias cfg_panel_ram: panelRam.checked
    property alias cfg_panel_ram_gb: panelRamGb.checked
    property alias cfg_overlay_cpu_temp: overlayCpuTemp.checked
    property alias cfg_overlay_cpu_load: overlayCpuLoad.checked
    property alias cfg_overlay_gpu_temp: overlayGpuTemp.checked
    property alias cfg_overlay_gpu_mem: overlayGpuMem.checked
    property alias cfg_overlay_cpu_fan: overlayCpuFan.checked
    property alias cfg_overlay_gpu_fan: overlayGpuFan.checked
    property alias cfg_overlay_ram: overlayRam.checked
    property alias cfg_overlay_ram_gb: overlayRamGb.checked
    property bool cfg_panel_cpu_tempDefault
    property bool cfg_panel_cpu_loadDefault
    property bool cfg_panel_gpu_tempDefault
    property bool cfg_panel_gpu_memDefault
    property bool cfg_panel_cpu_fanDefault
    property bool cfg_panel_gpu_fanDefault
    property bool cfg_panel_ramDefault
    property bool cfg_panel_ram_gbDefault
    property bool cfg_overlay_cpu_tempDefault
    property bool cfg_overlay_cpu_loadDefault
    property bool cfg_overlay_gpu_tempDefault
    property bool cfg_overlay_gpu_memDefault
    property bool cfg_overlay_cpu_fanDefault
    property bool cfg_overlay_gpu_fanDefault
    property bool cfg_overlay_ramDefault
    property bool cfg_overlay_ram_gbDefault

    Kirigami.FormLayout {
        QQC2.ComboBox {
            Kirigami.FormData.label: i18n("Desktop orientation:")
            model: [i18n("Horizontal"), i18n("Vertical")]
            currentIndex: cfg_desktop_orientation === "vertical" ? 1 : 0
            onActivated: cfg_desktop_orientation = currentIndex === 1 ? "vertical" : "horizontal"
        }
        QQC2.ComboBox {
            Kirigami.FormData.label: i18n("Desktop gauge style:")
            model: [i18n("Digital"), i18n("Analog · Audi style")]
            currentIndex: cfg_desktop_style === "analog" ? 1 : 0
            onActivated: cfg_desktop_style = currentIndex === 1 ? "analog" : "digital"
        }
        QQC2.CheckBox { id: desktop0; Kirigami.FormData.label: i18n("Show on the desktop:"); text: i18n("CPU temperature") }
        QQC2.CheckBox { id: desktop1; text: i18n("CPU load") }
        QQC2.CheckBox { id: desktop2; text: i18n("GPU temperature") }
        QQC2.CheckBox { id: desktop3; text: i18n("GPU memory (VRAM) in use") }
        QQC2.CheckBox { id: desktop4; text: i18n("CPU fan speed") }
        QQC2.CheckBox { id: desktop5; text: i18n("GPU fan speed") }
        QQC2.CheckBox { id: desktop6; text: i18n("Memory in use") }
        QQC2.CheckBox { id: desktop7; text: i18n("Memory in use, in GB") }
        QQC2.CheckBox { id: desktopDownload; text: i18n("Download") }
        QQC2.CheckBox { id: desktopUpload; text: i18n("Upload") }
        Item { Kirigami.FormData.isSection: true }
        QQC2.ComboBox {
            Kirigami.FormData.label: i18n("Overlay and network gauges:")
            model: [i18n("Digital"), i18n("Analog · Audi style")]
            currentIndex: cfg_overlay_style === "analog" ? 1 : 0
            onActivated: cfg_overlay_style = currentIndex === 1 ? "analog" : "digital"
        }
        Item { Kirigami.FormData.isSection: true }
        OverlaySizeControl {
            Kirigami.FormData.label: i18n("Overlay size:")
        }
        Item { Kirigami.FormData.isSection: true }
        QQC2.ComboBox {
            Kirigami.FormData.label: i18n("Panel gauge style:")
            model: [i18n("Digital"), i18n("Analog · Audi style")]
            currentIndex: cfg_panel_style === "analog" ? 1 : 0
            onActivated: cfg_panel_style = currentIndex === 1 ? "analog" : "digital"
        }
        QQC2.CheckBox { id: panelCpuTemp; Kirigami.FormData.label: i18n("Show on the panel:"); text: i18n("CPU temperature") }
        QQC2.CheckBox { id: panelCpuLoad; text: i18n("CPU load") }
        QQC2.CheckBox { id: panelGpuTemp; text: i18n("GPU temperature") }
        QQC2.CheckBox { id: panelGpuMem; text: i18n("GPU memory (VRAM) in use") }
        QQC2.CheckBox { id: panelCpuFan; text: i18n("CPU fan speed") }
        QQC2.CheckBox { id: panelGpuFan; text: i18n("GPU fan speed") }
        QQC2.CheckBox { id: panelRam; text: i18n("Memory in use") }
        QQC2.CheckBox { id: panelRamGb; text: i18n("Memory in use, in GB") }
        QQC2.CheckBox { id: panelDownload; text: i18n("Download") }
        QQC2.CheckBox { id: panelUpload; text: i18n("Upload") }

        Item { Kirigami.FormData.isSection: true }

        QQC2.CheckBox { id: overlayCpuTemp; Kirigami.FormData.label: i18n("Show in the overlay:"); text: i18n("CPU temperature") }
        QQC2.CheckBox { id: overlayCpuLoad; text: i18n("CPU load") }
        QQC2.CheckBox { id: overlayGpuTemp; text: i18n("GPU temperature") }
        QQC2.CheckBox { id: overlayGpuMem; text: i18n("GPU memory (VRAM) in use") }
        QQC2.CheckBox { id: overlayCpuFan; text: i18n("CPU fan speed") }
        QQC2.CheckBox { id: overlayGpuFan; text: i18n("GPU fan speed") }
        QQC2.CheckBox { id: overlayRam; text: i18n("Memory in use") }
        QQC2.CheckBox { id: overlayRamGb; text: i18n("Memory in use, in GB") }
        QQC2.CheckBox { id: overlayDownload; text: i18n("Download") }
        QQC2.CheckBox { id: overlayUpload; text: i18n("Upload") }
    }
}
