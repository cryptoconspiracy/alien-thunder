import QtQuick
import QtQuick.Window
import org.kde.layershell as LayerShell

Window {
    id: bar

    required property var overlay
    required property var backend

    property int mx: 0
    property int my: 0
    property int ox: 0  // the top-left corner of the screen the bar is on
    property int oy: 0
    property int frame: 0
    readonly property var targetScreen: backend.screens.find(s => s.name === backend.config.screen) || backend.screens[0]
    readonly property real maximumScale: Math.min(2.5, targetScreen.width / content.implicitWidth,
                                                 targetScreen.height / content.implicitHeight)
    readonly property real minimumScale: Math.min(0.5, maximumScale)
    readonly property real uiScale: Math.min(backend.config.scale, maximumScale)

    // Set once. A layer surface that changes size can be left without a screen for a
    // moment, and Qt crashes on it; showing other readings restarts the overlay instead.
    width: 1
    height: 1
    color: "transparent"
    visible: false

    LayerShell.Window.scope: "alien-thunder-overlay"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorTop | LayerShell.Window.AnchorLeft
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone
    LayerShell.Window.exclusionZone: -1

    function setMargins() {
        LayerShell.Window.margins.left = mx
        LayerShell.Window.margins.top = my
        // New margins only reach the compositor with the next frame, so something on
        // screen has to change with them.
        frame++
    }

    // Never hidden and shown again to move: hiding destroys the surface, and Qt can still
    // deliver a pending repaint to it afterwards, which crashed the overlay. The screen is
    // set once, before the surface exists; moving to another screen restarts the overlay.
    function place(pos, first) {
        ox = pos.ox
        oy = pos.oy
        mx = pos.x
        my = pos.y
        if (first)
            LayerShell.Window.screen = backend.screenObject(pos.screen)
        setMargins()
    }

    Component.onCompleted: {
        width = Math.ceil(content.implicitWidth * uiScale)
        height = Math.ceil(content.implicitHeight * uiScale)
        place(backend.restore(bar), true)
        visible = true
    }

    BarContent {
        id: content
        width: implicitWidth
        height: implicitHeight
        scale: bar.uiScale
        transformOrigin: Item.TopLeft
        backend: bar.backend
        opacity: bar.overlay.dragging || resizeArea.pressed ? 0.55 : 1.0
        onCloseClicked: bar.backend.close()
    }

    // While dragging, a bright frame says "let go anywhere".
    Rectangle {
        anchors.fill: parent
        radius: 10
        color: "transparent"
        border.width: 2
        border.color: "#ff6a00"
        visible: bar.overlay.dragging || resizeArea.pressed
    }

    // Changes with every move so the new margins go out with a fresh frame.
    Rectangle {
        width: 1
        height: 1
        color: bar.frame % 2 ? "#01000000" : "#02000000"
    }

    MouseArea {
        id: drag
        anchors.fill: parent
        anchors.rightMargin: 30 * bar.uiScale  // the ✕ has its own mouse area
        cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
        property point start

        // The bar doesn't move while the button is down, so these coordinates stay
        // true for the whole drag.
        onPressed: (m) => start = Qt.point(m.x, m.y)
        onPositionChanged: (m) => {
            const dx = m.x - start.x
            const dy = m.y - start.y
            if (!bar.overlay.dragging && Math.abs(dx) + Math.abs(dy) < 4)
                return
            bar.overlay.dropX = bar.ox + bar.mx + dx
            bar.overlay.dropY = bar.oy + bar.my + dy
            bar.overlay.dragging = true
        }
        onReleased: {
            if (!bar.overlay.dragging)
                return
            const r = bar.backend.drop(bar, Math.round(bar.overlay.dropX), Math.round(bar.overlay.dropY))
            if (r.moved) {
                bar.backend.relaunch()
                return
            }
            bar.overlay.dragging = false
            bar.place(r, false)
        }
        onCanceled: bar.overlay.dragging = false
    }

    Text {
        anchors.centerIn: parent
        visible: resizeArea.pressed
        text: Math.round(resizeArea.nextScale * 100) + "%"
        color: "#ff6a00"
        font.pixelSize: 20
        font.bold: true
        style: Text.Outline
        styleColor: "#0b0d10"
    }

    // Keep the surface fixed during the gesture; recreate it at the saved size on release.
    MouseArea {
        id: resizeArea
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        width: Math.max(16, 18 * bar.uiScale)
        height: Math.max(14, 16 * bar.uiScale)
        cursorShape: Qt.SizeFDiagCursor
        hoverEnabled: true
        property point start
        property real nextScale: bar.uiScale
        onPressed: (m) => {
            start = Qt.point(m.x, m.y)
            nextScale = bar.uiScale
        }
        onPositionChanged: (m) => {
            if (!pressed) return
            const dx = (m.x - start.x) / content.implicitWidth
            const dy = (m.y - start.y) / content.implicitHeight
            const delta = Math.abs(dx) > Math.abs(dy) ? dx : dy
            nextScale = Math.max(bar.minimumScale, Math.min(bar.maximumScale, bar.uiScale + delta))
        }
        onReleased: bar.backend.resize(nextScale)
        Accessible.role: Accessible.Grip
        Accessible.name: qsTr("Resize overlay")
        Text {
            anchors.centerIn: parent
            text: "◢"
            font.pixelSize: 12
            color: resizeArea.containsMouse ? "#ff6a00" : "#5c6b77"
        }
    }
}
