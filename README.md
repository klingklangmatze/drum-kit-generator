# Drum Kit Generator

A Python script that generates random drum kit presets (`.ablpresetbundle`) for **Ableton Move** and **Ableton Note**.

Born out of laziness and a love for happy accidents — instead of building kits by hand, this script scans your sample library and assembles 16-pad drum kits automatically, each one different.

---

## Requirements

- Python 3.10+
- No external dependencies — standard library only

---

## How to Use

1. Edit the `CONFIG` block at the top of the script
2. Run: `python ae_drumkit_generator.py`
3. Upload the generated `.ablpresetbundle` files to Move via Move Manager, or open them directly in Note

---

## Config Reference

### Folders & Naming

```python
SAMPLES_FOLDER = "/Users/yourname/Samples"
OUTPUT_FOLDER  = "/Users/yourname/Kits"
```

Point `SAMPLES_FOLDER` at the root of your sample library — the script scans all subfolders recursively. `OUTPUT_FOLDER` is where the finished `.ablpresetbundle` files land.

```python
KIT_COUNT  = 10        # how many kits to generate
KIT_NAME   = "ae-kit"  # base name → ae-kit-01, ae-kit-02 …
NAME_START = 1         # first number, useful for adding to an existing collection
```

---

### Effects

```python
RETURN_EFFECT          = "reverb"
RANDOM_RETURN_EFFECT   = False
RANDOM_RETURN_SETTINGS = False
```

`RETURN_EFFECT` sets the send/return effect on the drum rack. `INSERT_EFFECT` sits after the drum rack on the main chain. Both accept the same full list of effects:

`reverb` `delay` `autoFilter` `chorus` `phaser` `redux2` `erosion` `autoShift` `autoPan` `channelEq` `saturator` `dynamics`

The `dynamics` option is a special audioEffectRack containing a Channel EQ and Compressor with 8 mapped macros (Low Gain, Mid Gain, High Gain, Comp Hi Pass, Release, Threshold, Output, Comp Dry/Wet).

Set `RANDOM_RETURN_EFFECT = True` to pick a different return effect for every kit. Set `RANDOM_RETURN_SETTINGS = True` to also randomize the effect's parameters. Set `INSERT_EFFECT = "random"` to pick a different insert effect for every kit.

---

### Pad FX Randomization

```python
RANDOMIZE_FX      = True
RANDOMIZE_FX_PADS = [8, 9, 10, 11, 12, 13, 14, 15]  # 0-based, so pad 9–16
TRANSPOSE_RANGE   = (-12, 12)
```

When enabled, pads in `RANDOMIZE_FX_PADS` get randomized:
- **Playback effect** (Stretch, FM, Pitch Env, Punch, Ring Mod, Sub Osc, Noise, 8-Bit, Loop) — chosen per category
- **Filter** type (Lowpass / Highpass / Bandpass), frequency and resonance
- **Transpose** within `TRANSPOSE_RANGE` — weighted toward 0 so extreme shifts are less common
- **Send amount** to the return effect

`TRANSPOSE_RANGE` accepts any range within `(-48, 48)`.

---

### Pan Randomization

```python
RANDOMIZE_PAN      = True
RANDOMIZE_PAN_PADS = "all"
```

Randomizes the stereo position of each pad. Spread varies by category:

| Category | Spread |
|---|---|
| kick, tom, bass | always center |
| snare, rim, clap | very narrow (±0.105) |
| closedHH, openHH, hat, perc, conga, cymbal, crash, ride | wide (±0.49) |
| fx, vox | widest (±0.595) |
| synth, stab, lead, pad, chord | medium (±0.315) |

`RANDOMIZE_PAN_PADS` accepts `"all"` or a list of 0-based pad indices e.g. `[0, 1, 4, 6]`.

---

### Choke Groups

```python
CHOKE_GROUPS_HH = True
```

Assigns hi-hat pads to choke groups automatically:
- `closedHH`, `hat`, `openHH` → choke group 1 (closed chokes open)
- `crash`, `cymbal` → choke group 2

---

### Sample Filtering

```python
SKIP_LOOPS      = True
MAX_SAMPLE_SIZE = "2mb"
```

`SKIP_LOOPS` skips any file that contains `[120]`, `[130bpm]`, `loop` etc. in its name.

`MAX_SAMPLE_SIZE` accepts human-readable sizes: `"500kb"`, `"1.5mb"`, `"2mb"`, or `None` for no limit.

---

### Reproducibility & Output

```python
SEED    = None
VERBOSE = True
```

Set `SEED` to an integer (e.g. `42`) to get the same kits every time you run with the same config. `None` means fully random.

