import QtQuick

// Shared instrument face; bundled into the Plasma widget by make/install.sh.
Canvas {
    id: dial
    property real value: 0
    property real maximum: 100
    property real divisor: 1
    property string unit: "%"
    property color tint: "#ff6a00"
    property bool ready: true
    property bool compact: false
    readonly property real fraction: ready ? Math.max(0, Math.min(1, value / maximum)) : 0
    property real displayedFraction: fraction
    Behavior on displayedFraction { NumberAnimation { duration: 350; easing.type: Easing.OutCubic } }
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onDisplayedFractionChanged: requestPaint()
    onMaximumChanged: requestPaint()
    onDivisorChanged: requestPaint()
    onUnitChanged: requestPaint()
    onTintChanged: requestPaint()
    onCompactChanged: requestPaint()
    onPaint: {
        const ctx = getContext("2d")
        ctx.clearRect(0, 0, width, height)
        const radius = Math.max(1, Math.min(width, height) / 2 - 5)
        const cx = width / 2
        const cy = height / 2
        const start = Math.PI * 0.75
        const sweep = Math.PI * 1.5
        const angleAt = fraction => start + sweep * fraction
        ctx.fillStyle = "#080a0d"
        ctx.beginPath()
        ctx.arc(cx, cy, radius, 0, 2 * Math.PI)
        ctx.fill()
        ctx.lineWidth = 2
        ctx.lineCap = "round"
        ctx.strokeStyle = "#626872"
        ctx.beginPath()
        ctx.arc(cx, cy, radius, start, start + sweep)
        ctx.stroke()
        ctx.lineWidth = 3
        if (dial.displayedFraction > 0) {
            ctx.strokeStyle = Qt.alpha(dial.tint, 0.7)
            ctx.beginPath()
            ctx.arc(cx, cy, radius - 4, start, angleAt(dial.displayedFraction))
            ctx.stroke()
        }
        for (let n = 0; n <= 40; ++n) {
            if (dial.compact && n % 5 !== 0) continue
            const major = n % 10 === 0
            const a = angleAt(n / 40)
            ctx.lineWidth = major ? 2 : 1
            ctx.strokeStyle = major ? "#f4f5f7" : "#737983"
            ctx.beginPath()
            const outside = radius - (dial.compact ? 3 : 9)
            const inside = dial.compact ? radius * (major ? 0.55 : 0.7) : radius - (major ? 19 : 14)
            ctx.moveTo(cx + Math.cos(a) * outside, cy + Math.sin(a) * outside)
            ctx.lineTo(cx + Math.cos(a) * inside, cy + Math.sin(a) * inside)
            ctx.stroke()
            if (major && !dial.compact) {
                const divisor = dial.divisor
                const number = dial.maximum / divisor * n / 40
                ctx.font = "bold " + Math.max(9, Math.round(radius * 0.16)) + "px sans-serif"
                ctx.textAlign = "center"
                ctx.textBaseline = "middle"
                ctx.fillStyle = "#f4f5f7"
                ctx.fillText(Number(number.toFixed(2)).toString(),
                             cx + Math.cos(a) * (radius - 29), cy + Math.sin(a) * (radius - 29))
            }
        }
        const angle = angleAt(dial.displayedFraction)
        ctx.save()
        ctx.translate(cx, cy)
        ctx.rotate(angle)
        ctx.fillStyle = "#ff3344"
        ctx.beginPath()
        ctx.moveTo(dial.compact ? -3 : -10, dial.compact ? -1.5 : -2.5)
        ctx.lineTo(radius - (dial.compact ? 5 : 20), 0)
        ctx.lineTo(dial.compact ? -3 : -10, dial.compact ? 1.5 : 2.5)
        ctx.closePath()
        ctx.fill()
        ctx.restore()
        ctx.fillStyle = "#22262d"
        ctx.beginPath()
        ctx.arc(cx, cy, dial.compact ? 3 : 6, 0, 2 * Math.PI)
        ctx.fill()
        ctx.fillStyle = "#aeb4bd"
        ctx.font = "10px sans-serif"
        ctx.textAlign = "center"
        if (!dial.compact) ctx.fillText(dial.unit, cx, cy + radius * 0.62)
    }
}

