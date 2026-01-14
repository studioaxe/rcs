// ======================================================================
// Rental Calendar Sync v3.2.4 FINAL PATCH - Dashboard JS
// ======================================================================

console.log('%c🎯 Rental Calendar Sync v3.2.4 FINAL PATCH', 'color: #667eea; font-weight: bold; font-size: 14px;');
console.log('%cDashboard Frontend v3.2.4', 'color: #764ba2; font-size: 12px;');

// ======================================================================
// API HELPER
// ======================================================================

const API = {
    async get(url) {
        const res = await fetch(url, { credentials: 'include' });
        let data = null;
        try {
            data = await res.json();
        } catch {
            data = null;
        }
        if (!res.ok) {
            const msg = (data && (data.message || data.error)) || `HTTP ${res.status}`;
            throw new Error(msg);
        }
        return data;
    },

    async post(url, body = null) {
        const options = {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
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
            const msg = (data && (data.message || data.error)) || `HTTP ${res.status}`;
            throw new Error(msg);
        }
        return data;
    },
};

// ======================================================================
// DOM HELPERS
// ======================================================================

const $ = (sel) => document.querySelector(sel);
const $all = (sel) => document.querySelectorAll(sel);

function show(el) {
    if (typeof el === 'string') el = $(el);
    if (el) el.classList.add('active');
}

function hide(el) {
    if (typeof el === 'string') el = $(el);
    if (el) el.classList.remove('active');
}

function setText(sel, text) {
    const el = typeof sel === 'string' ? $(sel) : sel;
    if (el) el.textContent = text;
}

// ======================================================================
// STATE
// ======================================================================

const state = {
    authenticated: false,
    user: null,
};

// ======================================================================
// AUTHENTICATION
// ======================================================================

async function checkAuth() {
    try {
        const data = await API.get('/api/auth/check');
        state.authenticated = true;
        state.user = data.user;
        showView('dashboard-view');
        setText('#current-user', data.user);
    } catch {
        state.authenticated = false;
        showView('login-view');
    }
}

function showView(viewId) {
    $all('.view').forEach((v) => v.classList.remove('active'));
    const view = $(viewId);
    if (view) view.classList.add('active');
}

// ======================================================================
// LOGIN
// ======================================================================

function bindLoginForm() {
    const form = $('#login-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = $('#username').value.trim();
        const password = $('#password').value;

        if (!username || !password) {
            showAlert('Por favor preencha os campos', 'error');
            return;
        }

        const btn = form.querySelector('button[type="submit"]');
        btn.disabled = true;

        try {
            await API.post('/api/auth/login', { username, password });
            state.authenticated = true;
            state.user = username;
            showView('dashboard-view');
            form.reset();
            
            await loadDashboard();
        } catch (err) {
            showAlert('Erro: ' + err.message, 'error');
        } finally {
            btn.disabled = false;
        }
    });
}

function bindLogout() {
    const btn = $('#logout-btn');
    if (!btn) return;

    btn.addEventListener('click', async () => {
        try {
            await API.post('/api/auth/logout');
            state.authenticated = false;
            showView('login-view');
        } catch {
            showAlert('Erro ao fazer logout', 'error');
        }
    });
}

// ======================================================================
// SYNC BUTTONS
// ======================================================================

function bindSyncLocalButton() {
    const btn = $('#sync-local-btn');
    if (!btn) return;

    btn.addEventListener('click', async () => {
        btn.disabled = true;
        const originalHTML = btn.innerHTML;

        try {
            btn.innerHTML = '<span>🔄 Sincronizando...</span>';
            showAlert('Iniciando sincronização local...', 'info');

            const response = await API.post('/api/sync/local');

            if (response.status === 'success') {
                showAlert('✅ Sincronização concluída com sucesso!', 'success');
                await refreshStatus();
            } else {
                showAlert('⚠️ Erro: ' + (response.message || 'Sincronização falhou'), 'error');
            }
        } catch (err) {
            showAlert('❌ Erro: ' + err.message, 'error');
        } finally {
            btn.innerHTML = originalHTML;
            btn.disabled = false;
        }
    });
}

