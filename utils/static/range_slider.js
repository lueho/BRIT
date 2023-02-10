"use strict";
$(function() {
    $(".numeric-slider-range").slider({
        range: true,
        min: 0,
        max: 100,
        slide: function(event, ui) {
            $("#" + $(this).parent().attr("id") + "_min").val(ui.values[0]);
            $("#" + $(this).parent().attr("id") + "_max").val(ui.values[1]);
            if ($("#" + $(this).parent().attr("id") + "_text")[0].classList.contains('percentage-slider-values')) {
                $("#" + $(this).parent().attr("id") + "_text").text(ui.values[0] + '% - ' + ui.values[1] + '%');
            } else {
                $("#" + $(this).parent().attr("id") + "_text").text(ui.values[0] + ' - ' + ui.values[1]);
            }

        },
        create: function(event, ui) {
            $("#" + $(this).parent().attr("id") + "_min").val($(this).parent().data("cur_min"));
            $("#" + $(this).parent().attr("id") + "_max").val($(this).parent().data("cur_max"));
            $(this).slider("option", "step", $(this).parent().data("step"));
            $(this).slider("option", 'min', $(this).parent().data("range_min"));
            $(this).slider("option", 'max', $(this).parent().data("range_max"));
            $(this).slider("option", 'values', [$(this).parent().data("cur_min"), $(this).parent().data("cur_max")]);
        }
    });
});