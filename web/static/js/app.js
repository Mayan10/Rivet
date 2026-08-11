(() => {
  "use strict";

  const roomRowsEl = document.getElementById("room-rows");
  const addRoomBtn = document.getElementById("add-room");
  const form = document.getElementById("gen-form");
  const submitBtn = document.getElementById("submit-btn");
  const resultsEl = document.getElementById("results");
  const alertsEl = document.getElementById("alerts");
  const emptyStateEl = document.getElementById("empty-state");

  let roomTypes = [];
  let rowId = 0;

  const DEFAULT_ROOMS = [
    { room_type: "living_room", count: 1 },
    { room_type: "master_bedroom", count: 1, attached_bathroom: true },
    { room_type: "bedroom", count: 2, attached_bathroom: true },
    { room_type: "kitchen", count: 1 },
    { room_type: "dining_room", count: 1 },
    { room_type: "bathroom", count: 1 },
  ];

  function titleCase(s) {
    return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function addRoomRow(preset) {
    const id = `room-${rowId++}`;
    const row = document.createElement("div");
    row.className = "room-row";
    row.dataset.id = id;

    const options = roomTypes
      .map((t) => `<option value="${t}" ${preset && preset.room_type === t ? "selected" : ""}>${titleCase(t)}</option>`)
      .join("");

    row.innerHTML = `
      <div>
        <label>Room type</label>
        <select class="f-type">${options}</select>
      </div>
      <div>
        <label>Count</label>
        <input class="f-count" type="number" min="1" value="${preset?.count ?? 1}">
      </div>
      <div>
        <label>Area (m², optional)</label>
        <input class="f-area" type="number" min="1" step="0.5" placeholder="auto">
      </div>
      <div class="checkbox-field">
        <input class="f-ensuite" type="checkbox" id="${id}-ensuite" ${preset?.attached_bathroom ? "checked" : ""}>
        <label for="${id}-ensuite">Ensuite</label>
      </div>
      <button type="button" class="btn-remove" title="Remove room">✕</button>
    `;

    row.querySelector(".btn-remove").addEventListener("click", () => row.remove());
    roomRowsEl.appendChild(row);
  }

  function collectRooms() {
    return [...roomRowsEl.querySelectorAll(".room-row")].map((row) => {
      const area = row.querySelector(".f-area").value;
      return {
        room_type: row.querySelector(".f-type").value,
        count: parseInt(row.querySelector(".f-count").value, 10) || 1,
        target_area_sqm: area ? parseFloat(area) : null,
        attached_bathroom: row.querySelector(".f-ensuite").checked,
      };
    });
  }

  function showAlert(message, kind = "error") {
    alertsEl.innerHTML = `<div class="alert alert-${kind}">${message}</div>`;
  }

  function clearAlert() {
    alertsEl.innerHTML = "";
  }

  function scoreClass(score) {
    if (score >= 75) return "good";
    if (score >= 45) return "warn";
    return "bad";
  }

  function renderCandidates(candidates) {
    emptyStateEl.style.display = "none";
    resultsEl.innerHTML = "";

    candidates.forEach((c) => {
      const card = document.createElement("div");
      card.className = "candidate";

      const violationsHtml = c.violations.length
        ? `<ul class="violations">${c.violations.map((v) => `<li>${v}</li>`).join("")}</ul>`
        : `<div class="stat" style="color: var(--success)">No rule violations.</div>`;

      card.innerHTML = `
        <div class="cand-head">
          <span class="title">${c.candidate_id}</span>
          <span class="score-pill ${scoreClass(c.score)}">${c.score}/100</span>
        </div>
        <div class="cand-body">
          <div class="cand-preview">${c.svg}</div>
          <div class="cand-side">
            <div class="stat"><b>${c.gross_area_sqm} m²</b> gross floor area</div>
            <div class="stat"><b>${c.rooms.length}</b> rooms, <b>${c.openings.length}</b> openings</div>
            ${violationsHtml}
            <div class="cand-actions">
              <a class="btn-secondary" href="${c.dxf_url}" download>Download DXF</a>
              <button type="button" class="btn-secondary btn-png">PNG</button>
            </div>
          </div>
        </div>
      `;

      card.querySelector(".btn-png").addEventListener("click", () => {
        const a = document.createElement("a");
        a.href = `data:image/png;base64,${c.png_base64}`;
        a.download = `${c.candidate_id}.png`;
        a.click();
      });

      resultsEl.appendChild(card);
    });
  }

  async function loadRoomTypes() {
    const res = await fetch("/api/v1/room-types");
    roomTypes = await res.json();
    DEFAULT_ROOMS.forEach(addRoomRow);
  }

  addRoomBtn.addEventListener("click", () => addRoomRow());

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAlert();

    const rooms = collectRooms();
    if (rooms.length === 0) {
      showAlert("Add at least one room.");
      return;
    }

    const payload = {
      plot: {
        width_m: parseFloat(document.getElementById("width").value),
        length_m: parseFloat(document.getElementById("length").value),
        entrance: document.getElementById("entrance").value,
      },
      rooms,
      num_candidates: parseInt(document.getElementById("candidates").value, 10) || 3,
    };

    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="spinner"></span> Generating…`;

    try {
      const res = await fetch("/api/v1/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (!res.ok) {
        showAlert(data.error || "Generation failed.");
        return;
      }

      if (data.warnings && data.warnings.length) {
        showAlert(data.warnings.join("<br>"), "warn");
      }

      renderCandidates(data.candidates);
    } catch (err) {
      showAlert("Could not reach the server. Is it running?");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Generate floor plans";
    }
  });

  loadRoomTypes();
})();
