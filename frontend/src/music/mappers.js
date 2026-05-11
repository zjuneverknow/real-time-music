export function clamp01(value) {
  return Math.max(0, Math.min(1, value));
}

export function formatPercent(value) {
  return `${Math.round(clamp01(value) * 100)}%`;
}

export function formatMode(mode) {
  if (mode === "major") return "Major";
  if (mode === "minor") return "Minor";
  if (mode === "dorian") return "Dorian";
  return mode;
}

export function formatRegister(value) {
  if (value < 0.34) return "Low register";
  if (value > 0.66) return "High register";
  return "Mid register";
}

export function formatMotion(value) {
  return value > 0.6 ? "Leaping" : value < 0.35 ? "Stepwise" : "Balanced";
}
