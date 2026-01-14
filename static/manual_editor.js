// ======================================================================
// Rental Calendar Sync v3.2.4 - Manual Editor JS
// ======================================================================

console.log('%c📝 Manual Editor v3.2.4 FINAL PATCH', 'color: #667eea; font-weight: bold; font-size: 14px;');

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
            throw new Error((data && (data.message || data.error)) || `HTTP ${res.status}`);
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
            throw new Error((data && (data.message || data.error)) || `HTTP ${res.status}`);
        }
        return data;
    },
};

// ======================================================================
// STATE
// ======================================================================

let currentMonth = new Date().getMonth();
let currentYear = new Date().getFullYear();
let actionType = 'block';
let selectedDates = new Set();
let startDate = null;
let endDate = null;
let importEvents = [];
let manualEvents = [];

// ======================================================================
// CALENDAR RENDERING
// ======================================================================

function renderCalendar() {
    const grid = document.getElementById('calendarGrid');
    grid.innerHTML = '';

    const dayHeaders = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom'];
    dayHeaders.forEach(day => {
        const header = document.createElement('div');
        header.className = 'day-header';
        header.textContent = day;
        grid.appendChild(header);
    });

    const firstDay = new Date(currentYear, currentMonth, 1);
    const lastDay = new Date(currentYear, currentMonth + 1, 0);
    const startDateGrid = new Date(firstDay);
    startDateGrid.setDate(startDateGrid.getDate() - firstDay.getDay() + 1);

    let currentDate = new Date(startDateGrid);
    for (let i = 0; i < 42; i++) {
        const day = document.createElement('div');
        
        if (currentDate.getMonth() !== currentMonth) {
            day.className = 'calendar-day day-empty';
        } else {
            const dateStr = currentDate.toISOString().split('T')[0];
            day.className = 'calendar-day';
            day.textContent = currentDate.getDate();
            day.onclick = () => toggleDate(dateStr);

            // Aplicar classes de cor
            if (isManualBlockDate(dateStr)) {
                day.classList.add('day-manual-block');
            } else if (isManualRemoveDate(dateStr)) {
                day.classList.add('day-manual-remove');
            } else if (isReservationDate(dateStr)) {
                day.classList.add('day-reservation');
            } else if (isPrepTimeDate(dateStr)) {
                day.classList.add('day-prep-time');
            } else if (selectedDates.has(dateStr)) {
                day.classList.add('day-selected');
            } else {
                day.classList.add('day-available');
            }
        }
        
        grid.appendChild(day);
        currentDate.setDate(currentDate.getDate() + 1);
    }

    const monthNames = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
    document.getElementById('monthYear').textContent = `${monthNames[currentMonth]} ${currentYear}`;
}

function previousMonth() {
    if (currentMonth === 0) {
        currentMonth = 11;
        currentYear--;
    } else {
        currentMonth--;
    }
    renderCalendar();
}

function nextMonth() {
    if (currentMonth === 11) {
        currentMonth = 0;
        currentYear++;
    } else {
        currentMonth++;
    }
    renderCalendar();
}

// ======================================================================
// DATE SELECTION
// ======================================================================

function toggleDate(dateStr) {
    if (!startDate) {
        startDate = dateStr;
        selectedDates.add(dateStr);
    } else if (!endDate) {
        if (dateStr > startDate) {
            endDate = dateStr;
            fillDateRange();
        } else if (dateStr === startDate) {
            startDate = null;
            selectedDates.clear();
        } else {
            endDate = startDate;
            startDate = dateStr;
            fillDateRange();
        }
    } else {
        startDate = dateStr;
        endDate = null;
        selectedDates.clear();
        selectedDates.add(dateStr);
    }
    
    updateSelectedRange();
    renderCalendar();
}

function fillDateRange() {
    const start = new Date(startDate);
    const end = new Date(endDate);
    selectedDates.clear();

    while (start <= end) {
        const dateStr = start.toISOString().split('T')[0];
        selectedDates.add(dateStr);
        start.setDate(start.getDate() + 1);
    }
}

function updateSelectedRange() {
    const range = document.getElementById('selectedRange');
    const text = document.getElementById('rangeText');

    if (startDate && endDate) {
        range.style.display = 'block';
        text.textContent = `De ${startDate} a ${endDate}`;
    } else if (startDate) {
        range.style.display = 'block';
        text.textContent = `De ${startDate} (selecionando fim...)`;
    } else {
        range.style.display = 'none';
    }
}

// ======================================================================
// EVENT CHECKING
// ======================================================================

