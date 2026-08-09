const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const feed = document.getElementById("feed");
const emptyState = document.getElementById("emptyState");

const RESULTS_URL = "http://127.0.0.1:5000/results";
const POLL_INTERVAL_MS = 1500;

let lastSeenId = 0;

function parseSuggestion(text) {
  const grab = (label, nextLabels) => {
    const pattern = new RegExp(
      "\\*\\*" + label + ":\\*\\*\\s*([\\s\\S]*?)(?=\\*\\*(?:" + nextLabels.join("|") + "):\\*\\*|$)"
    );
    const match = text.match(pattern);
    return match ? match[1].trim() : "(not provided)";
  };
  return {
    cause: grab("CAUSE", ["FIX", "CHECK"]),
    fix: grab("FIX", ["CHECK"]),
    check: grab("CHECK", []),
  };
}

function addCard(result) {
  emptyState.style.display = "none";
  const parsed = parseSuggestion(result.suggestion);

  const card = document.createElement("div");
  card.className = "card";
  card.innerHTML = `
    <div class="card-head">
      <span class="card-service">${result.service || "unknown-service"}</span>
      <span class="card-time">${result.timestamp || ""}</span>
    </div>
    <div class="card-type">${result.error_type || "unspecified"}</div>
    <div class="block cause"><div class="block-label">CAUSE</div><div class="block-body">${parsed.cause}</div></div>
    <div class="block fix"><div class="block-label">FIX</div><div class="block-body">${parsed.fix}</div></div>
    <div class="block check"><div class="block-label">CHECK</div><div class="block-body">${parsed.check}</div></div>
    <div class="decision-row">
      <button class="btn-apply">Mark as applied</button>
      <button class="btn-reject">Reject / investigate</button>
    </div>
    <div class="decision-tag"></div>
  `;

  const tag = card.querySelector(".decision-tag");
  card.querySelector(".btn-apply").addEventListener("click", () => {
    tag.textContent = "Marked as applied — verify using the CHECK steps above.";
    tag.style.display = "block";
    tag.style.background = "var(--good-soft)";
    tag.style.color = "var(--good)";
  });
  card.querySelector(".btn-reject").addEventListener("click", () => {
    tag.textContent = "Marked as rejected — investigate manually.";
    tag.style.display = "block";
    tag.style.background = "var(--fail-soft)";
    tag.style.color = "var(--fail)";
  });

  feed.insertBefore(card, emptyState.nextSibling);
  feed.prepend(card);
}

function setConnected(isConnected) {
  if (isConnected) {
    statusDot.className = "dot live";
    statusText.textContent = "Connected";
  } else {
    statusDot.className = "dot down";
    statusText.textContent = "Not connected";
  }
}

// Quietly checks for new results every 1.5 seconds. This is invisible
// to the user - no manual refresh, no button. It only affects how this
// browser tab notices new results; CloudGuardian itself still only
// wakes up when a real webhook arrives, exactly as before.
async function poll() {
  try {
    const response = await fetch(`${RESULTS_URL}?since=${lastSeenId}`);
    if (!response.ok) {
      setConnected(false);
      return;
    }
    setConnected(true);
    const newResults = await response.json();
    newResults.forEach((result) => {
      addCard(result);
      if (result.id > lastSeenId) lastSeenId = result.id;
    });
  } catch (err) {
    setConnected(false);
  }
}

poll();
setInterval(poll, POLL_INTERVAL_MS);
