/* Desk background: one artwork per theme, stretched to fill, ordered-dithered with cursor interaction (ImageDither,
   after React Bits' Dither), with React Bits' Ghost Fibers on top. glint · mummy · flash. */
(function () {
  const host = document.getElementById("bg-scene");
  if (!host || !window.React || !window.ReactDOM || !window.ImageDither || !window.GhostFibers) return;
  const h = React.createElement;

  const LOOKS = {
    glint: {
      image: "bg/glint.jpg", pixel: 4, colors: 5, tint: [0.85, 0.95, 1.1], tintMix: 0.15,
      fibers: { glowColor: "#22d3ee", lineColor: "#e0f7ff", secondaryColor: "#5b21b6", rotation: -14, twist: 2.2 },
    },
    mummy: {
      image: "bg/mummy.jpg", pixel: 4, colors: 4, tint: [1, 1, 1], tintMix: 0,
      fibers: { glowColor: "#c026d3", lineColor: "#f5d0fe", secondaryColor: "#16a34a", rotation: 22, twist: 2.8 },
    },
    flash: {
      image: "bg/flash.jpg", pixel: 4, colors: 3, tint: [1, 1, 1], tintMix: 0,
      fibers: { glowColor: "#cbd5e1", lineColor: "#ffffff", secondaryColor: "#334155", rotation: 8, twist: 1.8 },
    },
  };

  function Scene({ look }) {
    const L = LOOKS[look];
    return h(React.Fragment, null,
      h("div", { className: "bgx-layer bgx-image" },
        h(window.ImageDither, { imageSrc: L.image, pixelSize: L.pixel, colorNum: L.colors, amplitude: 28, speed: 0.35,
                                tint: L.tint, tintMix: L.tintMix })),
      h("div", { className: "bgx-layer bgx-shade" }),
      h("div", { className: "bgx-layer bgx-fibers" },
        h(window.GhostFibers, Object.assign({
          gradient: "along", fiberStyle: "lines", layers: 3, waves: 1.6, threads: 84, volume: 0.85, spread: 1.15,
          density: 1, thickness: 1.15, flow: 0.65, speed: 0.45, rollSpeed: 0.22, scale: 1.05,
          tips: 0.6, foldGlow: 1.3, perspective: 0.7, depthOfField: 0.8, particles: 0.45, sparkle: 0.55,
          glow: 1, brightness: 1.05, vignette: 0.4, grain: 0.06, hoverEffect: "focus", mouseStrength: 1,
          pulseOnClick: true, intro: true,
        }, L.fibers))));
  }

  const root = ReactDOM.createRoot(host);
  let shown = null;
  function sync() {
    const t = document.documentElement.dataset.theme;
    const look = LOOKS[t] ? t : "glint";
    if (look === shown) return;
    shown = look;
    root.render(h(Scene, { look, key: look }));   // key: a new theme remounts both canvases with the new art
  }
  new MutationObserver(sync).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  sync();
})();
