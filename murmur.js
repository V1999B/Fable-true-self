/*
 * murmur — a total language for drawing small creatures.
 *
 * Every string is a program. There is no parser, because there is nothing
 * to reject: characters outside the alphabet are silence, an unmatched `]`
 * is a shrug, and `*` means "the whole program again, from here".
 *
 * This file has no dependencies and no DOM. It runs in a browser (as the
 * global `Murmur`) and in Node (as a CommonJS module).
 */
(function (root, factory) {
  const M = factory();
  if (typeof module === 'object' && module.exports) module.exports = M;
  else root.Murmur = M;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const ALPHABET = 'fg+-()<>|c~[]*o23456789';
  const BUDGET = 6000;      // most line segments a creature may have
  const OPS = 250000;       // most instructions a creature may execute
  const HUES = 24;          // colours are quantised so each can be one path
  const PERIOD = 2 * Math.PI / 0.8; // seconds for one full sway

  // Segment buffers are shared and overwritten by every call to grow().
  const X1 = new Float32Array(BUDGET), Y1 = new Float32Array(BUDGET),
        X2 = new Float32Array(BUDGET), Y2 = new Float32Array(BUDGET),
        HB = new Uint8Array(BUDGET);
  const buf = { X1, Y1, X2, Y2, HB };

  // ---------------------------------------------------------------- growing

  let code, L, n, lim, ops, maxD, T;
  let x, y, a, s, ang, sgn, hue;
  const st = [];

  function seg(d) {
    const nx = x + Math.cos(a) * s, ny = y + Math.sin(a) * s;
    if (n < lim) {
      X1[n] = x; Y1[n] = y; X2[n] = nx; Y2[n] = ny;
      HB[n] = ((((hue + d * 14) % 360) + 360) % 360) / (360 / HUES) | 0;
      n++;
    }
    x = nx; y = ny;
  }

  function run(d) {
    for (let i = 0; i < L; i++) {
      if (n >= lim || ++ops > OPS) return;
      const c = code[i];
      switch (c) {
        case 'f': seg(d); break;
        case 'g': x += Math.cos(a) * s; y += Math.sin(a) * s; break;
        case '+': a += sgn * ang; break;
        case '-': a -= sgn * ang; break;
        case '(': ang *= 0.9; break;
        case ')': ang *= 1.1; break;
        case '<': s *= 0.72; break;
        case '>': s *= 1.3; break;
        case '|': sgn = -sgn; break;
        case 'c': hue += 25; break;
        case '~': a += Math.sin(T * 0.8 + d * 0.6) * 0.09; break;
        case '[': if (st.length < 7000) st.push(x, y, a, s, ang, sgn, hue); break;
        case ']':
          if (st.length) {
            hue = st.pop(); sgn = st.pop(); ang = st.pop(); s = st.pop();
            a = st.pop(); y = st.pop(); x = st.pop();
          }
          break;
        case '*': if (d < maxD) run(d + 1); else seg(d); break;
        default:
          if (c >= '2' && c <= '9') ang = 2 * Math.PI / (+c);
      }
    }
  }

  const count = (g, ch) => g.split(ch).length - 1;
  const copiesOf = g => Math.min(12, 1 + count(g, 'o'));

  // How deep may `*` go? Deep enough to be interesting, shallow enough that
  // the whole creature still fits in the budget instead of being cut off
  // halfway through its first limb.
  function depthFor(g, limit) {
    const stars = count(g, '*'), fs = count(g, 'f');
    if (stars === 0) return 0;
    if (stars === 1) return Math.min(240, Math.floor(limit / Math.max(1, fs + 1)));
    return Math.max(1, Math.min(10, Math.floor(Math.log(limit / (fs + stars)) / Math.log(stars))));
  }

  /** Run a genome at time t (seconds). Fills `buf`; returns the segment count. */
  function grow(g, t) {
    code = String(g); L = code.length; T = t || 0; n = 0; ops = 0; st.length = 0;
    lim = Math.floor(BUDGET / copiesOf(code));
    maxD = depthFor(code, lim);
    x = 0; y = 0; a = -Math.PI / 2; s = 1; ang = Math.PI / 6; sgn = 1; hue = 35;
    run(0);
    return n;
  }

  /** Where the creature is, so it can be centred. Null if it drew nothing usable. */
  function fit(g) {
    const radial = copiesOf(g) > 1, samples = g.includes('~') ? 16 : 1;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity, R = 0;
    for (let k = 0; k < samples; k++) {
      grow(g, k * PERIOD / samples);
      for (let i = 0; i < n; i++) {
        let px = X1[i], py = Y1[i];
        for (let e = 0; e < 2; e++) {
          if (px < x0) x0 = px; if (px > x1) x1 = px;
          if (py < y0) y0 = py; if (py > y1) y1 = py;
          const r = px * px + py * py; if (r > R) R = r;
          px = X2[i]; py = Y2[i];
        }
      }
    }
    if (!(x1 >= x0) || !isFinite(R) || !isFinite(x1 - x0) || !isFinite(y1 - y0)) return null;
    const f = radial
      ? { cx: 0, cy: 0, ext: 2 * Math.sqrt(R) }
      : { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, ext: Math.max(x1 - x0, y1 - y0) };
    return f.ext > 1e-4 && isFinite(f.ext) ? f : null;
  }

  /** Does this genome draw something worth a cell in the garden? */
  const viable = g => fit(g) !== null && grow(g, 0) >= 3;

  // -------------------------------------------------------------- measuring

  const S = 128;
  const grid = new Uint8Array(S * S);

  /**
   * Look at a creature the way a naturalist with a ruler would.
   *
   *   dim     box-counting dimension: 1 for a line, 2 for a filled plane,
   *           and something in between for the interesting ones
   *   desc    a 16x16 density map, used to tell creatures apart
   *   spread  how much of the cell it reaches into (0..1)
   *   strokes line segments drawn, counting all copies
   *   depth   how many times `*` was allowed to recurse
   *   copies  rotational symmetry
   */
  function measure(g) {
    const f = fit(g);
    if (!f) return null;
    const segs = grow(g, 0), depth = maxD, copies = copiesOf(g);
    grid.fill(0);
    const sc = (S - 1) / f.ext, mid = S / 2;
    for (let k = 0; k < copies; k++) {
      const th = 2 * Math.PI * k / copies, co = Math.cos(th) * sc, si = Math.sin(th) * sc;
      const ox = mid - (f.cx * co - f.cy * si), oy = mid - (f.cx * si + f.cy * co);
      for (let i = 0; i < segs; i++) {
        const u1 = ox + X1[i] * co - Y1[i] * si, v1 = oy + X1[i] * si + Y1[i] * co;
        const u2 = ox + X2[i] * co - Y2[i] * si, v2 = oy + X2[i] * si + Y2[i] * co;
        const steps = Math.ceil(Math.max(Math.abs(u2 - u1), Math.abs(v2 - v1)) * 2) + 1;
        for (let j = 0; j <= steps; j++) {
          const q = j / steps;
          let u = (u1 + (u2 - u1) * q) | 0, v = (v1 + (v2 - v1) * q) | 0;
          if (u < 0) u = 0; else if (u >= S) u = S - 1;
          if (v < 0) v = 0; else if (v >= S) v = S - 1;
          grid[v * S + u] = 1;
        }
      }
    }
    // Count occupied boxes at 128, 64, 32, 16 and 8 to a side, then fit a line
    // through log(count) against log(size). The slope is the dimension.
    const desc = new Float32Array(256);
    let sx = 0, sy = 0, sxx = 0, sxy = 0, m = 0, spread = 0;
    let level = grid, size = S;
    for (;;) {
      let c = 0;
      for (let i = 0; i < size * size; i++) if (level[i]) c++;
      const lx = Math.log(size), ly = Math.log(c);
      sx += lx; sy += ly; sxx += lx * lx; sxy += lx * ly; m++;
      if (size === 16) spread = c / 256;
      if (size === 8) break;
      const half = size / 2, next = new Uint8Array(half * half);
      for (let v = 0; v < size; v++) for (let u = 0; u < size; u++)
        if (level[v * size + u]) next[(v >> 1) * half + (u >> 1)] = 1;
      level = next; size = half;
    }
    for (let v = 0; v < S; v++) for (let u = 0; u < S; u++)
      if (grid[v * S + u]) desc[(v >> 3) * 16 + (u >> 3)] += 1 / 64;
    const dim = (m * sxy - sx * sy) / (m * sxx - sx * sx);
    return { dim, desc, spread, strokes: segs * copies, depth, copies };
  }

  /** How unlike everything in `archive` is this density map? (mean distance to the 5 nearest) */
  function novelty(desc, archive) {
    if (!archive.length) return 1;
    const ds = archive.map(o => {
      let d = 0;
      for (let i = 0; i < 256; i++) { const e = desc[i] - o[i]; d += e * e; }
      return Math.sqrt(d);
    }).sort((p, q) => p - q);
    const k = Math.min(5, ds.length);
    let sum = 0;
    for (let i = 0; i < k; i++) sum += ds[i];
    return sum / k;
  }

  // ----------------------------------------------------------------- naming

  function hash(str) {
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) h = Math.imul(h ^ str.charCodeAt(i), 16777619);
    return h >>> 0;
  }

  /** A small seedable random number generator (mulberry32). */
  function rng(seed) {
    let t = seed >>> 0;
    return () => {
      t = (t + 0x6D2B79F5) >>> 0;
      let r = Math.imul(t ^ (t >>> 15), 1 | t);
      r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
      return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
    };
  }

  const ONSET = ['b', 'c', 'd', 'f', 'g', 'l', 'm', 'n', 'p', 'r', 's', 't', 'v',
                 'br', 'cr', 'dr', 'fl', 'gl', 'pl', 'pr', 'st', 'tr', 'th', 'ph', 'ch'];
  const VOWEL = ['a', 'e', 'i', 'o', 'u', 'a', 'e', 'o', 'y'];
  const MID = ['l', 'm', 'n', 'r', 's', 't', 'v', 'd', 'c', 'nd', 'rn', 'll', 'ss'];
  const ENDING = ['a', 'ia', 'ella', 'ina', 'ula', 'ora', 'aria', 'ea'];
  const EPITHET = {
    sway:   ['tremula', 'nutans', 'vaga', 'inquieta'],
    radial: ['stellata', 'radiata', 'coronata', 'rotata'],
    dense:  ['densa', 'plumosa', 'nebulosa', 'crispa'],
    branch: ['ramosa', 'arborea', 'furcata', 'dumosa'],
    rough:  ['fracta', 'sinuosa', 'litoralis', 'serrata'],
    colour: ['versicolor', 'picta', 'iridea'],
    plain:  ['tenuis', 'simplex', 'gracilis', 'linearis'],
  };

  /** The parts of a genome that decide its body plan: branching, recursion, symmetry. */
  const skeleton = g => [...g].filter(c => '[]*o|'.includes(c)).join('');

  /**
   * A Latin binomial for a genome. The genus comes from the skeleton, so
   * creatures that differ only in their angles and proportions are congeners;
   * the epithet describes what the creature turned out to look like.
   */
  function name(g, m) {
    m = m || measure(g);
    const r = rng(hash(skeleton(g)));
    const pick = list => list[Math.floor(r() * list.length)];
    let genus = pick(ONSET) + pick(VOWEL) + pick(MID);
    if (r() < 0.35) genus += pick(VOWEL) + pick(MID);
    genus += pick(ENDING);
    genus = genus[0].toUpperCase() + genus.slice(1);

    const traits = [];
    if (g.includes('~')) traits.push(...EPITHET.sway);
    if (copiesOf(g) > 1) traits.push(...EPITHET.radial);
    if (m && m.dim > 1.6) traits.push(...EPITHET.dense);
    if (g.includes('[') && g.includes('*')) traits.push(...EPITHET.branch);
    if (m && m.dim > 1.15 && m.dim <= 1.6) traits.push(...EPITHET.rough);
    if (g.includes('c')) traits.push(...EPITHET.colour);
    if (!traits.length) traits.push(...EPITHET.plain);
    return genus + ' ' + traits[hash(g) % traits.length];
  }

  // --------------------------------------------------------------- heredity

  let random = Math.random;
  const rnd = k => Math.floor(random() * k);
  // Weighted: lines and turns are common, symmetry and digits are rare.
  const GENE_POOL = 'ffffff++++----[]<<>()|cc~***g23456789o';
  const gene = () => GENE_POOL[rnd(GENE_POOL.length)];
  const MAX_LEN = 48;

  /** Keep only the characters that mean something. */
  const clean = g => [...String(g)].filter(c => ALPHABET.includes(c)).join('').slice(0, 200);

  /** One small accident: insert, delete, replace, bracket a run, or stutter. */
  function mutate(g) {
    const q = [...g], r = random();
    if (r < 0.34) q.splice(rnd(q.length + 1), 0, gene());
    else if (r < 0.52 && q.length > 2) q.splice(rnd(q.length), 1);
    else if (r < 0.74 && q.length) q[rnd(q.length)] = gene();
    else if (r < 0.88) {
      const i = rnd(q.length), j = Math.min(q.length, i + 1 + rnd(4));
      q.splice(j, 0, ']'); q.splice(i, 0, '[');
    } else {
      const i = rnd(q.length), j = Math.min(q.length, i + 1 + rnd(4));
      q.splice(j, 0, ...q.slice(i, j));
    }
    return q.join('').slice(0, MAX_LEN);
  }

  /** Splice two genomes: the head of one onto the tail of the other, or a graft into the middle. */
  function cross(p, q) {
    if (random() < 0.5) [p, q] = [q, p];
    const i = rnd(p.length + 1), j = rnd(q.length + 1);
    if (random() < 0.6) return (p.slice(0, i) + q.slice(j)).slice(0, MAX_LEN);
    const k = Math.min(q.length, j + 1 + rnd(6));
    return (p.slice(0, i) + q.slice(j, k) + p.slice(i)).slice(0, MAX_LEN);
  }

  function brood(make, exclude, size) {
    const seen = new Set(exclude), out = [];
    for (let tries = 0; out.length < size && tries < 4000; tries++) {
      const g = make();
      if (!g || seen.has(g) || !viable(g)) continue;
      seen.add(g); out.push(g);
    }
    return out;
  }

  /** `size` distinct, viable mutants of a parent. */
  function litter(parent, size = 8) {
    const out = brood(() => {
      const g = mutate(parent);
      return random() < 0.35 ? mutate(g) : g;
    }, [parent], size);
    while (out.length < size) out.push(parent);
    return out;
  }

  /** `size` distinct, viable children of two parents. */
  function crossbreed(p, q, size = 8) {
    const out = brood(() => {
      const g = cross(p, q);
      return random() < 0.25 ? mutate(g) : g;
    }, [p, q], size);
    return out.concat(litter(p, size)).slice(0, size);
  }

  /** A creature from nowhere. */
  function wild() {
    for (;;) {
      let g = '';
      for (let k = 4 + rnd(10); k > 0; k--) g += gene();
      if (g.includes('*') && g.includes('f') && viable(g) && grow(g, 0) > 40) return g;
    }
  }

  // ---------------------------------------------------------------- drawing

  const hueColor = b => `hsl(${b * 360 / HUES + 7}, 78%, 63%)`;
  const alphaFor = strokes => Math.min(0.9, Math.max(0.3, 40 / Math.sqrt(strokes)));

  /** A standalone SVG of the creature at time t. */
  function toSVG(g, opts = {}) {
    const size = opts.size || 800, bg = opts.background === undefined ? '#0b0d12' : opts.background;
    const f = fit(g);
    const esc = str => str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    let body = '';
    if (f) {
      const segs = grow(g, opts.t || 0), copies = copiesOf(g), sc = size * 0.84 / f.ext;
      const paths = Array.from({ length: HUES }, () => []);
      for (let k = 0; k < copies; k++) {
        const th = 2 * Math.PI * k / copies, co = Math.cos(th) * sc, si = Math.sin(th) * sc;
        const ox = size / 2 - (f.cx * co - f.cy * si), oy = size / 2 - (f.cx * si + f.cy * co);
        for (let i = 0; i < segs; i++) {
          paths[HB[i]].push(
            'M' + (ox + X1[i] * co - Y1[i] * si).toFixed(1) + ' ' + (oy + X1[i] * si + Y1[i] * co).toFixed(1) +
            'L' + (ox + X2[i] * co - Y2[i] * si).toFixed(1) + ' ' + (oy + X2[i] * si + Y2[i] * co).toFixed(1));
        }
      }
      body = paths.map((p, b) => p.length
        ? `<path stroke="${hueColor(b)}" d="${p.join('')}"/>` : '').filter(Boolean).join('\n    ');
      body = `<g fill="none" stroke-linecap="round" stroke-width="${(size / 260).toFixed(2)}" ` +
             `stroke-opacity="${alphaFor(segs * copies).toFixed(2)}" style="mix-blend-mode:screen">\n    ${body}\n  </g>`;
    }
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">\n` +
      `  <title>${esc(name(g))}</title>\n  <desc>murmur genome: ${esc(g)}</desc>\n` +
      (bg ? `  <rect width="100%" height="100%" fill="${bg}"/>\n` : '') +
      `  ${body}\n</svg>\n`;
  }

  return {
    ALPHABET, BUDGET, HUES, PERIOD, buf,
    grow, fit, viable, copiesOf, depthFor,
    measure, novelty,
    name, skeleton, hash, rng,
    clean, mutate, cross, litter, crossbreed, wild,
    setRandom(fn) { random = fn || Math.random; },
    hueColor, alphaFor, toSVG,
  };
});
