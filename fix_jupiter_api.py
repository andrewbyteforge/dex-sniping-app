"""
Fix Jupiter API endpoint to use the correct URL.
"""

import os

def fix_jupiter_api():
    """Update Jupiter monitor to use the correct API endpoint."""
    
    monitor_path = "monitors/jupiter_solana_monitor.py"
    
    if not os.path.exists(monitor_path):
        print(f"❌ File not found: {monitor_path}")
        return
    
    with open(monitor_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Update the API URL - Jupiter v6 API
    old_url = 'self.api_url = "https://api.jup.ag/tokens/v1"'
    new_url = 'self.api_url = "https://token.jup.ag/all"'
    
    if old_url in content:
        content = content.replace(old_url, new_url)
        print("✅ Updated Jupiter API URL to v6 endpoint")
    
    # Also update in the initialize method if it's there
    content = content.replace(
        '"https://api.jup.ag/tokens/v1"',
        '"https://token.jup.ag/all"'
    )
    
    # Update how we parse the response (v6 returns array directly)
    if "data = await response.json()" in content:
        # The response structure might be different
        old_parsing = """data = await response.json()
                
                # Filter for potentially new tokens
                new_tokens = []
                for token in data:"""
        
        new_parsing = """data = await response.json()
                
                # Filter for potentially new tokens
                new_tokens = []
                # Handle both array and object response
                token_list = data if isinstance(data, list) else data.get('tokens', [])
                for token in token_list:"""
        
        content = content.replace(old_parsing.strip(), new_parsing.strip())
    
    # Write back
    with open(monitor_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Jupiter monitor API fixed!")
    print("\n📋 Changes:")
    print("   - Updated to Jupiter v6 API endpoint")
    print("   - Fixed response parsing")
    print("\n💡 Note: If Jupiter still doesn't work, we can:")
    print("   1. Disable Jupiter and use only Ethereum/Base monitors")
    print("   2. Use a different Solana API")
    print("\n✅ Try running: python main_with_trading.py")

if __name__ == "__main__":
    fix_jupiter_api()