const socket = io();
const pill = document.getElementById("pill");
const pillText = document.getElementById("pillText");
const transcript = document.getElementById("transcript");
const readyPanel = document.getElementById("readyPanel");
const readyText = document.getElementById("readyText");
const generateBtn = document.getElementById("generateBtn");
const countdownWrap = document.getElementById("countdownWrap");
const countdownBar = document.getElementById("countdownBar");
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

// --- Ready / Spoke ---
socket.on("ready", d => {
    readyText.textContent = d.text;
    readyPanel.classList.add("visible");
    generateBtn.disabled = false;
});

socket.on("spoke", () => {
    readyPanel.classList.remove("visible");
    countdownWrap.classList.remove("visible");
    if (countdownTimeout) clearTimeout(countdownTimeout);
});

// --- Actions ---
function generate() {
    const text = document.getElementById("thoughtInput").value.trim();
    if (!text) return;
    generateBtn.disabled = true;
    readyPanel.classList.remove("visible");
    socket.emit("generate", { text });
    document.getElementById("thoughtInput").value = "";
}

function speak() {
    countdownWrap.classList.remove("visible");
    if (countdownTimeout) clearTimeout(countdownTimeout);
    socket.emit("speak");
}

function stop() {
    countdownWrap.classList.remove("visible");
    if (countdownTimeout) clearTimeout(countdownTimeout);
    socket.emit("stop");
    generateBtn.disabled = false;
}

document.getElementById("thoughtInput").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); generate(); }
});