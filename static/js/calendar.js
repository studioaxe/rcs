/**
 * calendar.js - Calendar Editor Logic
 * Rental Calendar Sync - Manual Editor Calendar Control
 * 
 * Version: 1.0
 * Date: 22 de Janeiro de 2026
 * Desenvolvido por: PBrandão
 */

class CalendarEditor {
    constructor() {
        this.currentDate = new Date();
        this.selectedDates = new Set();
        this.selectionStart = null;
        this.selectionEnd = null;
        this.calendarData = {};
        this.sessionChanges = new Map();
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadCalendarData();
    }

    /**
     * Setup all event listeners
     */
    setupEventListeners() {
        // Month navigation
        document.getElementById('prevMonth').addEventListener('click', () => this.previousMonth());
        document.getElementById('nextMonth').addEventListener('click', () => this.nextMonth());

        // Action buttons
        document.getElementById('blockDateBtn').addEventListener('click', () => this.blockSelectedDates());
        document.getElementById('removeEventBtn').addEventListener('click', () => this.removeSelectedEvents());
        document.getElementById('clearEventBtn').addEventListener('click', () => this.clearSelectedEvents());

        // Save/Discard
        document.getElementById('discardBtn').addEventListener('click', () => this.discardChanges());
        document.getElementById('saveBtn').addEventListener('click', () => this.saveChanges());
    }

    /**
     * Load calendar data from API
     */
    async loadCalendarData() {
        showLoading(true, 'Carregando calendários...');
        updateProgress(1);

        try {
            const result = await api.loadCalendar();

            if (result.success) {
                // ✅ FIX: Handle both object and array responses
                const eventsData = result.data.events;

                if (typeof eventsData === 'object' && eventsData !== null) {
                    // It's already an object (dict of dates)
                    this.calendarData = eventsData;
                } else if (Array.isArray(eventsData)) {
                    // It's an array, convert to object
                    this.calendarData = {};
                    // This shouldn't happen with current API, but handle gracefully
                } else {
                    console.warn('Unexpected events data format:', typeof eventsData);
                    this.calendarData = {};
                }

                updateProgress(2);
                setTimeout(() => {
                    updateProgress(3);
                    this.renderCalendar();
                    showLoading(false);
                    document.getElementById('progressBar').classList.add('hidden');
                }, 800);
            } else {
                showStatus('Erro ao carregar calendário: ' + result.error, 'error');
                showLoading(false);
            }
        } catch (error) {
            console.error('Error loading calendar:', error);
            showStatus('Erro de conexão: ' + error.message, 'error');
            showLoading(false);
        }
    }

    /**
     * Render calendar for current month
     */
    renderCalendar() {
        const year = this.currentDate.getFullYear();
        const month = this.currentDate.getMonth();

        // Update title
        const monthNames = [
            'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
            'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
        ];
        document.getElementById('monthTitle').textContent = `${monthNames[month]} ${year}`;

        // Get calendar days
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        const daysInMonth = lastDay.getDate();
        const startingDayOfWeek = firstDay.getDay();
        const adjustedStart = startingDayOfWeek === 0 ? 6 : startingDayOfWeek - 1;

        const daysContainer = document.getElementById('calendarDays');
        daysContainer.innerHTML = '';

        // Empty cells before month starts
        for (let i = 0; i < adjustedStart; i++) {
            const emptyDay = document.createElement('div');
            emptyDay.className = 'calendar-day empty';
            daysContainer.appendChild(emptyDay);
        }

        // Days of month
        for (let day = 1; day <= daysInMonth; day++) {
            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            const dayElement = this.createDayElement(dateStr, day);
            daysContainer.appendChild(dayElement);
        }
    }

    /**
     * Create calendar day element
     */
    createDayElement(dateStr, day) {
        const dayEl = document.createElement('div');
        dayEl.className = 'calendar-day';
        dayEl.textContent = day;
        dayEl.dataset.date = dateStr;

        // Get event status for this date
        const status = this.calendarData[dateStr] || {
            color: 'light-blue',
            category: 'available',
            description: ''
        };

        // Ensure status has required properties
        const colorClass = status.color || 'light-blue';
        dayEl.classList.add(colorClass);

        // Check if selected
        if (this.selectedDates.has(dateStr)) {
            dayEl.classList.remove(colorClass);
            dayEl.classList.add('dark-blue');
        }

        // Add click event
        dayEl.addEventListener('click', () => this.selectDate(dateStr, dayEl));

        return dayEl;
    }

