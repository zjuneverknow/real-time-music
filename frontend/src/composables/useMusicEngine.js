import { onBeforeUnmount, onMounted, reactive, ref } from "vue";
import * as Tone from "tone";
import { PLAYER_CONFIG } from "../music/constants";

function midiToNote(midi) {
  return Tone.Frequency(midi, "midi").toNote();
}

function createEngine() {
  const reverb = new Tone.Reverb({ decay: 6.5, wet: 0.26 });
  const lowpass = new Tone.Filter({ type: "lowpass", frequency: 2200, Q: 0.7 });
  const output = new Tone.Gain(0.9);
  const players = {
    pad: {
      instrument: new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: "triangle8" },
        envelope: { attack: 0.06, decay: 0.15, sustain: 0.45, release: 1.8 },
      }),
      gain: new Tone.Gain(0.5),
      meter: new Tone.Meter({ channels: 1, normalRange: true, smoothing: 0.86 }),
    },
    bass: {
      instrument: new Tone.MonoSynth({
        oscillator: { type: "sawtooth4" },
        filter: { Q: 2, type: "lowpass", rolloff: -24 },
        envelope: { attack: 0.02, decay: 0.2, sustain: 0.45, release: 0.8 },
        filterEnvelope: {
          attack: 0.02,
          decay: 0.18,
          sustain: 0.3,
          release: 0.7,
          baseFrequency: 80,
          octaves: 2,
        },
      }),
      gain: new Tone.Gain(0.62),
      meter: new Tone.Meter({ channels: 1, normalRange: true, smoothing: 0.86 }),
    },
    melody: {
      instrument: new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: "sine6" },
        envelope: { attack: 0.01, decay: 0.14, sustain: 0.18, release: 0.9 },
      }),
      gain: new Tone.Gain(0.52),
      meter: new Tone.Meter({ channels: 1, normalRange: true, smoothing: 0.8 }),
    },
  };

  Object.values(players).forEach((player) => {
    player.instrument.connect(player.gain);
    player.gain.connect(reverb);
    player.gain.connect(player.meter);
  });

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

      lowpass.frequency.rampTo(800 + brightness * 3400, 0.18);
      reverb.wet.rampTo(0.14 + (1 - brightness) * 0.25, 0.2);
      players.pad.gain.gain.rampTo(0.34 + (1 - density) * 0.22, 0.15);
      players.melody.gain.gain.rampTo(0.32 + density * 0.3 + meanPitch * 0.08, 0.15);

      players.pad.instrument.triggerAttackRelease(chordNotes, bar.bar_duration_seconds * 0.92, startAt, 0.42);
      players.bass.instrument.triggerAttackRelease(bassNote, secondsPerBeat * 2.1, startAt, 0.64);
      players.bass.instrument.triggerAttackRelease(bassNote, secondsPerBeat * 1.8, startAt + secondsPerBeat * 2, 0.56);

      bar.notes.forEach((note) => {
        players.melody.instrument.triggerAttackRelease(
          midiToNote(note.midi),
          Math.max(note.duration_beats * secondsPerBeat * 0.92, 0.09),
          startAt + note.start_beats * secondsPerBeat,
          note.velocity,
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
