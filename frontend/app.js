const state = {
  file: null,
  columns: [],
  preview: [],
  suggested: {},
  keepExtraCols: new Set(),
  categories: [],
  terminals: [],
  catMapping: {},
  termMapping: {},
  carouselsManual: [
    { name: "Carousel 1", wide: 8, narrow: 4 },
    { name: "Carousel 2", wide: 8, narrow: 4 },
    { name: "Carousel 3", wide: 8, narrow: 4 }
  ],
  carouselsTerminal: [],
  job: null,
  charts: {}
};

const steps = Array.from(document.querySelectorAll(".step"));
const stepButtons = Array.from(document.querySelectorAll(".stepper button"));
let currentStep = 1;

const fileInput = document.getElementById("fileInput");
const previewBtn = document.getElementById("previewBtn");
const previewTable = document.getElementById("previewTable");
const columnsList = document.getElementById("columnsList");
const fileHint = document.getElementById("fileHint");

const mapDeparture = document.getElementById("mapDeparture");
const mapFlight = document.getElementById("mapFlight");
const mapCategory = document.getElementById("mapCategory");
const mapPositions = document.getElementById("mapPositions");
const mapTerminal = document.getElementById("mapTerminal");
const mapOpening = document.getElementById("mapOpening");
const mapClosing = document.getElementById("mapClosing");
const extraCols = document.getElementById("extraCols");

const inspectBtn = document.getElementById("inspectBtn");
const categoryMapping = document.getElementById("categoryMapping");
const terminalMapping = document.getElementById("terminalMapping");

const timeStep = document.getElementById("timeStep");
const manualCarousels = document.getElementById("manualCarousels");
const terminalCarousels = document.getElementById("terminalCarousels");
const carouselList = document.getElementById("carouselList");
const terminalCarouselList = document.getElementById("terminalCarouselList");

const addCarousel = document.getElementById("addCarousel");
const addTerminalCarousel = document.getElementById("addTerminalCarousel");

const runBtn = document.getElementById("runBtn");
const runStatus = document.getElementById("runStatus");

const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");

const resultsSection = document.getElementById("resultsSection");
const kpiGrid = document.getElementById("kpiGrid");
const downloadsContainer = document.getElementById("downloads");
const warningsTable = document.getElementById("warningsTable");
const previewResultTable = document.getElementById("previewResultTable");
const newRunBtn = document.getElementById("newRunBtn");

const openDocs = document.getElementById("openDocs");
const openBaglist = document.getElementById("openBaglist");

function showStep(step) {
  currentStep = Math.max(1, Math.min(5, step));
  steps.forEach((el) => {
    const isActive = Number(el.dataset.step) === currentStep;
    el.classList.toggle("active", isActive);
  });
  stepButtons.forEach((btn) => {
    btn.classList.toggle("active", Number(btn.dataset.step) === currentStep);
  });
}

stepButtons.forEach((btn) => {
  btn.addEventListener("click", () => showStep(Number(btn.dataset.step)));
});

prevBtn.addEventListener("click", () => showStep(currentStep - 1));
nextBtn.addEventListener("click", () => showStep(currentStep + 1));

openDocs.addEventListener("click", () => {
  window.open("/docs", "_blank");
});

if (openBaglist) {
  openBaglist.addEventListener("click", () => {
    window.location.href = "/baglist";
  });
}

fileInput.addEventListener("change", (event) => {
  const file = event.target.files[0];
  state.file = file || null;
  if (file) {
    fileHint.textContent = `${file.name} (${Math.round(file.size / 1024)} KB)`;
  } else {
    fileHint.textContent = "Aucun fichier chargé.";
  }
});

previewBtn.addEventListener("click", async () => {
  if (!state.file) {
    alert("Chargez un fichier Excel.");
    return;
  }
  const formData = new FormData();
  formData.append("file", state.file);

  const res = await fetch("/api/preview", { method: "POST", body: formData });
  if (!res.ok) {
    alert("Erreur preview.");
    return;
  }
  const data = await res.json();
  state.columns = data.columns || [];
  state.preview = data.preview || [];
  state.suggested = data.suggested_mapping || {};
  renderColumns();
  renderPreviewTable(previewTable, state.preview);
  populateMappingSelects();
});

function renderColumns() {
  columnsList.innerHTML = "";
  state.columns.forEach((col) => {
    const span = document.createElement("span");
    span.textContent = col;
    columnsList.appendChild(span);
  });
}

