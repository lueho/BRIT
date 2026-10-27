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
    document.dispatchEvent(new CustomEvent('brit:rewire-modal-links'));
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
            document.dispatchEvent(new CustomEvent('brit:rewire-modal-links'));
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
 * Parse a typed author string into first and last names for a person.
 *
 * Rules:
 *  - "Last, First" (comma): everything before the first comma is last_names,
 *    everything after is first_names.  This is the standard bibliographic
 *    format.
 *  - "First Last" (no comma): the last word becomes last_names, the rest
 *    first_names.  A single word is stored as last_names only.
 */
function parsePersonName(rawInput) {
    const trimmedInput = (rawInput || '').trim();
    if (!trimmedInput) {
        return null;
    }

    if (trimmedInput.includes(',')) {
        const commaIndex = trimmedInput.indexOf(',');
        const lastNames = trimmedInput.slice(0, commaIndex).trim();
        const firstNames = trimmedInput.slice(commaIndex + 1).trim();
        if (!lastNames) {
            return null;
        }
        return { first_names: firstNames, last_names: lastNames };
    }

    const tokens = trimmedInput.split(/\s+/);
    const lastNames = tokens.pop();
    return { first_names: tokens.join(' '), last_names: lastNames };
}

/**
 * Mirror the server-side ``author_name_has_letter`` rule: names without any
 * letter are skipped by the quick-create endpoint, so never offer them.
 */
function authorNameHasLetter(value) {
    return /\p{L}/u.test(value || '');
}

function personDisplayName(parsed) {
    return parsed.first_names
        ? parsed.last_names + ', ' + parsed.first_names
        : parsed.last_names;
}

/**
 * Build the explicit "create" dropdown options for a typed author name.
 *
 * Rather than silently guessing the author type, the user picks one of these
 * options.  The new author is not written to the database here: the chosen
 * option becomes a pending chip and is only persisted together with the
 * source when "Add source" is clicked.
 */
function buildAuthorCreateOptions(rawInput) {
    const trimmedInput = (rawInput || '').trim();
    if (!trimmedInput) {
        return [];
    }

    const options = [];
    const person = parsePersonName(trimmedInput);
    if (person && authorNameHasLetter(person.last_names)) {
        const displayName = personDisplayName(person);
        options.push({
            id: 'pending-person:' + trimmedInput,
            author_type: 'person',
            first_names: person.first_names,
            last_names: person.last_names,
            label: displayName,
            create_label: 'Create person "' + displayName + '"',
            pending: true
        });
    }

    if (!authorNameHasLetter(trimmedInput)) {
        return options;
    }

    options.push({
        id: 'pending-organization:' + trimmedInput,
        author_type: 'organization',
        organization_name: trimmedInput,
        label: trimmedInput,
        create_label: 'Create organization "' + trimmedInput + '"',
        pending: true
    });

    return options;
}

/**
 * Map a selected author TomSelect option to the payload sent to the
 * source quick-create endpoint.
 *
 * Pending options (freshly typed names) carry the author fields and no id —
 * the endpoint creates the author transactionally with the source.  Options
 * from the autocomplete reference existing authors and only send their id.
 */
