"use strict";
// Initialize sliders on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.numeric-slider-range').forEach(sliderElem => {
    const sliderId = sliderElem.id;
    const minInput = document.getElementById(`${sliderId}_min`);
    const maxInput = document.getElementById(`${sliderId}_max`);
    const textDisplay = document.getElementById(`${sliderId}_text`);
    const unit = sliderElem.dataset.unit || '';
    const rangeMin = Number(sliderElem.dataset.range_min);
    const rangeMax = Number(sliderElem.dataset.range_max);
    const step = Number(sliderElem.dataset.step) || 1;
    const startMin = Number(sliderElem.dataset.cur_min) || rangeMin;
    const startMax = Number(sliderElem.dataset.cur_max) || rangeMax;

    noUiSlider.create(sliderElem, {
      start: [startMin, startMax],
      connect: true,
      range: { min: rangeMin, max: rangeMax },
      step
    });

    sliderElem.noUiSlider.on('update', values => {
      const [val0, val1] = values;
      if (minInput) minInput.value = val0;
      if (maxInput) maxInput.value = val1;
      if (textDisplay) textDisplay.textContent = `${val0}${unit} - ${val1}${unit}`;
    });
  });
});