function bindSyncOnlineButton() {
    const btn = $('#sync-online-btn');
    if (!btn) return;

    btn.addEventListener('click', async () => {
        if (!confirm('Iniciar sincronização online com GitHub? Isto pode levar alguns minutos.')) {
            return;
        }

        btn.disabled = true;
        const originalHTML = btn.innerHTML;

        try {
            btn.innerHTML = '<span>✅ Sincronizando Online...</span>';
            showAlert('Iniciando sincronização GitHub...', 'info');

            const response = await API.post('/api/sync/github');

            if (response.status === 'success') {
                showAlert('✅ Sincronização GitHub concluída! Aguarde o deploy...', 'success');
                await refreshStatus();
            } else {
                showAlert('⚠️ Erro: ' + (response.message || 'Sincronização falhou'), 'error');
            }
        } catch (err) {
            showAlert('❌ Erro: ' + err.message, 'error');
        } finally {
            btn.innerHTML = originalHTML;
            btn.disabled = false;
        }
    });
}

function bindManualEditorButton() {
    const btn = $('#manual-editor-btn');
    if (!btn) return;

    btn.addEventListener('click', () => {
        window.location.href = '/manual-editor';
    });
}

// ======================================================================
// DASHBOARD LOADING
// ======================================================================

async function loadDashboard() {
    await refreshStatus();
}

async function refreshStatus() {
    try {
        await Promise.all([
            refreshCounts(),
            refreshFileStatus(),
        ]);
    } catch (err) {
        console.error('Erro ao atualizar status:', err);
    }
}

async function refreshCounts() {
    try {
        const [imp, mas, man] = await Promise.all([
            API.get('/api/calendar/import').catch(() => null),
            API.get('/api/calendar/master').catch(() => null),
            API.get('/api/calendar/manual').catch(() => null),
        ]);

        setText('#stat-import', imp && typeof imp.count === 'number' ? imp.count : '-');
        setText('#stat-master', mas && typeof mas.count === 'number' ? mas.count : '-');
        setText('#stat-manual', man && typeof man.count === 'number' ? man.count : '-');
    } catch {
        setText('#stat-import', '-');
        setText('#stat-master', '-');
        setText('#stat-manual', '-');
    }
}

async function refreshFileStatus() {
    try {
        const response = await API.get('/api/status/files');

        const statusContainer = $('#files-status');
        if (!statusContainer) return;

        if (!response || !response.files || response.files.length === 0) {
            statusContainer.innerHTML = '<p class="loading">Nenhum ficheiro encontrado.</p>';
            return;
        }

        let html = '';
        response.files.forEach((f) => {
            const status = f.exists ? 'ok' : 'missing';
            const statusText = f.exists ? '✓ OK' : '✗ Faltante';
            const sizeText = f.size ? ` (${f.size})` : '';

            html += `
                <div class="file-item">
                    <span class="file-name">${f.name}</span>
                    <span class="file-status-pill ${status}">${statusText}</span>
                    <span class="file-size">${sizeText}</span>
                </div>
            `;
        });

        statusContainer.innerHTML = html;
    } catch (err) {
        const statusContainer = $('#files-status');
        if (statusContainer) {
            statusContainer.innerHTML = `<p class="loading">Erro ao carregar estado dos ficheiros</p>`;
        }
    }
}

// ======================================================================
// ALERTS
// ======================================================================

function showAlert(message, type = 'info') {
    const container = $('#alerts');
    if (!container) return;

    const alertEl = document.createElement('div');
    alertEl.className = `alert alert-${type}`;
    alertEl.textContent = message;

    container.appendChild(alertEl);

    setTimeout(() => {
        alertEl.style.animation = 'fadeOut 0.3s ease-out forwards';
        setTimeout(() => alertEl.remove(), 300);
    }, 3000);
}

// ======================================================================
// INITIALIZATION
// ======================================================================

document.addEventListener('DOMContentLoaded', async () => {
    bindLoginForm();
    bindLogout();
    bindSyncLocalButton();
    bindSyncOnlineButton();
    bindManualEditorButton();

    await checkAuth();

    if (state.authenticated) {
        await loadDashboard();
    }

    console.log('✅ Dashboard iniciado com sucesso');
});

window.APP_VERSION = 'v3.2.4 FINAL PATCH';
window.APP_NAME = 'Rental Calendar Sync';

console.log(`${window.APP_NAME} ${window.APP_VERSION}`);
