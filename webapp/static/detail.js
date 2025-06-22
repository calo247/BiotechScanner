// Catalyst detail page JavaScript
document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    const catalystId = urlParams.get('id');

    if (!catalystId) {
        document.getElementById('detail-loading').innerHTML = 'No catalyst ID provided';
        return;
    }

    loadCatalystDetail(catalystId);
});

async function loadCatalystDetail(id) {
    try {
        const response = await fetch(`/api/catalysts/${id}`);
        
        if (!response.ok) {
            throw new Error('Catalyst not found');
        }
        
        const catalyst = await response.json();
        displayCatalystDetail(catalyst);
        
    } catch (error) {
        console.error('Error loading catalyst:', error);
        document.getElementById('detail-loading').innerHTML = `Error: ${error.message}`;
    }
}

function displayCatalystDetail(catalyst) {
    const content = document.getElementById('detail-content');
    
    // Format indications
    let indicationsHtml = '';
    if (catalyst.indications && catalyst.indications.length > 0) {
        indicationsHtml = catalyst.indications.map(ind => {
            const name = typeof ind === 'string' ? ind : (ind.title || ind.indication_name || ind.name || 'Unknown');
            return `<span class="indication-tag">${escapeHtml(name)}</span>`;
        }).join('');
    } else if (catalyst.indications_text) {
        indicationsHtml = `<span class="indication-tag">${escapeHtml(catalyst.indications_text)}</span>`;
    }

    // Format stock data
    const stockData = catalyst.stock_data?.current || {};
    const marketCap = formatMarketCap(stockData.market_cap);
    const stockPrice = stockData.price ? '$' + stockData.price.toFixed(2) : 'N/A';
    const volume = stockData.volume ? stockData.volume.toLocaleString() : 'N/A';

    content.innerHTML = `
        <div class="catalyst-detail-card">
            <div class="detail-header-info">
                <div class="company-info">
                    <h1>${escapeHtml(catalyst.company.name)}</h1>
                    <span class="ticker-large">${escapeHtml(catalyst.company.ticker)}</span>
                </div>
                <div class="stage-info">
                    <span class="stage-badge ${catalyst.stage.toLowerCase().replace(/\s+/g, '-')}">${escapeHtml(catalyst.stage)}</span>
                </div>
            </div>

            <div class="detail-sections">
                <section class="drug-section">
                    <h2>Drug Information</h2>
                    <div class="info-grid">
                        <div class="info-item">
                            <label>Drug Name:</label>
                            <span>${escapeHtml(catalyst.drug_name)}</span>
                        </div>
                        <div class="info-item">
                            <label>Development Stage:</label>
                            <span>${escapeHtml(catalyst.stage_event_label || catalyst.stage)}</span>
                        </div>
                        <div class="info-item">
                            <label>Indications:</label>
                            <div class="indications-container">
                                ${indicationsHtml || '<span class="no-data">Not specified</span>'}
                            </div>
                        </div>
                        <div class="info-item mechanism">
                            <label>Mechanism of Action:</label>
                            <span>${escapeHtml(stripRichText(catalyst.mechanism_of_action) || 'Not specified')}</span>
                        </div>
                    </div>
                </section>

                <section class="catalyst-section">
                    <h2>Catalyst Event</h2>
                    <div class="info-grid">
                        <div class="info-item">
                            <label>Catalyst Date:</label>
                            <span class="catalyst-date">${escapeHtml(catalyst.catalyst_date_text || 'TBA')}</span>
                        </div>
                        <div class="info-item full-width">
                            <label>Catalyst Notes:</label>
                            <div class="catalyst-notes">
                                ${formatNoteWithDateBreaks(catalyst.note) || '<span class="no-data">No additional notes</span>'}
                            </div>
                        </div>
                        ${catalyst.catalyst_source ? `
                        <div class="info-item full-width">
                            <label>Source:</label>
                            <a href="${escapeHtml(catalyst.catalyst_source)}" target="_blank" class="source-link">View Source</a>
                        </div>
                        ` : ''}
                    </div>
                </section>

                <section class="market-section">
                    <h2>Market Information</h2>
                    <div class="info-grid">
                        <div class="info-item">
                            <label>Stock Price:</label>
                            <span class="price">${stockPrice}</span>
                        </div>
                        <div class="info-item">
                            <label>Market Cap:</label>
                            <span class="market-cap">${marketCap}</span>
                        </div>
                        <div class="info-item">
                            <label>Volume:</label>
                            <span>${volume}</span>
                        </div>
                        ${catalyst.financial_data && catalyst.financial_data.cash_balance ? `
                        <div class="info-item">
                            <label>Cash Balance:</label>
                            <span class="cash-balance">${formatCashBalance(catalyst.financial_data.cash_balance)} <small>(${catalyst.financial_data.cash_balance_period})</small></span>
                        </div>
                        ` : ''}
                        ${stockData.pe_ratio ? `
                        <div class="info-item">
                            <label>P/E Ratio:</label>
                            <span>${stockData.pe_ratio.toFixed(2)}</span>
                        </div>
                        ` : ''}
                        ${stockData.week_52_high && stockData.week_52_low ? `
                        <div class="info-item">
                            <label>52W Range:</label>
                            <span>$${stockData.week_52_low.toFixed(2)} - $${stockData.week_52_high.toFixed(2)}</span>
                        </div>
                        ` : ''}
                        ${catalyst.market_info ? `
                        <div class="info-item full-width">
                            <label>Market Info:</label>
                            <span>${escapeHtml(catalyst.market_info)}</span>
                        </div>
                        ` : ''}
                    </div>
                </section>

                ${catalyst.ai_report ? `
                <section class="ai-analysis-section">
                    <h2>AI Analysis Report</h2>
                    <div class="ai-report-container">
                        <div class="ai-report-header">
                            <div class="report-meta">
                                <span class="report-date">Generated: ${formatDate(catalyst.ai_report.created_at)}</span>
                                ${catalyst.ai_report.recommendation ? `<span class="recommendation-badge">${escapeHtml(catalyst.ai_report.recommendation)}</span>` : ''}
                                ${catalyst.ai_report.success_probability ? `<span class="success-prob">${(catalyst.ai_report.success_probability * 100).toFixed(0)}% Success</span>` : ''}
                            </div>
                        </div>
                        <div class="ai-report-content">
                            <div class="report-metrics">
                                ${catalyst.ai_report.price_target_upside ? `<div class="metric"><label>Upside:</label> <span class="upside">${escapeHtml(catalyst.ai_report.price_target_upside)}</span></div>` : ''}
                                ${catalyst.ai_report.price_target_downside ? `<div class="metric"><label>Downside:</label> <span class="downside">${escapeHtml(catalyst.ai_report.price_target_downside)}</span></div>` : ''}
                                ${catalyst.ai_report.risk_level ? `<div class="metric"><label>Risk Level:</label> <span class="risk-${catalyst.ai_report.risk_level.toLowerCase()}">${escapeHtml(catalyst.ai_report.risk_level)}</span></div>` : ''}
                            </div>
                            <div class="report-markdown">
                                ${renderMarkdown(catalyst.ai_report.report_markdown)}
                            </div>
                        </div>
                    </div>
                </section>
                ` : `
                <section class="ai-analysis-section">
                    <h2>AI Analysis Report</h2>
                    <div class="no-reports">
                        <p>No AI analysis report available for this catalyst yet.</p>
                        <p class="generate-hint">To generate an AI analysis report, use the command line tool:</p>
                        <code class="command-example">python3 analyze_catalyst.py --id ${catalyst.id}</code>
                    </div>
                </section>
                `}
            </div>
        </div>
    `;

    document.getElementById('detail-loading').style.display = 'none';
    document.getElementById('detail-content').style.display = 'block';
}

