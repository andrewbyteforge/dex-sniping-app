"""
Fix Jupiter monitor to only show new tokens, not existing ones.
"""

import os

def fix_jupiter_monitor():
    """Update Jupiter monitor to filter for new tokens only."""
    
    monitor_path = "monitors/jupiter_solana_monitor.py"
    
    if not os.path.exists(monitor_path):
        print(f"❌ File not found: {monitor_path}")
        return
    
    with open(monitor_path, 'r') as f:
        content = f.read()
    
    # Find the check_new_opportunities method
    if "def check_new_opportunities" in content:
        # Add age filter to only show tokens less than 24 hours old
        old_code = """# Filter tokens
                new_tokens = []
                for token in tokens:"""
        
        new_code = """# Filter tokens - only show new ones (< 24 hours old)
                new_tokens = []
                current_time = time.time()
                for token in tokens:
                    # Skip if token is older than 24 hours
                    if hasattr(token, 'created_at') and token.created_at:
                        age_hours = (current_time - token.created_at) / 3600
                        if age_hours > 24:
                            continue"""
        
        if old_code in content:
            content = content.replace(old_code, new_code)
            
            # Make sure time is imported
            if "import time" not in content:
                content = "import time\n" + content
        
        # Also update the token filtering to be more strict
        content = content.replace(
            'verified_tokens = [t for t in data if t.get("verified", False)]',
            '''# Only get new tokens with reasonable liquidity
        verified_tokens = []
        for t in data:
            if not t.get("verified", False):
                continue
            # Check liquidity
            liquidity = t.get("liquidity", {}).get("usd", 0)
            if liquidity < 1000:  # At least $1k liquidity
                continue
            # Check daily volume
            volume = t.get("daily_volume", 0)
            if volume < 100:  # At least $100 daily volume
                continue
            verified_tokens.append(t)'''
        )
        
        # Write back
        with open(monitor_path, 'w') as f:
            f.write(content)
        
        print("✅ Jupiter monitor updated to show only new tokens with liquidity")
    else:
        print("⚠️ Could not find the method to update")
    
    print("\n💡 You also need to add Etherscan/Basescan API keys to detect new tokens on Ethereum/Base")

if __name__ == "__main__":
    fix_jupiter_monitor()