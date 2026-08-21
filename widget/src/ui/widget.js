import { createMessagesArea } from './chat/messages.js';
import { createInputArea } from './chat/input.js';
import { createHeader } from './header.js';
import {
    setupInteractions,
    captureGeometry,
    enterInteractiveMode,
    exitInteractiveMode,
    applyGeometry,
    clearGeometry,
    getGeometry
} from './interactions.js';
import { animate } from './animations.js';

import '../styles/header.css';
import '../styles/widget.css';
import '../styles/chat.css';
import '../styles/course-badge.css';
import '../styles/toggle-button.css';


function getFloatingGeometry(container) {
    const oldStyle = container.getAttribute("style") || "";
    const wasExpanded = container.classList.contains("aicc-is-expanded");

    container.classList.remove("aicc-is-expanded");
    clearGeometry(container);
    container.style.transform = "";

    const rect = container.getBoundingClientRect();

    container.classList.toggle("aicc-is-expanded", wasExpanded);
    container.setAttribute("style", oldStyle);

    return {
        left: rect.left,
        top: rect.top,
        width: rect.width,
        height: rect.height
    };
}

function readCurrentGeometry(container) {
    const rect = container.getBoundingClientRect();

    return {
        left: rect.left,
        top: rect.top,
        width: rect.width,
        height: rect.height
    };
}

function expandWidget(container, maximizeBtn, interactions) {
    if (container.classList.contains("aicc-is-expanded")) {
        return;
    }

    container.classList.add("aicc-is-expanded");
    maximizeBtn.textContent = '⤡';

    animate(container, () => { }, {
        properties: ["left", "top", "width", "height"],
        onFinish: () => {
            enterInteractiveMode(container);
            interactions.setEnabled(true);
        }
    });
}

function collapseWidget(container, maximizeBtn, interactions) {
    if (!container.classList.contains("aicc-is-expanded")) {
        return;
    }

    interactions.setEnabled(false);

    const currentGeometry = getGeometry(container) || captureGeometry(container);
    const targetGeometry = getFloatingGeometry(container);

    maximizeBtn.textContent = '⤢';

    applyGeometry(container, currentGeometry);

    animate(container, () => {
        requestAnimationFrame(() => {
            applyGeometry(container, targetGeometry);
        });
    }, {
        properties: ["left", "top", "width", "height"],
        onFinish: () => {
            container.classList.remove("aicc-is-expanded");
            exitInteractiveMode(container);
        }
    });
}

export function createChatWidget() {
    const container = document.createElement('div');
    container.id = 'aicc-chatbot-container';
    container.className = 'aicc-chatbot-container';

    const { header, maximizeBtn } = createHeader();

    const { messages } = createMessagesArea();

    const { inputBox, input, button } = createInputArea();

    container.appendChild(header);
    container.appendChild(messages);
    container.appendChild(inputBox);

    document.body.appendChild(container);

    const interactions = setupInteractions(container, header);

    maximizeBtn.addEventListener('click', (e) => {
        e.stopPropagation();

        if (container.classList.contains("aicc-is-expanded")) {
            collapseWidget(container, maximizeBtn, interactions);
        } else {
            expandWidget(container, maximizeBtn, interactions);
        }
    });

    return { messages, input, button, container };
}
