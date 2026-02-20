/**
 * Source List Widget JavaScript
 * Handles TomSelect autocomplete for adding sources and managing the selected source list
 */

/**
 * Add a source to the visible list with remove button and modal detail link
 */
function addSourceToList(listElement, sourceId, sourceLabel, selectElement) {
    // Get the detail URL pattern from data attribute
    const urlPattern = listElement.dataset.detailUrlPattern;
    const detailUrl = urlPattern.replace('/0/', `/${sourceId}/`);

    const li = document.createElement('li');
    li.className = 'list-group-item d-flex justify-content-between align-items-start';
    li.dataset.value = sourceId;

    // Source title with modal link
    const titleDiv = document.createElement('div');
    titleDiv.className = 'source-title';

    const link = document.createElement('a');
    link.href = detailUrl;
    link.className = 'modal-link text-decoration-none';
    link.textContent = sourceLabel;
    titleDiv.appendChild(link);

    // Remove button
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'btn btn-sm btn-outline-danger source-remove-btn';
    removeBtn.dataset.value = sourceId;
    removeBtn.setAttribute('aria-label', 'Remove');
    removeBtn.innerHTML = '<i class="fas fa-trash"></i>';

    li.appendChild(titleDiv);
    li.appendChild(removeBtn);
    listElement.appendChild(li);

    // Wire modal links after insertion so the new link gets bound.
    if (window.wireModalLinks) {
        window.wireModalLinks();
    }
}

/**
 * Load a URL response into the shared modal container and display it.
 */
function openContentInModal(url) {
    const modalElement = document.getElementById('modal');
    if (!modalElement || !window.bootstrap) {
        window.location.href = url;
        return;
    }

    const modalContent = modalElement.querySelector('.modal-content');
    if (!modalContent) {
        window.location.href = url;
        return;
    }

    fetch(url, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
        .then(response => response.text())
        .then(html => {
            modalContent.innerHTML = html;
            let modalInstance = bootstrap.Modal.getInstance(modalElement);
            if (!modalInstance) {
                modalInstance = new bootstrap.Modal(modalElement, {
                    keyboard: false
                });
            }
            modalInstance.show();
            if (window.wireModalLinks) {
                window.wireModalLinks();
            }
        })
        .catch(() => {
            window.location.href = url;
        });
}

/**
 * Read a cookie value by name.
 */
function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split(';') : [];
    for (const cookie of cookies) {
        const trimmedCookie = cookie.trim();
        if (trimmedCookie.startsWith(name + '=')) {
            return decodeURIComponent(trimmedCookie.slice(name.length + 1));
        }
    }
    return '';
}

/**
 * Show inline feedback for widget-level errors.
 */
function showFeedback(feedbackElement, message) {
    if (!feedbackElement) {
        return;
    }
    feedbackElement.textContent = message;
    feedbackElement.classList.remove('d-none');
}

/**
 * Hide widget-level feedback.
 */
function clearFeedback(feedbackElement) {
    if (!feedbackElement) {
        return;
    }
    feedbackElement.textContent = '';
    feedbackElement.classList.add('d-none');
}

/**
 * Parse a typed author string into first and last names.
 */
function parseAuthorInput(rawInput) {
    const trimmedInput = (rawInput || '').trim();
    if (!trimmedInput) {
        return null;
    }

    if (trimmedInput.includes(',')) {
        const [lastNamesPart, firstNamesPart = ''] = trimmedInput.split(',', 2);
        const lastNames = lastNamesPart.trim();
        const firstNames = firstNamesPart.trim();
        if (!lastNames) {
            return null;
        }
        return {
            first_names: firstNames,
            last_names: lastNames
        };
    }

    const nameParts = trimmedInput.split(/\s+/).filter(Boolean);
    if (!nameParts.length) {
        return null;
    }

    if (nameParts.length === 1) {
        return {
            first_names: '',
            last_names: nameParts[0]
        };
    }

    return {
        first_names: nameParts.slice(0, -1).join(' '),
        last_names: nameParts[nameParts.length - 1]
    };
}

/**
 * Create a new author from typed input and return the created author payload.
 */
async function createAuthorFromInput(authorInput, quickCreateUrl, feedbackElement) {
    const parsedName = parseAuthorInput(authorInput);
    if (!parsedName || !parsedName.last_names) {
        showFeedback(
            feedbackElement,
            'Author needs at least a last name. Use "Last, First" or "First Last".'
        );
        return null;
    }

    const response = await fetch(quickCreateUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify(parsedName)
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        showFeedback(
            feedbackElement,
            payload.error || 'Could not create author. Please try again.'
        );
        return null;
    }

    clearFeedback(feedbackElement);
    return payload;
}