function populateMappingSelects() {
  const selects = [mapDeparture, mapFlight, mapCategory, mapPositions, mapTerminal, mapOpening, mapClosing];
  selects.forEach((sel) => {
    sel.innerHTML = "";
    const none = document.createElement("option");
    none.value = "";
    none.textContent = "(Aucune)";
    sel.appendChild(none);
    state.columns.forEach((col) => {
      const option = document.createElement("option");
      option.value = col;
      option.textContent = col;
      sel.appendChild(option);
    });
  });

  if (state.suggested.DepartureTime) mapDeparture.value = state.suggested.DepartureTime;
  if (state.suggested.FlightNumber) mapFlight.value = state.suggested.FlightNumber;
  if (state.suggested.Category) mapCategory.value = state.suggested.Category;
  if (state.suggested.Positions) mapPositions.value = state.suggested.Positions;
  if (state.suggested.Terminal) mapTerminal.value = state.suggested.Terminal;
  if (state.suggested.MakeupOpening) mapOpening.value = state.suggested.MakeupOpening;
  if (state.suggested.MakeupClosing) mapClosing.value = state.suggested.MakeupClosing;

  [mapDeparture, mapFlight, mapCategory, mapPositions, mapTerminal, mapOpening, mapClosing].forEach((sel) => {
    sel.addEventListener("change", renderExtraCols);
  });
  renderExtraCols();
}

function renderExtraCols() {
  extraCols.innerHTML = "";
  const mapped = new Set([
    mapDeparture.value,
    mapFlight.value,
    mapCategory.value,
    mapPositions.value,
    mapTerminal.value,
    mapOpening.value,
    mapClosing.value,
  ].filter(Boolean));

  state.columns.forEach((col) => {
    if (mapped.has(col)) return;
    const span = document.createElement("span");
    span.textContent = col;
    span.classList.toggle("active", state.keepExtraCols.has(col));
    span.addEventListener("click", () => {
      if (state.keepExtraCols.has(col)) {
        state.keepExtraCols.delete(col);
      } else {
        state.keepExtraCols.add(col);
      }
      renderExtraCols();
    });
    extraCols.appendChild(span);
  });
}

inspectBtn.addEventListener("click", async () => {
  if (!state.file) {
    alert("Chargez un fichier Excel.");
    return;
  }
  const columns = collectColumnMapping();
  if (!columns) return;
  const payload = JSON.stringify({ columns });

  const formData = new FormData();
  formData.append("file", state.file);
  formData.append("config", payload);

  const res = await fetch("/api/inspect", { method: "POST", body: formData });
  if (!res.ok) {
    alert("Erreur inspect.");
    return;
  }
  const data = await res.json();
  state.categories = data.categories || [];
  state.terminals = data.terminals || [];
  renderCategoryMapping();
  renderTerminalMapping();
});

function suggestCat(value) {
  const s = String(value).trim().toLowerCase();
  if (s.includes("wide") || ["wb", "w"].includes(s)) return "Wide";
  if (s.includes("narrow") || ["nb", "n"].includes(s)) return "Narrow";
  return "IGNORER";
}

function suggestTerm(value) {
  const s = String(value).trim().toUpperCase();
  const match = s.match(/\d+/);
  if (s.startsWith("T") && match) return `T${match[0]}`;
  if (s.includes("TERMINAL") && match) return `T${match[0]}`;
  if (match && match[0].length <= 2) return `T${match[0]}`;
  return s || "INCONNU";
}

function renderCategoryMapping() {
  categoryMapping.innerHTML = "";
  state.categories.forEach((cat) => {
    const row = document.createElement("div");
    row.className = "stack-row";

    const label = document.createElement("div");
    label.textContent = cat;

    const select = document.createElement("select");
    ["Wide", "Narrow", "IGNORER"].forEach((opt) => {
      const option = document.createElement("option");
      option.value = opt;
      option.textContent = opt;
      select.appendChild(option);
    });
    const defaultValue = state.catMapping[cat] || suggestCat(cat);
    select.value = defaultValue;
    state.catMapping[cat] = defaultValue;
    select.addEventListener("change", () => {
      state.catMapping[cat] = select.value;
    });

    row.appendChild(label);
    row.appendChild(select);
    categoryMapping.appendChild(row);
  });
}

