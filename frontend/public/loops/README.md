No external audio assets are required in `frontend/public/loops/`.

The frontend now uses pure Tone.js instruments only:

- Piano: `Tone.PolySynth(Tone.Synth)` for rhythmic arpeggios.
- Cello: `Tone.MonoSynth` for sustained roots and 5ths.
- Sparkle: `Tone.FMSynth` for high-register contour accents.

All musical events are scheduled through `Tone.Transport.scheduleRepeat`:

- Piano: 16th-note rhythmic arpeggios driven by the current chord.
- Cello: sustained roots or 5ths on half-note boundaries.
- Sparkle: high-register contour notes with a 20% trigger probability on 8th notes.

`alpha` controls tempo, harmonic drift from major to minor, reverb wetness,
delay feedback, and note density. Scale changes are committed only at the start
of a new bar.
