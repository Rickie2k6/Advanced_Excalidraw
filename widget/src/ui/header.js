export function createHeader() {
    const header = document.createElement('div');
    header.className = 'aicc-chat-widget-header';
    header.setAttribute('data-drag-handle', 'true');

    const avatarWrapper = document.createElement('div');
    avatarWrapper.className = 'aicc-chat-avatar-wrapper';

    const avatar = document.createElement('div');
    avatar.className = 'aicc-chat-avatar';
    avatar.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg"
            width="22"
            height="22"
            fill="none"
            viewBox="0 0 24 24"
            stroke="white"
            stroke-width="2">
        <rect x="4" y="8" width="16" height="12" rx="3"/>
        <path d="M12 4v4"/>
        <circle cx="9" cy="13" r="1"/>
        <circle cx="15" cy="13" r="1"/>
        <path d="M9 17h6"/>
        </svg>
    `;

    const online = document.createElement('div');
    online.className = 'aicc-chat-online-dot';

    avatarWrapper.appendChild(avatar);
    avatarWrapper.appendChild(online);

    const titleWrapper = document.createElement('div');
    titleWrapper.className = 'aicc-chat-title-wrapper';

    const title = document.createElement('div');
    title.className = 'aicc-chat-title';
    title.textContent = 'AI Course Companion';

    const subtitle = document.createElement('div');
    subtitle.className = 'aicc-chat-subtitle';
    subtitle.textContent = 'Online';

    titleWrapper.appendChild(title);
    titleWrapper.appendChild(subtitle);

    const leftGroup = document.createElement('div');
    leftGroup.className = 'aicc-chat-left-group';
    leftGroup.appendChild(avatarWrapper);
    leftGroup.appendChild(titleWrapper);

    const controls = document.createElement('div');
    controls.className = 'aicc-chat-controls';

    const maximizeBtn = document.createElement('button');
    maximizeBtn.type = 'button';
    maximizeBtn.className = 'aicc-chat-maximize-btn';
    maximizeBtn.innerText = '⤢';

    controls.appendChild(maximizeBtn);
    header.appendChild(leftGroup);
    header.appendChild(controls);

    

    return { header, maximizeBtn };
}