/**
 * Create a new source from typed input and return the created source payload.
 */
async function createSourceFromInput(title, quickCreateUrl, feedbackElement, metadata = {}) {
    const trimmedTitle = (title || '').trim();
    if (!trimmedTitle) {
        return null;
    }

    const requestPayload = { title: trimmedTitle };

    if (metadata.year !== undefined && metadata.year !== null && String(metadata.year).trim()) {
        requestPayload.year = String(metadata.year).trim();
    }

    if (Array.isArray(metadata.authors) && metadata.authors.length) {
        requestPayload.authors = metadata.authors;
    }

    const response = await fetch(quickCreateUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify(requestPayload)
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        showFeedback(
            feedbackElement,
            payload.error || 'Could not create source. Please try again.'
        );
        return null;
    }

    clearFeedback(feedbackElement);
    return payload;
}

/**
 * Initialize author TomSelect for optional source metadata input.
 */
function initAuthorTomSelect(authorInput, feedbackElement) {
    if (!authorInput) {
        return null;
    }

    const authorAutocompleteUrl = authorInput.dataset.authorAutocompleteUrl;
    const authorQuickCreateUrl = authorInput.dataset.authorQuickCreateUrl;

    if (!authorAutocompleteUrl) {
        return null;
    }

    if (authorInput.tomselect) {
        authorInput.tomselect.destroy();
    }

    const createAuthorHandler = authorQuickCreateUrl ? function (userInput, callback) {
        createAuthorFromInput(userInput, authorQuickCreateUrl, feedbackElement)
            .then(createdAuthor => {
                if (!createdAuthor || !createdAuthor.id) {
                    callback();
                    return;
                }

                callback({
                    id: String(createdAuthor.id),
                    first_names: createdAuthor.first_names || '',
                    last_names: createdAuthor.last_names || '',
                    label: createdAuthor.label || createdAuthor.text || userInput,
                    text: createdAuthor.text || createdAuthor.label || userInput
                });
            })
            .catch(() => {
                showFeedback(
                    feedbackElement,
                    'Could not create author. Please try again.'
                );
                callback();
            });
    } : false;

    return new TomSelect(authorInput, {
        valueField: 'id',
        labelField: 'label',
        searchField: ['label', 'last_names', 'first_names'],
        maxItems: null,
        maxOptions: 25,
        loadThrottle: 300,
        create: createAuthorHandler,
        persist: false,
        createFilter: function (userInput) {
            return !!(userInput && userInput.trim());
        },
        load: function (query, callback) {
            const url = authorAutocompleteUrl + (query ? '?q=' + encodeURIComponent(query) : '');
            fetch(url)
                .then(response => response.json())
                .then(data => {
                    callback(data.results || data);
                })
                .catch(() => {
                    callback();
                });
        },
        render: {
            option: function (data, escape) {
                return '<div class="option">' + escape(data.label || data.text || '') + '</div>';
            },
            item: function (data, escape) {
                return '<div>' + escape(data.label || data.text || '') + '</div>';
            }
        },
        placeholder: authorInput.getAttribute('placeholder') || 'Add authors...',
        plugins: ['remove_button']
    });
}