function renderTerminalMapping() {
  terminalMapping.innerHTML = "";
  state.terminals.forEach((term) => {
    const row = document.createElement("div");
    row.className = "stack-row";

    const label = document.createElement("div");
    label.textContent = term;

    const input = document.createElement("input");
    input.type = "text";
    const defaultValue = state.termMapping[term] || suggestTerm(term);
    input.value = defaultValue;
    state.termMapping[term] = defaultValue;

    const ignoreWrap = document.createElement("label");
    ignoreWrap.className = "checkbox";
    const ignore = document.createElement("input");
    ignore.type = "checkbox";
    ignoreWrap.appendChild(ignore);
    ignoreWrap.appendChild(document.createTextNode("IGNORER"));

    ignore.addEventListener("change", () => {
      if (ignore.checked) {
        input.disabled = true;
        state.termMapping[term] = "IGNORER";
      } else {
        input.disabled = false;
        state.termMapping[term] = input.value;
      }
    });

    input.addEventListener("input", () => {
      if (!ignore.checked) {
        state.termMapping[term] = input.value;
      }
    });

    row.appendChild(label);
    row.appendChild(input);
    row.appendChild(ignoreWrap);
    terminalMapping.appendChild(row);
  });
}

function renderCarouselList() {
  carouselList.innerHTML = "";
  state.carouselsManual.forEach((car, idx) => {
    const row = document.createElement("div");
    row.className = "stack-row";

    row.appendChild(makeInput("Nom", car.name, (val) => car.name = val));
    row.appendChild(makeNumber("Wide", car.wide, (val) => car.wide = val));
    row.appendChild(makeNumber("Narrow", car.narrow, (val) => car.narrow = val));

    const remove = document.createElement("button");
    remove.className = "ghost";
    remove.textContent = "Supprimer";
    remove.addEventListener("click", () => {
      state.carouselsManual.splice(idx, 1);
      renderCarouselList();
    });
    row.appendChild(remove);

    carouselList.appendChild(row);
  });
}

function renderTerminalCarouselList() {
  terminalCarouselList.innerHTML = "";
  state.carouselsTerminal.forEach((car, idx) => {
    const row = document.createElement("div");
    row.className = "stack-row";

    row.appendChild(makeInput("Terminal", car.terminal, (val) => car.terminal = val));
    row.appendChild(makeInput("Carousel", car.name, (val) => car.name = val));
    row.appendChild(makeNumber("Wide", car.wide, (val) => car.wide = val));
    row.appendChild(makeNumber("Narrow", car.narrow, (val) => car.narrow = val));

    const remove = document.createElement("button");
    remove.className = "ghost";
    remove.textContent = "Supprimer";
    remove.addEventListener("click", () => {
      state.carouselsTerminal.splice(idx, 1);
      renderTerminalCarouselList();
    });
    row.appendChild(remove);

    terminalCarouselList.appendChild(row);
  });
}

function makeInput(label, value, onChange) {
  const wrap = document.createElement("div");
  const lbl = document.createElement("label");
  lbl.textContent = label;
  const input = document.createElement("input");
  input.type = "text";
  input.value = value || "";
  input.addEventListener("input", () => onChange(input.value));
  wrap.appendChild(lbl);
  wrap.appendChild(input);
  return wrap;
}

function makeNumber(label, value, onChange) {
  const wrap = document.createElement("div");
  const lbl = document.createElement("label");
  lbl.textContent = label;
  const input = document.createElement("input");
  input.type = "number";
  input.value = value;
  input.addEventListener("input", () => onChange(Number(input.value)));
  wrap.appendChild(lbl);
  wrap.appendChild(input);
  return wrap;
}

addCarousel.addEventListener("click", () => {
  state.carouselsManual.push({ name: `Carousel ${state.carouselsManual.length + 1}`, wide: 8, narrow: 4 });
  renderCarouselList();
});

addTerminalCarousel.addEventListener("click", () => {
  state.carouselsTerminal.push({ terminal: "T1", name: `Carousel ${state.carouselsTerminal.length + 1}`, wide: 8, narrow: 4 });
  renderTerminalCarouselList();
});

const carouselsModeInputs = document.querySelectorAll("input[name='carouselsMode']");
carouselsModeInputs.forEach((input) => {
  input.addEventListener("change", () => {
    const mode = getCarouselsMode();
    manualCarousels.classList.toggle("hidden", mode !== "manual");
    terminalCarousels.classList.toggle("hidden", mode !== "file");
  });
});

