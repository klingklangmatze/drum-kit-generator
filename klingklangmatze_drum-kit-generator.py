"""
╔══════════════════════════════════════════════════════════════╗
║           DRUM KIT GENERATOR for Note and Move               ║
╠══════════════════════════════════════════════════════════════╣
║  1. Edit the CONFIG block below                              ║
║  2. Run                                                      ║
╚══════════════════════════════════════════════════════════════╝
"""

# ════════════════════════════════════════════════════════════════
#  CONFIG  –  edit here, then hit Run
# ════════════════════════════════════════════════════════════════

SAMPLES_FOLDER  = "/Users/yourname/Samples"   # folder with your sample library
OUTPUT_FOLDER   = "/Users/yourname/Kits"       # where the .ablpresetbundle files go

KIT_COUNT       = 10                           # how many kits to generate
KIT_NAME        = "ae-kit"                     # base name  →  ae-kit-01, ae-kit-02 …
NAME_START      = 1                            # first kit number (e.g. 1 → ae-kit-01)

RETURN_EFFECT         = "reverb"   # one of: reverb, delay, autoFilter, chorus,
                                   #   phaser, redux2, erosion, autoShift, autoPan,
                                   #   channelEq, saturator, dynamics
                                   #   — or use RANDOM_RETURN_EFFECT = True
RANDOM_RETURN_EFFECT  = True      # True = pick a random return effect for each kit
RANDOM_RETURN_SETTINGS= True      # True = also randomize that effect's parameters
INSERT_EFFECT         = "saturator" # one of: saturator, dynamics, reverb, delay,
                                    #   autoFilter, chorus, phaser, redux2, erosion,
                                    #   autoShift, autoPan — or "random"

RANDOMIZE_FX      = True    # randomize playback effects / filter / transpose
RANDOMIZE_FX_PADS = [8, 9, 10, 11, 12, 13, 14, 15]  # 0-based (pad 9–16)
TRANSPOSE_RANGE   = (-24, 12) # semitone range, full range is (-48, 48)

CHOKE_GROUPS_HH   = True   # closedHH chokes openHH (group 1); crash/cymbal group 2

# ── Loop filter ───────────────────────────────────────────────────
SKIP_LOOPS        = True   # skip files with [120], [130bpm], "loop" etc. in name

# ── Pan randomizing ───────────────────────────────────────────────
# drumCell Pan range: -1.0 (full left) to +1.0 (full right), 0.0 = center
# kick/tom/bass: always center | snare/clap/rim: near center
# hats/percs/cymbals: wider spread | fx/vox: widest | synths/pads: medium
RANDOMIZE_PAN      = True
RANDOMIZE_PAN_PADS = [6, 8, 9, 10, 11, 12, 13, 14, 15]  # "all" or list e.g. [2, 3, 6, 7, 8, 9, 10, 11]

MAX_SAMPLE_SIZE = "2mb"   # max file size per sample: e.g. "500kb", "1.5mb", "2mb", None = no limit
SEED            = None    # set an int (e.g. 42) for reproducible results, None = random
VERBOSE         = True    # print pad assignments for each kit

# ════════════════════════════════════════════════════════════════
#  END OF CONFIG  –  no need to edit below
# ════════════════════════════════════════════════════════════════

import json
import zipfile
import urllib.parse
import random
import sys
import wave
import struct
import io
from pathlib import Path
from collections import defaultdict


# ── Sample categories ───────────────────────────────────────────
CATEGORIES = {
    "kick":     ["kick", "kck", "bd", "bassdrum", "bass_drum"],
    "snare":    ["snare", "snr", "sd"],
    "rim":      ["rim", "rimshot", "sidestick"],
    "clap":     ["clap", "clp", "cp", "handclap"],
    "closedHH": ["closedhh", "closed_hh", "chh", "hihat_c", "hh_c",
                 "closedhat", "hh_closed", "hat_c"],
    "openHH":   ["openhh", "open_hh", "ohh", "hihat_o", "hh_o",
                 "openhat", "hh_open", "hat_o"],
    "hat":      ["hat", "hihat", "hi_hat", "hh"],
    "tom":      ["tom", "tm", "floor", "rack"],
    "conga":    ["conga", "cng"],
    "perc":     ["perc", "percussion", "shaker", "tamb", "tambourine",
                 "cowbell", "bongo", "agogo", "wood", "block",
                 "triangle", "cabasa", "maracas", "guiro", "claves"],
    "crash":    ["crash", "crsh"],
    "ride":     ["ride"],
    "cymbal":   ["cymbal", "cym"],
    "fx":       ["fx", "sfx", "effect", "noise", "glitch", "foley",
                 "impact", "hit", "riser", "sweep", "transition"],
    "vox":      ["vox", "vocal", "voice", "chant", "choir"],
    "bass":     ["bass", "sub"],
    "synth":    ["synth", "synthesizer", "analog"],
    "stab":     ["stab", "chord_hit"],
    "chord":    ["chord", "chords"],
    "lead":     ["lead", "melody", "melodic"],
    "pad":      ["pad", "atmosphere", "ambient", "texture", "drone",
                 "strings", "keys", "piano", "organ", "brass"],
}

# ── Pad layout: pad index (0-based) → preferred categories ──────
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

# ── Rack-level effects ────────────────────────────────────────────
# ALL parameters confirmed from real exported Move/Note presets

