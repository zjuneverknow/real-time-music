<script setup>
import { computed, reactive, ref } from "vue";
import { useMoodSocket } from "./composables/useMoodSocket";
import { useMusicEngine } from "./composables/useMusicEngine";
import { DEFAULT_SESSION, PLAYER_CONFIG } from "./music/constants";
import { formatMode, formatMotion, formatPercent, formatRegister } from "./music/mappers";

const session = reactive(structuredClone(DEFAULT_SESSION));
const status = ref("Backend-driven Harmony and Melody layers are ready to wire into the renderer.");

const { isLoading, isReady, levels, queueBar, startSystem } = useMusicEngine({
  onStatusChange(message) {
    status.value = message;
  },
});

const { mood, connectionState, pushMood } = useMoodSocket({
  onStatusChange(message) {
    status.value = message;
  },
  onSessionState(message) {
    session.connection = connectionState.value;
    session.source = message.source;
    session.emotion = message.emotion;
    session.control = message.control;
    session.controlTokens = message.control_tokens ?? [];
    session.vaTracker = message.va_tracker;
    session.harmony = message.harmony;
  },
  onMelodyBar(message) {
    session.connection = connectionState.value;
    session.emotion = message.emotion;
    session.control = message.control;
    session.controlTokens = message.control_tokens ?? [];
    session.vaTracker = message.va_tracker;
    session.harmony = message.harmony;
    session.lastBar = {
      bar_index: message.bar_index,
      note_count: message.notes.length,
      skeleton_count: message.skeleton?.length ?? 0,
      event_count: message.events?.length ?? message.notes.length,
    };

    if (isReady.value) {
      queueBar(message);
    }
  },
  onMoodAck(message) {
    session.source = message.source;
    session.emotion = message.emotion;
    session.control = message.control;
    session.controlTokens = message.control_tokens ?? [];
    session.vaTracker = message.va_tracker;
    status.value = `Mood applied: ${message.mood || "neutral"}. Harmony refreshes on the next phrase boundary.`;
  },
});

const progressionText = computed(() => session.harmony.progression.join(" -> "));
const bpmText = computed(() => `${session.harmony.bpm} BPM`);
const modeText = computed(() => formatMode(session.harmony.mode));
const densityText = computed(() => formatPercent(session.control.density));
const registerText = computed(() => formatRegister(session.control.mean_pitch));
const motionText = computed(() => formatMotion(session.control.volatility));
const connectionText = computed(() => connectionState.value);
const trackerText = computed(() => {
  if (!session.vaTracker) {
    return "waiting";
  }
  return `alpha ${session.vaTracker.smoothing_alpha.toFixed(2)} / conf ${formatPercent(session.vaTracker.confidence)}`;
});
</script>

