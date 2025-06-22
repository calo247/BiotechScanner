// Global state
let currentPage = 1;
let sortState = { column: 'date', direction: 'asc' };
let currentData = [];
let marketCapSlider = null;
let stockPriceSlider = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeMarketCapSlider();
    initializeStockPriceSlider();
    loadUpcomingCatalysts();
    setupSortHandlers();
    // Initialize reset button state
    updateResetButtonState(false);
});


// Initialize market cap slider
function initializeMarketCapSlider() {
    const container = document.getElementById('market-cap-slider');
    marketCapSlider = new MarketCapRangeSlider(container, {
        min: 0,
        max: 1000000000000, // 1 trillion
        currentMin: 0,
        currentMax: 1000000000000,
        onChange: (min, max) => {
            // Debounce the API call
            clearTimeout(window.marketCapTimeout);
            window.marketCapTimeout = setTimeout(() => {
                loadUpcomingCatalysts(1); // Reset to page 1
            }, 300);
        }
    });
}

// Initialize stock price slider
function initializeStockPriceSlider() {
    const container = document.getElementById('stock-price-slider');
    stockPriceSlider = new StockPriceRangeSlider(container, {
        min: 0,
        max: 1000, // $1000 max
        currentMin: 0,
        currentMax: 1000,
        onChange: (min, max) => {
            // Debounce the API call
            clearTimeout(window.stockPriceTimeout);
            window.stockPriceTimeout = setTimeout(() => {
                loadUpcomingCatalysts(1); // Reset to page 1
            }, 300);
        }
    });
}

// Handle time range filter changes
function handleTimeRangeChange() {
    const daysFilter = document.getElementById('days-filter').value;
    const customDateInputs = document.getElementById('custom-date-inputs');
    
    if (daysFilter === 'custom') {
        customDateInputs.style.display = 'flex';
        // Set default dates if not already set
        const startDate = document.getElementById('start-date');
        const endDate = document.getElementById('end-date');
        
        if (!startDate.value) {
            startDate.value = new Date().toISOString().split('T')[0]; // Today
        }
        if (!endDate.value) {
            const oneMonth = new Date();
            oneMonth.setMonth(oneMonth.getMonth() + 1);
            endDate.value = oneMonth.toISOString().split('T')[0]; // One month from today
        }
    } else {
        customDateInputs.style.display = 'none';
    }
    
    loadUpcomingCatalysts(1); // Reset to page 1
}