RACK_EFFECTS = {

    # ── reverb ── confirmed (completely different params than assumed!)
    "reverb": {
        "kind": "reverb",
        "parameters": {
            "Enabled": True,
            "RoomType": "SuperEco",
            "DecayTime": 2000.0,
            "PreDelay": 10.0,
            "RoomSize": 20.0,
            "MixDirect": 0.8,
            "MixReflect": 1.0,
            "MixDiffuse": 1.0,
            "DiffuseDelay": 0.8,
            "ShelfLowOn": True,
            "ShelfLoFreq": 200.0,
            "ShelfLoGain": 0.35,
            "ShelfHighOn": True,
            "ShelfHiFreq": 5000.0,
            "ShelfHiGain": 0.5,
            "BandLowOn": True,
            "BandHighOn": False,
            "BandFreq": 5000.0,
            "BandWidth": 2.0,
            "ChorusOn": True,
            "SpinOn": False,
            "FlatOn": True,
            "CutOn": True,
            "FreezeOn": False,
            "StereoSeparation": 100.0,
            "SizeModDepth": 0.5,
            "SizeModFreq": 0.5,
            "SizeSmoothing": "Fast",
            "AllPassGain": 0.6,
            "AllPassSize": 0.4,
            "EarlyReflectModDepth": 20.0,
            "EarlyReflectModFreq": 0.35,
        },
        "random": lambda: {
            "DecayTime":     round(random.uniform(1200, 2523), 0),
            "PreDelay":      round(random.uniform(5, 17), 2),
            "RoomSize":      round(random.uniform(7, 52), 2),
            "ShelfLoGain":   round(random.uniform(0.2, 0.47), 3),
            "ShelfHiGain":   round(random.uniform(0.2, 0.7), 3),
            "ShelfHiFreq":   round(random.uniform(4500, 7556), 0),
            "MixDirect":     round(random.uniform(0.55, 1.0), 3),
            "ChorusOn":      random.choice([True, False]),
            "SpinOn":        random.choice([True, False]),
            "SizeModDepth":  round(random.uniform(0.02, 4.0), 3),
        },
    },

    # ── delay ── confirmed
    "delay": {
        "kind": "delay",
        "parameters": {
            "Enabled": True,
            "DryWet": 0.5,
            "DryWetMode": "Equal-loudness",
            "Feedback": 0.58,
            "DelayLine_CompatibilityMode": "D",
            "DelayLine_Link": True,
            "DelayLine_PingPong": False,
            "DelayLine_SyncL": True,
            "DelayLine_SyncR": True,
            "DelayLine_SyncedSixteenthL": "2",
            "DelayLine_SyncedSixteenthR": "2",
            "DelayLine_TimeL": 0.001,
            "DelayLine_TimeR": 0.001,
            "DelayLine_SimpleDelayTimeL": 100.0,
            "DelayLine_SimpleDelayTimeR": 100.0,
            "DelayLine_PingPongDelayTimeL": 1.0,
            "DelayLine_PingPongDelayTimeR": 1.0,
            "DelayLine_OffsetL": 0.0,
            "DelayLine_OffsetR": 0.0,
            "DelayLine_SmoothingMode": "Repitch",
            "Filter_On": True,
            "Filter_Frequency": 1000.0,
            "Filter_Bandwidth": 4.75,
            "Modulation_AmountFilter": 0.0,
            "Modulation_AmountTime": 0.0,
            "Modulation_Frequency": 2.0,
            "Modulation_Waveform": "Triangle",
            "Modulation_Morph": 0.0,
            "Modulation_TimeMode": "Rate",
            "Modulation_SyncedRate": 4,
            "Modulation_Sixteenth": 16,
            "Modulation_Time": 1.0,
            "EcoProcessing": True,
            "Freeze": False,
        },
        "random": lambda: {
            "DryWet":                     round(random.uniform(0.25, 0.85), 3),
            "Feedback":                   round(random.uniform(0.1, 0.90), 3),
            "DelayLine_PingPong":         random.choice([True, False]),
            "DelayLine_SmoothingMode":    random.choice(["Repitch", "Fade", "Jump"]),
            "DelayLine_SyncedSixteenthL": random.choice(["1", "2", "3"]),
            "DelayLine_SyncedSixteenthR": random.choice(["2", "4"]),
            "Filter_Frequency":           round(random.uniform(200, 8000), 0),
            "Filter_Bandwidth":           round(random.uniform(1.73, 4.75), 2),
            "Modulation_AmountFilter":    round(random.uniform(0.0, 1.0), 3),
            "Modulation_AmountTime":      round(random.uniform(0.0, 0.094), 3),
            "Modulation_Frequency":       round(random.uniform(1.0, 5.0), 2),
            "Modulation_Waveform":        random.choice(["Triangle", "Sine", "S & H"]),
            "Modulation_Morph":           round(random.uniform(0.0, 0.36), 3),
            "DryWetMode":                 random.choice(["Equal-loudness", "Linear"]),
        },
    },

    # ── autoFilter ── confirmed (many more params than we had!)
    "autoFilter": {
        "kind": "autoFilter",
        "parameters": {
            "Enabled": True,
            "DryWet": 0.8,
            "Output": 0.5,
            "Filter_Type": "Low-pass",
            "Filter_Frequency": 2000.0,
            "Filter_Resonance": 0.3,
            "Filter_Drive": 0.0,
            "Filter_Slope": "24dB",
            "Filter_Circuit": "SVF",
            "Filter_Morph": 0.0,
            "Filter_MorphSlope": "24dB",
            "Filter_DjControl": 0.0,
            "Filter_VowelFormant": 0.0,
            "Filter_VowelPitch": 0,
            "Lfo_Amount": 0.2,
            "Lfo_Frequency": 1.0,
            "Lfo_Waveform": "Sine",
            "Lfo_TimeMode": "Rate",
            "Lfo_SyncedRate": 4,
            "Lfo_Sixteenth": 16,
            "Lfo_Time": 1.0,
            "Lfo_Phase": 0.0,
            "Lfo_PhaseOffset": 0.0,
            "Lfo_Morph": 0.0,
            "Lfo_Spin": 0.0,
            "Lfo_StereoMode": "Phase",
            "Lfo_QuantizationMode": "None",
            "Lfo_Steps": 8,
            "Lfo_Smoothing": 0.0,
            "Lfo_SahRate": -4,
            "Envelope_Amount": 0.0,
            "Envelope_Attack": 0.001,
            "Envelope_Release": 0.25,
            "Envelope_HoldOn": True,
            "Envelope_SahOn": False,
            "Envelope_SahRate": -4,
            "SideChainEq_Freq": 200.0,
            "SideChainEq_Gain": 0.0,
            "SideChainEq_Mode": "High pass",
            "SideChainEq_On": False,
            "SideChainEq_Q": 0.707,
            "SideChainListen": False,
            "SideChainMono": True,
            "SoftClipOn": False,
            "HiQuality": False,
            "InternalSideChainGain": 1.0,
        },
        "random": lambda: {
            "DryWet":           round(random.uniform(0.5, 1.0), 3),
            "Output":           round(random.uniform(0.35, 1.0), 3),
            "Filter_Type":      random.choice(["Low-pass", "High-pass", "Band-pass", "Notch", "Morph", "DJ", "Comb", "Resampling", "Notch+LP", "Vowel"]),
            "Filter_Frequency": round(random.uniform(80, 18000), 2),
            "Filter_Resonance": round(random.uniform(0.0, 0.95), 3),
            "Filter_Drive":     round(random.uniform(0.0, 0.25), 3),
            "Filter_Circuit":   random.choice(["SVF", "DFM", "MS2", "PRD"]),
            "Lfo_Amount":       round(random.uniform(0.0, 0.38), 3),
            "Lfo_Frequency":    round(random.uniform(0.1, 15.0), 3),
            "Lfo_Waveform":     random.choice(["Sine", "Triangle", "Ramp Up", "Ramp Down", "Square", "Wander", "S&H"]),
            "Lfo_TimeMode":     random.choice(["Rate", "Synced", "Sixteenth"]),
            "Envelope_Amount":  round(random.uniform(-0.6, 0.02), 3),
            "Envelope_Attack":  round(random.uniform(0.0, 0.02), 4),
            "Envelope_Release": round(random.uniform(0.1, 2.0), 3),
            "SoftClipOn":       random.choice([True, False]),
        },
    },

    # ── chorus ── confirmed (many more params!)
    "chorus": {
        "kind": "chorus",
        "parameters": {
            "Enabled": True,
            "DryWet": 0.7,
            "Amount": 0.5,
            "Rate": 0.9,
            "Feedback": 0.1,
            "Width": 1.0,
            "Mode": "Classic",
            "Warmth": 0.0,
            "Shaping": 0.0,
            "ChorusDelayTime": "20 ms",
            "ChorusTapCount": "2",
            "HighpassEnabled": True,
            "HighpassFrequency": 20.0,
            "InvertFeedback": False,
            "OutputGain": 1.0,
            "VibratoOffset": 0.0,
        },
        "random": lambda: {
            "DryWet":           round(random.uniform(0.4, 1.0), 3),
            "Amount":           round(random.uniform(0.1, 1.0), 3),
            "Rate":             round(random.uniform(0.05, 8.0), 3),
            "Feedback":         round(random.uniform(0.0, 0.9), 3),
            "Width":            round(random.uniform(0.5, 1.0), 3),
            "Mode":             random.choice(["Classic", "Ensemble", "Vibrato"]),
            "Warmth":           round(random.uniform(0.0, 0.6), 3),
            "ChorusDelayTime":  random.choice(["20 ms", "35 ms", "Auto"]),
            "HighpassFrequency": round(random.uniform(20.0, 200.0), 2),
            "InvertFeedback":   random.choice([True, False]),
        },
    },

    # ── phaser ── confirmed (many more params!)
    "phaser": {
        "kind": "phaser",
        "parameters": {
            "Enabled": True,
            "DryWet": 0.8,
            "Mode": "Phaser",
            "CenterFrequency": 400.0,
            "Feedback": 0.3,
            "Notches": 4,
            "Spread": 0.5,
            "ModulationBlend": 0.0,
            "OutputGain": 1.0,
            "SafeBassFrequency": 100.0,
            "Warmth": 0.0,
            "InvertWet": False,
            "FlangerDelayTime": 0.0025,
            "DoublerDelayTime": 0.08,
            "Modulation_Amount": 0.75,
            "Modulation_Frequency": 0.2,
            "Modulation_Frequency2": 0.2,
            "Modulation_Waveform": "Triangle",
            "Modulation_Sync": False,
            "Modulation_Sync2": True,
            "Modulation_SyncedRate": 6,
            "Modulation_SyncedRate2": 4,
            "Modulation_DutyCycle": 0.0,
            "Modulation_LfoBlend": 0.0,
            "Modulation_PhaseOffset": 0.0,
            "Modulation_Spin": 0.0,
            "Modulation_SpinEnabled": False,
            "Modulation_EnvelopeEnabled": True,
            "Modulation_EnvelopeAmount": 0.0,
            "Modulation_EnvelopeAttack": 0.006,
            "Modulation_EnvelopeRelease": 0.2,
        },
        "random": lambda: {
            "DryWet":               round(random.uniform(0.67, 1.0), 3),
            "Mode":                 random.choice(["Phaser", "Flanger", "Doubler"]),
            "CenterFrequency":      round(random.uniform(77, 1544), 2),
            "Feedback":             round(random.uniform(0.0, 0.67), 3),
            "Notches":              random.choice([2, 4, 8, 16]),
            "Spread":               round(random.uniform(0.35, 1.0), 3),
            "ModulationBlend":      round(random.uniform(0.0, 0.95), 3),
            "Warmth":               round(random.uniform(0.0, 0.6), 3),
            "Modulation_Amount":    round(random.uniform(0.62, 1.0), 3),
            "Modulation_Frequency": round(random.uniform(0.11, 0.37), 4),
            "Modulation_Sync":      random.choice([True, False]),
            "Modulation_SyncedRate": random.choice([4, 5, 6, 8, 10, 12, 14]),
        },
    },

    # ── redux2 ── confirmed
    "redux2": {
        "kind": "redux2",
        "parameters": {
            "Enabled": True,
            "DryWet": 1.0,
            "BitDepth": 16,
            "SampleRate": 40000.0,
            "Jitter": 0.0,
            "EcoProcessing": True,
            "EnablePostFilter": False,
            "EnablePreFilter": False,
            "QuantizerShape": 0.0,
            "QuantizerDcShift": False,
            "PostFilterValue": 0.0,
        },
        "random": lambda: {
            "DryWet":     round(random.uniform(0.3, 1.0), 3),
            "BitDepth":   random.randint(4, 16),
            "SampleRate": round(random.uniform(4000, 40000), 0),
            "Jitter":     round(random.uniform(0.0, 0.5), 3),
        },
    },

    # ── erosion ── confirmed
    "erosion": {
        "kind": "erosion",
        "parameters": {
            "Enabled": True,
            "Amount": 0.3,
            "Frequency": 500.0,
            "FilterWidth": 1.0,
            "NoiseBlend": 0.5,
            "StereoWidth": 0.25,
        },
        "random": lambda: {
            "Amount":      round(random.uniform(0.2, 0.86), 3),
            "Frequency":   round(random.uniform(29, 3520), 2),
            "FilterWidth": round(random.uniform(0.1, 2.5), 3),
            "NoiseBlend":  round(random.uniform(0.0, 1.0), 3),
            "StereoWidth": round(random.uniform(0.25, 1.0), 3),
        },
    },

    # ── autoPan ── confirmed (many more params!)
    "autoPan": {
        "kind": "autoPan",
        "parameters": {
            "Enabled": True,
            "Mode": "Panning",
            "Modulation_Amount": 0.5,
            "Modulation_Frequency": 1.0,
            "Modulation_Phase": 180.0,
            "Modulation_Waveform": "Sine",
            "Modulation_TimeMode": "Rate",
            "Modulation_SyncedRate": 6,
            "Modulation_Sixteenth": 16,
            "Modulation_Time": 1.0,
            "Modulation_Spin": 0.0,
            "Modulation_Invert": False,
            "Modulation_PhaseOffset": 0.0,
            "Modulation_StereoMode": "Phase",
            "AttackTime": 0.0,
            "DynamicFrequencyModulation": 0.0,
            "HarmonicMode": False,
            "PanningWaveformShape": 0.0,
            "TremoloWaveformShape": 0.0,
            "VintageMode": False,
        },
        "random": lambda: {
            "Mode":                 random.choice(["Panning", "Tremolo"]),
            "Modulation_Amount":    round(random.uniform(0.5, 1.0), 3),
            "Modulation_Frequency": round(random.uniform(1.0, 4.0), 3),
            "Modulation_Phase":     random.choice([22.5, 45.0, 90.0, 180.0]),
            "Modulation_Waveform":  random.choice(["Sine", "Triangle", "Saw Down", "Square", "Random", "Wander", "S&H"]),
            "Modulation_TimeMode":  random.choice(["Rate", "Synced"]),
            "Modulation_SyncedRate": random.choice([6, 9, 12, 17]),
            "Modulation_Spin":      round(random.uniform(0.0, 0.156), 3),
            "VintageMode":          random.choice([True, False]),
            "DynamicFrequencyModulation": round(random.uniform(0.0, 0.44), 3),
        },
    },

    # ── autoShift ── confirmed (completely different params than assumed!)
    "autoShift": {
        "kind": "autoShift",
        "parameters": {
            "Enabled": True,
            "Global_DryWet": 1.0,
            "Global_InputGain": 0.0,
            "Global_LiveMode": True,
            "Global_PitchRange": "Mid",
            "Global_UseScale": False,
            "PitchShift_ShiftSemitones": 0,
            "PitchShift_Detune": 0.0,
            "PitchShift_FormantFollow": 1.0,
            "PitchShift_FormantShift": 0.0,
            "PitchShift_ShiftScaleDegrees": 0,
            "Quantizer_Active": True,
            "Quantizer_Amount": 0.0,
            "Quantizer_InternalScale": "Custom",
            "Quantizer_RootNote": "C",
            "Quantizer_Smooth": True,
            "Quantizer_SmoothingTime": 0.05,
            "Lfo_Enabled": False,
            "Lfo_RateHz": 0.5,
            "Lfo_SyncOn": False,
            "Lfo_SyncedRate": 6,
            "Lfo_Waveform": "Sine",
            "Lfo_OnsetRetrigger": True,
            "Lfo_Attack": 0.0,
            "Lfo_Delay": 0.0,
            "Modulation_LfoToPitchModAmount": 0.0,
            "Modulation_LfoToVolumeModAmount": 0.0,
            "Modulation_LfoToPanModAmount": 0.0,
            "Modulation_LfoToFormantModAmount": 0.0,
            "Vibrato_Amount": 0.0,
            "Vibrato_Attack": 0.0,
            "Vibrato_RateHz": 6.0,
            "Vibrato_Humanization": False,
            "MidiInput_Enabled": False,
            "MidiInput_AttackTime": 0.02,
            "MidiInput_ReleaseTime": 0.02,
            "MidiInput_Glide": 0.0,
            "MidiInput_Latch": "Gate",
            "MidiInput_MonoPoly": "Mono",
            "MidiInput_NumVoices": "4",
            "MidiInput_PitchBendRange": 6,
        },
        "random": lambda: {
            "Global_DryWet":              round(random.uniform(0.9, 1.0), 3),
            "PitchShift_ShiftSemitones":  random.choice([-12, -7, -5, -3, -2, 0, 2, 3, 5, 7, 12]),
            "PitchShift_FormantShift":    round(random.uniform(-1.0, 0.0), 3),
            "Quantizer_Amount":           round(random.uniform(0.0, 0.5), 3),
            "Lfo_Enabled":                random.choice([True, False]),
            "Lfo_RateHz":                 round(random.uniform(0.42, 0.5), 4),
            "Lfo_SyncOn":                 random.choice([True, False]),
            "Lfo_SyncedRate":             random.choice([4, 6, 8, 9, 12, 16]),
            "Modulation_LfoToPitchModAmount": round(random.uniform(0.0, 12.0), 2),
        },
    },

    # ── channelEq ── confirmed
    "channelEq": {
        "kind": "channelEq",
        "parameters": {
            "Enabled": True,
            "Gain": 1.0,
            "LowShelfGain": 1.0,
            "MidGain": 1.0,
            "HighShelfGain": 1.0,
            "MidFrequency": 1500.0,
            "HighpassOn": False,
        },
        "random": lambda: {
            "Gain":          round(random.uniform(0.43, 1.13), 3),
            "LowShelfGain":  round(random.uniform(0.18, 1.41), 3),
            "MidGain":       round(random.uniform(0.25, 1.67), 3),
            "HighShelfGain": round(random.uniform(0.27, 4.16), 3),
            "MidFrequency":  round(random.uniform(120, 2107), 2),
            "HighpassOn":    random.choice([True, False]),
        },
    },

    # ── saturator ── confirmed (many more params!)
    "saturator": {
        "kind": "saturator",
        "parameters": {
            "Enabled": True,
            "DryWet": 1.0,
            "Type": "Analog Clip",
            "BaseDrive": 0.0,
            "PreDrive": 0.0,
            "PostDrive": 0.0,
            "PostClip": "off",
            "ColorOn": True,
            "ColorDepth": 0.0,
            "ColorFrequency": 999.9998779296876,
            "ColorWidth": 0.3,
            "BassShaperThreshold": -50.0,
            "Oversampling": False,
            "PreDcFilter": False,
            "WsCurve": 0.05,
            "WsDamp": 0.0,
            "WsDepth": 0.0,
            "WsDrive": 1.0,
            "WsLin": 0.5,
            "WsPeriod": 0.0,
        },
        "random": lambda: {
            "Type":       random.choice(["Analog Clip", "Soft Sine", "Medium Curve", "Hard Curve", "Sinoid Fold", "Digital Clip", "Waveshaper", "Bass Shaper"]),
            "BaseDrive":  round(random.uniform(0.0, 5.4), 3),
            "PreDrive":   round(random.uniform(0.0, 8.0), 3),
            "PostDrive":  round(random.uniform(-5.14, 0.0), 3),
            "PostClip":   random.choice(["off", "on"]),
            "ColorDepth": round(random.uniform(0.0, 13.4), 3),
            "ColorFrequency": round(random.uniform(178, 1000), 2),
            "ColorWidth": round(random.uniform(0.25, 0.85), 3),
        },
    },

    # ── dynamics ── confirmed audioEffectRack (channelEq + compressor)
    "dynamics": {
        "kind": "_audioEffectRack",
        "parameters": {},
        "random": lambda: {
            "low_gain":  round(random.uniform(0.5, 2.0), 3),
            "mid_gain":  round(random.uniform(0.5, 2.0), 3),
            "high_gain": round(random.uniform(0.5, 2.0), 3),
            "threshold": round(random.uniform(0.05, 1.0), 3),
            "release":   round(random.uniform(10.0, 200.0), 1),
            "output":    round(random.uniform(0.0, 20.0), 1),
        },
    },
}