function goBack() {
    window.history.back();
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function stripRichText(text) {
    if (!text) return '';
    
    // Create a temporary div to parse HTML
    const div = document.createElement('div');
    div.innerHTML = text;
    
    // Get text content only (strips all HTML tags)
    let cleanText = div.textContent || div.innerText || '';
    
    // Clean up common rich text artifacts
    cleanText = cleanText
        .replace(/\s+/g, ' ')  // Multiple spaces to single space
        .replace(/^\s+|\s+$/g, '')  // Trim whitespace
        .replace(/\n+/g, ' ')  // Replace newlines with spaces
        .replace(/\t+/g, ' ');  // Replace tabs with spaces
    
    return cleanText;
}

function formatNoteWithDateBreaks(note) {
    if (!note) return '';
    return escapeHtml(note).replace(/(\b\d{1,2}\/\d{1,2}\/\d{2,4})/g, '<br><strong>$1</strong>').replace(/^<br>/, '');
}

function formatMarketCap(value) {
    if (!value) return 'N/A';
    if (value >= 1e9) return '$' + (value / 1e9).toFixed(1) + 'B';
    if (value >= 1e6) return '$' + (value / 1e6).toFixed(1) + 'M';
    return '$' + value.toFixed(0);
}

function formatCashBalance(value) {
    if (!value && value !== 0) return 'N/A';
    if (value >= 1e9) return '$' + (value / 1e9).toFixed(2) + 'B';
    if (value >= 1e6) return '$' + (value / 1e6).toFixed(1) + 'M';
    if (value >= 1e3) return '$' + (value / 1e3).toFixed(0) + 'K';
    return '$' + value.toFixed(0);
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}


function renderMarkdown(markdown) {
    if (!markdown) return '';
    
    // Basic markdown rendering
    let html = escapeHtml(markdown);
    
    // Headers
    html = html.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.*?)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.*?)$/gm, '<h1>$1</h1>');
    
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Italic
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    // Lists
    html = html.replace(/^- (.*?)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
    html = html.replace(/^\d+\. (.*?)$/gm, '<li>$1</li>');
    
    // Paragraphs
    html = html.replace(/\n\n/g, '</p><p>');
    html = '<p>' + html + '</p>';
    
    // Line breaks
    html = html.replace(/\n/g, '<br>');
    
    // Clean up empty paragraphs
    html = html.replace(/<p><\/p>/g, '');
    html = html.replace(/<p><br>/g, '<p>');
    
    return html;
}