#!/usr/bin/env python3
"""Generate sounds/fahh.wav -- a synthesized "fahh" vocal exclamation.

Klatt-style parallel formant synthesis: a Rosenberg glottal pulse train
excites four /ah/ formant resonators, preceded by a noise burst for the /f/.
Pure stdlib (no numpy) so it runs anywhere.

    python3 sounds/make_fahh.py
"""

import math
import os
import struct
import wave

FS = 44100
DUR = 0.80

# /ah/ formants: center freq, bandwidth, relative amplitude.
FORMANTS = [(730, 70, 1.00), (1090, 100, 0.50), (2440, 140, 0.18), (3400, 180, 0.08)]

# Pitch contour: a rise into the vowel, then a long fall (an exclamation).
F0_POINTS = [(0.07, 205), (0.16, 240), (0.35, 225), (0.80, 150)]
# Loudness contour for the vowel.
AMP_POINTS = [(0.07, 0.0), (0.14, 1.0), (0.40, 0.95), (0.62, 0.60), (0.80, 0.0)]
# Loudness contour for the /f/ fricative.
FRIC_POINTS = [(0.0, 0.0), (0.02, 1.0), (0.07, 0.85), (0.12, 0.0)]

# Tuned so the /f/ sits ~13 dB under the vowel: audible, but not a hiss.
FRIC_LEVEL = 1.8
BREATH_LEVEL = 0.03
VIBRATO_HZ = 5.2
VIBRATO_DEPTH = 0.012
PEAK = 0.89


def envelope(points, t):
    """Piecewise-linear interpolation over (time, value) points."""
    if t <= points[0][0]:
        return points[0][1]
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return points[-1][1]


class Resonator:
    """Two-pole Klatt resonator."""

    def __init__(self, freq, bandwidth):
        r = math.exp(-math.pi * bandwidth / FS)
        self.c = -(r * r)
        self.b = 2.0 * r * math.cos(2.0 * math.pi * freq / FS)
        self.a = 1.0 - self.b - self.c
        self.y1 = 0.0
        self.y2 = 0.0

    def step(self, x):
        y = self.a * x + self.b * self.y1 + self.c * self.y2
        self.y2 = self.y1
        self.y1 = y
        return y


def rosenberg(phase, open_frac=0.40, close_frac=0.16):
    """Rosenberg glottal flow pulse over one normalized period."""
    if phase < open_frac:
        return 0.5 * (1.0 - math.cos(math.pi * phase / open_frac))
    if phase < open_frac + close_frac:
        return math.cos(math.pi * (phase - open_frac) / (2.0 * close_frac))
    return 0.0


def synthesize():
    n_samples = int(FS * DUR)
    # Deterministic noise so reruns produce a byte-identical file.
    rng_state = 0x2545F4914F6CDD1D

    def noise():
        nonlocal rng_state
        rng_state = (rng_state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        return ((rng_state >> 40) / float(1 << 23)) - 1.0

    resonators = [(Resonator(f, bw), amp) for f, bw, amp in FORMANTS]
    fric_res = Resonator(5000, 4000)

    phase = 0.0
    prev_flow = 0.0
    out = []

    for n in range(n_samples):
        t = n / FS

        # --- voiced /ah/ ---
        f0 = envelope(F0_POINTS, t)
        f0 *= 1.0 + VIBRATO_DEPTH * math.sin(2.0 * math.pi * VIBRATO_HZ * t)
        phase += f0 / FS
        if phase >= 1.0:
            phase -= 1.0

        flow = rosenberg(phase)
        # Differentiate the flow: the derivative is what excites the tract.
        source = (flow - prev_flow) * FS / f0
        prev_flow = flow
        source += BREATH_LEVEL * noise()
        source *= envelope(AMP_POINTS, t)

        vowel = 0.0
        for res, amp in resonators:
            vowel += amp * res.step(source)

        # --- /f/ fricative burst ---
        fric = fric_res.step(noise()) * envelope(FRIC_POINTS, t) * FRIC_LEVEL

        out.append(vowel * 0.30 + fric)

    # Normalize, then fade the edges to kill clicks.
    peak = max(abs(s) for s in out) or 1.0
    scale = PEAK / peak
    fade_in = int(0.003 * FS)
    fade_out = int(0.020 * FS)
    for i in range(n_samples):
        g = scale
        if i < fade_in:
            g *= i / fade_in
        if i > n_samples - fade_out:
            g *= (n_samples - i) / fade_out
        out[i] *= g
    return out


def main():
    samples = synthesize()
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fahh.wav")
    frames = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FS)
        w.writeframes(frames)
    print("wrote %s (%d frames, %.2fs)" % (path, len(samples), len(samples) / FS))


if __name__ == "__main__":
    main()
