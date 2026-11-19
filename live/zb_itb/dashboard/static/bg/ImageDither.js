/* ImageDither: an image, pixelated and ordered-dithered (8x8 Bayer) in WebGL, after React Bits' Dither background
   (reactbits.dev/backgrounds/dither, MIT). React Bits' Dither dithers generated waves; this one dithers a photo.
   No interaction: slow, non-linear (domain-warped noise) waves drift through the image on their own, bending the
   pixel grid and changing how coarse the dither is as they pass.
   The image is stretched to fill the viewport (no cropping). */
(function () {
  const { useEffect, useRef } = React;

  const VERT = `attribute vec2 p; void main(){ gl_Position = vec4(p, 0.0, 1.0); }`;
  const FRAG = `
precision highp float;
uniform sampler2D uTex;
uniform vec2 uRes;        // canvas px
uniform float uTime;
uniform float uPixel;     // dither cell, px
uniform float uColors;    // levels per channel
uniform float uAmp;       // wave displacement, px
uniform float uSpeed;
uniform vec3 uTint;
uniform float uTintMix;

float bayer8(vec2 a) {
  a = floor(mod(a, 8.0));
  float v = 0.0;
  vec2 b = a;
  for (int i = 0; i < 3; i++) {
    vec2 q = mod(b, 2.0);
    v = v * 4.0 + (q.x * 2.0 + q.y * 3.0 - q.x * q.y * 4.0);   // 2x2 Bayer [[0,2],[3,1]]
    b = floor(b / 2.0);
  }
  return v / 64.0;
}

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0.0, a = 0.5;
  mat2 r = mat2(0.8, -0.6, 0.6, 0.8);
  for (int i = 0; i < 5; i++) { v += a * noise(p); p = r * p * 2.03 + 11.7; a *= 0.5; }
  return v;
}

void main() {
  vec2 frag = gl_FragCoord.xy;
  float t = uTime * uSpeed;
  // domain warping: noise fed through noise gives folding, non-linear waves
  vec2 p = frag / uRes * vec2(uRes.x / uRes.y, 1.0) * 2.2;
  vec2 q = vec2(fbm(p + vec2(0.0, t * 0.30)), fbm(p + vec2(5.2, 1.3) - t * 0.22));
  vec2 r = vec2(fbm(p + 3.5 * q + vec2(1.7, 9.2) + t * 0.15), fbm(p + 3.5 * q + vec2(8.3, 2.8) - t * 0.18));
  vec2 warped = frag + (r - 0.5) * 2.0 * uAmp;

  vec2 cellPos = floor(warped / uPixel);
  vec2 uv = clamp((cellPos + 0.5) * uPixel / uRes, 0.0, 1.0);
  vec3 col = texture2D(uTex, vec2(uv.x, 1.0 - uv.y)).rgb;   // stretched to fill
  col = mix(col, col * uTint * 1.6, uTintMix);
  col *= 0.88 + 0.28 * fbm(p * 0.8 + 2.0 * r - t * 0.1);      // the waves also shade the image a little

  // the waves drive the dither: crests get finer shading, troughs crush down to a few levels
  float w = smoothstep(0.3, 0.75, fbm(p * 1.3 + 3.0 * r + vec2(t * 0.25, -t * 0.2)));
  float levels = floor(mix(2.0, uColors + 2.0, w) + 0.5);
  float t8 = bayer8(floor(frag / uPixel)) - 0.5;
  vec3 qc = floor(col * (levels - 1.0) + t8 + 0.5) / (levels - 1.0);
  gl_FragColor = vec4(clamp(qc, 0.0, 1.0), 1.0);
}`;

  function ImageDither({ imageSrc, pixelSize = 4, colorNum = 4, amplitude = 28, speed = 0.35,
                         tint = [1, 1, 1], tintMix = 0, className = "" }) {
    const box = useRef(null);
    useEffect(() => {
      const host = box.current;
      const cv = document.createElement("canvas");
      cv.className = "image-dither-canvas";
      host.appendChild(cv);
      const gl = cv.getContext("webgl", { antialias: false, premultipliedAlpha: false });
      if (!gl) return () => cv.remove();
      const sh = (t, src) => { const s = gl.createShader(t); gl.shaderSource(s, src); gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) console.error(gl.getShaderInfoLog(s)); return s; };
      const pr = gl.createProgram();
      gl.attachShader(pr, sh(gl.VERTEX_SHADER, VERT)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, FRAG));
      gl.linkProgram(pr); gl.useProgram(pr);
      const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
      const loc = gl.getAttribLocation(pr, "p"); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
      const U = (n) => gl.getUniformLocation(pr, n);
      const u = { res: U("uRes"), time: U("uTime"), pixel: U("uPixel"), colors: U("uColors"), amp: U("uAmp"),
                  speed: U("uSpeed"), tint: U("uTint"), tintMix: U("uTintMix") };

      const tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([0, 0, 0, 255]));
      let ready = false;
      const img = new Image();
      img.onload = () => { gl.bindTexture(gl.TEXTURE_2D, tex); gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img); ready = true; };
      img.src = imageSrc;

      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const fit = () => { cv.width = Math.max(1, host.clientWidth * dpr); cv.height = Math.max(1, host.clientHeight * dpr); gl.viewport(0, 0, cv.width, cv.height); };
      fit();
      const ro = new ResizeObserver(fit); ro.observe(host);

      const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const t0 = performance.now(); let raf = 0;
      const frame = (now) => {
        gl.uniform2f(u.res, cv.width, cv.height);
        gl.uniform1f(u.time, reduce ? 0 : (now - t0) / 1000);
        gl.uniform1f(u.pixel, pixelSize * dpr);
        gl.uniform1f(u.colors, colorNum);
        gl.uniform1f(u.amp, amplitude * dpr);
        gl.uniform1f(u.speed, speed);
        gl.uniform3f(u.tint, tint[0], tint[1], tint[2]);
        gl.uniform1f(u.tintMix, tintMix);
        if (ready) gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
        raf = requestAnimationFrame(frame);
      };
      raf = requestAnimationFrame(frame);
      return () => {
        cancelAnimationFrame(raf); ro.disconnect();
        const lose = gl.getExtension("WEBGL_lose_context"); if (lose) lose.loseContext();
        cv.remove();
      };
    }, [imageSrc, pixelSize, colorNum, amplitude, speed, tintMix]);
    return React.createElement("div", { ref: box, className: "image-dither-container " + className });
  }
  window.ImageDither = ImageDither;
})();
