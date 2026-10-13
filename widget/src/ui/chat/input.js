export function createInputArea() {
    const inputBox = document.createElement('div');
    inputBox.className = 'aicc-chat-input-box';

    const input = document.createElement('input');
    input.className = 'aicc-chat-input';
    input.placeholder = 'Ask me something...';
    input.type = 'text';

    const button = document.createElement('button');
    button.className = 'aicc-chat-send-btn';
    button.innerText = '➜';

    inputBox.appendChild(input);
    inputBox.appendChild(button);

    return { inputBox, input, button };
}