function isReservationDate(dateStr) {
    return importEvents.some(e => {
        if (e.type === 'RESERVATION') {
            return dateStr >= e.dateStart && dateStr <= e.dateEnd;
        }
        return false;
    });
}

function isPrepTimeDate(dateStr) {
    return importEvents.some(e => {
        if (e.type === 'PREP-TIME') {
            return dateStr >= e.dateStart && dateStr <= e.dateEnd;
        }
        return false;
    });
}

function isManualBlockDate(dateStr) {
    return manualEvents.some(e => 
        e.type === 'MANUAL-BLOCK' && dateStr >= e.dateStart && dateStr <= e.dateEnd
    );
}

function isManualRemoveDate(dateStr) {
    return manualEvents.some(e => 
        e.type === 'MANUAL-REMOVE' && dateStr >= e.dateStart && dateStr <= e.dateEnd
    );
}

// ======================================================================
// ACTION TYPE
// ======================================================================

function setActionType(type) {
    actionType = type;
    document.getElementById('blockBtn').classList.toggle('active', type === 'block');
    document.getElementById('removeBtn').classList.toggle('active', type === 'remove');
}

// ======================================================================
// EVENTS LOADING
// ======================================================================

async function loadCalendars() {
    try {
        updateProgress(25, 'Carregando import_calendar.ics...');
        
        const importRes = await API.get('/api/calendar/import');
        if (importRes && importRes.events) {
            parseImportEvents(importRes.events);
        }

        updateProgress(50, 'Carregando manual_calendar.ics...');
        
        const manualRes = await API.get('/api/calendar/manual');
        if (manualRes && manualRes.events) {
            parseManualEvents(manualRes.events);
        }

        updateProgress(75, 'Renderizando calendário...');
        buildLegend();
        renderCalendar();
        
        updateProgress(100, 'Pronto!');
        setTimeout(() => updateProgress(0, 'Aguardando ação...'), 2000);
    } catch (error) {
        showNotification('Erro ao carregar: ' + error.message, 'error');
        updateProgress(0, 'Erro');
    }
}

function parseImportEvents(events) {
    importEvents = events.map(e => {
        const categories = String(e.categories || '').toUpperCase().trim();
        let type = 'UNKNOWN';
        
        if (categories.includes('RESERVATION')) type = 'RESERVATION';
        else if (categories.includes('PREP-TIME')) type = 'PREP-TIME';
        
        return {
            type,
            summary: e.summary,
            description: e.description,
            dateStart: e.dtstart,
            dateEnd: e.dtend,
            source: e.source
        };
    });
}

function parseManualEvents(events) {
    manualEvents = events.map(e => {
        const categories = String(e.categories || '').toUpperCase().trim();
        let type = 'UNKNOWN';
        
        if (categories.includes('MANUAL-BLOCK')) type = 'MANUAL-BLOCK';
        else if (categories.includes('MANUAL-REMOVE')) type = 'MANUAL-REMOVE';
        
        return {
            type,
            summary: e.summary,
            description: e.description,
            dateStart: e.dtstart,
            dateEnd: e.dtend
        };
    });
}

// ======================================================================
// LEGEND BUILDING
// ======================================================================

function buildLegend() {
    const legendItems = document.getElementById('legendItems');
    legendItems.innerHTML = '';

    const eventsMap = new Map();

    // Agrupar eventos por SUMMARY
    importEvents.forEach(e => {
        const key = e.summary;
        if (!eventsMap.has(key)) {
            eventsMap.set(key, {
                summary: e.summary,
                description: e.description,
                type: e.type,
                editable: false
            });
        }
    });

    manualEvents.forEach(e => {
        const key = e.summary;
        if (!eventsMap.has(key)) {
            eventsMap.set(key, {
                summary: e.summary,
                description: e.description,
                type: e.type,
                editable: true
            });
        }
    });

    // Renderizar legenda
    eventsMap.forEach((event, key) => {
        const item = document.createElement('div');
        item.className = 'legend-item';

        let iconClass = '';
        if (event.type === 'RESERVATION') iconClass = 'icon-reservation';
        else if (event.type === 'PREP-TIME') iconClass = 'icon-prep-time';
        else if (event.type === 'MANUAL-BLOCK') iconClass = 'icon-manual-block';
        else if (event.type === 'MANUAL-REMOVE') iconClass = 'icon-manual-remove';

        item.innerHTML = `
            <div class="legend-icon ${iconClass}"></div>
            <div style="flex: 1;">
                <strong>${event.summary}</strong><br>
                <small>${event.description || 'Sem descrição'}</small>
            </div>
        `;

        legendItems.appendChild(item);
    });
}

