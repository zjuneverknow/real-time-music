import { onBeforeUnmount, onMounted, reactive, ref } from "vue";
import * as Tone from "tone";
import { PLAYER_CONFIG } from "../music/constants";

function midiToNote(midi) {
  return Tone.Frequency(midi, "midi").toNote();
}

function createEngine() {
  const reverb = new Tone.Reverb({ decay: 8.5, wet: 0.34 });
  const delay = new Tone.FeedbackDelay({ delayTime: "8n", feedback: 0.16, wet: 0.08 });
  const lowpass = new Tone.Filter({ type: "lowpass", frequency: 1800, Q: 0.55 });
  const output = new Tone.Gain(0.78);
  const players = {
    pad: {
      instrument: new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: "sine4" },
        envelope: { attack: 0.22, decay: 0.45, sustain: 0.58, release: 3.2 },
      }),
      gain: new Tone.Gain(0.46),
      meter: new Tone.Meter({ channels: 1, normalRange: true, smoothing: 0.86 }),
    },
    bass: {
      instrument: new Tone.MonoSynth({
        oscillator: { type: "triangle2" },
        filter: { Q: 2, type: "lowpass", rolloff: -24 },
        envelope: { attack: 0.08, decay: 0.28, sustain: 0.38, release: 1.25 },
        filterEnvelope: {
          attack: 0.08,
          decay: 0.28,
          sustain: 0.22,
          release: 0.7,
          baseFrequency: 80,
          octaves: 1.45,
        },
      }),
      gain: new Tone.Gain(0.36),
      meter: new Tone.Meter({ channels: 1, normalRange: true, smoothing: 0.86 }),
    },
    melody: {
      instrument: new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: "triangle4" },
        envelope: { attack: 0.045, decay: 0.22, sustain: 0.24, release: 1.35 },
      }),
      gain: new Tone.Gain(0.42),
      meter: new Tone.Meter({ channels: 1, normalRange: true, smoothing: 0.8 }),
    },
  };

  Object.values(players).forEach((player) => {
    player.instrument.connect(player.gain);
    player.gain.connect(delay);
    player.gain.connect(reverb);
    player.gain.connect(player.meter);
  });

  delay.connect(reverb);
  reverb.connect(lowpass);
  lowpass.connect(output);
  output.toDestination();

  return {
    queueBar(bar) {
      const startAt = Tone.now() + 0.12;
      const secondsPerBeat = bar.bar_duration_seconds / 4;
      const chordNotes = bar.harmony.chord.tones.map(midiToNote);
      const bassNote = midiToNote(bar.harmony.chord.bass_root);
      const brightness = bar.emotion?.brightness ?? 0.4;
      const density = bar.control?.density ?? 0.3;
      const meanPitch = bar.control?.mean_pitch ?? 0.4;
      const melodySalience = bar.control?.melody_salience ?? 0.35;
      const rhythmSalience = bar.control?.rhythm_salience ?? 0.35;
      const wetness = bar.control?.wetness ?? 0.5;

      lowpass.frequency.rampTo(650 + brightness * 2400, 0.28);
      reverb.wet.rampTo(0.18 + wetness * 0.42, 0.35);
      delay.wet.rampTo(0.04 + wetness * 0.14, 0.3);
      players.pad.gain.gain.rampTo(0.38 + (1 - density) * 0.2, 0.25);
      players.bass.gain.gain.rampTo(0.2 + rhythmSalience * 0.22, 0.25);
      players.melody.gain.gain.rampTo(0.22 + melodySalience * 0.28 + meanPitch * 0.04, 0.25);

      players.pad.instrument.triggerAttackRelease(chordNotes, bar.bar_duration_seconds * 0.96, startAt, 0.34);
      if (rhythmSalience > 0.18) {
        players.bass.instrument.triggerAttackRelease(bassNote, secondsPerBeat * 2.3, startAt, 0.42);
        if (rhythmSalience > 0.42) {
          players.bass.instrument.triggerAttackRelease(bassNote, secondsPerBeat * 1.8, startAt + secondsPerBeat * 2, 0.34);
        }
      }

      bar.notes.forEach((note) => {
        players.melody.instrument.triggerAttackRelease(
          midiToNote(note.midi),
          Math.max(note.duration_beats * secondsPerBeat * 0.96, 0.12),
          startAt + note.start_beats * secondsPerBeat,
          Math.min(note.velocity * 0.82, 0.72),
        );
      });
    },
    getLevels() {
      return Object.fromEntries(
        PLAYER_CONFIG.map(({ key }) => [key, Math.max(0, players[key].meter.getValue() || 0)]),
      );
    },
    dispose() {
      Object.values(players).forEach((player) => {
        player.instrument.dispose();
        player.gain.dispose();
        player.meter.dispose();
      });
      reverb.dispose();
      delay.dispose();
      lowpass.dispose();
      output.dispose();
    },
  };
}

export function useMusicEngine(options = {}) {
  const { onStatusChange = () => {} } = options;
  const isLoading = ref(false);
  const isReady = ref(false);
  const levels = reactive(Object.fromEntries(PLAYER_CONFIG.map(({ key }) => [key, 0])));
  const engineRef = ref(null);
  let frameId = 0;

  onMounted(() => {
    const syncLevels = () => {
      if (engineRef.value) {
        Object.assign(levels, engineRef.value.getLevels());
      }
      frameId = requestAnimationFrame(syncLevels);
    };

    frameId = requestAnimationFrame(syncLevels);
  });

  onBeforeUnmount(() => {
    cancelAnimationFrame(frameId);
    engineRef.value?.dispose();
  });

  async function startSystem() {
    if (isReady.value || isLoading.value) {
      return;
    }

    isLoading.value = true;
    onStatusChange("Starting renderer and preparing Tone.js voices...");

    try {
      await Tone.start();
      engineRef.value = createEngine();
      isReady.value = true;
      onStatusChange("Renderer is live. Waiting for backend Harmony and Melody bars.");
    } catch (error) {
      onStatusChange(error instanceof Error ? error.message : "Failed to start audio renderer.");
    } finally {
      isLoading.value = false;
    }
  }

  function queueBar(bar) {
    if (!engineRef.value) {
      return;
    }

    engineRef.value.queueBar(bar);
  }

  return {
    isLoading,
    isReady,
    levels,
    queueBar,
    startSystem,
  };
}
