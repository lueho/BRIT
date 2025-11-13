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
    
    // Wire modal links if the function exists
    if (window.wireModalLinks) {
        window.wireModalLinks();
    }
    
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
}

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all source list widgets on the page
    document.querySelectorAll('input.source-tomselect-add').forEach(function(input) {
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
        const autocompleteUrl = input.dataset.autocompleteUrl;
        const labelField = input.dataset.labelField;
        
        // Destroy any existing TomSelect instance
        if (input.tomselect) {
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
            preload: 'focus',
            create: false,
            persist: false,
            
            // Load options from autocomplete endpoint
            load: function(query, callback) {
                const url = autocompleteUrl + (query ? '?q=' + encodeURIComponent(query) : '');
                fetch(url)
                    .then(response => response.json())
                    .then(data => {
                        callback(data.results || data);
                    })
                    .catch(() => {
                        callback();
                    });
            },
            
            // When a source is selected, add it to the list
            onChange: function(value) {
                if (!value) return;
                
                const option = tomselect.options[value];
                if (!option) return;
                
                // Check if already selected
                if (targetSelect.querySelector(`option[value="${value}"]`)) {
                    tomselect.clear();
                    return;
                }
                
                // Add to hidden select for form submission
                const optionElement = document.createElement('option');
                optionElement.value = value;
                optionElement.text = option[labelField];
                optionElement.selected = true;
                targetSelect.appendChild(optionElement);
                
                // Add to visible list
                addSourceToList(listElement, value, option[labelField], targetSelect);
                
                // Clear the search input
                tomselect.clear();
                
                // Hide empty message
                if (emptyMessage) {
                    emptyMessage.style.display = 'none';
                }
            },
            
            // Render functions
            render: {
                option: function(data, escape) {
                    return '<div class="option">' + escape(data[labelField]) + '</div>';
                },
                item: function(data, escape) {
                    return '<div>' + escape(data[labelField]) + '</div>';
                }
            },
            
            placeholder: 'Search sources...',
            plugins: ['clear_button'],
            closeAfterSelect: true,
            hideSelected: true
        });
        
        // Handle remove button clicks
        listElement.addEventListener('click', function(e) {
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
            form.addEventListener('submit', function() {
                // Select all options in the hidden select to ensure they're submitted
                Array.from(targetSelect.options).forEach(option => {
                    option.selected = true;
                });
            });
        }
    });
});
