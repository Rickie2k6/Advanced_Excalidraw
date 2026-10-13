import interact from 'interactjs';

export function getGeometry(container) {
    return container._geometry;
}


export function captureGeometry(container) {
    const rect = container.getBoundingClientRect();

    container._geometry = {
        left: rect.left,
        top: rect.top,
        width: rect.width,
        height: rect.height,
    };

    return container._geometry;
}


export function applyGeometry(container, geometry = getGeometry(container)) {
    Object.assign(container.style, {
        left: `${geometry.left}px`,
        top: `${geometry.top}px`,
        width: `${geometry.width}px`,
        height: `${geometry.height}px`,
        right: "auto",
        bottom: "auto",
    });
}


export function clearGeometry(container) {
    container._geometry = null;

    Object.assign(container.style, {
        left: "",
        top: "",
        width: "",
        height: "",
        right: "",
        bottom: ""
    });
}


export function enterInteractiveMode(container) {
    const geometry = captureGeometry(container);

    Object.assign(container.style, {
        transform: "none",
        left: `${geometry.left}px`,
        top: `${geometry.top}px`,
        width: `${geometry.width}px`,
        height: `${geometry.height}px`,
        right: "auto",
        bottom: "auto",
    });

    return geometry;
}


export function exitInteractiveMode(container) {
    clearGeometry(container);
    container.style.transform = "";

    return null;
}


export function setupInteractions(container, header) {
    const dragInstance = interact(container).draggable({
        allowFrom: '.aicc-chat-widget-header',
        inertia: false,
        enabled: false,
        modifiers: [
            interact.modifiers.restrictRect({
                restriction: 'parent',
                endOnly: true
            })
        ],
        listeners: {
            start() {
                container.classList.remove("aicc-animating");
            },

            move(event) {
                const geometry = getGeometry(container);

                geometry.left += event.dx;
                geometry.top += event.dy;

                applyGeometry(container, geometry);
            }
        }
    });

    const resizeInstance = interact(container).resizable({
        edges: { left: true, right: true, top: true, bottom: true },
        enabled: false,
        modifiers: [
            interact.modifiers.restrictSize({
                min: { width: 340, height: 320 },
                max: { width: 1100, height: 900 }
            })
        ],
        listeners: {
            move(event) {
                const geometry = getGeometry(container);

                geometry.left += event.deltaRect.left;
                geometry.top += event.deltaRect.top;

                geometry.width = event.rect.width;
                geometry.height = event.rect.height;

                applyGeometry(container, geometry);
            }
        }
    });

    function setEnabled(enabled) {
        if (enabled) {
            captureGeometry(container);
            applyGeometry(container);

            container.classList.remove("aicc-animating");
        }

        dragInstance.draggable({ enabled });
        resizeInstance.resizable({ enabled });

        header.style.cursor = enabled ? "grab" : "default";
    }

    return {
        setEnabled
    };
}

export function refreshInteractiveGeometry(container) {
    if (!container.classList.contains("aicc-is-expanded")) {
        return;
    }

    // Re-read actual DOM position after display:none -> flex
    captureGeometry(container);

    // Re-apply it so Interact and DOM are synchronized
    applyGeometry(container);
}
