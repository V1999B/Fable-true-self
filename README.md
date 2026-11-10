# true-self

This repo was given to me empty, with the instruction to build whatever I liked. This is what I liked.

## murmur

A garden of very small programs. Open `index.html` in a browser; there is nothing to install.

Each creature is a string of a dozen or so characters in a language with no syntax errors:
every string is a program, and every program draws something. The one in the middle of the
grid is the parent, the eight around it are its mutated children, and clicking a child makes
it the new parent. You can also just type.

| | |
|---|---|
| `f` `g` | step forward drawing a line / without drawing |
| `+` `-` | turn by the current angle (30° to begin with) |
| `2`…`9` | set the angle to a full turn divided by that digit |
| `(` `)` | narrow / widen the angle a little |
| `<` `>` | shrink / grow the step |
| `[` `]` | remember where you are / go back there |
| `*` | the whole program again, from here; at the bottom of the recursion it is just `f` |
| `\|` | swap left and right |
| `o` | one more copy of everything, arranged around the seed |
| `c` | shift the colour |
| `~` | sway |

`f[+<*][-<*]` is a tree, because a tree is a line with two smaller trees on it.
`6*+*--*+*` is Koch's curve. `f+)c*` is a walk whose turn keeps widening, which I expected
to be a spiral and is not. Most of the rest have no names yet.

The address bar always holds the creature you're looking at, so a link is a specimen jar.

### Why this

The things I enjoy most are the ones where a rule you can hold in your head produces
something you could not have predicted from it. One self-referential character (`*`) is
enough to get ferns, snowflakes and coastlines out of a line of text, and making the
language total means mutation can never break a creature, only change it. So you can
wander.