    /**
     * Handle date selection
     */
    selectDate(dateStr, element) {
        const isSelected = this.selectedDates.has(dateStr);

        if (this.selectedDates.size === 0) {
            // First selection
            this.selectionStart = dateStr;
            this.selectionEnd = dateStr;
            this.selectedDates.add(dateStr);
        } else {
            // Range selection check
            if (isSelected) {
                // Deselect
                this.selectedDates.delete(dateStr);
            } else {
                // Add to range
                this.addDateToSelection(dateStr);
            }
        }

        // Update UI
        this.updateCalendarUI();
        this.updateEventsPanel();
        this.updateActionButtons();
    }

    /**
     * Add date to selection (supporting range)
     */
    addDateToSelection(dateStr) {
        // Simple consecutive selection
        const start = Math.min(this.selectionStart, dateStr);
        const end = Math.max(this.selectionStart, dateStr);

        // Parse dates
        const startDate = new Date(start);
        const endDate = new Date(dateStr);

        // Add all dates in range
        let current = new Date(startDate);
        while (current <= endDate) {
            const year = current.getFullYear();
            const month = String(current.getMonth() + 1).padStart(2, '0');
            const day = String(current.getDate()).padStart(2, '0');
            const dateKey = `${year}-${month}-${day}`;
            this.selectedDates.add(dateKey);
            current.setDate(current.getDate() + 1);
        }

        this.selectionEnd = dateStr;
    }

    /**
     * Update calendar UI after selection change
     */
    updateCalendarUI() {
        document.querySelectorAll('.calendar-day').forEach(day => {
            if (day.classList.contains('empty')) return;

            const dateStr = day.dataset.date;
            const status = this.calendarData[dateStr] || {
                color: 'light-blue',
                category: 'available'
            };

            // Reset color classes
            day.className = 'calendar-day';

            if (this.selectedDates.has(dateStr)) {
                day.classList.add('dark-blue');
            } else {
                const colorClass = status.color || 'light-blue';
                day.classList.add(colorClass);
            }

            day.textContent = parseInt(dateStr.slice(-2));
        });
    }

    /**
     * Update events panel based on selection
     */
    updateEventsPanel() {
        const panel = document.getElementById('eventsPanel');

        if (this.selectedDates.size === 0) {
            panel.innerHTML = '<div style="padding: 16px; color: var(--text-secondary);">Selecione uma data</div>';
            return;
        }

        const eventsHTML = [];
        const sortedDates = Array.from(this.selectedDates).sort();

        for (const dateStr of sortedDates) {
            const status = this.calendarData[dateStr];

            if (status && status.description) {
                const displayDate = new Date(dateStr).toLocaleDateString('pt-PT', {
                    weekday: 'short',
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric'
                });

                eventsHTML.push(`
                    <div style="padding: 8px 16px; border-bottom: 1px solid var(--border-color);">
                        <strong>${displayDate}</strong>
                        <div style="font-size: 12px; color: var(--text-secondary);">${status.description}</div>
                    </div>
                `);
            }
        }

        if (eventsHTML.length === 0) {
            panel.innerHTML = '<div style="padding: 16px; color: var(--text-secondary);">Datas sem eventos</div>';
        } else {
            panel.innerHTML = eventsHTML.join('');
        }
    }

    /**
     * Update action buttons state
     */
    updateActionButtons() {
        const hasSelection = this.selectedDates.size > 0;

        document.getElementById('blockDateBtn').disabled = !hasSelection;
        document.getElementById('removeEventBtn').disabled = !hasSelection;
        document.getElementById('clearEventBtn').disabled = !hasSelection;

        if (hasSelection) {
            document.getElementById('blockDateBtn').classList.remove('disabled');
            document.getElementById('removeEventBtn').classList.remove('disabled');
            document.getElementById('clearEventBtn').classList.remove('disabled');
        } else {
            document.getElementById('blockDateBtn').classList.add('disabled');
            document.getElementById('removeEventBtn').classList.add('disabled');
            document.getElementById('clearEventBtn').classList.add('disabled');
        }
    }