function authorOptionToMetadata(option) {
    if (!option) {
        return null;
    }
    if (option.pending) {
        if (option.author_type === 'organization') {
            return {
                author_type: 'organization',
                organization_name: option.organization_name || ''
            };
        }
        return {
            first_names: option.first_names || '',
            last_names: option.last_names || ''
        };
    }
    return { id: String(option.id) };
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
 *
 * When the input advertises author creation (``data-author-quick-create-url``),
 * the dropdown also offers explicit "Create person" / "Create organization"
 * options for the typed name.  Selecting one adds a pending chip — the author
 * record is only created server-side when the source itself is saved.
 */
function initAuthorTomSelect(authorInput) {
    if (!authorInput) {
        return null;
    }

    const authorAutocompleteUrl = authorInput.dataset.authorAutocompleteUrl;

    if (!authorAutocompleteUrl) {
        return null;
    }

    const canCreateAuthor = Boolean(authorInput.dataset.authorQuickCreateUrl);

    if (authorInput.tomselect) {
        authorInput.tomselect.destroy();
    }

    return new TomSelect(authorInput, {
        valueField: 'id',
        labelField: 'label',
        searchField: ['label', 'last_names', 'first_names'],
        maxItems: null,
        maxOptions: 25,
        loadThrottle: 300,
        create: false,
        persist: false,
        load: function (query, callback) {
            const createOptions = canCreateAuthor ? buildAuthorCreateOptions(query) : [];
            const url = authorAutocompleteUrl + '?q=' + encodeURIComponent(query);
            fetch(url)
                .then(response => response.json())
                .then(data => {
                    callback((data.results || data).concat(createOptions));
                })
                .catch(() => {
                    callback(createOptions);
                });
        },
        render: {
            option: function (data, escape) {
                if (data.pending) {
                    return '<div class="option create">' + escape(data.create_label || data.label || '') + '</div>';
                }
                return '<div class="option">' + escape(data.label || data.text || '') + '</div>';
            },
            item: function (data, escape) {
                const label = escape(data.label || data.text || '');
                if (data.pending) {
                    return '<div>' + label + ' <span class="badge text-bg-secondary">new ' + escape(data.author_type || 'author') + '</span></div>';
                }
                return '<div>' + label + '</div>';
            }
        },
        placeholder: authorInput.getAttribute('placeholder') || 'Add authors...',
        plugins: ['remove_button']
    });
}

/**
 * Delete a quick-created source from the database via the quick-create endpoint.
 * ``authorCleanupToken`` is the signed token returned when the source was
 * quick-created; it lets the server also remove the authors created with it
 * while nothing else references them.
 * Silently ignores failures (e.g. network errors) since the source may already
 * have been saved as part of the parent form.
 */
async function deleteQuickCreatedSource(sourceId, quickCreateUrl, authorCleanupToken = '') {
    if (!sourceId || !quickCreateUrl) {
        return;
    }
    try {
        await fetch(quickCreateUrl, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ id: sourceId, author_cleanup_token: authorCleanupToken })
        });
    } catch (_) {
        // Silently ignore network errors — the source will remain but that is
        // preferable to blocking the user.
    }
}

