"use strict";

// Format number based on the specified format
function formatNumber(value, format, step) {
  // Convert to number first
  const numValue = Number(value);

  // Handle different format options
  switch (format) {
    case 'integer':
      return Math.round(numValue).toString();
    case 'float-1':
      return numValue.toFixed(1);
    case 'float-2':
      return numValue.toFixed(2);
    case 'auto':
    default:
      // Auto-detect based on step size
      if (step === 1 || step % 1 === 0) {
        // Integer step, show as integer
        return Math.round(numValue).toString();
      } else if (step < 0.1) {
        // Very small steps, show 2 decimal places
        return numValue.toFixed(2);
      } else {
        // Medium steps, show 1 decimal place
        return numValue.toFixed(1);
      }
  }
}

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
    const numberFormat = sliderElem.dataset.number_format || 'auto';

    noUiSlider.create(sliderElem, {
      start: [startMin, startMax],
      connect: true,
      range: { min: rangeMin, max: rangeMax },
      step
    });

    sliderElem.noUiSlider.on('update', values => {
      const [val0, val1] = values;
      // Store raw values in hidden inputs
      if (minInput) minInput.value = val0;
      if (maxInput) maxInput.value = val1;

      // Format the values for display
      const formattedMin = formatNumber(val0, numberFormat, step);
      const formattedMax = formatNumber(val1, numberFormat, step);

      // Update display text with formatted values
      if (textDisplay) {
        textDisplay.textContent = `${formattedMin}${unit} - ${formattedMax}${unit}`;
      }
    });
  });
});