<template>
  <main class="appShell">
    <section class="heroPanel panel">
      <p class="eyebrow">Emotion-Driven Music Generator</p>
      <h1>Harmony stays structural. Melody stays alive.</h1>
      <p class="lede">
        Harmony and Melody generation now live in the backend. The frontend is only responsible
        for WebSocket transport, state visualization, and Tone.js rendering.
      </p>

      <div class="controls">
        <button type="button" :disabled="isLoading || isReady" @click="startSystem">
          {{ isLoading ? "Starting Audio..." : isReady ? "Renderer Ready" : "Start Audio Renderer" }}
        </button>
        <button type="button" class="secondary" :disabled="!isReady" @click="pushMood">
          Send Mood
        </button>
      </div>

      <label class="moodComposer">
        <span>Mood Prompt</span>
        <input v-model="mood" placeholder="calm, wet, restrained, but hopeful" />
      </label>

      <div class="heroStats">
        <article class="spotlightCard">
          <span>Connection</span>
          <strong>{{ connectionText }}</strong>
          <small>{{ session.source }}</small>
        </article>
        <article class="spotlightCard spotlightCard--accent">
          <span>Harmony Layer</span>
          <strong>{{ modeText }} / {{ bpmText }}</strong>
          <small>{{ progressionText }}</small>
        </article>
        <article class="spotlightCard">
          <span>Melody Layer</span>
          <strong>{{ densityText }} density / {{ motionText }}</strong>
          <small>{{ registerText }}</small>
        </article>
      </div>

      <p class="status">{{ status }}</p>
    </section>

    <section class="panel panel--stacked">
      <div class="sectionHeader">
        <h2>Harmony Layer</h2>
        <span>Low-frequency updates every phrase.</span>
      </div>

      <div class="infoGrid">
        <article class="infoCard">
          <span>Key / Mode</span>
          <strong>{{ session.harmony.key }} {{ modeText }}</strong>
        </article>
        <article class="infoCard">
          <span>Scale</span>
          <strong>{{ session.harmony.scale }}</strong>
        </article>
        <article class="infoCard">
          <span>Current Chord</span>
          <strong>{{ session.harmony.current_chord }}</strong>
        </article>
        <article class="infoCard">
          <span>Phrase Position</span>
          <strong>{{ session.harmony.phrase_bar }} / {{ session.harmony.phrase_length }}</strong>
        </article>
      </div>
    </section>

    <section class="panel panel--stacked">
      <div class="sectionHeader">
        <h2>Melody Layer</h2>
        <span>High-frequency generation per bar.</span>
      </div>

      <div class="infoGrid">
        <article class="infoCard">
          <span>Density</span>
          <strong>{{ densityText }}</strong>
        </article>
        <article class="infoCard">
          <span>Motion</span>
          <strong>{{ motionText }}</strong>
        </article>
        <article class="infoCard">
          <span>Register</span>
          <strong>{{ registerText }}</strong>
        </article>
        <article class="infoCard">
          <span>Last Bar</span>
          <strong>{{ session.lastBar.note_count }} notes</strong>
        </article>
        <article class="infoCard">
          <span>Skeleton</span>
          <strong>{{ session.lastBar.skeleton_count }} anchors</strong>
        </article>
        <article class="infoCard">
          <span>Music Events</span>
          <strong>{{ session.lastBar.event_count }} events</strong>
        </article>
      </div>
    </section>

    <section class="panel panel--stacked">
      <div class="sectionHeader">
        <h2>Control Tokens</h2>
        <span>Discrete condition prefix for rule or Transformer generators.</span>
      </div>

      <div class="tokenGrid">
        <span v-for="token in session.controlTokens" :key="token" class="tokenPill">
          {{ token }}
        </span>
      </div>
    </section>

    <section class="panel panel--stacked">
      <div class="sectionHeader">
        <h2>Emotion Input</h2>
        <span>The compact state that drives harmony selection and melody control.</span>
      </div>

      <div class="infoGrid">
        <article class="infoCard">
          <span>Valence</span>
          <strong>{{ formatPercent(session.emotion.valence) }}</strong>
        </article>
        <article class="infoCard">
          <span>Brightness</span>
          <strong>{{ formatPercent(session.emotion.brightness) }}</strong>
        </article>
        <article class="infoCard">
          <span>Arousal</span>
          <strong>{{ formatPercent(session.emotion.arousal) }}</strong>
        </article>
        <article class="infoCard">
          <span>Mean Pitch</span>
          <strong>{{ formatPercent(session.emotion.mean_pitch) }}</strong>
        </article>
        <article class="infoCard">
          <span>VA Tracker</span>
          <strong>{{ trackerText }}</strong>
        </article>
        <article class="infoCard" v-if="session.vaTracker">
          <span>Raw VA</span>
          <strong>
            {{ formatPercent(session.vaTracker.raw_valence) }} /
            {{ formatPercent(session.vaTracker.raw_arousal) }}
          </strong>
        </article>
      </div>
    </section>

    <section class="panel panel--stacked">
      <div class="sectionHeader">
        <h2>Renderer Levels</h2>
        <span>Frontend audio render only; no composition logic lives here anymore.</span>
      </div>
      <div class="meters">
        <div v-for="layer in PLAYER_CONFIG" :key="layer.key" class="layerMeter">
          <div class="layerMeter__header">
            <span>{{ layer.label }}</span>
            <span>{{ Math.round((levels[layer.key] ?? 0) * 100) }}%</span>
          </div>
          <div class="layerMeter__track">
            <div
              class="layerMeter__fill"
              :style="{
                width: `${Math.max((levels[layer.key] ?? 0) * 100, 4)}%`,
                background: layer.color,
              }"
            />
          </div>
        </div>
      </div>
    </section>
  </main>
</template>
