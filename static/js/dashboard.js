/* ============================================================================
   DASHBOARD.JS - Lógica do Dashboard
   ============================================================================ */

document.addEventListener('DOMContentLoaded', () => {
    initializeDashboard();
});

function initializeDashboard() {
    const btnSyncOnline = document.getElementById('btn-sync-online');
    const btnManualEditor = document.getElementById('btn-manual-editor');
    const statusMessage = document.getElementById('status-message');

    // Event listeners
    btnSyncOnline.addEventListener('click', handleSyncOnline);
    btnManualEditor.addEventListener('click', handleManualEditor);
}

async function handleSyncOnline(e) {
    e.preventDefault();
    const btn = e.target.closest('button');
    const statusMessage = document.getElementById('status-message');

    try {
        // Disable button
        btn.disabled = true;
        showStatus('Sincronizando calendários...', 'info', statusMessage);

        // Call API
        const response = await fetch('/api/sync', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const data = await response.json();

        if (response.ok) {
            showStatus('✅ Sincronização concluída com sucesso!', 'success', statusMessage);
            console.log('Sync successful:', data);
        } else {
            showStatus('❌ Erro na sincronização: ' + data.message, 'error', statusMessage);
            console.error('Sync error:', data);
        }
    } catch (error) {
        showStatus('❌ Erro na requisição: ' + error.message, 'error', statusMessage);
        console.error('Request error:', error);
    } finally {
        btn.disabled = false;
    }
}

function handleManualEditor(e) {
    e.preventDefault();
    window.location.href = '/manual-editor';
}

function showStatus(message, type, element) {
    element.textContent = message;
    element.className = `status-message ${type}`;
    element.classList.remove('hidden');

    // Auto-hide after 5 seconds
    setTimeout(() => {
        element.classList.add('hidden');
    }, 5000);
}
