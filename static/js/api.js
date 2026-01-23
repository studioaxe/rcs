/**
 * api.js - API Communication Helper
 * Rental Calendar Sync - Frontend API Interface
 * 
 * Version: 1.0
 * Date: 19 de Janeiro de 2026
 * Desenvolvido por: PBrandão
 */

class CalendarAPI {
    constructor() {
        this.baseUrl = '';
        this.headers = {
            'Content-Type': 'application/json'
        };
    }

    /**
     * Make API request
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            headers: this.headers,
            ...options
        };

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || 'API Error');
            }

            return { success: true, data };
        } catch (error) {
            console.error('API Error:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Load calendar data (import + manual)
     */
    async loadCalendar() {
        return this.request('/api/calendar/load', { method: 'GET' });
    }

    /**
     * Get events in date range
     */
    async getEvents(startDate, endDate) {
        const params = new URLSearchParams({
            start: startDate,
            end: endDate
        });
        return this.request(`/api/calendar/events?${params}`, { method: 'GET' });
    }

    /**
     * Sync calendar (manual trigger)
     */
    async syncCalendar() {
        return this.request('/api/calendar/sync', { method: 'POST' });
    }

    /**
     * Add manual block event(s)
     */
    async blockDates(dates, description = 'Data Bloqueada Manualmente') {
        return this.request('/api/manual/block-date', {
            method: 'POST',
            body: JSON.stringify({ dates, description })
        });
    }

    /**
     * Add manual remove event(s)
     */
    async removeEvents(dates, description = 'Data Desbloqueada Manualmente') {
        return this.request('/api/manual/remove-event', {
            method: 'POST',
            body: JSON.stringify({ dates, description })
        });
    }

    /**
     * Clear manual event(s)
     */
    async clearEvents(dates) {
        return this.request('/api/manual/clear-event', {
            method: 'POST',
            body: JSON.stringify({ dates })
        });
    }

    /**
     * Save manual calendar and sync
     */
    async saveManualCalendar() {
        return this.request('/api/manual/save', { method: 'POST' });
    }

    /**
     * Get session info
     */
    async getSessionInfo() {
        return this.request('/api/session', { method: 'GET' });
    }
}

// Create global API instance
const api = new CalendarAPI();

// Utility Functions
function showStatus(message, type = 'success') {
    const statusEl = document.getElementById('statusMessage');
    if (statusEl) {
        statusEl.textContent = message;
        statusEl.className = `status-message ${type}`;
        statusEl.classList.remove('hidden');
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            statusEl.classList.add('hidden');
        }, 5000);
    }
}

function showLoading(show = true, text = 'Carregando...') {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        if (show) {
            document.getElementById('loadingText').textContent = text;
            overlay.classList.remove('hidden');
        } else {
            overlay.classList.add('hidden');
        }
    }
}

function updateProgress(step) {
    for (let i = 1; i <= 3; i++) {
        const progressItem = document.getElementById(`progress${i}`);
        if (progressItem) {
            progressItem.classList.remove('active', 'completed');
            if (i < step) {
                progressItem.classList.add('completed');
            } else if (i === step) {
                progressItem.classList.add('active');
            }
        }
    }
}

/**
 * Format date from YYYYMMDD to YYYY-MM-DD
 */
function formatDateToISO(dateStr) {
    if (dateStr.includes('-')) return dateStr;
    return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`;
}

/**
 * Format date from YYYY-MM-DD to YYYYMMDD
 */
function formatDateToCompact(dateStr) {
    if (!dateStr.includes('-')) return dateStr;
    return dateStr.replace(/-/g, '');
}

/**
 * Format date for display
 */
function formatDateDisplay(dateStr) {
    const date = new Date(`${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`);
    return date.toLocaleDateString('pt-PT', { 
        weekday: 'short',
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
    });
}

/**
 * Get date range between two dates
 */
function getDateRange(startDate, endDate) {
    const dates = [];
    let current = new Date(startDate);
    const end = new Date(endDate);

    while (current <= end) {
        const year = current.getFullYear();
        const month = String(current.getMonth() + 1).padStart(2, '0');
        const day = String(current.getDate()).padStart(2, '0');
        dates.push(`${year}-${month}-${day}`);
        current.setDate(current.getDate() + 1);
    }

    return dates;
}

/**
 * Check if date is in selected range
 */
function isDateInRange(date, rangeStart, rangeEnd) {
    if (!rangeStart || !rangeEnd) return false;
    return date >= rangeStart && date <= rangeEnd;
}

/**
 * Parse ICS event categories
 */
function getEventCategory(event) {
    const categories = event.categories || [];
    if (typeof categories === 'string') {
        return categories;
    }
    return categories[0] || 'UNKNOWN';
}

/**
 * Get color for event category
 */
function getCategoryColor(category) {
    const colorMap = {
        'RESERVATION': 'red',
        'PREP-TIME': 'orange',
        'MANUAL-BLOCK': 'neon-green',
        'MANUAL-REMOVE': 'yellow',
        'AVAILABLE': 'light-blue'
    };
    return colorMap[category] || 'light-blue';
}

/**
 * Merge date ranges (consecutive dates)
 */
function mergeConsecutiveDates(dates) {
    if (dates.length === 0) return [];

    const sorted = dates.sort();
    const merged = [];
    let rangeStart = sorted[0];
    let rangeEnd = sorted[0];

    for (let i = 1; i < sorted.length; i++) {
        const current = new Date(sorted[i]);
        const next = new Date(rangeEnd);
        next.setDate(next.getDate() + 1);

        if (current.toISOString().split('T')[0] === next.toISOString().split('T')[0]) {
            rangeEnd = sorted[i];
        } else {
            merged.push({ start: rangeStart, end: rangeEnd });
            rangeStart = sorted[i];
            rangeEnd = sorted[i];
        }
    }

    merged.push({ start: rangeStart, end: rangeEnd });
    return merged;
}

/**
 * Create event object from form data
 */
function createEventObject(dates, category, description) {
    return {
        dates: dates.map(d => formatDateToISO(d)),
        category: category,
        description: description
    };
}

/**
 * Debounce function for performance
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Throttle function for performance
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * Notify user of operation completion
 */
function notify(message, duration = 3000, type = 'success') {
    showStatus(message, type);
}

/**
 * Log for debugging
 */
function debugLog(label, data) {
    if (window.DEBUG) {
        console.log(`[${label}]`, data);
    }
}
