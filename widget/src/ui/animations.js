function matchesTransitionProperty(event, options) {
    if (options.finishCondition) {
        return options.finishCondition(event);
    }

    const properties = options.properties || (options.property ? [options.property] : ['opacity']);
    const propertyName = event.propertyName || '';

    return properties.some((property) => propertyName === property || propertyName.startsWith(`${property}-`));
}

export function animate(container, callback, options = {}) {
    const normalizedOptions = typeof options === 'function' ? { onFinish: options } : options;
    const { onFinish } = normalizedOptions;

    container.classList.add("aicc-animating");

    const onEnd = (event) => {
        if (event.target !== container) {
            return;
        }

        if (!matchesTransitionProperty(event, normalizedOptions)) {
            return;
        }

        container.removeEventListener("transitionend", onEnd);
        container.classList.remove("aicc-animating");

        onFinish?.();
    };

    container.addEventListener("transitionend", onEnd);

    callback();
}