// Global state
let currentPage = 1;
let sortState = { column: 'date', direction: 'asc' };
let currentData = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadUpcomingCatalysts();
    setupSortHandlers();
});


// Load upcoming catalysts
async function loadUpcomingCatalysts(page = 1) {
    const stageFilter = document.getElementById('stage-filter').value;
    const searchTerm = document.getElementById('search-filter').value;
    
    document.getElementById('upcoming-loading').style.display = 'block';
    document.getElementById('upcoming-content').style.display = 'none';
    
    try {
        const params = new URLSearchParams({
            stage: stageFilter,
            search: searchTerm,
            page: page,
            per_page: 25
        });
        
        const response = await fetch(`/api/catalysts/upcoming?${params}`);
        const data = await response.json();
        
        currentData = data.results;
        displayUpcomingCatalysts(sortData(data.results, sortState));
        updatePagination(page, data.total_pages);
        currentPage = page;
        
    } catch (error) {
        console.error('Error loading catalysts:', error);
        document.getElementById('upcoming-content').innerHTML = '<p>Error loading catalysts</p>';
    } finally {
        document.getElementById('upcoming-loading').style.display = 'none';
        document.getElementById('upcoming-content').style.display = 'block';
    }
}

// Display upcoming catalysts
function displayUpcomingCatalysts(catalysts) {
    const tbody = document.getElementById('upcoming-tbody');
    
    if (catalysts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No upcoming catalysts found</td></tr>';
        return;
    }
    
    tbody.innerHTML = catalysts.map(catalyst => {
        const daysUntil = getDaysUntil(catalyst.catalyst_date);
        const dateClass = daysUntil <= 30 ? 'date-soon' : daysUntil <= 60 ? 'date-medium' : 'date-later';
        const stageClass = catalyst.stage.toLowerCase().replace(/\s+/g, '-');
        
        // Extract first indication
        let indication = '';
        if (catalyst.indications && catalyst.indications.length > 0) {
            const ind = catalyst.indications[0];
            indication = typeof ind === 'string' ? ind : ind.indication_name || ind.name || '';
        }
        
        return `
            <tr>
                <td class="date-cell ${dateClass}">${formatDate(catalyst.catalyst_date)}</td>
                <td><span class="ticker">${escapeHtml(catalyst.company.ticker)}</span></td>
                <td>${escapeHtml(catalyst.company.name)}</td>
                <td>${escapeHtml(catalyst.drug_name)}</td>
                <td><span class="stage-badge ${stageClass}">${catalyst.stage}</span></td>
                <td>${escapeHtml(indication)}</td>
                <td class="market-cap">${formatMarketCap(catalyst.company.market_cap)}</td>
                <td class="price">${catalyst.company.stock_price ? '$' + catalyst.company.stock_price.toFixed(2) : 'N/A'}</td>
            </tr>
            ${catalyst.note ? `
            <tr class="note-row">
                <td colspan="8">
                    <div class="note-content">
                        ${formatNoteWithDateBreaks(catalyst.note)}
                    </div>
                </td>
            </tr>
            ` : ''}`;
    }).join('');
    
    // Show/hide table
    document.getElementById('upcoming-content').style.display = 'block';
}


// Update pagination
function updatePagination(currentPageNum, totalPages) {
    const container = document.getElementById('upcoming-pagination');
    
    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }
    
    container.innerHTML = `
        <button onclick="loadUpcomingCatalysts(${currentPageNum - 1})" ${currentPageNum === 1 ? 'disabled' : ''}>
            Previous
        </button>
        <span class="page-info">Page ${currentPageNum} of ${totalPages}</span>
        <button onclick="loadUpcomingCatalysts(${currentPageNum + 1})" ${currentPageNum === totalPages ? 'disabled' : ''}>
            Next
        </button>
    `;
}

// Utility functions
function formatDate(dateString) {
    if (!dateString) return 'TBA';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function getDaysUntil(dateString) {
    if (!dateString) return Infinity;
    const date = new Date(dateString);
    const today = new Date();
    const diffTime = date - today;
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
}

function formatMarketCap(value) {
    if (!value) return 'N/A';
    if (value >= 1e9) return '$' + (value / 1e9).toFixed(1) + 'B';
    if (value >= 1e6) return '$' + (value / 1e6).toFixed(1) + 'M';
    return '$' + value.toFixed(0);
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatNoteWithDateBreaks(note) {
    if (!note) return '';
    
    // Replace slash dates with bold versions and add line breaks
    return escapeHtml(note).replace(/(\b\d{1,2}\/\d{1,2}\/\d{2,4})/g, '<br><strong>$1</strong>').replace(/^<br>/, '');
}

// Filter table based on search input - triggers API call
function filterTable() {
    // Reset to page 1 when searching
    currentPage = 1;
    loadUpcomingCatalysts(1);
}

// Sort data based on column and direction
function sortData(data, sortConfig) {
    const sorted = [...data];
    
    sorted.sort((a, b) => {
        let aVal, bVal;
        
        switch (sortConfig.column) {
            case 'date':
                aVal = new Date(a.catalyst_date || '');
                bVal = new Date(b.catalyst_date || '');
                break;
            case 'ticker':
                aVal = (a.company?.ticker || a.ticker || '').toLowerCase();
                bVal = (b.company?.ticker || b.ticker || '').toLowerCase();
                break;
            case 'company':
                aVal = (a.company?.name || a.company_name || '').toLowerCase();
                bVal = (b.company?.name || b.company_name || '').toLowerCase();
                break;
            case 'stage':
                aVal = (a.stage || '').toLowerCase();
                bVal = (b.stage || '').toLowerCase();
                break;
            case 'marketcap':
                aVal = a.company?.market_cap || 0;
                bVal = b.company?.market_cap || 0;
                break;
            case 'price':
                aVal = a.company?.stock_price || 0;
                bVal = b.company?.stock_price || 0;
                break;
            default:
                return 0;
        }
        
        if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
        if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
        return 0;
    });
    
    return sorted;
}

// Setup sort handlers
function setupSortHandlers() {
    document.querySelectorAll('.sortable').forEach(th => {
        th.addEventListener('click', function() {
            const column = this.dataset.sort;
            
            // Update sort state
            if (sortState.column === column) {
                sortState.direction = sortState.direction === 'asc' ? 'desc' : 'asc';
            } else {
                sortState.column = column;
                sortState.direction = 'asc';
            }
            
            // Update UI
            updateSortIndicators();
            
            // Re-display sorted data
            displayUpcomingCatalysts(sortData(currentData, sortState));
        });
    });
}

// Update sort indicators
function updateSortIndicators() {
    // Reset all indicators
    document.querySelectorAll('.sortable').forEach(th => {
        th.classList.remove('sorted-asc', 'sorted-desc');
        th.querySelector('.sort-icon').textContent = '↕';
    });
    
    // Set active indicator
    const activeHeader = document.querySelector(`[data-sort="${sortState.column}"]`);
    if (activeHeader) {
        activeHeader.classList.add(`sorted-${sortState.direction}`);
        activeHeader.querySelector('.sort-icon').textContent = sortState.direction === 'asc' ? '↑' : '↓';
    }
}