// ======================================================================
// SAVE CHANGES
// ======================================================================

async function saveChanges() {
    if (!startDate || !endDate) {
        showNotification('Selecione um período!', 'error');
        return;
    }

    if (new Date(startDate) > new Date(endDate)) {
        showNotification('Data de início não pode ser após data de fim!', 'error');
        return;
    }

    if (new Date(endDate) < new Date()) {
        showNotification('Não pode selecionar datas passadas!', 'error');
        return;
    }

    const notes = document.getElementById('notes').value;

    try {
        updateProgress(50, 'Processando alterações...');

        const response = await API.post('/api/manual/upload', {
            action_type: actionType,
            start_date: startDate,
            end_date: endDate,
            description: notes,
            ics_content: generateICS()
        });

        if (response.status === 'success') {
            updateProgress(100, 'Sucesso!');
            showNotification('Alterações guardadas com sucesso! ✅', 'success');
            resetSelection();
            setTimeout(loadCalendars, 2000);
        } else {
            throw new Error(response.message || 'Erro desconhecido');
        }
    } catch (error) {
        updateProgress(0, 'Erro');
        showNotification('Erro: ' + error.message, 'error');
    }
}

function discardChanges() {
    resetSelection();
    showNotification('Alterações descartadas', 'info');
    renderCalendar();
}

function resetSelection() {
    startDate = null;
    endDate = null;
    selectedDates.clear();
    document.getElementById('notes').value = '';
    updateSelectedRange();
}

// ======================================================================
// ICS GENERATION
// ======================================================================

function generateICS() {
    const endDateObj = new Date(endDate);
    endDateObj.setDate(endDateObj.getDate() + 1);
    const endDateFormatted = endDateObj.toISOString().split('T')[0].replace(/-/g, '');

    const summary = actionType === 'block' ? 'BLOQUEADO' : 'REMOVIDO';
    const category = actionType === 'block' ? 'MANUAL-BLOCK' : 'MANUAL-REMOVE';
    const description = document.getElementById('notes').value || 
        (actionType === 'block' ? 'Data Bloqueada Manualmente' : 'Data Desbloqueada Manualmente');

    return `BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Rental Manual Calendar//PT
CALSCALE:GREGORIAN
X-WR-CALNAME:Manual Calendar
X-WR-TIMEZONE:Europe/Lisbon
BEGIN:VEVENT
UID:manual-${Date.now()}
CATEGORIES:${category}
DTSTART;VALUE=DATE:${startDate.replace(/-/g, '')}
DTEND;VALUE=DATE:${endDateFormatted}
SUMMARY:${summary}
DESCRIPTION:${description}
STATUS:CONFIRMED
TRANSP:TRANSPARENT
END:VEVENT
END:VCALENDAR`;
}

// ======================================================================
// PROGRESS & NOTIFICATIONS
// ======================================================================

function updateProgress(percent, message) {
    document.getElementById('progressBar').style.width = percent + '%';
    document.getElementById('progressText').textContent = Math.round(percent);
    document.getElementById('progressMessage').textContent = message;
}

function showNotification(message, type) {
    const notif = document.getElementById('notification');
    notif.textContent = message;
    notif.className = `notification ${type}`;
    
    setTimeout(() => {
        notif.className = 'notification';
    }, 3000);
}

// ======================================================================
// NAVIGATION
// ======================================================================

function bindDashboardButton() {
    const btn = document.getElementById('dashboard-btn');
    if (btn) {
        btn.addEventListener('click', () => {
            window.location.href = '/dashboard';
        });
    }
}

function bindLogout() {
    const btn = document.getElementById('logout-btn');
    if (btn) {
        btn.addEventListener('click', async () => {
            try {
                await API.post('/api/auth/logout');
                window.location.href = '/';
            } catch {
                showNotification('Erro ao fazer logout', 'error');
            }
        });
    }
}

// ======================================================================
// INITIALIZATION
// ======================================================================

window.addEventListener('load', () => {
    // Preencher utilizador
    const userEl = document.getElementById('current-user');
    if (userEl) {
        userEl.textContent = localStorage.getItem('username') || 'Admin';
    }

    bindDashboardButton();
    bindLogout();
    
    renderCalendar();
    loadCalendars();

    console.log('✅ Manual Editor iniciado com sucesso');
});

console.log('📝 Manual Editor v3.2.4 FINAL PATCH - Pronto');
