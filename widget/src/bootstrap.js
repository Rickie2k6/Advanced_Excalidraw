export function loadWidgetCSS() {
    const styles = [
        "widget.css",
        "header.css",
        "chat.css",
        "toggle-button.css"
    ];

    styles.forEach((file) => {
        const href = new URL(
            `./styles/${file}`,
            import.meta.url
        ).toString();

        const alreadyLoaded = [...document.styleSheets].some(
            (sheet) => sheet.href === href
        );

        if (alreadyLoaded) {
            return;
        }

        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = href;
        link.dataset.chatWidget = "true";

        document.head.appendChild(link);
    });
}

export function onDOMReady(callback) {
    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            callback,
            { once: true }
        );
    } else {
        callback();
    }
}