ALL_RETURN_EFFECTS = list(RACK_EFFECTS.keys())




def make_dynamics_rack(rnd: bool = False) -> dict:
    """Builds the confirmed audioEffectRack (channelEq + compressor) for Dynamics insert."""
    cfg = RACK_EFFECTS["dynamics"]["random"]() if rnd else {}

    low_gain  = cfg.get("low_gain",  1.0)
    mid_gain  = cfg.get("mid_gain",  1.0)
    high_gain = cfg.get("high_gain", 1.0)
    threshold = cfg.get("threshold", 1.0)
    release   = cfg.get("release",   30.0)
    output    = cfg.get("output",    0.0)

    return {
        "presetUri": None,
        "kind":      "audioEffectRack",
        "name":      "Dynamics",
        "lockId":    1001,
        "lockSeal":  -100211998,
        "parameters": {
            "Enabled": True,
            "Macro0": {"value": low_gain * 64.5,  "customName": "Low Gain"},
            "Macro1": {"value": mid_gain * 64.5,  "customName": "Mid Gain"},
            "Macro2": {"value": high_gain * 64.5, "customName": "High Gain"},
            "Macro3": {"value": 34.26,            "customName": "Comp Hi Pass"},
            "Macro4": {"value": release,           "customName": "Release"},
            "Macro5": {"value": threshold * 46.0, "customName": "Threshold"},
            "Macro6": {"value": output,            "customName": "Output"},
            "Macro7": {"value": 3.0,               "customName": "Comp Dry/Wet"},
        },
        "chains": [{
            "name": "", "color": 8,
            "devices": [
                {
                    "presetUri": None, "kind": "channelEq", "name": "",
                    "parameters": {
                        "Enabled": True,
                        "Gain": 1.0,
                        "HighpassOn": False,
                        "MidFrequency": 580.0,
                        "LowShelfGain": {"value": 1.0, "macroMapping": {"macroIndex": 0, "rangeMin": 0.18, "rangeMax": 5.6}},
                        "MidGain":      {"value": 1.0, "macroMapping": {"macroIndex": 1, "rangeMin": 0.25, "rangeMax": 4.0}},
                        "HighShelfGain":{"value": 1.0, "macroMapping": {"macroIndex": 2, "rangeMin": 0.18, "rangeMax": 5.6}},
                    },
                    "deviceData": {},
                },
                {
                    "presetUri": None, "kind": "compressor", "name": "",
                    "parameters": {
                        "Attack":                  1.0,
                        "AutoReleaseControlOnOff": False,
                        "ExpansionRatio":          1.15,
                        "GainCompensation":        False,
                        "Knee":                    0.1,
                        "LogEnvelope":             True,
                        "Model":                   "RMS",
                        "Ratio":                   2.0,
                        "SideChainEq_Gain":        0.0,
                        "SideChainEq_Mode":        "High pass",
                        "SideChainEq_On":          True,
                        "SideChainEq_Q":           0.41,
                        "DryWet":      {"value": 1.0,  "macroMapping": {"macroIndex": 7, "rangeMin": 0.0,   "rangeMax": 1.0}},
                        "Enabled":     {"value": True, "macroMapping": {"macroIndex": 7, "rangeMin": 1.0,   "rangeMax": 127.0}},
                        "Gain":        {"value": 0.0,  "macroMapping": {"macroIndex": 6, "rangeMin": 0.0,   "rangeMax": 36.0}},
                        "Release":     {"value": 30.0, "macroMapping": {"macroIndex": 4, "rangeMin": 1.0,   "rangeMax": 1000.0}},
                        "SideChainEq_Freq": {"value": 80.0, "macroMapping": {"macroIndex": 3, "rangeMin": 30.0, "rangeMax": 15000.0}},
                        "Threshold":   {"value": 1.0,  "macroMapping": {"macroIndex": 5, "rangeMin": 0.003, "rangeMax": 1.0}},
                    },
                    "deviceData": {},
                },
            ],
            "mixer": {"pan": 0.0, "solo-cue": False, "speakerOn": True, "volume": 0.0, "sends": []},
        }],
    }


