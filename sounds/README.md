# Sounds

`fahh.mp3` plays when one of the `fahhPlayers` (see `index.html`) is sold,
instead of that team's usual sound.

## Files

- **`fahh.mp3`** — what the page plays. The meme clip with its leading silence
  removed: 3.63s, 44.1kHz stereo. Sound starts 21ms in instead of 0.93s in.
- **`Fahh - meme sound effect.mp3`** — the untrimmed original (4.53s), kept as
  the source so the trim can be redone.
- **`trim_silence.py`** — regenerates `fahh.mp3` from the original.
- **`make_fahh.py`** / **`fahh.wav`** — a synthesized stand-in from before the
  real clip was available. No longer used by the page; safe to delete.

## Re-trimming

```
python3 sounds/trim_silence.py "Fahh - meme sound effect.mp3" fahh.mp3
```

This cuts on MPEG frame boundaries and copies the frames through, so there's no
re-encode and no generation loss — verified sample-identical to the original
past the cut point. It keeps 10ms of preroll ahead of the first audible sample
to preserve the attack and cover the decoder's priming delay.

Autodetection needs `miniaudio` (`pip install miniaudio`). Without it, pass the
cut point yourself:

```
python3 sounds/trim_silence.py in.mp3 out.mp3 --cut 0.925
```

## Note

`fahh.mp3` still has ~1.4s of *trailing* silence (audio ends at 2.24s of 3.63s).
Harmless for playback — it just ends. To drop it too, trim from the tail.