function getCarouselsMode() {
  return document.querySelector("input[name='carouselsMode']:checked").value;
}

runBtn.addEventListener("click", async () => {
  if (!state.file) {
    alert("Chargez un fichier Excel.");
    return;
  }
  const config = buildRunConfig();
  if (!config) return;

  runStatus.textContent = "Exécution...";
  const formData = new FormData();
  formData.append("file", state.file);
  formData.append("config", JSON.stringify(config));

  const res = await fetch("/api/run", { method: "POST", body: formData });
  if (!res.ok) {
    const err = await res.json();
    runStatus.textContent = "Erreur.";
    alert(err.detail || "Erreur API");
    return;
  }
  const data = await res.json();
  state.job = data;
  runStatus.textContent = "Terminé.";
  renderResults(data);
  resultsSection.classList.remove("hidden");
  resultsSection.scrollIntoView({ behavior: "smooth" });
});

newRunBtn.addEventListener("click", () => {
  resultsSection.classList.add("hidden");
  showStep(1);
});

function collectColumnMapping() {
  if (!mapDeparture.value || !mapFlight.value || !mapCategory.value || !mapPositions.value) {
    alert("Mapping colonnes incomplet.");
    return null;
  }
  return {
    departure_time: mapDeparture.value,
    flight_number: mapFlight.value,
    category: mapCategory.value,
    positions: mapPositions.value,
    terminal: mapTerminal.value || null,
    makeup_opening: mapOpening.value || null,
    makeup_closing: mapClosing.value || null,
    keep_extra_cols: Array.from(state.keepExtraCols)
  };
}

function buildRunConfig() {
  const columns = collectColumnMapping();
  if (!columns) return null;
  if (!state.categories.length) {
    alert("Cliquez sur 'Analyser les valeurs' pour charger les catégories.");
    return null;
  }

  const makeupMode = document.querySelector("input[name='makeupMode']:checked").value;
  if (makeupMode === "columns" && (!columns.makeup_opening || !columns.makeup_closing)) {
    alert("Sélectionnez MakeupOpening et MakeupClosing ou passez en mode calcul.");
    return null;
  }
  const makeup = {
    mode: makeupMode,
    wide_open_min: Number(document.getElementById("wideOpen").value || 120),
    wide_close_min: Number(document.getElementById("wideClose").value || 60),
    narrow_open_min: Number(document.getElementById("narrowOpen").value || 90),
    narrow_close_min: Number(document.getElementById("narrowClose").value || 45)
  };

  const mapping = {
    categories: state.categories.reduce((acc, cat) => {
      acc[cat] = state.catMapping[cat] || suggestCat(cat);
      return acc;
    }, {}),
    terminals: state.terminals.reduce((acc, term) => {
      acc[term] = state.termMapping[term] || suggestTerm(term);
      return acc;
    }, {})
  };

  const carouselsMode = getCarouselsMode();
  const carousels = {
    mode: carouselsMode,
    manual: {},
    by_terminal: {}
  };

  if (carouselsMode === "manual") {
    if (!state.carouselsManual.length) {
      alert("Ajoutez au moins un carrousel manuel.");
      return null;
    }
    state.carouselsManual.forEach((car) => {
      carousels.manual[car.name] = { wide: Number(car.wide), narrow: Number(car.narrow) };
    });
  } else {
    if (!columns.terminal) {
      alert("Le mode carrousels par terminal requiert la colonne Terminal.");
      return null;
    }
    if (!state.carouselsTerminal.length) {
      alert("Ajoutez au moins un carrousel par terminal.");
      return null;
    }
    state.carouselsTerminal.forEach((car) => {
      if (!carousels.by_terminal[car.terminal]) {
        carousels.by_terminal[car.terminal] = {};
      }
      carousels.by_terminal[car.terminal][car.name] = { wide: Number(car.wide), narrow: Number(car.narrow) };
    });
  }

  const rules = {
    apply_readjustment: document.getElementById("applyReadjustment").checked,
    rule_multi: document.getElementById("ruleMulti").checked,
    rule_narrow_wide: document.getElementById("ruleNarrowWide").checked,
    rule_extras: document.getElementById("ruleExtras").checked,
    max_carousels_narrow: Number(document.getElementById("maxCarouselsNarrow").value || 3),
    max_carousels_wide: Number(document.getElementById("maxCarouselsWide").value || 2),
    rule_order: []
  };

  const order = [];
  if (rules.rule_multi) order.push("multi");
  if (rules.rule_narrow_wide) order.push("narrow_wide");
  if (rules.rule_extras) order.push("extras");
  rules.rule_order = order;

  const extras = {
    by_terminal: {
      ALL: {
        wide: Number(document.getElementById("extraWide").value || 8),
        narrow: Number(document.getElementById("extraNarrow").value || 4)
      }
    }
  };

  const colors = {
    color_mode: "category",
    wide_color: document.getElementById("wideColor").value,
    narrow_color: document.getElementById("narrowColor").value,
    split_color: document.getElementById("splitColor").value,
    narrow_wide_color: document.getElementById("narrowWideColor").value
  };

  return {
    columns,
    mapping,
    makeup,
    time_step_minutes: Number(timeStep.value || 5),
    carousels,
    rules,
    extras,
    colors
  };
}

