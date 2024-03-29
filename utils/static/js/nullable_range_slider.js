// This files must be included after the range_slider.js file.

"use strict";
$(function() {

    const checkboxIncludeUnknown = $(".checkbox-include-unknown");

    checkboxIncludeUnknown.each(function() {
        const checkbox = $(this);
        const formRow = checkbox.closest(".form-row");
        const slider = formRow.find(".numeric-slider-range");
        const isNullInput = $(`#${slider.attr("id")}_is_null`);
        isNullInput.val(slider.data("cur_is_null"));
        checkbox.prop('checked', isNullInput.val() === "true");
    });
    checkboxIncludeUnknown.on('click', function() {
        const checkbox = $(this);
        const formRow = checkbox.closest(".form-row");
        const sliderId = formRow.find(".numeric-slider-range").attr("id");
        const isNullInput = $(`#${sliderId}_is_null`);

        isNullInput.val(checkbox.is(':checked'));
    });
});