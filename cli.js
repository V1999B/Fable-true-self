#!/usr/bin/env node
'use strict';
const M = require('./murmur.js');

const USAGE = `murmur — grow a creature from a string

  murmur '<genome>'            write the creature to stdout as SVG
  murmur --describe '<genome>' name it and measure it
  murmur --wild                grow one from nowhere (add --describe to only name it)
  murmur --litter '<genome>'   list eight mutant children

options
  --size <px>    SVG width and height (default 800)
  --time <sec>   moment to draw a swaying creature at (default 0)
  --bare         no background rectangle

Quote the genome: most of its alphabet means something to a shell too.
`;

// `murmur ... | head` should end quietly, not with a stack trace
process.stdout.on('error', e => { if (e.code === 'EPIPE') process.exit(0); throw e; });

const args = process.argv.slice(2);
const flag = name => { const i = args.indexOf(name); return i < 0 ? false : (args.splice(i, 1), true); };
const option = (name, fallback) => {
  const i = args.indexOf(name);
  if (i < 0) return fallback;
  const v = Number(args[i + 1]); args.splice(i, 2);
  if (!Number.isFinite(v)) { process.stderr.write(`${name} needs a number\n`); process.exit(2); }
  return v;
};

if (flag('--help') || flag('-h') || !args.length) { process.stdout.write(USAGE); process.exit(args.length ? 0 : 2); }
const describe = flag('--describe'), wild = flag('--wild'), litter = flag('--litter'), bare = flag('--bare');
const size = option('--size', 800), t = option('--time', 0);
const genome = wild ? M.wild() : M.clean(args[0] || '');

if (litter) {
  for (const kid of M.litter(genome)) console.log(kid.padEnd(50) + M.name(kid));
} else if (describe) {
  const m = M.measure(genome);
  console.log(genome);
  if (!m) console.log('a quiet one: it runs, but leaves nothing you can see');
  else {
    console.log(M.name(genome, m));
    console.log(`dimension ${m.dim.toFixed(2)} · ${m.strokes} strokes · ` +
      (m.depth ? `${m.depth} deep` : 'no recursion') + (m.copies > 1 ? ` · ${m.copies}-fold` : ''));
  }
} else {
  if (wild) process.stderr.write(genome + '\n');
  process.stdout.write(M.toSVG(genome, { size, t, background: bare ? null : undefined }));
}
