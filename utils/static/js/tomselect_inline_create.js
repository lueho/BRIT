"use strict";

(function () {
    if (window.__britTomSelectInlineCreateInitialized) {
        return;
    }
    window.__britTomSelectInlineCreateInitialized = true;

    const selector = 'select[data-tomselect-create-url]';

    function getCookie(name) {
        const cookieValue = document.cookie
            .split(';')
            .map(cookie => cookie.trim())
            .find(cookie => cookie.startsWith(name + '='));

        if (!cookieValue) {
            return '';
        }

        return decodeURIComponent(cookieValue.split('=').slice(1).join('='));
    }

    function buildPayload(select, userInput) {
        const payloadKey = select.dataset.tomselectCreatePayloadKey || 'name';
        const payload = {
            [payloadKey]: userInput
        };

        const extraPayloadRaw = select.dataset.tomselectCreateExtraPayload;
        if (!extraPayloadRaw) {
            return payload;
        }

        try {
            return {
                ...payload,
                ...JSON.parse(extraPayloadRaw)
            };
        } catch (_error) {
            return payload;
        }
    }

    async function createOption(select, userInput) {
        const quickCreateUrl = select.dataset.tomselectCreateUrl;
        const response = await fetch(quickCreateUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(buildPayload(select, userInput))
        });

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(
                payload.error
                || select.dataset.tomselectCreateErrorMessage
                || 'Could not create option.'
            );
        }

        return payload;
    }

    function reportCreateError(instance, message) {
        const input = instance && instance.control_input;
        if (input && typeof input.setCustomValidity === 'function') {
            input.setCustomValidity(message);
            input.reportValidity();
            window.setTimeout(() => input.setCustomValidity(''), 0);
            return;
        }

        window.alert(message);
    }

    function enhanceInstance(select) {
        const instance = select.tomselect;
        if (!instance) {
            return false;
        }

        if (instance.settings._inlineCreateEnhanced) {
            return true;
        }

        const quickCreateUrl = select.dataset.tomselectCreateUrl;
        if (!quickCreateUrl) {
            return true;
        }

        instance.settings.createFilter = function (input) {
            return !!(input && input.trim());
        };
        instance.settings.persist = false;
        instance.settings.create = function (input, callback) {
            const trimmedInput = (input || '').trim();
            if (!trimmedInput) {
                callback();
                return;
            }

            createOption(select, trimmedInput)
                .then(createdOption => {
                    const valueField = instance.settings.valueField || 'id';
                    const labelField = instance.settings.labelField || 'name';
                    const optionValue = createdOption[valueField] ?? createdOption.id;
                    const fallbackLabel = createdOption[labelField] || createdOption.name || trimmedInput;
                    const option = {
                        ...createdOption,
                        [valueField]: String(optionValue),
                        [labelField]: fallbackLabel,
                        text: createdOption.text || createdOption.label || fallbackLabel
                    };
                    callback(option);
                })
                .catch(error => {
                    callback();
                    reportCreateError(instance, error.message || 'Could not create option.');
                });
        };
        instance.settings._inlineCreateEnhanced = true;
        instance.refreshOptions(false);
        return true;
    }

    function scheduleEnhancement(select, attempt = 0) {
        if (!select || !document.body.contains(select)) {
            return;
        }

        if (enhanceInstance(select)) {
            return;
        }

        if (attempt >= 20) {
            return;
        }

        window.setTimeout(() => scheduleEnhancement(select, attempt + 1), 50);
    }

    function scan(container) {
        if (!container) {
            return;
        }

        if (container.matches && container.matches(selector)) {
            scheduleEnhancement(container);
        }

        if (container.querySelectorAll) {
            container.querySelectorAll(selector).forEach(select => {
                scheduleEnhancement(select);
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            scan(document);
        });
    } else {
        scan(document);
    }

    const observer = new MutationObserver(mutations => {
        mutations.forEach(mutation => {
            mutation.addedNodes.forEach(node => {
                if (node.nodeType === 1) {
                    scan(node);
                }
            });
        });
    });

    observer.observe(document.body, { childList: true, subtree: true });
})();
