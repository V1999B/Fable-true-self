'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const M = require('../murmur.js');

test('the language is total: no string can make it throw or overrun', () => {
  const r = M.rng(1);
  for (let i = 0; i < 1500; i++) {
    let g = '';
    const len = Math.floor(r() * 60);
    // half from the alphabet, half from all of printable ASCII
    for (let k = 0; k < len; k++) {
      g += r() < 0.5 ? M.ALPHABET[Math.floor(r() * M.ALPHABET.length)]
                     : String.fromCharCode(32 + Math.floor(r() * 95));
    }
    const n = M.grow(g, r() * 10);
    assert.ok(n >= 0 && n <= M.BUDGET, g);
    const f = M.fit(g);
    assert.ok(f === null || (Number.isFinite(f.ext) && f.ext > 0), g);
    if (i % 5 === 0) { M.measure(g); M.name(g); M.toSVG(g); }
  }
});

test('pathological genomes are survivable', () => {
  for (const g of ['', '*', '*'.repeat(200), '['.repeat(5000), ']'.repeat(50),
                   '>'.repeat(40) + '*', '<'.repeat(40) + 'f*', 'o'.repeat(99) + 'f', '[*]*[*]']) {
    assert.doesNotThrow(() => { M.grow(g, 0); M.fit(g); M.measure(g); M.name(g); M.toSVG(g); }, g.slice(0, 20));
  }
});

test('characters outside the alphabet are silence', () => {
  const plain = 'f[+<*][-<*]', noisy = 'hello f[+<* world ][-<*]!';
  assert.equal(M.clean(noisy), 'of[+<*o][-<*]', 'the o in hello and in world are real instructions');
  const a = M.grow(plain, 0), xs = Array.from(M.buf.X2.slice(0, a));
  const b = M.grow('hell f[+<* wrld ][-<*]!', 0);
  assert.equal(a, b);
  assert.deepEqual(Array.from(M.buf.X2.slice(0, b)), xs);
});

test('recursion: Koch has 4^(depth+1) strokes, a binary tree 2^(depth+1) - 1', () => {
  const koch = M.measure('6*+*--*+*');
  assert.equal(koch.strokes, 4 ** (koch.depth + 1));
  const tree = M.measure('f[+<*][-<*]');
  assert.equal(tree.strokes, 2 ** (tree.depth + 2) - 1);
});

test('a creature without ~ does not depend on time', () => {
  M.grow('6*+*--*+*', 0); const a = Array.from(M.buf.Y2.slice(0, 50));
  M.grow('6*+*--*+*', 7.3); assert.deepEqual(Array.from(M.buf.Y2.slice(0, 50)), a);
  M.grow('~f[+<*][-<*]', 0); const b = M.buf.X2[40];
  M.grow('~f[+<*][-<*]', 1); assert.notEqual(M.buf.X2[40], b);
});

test('dimension: lines are 1, known fractals land near their true values', () => {
  const dim = g => M.measure(g).dim;
  assert.ok(Math.abs(dim('ffff') - 1) < 0.03);
  assert.ok(Math.abs(dim('3+ffff') - 1) < 0.08, 'a slanted line is still a line');
  assert.ok(Math.abs(dim('6*+*--*+*') - Math.log(4) / Math.log(3)) < 0.1, 'Koch curve');
  assert.ok(Math.abs(dim('4*+*-*-*+*') - Math.log(5) / Math.log(3)) < 0.1, 'quadratic Koch curve');
  assert.ok(dim('6f[+<*][-<*]<*ooooo') > 1.6, 'a dense thing is dense');
  for (const g of ['ffff', '6*+*--*+*', '8+*--*+', 'f+)c*ooo']) {
    const d = dim(g);
    assert.ok(d > 0.9 && d < 2.05, `${g}: ${d}`);
  }
});

test('novelty: a creature is not new to an archive that contains it', () => {
  const tree = M.measure('f[+<*][-<*]').desc, koch = M.measure('6*+*--*+*').desc;
  assert.equal(M.novelty(tree, [tree]), 0);
  assert.ok(M.novelty(koch, [tree]) > 0.5);
  assert.equal(M.novelty(koch, []), 1);
});

test('names: deterministic binomials, and congeners share a genus', () => {
  const n = M.name('f[+<*][-<*]');
  assert.match(n, /^[A-Z][a-z]+ [a-z]+$/);
  assert.equal(M.name('f[+<*][-<*]'), n);
  // same brackets and stars, different angles and proportions
  assert.equal(M.name('5f[+<<*][--<*]').split(' ')[0], n.split(' ')[0]);
  // a different body plan
  assert.notEqual(M.name('6*+*--*+*').split(' ')[0], n.split(' ')[0]);
});

test('heredity: children are clean, bounded, viable and distinct', () => {
  M.setRandom(M.rng(42));
  try {
    for (const parent of ['f[+<*][-<*]', '6*+*--*+*', '+++', 'f']) {
      const kids = M.litter(parent);
      assert.equal(kids.length, 8);
      for (const k of kids) {
        assert.equal(M.clean(k), k);
        assert.ok(k.length <= 48);
        assert.ok(k === parent || M.viable(k), k);
      }
      assert.ok(new Set(kids).size >= 6, 'mostly distinct');
    }
    const crossed = M.crossbreed('f[+<*][-<*]', '6*+*--*+*');
    assert.equal(crossed.length, 8);
    crossed.forEach(k => assert.ok(M.viable(k), k));
    const w = M.wild();
    assert.ok(M.viable(w) && w.includes('*'));
  } finally { M.setRandom(null); }
});

test('heredity is reproducible under a seeded generator', () => {
  M.setRandom(M.rng(7)); const a = M.litter('f[+<*][-<*]');
  M.setRandom(M.rng(7)); const b = M.litter('f[+<*][-<*]');
  M.setRandom(null);
  assert.deepEqual(a, b);
});

test('svg: one document, escaped genome, a path per colour used', () => {
  const svg = M.toSVG('f[+<*][-<*]', { size: 400 });
  assert.match(svg, /^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg" viewBox="0 0 400 400"/);
  assert.ok(svg.includes('<desc>murmur genome: f[+&lt;*][-&lt;*]</desc>'));
  assert.ok((svg.match(/<path /g) || []).length >= 2);
  assert.ok(!/NaN|Infinity/.test(svg));
  assert.ok(!M.toSVG('+++').includes('<path'), 'a quiet one is an empty picture, not an error');
});