def make_rack_effect(name: str, randomize_settings: bool = False) -> dict:
    if name == "dynamics":
        return make_dynamics_rack(rnd=randomize_settings)
    cfg = RACK_EFFECTS[name]
    params = dict(cfg["parameters"])
    if randomize_settings and "random" in cfg:
        params.update(cfg["random"]())
    return {"presetUri": None, "kind": cfg["kind"], "name": "", "parameters": params}

FILTER_TYPES = ["Lowpass", "Highpass", "Bandpass"]

DEFAULT_DRUM_CELL_PARAMS = {
    "Effect_EightBitFilterDecay": 5.0,    "Effect_EightBitResamplingRate": 14080.0,
    "Effect_FmAmount": 0.0,               "Effect_FmFrequency": 1000.0,
    "Effect_LoopLength": 0.3,             "Effect_LoopOffset": 0.02,
    "Effect_NoiseAmount": 0.0,            "Effect_NoiseFrequency": 10000.0,
    "Effect_On": True,                    "Effect_PitchEnvelopeAmount": 0.0,
    "Effect_PitchEnvelopeDecay": 0.3,     "Effect_PunchAmount": 0.0,
    "Effect_PunchTime": 0.12,             "Effect_RingModAmount": 0.0,
    "Effect_RingModFrequency": 1000.0,    "Effect_StretchFactor": 1.0,
    "Effect_StretchGrainSize": 0.1,       "Effect_SubOscAmount": 0.0,
    "Effect_SubOscFrequency": 60.0,       "Effect_Type": "Stretch",
    "Enabled": True, "NotePitchBend": True, "Pan": 0.0, "Voice_Detune": 0.0,
    "Voice_Envelope_Attack": 0.0001,      "Voice_Envelope_Decay": 1.0,
    "Voice_Envelope_Hold": 9.0,           "Voice_Envelope_Mode": "A-H-D",
    "Voice_Filter_Frequency": 22000.0,    "Voice_Filter_On": True,
    "Voice_Filter_PeakGain": 1.0,         "Voice_Filter_Resonance": 0.0,
    "Voice_Filter_Type": "Lowpass",       "Voice_Gain": 1.0,
    "Voice_ModulationAmount": 0.0,        "Voice_ModulationSource": "Velocity",
    "Voice_ModulationTarget": "Filter",   "Voice_PlaybackLength": 1.0,
    "Voice_PlaybackStart": 0.0,           "Voice_Transpose": 0,
    "Voice_VelocityToVolume": 0.35,       "Volume": -12.0,
    "Voice_PitchToEnvelopeModulation": False,
}


