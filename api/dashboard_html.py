# api/dashboard_html.py
"""
HTML template generator for the dashboard interface.
Contains the enhanced dashboard HTML with watchlist functionality.
"""


def get_enhanced_dashboard_html() -> str:
    """
    Get enhanced dashboard HTML with watchlist functionality.
    
    Returns:
        Complete HTML string for the dashboard interface
    """
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DEX Sniping Dashboard</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                color: white;
                min-height: 100vh;
                padding: 20px;
            }
            .container { max-width: 1400px; margin: 0 auto; }
            .header {
                text-align: center;
                margin-bottom: 30px;
                padding: 20px;
                background: rgba(255,255,255,0.1);
                border-radius: 10px;
                backdrop-filter: blur(10px);
            }
            .main-grid {
                display: grid;
                grid-template-columns: 2fr 1fr;
                gap: 20px;
                margin-bottom: 20px;
            }
            .left-panel, .right-panel {
                display: flex;
                flex-direction: column;
                gap: 20px;
            }
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
            }
            .stat-card {
                background: rgba(255,255,255,0.1);
                padding: 15px;
                border-radius: 10px;
                text-align: center;
                backdrop-filter: blur(10px);
            }
            .stat-value { font-size: 1.8em; font-weight: bold; color: #4CAF50; }
            .stat-label { margin-top: 5px; opacity: 0.8; font-size: 0.9em; }
            
            .opportunities, .watchlist-panel {
                background: rgba(255,255,255,0.1);
                border-radius: 10px;
                padding: 20px;
                backdrop-filter: blur(10px);
            }
            
            .section-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
                padding-bottom: 10px;
                border-bottom: 1px solid rgba(255,255,255,0.2);
            }
            
            .section-title {
                font-size: 1.2em;
                font-weight: bold;
            }
            
            .controls {
                display: flex;
                gap: 8px;
            }
            
            .action-btn {
                padding: 6px 12px;
                border: none;
                border-radius: 6px;
                background: rgba(33, 150, 243, 0.8);
                color: white;
                cursor: pointer;
                font-size: 12px;
                transition: all 0.3s ease;
            }
            .action-btn:hover {
                background: rgba(33, 150, 243, 1);
                transform: translateY(-1px);
            }
            .action-btn.success { background: rgba(76, 175, 80, 0.8); }
            .action-btn.success:hover { background: rgba(76, 175, 80, 1); }
            .action-btn.danger { background: rgba(244, 67, 54, 0.8); }
            .action-btn.danger:hover { background: rgba(244, 67, 54, 1); }
            
            .opportunity-item, .watchlist-item {
                background: rgba(255,255,255,0.1);
                margin: 8px 0;
                padding: 12px;
                border-radius: 8px;
                border-left: 4px solid #4CAF50;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            .opportunity-item:hover, .watchlist-item:hover {
                background: rgba(255,255,255,0.2);
                transform: translateY(-1px);
            }
            
            .watchlist-item {
                border-left-color: #2196F3;
            }
            
            .item-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }
            
            .token-symbol {
                font-size: 1.1em;
                font-weight: bold;
                color: #4CAF50;
            }
            
            .watchlist-item .token-symbol {
                color: #2196F3;
            }
            
            .risk-badge {
                padding: 3px 6px;
                border-radius: 12px;
                font-size: 10px;
                font-weight: bold;
                text-transform: uppercase;
            }
            .risk-low { background: rgba(76, 175, 80, 0.3); color: #4CAF50; }
            .risk-medium { background: rgba(255, 193, 7, 0.3); color: #FFC107; }
            .risk-high { background: rgba(244, 67, 54, 0.3); color: #F44336; }
            .risk-critical { background: rgba(139, 0, 0, 0.3); color: #8B0000; }
            .risk-unknown { background: rgba(158, 158, 158, 0.3); color: #9E9E9E; }
            
            .item-details {
                font-size: 0.85em;
                opacity: 0.9;
                line-height: 1.4;
            }
            
            .chain-badge {
                display: inline-block;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 9px;
                margin-right: 6px;
                background: rgba(33, 150, 243, 0.3);
                color: #2196F3;
            }
            
            .recommendation {
                display: inline-block;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 9px;
                margin-left: 6px;
                font-weight: bold;
            }
            .rec-strong-buy { background: rgba(76, 175, 80, 0.3); color: #4CAF50; }
            .rec-buy { background: rgba(33, 150, 243, 0.3); color: #2196F3; }
            .rec-small-buy { background: rgba(33, 150, 243, 0.2); color: #2196F3; }
            .rec-watch { background: rgba(255, 193, 7, 0.3); color: #FFC107; }
            .rec-avoid { background: rgba(244, 67, 54, 0.3); color: #F44336; }
            .rec-unknown { background: rgba(158, 158, 158, 0.3); color: #9E9E9E; }
            
            .item-actions {
                margin-top: 8px;
                display: flex;
                gap: 6px;
            }
            
            .connection-status {
                position: fixed;
                top: 10px;
                right: 10px;
                padding: 8px 12px;
                border-radius: 5px;
                font-size: 12px;
                z-index: 999;
            }
            .connected { background: #4CAF50; }
            .disconnected { background: #f44336; }
            
            /* Modal Styles */
            .modal-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.8);
                backdrop-filter: blur(5px);
                z-index: 1000;
                display: none;
                justify-content: center;
                align-items: center;
                animation: fadeIn 0.3s ease;
            }
            .modal-overlay.show { display: flex; }
            .modal-content {
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                max-width: 600px;
                max-height: 90vh;
                width: 90%;
                overflow-y: auto;
                animation: slideIn 0.3s ease;
            }
            .modal-header {
                padding: 20px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .modal-header h2 {
                margin: 0;
                color: #4CAF50;
                font-size: 20px;
            }
            .modal-close {
                background: none;
                border: none;
                color: white;
                font-size: 24px;
                cursor: pointer;
                padding: 0;
                width: 30px;
                height: 30px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: background 0.3s ease;
            }
            .modal-close:hover {
                background: rgba(255, 255, 255, 0.1);
            }
            .modal-body {
                padding: 20px;
            }
            .form-group {
                margin-bottom: 15px;
            }
            .form-group label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            .form-group input, .form-group textarea, .form-group select {
                width: 100%;
                padding: 8px 12px;
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 6px;
                background: rgba(255, 255, 255, 0.1);
                color: white;
                font-size: 14px;
            }
            .form-group input::placeholder, .form-group textarea::placeholder {
                color: rgba(255, 255, 255, 0.5);
            }
            .form-group textarea {
                resize: vertical;
                min-height: 60px;
            }
            
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            @keyframes slideIn {
                from { transform: translateY(-50px); opacity: 0; }
                to { transform: translateY(0); opacity: 1; }
            }
            
            @media (max-width: 1024px) {
                .main-grid {
                    grid-template-columns: 1fr;
                }
                .stats {
                    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>DEX Sniping Dashboard v2.0</h1>
                <p>Real-time multi-chain token monitoring with intelligent analysis & watchlist</p>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-value" id="total-opportunities">0</div>
                    <div class="stat-label">Total Opportunities</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="high-confidence">0</div>
                    <div class="stat-label">High Confidence</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="analysis-rate">0</div>
                    <div class="stat-label">Analysis/Min</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="connected-clients">0</div>
                    <div class="stat-label">Connected Clients</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="watchlist-count">0</div>
                    <div class="stat-label">Watchlist Items</div>
                </div>
            </div>
            
            <div class="main-grid">
                <div class="left-panel">
                    <div class="opportunities">
                        <div class="section-header">
                            <span class="section-title">Live Opportunities</span>
                            <div class="controls">
                                <button class="action-btn" onclick="clearOpportunities()">Clear</button>
                            </div>
                        </div>
                        <div id="opportunity-list">
                            <p>Connecting to live feed...</p>
                        </div>
                    </div>
                </div>
                
                <div class="right-panel">
                    <div class="watchlist-panel">
                        <div class="section-header">
                            <span class="section-title">Watchlist</span>
                            <div class="controls">
                                <button class="action-btn success" onclick="showAddToWatchlistModal()">Add</button>
                                <button class="action-btn" onclick="refreshWatchlist()">Refresh</button>
                                <button class="action-btn danger" onclick="clearWatchlist()">Clear</button>
                            </div>
                        </div>
                        <div id="watchlist-list">
                            <p>Loading watchlist...</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div id="connection-status" class="connection-status disconnected">
            Connecting...
        </div>
        
        <!-- Add to Watchlist Modal -->
        <div id="add-watchlist-modal" class="modal-overlay">
            <div class="modal-content">
                <div class="modal-header">
                    <h2>Add to Watchlist</h2>
                    <button class="modal-close" onclick="closeAddWatchlistModal()">&times;</button>
                </div>
                <div class="modal-body">
                    <form onsubmit="submitAddToWatchlist(event)">
                        <div class="form-group">
                            <label for="watchlist-token-address">Token Address *</label>
                            <input type="text" id="watchlist-token-address" required 
                                   placeholder="0x... or Solana address">
                        </div>
                        <div class="form-group">
                            <label for="watchlist-token-symbol">Token Symbol *</label>
                            <input type="text" id="watchlist-token-symbol" required 
                                   placeholder="e.g., DOGE, PEPE">
                        </div>
                        <div class="form-group">
                            <label for="watchlist-chain">Chain *</label>
                            <select id="watchlist-chain" required>
                                <option value="ETHEREUM">Ethereum</option>
                                <option value="BASE">Base</option>
                                <option value="SOLANA">Solana</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="watchlist-reason">Reason</label>
                            <input type="text" id="watchlist-reason" 
                                   placeholder="Why are you watching this token?">
                        </div>
                        <div class="form-group">
                            <label for="watchlist-target-price">Target Price (USD)</label>
                            <input type="number" id="watchlist-target-price" step="0.000001" 
                                   placeholder="0.001">
                        </div>
                        <div class="form-group">
                            <label for="watchlist-stop-loss">Stop Loss (USD)</label>
                            <input type="number" id="watchlist-stop-loss" step="0.000001" 
                                   placeholder="0.0005">
                        </div>
                        <div class="form-group">
                            <label for="watchlist-notes">Notes</label>
                            <textarea id="watchlist-notes" 
                                      placeholder="Additional notes or analysis..."></textarea>
                        </div>
                        <div class="controls">
                            <button type="submit" class="action-btn success">Add to Watchlist</button>
                            <button type="button" class="action-btn" onclick="closeAddWatchlistModal()">Cancel</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
        
        <script>
            let ws = null;
            let reconnectAttempts = 0;
            const maxReconnectAttempts = 5;
            let opportunities = [];
            let watchlist = [];
            
            // WebSocket connection
            function connectWebSocket() {
                try {
                    ws = new WebSocket('ws://localhost:8000/ws');
                    
                    ws.onopen = function() {
                        console.log('WebSocket connected');
                        updateConnectionStatus(true);
                        reconnectAttempts = 0;
                    };
                    
                    ws.onmessage = function(event) {
                        try {
                            const data = JSON.parse(event.data);
                            handleWebSocketMessage(data);
                        } catch (e) {
                            console.error('Error parsing message:', e);
                        }
                    };
                    
                    ws.onclose = function() {
                        console.log('WebSocket disconnected');
                        updateConnectionStatus(false);
                        
                        if (reconnectAttempts < maxReconnectAttempts) {
                            reconnectAttempts++;
                            setTimeout(connectWebSocket, 3000 * reconnectAttempts);
                        }
                    };
                    
                    ws.onerror = function(error) {
                        console.error('WebSocket error:', error);
                        updateConnectionStatus(false);
                    };
                    
                } catch (error) {
                    console.error('WebSocket connection error:', error);
                    updateConnectionStatus(false);
                }
            }
            
            function handleWebSocketMessage(data) {
                try {
                    // Debug logging to see what we're receiving
                    if (data.type === 'new_opportunity') {
                        console.log('Received opportunity data:', data.data);
                        console.log('Liquidity USD type:', typeof data.data.liquidity_usd, 'Value:', data.data.liquidity_usd);
                    }
                    
                    switch (data.type) {
                        case 'new_opportunity':
                            addOpportunityToList(data.data);
                            break;
                        case 'stats_update':
                            updateStats(data.data);
                            break;
                        case 'watchlist_updated':
                            refreshWatchlist();
                            break;
                        case 'connected':
                            console.log('WebSocket connection confirmed');
                            break;
                        case 'heartbeat':
                            // Ignore heartbeat messages
                            break;
                        default:
                            console.log('Unknown message type:', data.type, data);
                    }
                } catch (error) {
                    console.error('Error handling WebSocket message:', error);
                    console.error('Message data:', data);
                }
            }
            
            function addOpportunityToList(opportunity) {
                try {
                    const list = document.getElementById('opportunity-list');
                    
                    opportunities.unshift(opportunity);
                    if (opportunities.length > 20) {
                        opportunities.pop();
                    }
                    
                    const item = document.createElement('div');
                    item.className = 'opportunity-item';
                    
                    // Safely extract values with proper fallbacks
                    const tokenSymbol = opportunity.token_symbol || 'UNKNOWN';
                    const tokenAddress = opportunity.token_address || '';
                    const chain = opportunity.chain || 'unknown';
                    const riskLevel = opportunity.risk_level || 'unknown';
                    const recommendation = opportunity.recommendation || 'UNKNOWN';
                    const confidence = opportunity.confidence || 'UNKNOWN';
                    const score = parseFloat(opportunity.score) || 0;
                    const liquidityUsd = parseFloat(opportunity.liquidity_usd) || 0;
                    const dexName = opportunity.dex_name || 'Unknown DEX';
                    const detectedAt = opportunity.detected_at ? new Date(opportunity.detected_at) : new Date();
                    
                    // Format liquidity value nicely
                    let liquidityDisplay;
                    if (liquidityUsd >= 1000000) {
                        liquidityDisplay = `${(liquidityUsd / 1000000).toFixed(2)}M`;
                    } else if (liquidityUsd >= 1000) {
                        liquidityDisplay = `${(liquidityUsd / 1000).toFixed(1)}K`;
                    } else if (liquidityUsd > 0) {
                        liquidityDisplay = `${liquidityUsd.toFixed(2)}`;
                    } else {
                        liquidityDisplay = 'Unknown';
                    }
                    
                    // Calculate age
                    const ageMinutes = Math.floor((Date.now() - detectedAt.getTime()) / 60000);
                    const ageDisplay = ageMinutes < 60 ? `${ageMinutes}m` : `${Math.floor(ageMinutes / 60)}h`;
                    
                    // Clean recommendation for CSS class
                    const recClass = recommendation.toLowerCase().replace(/[^a-z]/g, '-');
                    
                    item.innerHTML = `
                        <div class="item-header">
                            <span class="token-symbol">${escapeHtml(tokenSymbol)}</span>
                            <span class="risk-badge risk-${riskLevel}">${riskLevel.toUpperCase()}</span>
                        </div>
                        <div class="item-details">
                            <span class="chain-badge">${chain.toUpperCase()}</span>
                            <strong>${escapeHtml(dexName)}</strong><br>
                            Rec: <span class="recommendation rec-${recClass}">${recommendation}</span>
                            (${confidence})<br>
                            Score: ${score.toFixed(2)} | Liquidity: ${liquidityDisplay}<br>
                            <small>Age: ${ageDisplay} | ${detectedAt.toLocaleTimeString()}</small>
                        </div>
                        <div class="item-actions">
                            <button class="action-btn success" onclick="addOpportunityToWatchlist('${escapeHtml(tokenAddress)}', '${escapeHtml(tokenSymbol)}', '${escapeHtml(chain)}')">Watch</button>
                            <button class="action-btn" onclick="executeTrade('${escapeHtml(tokenSymbol)}')">Trade</button>
                        </div>
                    `;
                    
                    list.insertBefore(item, list.firstChild);
                    
                    // Keep only last 10 opportunities visible
                    while (list.children.length > 10) {
                        list.removeChild(list.lastChild);
                    }
                    
                } catch (error) {
                    console.error('Error adding opportunity:', error);
                    console.error('Opportunity data:', opportunity);
                }
            }
            
            // Helper function to escape HTML to prevent XSS
            function escapeHtml(text) {
                if (typeof text !== 'string') {
                    return String(text || '');
                }
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }
            
            // Watchlist functions
            async function refreshWatchlist() {
                try {
                    const response = await fetch('/api/watchlist');
                    const data = await response.json();
                    watchlist = data.items || [];
                    renderWatchlist();
                    updateWatchlistCount();
                } catch (error) {
                    console.error('Error refreshing watchlist:', error);
                    showNotification('Error refreshing watchlist', 'error');
                }
            }
            
            function renderWatchlist() {
                try {
                    const list = document.getElementById('watchlist-list');
                    
                    if (watchlist.length === 0) {
                        list.innerHTML = '<p>No tokens in watchlist...</p>';
                        return;
                    }
                    
                    list.innerHTML = '';
                    
                    watchlist.forEach(item => {
                        const div = document.createElement('div');
                        div.className = 'watchlist-item';
                        
                        const addedAt = new Date(item.added_at);
                        const targetPrice = item.target_price ? `$${item.target_price}` : 'N/A';
                        
                        div.innerHTML = `
                            <div class="item-header">
                                <span class="token-symbol">${item.token_symbol}</span>
                                <span class="chain-badge">${item.chain}</span>
                            </div>
                            <div class="item-details">
                                Target: ${targetPrice} | Status: ${item.status}<br>
                                <small>Added: ${addedAt.toLocaleDateString()}</small><br>
                                <small>${item.reason}</small>
                            </div>
                            <div class="item-actions">
                                <button class="action-btn danger" onclick="removeFromWatchlist('${item.token_address}', '${item.chain}')">Remove</button>
                            </div>
                        `;
                        
                        list.appendChild(div);
                    });
                } catch (error) {
                    console.error('Error rendering watchlist:', error);
                }
            }
            
            function showAddToWatchlistModal() {
                document.getElementById('add-watchlist-modal').classList.add('show');
            }
            
            function closeAddWatchlistModal() {
                document.getElementById('add-watchlist-modal').classList.remove('show');
                // Clear form
                document.getElementById('watchlist-token-address').value = '';
                document.getElementById('watchlist-token-symbol').value = '';
                document.getElementById('watchlist-reason').value = '';
                document.getElementById('watchlist-target-price').value = '';
                document.getElementById('watchlist-stop-loss').value = '';
                document.getElementById('watchlist-notes').value = '';
            }
            
            async function submitAddToWatchlist(event) {
                event.preventDefault();
                
                try {
                    const formData = {
                        token_address: document.getElementById('watchlist-token-address').value,
                        token_symbol: document.getElementById('watchlist-token-symbol').value,
                        chain: document.getElementById('watchlist-chain').value,
                        reason: document.getElementById('watchlist-reason').value || 'Manual addition',
                        target_price: document.getElementById('watchlist-target-price').value ? 
                                     parseFloat(document.getElementById('watchlist-target-price').value) : null,
                        stop_loss: document.getElementById('watchlist-stop-loss').value ? 
                                  parseFloat(document.getElementById('watchlist-stop-loss').value) : null,
                        notes: document.getElementById('watchlist-notes').value
                    };
                    
                    const response = await fetch('/api/watchlist/add', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(formData)
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        showNotification('Added to watchlist successfully', 'success');
                        closeAddWatchlistModal();
                        refreshWatchlist();
                    } else {
                        showNotification(result.message || 'Failed to add to watchlist', 'error');
                    }
                } catch (error) {
                    console.error('Error adding to watchlist:', error);
                    showNotification('Error adding to watchlist', 'error');
                }
            }
            
            async function addOpportunityToWatchlist(tokenAddress, tokenSymbol, chain) {
                try {
                    const formData = {
                        token_address: tokenAddress,
                        token_symbol: tokenSymbol,
                        chain: chain,
                        reason: 'Added from opportunity'
                    };
                    
                    const response = await fetch('/api/watchlist/add', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(formData)
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        showNotification(`${tokenSymbol} added to watchlist`, 'success');
                        refreshWatchlist();
                    } else {
                        showNotification(result.message || 'Failed to add to watchlist', 'error');
                    }
                } catch (error) {
                    console.error('Error adding to watchlist:', error);
                    showNotification('Error adding to watchlist', 'error');
                }
            }
            
            async function removeFromWatchlist(tokenAddress, chain) {
                try {
                    const response = await fetch(`/api/watchlist/remove?token_address=${encodeURIComponent(tokenAddress)}&chain=${encodeURIComponent(chain)}`, {
                        method: 'DELETE'
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        showNotification('Removed from watchlist', 'success');
                        refreshWatchlist();
                    } else {
                        showNotification(result.message || 'Failed to remove from watchlist', 'error');
                    }
                } catch (error) {
                    console.error('Error removing from watchlist:', error);
                    showNotification('Error removing from watchlist', 'error');
                }
            }
            
            async function clearWatchlist() {
                if (confirm('Are you sure you want to clear the entire watchlist?')) {
                    try {
                        for (const item of watchlist) {
                            await removeFromWatchlist(item.token_address, item.chain);
                        }
                        showNotification('Watchlist cleared', 'success');
                    } catch (error) {
                        console.error('Error clearing watchlist:', error);
                        showNotification('Error clearing watchlist', 'error');
                    }
                }
            }
            
            function updateWatchlistCount() {
                document.getElementById('watchlist-count').textContent = watchlist.length;
            }
            
            // Utility functions
            function clearOpportunities() {
                document.getElementById('opportunity-list').innerHTML = '<p>Opportunities cleared...</p>';
                opportunities = [];
            }
            
            function executeTrade(tokenSymbol) {
                showNotification(`Trade execution for ${tokenSymbol} - Feature coming soon!`, 'info');
            }
            
            function updateStats(stats) {
                try {
                    if (stats.analysis_rate !== undefined) {
                        document.getElementById('analysis-rate').textContent = stats.analysis_rate;
                    }
                } catch (error) {
                    console.error('Error updating stats:', error);
                }
            }
            
            function updateConnectionStatus(connected) {
                try {
                    const statusEl = document.getElementById('connection-status');
                    if (connected) {
                        statusEl.textContent = 'Connected';
                        statusEl.className = 'connection-status connected';
                    } else {
                        statusEl.textContent = 'Disconnected';
                        statusEl.className = 'connection-status disconnected';
                    }
                } catch (error) {
                    console.error('Error updating connection status:', error);
                }
            }
            
            function showNotification(message, type = 'info') {
                try {
                    const notification = document.createElement('div');
                    const bgColor = type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3';
                    
                    notification.style.cssText = `
                        position: fixed;
                        top: 70px;
                        right: 20px;
                        background: ${bgColor};
                        color: white;
                        padding: 10px 20px;
                        border-radius: 5px;
                        z-index: 1001;
                        animation: slideInRight 0.3s ease;
                        max-width: 300px;
                        word-wrap: break-word;
                    `;
                    notification.textContent = message;
                    document.body.appendChild(notification);
                    
                    setTimeout(() => {
                        if (notification.parentNode) {
                            notification.remove();
                        }
                    }, 3000);
                } catch (error) {
                    console.error('Error showing notification:', error);
                }
            }
            
            // Fetch initial data
            async function fetchStats() {
                try {
                    const response = await fetch('/api/stats');
                    const stats = await response.json();
                    
                    document.getElementById('total-opportunities').textContent = stats.total_opportunities || 0;
                    document.getElementById('high-confidence').textContent = stats.high_confidence || 0;
                    document.getElementById('analysis-rate').textContent = stats.analysis_rate || 0;
                    document.getElementById('connected-clients').textContent = stats.connected_clients || 0;
                    
                } catch (error) {
                    console.error('Error fetching stats:', error);
                }
            }
            
            // Close modals when clicking outside
            document.getElementById('add-watchlist-modal').addEventListener('click', function(e) {
                if (e.target === this) {
                    closeAddWatchlistModal();
                }
            });
            
            // Initialize
            try {
                connectWebSocket();
                fetchStats();
                refreshWatchlist();
                setInterval(fetchStats, 10000);
                setInterval(refreshWatchlist, 30000); // Refresh watchlist every 30s
            } catch (error) {
                console.error('Error during initialization:', error);
            }
        </script>
    </body>
    </html>
    """