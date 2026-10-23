/* detail_v2 — shared behaviors for the sectioned detail layout ("sdv2").
   Currently: measures the sticky action rail so --sdv2-rail-height keeps
   anchor scroll offsets correct when the rail wraps onto a second line. */
(function () {
  "use strict";

  const root = document.querySelector(".sdv2");
  if (!root) return;

  const actionRail = root.querySelector(".sdv2-rail");
  if (actionRail && "ResizeObserver" in window) {
    new ResizeObserver(() => {
      root.style.setProperty("--sdv2-rail-height", `${actionRail.offsetHeight}px`);
    }).observe(actionRail);
  }
})();