document.addEventListener('DOMContentLoaded', function () {
    // Initialize all source list widgets on the page
    document.querySelectorAll('input.source-tomselect-add').forEach(function (input) {
        if (input.dataset.sourceListWidgetInitialized === 'true') {
            return;
        }

        if (input.tagName !== 'INPUT') {
            console.warn('Expected input element but found:', input.tagName);
            return;
        }

        // Guard against duplicate script inclusion / re-initialization.
        input.dataset.sourceListWidgetInitialized = 'true';

        const widgetContainer = input.closest('.source-list-widget-container');

        // --- Configuration from data attributes ---
        const targetSelectId = input.dataset.targetSelect;
        const targetSelect = widgetContainer
            ? widgetContainer.querySelector(`select[id="${targetSelectId}"]`)
            : document.getElementById(targetSelectId);
        const listElement = widgetContainer
            ? widgetContainer.querySelector('ul.list-group')
            : document.getElementById(targetSelectId + '_list');
        const emptyMessage = widgetContainer
            ? widgetContainer.querySelector('p[id$="_empty"]')
            : document.getElementById(targetSelectId + '_empty');
        const feedbackElement = widgetContainer
            ? widgetContainer.querySelector('p[id$="_feedback"]')
            : document.getElementById(targetSelectId + '_feedback');
        const autocompleteUrl = input.dataset.autocompleteUrl;
        const quickCreateUrl = input.dataset.quickCreateUrl;
        const labelField = input.dataset.labelField;
        const authorsInput = widgetContainer
            ? widgetContainer.querySelector('input.source-author-tomselect-add')
            : document.getElementById(targetSelectId + '_authors');
        const yearInput = widgetContainer
            ? widgetContainer.querySelector('input.source-year-input')
            : document.getElementById(targetSelectId + '_year');
        const newTitleInput = widgetContainer
            ? widgetContainer.querySelector('input.source-new-title')
            : document.getElementById(targetSelectId + '_new_title');

        if (!targetSelect || !listElement) {
            return;
        }

        // Track sources created via quick-create in this widget session, mapped
        // to their author cleanup token, so the source and the authors created
        // with it can be deleted if the user removes the source before saving.
        const quickCreatedSources = new Map();

        // --- Author TomSelect for the create-new-source section ---
        if (input.tomselect) {
            input.tomselect.destroy();
        }

        const authorTomSelect = initAuthorTomSelect(authorsInput);

        const buildAuthorMetadata = function () {
            if (!authorTomSelect || !authorTomSelect.items.length) {
                return [];
            }
            return authorTomSelect.items
                .map(function (authorId) {
                    return authorOptionToMetadata(authorTomSelect.options[authorId]);
                })
                .filter(Boolean);
        };

        // --- Helper: add a source to the visible list and hidden select ---
        function addSourceToWidget(sourceId, sourceLabel, isQuickCreated, authorCleanupToken = '') {
            // Guard against duplicates
            if (targetSelect.querySelector(`option[value="${sourceId}"]`)) {
                return;
            }

            if (isQuickCreated) {
                quickCreatedSources.set(String(sourceId), authorCleanupToken);
            }

            clearFeedback(feedbackElement);

            const optionElement = document.createElement('option');
            optionElement.value = sourceId;
            optionElement.text = sourceLabel;
            optionElement.selected = true;
            targetSelect.appendChild(optionElement);

            addSourceToList(listElement, sourceId, sourceLabel, targetSelect);

            if (emptyMessage) {
                emptyMessage.classList.add('d-none');
            }
        }

        // --- Search TomSelect (no create handler — search only) ---
        const tomselect = new TomSelect(input, {
            valueField: 'id',
            labelField: labelField,
            searchField: [labelField, 'title'],
            placeholder: input.getAttribute('placeholder') || 'Search sources...',
            maxOptions: 50,
            loadThrottle: 300,
            preload: 'focus',
            create: false,
            persist: false,

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

            onChange: function (value) {
                if (!value) return;

                const option = tomselect.options[value];
                if (!option) return;

                const sourceLabel =
                    option[labelField] ||
                    option.label ||
                    option.text ||
                    option.title ||
                    value;

                addSourceToWidget(value, sourceLabel, false);
                tomselect.clear();
            },

            render: {
                option: function (data, escape) {
                    return '<div class="option">' + escape(data[labelField] || '') + '</div>';
                },
                item: function (data, escape) {
                    return '<div>' + escape(data[labelField] || '') + '</div>';
                }
            },

            plugins: ['clear_button'],
            closeAfterSelect: true,
            hideSelected: true
        });

        // --- "Add source" button handler ---
        const createBtn = widgetContainer
            ? widgetContainer.querySelector(
                `.source-create-btn[data-target-select="${targetSelectId}"]`
            )
            : document.querySelector(
                `.source-create-btn[data-target-select="${targetSelectId}"]`
            );

        if (createBtn && quickCreateUrl) {
            createBtn.addEventListener('click', async function () {
                const title = newTitleInput ? newTitleInput.value.trim() : '';
                if (!title) {
                    showFeedback(feedbackElement, 'Please enter a title for the new source.');
                    if (newTitleInput) {
                        newTitleInput.focus();
                    }
                    return;
                }

                const yearValue = yearInput ? yearInput.value.trim() : '';
                const selectedAuthors = buildAuthorMetadata();

                createBtn.disabled = true;
                clearFeedback(feedbackElement);

                const createdSource = await createSourceFromInput(
                    title,
                    quickCreateUrl,
                    feedbackElement,
                    { year: yearValue, authors: selectedAuthors }
                ).catch(() => null);

                createBtn.disabled = false;

                if (!createdSource || !createdSource.id) {
                    return;
                }

                const optionLabel =
                    createdSource[labelField] ||
                    createdSource.label ||
                    createdSource.text ||
                    createdSource.title ||
                    title;

                addSourceToWidget(
                    String(createdSource.id),
                    optionLabel,
                    true,
                    createdSource.author_cleanup_token || ''
                );

                // Clear the create-new-source form
                if (newTitleInput) {
                    newTitleInput.value = '';
                }
                if (authorTomSelect) {
                    authorTomSelect.clear(true);
                }
                if (yearInput) {
                    yearInput.value = '';
                }
            });
        }

        // --- Remove button / modal link handler ---
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
                const sourceId = String(removeBtn.dataset.value);

                // If this was quick-created in this session, delete it from the DB
                if (quickCreatedSources.has(sourceId) && quickCreateUrl) {
                    const authorCleanupToken = quickCreatedSources.get(sourceId);
                    quickCreatedSources.delete(sourceId);
                    deleteQuickCreatedSource(sourceId, quickCreateUrl, authorCleanupToken);
                }

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

                if (listElement.children.length === 0 && emptyMessage) {
                    emptyMessage.classList.remove('d-none');
                }
            }
        });

        // --- Ensure all options are selected on form submit ---
        const form = targetSelect.closest('form');
        if (form) {
            form.addEventListener('submit', function () {
                Array.from(targetSelect.options).forEach(option => {
                    option.selected = true;
                });
            });
        }
    });
});