document.addEventListener('DOMContentLoaded', function () {
    // Initialize all source list widgets on the page
    document.querySelectorAll('input.source-tomselect-add').forEach(function (input) {
        // Validate element type
        if (input.tagName !== 'INPUT') {
            console.warn('Expected input element but found:', input.tagName);
            return;
        }

        // Get configuration from data attributes
        const targetSelectId = input.dataset.targetSelect;
        const targetSelect = document.getElementById(targetSelectId);
        const listElement = document.getElementById(targetSelectId + '_list');
        const emptyMessage = document.getElementById(targetSelectId + '_empty');
        const feedbackElement = document.getElementById(targetSelectId + '_feedback');
        const autocompleteUrl = input.dataset.autocompleteUrl;
        const quickCreateUrl = input.dataset.quickCreateUrl;
        const labelField = input.dataset.labelField;
        const authorsInput = document.getElementById(targetSelectId + '_authors');
        const yearInput = document.getElementById(targetSelectId + '_year');

        // Destroy any existing TomSelect instance
        if (input.tomselect) {
            input.tomselect.destroy();
        }

        const authorTomSelect = initAuthorTomSelect(authorsInput, feedbackElement);

        const buildAuthorMetadata = function () {
            if (!authorTomSelect || !authorTomSelect.items.length) {
                return [];
            }

            return authorTomSelect.items
                .map(function (authorId) {
                    const option = authorTomSelect.options[authorId];
                    if (!option) {
                        return null;
                    }

                    return {
                        id: String(authorId),
                        first_names: option.first_names || '',
                        last_names: option.last_names || ''
                    };
                })
                .filter(Boolean);
        };

        const createHandler = quickCreateUrl ? function (userInput, callback) {
            const yearValue = yearInput ? yearInput.value : '';
            const selectedAuthors = buildAuthorMetadata();

            createSourceFromInput(userInput, quickCreateUrl, feedbackElement, {
                year: yearValue,
                authors: selectedAuthors
            })
                .then(createdSource => {
                    if (!createdSource || !createdSource.id) {
                        callback();
                        return;
                    }

                    if (authorTomSelect) {
                        authorTomSelect.clear(true);
                    }
                    if (yearInput) {
                        yearInput.value = '';
                    }

                    const optionLabel =
                        createdSource[labelField] ||
                        createdSource.label ||
                        createdSource.text ||
                        createdSource.title ||
                        userInput;

                    callback({
                        id: String(createdSource.id),
                        title: createdSource.title || userInput,
                        [labelField]: optionLabel
                    });
                })
                .catch(() => {
                    showFeedback(
                        feedbackElement,
                        'Could not create source. Please try again.'
                    );
                    callback();
                });
        } : false;

        // Initialize TomSelect for autocomplete
        const tomselect = new TomSelect(input, {
            valueField: 'id',
            labelField: labelField,
            searchField: [labelField, 'title'],
            placeholder: input.getAttribute('placeholder') || 'Search sources...',
            maxOptions: 50,
            loadThrottle: 300,
            preload: 'focus',
            create: createHandler,
            persist: false,

            createFilter: function (userInput) {
                return !!(userInput && userInput.trim());
            },

            // Load options from autocomplete endpoint
            load: function (query, callback) {
                const url = autocompleteUrl + (query ? '?q=' + encodeURIComponent(query) : '');
                fetch(url)
                    .then(response => response.json())
                    .then(data => {
                        clearFeedback(feedbackElement);
                        callback(data.results || data);
                    })
                    .catch(() => {
                        callback();
                    });
            },

            // When a source is selected, add it to the list
            onChange: function (value) {
                if (!value) return;

                const option = tomselect.options[value];
                if (!option) return;

                // Check if already selected
                if (targetSelect.querySelector(`option[value="${value}"]`)) {
                    tomselect.clear();
                    return;
                }

                clearFeedback(feedbackElement);

                const sourceLabel =
                    option[labelField] ||
                    option.label ||
                    option.text ||
                    option.title ||
                    value;

                // Add to hidden select for form submission
                const optionElement = document.createElement('option');
                optionElement.value = value;
                optionElement.text = sourceLabel;
                optionElement.selected = true;
                targetSelect.appendChild(optionElement);

                // Add to visible list
                addSourceToList(listElement, value, sourceLabel, targetSelect);

                // Clear the search input
                tomselect.clear();

                // Hide empty message
                if (emptyMessage) {
                    emptyMessage.style.display = 'none';
                }
            },

            // Render functions
            render: {
                option: function (data, escape) {
                    return '<div class="option">' + escape(data[labelField]) + '</div>';
                },
                item: function (data, escape) {
                    return '<div>' + escape(data[labelField]) + '</div>';
                }
            },

            placeholder: 'Search sources...',
            plugins: ['clear_button'],
            closeAfterSelect: true,
            hideSelected: true
        });

        // Handle remove button clicks
        listElement.addEventListener('click', function (e) {
            const modalLink = e.target.closest('a.modal-link');
            if (modalLink && listElement.contains(modalLink)) {
                e.preventDefault();
                const modalUrl = modalLink.getAttribute('data-link') || modalLink.getAttribute('href');
                if (modalUrl) {
                    openContentInModal(modalUrl);
                }
                return;
            }

            const removeBtn = e.target.classList.contains('source-remove-btn')
                ? e.target
                : e.target.closest('.source-remove-btn');

            if (removeBtn) {
                const sourceId = removeBtn.dataset.value;

                // Remove from hidden select
                const option = targetSelect.querySelector(`option[value="${sourceId}"]`);
                if (option) {
                    option.remove();
                }

                // Remove from visible list
                const li = removeBtn.closest('li');
                if (li) {
                    li.remove();
                }

                // Show empty message if no sources left
                if (listElement.children.length === 0 && emptyMessage) {
                    emptyMessage.style.display = 'block';
                }
            }
        });

        // Ensure all options are selected on form submit
        const form = targetSelect.closest('form');
        if (form) {
            form.addEventListener('submit', function () {
                // Select all options in the hidden select to ensure they're submitted
                Array.from(targetSelect.options).forEach(option => {
                    option.selected = true;
                });
            });
        }
    });
});
