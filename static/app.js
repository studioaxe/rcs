// ======================================================================
// Rental Calendar Sync 4.0 - Frontend JS
// ======================================================================

const API = {
  async get(url) {
    const res = await fetch(url, { credentials: "include" });
    let data = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    if (!res.ok) {
      const msg =
        (data && (data.message || data.error)) || `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return data;
  },

  async post(url, body = null) {
    const options = {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
    };
    if (body) options.body = JSON.stringify(body);
    const res = await fetch(url, options);
    let data = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    if (!res.ok) {
      const msg =
        (data && (data.message || data.error)) || `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return data;
  },
};

// Helpers de DOM
const $ = (sel) => document.querySelector(sel);
const $all = (sel) => document.querySelectorAll(sel);

function show(el) {
  if (typeof el === "string") el = $(el);
  if (el) el.classList.remove("d-none");
}

function hide(el) {
  if (typeof el === "string") el = $(el);
  if (el) el.classList.add("d-none");
}

function setText(sel, text) {
  const el = typeof sel === "string" ? $(sel) : sel;
  if (el) el.textContent = text;
}

function setHTML(sel, html) {
  const el = typeof sel === "string" ? $(sel) : sel;
  if (el) el.innerHTML = html;
}

function statusMessage(type, text) {
  const cls =
    type === "success"
      ? "status success"
      : type === "error"
      ? "status error"
      : "status info";
  return `<div class="${cls}">${text}</div>`;
}

// Tema
const Theme = {
  init() {
    const stored = localStorage.getItem("rc_theme");
    if (stored === "dark") {
      document.body.classList.add("theme-dark");
    } else if (stored === "light") {
      document.body.classList.remove("theme-dark");
    }
  },
  toggle() {
    const isDark = document.body.classList.toggle("theme-dark");
    localStorage.setItem("rc_theme", isDark ? "dark" : "light");
  },
};

// Estado
const state = {
  authenticated: false,
  username: null,
};

// ----------------------------------------------------------------------
// Autenticação
// ----------------------------------------------------------------------

async function checkAuth() {
  try {
    const data = await API.get("/api/auth/status");
    state.authenticated = !!data.authenticated;
    state.username = data.username || null;
    updateView();
  } catch {
    state.authenticated = false;
    state.username = null;
    updateView();
  }
}

async function performLogin(username, password) {
  const formData = new FormData();
  formData.append("username", username);
  formData.append("password", password);

  const res = await fetch("/login", {
    method: "POST",
    body: formData,
    credentials: "include",
  });

  if (res.status === 401) {
    throw new Error("Utilizador ou password incorretos");
  }
  if (!res.ok) {
    throw new Error(`Erro de login (HTTP ${res.status})`);
  }
}

// ----------------------------------------------------------------------
// UI / Navegação
// ----------------------------------------------------------------------

function updateView() {
  const loginView = $("#login-view");
  const dashView = $("#dashboard-view");

  if (!loginView || !dashView) return;

  if (state.authenticated) {
    loginView.classList.add("d-none");
    dashView.classList.remove("d-none");
    setText(
      "#user-label",
      state.username ? `Utilizador: ${state.username}` : ""
    );
  } else {
    dashView.classList.add("d-none");
    loginView.classList.remove("d-none");
  }
}

// ----------------------------------------------------------------------
// Bindings principais
// ----------------------------------------------------------------------

function bindLoginForm() {
  const form = $("#login-form");
  if (!form) return;
  const errorBox = $("#login-error");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (errorBox) hide(errorBox);

    const username = $("#login-username")?.value.trim();
    const password = $("#login-password")?.value;

    if (!username || !password) {
      if (errorBox) {
        errorBox.textContent = "Preencha utilizador e palavra-passe.";
        show(errorBox);
      }
      return;
    }

    try {
      await performLogin(username, password);
      await checkAuth();
      if (state.authenticated) {
        await loadEnvironmentBadge();
        await refreshFileStatus();
        await refreshCounts();
      }
    } catch (err) {
      if (errorBox) {
        errorBox.textContent = err.message || "Erro ao autenticar.";
        show(errorBox);
      }
    }
  });
}

function bindLogout() {
  const btn = $("#logout-btn");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    await fetch("/logout", { credentials: "include" });
    state.authenticated = false;
    state.username = null;
    updateView();
  });
}

function bindThemeToggle() {
  const btn = $("#theme-toggle");
  if (!btn) return;
  btn.addEventListener("click", () => Theme.toggle());
}

function bindSyncButton() {
  const btn = $("#sync-btn");
  const spinner = $("#sync-spinner");
  const label = $("#sync-btn-label");
  const statusBox = $("#sync-status");
  if (!btn || !spinner || !label || !statusBox) return;

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    show(spinner);
    label.textContent = "A sincronizar...";
    setHTML(
      statusBox,
      statusMessage("info", "Sincronização em curso...")
    );

    try {
      const data = await API.post("/api/calendar/sync-local");
      if (data.status === "success") {
        setHTML(
          statusBox,
          statusMessage(
            "success",
            `Sincronização concluída. Eventos: ${
              data.events_downloaded ?? "-"
            }`
          )
        );
      } else {
        setHTML(
          statusBox,
          statusMessage(
            "error",
            data.message || "Falha na sincronização."
          )
        );
      }
      await refreshFileStatus();
      await refreshCounts();
    } catch (err) {
      setHTML(
        statusBox,
        statusMessage(
          "error",
          `Erro na sincronização: ${err.message}`
        )
      );
    } finally {
      btn.disabled = false;
      hide(spinner);
      label.textContent = "Sincronizar Calendários (Render)";
    }
  });
}

