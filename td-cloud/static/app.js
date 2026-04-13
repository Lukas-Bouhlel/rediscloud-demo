const socket = io();

const serverPill = document.getElementById("server-pill");
const initialState = document.getElementById("initial-state");
const updates = document.getElementById("updates");
const input = document.getElementById("message-input");
const publishBtn = document.getElementById("publish-btn");
const publishStatus = document.getElementById("publish-status");

function renderEntry(entry, container, prefix) {
  const item = document.createElement("div");
  item.className = "item";
  const header = document.createElement("div");
  header.className = "item-header";
  header.textContent = prefix;
  const body = document.createElement("pre");
  body.textContent = JSON.stringify(entry, null, 2);
  item.appendChild(header);
  item.appendChild(body);
  container.prepend(item);
}

socket.on("connect", () => {
  publishStatus.textContent = "Connecte au serveur.";
});

socket.on("initial_state", (payload) => {
  serverPill.textContent = `server_id: ${payload.server_id}`;
  initialState.innerHTML = "";
  Object.entries(payload.entries || {}).forEach(([key, value]) => {
    renderEntry({ redis_key: key, ...value }, initialState, "initial_state");
  });
});

socket.on("update", (payload) => {
  renderEntry(payload, updates, "update");
});

publishBtn.addEventListener("click", async () => {
  const message = input.value.trim();
  if (!message) {
    publishStatus.textContent = "Veuillez saisir un message.";
    return;
  }

  publishBtn.disabled = true;
  publishStatus.textContent = "Publication en cours...";

  try {
    const response = await fetch("/publish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Erreur de publication");
    }

    publishStatus.textContent = `Publie: ${data.redis_key}`;
    input.value = "";
  } catch (err) {
    publishStatus.textContent = `Erreur: ${err.message}`;
  } finally {
    publishBtn.disabled = false;
  }
});
