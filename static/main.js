const socket = io();
const pill = document.getElementById("pill");
const pillText = document.getElementById("pillText");
const transcript = document.getElementById("transcript");
const generateBtn = document.getElementById("generateBtn");
const countdownWrap = document.getElementById("countdownWrap");
const countdownBar = document.getElementById("countdownBar");
const queueSection = document.getElementById("queueSection");
const queueList = document.getElementById("queueList");

let partialLine = null;
let countdownTimeout = null;

// --- Trigger word state ---
let triggerWords = ["questions", "thoughts", "liam", "add anything", "feedback"];
let triggersEnabled = true;

function renderTags() {
    const wrap = document.getElementById("tagWrap");
    const input = document.getElementById("tagInput");
    wrap.innerHTML = "";
    triggerWords.forEach(w => {
        const tag = document.createElement("div");
        tag.className = "tag";
        tag.innerHTML = `<span>${w}</span><button onclick="removeTag('${w}')">✕</button>`;
        wrap.appendChild(tag);
    });
    wrap.appendChild(input);
}

function removeTag(word) {
    triggerWords = triggerWords.filter(w => w !== word);
    renderTags();
    updateTriggers();
}

function handleTagKey(e) {
    if (e.key === "Enter" || e.key === ",") {
        e.preventDefault();
        const val = e.target.value.trim().toLowerCase();
        if (val && !triggerWords.includes(val)) {
            triggerWords.push(val);
            renderTags();
            updateTriggers();
        }
        e.target.value = "";
    }
}

function updateTriggers() {
    triggersEnabled = document.getElementById("triggerToggle").checked;
    document.getElementById("toggleLabel").textContent = triggersEnabled ? "On" : "Off";
    socket.emit("update_triggers", { words: triggerWords, enabled: triggersEnabled });
}

renderTags();

// --- Status ---
function setStatus(msg, state) {
    pillText.textContent = msg;
    pill.className = "status-pill " + (state || "listening");
}

socket.on("connect", () => setStatus("Connected", "listening"));
socket.on("disconnect", () => setStatus("Disconnected", ""));
socket.on("status", d => setStatus(d.msg, d.state));

// --- Transcript ---
socket.on("transcript", d => {
    if (!d.final) {
        if (!partialLine) {
            partialLine = document.createElement("div");
            partialLine.className = "t-line partial";
            transcript.appendChild(partialLine);
        }
        partialLine.textContent = d.text;
    } else {
        if (partialLine) {
            partialLine.classList.remove("partial");
            partialLine = null;
        } else {
            const line = document.createElement("div");
            line.className = "t-line";
            line.textContent = d.text;
            transcript.appendChild(line);
        }
    }
    transcript.scrollTop = transcript.scrollHeight;
});

socket.on("trigger", d => {
    const last = transcript.querySelector(".t-line:last-child");
    if (last) last.classList.add("trigger");
});

// --- Countdown bar ---
socket.on("trigger_countdown", d => {
    const delay = d.delay * 1000;
    countdownWrap.classList.add("visible");
    countdownBar.style.transition = "none";
    countdownBar.style.width = "100%";
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            countdownBar.style.transition = `width ${delay}ms linear`;
            countdownBar.style.width = "0%";
        });
    });
    if (countdownTimeout) clearTimeout(countdownTimeout);
    countdownTimeout = setTimeout(() => countdownWrap.classList.remove("visible"), delay);
});

socket.on("spoke", () => {
    countdownWrap.classList.remove("visible");
    if (countdownTimeout) clearTimeout(countdownTimeout);
});

// --- Queue ---

function syncQueueVisibility() {
    queueSection.style.display = queueList.children.length > 0 ? "block" : "none";
}

// Add a new card (loading state initially)
socket.on("queue_add", d => {
    // If card already exists (e.g. regenerate), update it
    const existing = document.getElementById(`card-${d.id}`);
    if (existing) {
        setCardLoading(existing, d.loading);
        if (d.text) existing.querySelector(".card-textarea").value = d.text;
        return;
    }

    const card = document.createElement("div");
    card.className = "queue-card loading";
    card.id = `card-${d.id}`;
    // First card gets the "next" badge (auto-fire target)
    const isFirst = queueList.children.length === 0;

    card.innerHTML = `
        <div class="card-header">
            <span class="card-badge">${isFirst ? "next" : "queued"}</span>
            <div class="card-actions">
                <button class="btn btn-speak card-speak" onclick="speakItem('${d.id}')" disabled>▶ Speak</button>
                <button class="btn btn-stop card-remove" onclick="removeItem('${d.id}')">✕</button>
            </div>
        </div>
        <textarea class="card-textarea" rows="2" onblur="onCardBlur('${d.id}', this)">${d.text}</textarea>
        <div class="card-footer">
            <span class="card-status">generating…</span>
        </div>
    `;

    queueList.appendChild(card);
    // Set baseline so onCardBlur can detect changes immediately
    card.dataset.originalText = d.text;
    syncQueueVisibility();
    refreshBadges();
});

// Mark card as ready
socket.on("queue_ready", d => {
    const card = document.getElementById(`card-${d.id}`);
    if (!card) return;
    card.classList.remove("loading");
    card.querySelector(".card-speak").disabled = false;
    card.querySelector(".card-status").textContent = "ready";
    // Update baseline so next edit is compared against the regenerated text
    const ta = card.querySelector(".card-textarea");
    if (ta) card.dataset.originalText = ta.value.trim();
});

// Mark card as errored
socket.on("queue_error", d => {
    const card = document.getElementById(`card-${d.id}`);
    if (!card) return;
    card.classList.remove("loading");
    card.classList.add("error");
    card.querySelector(".card-status").textContent = `error: ${d.error}`;
});

// Remove card
socket.on("queue_remove", d => {
    const card = document.getElementById(`card-${d.id}`);
    if (card) {
        card.classList.add("removing");
        setTimeout(() => {
            card.remove();
            syncQueueVisibility();
            refreshBadges();
        }, 250);
    }
});

function setCardLoading(card, loading) {
    if (loading) {
        card.classList.add("loading");
        card.querySelector(".card-speak").disabled = true;
        card.querySelector(".card-status").textContent = "regenerating…";
    }
}

function refreshBadges() {
    const cards = queueList.querySelectorAll(".queue-card");
    cards.forEach((card, i) => {
        const badge = card.querySelector(".card-badge");
        if (badge) badge.textContent = i === 0 ? "next" : "queued";
    });
}

function onCardBlur(id, textarea) {
    const card = document.getElementById(`card-${id}`);
    if (!card) return;
    const current = textarea.value.trim();
    if (!current) return;
    if (card.dataset.originalText !== current) {
        card.dataset.originalText = current;
        socket.emit("regenerate", { id, text: current });
    }
}

function speakItem(id) {
    countdownWrap.classList.remove("visible");
    if (countdownTimeout) clearTimeout(countdownTimeout);
    socket.emit("speak", { id });
}

function removeItem(id) {
    socket.emit("remove", { id });
}

// --- Actions ---
function generate() {
    const text = document.getElementById("thoughtInput").value.trim();
    if (!text) return;
    socket.emit("generate", { text });
    document.getElementById("thoughtInput").value = "";
}

function stop() {
    countdownWrap.classList.remove("visible");
    if (countdownTimeout) clearTimeout(countdownTimeout);
    socket.emit("stop");
}

document.getElementById("thoughtInput").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); generate(); }
});