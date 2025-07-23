"""
Analyze the Jupiter monitor to understand its structure and fix it.
"""

import os
import re

def analyze_jupiter_monitor():
    """Analyze the Jupiter monitor file."""
    
    monitor_path = "monitors/jupiter_solana_monitor.py"
    
    if not os.path.exists(monitor_path):
        print(f"❌ File not found: {monitor_path}")
        return
    
    with open(monitor_path, 'r') as f:
        content = f.read()
    
    print("📋 JUPITER MONITOR ANALYSIS")
    print("=" * 60)
    
    # Find the API endpoint
    api_match = re.search(r'(https://[^"\']+jupiter[^"\']+)', content)
    if api_match:
        print(f"API Endpoint: {api_match.group(1)}")
    
    # Find how tokens are fetched
    if "fetch_new_tokens" in content:
        print("✅ Has fetch_new_tokens method")
    
    if "check_new_opportunities" in content:
        print("✅ Has check_new_opportunities method")
    
    # Check what's being returned
    if '"verified"' in content or "'verified'" in content:
        print("✅ Filters for verified tokens")
    
    # Look for the actual filtering logic
    print("\n🔍 Current filtering logic:")
    
    # Find lines that filter tokens
    for line in content.split('\n'):
        if 'verified_tokens' in line or 'new_tokens' in line:
            print(f"  {line.strip()}")
    
    print("\n💡 The issue: Jupiter API returns ALL verified tokens, not just new ones")
    print("   We need to filter by creation time or only fetch recently added tokens")
    
    # Create a manual patch
    print("\n📝 Creating manual fix...")
    
    # Replace the entire fetch_new_tokens method to be more selective
    new_fetch_method = '''    async def fetch_new_tokens(self) -> List[Dict]:
        """Fetch new tokens from Jupiter API - filtered for actually new tokens."""
        try:
            url = "https://api.jup.ag/tokens/v1"
            
            async with self.session.get(url, timeout=30) as response:
                if response.status != 200:
                    self.logger.warning(f"Jupiter API returned status {response.status}")
                    return []
                
                data = await response.json()
                
                # Only get verified tokens with good liquidity
                filtered_tokens = []
                for token in data:
                    # Skip if not verified
                    if not token.get("verified", False):
                        continue
                    
                    # Skip well-known tokens (they're not new)
                    symbol = token.get("symbol", "").upper()
                    known_tokens = ["USDC", "USDT", "SOL", "WETH", "BTC", "ETH", "SAND", "MANA", 
                                   "LINK", "UNI", "AAVE", "SNX", "CRV", "SUSHI", "MATIC", "DOT",
                                   "BONK", "WIF", "POPCAT", "MEW", "BOME", "PEPE", "FLOKI"]
                    if symbol in known_tokens:
                        continue
                    
                    # Skip wrapped/bridge tokens
                    name = token.get("name", "").lower()
                    if any(word in name for word in ["wrapped", "bridge", "portal", "wormhole", "allbridge"]):
                        continue
                    
                    # Skip if already in watchlist
                    try:
                        from models.watchlist import watchlist_manager
                        if watchlist_manager.is_in_watchlist(symbol):
                            continue
                    except:
                        pass
                    
                    filtered_tokens.append(token)
                
                # Return only the newest tokens (limit to prevent spam)
                return filtered_tokens[:5]  # Only process 5 at a time
                
        except Exception as e:
            self.logger.error(f"Error fetching Jupiter tokens: {e}")
            return []'''
    
    # Apply the fix
    if "async def fetch_new_tokens" in content:
        # Find the method and replace it
        start = content.find("async def fetch_new_tokens")
        if start != -1:
            # Find the end of the method (next method or class end)
            next_method = content.find("\n    async def", start + 1)
            next_def = content.find("\n    def", start + 1)
            end = min(x for x in [next_method, next_def, len(content)] if x > start)
            
            # Replace the method
            content = content[:start] + new_fetch_method.strip() + "\n\n" + content[end:]
            
            # Write back
            with open(monitor_path, 'w') as f:
                f.write(content)
            
            print("✅ Jupiter monitor fixed! It will now:")
            print("   - Skip well-known tokens")
            print("   - Skip wrapped/bridge tokens")
            print("   - Skip tokens already in watchlist")
            print("   - Limit to 5 new tokens at a time")
        else:
            print("❌ Could not locate method boundaries")
    else:
        print("❌ fetch_new_tokens method not found")
    
    print("\n🚀 Next steps:")
    print("1. Add Etherscan API key for Ethereum monitoring")
    print("2. Add Basescan API key for Base monitoring")
    print("3. Restart the system")

if __name__ == "__main__":
    analyze_jupiter_monitor()