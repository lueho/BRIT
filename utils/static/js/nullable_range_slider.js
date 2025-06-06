// This files must be included after the range_slider.js file.
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.checkbox-include-unknown').forEach(checkbox => {
        const formRow = checkbox.closest('.form-row');
        if (!formRow) return;
        const slider = formRow.querySelector('.numeric-slider-range');
        if (!slider) return;
        const isNullInput = document.getElementById(`${slider.id}_is_null`);
        if (isNullInput) {
            isNullInput.value = slider.dataset.cur_is_null;
            checkbox.checked = isNullInput.value === 'true';
        }
    });
    document.querySelectorAll('.checkbox-include-unknown').forEach(checkbox => {
        checkbox.addEventListener('click', () => {
            const formRow = checkbox.closest('.form-row');
            if (!formRow) return;
            const slider = formRow.querySelector('.numeric-slider-range');
            if (!slider) return;
            const isNullInput = document.getElementById(`${slider.id}_is_null`);
            if (isNullInput) {
                isNullInput.value = checkbox.checked.toString();
            }
        });
    });
});