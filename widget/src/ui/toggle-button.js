import { animate } from './animations.js';
import { refreshInteractiveGeometry } from './interactions.js'

function isWidgetOpen(container) {
    return getComputedStyle(container).display !== "none";
}

function openWidget(container) {
    if (isWidgetOpen(container)) {
        return;
    }

    container.style.display = "flex";
    container.style.opacity = "0";

    requestAnimationFrame(() => {
        animate(
            container,
            () => {
                container.style.opacity = "1";
            },
            () => {
                refreshInteractiveGeometry(container);
            }
        );
    });
}

function closeWidget(container) {
    if (!isWidgetOpen(container)) {
        return;
    }

    animate(
        container,
        () => {
            container.style.opacity = "0";
        },
        () => {
            container.style.display = "none";
        }
    );
}

function toggleWidget(container) {
    if (isWidgetOpen(container)) {
        closeWidget(container);
        return false;
    }

    openWidget(container);
    return true;
}

export function createToggleButton(container) {
    const btn = document.createElement('div');
    btn.id = 'chatbot-toggle-btn';
    btn.className = 'aicc-chatbot-toggle-btn';
    btn.innerText = '💬';

    btn.addEventListener('mouseenter', () => {
        btn.style.transform = 'scale(1.06)';
    });

    btn.addEventListener('mouseleave', () => {
        btn.style.transform = 'scale(1)';
    });

    btn.addEventListener("click", () => {
        const isOpen = toggleWidget(container);
        btn.innerText = isOpen ? "✕" : "💬";
    });

    document.body.appendChild(btn);
    return btn;
}