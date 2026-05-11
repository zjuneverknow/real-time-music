import { onBeforeUnmount, onMounted, ref } from "vue";
import { DEFAULT_MOOD } from "../music/constants";

export function useMoodSocket(options = {}) {
  const {
    onStatusChange = () => {},
    onSessionState = () => {},
    onMelodyBar = () => {},
    onMoodAck = () => {},
  } = options;

  const mood = ref(DEFAULT_MOOD);
  const connectionState = ref("connecting");
  const wsRef = ref(null);

  onMounted(() => {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${protocol}://${window.location.hostname}:8000/ws/music`);
    wsRef.value = socket;

    socket.onopen = () => {
      connectionState.value = "connected";
      onStatusChange("Backend socket connected. Harmony and Melody are now server-driven.");
    };

    socket.onmessage = (event) => {
      const message = JSON.parse(event.data);

      if (message.type === "session_state") {
        onSessionState(message);
        return;
      }

      if (message.type === "melody_bar") {
        onMelodyBar(message);
        return;
      }

      if (message.type === "mood_ack") {
        onMoodAck(message);
      }
    };

    socket.onerror = () => {
      connectionState.value = "error";
      onStatusChange("WebSocket unavailable. Start the backend on port 8000 to stream music bars.");
    };

    socket.onclose = () => {
      connectionState.value = "closed";
    };
  });

  onBeforeUnmount(() => {
    wsRef.value?.close();
  });

  function pushMood() {
    if (wsRef.value?.readyState !== WebSocket.OPEN) {
      onStatusChange("Socket not ready, so the mood prompt cannot be sent yet.");
      return;
    }

    wsRef.value.send(JSON.stringify({ mood: mood.value }));
    onStatusChange("Mood prompt sent. New Melody control is immediate; Harmony will refresh on the next phrase.");
  }

  return {
    mood,
    connectionState,
    pushMood,
  };
}
