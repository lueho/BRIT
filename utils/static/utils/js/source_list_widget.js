/**
 * Source List Widget - Display sources as list with TomSelect autocomplete
 * 
 * This widget combines:
 * - Server-side autocomplete for adding sources (doesn't load thousands of options)
 * - List display of selected sources (one per line with full titles)
 * - Easy removal of sources
 */

document.addEventListener('DOMContentLoaded', function () {
    // Initialize all source list widgets on the page
    // Use input selector to avoid matching TomSelect wrapper divs
    document.querySelectorAll('input.source-tomselect-add').forEach(input => {
        // Skip if this is not actually an input element
        if (input.tagName !== 'INPUT') {
            console.warn('Expected input element but found:', input.tagName);
            return;
        }
        
        const targetSelectId = input.dataset.targetSelect;
        const targetSelect = document.getElementById(targetSelectId);
        const listEl = document.getElementById(targetSelectId + '_list');
        const emptyEl = document.getElementById(targetSelectId + '_empty');
        const autocompleteUrl = input.dataset.autocompleteUrl;
        const labelField = input.dataset.labelField;

        // Check if TomSelect is already initialized (by django-tomselect)
        if (input.tomselect) {
            // Destroy existing instance
            input.tomselect.destroy();
        }

        // Initialize TomSelect for autocomplete
        const tomselect = new TomSelect(input, {
            valueField: 'id',
            labelField: labelField,
            searchField: [labelField, 'title'],
            placeholder: input.getAttribute('placeholder') || 'Search sources...',
            maxOptions: 50,
            loadThrottle: 300,
            preload: false,
            create: false,
            persist: false,
            load: function (query, callback) {
                if (!query.length) return callback();

                fetch(autocompleteUrl + '?q=' + encodeURIComponent(query))
                    .then(response => response.json())
                    .then(json => {
                        callback(json.results || json);
                    })
                    .catch(() => {
                        callback();
                    });
            },
            onChange: function (value) {
                if (!value) return;

                // Get the selected item
                const item = tomselect.options[value];
                if (!item) return;

                // Check if already in the list
                if (targetSelect.querySelector(`option[value="${value}"]`)) {
                    tomselect.clear();
                    return;
                }

                // Add to hidden select
                const option = document.createElement('option');
                option.value = value;
                option.text = item[labelField];
                option.selected = true;
                targetSelect.appendChild(option);

                // Add to visible list
                addSourceToList(listEl, value, item[labelField], targetSelect);

                // Clear tomselect
                tomselect.clear();

                // Hide empty message
                if (emptyEl) emptyEl.style.display = 'none';
            },
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

        // Handle remove buttons
        listEl.addEventListener('click', function (e) {
            if (e.target.classList.contains('source-remove-btn') ||
                e.target.closest('.source-remove-btn')) {
                const btn = e.target.classList.contains('source-remove-btn')
                    ? e.target
                    : e.target.closest('.source-remove-btn');
                const value = btn.dataset.value;

                // Remove from hidden select
                const option = targetSelect.querySelector(`option[value="${value}"]`);
                if (option) option.remove();

                // Remove from visible list
                const listItem = btn.closest('li');
                if (listItem) listItem.remove();

                // Show empty message if no sources left
                if (listEl.children.length === 0 && emptyEl) {
                    emptyEl.style.display = 'block';
                }
            }
        });

        // Ensure all options are selected when form is submitted
        const form = targetSelect.closest('form');
        if (form) {
            form.addEventListener('submit', function() {
                // Select all options in the hidden select to ensure they're submitted
                Array.from(targetSelect.options).forEach(option => {
                    option.selected = true;
                });
            });
        }
    });
});

/**
 * Add a source to the visible list
 */
function addSourceToList(listEl, value, label, targetSelect) {
    const li = document.createElement('li');
    li.className = 'list-group-item d-flex justify-content-between align-items-start';
    li.dataset.value = value;

    const titleDiv = document.createElement('div');
    titleDiv.className = 'source-title';
    titleDiv.textContent = label;

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'btn btn-sm btn-outline-danger source-remove-btn';
    removeBtn.dataset.value = value;
    removeBtn.setAttribute('aria-label', 'Remove');
    removeBtn.innerHTML = '<i class="fas fa-trash"></i>';

    li.appendChild(titleDiv);
    li.appendChild(removeBtn);
    listEl.appendChild(li);
}
