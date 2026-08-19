#!/usr/bin/env python3
"""Strip leading silence from an MP3 without re-encoding it.

Works at MPEG frame granularity (26.12ms for 44.1kHz Layer III), so the audio
data is copied through untouched -- no generation loss, no encoder needed.

    python3 sounds/trim_silence.py "Fahh - meme sound effect.mp3" fahh.mp3

Silence detection needs a decoder (miniaudio). If it isn't importable, pass an
explicit cut point instead:

    python3 sounds/trim_silence.py in.mp3 out.mp3 --cut 0.925
"""

import argparse
import os
import sys

BITRATES_MPEG1 = [None, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, None]
SAMPLE_RATES_MPEG1 = [44100, 48000, 32000, None]
SAMPLES_PER_FRAME = 1152  # MPEG1 Layer III

# Keep a little audio ahead of the first non-zero sample: preserves the attack
# and gives the decoder its ~529-sample priming delay inside the silence.
PREROLL = 0.010
# -60 dBFS. Below this is inaudible and treated as silence.
THRESHOLD = 0.001


def id3v2_size(data):
    """Byte length of a leading ID3v2 tag, or 0 if there isn't one."""
    if len(data) < 10 or data[:3] != b"ID3":
        return 0
    flags = data[5]
    # Syncsafe integer: 7 bits per byte.
    size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
    total = 10 + size
    if flags & 0x10:  # footer present
        total += 10
    return total


def parse_frames(data, start):
    """Yield (offset, length, is_xing) for each MPEG audio frame."""
    pos = start
    end = len(data)
    while pos + 4 <= end:
        if data[pos] != 0xFF or (data[pos + 1] & 0xE0) != 0xE0:
            pos += 1  # resync
            continue
        h = data[pos:pos + 4]
        version = (h[1] >> 3) & 0x03   # 3 = MPEG1
        layer = (h[1] >> 1) & 0x03     # 1 = Layer III
        bitrate_idx = (h[2] >> 4) & 0x0F
        rate_idx = (h[2] >> 2) & 0x03
        padding = (h[2] >> 1) & 0x01
        if version != 3 or layer != 1:
            pos += 1
            continue
        bitrate = BITRATES_MPEG1[bitrate_idx]
        rate = SAMPLE_RATES_MPEG1[rate_idx]
        if not bitrate or not rate:
            pos += 1
            continue
        length = (144 * bitrate * 1000) // rate + padding
        if length <= 4 or pos + length > end:
            break
        tag = data[pos:pos + length]
        is_xing = b"Xing" in tag[:64] or b"Info" in tag[:64]
        yield pos, length, is_xing
        pos += length


def find_cut(path):
    """Seconds of leading silence in `path`, as a suggested cut point."""
    try:
        import miniaudio
    except ImportError:
        sys.exit("miniaudio not importable -- pass --cut SECONDS explicitly")
    d = miniaudio.decode_file(path)
    ch = d.nchannels
    s = d.samples
    n = len(s) // ch
    first = None
    for i in range(n):
        if max(abs(s[i * ch + c]) for c in range(ch)) / 32768.0 > THRESHOLD:
            first = i
            break
    if first is None:
        sys.exit("track appears to be entirely silent")
    return max(0.0, first / d.sample_rate - PREROLL), d.sample_rate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--cut", type=float, default=None,
                    help="seconds to remove from the front (default: autodetect)")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    src = args.src if os.path.isabs(args.src) else os.path.join(here, args.src)
    dst = args.dst if os.path.isabs(args.dst) else os.path.join(here, args.dst)

    data = open(src, "rb").read()

    if args.cut is None:
        cut, rate = find_cut(src)
        print("detected %.4fs of leading silence (incl. %.0fms preroll kept)" % (cut, PREROLL * 1000))
    else:
        cut, rate = args.cut, 44100

    frames = list(parse_frames(data, id3v2_size(data)))
    if not frames:
        sys.exit("no MPEG frames found")

    frame_dur = SAMPLES_PER_FRAME / rate
    drop = int(cut / frame_dur)

    kept = []
    dropped = 0
    for off, length, is_xing in frames:
        if is_xing and not kept and dropped == 0:
            continue  # metadata-only frame, carries no audio
        if dropped < drop:
            dropped += 1
            continue
        kept.append((off, length))

    if not kept:
        sys.exit("cut point is past the end of the file")

    out = b"".join(data[off:off + length] for off, length in kept)
    with open(dst, "wb") as f:
        f.write(out)

    print("frames: %d total, dropped %d (%.4fs), kept %d" % (
        len(frames), dropped, dropped * frame_dur, len(kept)))
    print("wrote %s (%d -> %d bytes)" % (dst, len(data), len(out)))


if __name__ == "__main__":
    main()
