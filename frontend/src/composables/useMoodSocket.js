import { onBeforeUnmount, onMounted, ref } from "vue";
import { DEFAULT_MOOD } from "../music/constants";

export function useMoodSocket(options = {}) {
  const {
    onStatusChange = () => {},
    onSessionState = () => {},
    onMelodyBar = () => {},
    onMoodAck = () => {},
    onFeedbackAck = () => {},
    onSceneAck = () => {},
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
        return;
      }

      if (message.type === "feedback_ack") {
        onFeedbackAck(message);
        return;
      }

      if (message.type === "scene_ack") {
        onSceneAck(message);
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

  function send(message) {
    if (wsRef.value?.readyState !== WebSocket.OPEN) {
      onStatusChange("Socket not ready, so the message cannot be sent yet.");
      return false;
    }

    wsRef.value.send(JSON.stringify(message));
    return true;
  }

  function pushMood(sceneId = "none") {
    if (!send({ type: "mood", mood: mood.value, scene_id: sceneId })) {
      return;
    }
    onStatusChange("Mood prompt sent. New Melody control is immediate; Harmony will refresh on the next phrase.");
  }

  function pushScene(sceneId) {
    if (send({ type: "scene_update", scene_id: sceneId })) {
      onStatusChange("Scene update sent. The next bars will use the new scene bias.");
    }
  }

  function pushFeedback(feedbackType, like = null) {
    if (send({ type: "feedback", feedback_type: feedbackType, like })) {
      onStatusChange(`Feedback sent: ${feedbackType}.`);
    }
  }

  return {
    mood,
    connectionState,
    pushMood,
    pushScene,
    pushFeedback,
  };
}