# ── Metadata stripping ───────────────────────────────────────────

def strip_wav_metadata(src: Path) -> bytes:
    """
    Returns clean WAV bytes with only fmt + data chunks – no ID3, LIST,
    INFO, bext, iXML, PEAK, JUNK or any other metadata chunks.
    Falls back to raw file bytes if the file is not a valid WAV.
    """
    try:
        with wave.open(str(src), "rb") as w:
            n_channels    = w.getnchannels()
            sampwidth     = w.getsampwidth()
            framerate     = w.getframerate()
            n_frames      = w.getnframes()
            audio_data    = w.readframes(n_frames)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(n_channels)
            w.setsampwidth(sampwidth)
            w.setframerate(framerate)
            w.writeframes(audio_data)

        return buf.getvalue()

    except Exception:
        # Not a standard WAV (e.g. AIFF, FLAC, MP3) – pass through as-is
        return src.read_bytes()


# ── Helpers ──────────────────────────────────────────────────────

import re

def clean_sample_name(path: Path) -> str:
    """
    Returns a human-readable display name for a sample, stripping
    leading numbering patterns like:
      01-kick.wav  →  kick
      03_Snare_808 →  Snare 808
      007 hat.wav  →  hat
    Also replaces underscores/hyphens with spaces and title-cases.
    """
    name = path.stem
    # strip leading number + separator (e.g. "01-", "003_", "07 ")
    name = re.sub(r"^\d+[\s\-_]+", "", name)
    # replace remaining underscores/hyphens with spaces
    name = re.sub(r"[\-_]+", " ", name)
    return name.strip()