// Load upcoming catalysts
async function loadUpcomingCatalysts(page = 1) {
    const stageFilter = document.getElementById('stage-filter').value;
    const daysFilter = document.getElementById('days-filter').value;
    const searchTerm = document.getElementById('search-filter').value;
    
    // Get market cap range from slider
    const marketCapRange = marketCapSlider ? marketCapSlider.getValues() : { min: 0, max: 1000000000000 };
    
    // Get stock price range from slider
    const stockPriceRange = stockPriceSlider ? stockPriceSlider.getValues() : { min: 0, max: 1000 };
    
    document.getElementById('upcoming-loading').style.display = 'block';
    document.getElementById('upcoming-content').style.display = 'none';
    
    try {
        const params = new URLSearchParams({
            stage: stageFilter,
            search: searchTerm,
            sort_by: sortState.column,
            sort_dir: sortState.direction,
            page: page,
            per_page: 25
        });
        
        // Handle time range - either days or custom dates
        if (daysFilter === 'custom') {
            const startDate = document.getElementById('start-date').value;
            const endDate = document.getElementById('end-date').value;
            
            if (startDate) params.append('start_date', startDate);
            if (endDate) params.append('end_date', endDate);
        } else if (daysFilter) {
            params.append('days', daysFilter);
        }
        
        // Add market cap range parameters only if not full range
        if (marketCapRange.min > 0 || marketCapRange.max < 1000000000000) {
            params.append('min_marketcap', marketCapRange.min);
            params.append('max_marketcap', marketCapRange.max);
        }
        
        // Add stock price range parameters only if not full range
        if (stockPriceRange.min > 0 || stockPriceRange.max < 1000) {
            params.append('min_stockprice', stockPriceRange.min);
            params.append('max_stockprice', stockPriceRange.max);
        }
        
        const response = await fetch(`/api/catalysts/upcoming?${params}`);
        const data = await response.json();
        
        currentData = data.results;
        displayUpcomingCatalysts(data.results);
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
    
    // Update filter status
    updateFilterStatus();
    
    if (catalysts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No upcoming catalysts found</td></tr>';
        return;
    }
    
    tbody.innerHTML = catalysts.map(catalyst => {
        const stageClass = catalyst.stage.toLowerCase().replace(/\s+/g, '-');
        
        // Extract first indication
        let indication = '';
        if (catalyst.indications && catalyst.indications.length > 0) {
            const ind = catalyst.indications[0];
            indication = typeof ind === 'string' ? ind : ind.title || ind.indication_name || ind.name || '';
        }
        
        // Use catalyst_date_text or fallback to formatted date
        const displayDate = catalyst.catalyst_date_text || formatDate(catalyst.catalyst_date);
        
        // Create drug & indication column content
        const drugAndIndicationContent = `
            <div class="drug-name">${escapeHtml(catalyst.drug_name)}</div>
            ${indication ? `<div class="drug-indication">${escapeHtml(indication)}</div>` : ''}
        `;
        
        return `
            <tr class="catalyst-row" data-catalyst-id="${catalyst.id}" onclick="viewCatalystDetail(${catalyst.id})">
                <td class="date-cell">${escapeHtml(displayDate)}</td>
                <td><span class="ticker">${escapeHtml(catalyst.company.ticker)}</span></td>
                <td>${escapeHtml(catalyst.company.name)}</td>
                <td class="drug-indication-cell">${drugAndIndicationContent}</td>
                <td class="stage-cell"><span class="stage-badge ${stageClass}">${catalyst.stage}</span></td>
                <td class="market-cap">${formatMarketCap(catalyst.company.market_cap)}</td>
                <td class="price">${catalyst.company.stock_price ? '$' + catalyst.company.stock_price.toFixed(2) : 'N/A'}</td>
            </tr>
            ${catalyst.note ? `
            <tr class="note-row">
                <td colspan="7">
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
            
            // Reset to page 1 when sorting and reload data
            currentPage = 1;
            loadUpcomingCatalysts(1);
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

// Navigate to catalyst detail page
function viewCatalystDetail(catalystId) {
    window.location.href = `/catalyst/${catalystId}?id=${catalystId}`;
}

// Update filter status display
function updateFilterStatus() {
    const activeFilters = [];
    
    const stage = document.getElementById('stage-filter').value;
    if (stage) activeFilters.push(`Stage: ${stage}`);
    
    // Market cap range from slider
    if (marketCapSlider) {
        const range = marketCapSlider.getValues();
        if (range.min > 0 || range.max < 1000000000000) {
            const minStr = range.min.toLocaleString('en-US');
            const maxStr = range.max.toLocaleString('en-US');
            activeFilters.push(`Market Cap: $${minStr} - $${maxStr}`);
        }
    }
    
    // Stock price range from slider
    if (stockPriceSlider) {
        const range = stockPriceSlider.getValues();
        if (range.min > 0 || range.max < 1000) {
            const minStr = range.min.toLocaleString('en-US');
            const maxStr = range.max.toLocaleString('en-US');
            activeFilters.push(`Stock Price: $${minStr} - $${maxStr}`);
        }
    }
    
    const days = document.getElementById('days-filter').value;
    if (days === 'custom') {
        const startDate = document.getElementById('start-date').value;
        const endDate = document.getElementById('end-date').value;
        if (startDate || endDate) {
            const startStr = startDate ? new Date(startDate).toLocaleDateString() : 'Start';
            const endStr = endDate ? new Date(endDate).toLocaleDateString() : 'End';
            activeFilters.push(`Time: ${startStr} - ${endStr}`);
        }
    } else if (days) {
        const daysText = document.getElementById('days-filter').selectedOptions[0].text;
        activeFilters.push(`Time: ${daysText}`);
    }
    
    const search = document.getElementById('search-filter').value;
    if (search) activeFilters.push(`Search: "${search}"`);
    
    // Update or create filter status element
    let filterStatus = document.getElementById('filter-status');
    if (!filterStatus) {
        filterStatus = document.createElement('div');
        filterStatus.id = 'filter-status';
        filterStatus.className = 'filter-status';
        const filtersDiv = document.querySelector('.filters');
        filtersDiv.parentNode.insertBefore(filterStatus, filtersDiv.nextSibling);
    }
    
    if (activeFilters.length > 0) {
        filterStatus.innerHTML = `<strong>Active Filters:</strong> ${activeFilters.join(' | ')}`;
        filterStatus.style.display = 'block';
    } else {
        filterStatus.style.display = 'none';
    }
    
    // Update reset button state
    updateResetButtonState(activeFilters.length > 0);
}

// Reset all filters to default values
function resetAllFilters() {
    // Reset stage filter
    document.getElementById('stage-filter').value = '';
    
    // Reset time range filter
    document.getElementById('days-filter').value = '';
    document.getElementById('custom-date-inputs').style.display = 'none';
    document.getElementById('start-date').value = '';
    document.getElementById('end-date').value = '';
    
    // Reset search filter
    document.getElementById('search-filter').value = '';
    
    // Reset market cap slider
    if (marketCapSlider) {
        marketCapSlider.setValues(0, 1000000000000);
    }
    
    // Reset stock price slider
    if (stockPriceSlider) {
        stockPriceSlider.setValues(0, 1000);
    }
    
    // Reload catalysts with default filters
    loadUpcomingCatalysts(1);
}

// Update reset button state based on whether filters are active
function updateResetButtonState(hasActiveFilters) {
    const resetButton = document.getElementById('reset-all-filters');
    if (resetButton) {
        resetButton.disabled = !hasActiveFilters;
        if (hasActiveFilters) {
            resetButton.classList.remove('disabled');
        } else {
            resetButton.classList.add('disabled');
        }
    }
}