function renderPreviewTable(table, rows) {
  const thead = table.querySelector("thead");
  const tbody = table.querySelector("tbody");
  thead.innerHTML = "";
  tbody.innerHTML = "";
  if (!rows || rows.length === 0) return;

  const columns = Object.keys(rows[0]);
  const headRow = document.createElement("tr");
  columns.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    columns.forEach((col) => {
      const td = document.createElement("td");
      td.textContent = row[col];
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

function renderResults(data) {
  renderKpis(data.kpis || {});
  renderWarnings(data.warnings || []);
  renderDownloads(data.downloads || {});
  renderCharts(data.kpis || {});
  if (data.job_id) {
    loadPreview(data.job_id);
  }
}

function renderKpis(kpis) {
  kpiGrid.innerHTML = "";
  const items = [
    { label: "Total vols", value: kpis.total_flights },
    { label: "% assignés", value: `${kpis.assigned_pct || 0}%` },
    { label: "UNASSIGNED", value: kpis.unassigned_count },
    { label: "Split", value: kpis.split_count },
    { label: "% Split", value: `${kpis.split_pct || 0}%` },
    { label: "Narrow -> Wide", value: kpis.narrow_wide_count },
  ];

  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "kpi-card";
    const title = document.createElement("div");
    title.className = "kpi-title";
    title.textContent = item.label;
    const value = document.createElement("div");
    value.className = "kpi-value";
    value.textContent = item.value ?? "-";
    card.appendChild(title);
    card.appendChild(value);
    kpiGrid.appendChild(card);
  });
}

function renderDownloads(downloads) {
  downloadsContainer.innerHTML = "";
  Object.entries(downloads).forEach(([key, url]) => {
    const link = document.createElement("a");
    link.href = url;
    link.textContent = key;
    link.setAttribute("download", "");
    downloadsContainer.appendChild(link);
  });
}

function renderWarnings(warnings) {
  renderPreviewTable(warningsTable, warnings);
}

async function loadPreview(jobId) {
  const res = await fetch(`/api/jobs/${jobId}/preview/summary_readjusted.csv?limit=20`);
  if (!res.ok) return;
  const data = await res.json();
  renderPreviewTable(previewResultTable, data.rows || []);
}

function renderCharts(kpis) {
  const assignedCtx = document.getElementById("assignedChart");
  const rulesCtx = document.getElementById("rulesChart");

  if (state.charts.assigned) state.charts.assigned.destroy();
  if (state.charts.rules) state.charts.rules.destroy();

  const assigned = (kpis.total_flights || 0) - (kpis.unassigned_count || 0);
  const unassigned = kpis.unassigned_count || 0;

  state.charts.assigned = new Chart(assignedCtx, {
    type: "doughnut",
    data: {
      labels: ["Assignés", "Unassigned"],
      datasets: [{
        data: [assigned, unassigned],
        backgroundColor: ["#38bdf8", "#f97316"]
      }]
    },
    options: {
      plugins: { legend: { position: "bottom" } }
    }
  });

  state.charts.rules = new Chart(rulesCtx, {
    type: "bar",
    data: {
      labels: ["Split", "Narrow -> Wide"],
      datasets: [{
        label: "Vols",
        data: [kpis.split_count || 0, kpis.narrow_wide_count || 0],
        backgroundColor: ["#0ea5e9", "#f59e0b"]
      }]
    },
    options: {
      plugins: { legend: { display: false } }
    }
  });
}

showStep(1);
renderCarouselList();
renderTerminalCarouselList();
