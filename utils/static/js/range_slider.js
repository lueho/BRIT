"use strict";
$(function() {
    $(".numeric-slider-range").each(function() {
        const slider = $(this);
        const sliderId = slider.attr("id");
        const minInput = $("#" + sliderId + "_min");
        const maxInput = $("#" + sliderId + "_max");
        const textDisplay = $("#" + sliderId + "_text");
        const unit = slider.data("unit");

        slider.slider({
            range: true,
            min: 0,
            max: 100,
            slide: (event, ui) => {
                minInput.val(ui.values[0]);
                maxInput.val(ui.values[1]);
                textDisplay.text(ui.values[0] + `${unit} - ` + ui.values[1] + `${unit}`);
            },
            create: () => {
                minInput.val(slider.data("cur_min"));
                maxInput.val(slider.data("cur_max"));
                slider.slider("option", "step", slider.data("step"));
                slider.slider("option", 'min', slider.data("range_min"));
                slider.slider("option", 'max', slider.data("range_max"));
                slider.slider("option", 'values', [slider.data("cur_min"), slider.data("cur_max")]);
            }
        });
    });
    // const checkboxIncludeUnknown = $(".checkbox-include-unknown");
    // checkboxIncludeUnknown.each(function() {
    //     const checkbox = $(this);
    //     const formRow = checkbox.closest(".form-row");
    //     const slider = formRow.find(".numeric-slider-range");
    //     const isNullInput = $(`#${slider.attr("id")}_is_null`);
    //     isNullInput.val(slider.data("cur_is_null"));
    //     checkbox.prop('checked', isNullInput.val() === "true");
    // });
    // checkboxIncludeUnknown.on('click', function() {
    //     const checkbox = $(this);
    //     const formRow = checkbox.closest(".form-row");
    //     const sliderId = formRow.find(".numeric-slider-range").attr("id");
    //     const isNullInput = $(`#${sliderId}_is_null`);
    //
    //     isNullInput.val(checkbox.is(':checked'));
    // });
});