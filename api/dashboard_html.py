# api/dashboard_html.py
"""
HTML template generator for the dashboard interface.
Contains the enhanced dashboard HTML with watchlist functionality.
"""

import time
from typing import Optional


def get_enhanced_dashboard_html() -> str:
    """
    Get enhanced dashboard HTML with watchlist functionality.
    
    Returns:
        Complete HTML string for the dashboard interface
    
    Raises:
        Exception: If template generation fails
    """
    try:
        # Add cache busting timestamp
        cache_bust = int(time.time())
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DEX Sniping Dashboard v2.1.{cache_bust}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            backdrop-filter: blur(10px);
        }}
        .main-grid {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }}
        .left-panel, .right-panel {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }}
        .stat-card {{
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            backdrop-filter: blur(10px);
        }}
        .stat-value {{ font-size: 1.8em; font-weight: bold; color: #4CAF50; }}
        .stat-label {{ margin-top: 5px; opacity: 0.8; font-size: 0.9em; }}
        
        .opportunities, .watchlist-panel {{
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 20px;
            backdrop-filter: blur(10px);
        }}
        
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.2);
        }}
        
        .section-title {{
            font-size: 1.2em;
            font-weight: bold;
        }}
        
        .controls {{
            display: flex;
            gap: 8px;
        }}
        
        .action-btn {{
            padding: 6px 12px;
            border: none;
            border-radius: 6px;
            background: rgba(33, 150, 243, 0.8);
            color: white;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.3s ease;
        }}
        .action-btn:hover {{
            background: rgba(33, 150, 243, 1);
            transform: translateY(-1px);
        }}
        .action-btn.success {{ background: rgba(76, 175, 80, 0.8); }}
        .action-btn.success:hover {{ background: rgba(76, 175, 80, 1); }}
        .action-btn.danger {{ background: rgba(244, 67, 54, 0.8); }}
        .action-btn.danger:hover {{ background: rgba(244, 67, 54, 1); }}
        
        .opportunity-item, .watchlist-item {{
            background: rgba(255,255,255,0.1);
            margin: 8px 0;
            padding: 12px;
            border-radius: 8px;
            border-left: 4px solid #4CAF50;
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        .opportunity-item:hover, .watchlist-item:hover {{
            background: rgba(255,255,255,0.2);
            transform: translateY(-1px);
        }}
        
        .watchlist-item {{
            border-left-color: #2196F3;
        }}
        
        .item-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}
        
        .token-symbol {{
            font-size: 1.1em;
            font-weight: bold;
            color: #4CAF50;
        }}
        
        .watchlist-item .token-symbol {{
            color: #2196F3;
        }}
        
        .risk-badge {{
            padding: 3px 6px;
            border-radius: 12px;
            font-size: 10px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .risk-low {{ background: rgba(76, 175, 80, 0.3); color: #4CAF50; }}
        .risk-medium {{ background: rgba(255, 193, 7, 0.3); color: #FFC107; }}
        .risk-high {{ background: rgba(244, 67, 54, 0.3); color: #F44336; }}
        .risk-critical {{ background: rgba(139, 0, 0, 0.3); color: #8B0000; }}
        .risk-unknown {{ background: rgba(158, 158, 158, 0.3); color: #9E9E9E; }}
        
        .item-details {{
            font-size: 0.85em;
            opacity: 0.9;
            line-height: 1.4;
        }}
        
        .chain-badge {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 9px;
            margin-right: 6px;
            background: rgba(33, 150, 243, 0.3);
            color: #2196F3;
        }}
        
        .recommendation {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 9px;
            margin-left: 6px;
            font-weight: bold;
        }}
        .rec-strong-buy {{ background: rgba(76, 175, 80, 0.3); color: #4CAF50; }}
        .rec-buy {{ background: rgba(33, 150, 243, 0.3); color: #2196F3; }}
        .rec-small-buy {{ background: rgba(33, 150, 243, 0.2); color: #2196F3; }}
        .rec-watch {{ background: rgba(255, 193, 7, 0.3); color: #FFC107; }}
        .rec-avoid {{ background: rgba(244, 67, 54, 0.3); color: #F44336; }}
        .rec-unknown {{ background: rgba(158, 158, 158, 0.3); color: #9E9E9E; }}
        
        .item-actions {{
            margin-top: 8px;
            display: flex;
            gap: 6px;
        }}
        
        .connection-status {{
            position: fixed;
            top: 10px;
            right: 10px;
            padding: 8px 12px;
            border-radius: 5px;
            font-size: 12px;
            z-index: 999;
        }}
        .connected {{ background: #4CAF50; }}
        .disconnected {{ background: #f44336; }}
        
        .debug-info {{
            position: fixed;
            bottom: 10px;
            left: 10px;
            background: rgba(0,0,0,0.8);
            padding: 10px;
            border-radius: 5px;
            font-size: 11px;
            max-width: 300px;
            z-index: 999;
        }}
        
        .modal-overlay {{
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
        }}
        .modal-overlay.show {{ display: flex; }}
        .modal-content {{
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            max-width: 600px;
            max-height: 90vh;
            width: 90%;
            overflow-y: auto;
            animation: slideIn 0.3s ease;
        }}
        .modal-header {{
            padding: 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .modal-header h2 {{
            margin: 0;
            color: #4CAF50;
            font-size: 20px;
        }}
        .modal-close {{
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
        }}
        .modal-close:hover {{
            background: rgba(255, 255, 255, 0.1);
        }}
        .modal-body {{
            padding: 20px;
        }}
        .form-group {{
            margin-bottom: 15px;
        }}
        .form-group label {{
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
            font-size: 14px;
        }}
        .form-group input, .form-group textarea, .form-group select {{
            width: 100%;
            padding: 8px 12px;
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 6px;
            background: rgba(255, 255, 255, 0.1);
            color: white;
            font-size: 14px;
        }}
        .form-group input::placeholder, .form-group textarea::placeholder {{
            color: rgba(255, 255, 255, 0.5);
        }}
        .form-group textarea {{
            resize: vertical;
            min-height: 60px;
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}
        @keyframes slideIn {{
            from {{ transform: translateY(-50px); opacity: 0; }}
            to {{ transform: translateY(0); opacity: 1; }}
        }}
        
        @media (max-width: 1024px) {{
            .main-grid {{
                grid-template-columns: 1fr;
            }}
            .stats {{
                grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>DEX Sniping Dashboard v2.1.{cache_bust}</h1>
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
                            <button class="action-btn success" onclick="createTestOpportunity()">Test</button>
                            <button class="action-btn" onclick="debugOpportunities()">Debug</button>
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
    
    <div id="debug-info" class="debug-info" style="display: none;">
        <div>Version: 2.1.{cache_bust}</div>
        <div>Opportunities: <span id="debug-opp-count">0</span></div>
        <div>Last Update: <span id="debug-last-update">Never</span></div>
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
        console.log('Dashboard v2.1.{cache_bust} loading...');
        
        let ws = null;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 5;
        let opportunities = [];
        let watchlist = [];
        
        /**
         * Escape HTML to prevent XSS attacks
         * @param {{string|number|null|undefined}} text - Text to escape
         * @returns {{string}} Escaped HTML string
         */
        function escapeHtml(text) {{
            try {{
                if (typeof text !== 'string') {{
                    return String(text || '');
                }}
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }} catch (error) {{
                console.error('Error escaping HTML:', error);
                return String(text || '');
            }}
        }}
        
        /**
         * Safely extract nested object properties
         * @param {{object}} obj - Object to extract from
         * @param {{string}} path - Dot-separated path to property
         * @param {{any}} defaultValue - Default value if extraction fails
         * @returns {{any}} Extracted value or default
         */
        function safeExtract(obj, path, defaultValue = '') {{
            try {{
                if (!obj || typeof obj !== 'object') {{
                    return defaultValue;
                }}
                
                const keys = path.split('.');
                let value = obj;
                
                for (const key of keys) {{
                    if (value && typeof value === 'object' && key in value) {{
                        value = value[key];
                    }} else {{
                        return defaultValue;
                    }}
                }}
                
                return value !== null && value !== undefined ? value : defaultValue;
            }} catch (error) {{
                console.warn(`Error extracting ${{path}}:`, error);
                return defaultValue;
            }}
        }}
        
        /**
         * Add new opportunity to the dashboard list
         * @param {{object}} opportunity - Opportunity data object
         */
        function addOpportunityToList(opportunity) {{
            try {{
                console.log('Processing opportunity data:', opportunity);
                
                const list = document.getElementById('opportunity-list');
                if (!list) {{
                    console.error('Opportunity list element not found');
                    return;
                }}
                
                opportunities.unshift(opportunity);
                if (opportunities.length > 20) {{
                    opportunities.pop();
                }}
                
                const item = document.createElement('div');
                item.className = 'opportunity-item';
                
                // Extract basic fields safely
                const tokenSymbol = safeExtract(opportunity, 'token_symbol', 'UNKNOWN');
                const tokenAddress = safeExtract(opportunity, 'token_address', '');
                const chain = safeExtract(opportunity, 'chain', 'unknown');
                const riskLevel = safeExtract(opportunity, 'risk_level', 'unknown');
                const recommendation = safeExtract(opportunity, 'recommendation', 'UNKNOWN');
                const confidence = safeExtract(opportunity, 'confidence', 'UNKNOWN');
                const dexName = safeExtract(opportunity, 'dex_name', 'Unknown DEX');
                
                // Handle score with proper number parsing
                let score = 0;
                try {{
                    const rawScore = safeExtract(opportunity, 'score', 0);
                    score = parseFloat(rawScore) || 0;
                }} catch (error) {{
                    console.warn('Error parsing score:', error);
                    score = 0;
                }}
                
                // Handle liquidity_usd with comprehensive type checking
                let liquidityUsd = 0;
                try {{
                    const rawLiquidity = safeExtract(opportunity, 'liquidity_usd', 0);
                    console.log('Raw liquidity value:', rawLiquidity, 'Type:', typeof rawLiquidity);
                    
                    if (typeof rawLiquidity === 'number') {{
                        liquidityUsd = rawLiquidity;
                    }} else if (typeof rawLiquidity === 'string') {{
                        liquidityUsd = parseFloat(rawLiquidity) || 0;
                    }} else if (typeof rawLiquidity === 'object' && rawLiquidity !== null) {{
                        console.warn('Liquidity is an object:', rawLiquidity);
                        // Try common object properties
                        if ('value' in rawLiquidity) liquidityUsd = parseFloat(rawLiquidity.value) || 0;
                        else if ('amount' in rawLiquidity) liquidityUsd = parseFloat(rawLiquidity.amount) || 0;
                        else if ('usd' in rawLiquidity) liquidityUsd = parseFloat(rawLiquidity.usd) || 0;
                        else liquidityUsd = 0;
                    }} else {{
                        liquidityUsd = 0;
                    }}
                }} catch (error) {{
                    console.warn('Error parsing liquidity:', error);
                    liquidityUsd = 0;
                }}
                
                console.log('Processed liquidity USD:', liquidityUsd);
                
                // Format liquidity display
                let liquidityDisplay;
                if (liquidityUsd >= 1000000) {{
                    liquidityDisplay = `${{(liquidityUsd / 1000000).toFixed(2)}}M`;
                }} else if (liquidityUsd >= 1000) {{
                    liquidityDisplay = `${{(liquidityUsd / 1000).toFixed(1)}}K`;
                }} else if (liquidityUsd > 0) {{
                    liquidityDisplay = `${{liquidityUsd.toFixed(2)}}`;
                }} else {{
                    liquidityDisplay = 'Unknown';
                }}
                
                // Handle detected_at timestamp
                let detectedAt = new Date();
                try {{
                    const rawDate = safeExtract(opportunity, 'detected_at', null);
                    if (rawDate) {{
                        detectedAt = new Date(rawDate);
                        if (isNaN(detectedAt.getTime())) {{
                            detectedAt = new Date();
                        }}
                    }}
                }} catch (error) {{
                    console.warn('Error parsing date:', error);
                    detectedAt = new Date();
                }}
                
                // Calculate age display
                const ageMinutes = Math.floor((Date.now() - detectedAt.getTime()) / 60000);
                const ageDisplay = ageMinutes < 60 ? `${{ageMinutes}}m` : `${{Math.floor(ageMinutes / 60)}}h`;
                
                // Clean recommendation for CSS class
                const recClass = String(recommendation).toLowerCase().replace(/[^a-z]/g, '-');
                
                console.log('Final processed data:', {{
                    tokenSymbol, chain, riskLevel, recommendation, confidence, 
                    score, liquidityUsd, liquidityDisplay, dexName
                }});
                
                // Build HTML with proper escaping
                item.innerHTML = `
                    <div class="item-header">
                        <span class="token-symbol">${{escapeHtml(tokenSymbol)}}</span>
                        <span class="risk-badge risk-${{riskLevel}}">${{riskLevel.toUpperCase()}}</span>
                    </div>
                    <div class="item-details">
                        <span class="chain-badge">${{chain.toUpperCase()}}</span>
                        <strong>${{escapeHtml(dexName)}}</strong><br>
                        Rec: <span class="recommendation rec-${{recClass}}">${{recommendation}}</span>
                        (${{confidence}})<br>
                        Score: ${{score.toFixed(2)}} | Liquidity: ${{liquidityDisplay}}<br>
                        <small>Age: ${{ageDisplay}} | ${{detectedAt.toLocaleTimeString()}}</small>
                    </div>
                    <div class="item-actions">
                        <button class="action-btn success" onclick="addOpportunityToWatchlist('${{escapeHtml(tokenAddress)}}', '${{escapeHtml(tokenSymbol)}}', '${{escapeHtml(chain)}}')">Watch</button>
                        <button class="action-btn" onclick="executeTrade('${{escapeHtml(tokenSymbol)}}')">Trade</button>
                    </div>
                `;
                
                list.insertBefore(item, list.firstChild);
                
                // Keep only last 10 opportunities visible
                while (list.children.length > 10) {{
                    list.removeChild(list.lastChild);
                }}
                
                // Update debug info
                const debugCount = document.getElementById('debug-opp-count');
                const debugUpdate = document.getElementById('debug-last-update');
                if (debugCount) debugCount.textContent = opportunities.length;
                if (debugUpdate) debugUpdate.textContent = new Date().toLocaleTimeString();
                
            }} catch (error) {{
                console.error('Error adding opportunity:', error);
                console.error('Opportunity data:', opportunity);
            }}
        }}
        
        /**
         * Create test opportunity for debugging
         */
        function createTestOpportunity() {{
            try {{
                const testOpportunity = {{
                    token_symbol: 'TEST',
                    token_address: '0x1234567890123456789012345678901234567890',
                    chain: 'ETHEREUM',
                    risk_level: 'medium',
                    recommendation: 'BUY',
                    confidence: 'HIGH',
                    score: 0.75,
                    liquidity_usd: 50000,
                    dex_name: 'Test DEX',
                    detected_at: new Date().toISOString()
                }};
                
                console.log('Creating test opportunity:', testOpportunity);
                addOpportunityToList(testOpportunity);
            }} catch (error) {{
                console.error('Error creating test opportunity:', error);
            }}
        }}
        
        /**
         * Debug function to inspect opportunities data
         */
        function debugOpportunities() {{
            try {{
                console.log('Current opportunities array:', opportunities);
                
                const debugInfo = document.getElementById('debug-info');
                if (debugInfo) {{
                    debugInfo.style.display = 'block';
                }}
                
                // Test fetch from API
                fetch('/api/opportunities')
                    .then(response => {{
                        if (!response.ok) {{
                            throw new Error(`HTTP ${{response.status}}: ${{response.statusText}}`);
                        }}
                        return response.json();
                    }})
                    .then(data => {{
                        console.log('API opportunities data:', data);
                        if (Array.isArray(data) && data.length > 0) {{
                            console.log('First opportunity structure:', data[0]);
                            console.log('First opportunity liquidity_usd:', data[0].liquidity_usd, 'Type:', typeof data[0].liquidity_usd);
                        }}
                    }})
                    .catch(error => {{
                        console.error('Error fetching opportunities:', error);
                    }});
            }} catch (error) {{
                console.error('Error in debug function:', error);
            }}
        }}
        
        /**
         * Establish WebSocket connection with retry logic
         */
        function connectWebSocket() {{
            try {{
                if (ws && ws.readyState === WebSocket.OPEN) {{
                    console.log('WebSocket already connected');
                    return;
                }}
                
                console.log('Connecting to WebSocket...');
                ws = new WebSocket('ws://localhost:8000/ws');
                
                ws.onopen = function() {{
                    console.log('WebSocket connected successfully');
                    updateConnectionStatus(true);
                    reconnectAttempts = 0;
                }};
                
                ws.onmessage = function(event) {{
                    try {{
                        const data = JSON.parse(event.data);
                        handleWebSocketMessage(data);
                    }} catch (error) {{
                        console.error('Error parsing WebSocket message:', error);
                        console.error('Raw message:', event.data);
                    }}
                }};
                
                ws.onclose = function(event) {{
                    console.log('WebSocket disconnected. Code:', event.code, 'Reason:', event.reason);
                    updateConnectionStatus(false);
                    
                    if (reconnectAttempts < maxReconnectAttempts) {{
                        reconnectAttempts++;
                        const delay = 3000 * reconnectAttempts;
                        console.log(`Reconnecting in ${{delay}}ms... (attempt ${{reconnectAttempts}}/${{maxReconnectAttempts}})`);
                        setTimeout(connectWebSocket, delay);
                    }} else {{
                        console.error('Max reconnection attempts reached');
                    }}
                }};
                
                ws.onerror = function(error) {{
                    console.error('WebSocket error:', error);
                    updateConnectionStatus(false);
                }};
                
            }} catch (error) {{
                console.error('WebSocket connection error:', error);
                updateConnectionStatus(false);
            }}
        }}
        
        /**
         * Handle incoming WebSocket messages
         * @param {{object}} data - Parsed message data
         */
        function handleWebSocketMessage(data) {{
            try {{
                console.log('Received WebSocket message type:', data.type);
                
                if (data.type === 'new_opportunity') {{
                    console.log('New opportunity data:', data.data);
                }}
                
                switch (data.type) {{
                    case 'new_opportunity':
                        if (data.data) {{
                            addOpportunityToList(data.data);
                        }} else {{
                            console.warn('Received new_opportunity message without data');
                        }}
                        break;
                        
                    case 'stats_update':
                        if (data.data) {{
                            updateStats(data.data);
                        }}
                        break;
                        
                    case 'watchlist_updated':
                        refreshWatchlist();
                        break;
                        
                    case 'connected':
                    case 'subscribed':
                        console.log('WebSocket connection confirmed');
                        break;
                        
                    case 'heartbeat':
                    case 'ping':
                        // Ignore heartbeat messages
                        break;
                        
                    default:
                        console.log('Unknown message type:', data.type, data);
                }}
            }} catch (error) {{
                console.error('Error handling WebSocket message:', error);
                console.error('Message data:', data);
            }}
        }}
        
        /**
         * Update connection status indicator
         * @param {{boolean}} connected - Connection status
         */
        function updateConnectionStatus(connected) {{
            try {{
                const statusEl = document.getElementById('connection-status');
                if (!statusEl) return;
                
                if (connected) {{
                    statusEl.textContent = 'Connected';
                    statusEl.className = 'connection-status connected';
                }} else {{
                    statusEl.textContent = 'Disconnected';
                    statusEl.className = 'connection-status disconnected';
                }}
            }} catch (error) {{
                console.error('Error updating connection status:', error);
            }}
        }}
        
        /**
         * Update statistics display
         * @param {{object}} stats - Statistics data
         */
        function updateStats(stats) {{
            try {{
                if (!stats || typeof stats !== 'object') return;
                
                const elements = {{
                    'total-opportunities': stats.total_opportunities,
                    'high-confidence': stats.high_confidence,
                    'analysis-rate': stats.analysis_rate,
                    'connected-clients': stats.connected_clients
                }};
                
                for (const [id, value] of Object.entries(elements)) {{
                    const element = document.getElementById(id);
                    if (element && value !== undefined) {{
                        element.textContent = value;
                    }}
                }}
            }} catch (error) {{
                console.error('Error updating stats:', error);
            }}
        }}
        
        /**
         * Fetch statistics from API
         */
        async function fetchStats() {{
            try {{
                const response = await fetch('/api/stats');
                if (!response.ok) {{
                    throw new Error(`HTTP ${{response.status}}: ${{response.statusText}}`);
                }}
                
                const stats = await response.json();
                updateStats(stats);
            }} catch (error) {{
                console.error('Error fetching stats:', error);
            }}
        }}
        
        /**
         * Clear opportunities list
         */
        function clearOpportunities() {{
            try {{
                const list = document.getElementById('opportunity-list');
                if (list) {{
                    list.innerHTML = '<p>Opportunities cleared...</p>';
                }}
                opportunities = [];
                
                const debugCount = document.getElementById('debug-opp-count');
                if (debugCount) {{
                    debugCount.textContent = '0';
                }}
            }} catch (error) {{
                console.error('Error clearing opportunities:', error);
            }}
        }}
        
        /**
         * Execute trade for token
         * @param {{string}} tokenSymbol - Token symbol to trade
         */
        function executeTrade(tokenSymbol) {{
            try {{
                showNotification(`Trade execution for ${{tokenSymbol}} - Feature coming soon!`, 'info');
            }} catch (error) {{
                console.error('Error executing trade:', error);
            }}
        }}
        
        /**
         * Show notification message
         * @param {{string}} message - Notification message
         * @param {{string}} type - Notification type (success, error, info)
         */
        function showNotification(message, type = 'info') {{
            try {{
                const notification = document.createElement('div');
                const bgColor = type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3';
                
                notification.style.cssText = `
                    position: fixed;
                    top: 70px;
                    right: 20px;
                    background: ${{bgColor}};
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
                
                setTimeout(() => {{
                    if (notification.parentNode) {{
                        notification.remove();
                    }}
                }}, 3000);
            }} catch (error) {{
                console.error('Error showing notification:', error);
            }}
        }}
        
        // Watchlist functions (placeholders for future implementation)
        function showAddToWatchlistModal() {{
            showNotification('Watchlist modal - Feature coming soon!', 'info');
        }}
        
        function closeAddWatchlistModal() {{
            // Placeholder for modal close functionality
        }}
        
        function refreshWatchlist() {{
            console.log('Refreshing watchlist...');
            // Placeholder for watchlist refresh
        }}
        
        function clearWatchlist() {{
            showNotification('Clear watchlist - Feature coming soon!', 'info');
        }}
        
        function addOpportunityToWatchlist(tokenAddress, tokenSymbol, chain) {{
            showNotification(`Adding ${{tokenSymbol}} to watchlist - Feature coming soon!`, 'info');
        }}
        
        // Expose functions to global scope for debugging
        window.createTestOpportunity = createTestOpportunity;
        window.debugOpportunities = debugOpportunities;
        window.clearOpportunities = clearOpportunities;
        
        // Initialize dashboard
        try {{
            console.log('Dashboard v2.1.{cache_bust} initializing...');
            
            // Start WebSocket connection
            connectWebSocket();
            
            // Fetch initial stats
            fetchStats();
            
            // Set up periodic stats refresh
            setInterval(fetchStats, 10000); // Every 10 seconds
            
            // Show debug panel after 5 seconds if no opportunities
            setTimeout(() => {{
                if (opportunities.length === 0) {{
                    const debugInfo = document.getElementById('debug-info');
                    if (debugInfo) {{
                        debugInfo.style.display = 'block';
                    }}
                }}
            }}, 5000);
            
            console.log('Dashboard initialization complete');
            
        }} catch (error) {{
            console.error('Error during dashboard initialization:', error);
        }}
    </script>
</body>
</html>"""

    except Exception as error:
        # Log error and return fallback HTML
        print(f"Error generating dashboard HTML: {error}")
        return _get_fallback_html()


def _get_fallback_html() -> str:
    """
    Get fallback HTML template in case of errors.
    
    Returns:
        Basic HTML string for emergency fallback
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DEX Sniping Dashboard - Error</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            background: #1e3c72; 
            color: white; 
            padding: 20px; 
            text-align: center; 
        }
        .error-container {
            max-width: 600px;
            margin: 100px auto;
            padding: 40px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
        }
    </style>
</head>
<body>
    <div class="error-container">
        <h1>Dashboard Error</h1>
        <p>There was an error generating the dashboard template.</p>
        <p>Please check the server logs for more information.</p>
        <button onclick="location.reload()">Retry</button>
    </div>
</body>
</html>"""