def detect_category(filename: str) -> str | None:
    name = filename.lower().replace("-", "_").replace(" ", "_")
    # longer keywords checked first to avoid false matches
    for category, keywords in sorted(CATEGORIES.items(), key=lambda x: -max(len(k) for k in x[1])):
        for kw in keywords:
            if kw in name:
                return category
    return None


def parse_size(size_str: str) -> int | None:
    """
    Parses a human-readable size string into bytes.
    Examples: "500kb" → 512000, "1.5mb" → 1572864, "2mb" → 2097152
    Returns None if size_str is None or empty.
    """
    if not size_str:
        return None
    s = size_str.strip().lower().replace(" ", "")
    units = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3}
    for suffix, multiplier in sorted(units.items(), key=lambda x: -len(x[0])):
        if s.endswith(suffix):
            number = float(s[:-len(suffix)])
            return int(number * multiplier)
    return int(s)  # assume raw bytes if no unit


def is_loop(filename: str) -> bool:
    """Returns True if filename looks like a loop – has [bpm] pattern or 'loop' in name."""
    import re
    name = filename.lower()
    if "loop" in name:
        return True
    if re.search(r'\[\d+', name):   # matches [120], [130bpm], [120 bpm] etc.
        return True
    return False


def scan_samples(folder: Path) -> dict:
    categorized = defaultdict(list)
    skipped = []
    too_large = []
    loops_skipped = []
    extensions = {".wav", ".aif", ".aiff", ".flac", ".mp3"}
    max_bytes = parse_size(MAX_SAMPLE_SIZE)

    for f in sorted(folder.rglob("*")):
        if f.suffix.lower() in extensions:
            if SKIP_LOOPS and is_loop(f.stem):
                loops_skipped.append(f.name)
                continue
            if max_bytes is not None and f.stat().st_size > max_bytes:
                too_large.append(f.name)
                continue
            cat = detect_category(f.stem)
            if cat:
                categorized[cat].append(f)
            else:
                skipped.append(f.name)

    total = sum(len(v) for v in categorized.values())
    size_info = f"  (max size: {MAX_SAMPLE_SIZE})" if MAX_SAMPLE_SIZE else ""
    print(f"✓ {total} samples found across {len(categorized)} categories{size_info}:")
    for cat, files in sorted(categorized.items()):
        print(f"  {cat:12s}  {len(files):4d}")
    if loops_skipped:
        print(f"  (skipped {len(loops_skipped)} loops)")
    if too_large:
        print(f"  (skipped {len(too_large)} files exceeding {MAX_SAMPLE_SIZE})")
    if skipped:
        print(f"  (skipped {len(skipped)} unrecognized files)")
    print()
    return dict(categorized)


def pick_sample(categorized: dict, categories: list) -> tuple:
    """
    Collects all available samples across every category in the list,
    then picks one at random – so pad 15 is equally likely to land on
    a pad, synth, lead, crash, ride, cymbal, fx or vox sample.
    """
    pool = []  # list of (sample_path, category)
    for cat in categories:
        candidates = list(categorized.get(cat, []))
        # hat → also include closedHH / openHH
        if cat == "hat" and not candidates:
            for sub in ("closedHH", "openHH"):
                candidates += categorized.get(sub, [])
        for s in candidates:
            pool.append((s, cat))

    if not pool:
        return None, None

    sample, cat = random.choice(pool)
    return sample, cat