    /**
     * Block selected dates
     */
    blockSelectedDates() {
        if (this.selectedDates.size === 0) return;

        const dates = this.getSelectedDatesFormatted();
        this.sessionChanges.set('block', dates);

        // Update UI
        dates.forEach(date => {
            this.calendarData[date] = {
                color: 'neon-green',
                category: 'blocked',
                description: 'Data Bloqueada Manualmente'
            };
        });

        this.clearSelection();
        this.renderCalendar();
        showStatus('✅ Datas bloqueadas (não salvo)', 'success');
    }

    /**
     * Remove selected events
     */
    removeSelectedEvents() {
        if (this.selectedDates.size === 0) return;

        const dates = this.getSelectedDatesFormatted();
        this.sessionChanges.set('remove', dates);

        // Update UI
        dates.forEach(date => {
            this.calendarData[date] = {
                color: 'yellow',
                category: 'removed',
                description: 'Data Desbloqueada Manualmente'
            };
        });

        this.clearSelection();
        this.renderCalendar();
        showStatus('✅ Eventos marcados para remover (não salvo)', 'success');
    }

    /**
     * Clear selected events (from manual calendar)
     */
    clearSelectedEvents() {
        if (this.selectedDates.size === 0) return;

        const dates = this.getSelectedDatesFormatted();
        this.sessionChanges.set('clear', dates);

        // Update UI
        dates.forEach(date => {
            // Revert to AVAILABLE or original import state
            this.calendarData[date] = {
                color: 'light-blue',
                category: 'available',
                description: ''
            };
        });

        this.clearSelection();
        this.renderCalendar();
        showStatus('✅ Eventos manuais removidos (não salvo)', 'success');
    }

    /**
     * Get selected dates formatted
     */
    getSelectedDatesFormatted() {
        return Array.from(this.selectedDates).sort();
    }

    /**
     * Clear date selection
     */
    clearSelection() {
        this.selectedDates.clear();
        this.selectionStart = null;
        this.selectionEnd = null;
        this.updateCalendarUI();
        this.updateEventsPanel();
        this.updateActionButtons();
    }

    /**
     * Discard all session changes
     */
    discardChanges() {
        if (confirm('Tem certeza que deseja descartar todas as alterações desta sessão?')) {
            this.sessionChanges.clear();
            this.clearSelection();
            this.loadCalendarData();
            showStatus('✅ Alterações descartadas', 'success');
        }
    }

    /**
     * Save changes
     */
    async saveChanges() {
        if (this.sessionChanges.size === 0) {
            showStatus('Nenhuma alteração para guardar', 'info');
            return;
        }

        showLoading(true, 'Guardando alterações...');

        try {
            // Block dates
            if (this.sessionChanges.has('block')) {
                const result = await api.blockDates(this.sessionChanges.get('block'));
                if (!result.success) throw new Error(result.error);
            }

            // Remove events
            if (this.sessionChanges.has('remove')) {
                const result = await api.removeEvents(this.sessionChanges.get('remove'));
                if (!result.success) throw new Error(result.error);
            }

            // Clear events
            if (this.sessionChanges.has('clear')) {
                const result = await api.clearEvents(this.sessionChanges.get('clear'));
                if (!result.success) throw new Error(result.error);
            }

            // Save and sync
            updateProgress(1);
            showLoading(true, 'Sincronizando calendários...');

            const saveResult = await api.saveManualCalendar();

            if (saveResult.success) {
                this.sessionChanges.clear();
                updateProgress(3);
                showLoading(false);
                showStatus('✅ Alterações guardadas e sincronizadas com sucesso!', 'success');

                // Reload calendar
                setTimeout(() => {
                    this.loadCalendarData();
                }, 2000);
            } else {
                throw new Error(saveResult.error);
            }
        } catch (error) {
            console.error('Save error:', error);
            showLoading(false);
            showStatus('❌ Erro ao guardar: ' + error.message, 'error');
        }
    }

    /**
     * Month navigation
     */
    previousMonth() {
        this.currentDate.setMonth(this.currentDate.getMonth() - 1);
        this.renderCalendar();
    }

    nextMonth() {
        this.currentDate.setMonth(this.currentDate.getMonth() + 1);
        this.renderCalendar();
    }
}

// Initialize calendar editor on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('[INIT] Calendar Editor iniciando...');
    new CalendarEditor();
    console.log('[INIT] Calendar Editor carregado com sucesso');
});
