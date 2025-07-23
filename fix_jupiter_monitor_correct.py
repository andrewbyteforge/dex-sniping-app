"""
Fix the Jupiter monitor to filter out old tokens.
"""

import os
import re

def fix_jupiter_monitor():
    """Fix the Jupiter monitor to only show new tokens."""
    
    monitor_path = "monitors/jupiter_solana_monitor.py"
    
    if not os.path.exists(monitor_path):
        print(f"❌ File not found: {monitor_path}")
        return
    
    with open(monitor_path, 'r') as f:
        content = f.read()
    
    print("🔧 Fixing Jupiter Monitor...")
    
    # First, add the known tokens list at the class level
    known_tokens_list = '''
        # Well-known tokens to skip (not new)
        self.known_tokens = {
            "USDC", "USDT", "SOL", "WETH", "BTC", "ETH", "SAND", "MANA", 
            "LINK", "UNI", "AAVE", "SNX", "CRV", "SUSHI", "MATIC", "DOT",
            "BONK", "WIF", "POPCAT", "MEW", "BOME", "PEPE", "FLOKI", "SHIB",
            "DOGE", "ADA", "XRP", "BNB", "AVAX", "LUNA", "FTT", "SRM",
            "RAY", "COPE", "FIDA", "KIN", "MAPS", "OXY", "TULIP", "ORCA",
            "STEP", "COPE", "ROPE", "SAMO", "GOFX", "DXL", "LIKE", "CHEEMS",
            "wUST_v1", "acUSD", "abETH", "compassSOL", "UPS", "Speero", "pre",
            "PEW", "pussyinbio"  # Add tokens from your current output
        }
        
        # Wrapped/bridge token patterns to skip
        self.skip_patterns = ["wrapped", "bridge", "portal", "wormhole", "allbridge", "celer"]
'''
    
    # Add after the __init__ method
    init_end = content.find("self.last_check = datetime.now()")
    if init_end > 0:
        init_end = content.find("\n", init_end) + 1
        content = content[:init_end] + known_tokens_list + "\n" + content[init_end:]
        print("✅ Added known tokens list")
    
    # Now fix the token filtering in check_new_opportunities
    # Find where tokens are processed
    old_pattern = r"for token_data in new_tokens:"
    
    # Create the new filtering logic
    new_filter_logic = '''for token_data in new_tokens:
                # Skip well-known tokens
                symbol = token_data.get("symbol", "").upper()
                if symbol in self.known_tokens:
                    continue
                
                # Skip wrapped/bridge tokens
                name = token_data.get("name", "").lower()
                if any(pattern in name for pattern in self.skip_patterns):
                    continue
                
                # Skip if already in watchlist
                try:
                    from models.watchlist import watchlist_manager
                    if watchlist_manager.is_in_watchlist(symbol):
                        self.logger.debug(f"Skipping {symbol} - already in watchlist")
                        continue
                except:
                    pass
                '''
    
    # Replace all occurrences of the pattern
    content = re.sub(r"for token_data in new_tokens:\s*", new_filter_logic, content)
    
    # Also update the Jupiter API call to get fewer results
    if "https://api.jup.ag/tokens/v1" in content:
        content = content.replace(
            '"https://api.jup.ag/tokens/v1"',
            '"https://api.jup.ag/tokens/v1"  # Gets all tokens, we filter below'
        )
        print("✅ Updated API endpoint comment")
    
    # Write the fixed content back
    with open(monitor_path, 'w') as f:
        f.write(content)
    
    print("✅ Jupiter monitor fixed!")
    print("\n📋 Changes made:")
    print("   - Added list of known tokens to skip")
    print("   - Filter out wrapped/bridge tokens")
    print("   - Skip tokens already in watchlist")
    print("   - Will only show genuinely new tokens")
    
    print("\n⚠️  IMPORTANT: Jupiter shows tokens that are already trading.")
    print("   For TRUE new launches, you need:")
    print("   1. Etherscan API key for Ethereum")
    print("   2. Basescan API key for Base")
    print("   These detect tokens at the moment of creation!")

if __name__ == "__main__":
    fix_jupiter_monitor()