export const PLAYER_CONFIG = [
  { key: "pad", label: "Harmony Pad", color: "#f29d52" },
  { key: "bass", label: "Bass Pulse", color: "#ff6f61" },
  { key: "melody", label: "Melody Lead", color: "#57b6ff" },
];

export const DEFAULT_MOOD = "happy";

export const DEFAULT_SESSION = {
  connection: "connecting",
  source: "default",
  emotion: {
    valence: 0.38,
    brightness: 0.34,
    arousal: 0.42,
    density: 0.28,
    volatility: 0.24,
    mean_pitch: 0.35,
  },
  control: {
    density: 0.28,
    volatility: 0.24,
    mean_pitch: 0.35,
  },
  controlTokens: [],
  vaTracker: null,
  harmony: {
    key: "C",
    mode: "minor",
    bpm: 102,
    progression: ["i", "VI", "III", "VII"],
    scale: "aeolian",
    current_chord: "i",
    phrase_bar: 1,
    phrase_length: 4,
  },
  lastBar: {
    bar_index: 0,
    note_count: 0,
    skeleton_count: 0,
    event_count: 0,
  },
};
