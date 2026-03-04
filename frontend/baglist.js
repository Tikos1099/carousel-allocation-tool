const state = {
  step: 1,
  files: {
    bags: null,
    allocation: null,
    transfers: null,
  },
  preview: {
    bags: { columns: [], preview: [] },
    allocation: { columns: [], preview: [] },
    transfers: { columns: [], preview: [] },
  },
  template: [],
  lastJobId: null,
};

const STORAGE_KEY = "baglist_builder_state_v1";

const stepButtons = Array.from(document.querySelectorAll("#baglistStepper button"));
const steps = Array.from(document.querySelectorAll(".step"));
const prevBtn = document.getElementById("baglistPrevBtn");
const nextBtn = document.getElementById("baglistNextBtn");

const bagsFileInput = document.getElementById("bagsFile");
const allocationFileInput = document.getElementById("allocationFile");
const transfersFileInput = document.getElementById("transfersFile");

const bagsHint = document.getElementById("bagsHint");
const allocationHint = document.getElementById("allocationHint");
const transfersHint = document.getElementById("transfersHint");
const previewStatus = document.getElementById("previewStatus");

const previewBtn = document.getElementById("previewBaglistBtn");
const bagsColumns = document.getElementById("bagsColumns");
const allocationColumns = document.getElementById("allocationColumns");
const transfersColumns = document.getElementById("transfersColumns");

const bagsPreviewTable = document.getElementById("bagsPreviewTable");
const allocationPreviewTable = document.getElementById("allocationPreviewTable");
const transfersPreviewTable = document.getElementById("transfersPreviewTable");

const templateList = document.getElementById("templateList");
const addColumnBtn = document.getElementById("addColumnBtn");
const runBtn = document.getElementById("runBaglistBtn");
const runStatus = document.getElementById("runBaglistStatus");

const exportProfileBtn = document.getElementById("exportProfileBtn");
const importProfileInput = document.getElementById("importProfileInput");

const resultsSection = document.getElementById("baglistResults");
const kpiGrid = document.getElementById("baglistKpis");
const downloadsContainer = document.getElementById("baglistDownloads");
const warningsTable = document.getElementById("baglistWarningsTable");
const previewResultTable = document.getElementById("baglistPreviewTable");

const openDocs = document.getElementById("openDocs");
const openMain = document.getElementById("openMain");

const datalistIds = {
  bags: "bagsFieldsList",
  allocation: "allocationFieldsList",
  transfers: "transfersFieldsList",
};

function ensureDatalist(id) {
  let list = document.getElementById(id);
  if (!list) {
    list = document.createElement("datalist");
    list.id = id;
    document.body.appendChild(list);
  }
  return list;
}

function updateDatalist(id, items) {
  const list = ensureDatalist(id);
  list.innerHTML = "";
  items.forEach((item) => {
    const option = document.createElement("option");
    option.value = item;
    list.appendChild(option);
  });
}