def randomize_pad(params: dict, category: str) -> tuple:
    p = dict(params)

    # choose effect type by sample category
    if category in ("kick", "bass"):
        effect = random.choice(["Pitch Env", "Punch", "Sub Osc"])
    elif category in ("snare", "rim"):
        effect = random.choice(["Noise", "Pitch Env", "Punch"])
    elif category == "clap":
        effect = random.choice(["Noise", "8-Bit", "Stretch"])
    elif category in ("closedHH", "hat"):
        effect = random.choice(["8-Bit", "Stretch", "Ring Mod", "Loop"])
    elif category in ("openHH", "crash", "ride", "cymbal"):
        effect = random.choice(["Ring Mod", "FM", "Stretch", "Loop"])
    elif category in ("perc", "tom", "conga"):
        effect = random.choice(["Pitch Env", "Stretch", "Punch", "FM", "Loop"])
    elif category in ("fx", "vox"):
        effect = random.choice(["Stretch", "Ring Mod", "FM", "Loop"])
    else:
        effect = random.choice(["FM", "Pitch Env", "Stretch", "Ring Mod"])

    p["Effect_Type"] = effect
    p["Effect_On"]   = True

    if effect == "Pitch Env":
        # confirmed: Amount -1.0..+1.0, Decay 0.005..2.0
        p["Effect_PitchEnvelopeAmount"] = round(random.uniform(-1.0, 1.0), 3)
        p["Effect_PitchEnvelopeDecay"]  = round(random.uniform(0.005, 2.0), 3)
    elif effect == "Punch":
        # confirmed: Amount 0..1.0, Time 0.06..1.0
        p["Effect_PunchAmount"] = round(random.uniform(0.0, 1.0), 3)
        p["Effect_PunchTime"]   = round(random.uniform(0.06, 1.0), 3)
    elif effect == "Sub Osc":
        # confirmed: Amount 0..1.0, Frequency 30..120
        p["Effect_SubOscAmount"]    = round(random.uniform(0.0, 1.0), 3)
        p["Effect_SubOscFrequency"] = round(random.uniform(30.0, 120.0), 1)
    elif effect == "Noise":
        # confirmed: Amount 0..1.0, Frequency 180..15000
        p["Effect_NoiseAmount"]    = round(random.uniform(0.0, 1.0), 3)
        p["Effect_NoiseFrequency"] = round(random.uniform(180.0, 15000.0), 0)
    elif effect == "8-Bit":
        # confirmed: ResamplingRate 1000..30000, FilterDecay 0.011..5.0
        p["Effect_EightBitResamplingRate"] = round(random.uniform(1000.0, 30000.0), 0)
        p["Effect_EightBitFilterDecay"]    = round(random.uniform(0.011, 5.0), 3)
    elif effect == "Stretch":
        # confirmed: StretchFactor 1..20, GrainSize 0.005..0.3
        p["Effect_StretchFactor"]    = round(random.uniform(1.0, 20.0), 2)
        p["Effect_StretchGrainSize"] = round(random.uniform(0.005, 0.3), 3)
    elif effect == "FM":
        # confirmed: FmAmount 0..1.0, FmFrequency 10..4500
        p["Effect_FmAmount"]    = round(random.uniform(0.0, 1.0), 3)
        p["Effect_FmFrequency"] = round(random.uniform(10.0, 4500.0), 1)
    elif effect == "Ring Mod":
        # confirmed: RingModAmount 0..1.0, RingModFrequency 1..5000
        p["Effect_RingModAmount"]    = round(random.uniform(0.0, 1.0), 3)
        p["Effect_RingModFrequency"] = round(random.uniform(1.0, 5000.0), 1)
    elif effect == "Loop":
        # confirmed: LoopLength 0.01..0.5, LoopOffset 0..1.0
        p["Effect_LoopLength"] = round(random.uniform(0.01, 0.5), 3)
        p["Effect_LoopOffset"] = round(random.uniform(0.0, 1.0), 3)

    # transpose – uses TRANSPOSE_RANGE, weighted toward center (less extreme shifts more likely)
    lo, hi = max(-48, TRANSPOSE_RANGE[0]), min(48, TRANSPOSE_RANGE[1])
    semitones = list(range(lo, hi + 1))
    center = (lo + hi) / 2
    span = max(hi - lo, 1)
    weights = [1 + 5 * (1 - abs(s - center) / (span / 2)) for s in semitones]
    p["Voice_Transpose"] = random.choices(semitones, weights=weights)[0]

    # filter
    ftype = random.choice(FILTER_TYPES)
    p["Voice_Filter_Type"] = ftype
    p["Voice_Filter_On"]   = True
    if ftype == "Lowpass":
        p["Voice_Filter_Frequency"] = round(random.uniform(800, 20000), 1)
    elif ftype == "Highpass":
        p["Voice_Filter_Frequency"] = round(random.uniform(80, 3000), 1)
    else:
        p["Voice_Filter_Frequency"] = round(random.uniform(300, 8000), 1)
    p["Voice_Filter_Resonance"] = round(random.uniform(0.0, 0.55), 2)

    return p, effect


