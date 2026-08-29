const state = {
  position: null,
  conversationId: "",
  user: localStorage.getItem("campus-agent-user") || crypto.randomUUID(),
  busy: false,
};
localStorage.setItem("campus-agent-user", state.user);

const messages = document.querySelector("#messages");
const composer = document.querySelector("#composer");
const input = document.querySelector("#queryInput");
const sendButton = document.querySelector("#sendButton");
const locationButton = document.querySelector("#locationButton");
const locationLabel = document.querySelector("#locationLabel");

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatAnswer(value) {
  let html = escapeHtml(value);
  html = html.replace(/\[([^\]]+)\]\((https:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  return html
    .split(/\n{2,}/)
    .map((block) => `<p>${block.replaceAll("\n", "<br>")}</p>`)
    .join("");
}

function addMessage(role, text = "") {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  if (role === "assistant") {
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = "游";
    article.append(avatar);
  }
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = role === "assistant" ? formatAnswer(text) : `<p>${escapeHtml(text)}</p>`;
  article.append(bubble);
  messages.append(article);
  messages.scrollTop = messages.scrollHeight;
  return bubble;
}

function locate() {
  locationButton.className = "location-button";
  locationLabel.textContent = "正在定位";
  if (!navigator.geolocation) {
    locationButton.classList.add("failed");
    locationLabel.textContent = "使用清华默认位置";
    return;
  }
  navigator.geolocation.getCurrentPosition(
    ({ coords }) => {
      state.position = {
        longitude: coords.longitude,
        latitude: coords.latitude,
        accuracy: coords.accuracy,
      };
      locationButton.classList.add("ready");
      locationLabel.textContent = `已定位 · ±${Math.round(coords.accuracy)}m`;
    },
    () => {
      state.position = null;
      locationButton.classList.add("failed");
      locationLabel.textContent = "使用清华默认位置";
    },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
  );
}

function handleEvent(event) {
  if (event.conversation_id) state.conversationId = event.conversation_id;
  if (["message", "agent_message"].includes(event.event) && event.answer) return event.answer;
  if (event.event === "error") throw new Error(event.message || "Dify 调用失败");
  return "";
}

async function sendQuery(query) {
  if (state.busy || !query.trim()) return;
  state.busy = true;
  sendButton.disabled = true;
  input.value = "";
  addMessage("user", query);
  const answerBubble = addMessage("assistant", "");
  answerBubble.classList.add("typing");
  let answer = "";

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        ...(state.position || {}),
        coordinate_system: "gps",
        conversation_id: state.conversationId,
        user: state.user,
      }),
    });
    if (!response.ok || !response.body) throw new Error(`聊天服务返回 ${response.status}`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done }).replaceAll("\r\n", "\n");
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";
      for (const chunk of chunks) {
        const line = chunk.split("\n").find((item) => item.startsWith("data:"));
        if (!line) continue;
        const payload = JSON.parse(line.slice(5).trim());
        answer += handleEvent(payload);
        answerBubble.classList.remove("typing");
        answerBubble.innerHTML = formatAnswer(answer);
        messages.scrollTop = messages.scrollHeight;
      }
      if (done) break;
    }
    if (!answer) answerBubble.innerHTML = "<p>暂时没有取得推荐，请稍后重试。</p>";
  } catch (error) {
    answerBubble.classList.remove("typing");
    answerBubble.innerHTML = `<p>请求失败：${escapeHtml(error.message)}</p>`;
  } finally {
    state.busy = false;
    sendButton.disabled = false;
    input.focus();
  }
}

composer.addEventListener("submit", (event) => {
  event.preventDefault();
  sendQuery(input.value);
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 132)}px`;
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => sendQuery(button.dataset.prompt));
});
locationButton.addEventListener("click", locate);
locate();