function saveState() {
  const payload = {
    step: state.step,
    template: state.template,
    lastJobId: state.lastJobId,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function loadState() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return;
  try {
    const payload = JSON.parse(raw);
    state.step = payload.step || 1;
    state.template = Array.isArray(payload.template) ? payload.template : [];
    state.lastJobId = payload.lastJobId || null;
  } catch (err) {
    console.warn("State load failed", err);
  }
}

function showStep(step) {
  const safeStep = Math.max(1, Math.min(3, step));
  state.step = safeStep;
  steps.forEach((el) => {
    el.classList.toggle("active", Number(el.dataset.step) === safeStep);
  });
  stepButtons.forEach((btn) => {
    btn.classList.toggle("active", Number(btn.dataset.step) === safeStep);
  });
  saveState();
}

stepButtons.forEach((btn) => {
  btn.addEventListener("click", () => showStep(Number(btn.dataset.step)));
});

prevBtn.addEventListener("click", () => showStep(state.step - 1));
nextBtn.addEventListener("click", () => showStep(state.step + 1));

openDocs.addEventListener("click", () => {
  window.open("/docs", "_blank");
});

openMain.addEventListener("click", () => {
  window.location.href = "/app";
});

function updateFileHint(input, hintEl, targetKey) {
  const file = input.files[0] || null;
  state.files[targetKey] = file;
  if (file) {
    hintEl.textContent = `${file.name} (${Math.round(file.size / 1024)} KB)`;
  } else {
    hintEl.textContent = "Aucun fichier chargé.";
  }
}

bagsFileInput.addEventListener("change", () => updateFileHint(bagsFileInput, bagsHint, "bags"));
allocationFileInput.addEventListener("change", () => updateFileHint(allocationFileInput, allocationHint, "allocation"));
transfersFileInput.addEventListener("change", () => updateFileHint(transfersFileInput, transfersHint, "transfers"));

function renderTags(container, items) {
  container.innerHTML = "";
  items.forEach((item) => {
    const span = document.createElement("span");
    span.textContent = item;
    container.appendChild(span);
  });
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

previewBtn.addEventListener("click", async () => {
  if (!state.files.bags) {
    alert("Chargez un bags_file.");
    return;
  }
  previewStatus.textContent = "Prévisualisation...";
  const formData = new FormData();
  formData.append("bags_file", state.files.bags);
  if (state.files.allocation) formData.append("allocation_file", state.files.allocation);
  if (state.files.transfers) formData.append("transfers_file", state.files.transfers);

  const res = await fetch("/api/baglist/preview", { method: "POST", body: formData });
  if (!res.ok) {
    previewStatus.textContent = "Erreur.";
    alert("Erreur preview baglist.");
    return;
  }
  const data = await res.json();
  state.preview = data;
  renderTags(bagsColumns, data.bags.columns || []);
  renderTags(allocationColumns, data.allocation.columns || []);
  renderTags(transfersColumns, data.transfers.columns || []);
  renderPreviewTable(bagsPreviewTable, data.bags.preview || []);
  renderPreviewTable(allocationPreviewTable, data.allocation.preview || []);
  renderPreviewTable(transfersPreviewTable, data.transfers.preview || []);
  updateDatalist(datalistIds.bags, data.bags.columns || []);
  updateDatalist(datalistIds.allocation, data.allocation.columns || []);
  updateDatalist(datalistIds.transfers, data.transfers.columns || []);
  previewStatus.textContent = "Prévisualisation chargée.";
  showStep(2);
});

function makeId() {
  return `col_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function createColumnConfig() {
  return {
    id: makeId(),
    output_column: "",
    type: "copy",
    field: "",
    value: "",
    source: "allocation",
    join_left_key: "",
    join_right_key: "",
    strategy: "first",
    default: "",
    expression: "",
    format: "none",
    format_custom: "",
  };
}

function updateColumn(idx, patch) {
  state.template[idx] = { ...state.template[idx], ...patch };
  saveState();
  renderTemplateList();
}

function renderTemplateList() {
  templateList.innerHTML = "";
  if (!state.template.length) {
    const empty = document.createElement("div");
    empty.className = "builder-empty";
    empty.textContent = "Ajoutez une colonne pour commencer.";
    templateList.appendChild(empty);
    return;
  }

  state.template.forEach((col, idx) => {
    const row = document.createElement("div");
    row.className = "builder-row";
    row.draggable = true;
    row.dataset.index = idx;

    row.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData("text/plain", String(idx));
      row.classList.add("dragging");
    });
    row.addEventListener("dragend", () => row.classList.remove("dragging"));
    row.addEventListener("dragover", (event) => event.preventDefault());
    row.addEventListener("drop", (event) => {
      event.preventDefault();
      const from = Number(event.dataTransfer.getData("text/plain"));
      if (Number.isNaN(from) || from === idx) return;
      const moved = state.template.splice(from, 1)[0];
      state.template.splice(idx, 0, moved);
      saveState();
      renderTemplateList();
    });

    const handle = document.createElement("div");
    handle.className = "builder-handle";
    handle.textContent = "↕";

    const outputInput = document.createElement("input");
    outputInput.type = "text";
    outputInput.placeholder = "Nom colonne output";
    outputInput.value = col.output_column;
    outputInput.addEventListener("input", (event) => updateColumn(idx, { output_column: event.target.value }));

    const typeSelect = document.createElement("select");
    ["copy", "const", "lookup", "formula", "format"].forEach((type) => {
      const option = document.createElement("option");
      option.value = type;
      option.textContent = type;
      typeSelect.appendChild(option);
    });
    typeSelect.value = col.type;
    typeSelect.addEventListener("change", (event) => {
      const nextType = event.target.value;
      const patch = { type: nextType };
      if (nextType === "lookup") {
        patch.source = col.source || "allocation";
        if (!col.join_left_key) {
          patch.join_left_key = patch.source === "allocation" ? "DepFlightId" : "ArrFlightId";
          patch.join_right_key = patch.join_left_key;
        }
      }
      updateColumn(idx, patch);
    });

    const fields = document.createElement("div");
    fields.className = "builder-fields";

    if (col.type === "copy" || col.type === "format") {
      const fieldInput = document.createElement("input");
      fieldInput.type = "text";
      fieldInput.placeholder = "Champ source (bags)";
      fieldInput.value = col.field;
      fieldInput.setAttribute("list", datalistIds.bags);
      fieldInput.addEventListener("input", (event) => updateColumn(idx, { field: event.target.value }));
      fields.appendChild(wrapField("field", fieldInput));
    }

    if (col.type === "const") {
      const valueInput = document.createElement("input");
      valueInput.type = "text";
      valueInput.placeholder = "Valeur constante";
      valueInput.value = col.value;
      valueInput.addEventListener("input", (event) => updateColumn(idx, { value: event.target.value }));
      fields.appendChild(wrapField("value", valueInput));
    }

    if (col.type === "lookup") {
      const sourceSelect = document.createElement("select");
      ["allocation", "transfers"].forEach((src) => {
        const option = document.createElement("option");
        option.value = src;
        option.textContent = src;
        sourceSelect.appendChild(option);
      });
      sourceSelect.value = col.source || "allocation";
      sourceSelect.addEventListener("change", (event) => {
        const source = event.target.value;
        updateColumn(idx, {
          source,
          join_left_key: source === "allocation" ? "DepFlightId" : "ArrFlightId",
          join_right_key: source === "allocation" ? "DepFlightId" : "ArrFlightId",
        });
      });
      fields.appendChild(wrapField("source", sourceSelect));

      const fieldInput = document.createElement("input");
      fieldInput.type = "text";
      fieldInput.placeholder = "Champ lookup";
      fieldInput.value = col.field;
      fieldInput.setAttribute("list", col.source === "transfers" ? datalistIds.transfers : datalistIds.allocation);
      fieldInput.addEventListener("input", (event) => updateColumn(idx, { field: event.target.value }));
      fields.appendChild(wrapField("field", fieldInput));

      const leftKeyInput = document.createElement("input");
      leftKeyInput.type = "text";
      leftKeyInput.placeholder = "left_key (bags)";
      leftKeyInput.value = col.join_left_key;
      leftKeyInput.setAttribute("list", datalistIds.bags);
      leftKeyInput.addEventListener("input", (event) => updateColumn(idx, { join_left_key: event.target.value }));
      fields.appendChild(wrapField("left_key", leftKeyInput));

      const rightKeyInput = document.createElement("input");
      rightKeyInput.type = "text";
      rightKeyInput.placeholder = "right_key";
      rightKeyInput.value = col.join_right_key;
      rightKeyInput.addEventListener("input", (event) => updateColumn(idx, { join_right_key: event.target.value }));
      fields.appendChild(wrapField("right_key", rightKeyInput));

      const defaultInput = document.createElement("input");
      defaultInput.type = "text";
      defaultInput.placeholder = "default";
      defaultInput.value = col.default;
      defaultInput.addEventListener("input", (event) => updateColumn(idx, { default: event.target.value }));
      fields.appendChild(wrapField("default", defaultInput));

      const strategySelect = document.createElement("select");
      ["first", "error"].forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        strategySelect.appendChild(option);
      });
      strategySelect.value = col.strategy || "first";
      strategySelect.addEventListener("change", (event) => updateColumn(idx, { strategy: event.target.value }));
      fields.appendChild(wrapField("strategy", strategySelect));
    }

    if (col.type === "formula") {
      const exprInput = document.createElement("input");
      exprInput.type = "text";
      exprInput.placeholder = "Expression (ex: minutes(to_datetime(InputDay, UnloadTime)))";
      exprInput.value = col.expression;
      exprInput.addEventListener("input", (event) => updateColumn(idx, { expression: event.target.value }));
      fields.appendChild(wrapField("expression", exprInput));
    }

    const formatSelect = document.createElement("select");
    ["none", "datetime", "date", "time", "number", "int", "text", "bool", "minutes", "custom"].forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      formatSelect.appendChild(option);
    });
    formatSelect.value = col.format || "none";
    formatSelect.addEventListener("change", (event) => updateColumn(idx, { format: event.target.value }));
    fields.appendChild(wrapField("format", formatSelect));

    if (col.format === "custom") {
      const fmtInput = document.createElement("input");
      fmtInput.type = "text";
      fmtInput.placeholder = "Format Excel (ex: DD/MM/YY HH:MM)";
      fmtInput.value = col.format_custom;
      fmtInput.addEventListener("input", (event) => updateColumn(idx, { format_custom: event.target.value }));
      fields.appendChild(wrapField("custom", fmtInput));
    }

    const actions = document.createElement("div");
    actions.className = "builder-row-actions";
    const duplicateBtn = document.createElement("button");
    duplicateBtn.className = "ghost";
    duplicateBtn.textContent = "Dupliquer";
    duplicateBtn.addEventListener("click", () => {
      const copy = { ...col, id: makeId() };
      state.template.splice(idx + 1, 0, copy);
      saveState();
      renderTemplateList();
    });
    const removeBtn = document.createElement("button");
    removeBtn.className = "ghost";
    removeBtn.textContent = "Supprimer";
    removeBtn.addEventListener("click", () => {
      state.template.splice(idx, 1);
      saveState();
      renderTemplateList();
    });
    actions.appendChild(duplicateBtn);
    actions.appendChild(removeBtn);

    row.appendChild(handle);
    row.appendChild(outputInput);
    row.appendChild(typeSelect);
    row.appendChild(fields);
    row.appendChild(actions);
    templateList.appendChild(row);
  });
}

function wrapField(label, input) {
  const wrap = document.createElement("div");
  wrap.className = "builder-field";
  const lbl = document.createElement("label");
  lbl.textContent = label;
  wrap.appendChild(lbl);
  wrap.appendChild(input);
  return wrap;
}

addColumnBtn.addEventListener("click", () => {
  state.template.push(createColumnConfig());
  saveState();
  renderTemplateList();
});

exportProfileBtn.addEventListener("click", () => {
  const payload = {
    columns: state.template,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "baglist_profile.json";
  link.click();
  URL.revokeObjectURL(url);
});

importProfileInput.addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    const text = await file.text();
    const payload = JSON.parse(text);
    if (Array.isArray(payload.columns)) {
      state.template = payload.columns.map((col) => ({ id: makeId(), ...col }));
      saveState();
      renderTemplateList();
    } else {
      alert("Profil invalide.");
    }
  } catch (err) {
    alert("Erreur lecture profil.");
  } finally {
    importProfileInput.value = "";
  }
});

function buildConfig() {
  return {
    columns: state.template.map((col) => {
      const cfg = {
        output_column: col.output_column,
        type: col.type,
      };
      if (col.type === "copy" || col.type === "format") {
        cfg.field = col.field;
      }
      if (col.type === "const") {
        cfg.value = col.value;
      }
      if (col.type === "lookup") {
        cfg.source = col.source || "allocation";
        cfg.field = col.field;
        cfg.default = col.default;
        cfg.join = {
          left_key: col.join_left_key,
          right_key: col.join_right_key,
          strategy: col.strategy || "first",
        };
      }
      if (col.type === "formula") {
        cfg.expression = col.expression;
      }
      if (col.format && col.format !== "none") {
        cfg.format = col.format === "custom" ? col.format_custom : col.format;
      }
      return cfg;
    }),
  };
}

function renderKpis(kpis) {
  kpiGrid.innerHTML = "";
  const items = [
    { label: "Rows in", value: kpis.rows_in },
    { label: "Rows out", value: kpis.rows_out },
    { label: "Warnings", value: kpis.warnings_count },
    { label: "Missing DepFlightId", value: kpis.missing_depflightid },
    { label: "Missing ArrFlightId", value: kpis.missing_arrflightid },
    { label: "Alloc not found", value: kpis.allocation_not_found },
    { label: "Transfers not found", value: kpis.transfers_not_found },
    { label: "Alloc duplicates", value: kpis.allocation_duplicates },
    { label: "Transfers duplicates", value: kpis.transfers_duplicates },
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
  Object.entries(downloads || {}).forEach(([key, url]) => {
    const link = document.createElement("a");
    link.href = url;
    link.textContent = key;
    link.setAttribute("download", "");
    downloadsContainer.appendChild(link);
  });
}

async function loadJob(jobId) {
  const res = await fetch(`/api/baglist/jobs/${jobId}`);
  if (!res.ok) {
    alert("Job baglist introuvable.");
    return;
  }
  const data = await res.json();
  renderKpis(data.kpis || {});
  renderDownloads(data.downloads || {});
  renderPreviewTable(warningsTable, data.warnings_sample || []);
  renderPreviewTable(previewResultTable, data.preview_rows || []);
  resultsSection.classList.remove("hidden");
  showStep(3);
}

runBtn.addEventListener("click", async () => {
  if (!state.files.bags) {
    alert("Chargez un bags_file.");
    return;
  }
  if (!state.template.length) {
    alert("Ajoutez au moins une colonne.");
    return;
  }
  const config = buildConfig();
  runStatus.textContent = "Exécution...";
  const formData = new FormData();
  formData.append("bags_file", state.files.bags);
  if (state.files.allocation) formData.append("allocation_file", state.files.allocation);
  if (state.files.transfers) formData.append("transfers_file", state.files.transfers);
  formData.append("config_json", JSON.stringify(config));

  const res = await fetch("/api/baglist/run", { method: "POST", body: formData });
  if (!res.ok) {
    const err = await res.json();
    runStatus.textContent = "Erreur.";
    alert(err.detail || "Erreur baglist.");
    return;
  }
  const data = await res.json();
  runStatus.textContent = "Terminé.";
  state.lastJobId = data.job_id;
  saveState();
  history.pushState({}, "", `/baglist/results/${data.job_id}`);
  renderKpis(data.kpis || {});
  renderDownloads(data.downloads || {});
  renderPreviewTable(warningsTable, data.warnings_sample || []);
  renderPreviewTable(previewResultTable, data.preview_rows || []);
  showStep(3);
});

loadState();
renderTemplateList();
showStep(state.step || 1);

const pathParts = window.location.pathname.split("/").filter(Boolean);
if (pathParts.length >= 3 && pathParts[0] === "baglist" && pathParts[1] === "results") {
  const jobId = pathParts[2];
  if (jobId) {
    loadJob(jobId);
  }
}