function bindLoadCalendarsButton() {
  const btn = $("#load-calendars-btn");
  if (!btn) return;
  btn.addEventListener("click", refreshCounts);
}

function bindExportButtons() {
  $all("[data-export]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const type = btn.getAttribute("data-export");
      if (!type) return;
      window.location.href = `/api/calendar/export?type=${encodeURIComponent(
        type
      )}`;
    });
  });
}

// Botão “Forçar Full Auto (GitHub)” com melhor feedback
let pollInterval = null;

function bindFullAutoButton() {
  const btn = $("#full-auto-btn");
  const statusBox = $("#full-auto-status");
  if (!btn || !statusBox) return;

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    setHTML(
      statusBox,
      statusMessage(
        "info",
        "⏳ A disparar workflow GitHub... (aguarde ~1-2 min)"
      )
    );

    try {
      const data = await API.post("/api/full-auto/trigger");

      if (data.status === "success") {
        setHTML(
          statusBox,
          statusMessage(
            "success",
            `✅ ${
              data.message || "Workflow disparado!"
            }\nDisparado por: ${
              data.triggered_by
            }\nHora: ${new Date().toLocaleString("pt-PT")}`
          )
        );

        // Placeholder: neste momento só informa; polling real exigiria endpoint extra
        pollWorkflowStatus();
      } else {
        setHTML(
          statusBox,
          statusMessage(
            "error",
            `❌ Erro: ${
              data.message || "Falha ao disparar workflow"
            }`
          )
        );
      }
    } catch (err) {
      setHTML(
        statusBox,
        statusMessage(
          "error",
          `❌ Erro na chamada: ${err.message}`
        )
      );
    } finally {
      btn.disabled = false;
    }
  });
}

// Polling (apenas informativo por agora)
async function pollWorkflowStatus() {
  const msg =
    "💡 Dica: pode acompanhar a execução em GitHub → Actions do repositório.";
  console.log(msg);
  // Endpoint /api/workflow/status pode ser adicionado futuramente
}

// ----------------------------------------------------------------------
// Dados / Atualizações
// ----------------------------------------------------------------------

async function loadEnvironmentBadge() {
  const badge = $("#env-badge");
  if (!badge) return;
  try {
    const data = await API.get("/api/health");
    const env = (data.environment || "").toLowerCase();
    if (env === "production") {
      badge.textContent = "PROD";
      badge.classList.add("badge-danger");
    } else if (env === "testing") {
      badge.textContent = "TEST";
      badge.classList.add("badge-warning");
    } else {
      badge.textContent = "DEV";
      badge.classList.add("badge-success");
    }
  } catch {
    // ignore
  }
}

async function refreshFileStatus() {
  try {
    const data = await API.get("/api/calendar/status");
    const files = data.files || {};
    let html = "";

    Object.entries(files).forEach(([key, info]) => {
      const exists = info.exists;
      const size = exists ? (info.size_kb || 0) + " KB" : "-";
      html += `
        <div class="file-item">
          <div class="file-name">${key}</div>
          <div class="file-status-pill ${exists ? "ok" : "missing"}">
            ${exists ? "Existe" : "Não existe"}
          </div>
          <div class="file-size">${size}</div>
        </div>
      `;
    });

    setHTML("#files-status", html || "<p>Nenhum ficheiro encontrado.</p>");
  } catch (err) {
    setHTML(
      "#files-status",
      `<p class="text-error">Erro ao carregar estado dos ficheiros: ${err.message}</p>`
    );
  }
}

async function refreshCounts() {
  try {
    const [imp, mas, man] = await Promise.all([
      API.get("/api/calendar/import").catch(() => null),
      API.get("/api/calendar/master").catch(() => null),
      API.get("/api/calendar/manual").catch(() => null),
    ]);

    setText(
      "#stat-import",
      imp && typeof imp.count === "number" ? imp.count : "-"
    );
    setText(
      "#stat-master",
      mas && typeof mas.count === "number" ? mas.count : "-"
    );
    setText(
      "#stat-manual",
      man && typeof man.count === "number" ? man.count : "-"
    );
  } catch {
    setText("#stat-import", "-");
    setText("#stat-master", "-");
    setText("#stat-manual", "-");
  }
}

// ----------------------------------------------------------------------
// Inicialização
// ----------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", async () => {
  Theme.init();
  bindLoginForm();
  bindLogout();
  bindThemeToggle();
  bindSyncButton();
  bindLoadCalendarsButton();
  bindExportButtons();
  bindFullAutoButton();
  await checkAuth();
  if (state.authenticated) {
    await loadEnvironmentBadge();
    await refreshFileStatus();
    await refreshCounts();
  }
});