def build_kit(categorized: dict, kit_name: str) -> tuple:
    pad_chains = []
    used_samples = []
    pad_log = []

    for idx in range(16):
        categories = PAD_LAYOUT[idx]
        sample_path, used_cat = pick_sample(categorized, categories)

        if sample_path is None:
            params     = dict(DEFAULT_DRUM_CELL_PARAMS)
            sample_uri = None
            pad_name   = ""
            send_db    = -70.0
            choke      = None
            log        = f"Pad {idx+1:2d}  (N{36+idx})  [empty – no {'/'.join(categories)}]"
        else:
            params    = dict(DEFAULT_DRUM_CELL_PARAMS)
            pad_name  = used_cat
            fx_label  = ""

            # ── Playback FX + filter + transpose ──────────────────────
            if RANDOMIZE_FX and idx in RANDOMIZE_FX_PADS:
                params, effect = randomize_pad(params, used_cat)
                p = params
                fx_label = (f"  {effect:10s}  T:{p['Voice_Transpose']:+d}"
                            f"  {p['Voice_Filter_Type']} {p['Voice_Filter_Frequency']:.0f}Hz"
                            f"  Q:{p['Voice_Filter_Resonance']:.2f}")

            # ── Pan ───────────────────────────────────────────────────
            # drumCell "Pan" parameter: -1.0 = full left, +1.0 = full right
            if RANDOMIZE_PAN and (RANDOMIZE_PAN_PADS == "all" or idx in RANDOMIZE_PAN_PADS):
                if used_cat in ("kick", "tom", "bass"):
                    pan = 0.0
                elif used_cat in ("snare", "rim", "clap"):
                    pan = round(random.uniform(-0.105, 0.105), 3)
                elif used_cat in ("closedHH", "openHH", "hat",
                                  "perc", "conga", "cymbal", "crash", "ride"):
                    pan = round(random.uniform(-0.49, 0.49), 3)
                elif used_cat in ("fx", "vox"):
                    pan = round(random.uniform(-0.595, 0.595), 3)
                else:  # synth, stab, lead, pad, chord
                    pan = round(random.uniform(-0.315, 0.315), 3)
                params["Pan"] = pan
                fx_label += f"  pan:{pan:+.2f}"

            # ── Choke groups ──────────────────────────────────────────
            choke = None
            if CHOKE_GROUPS_HH:
                if used_cat in ("closedHH", "hat", "openHH"):
                    choke = 1
                elif used_cat in ("crash", "cymbal"):
                    choke = 2

            # ── Send amount ───────────────────────────────────────────
            if RANDOMIZE_FX and idx in RANDOMIZE_FX_PADS:
                send_db = round(random.uniform(-30.0, 0.0), 1)
            else:
                send_db = -70.0

            # ── Filename ──────────────────────────────────────────────
            cat_counts = sum(1 for _, n in used_samples
                             if n.startswith(used_cat + ".") or n.startswith(used_cat + "-"))
            clean_filename = (used_cat + sample_path.suffix.lower() if cat_counts == 0
                              else f"{used_cat}-{cat_counts + 1}{sample_path.suffix.lower()}")
            sample_uri = f"Samples/{urllib.parse.quote(clean_filename)}"
            used_samples.append((sample_path, clean_filename))

            log = (f"Pad {idx+1:2d}  (N{36+idx})  [{used_cat:10s}]  "
                   f"{clean_filename:20s} ← {sample_path.name}{fx_label}")

        pad_chains.append({
            "name": pad_name, "color": 2,
            "devices": [{"presetUri": None, "kind": "drumCell", "name": "",
                         "parameters": params,
                         "deviceData": {"sampleUri": sample_uri}}],
            "mixer": {"pan": 0.0, "solo-cue": False, "speakerOn": True,
                      "volume": 0.0,
                      "sends": [{"isEnabled": True, "amount": send_db}]},
            "drumZoneSettings": {
                "receivingNote": 36 + idx,
                "sendingNote":   60,
                "chokeGroup":    choke,
            },
        })
        pad_log.append(log)

    # ── Return effect: random or fixed ──────────────────────────────
    ret_fx_name    = random.choice(ALL_RETURN_EFFECTS) if RANDOM_RETURN_EFFECT else RETURN_EFFECT
    ret_fx_device  = make_rack_effect(ret_fx_name, randomize_settings=RANDOM_RETURN_SETTINGS)
    insert_fx_name = random.choice(list(RACK_EFFECTS.keys())) if INSERT_EFFECT == "random" else INSERT_EFFECT
    insert_fx_device = make_rack_effect(insert_fx_name, randomize_settings=RANDOM_RETURN_SETTINGS)

    preset = {
        "$schema": "http://tech.ableton.com/schema/song/1.8.2/devicePreset.json",
        "kind": "instrumentRack",
        "name": kit_name,
        "parameters": {"Enabled": True, **{f"Macro{i}": 0.0 for i in range(8)}},
        "chains": [{
            "name": "", "color": 2,
            "devices": [
                {
                    "presetUri": None, "kind": "drumRack", "name": "",
                    "parameters": {"Enabled": True, **{f"Macro{i}": 0.0 for i in range(8)}},
                    "chains": pad_chains,
                    "returnChains": [{
                        "name": ret_fx_name, "color": 2,
                        "devices": [ret_fx_device],
                        "mixer": {"pan": 0.0, "solo-cue": False, "speakerOn": True, "volume": 0.0},
                    }],
                },
                insert_fx_device,
            ],
            "mixer": {"pan": 0.0, "solo-cue": False, "speakerOn": True, "volume": 0.0, "sends": []},
        }],
    }

    return preset, used_samples, pad_log, ret_fx_name, insert_fx_name


def write_bundle(preset: dict, samples: list, path: Path):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Preset.ablpreset", json.dumps(preset, indent=2, ensure_ascii=False))
        seen = set()
        for src_path, clean_name in samples:
            if clean_name not in seen:
                clean_bytes = strip_wav_metadata(src_path)
                z.writestr(f"Samples/{clean_name}", clean_bytes)
                seen.add(clean_name)


# ── Main ─────────────────────────────────────────────────────────

def main():
    if SEED is not None:
        random.seed(SEED)
        print(f"Seed: {SEED}")

    samples_folder = Path(SAMPLES_FOLDER)
    output_folder  = Path(OUTPUT_FOLDER)

    if not samples_folder.is_dir():
        print(f"❌  Samples folder not found: {samples_folder}")
        sys.exit(1)

    output_folder.mkdir(parents=True, exist_ok=True)

    print(f"📂  Scanning: {samples_folder}\n")
    categorized = scan_samples(samples_folder)

    if not categorized:
        print("❌  No recognizable samples found.")
        sys.exit(1)

    digits    = len(str(NAME_START + KIT_COUNT - 1))
    separator = "─" * 60
    print(f"🥁  Generating {KIT_COUNT} kits  →  {output_folder}\n{separator}")

    for i in range(KIT_COUNT):
        number   = NAME_START + i
        kit_name = f"{KIT_NAME}-{str(number).zfill(digits)}"
        out_path = output_folder / f"{kit_name}.ablpresetbundle"

        preset, samples, pad_log, ret_fx, ins_fx = build_kit(categorized, kit_name)
        write_bundle(preset, samples, out_path)

        print(f"\n  ▶  {kit_name}  [return: {ret_fx}  insert: {ins_fx if ins_fx != 'dynamics' else 'Dynamics (EQ+Comp)'}]")
        if VERBOSE:
            for line in pad_log:
                print(f"     {line}")

    print(f"\n{separator}")
    print(f"✅  {KIT_COUNT} kits saved to: {output_folder.resolve()}")


if __name__ == "__main__":
    main()