`VERBOSE` prints a full pad map for each kit showing which sample landed on which pad, the playback effect, filter, transpose and pan value.

---

## Advanced Config

These settings live further down in the script and require editing the code directly.

### Pad Layout

`PAD_LAYOUT` maps each of the 16 pads (0-based) to a list of sample categories. The script pools all available samples across all listed categories and picks randomly — so pad 15 is equally likely to get any of its listed categories.

```python
PAD_LAYOUT = {
    0:  ["kick"],
    1:  ["rim", "snare"],
    2:  ["snare"],
    3:  ["clap", "perc"],
    4:  ["snare", "perc", "tom", "conga"],
    5:  ["kick"],
    6:  ["closedHH", "hat"],
    7:  ["tom", "perc", "conga"],
    8:  ["stab", "bass", "synth", "lead"],
    9:  ["perc", "fx", "tom"],
    10: ["openHH", "hat"],
    11: ["perc", "ride", "cymbal"],
    12: ["stab", "bass", "synth", "pad", "lead", "chord"],
    13: ["stab", "chord", "lead", "pad", "synth"],
    14: ["crash", "ride", "cymbal", "fx", "vox"],
    15: ["pad", "synth", "lead", "crash", "ride", "cymbal", "fx", "vox"],
}
```

### Sample Categories

`CATEGORIES` maps category names to filename keywords. A sample is assigned to the first matching category (case-insensitive). Files that don't match any category are skipped.

Recognized categories: `kick` `snare` `rim` `clap` `closedHH` `openHH` `hat` `tom` `conga` `perc` `crash` `ride` `cymbal` `bass` `stab` `synth` `lead` `pad` `chord` `fx` `vox`

You can add your own keywords to any category by editing the `CATEGORIES` dict.

### Playback Effects per Category

Inside `randomize_pad()` you can change which playback effects are available per sample category. For example, to allow Sub Osc on snares:

```python
elif category in ("snare", "rim"):
    effect = random.choice(["Noise", "Pitch Env", "Punch", "Sub Osc"])
```

Available playback effects and their confirmed parameter ranges (verified against real Move/Note presets):

| Effect | Parameter | Min | Max |
|---|---|---|---|
| Stretch | Factor | 1.0 | 20.0 |
| Stretch | GrainSize | 0.005 | 0.3 |
| FM | Amount | 0.0 | 1.0 |
| FM | Frequency | 10 Hz | 4500 Hz |
| Pitch Env | Amount | -1.0 | +1.0 |
| Pitch Env | Decay | 0.005 s | 2.0 s |
| Punch | Amount | 0.0 | 1.0 |
| Punch | Time | 0.06 s | 1.0 s |
| Ring Mod | Amount | 0.0 | 1.0 |
| Ring Mod | Frequency | 1 Hz | 5000 Hz |
| Sub Osc | Amount | 0.0 | 1.0 |
| Sub Osc | Frequency | 30 Hz | 120 Hz |
| Noise | Amount | 0.0 | 1.0 |
| Noise | Frequency | 180 Hz | 15000 Hz |
| 8-Bit | ResamplingRate | 1000 | 30000 |
| 8-Bit | FilterDecay | 0.011 | 5.0 |
| Loop | Length | 0.01 | 0.5 |
| Loop | Offset | 0.0 | 1.0 |

### Rack Effects Parameters

All rack effects have a `"random"` lambda inside `RACK_EFFECTS` that controls which parameters get randomized and over what range. You can tighten or widen any range. For example to make the reverb always long and lush:

```python
"reverb": {
    ...
    "random": lambda: {
        "DecayTime": round(random.uniform(2000, 2523), 0),
        "RoomSize":  round(random.uniform(30, 52), 2),
        ...
    },
},
```

---

## How Sample Scanning Works

The script recursively scans `SAMPLES_FOLDER` for `.wav`, `.aif`, `.aiff`, `.flac`, and `.mp3` files. Each file is categorized by matching keywords in its filename against `CATEGORIES`. The console prints a summary of how many samples were found per category, plus how many loops and oversized files were skipped.

WAV files are stripped of all metadata chunks (ID3, LIST, INFO, bext, etc.) before being packed into the bundle, leaving only the `fmt` and `data` chunks. This keeps bundle sizes lean and avoids import issues on Move.

---

## Notes

- All effect parameters have been verified against real `.ablpresetbundle` files exported from Ableton Live and tested on Move/Note
- The `dynamics` insert is an `audioEffectRack` (not a native effect kind) — this matches how Ableton itself exports it from Live
- Pan randomization uses the drumCell internal `Pan` parameter (range -1.0 to +1.0), which is the value Move/Note actually reads on preset load
