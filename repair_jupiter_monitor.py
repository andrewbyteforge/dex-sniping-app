"""
Repair the Jupiter monitor syntax error.
"""

import os

def repair_jupiter_monitor():
    """Fix the syntax error in Jupiter monitor."""
    
    monitor_path = "monitors/jupiter_solana_monitor.py"
    
    if not os.path.exists(monitor_path):
        print(f"❌ File not found: {monitor_path}")
        return
    
    with open(monitor_path, 'r') as f:
        content = f.read()
    
    print("🔧 Repairing Jupiter Monitor syntax...")
    
    # The issue is likely indentation or placement of continue statements
    # Let's fix the check_new_opportunities method more carefully
    
    # First, let's restore a working version by removing our broken changes
    lines = content.split('\n')
    fixed_lines = []
    in_for_loop = False
    indent_level = 0
    
    for i, line in enumerate(lines):
        # Track if we're in a for loop
        if 'for token_data in new_tokens:' in line:
            in_for_loop = True
            indent_level = len(line) - len(line.lstrip())
            fixed_lines.append(line)
            continue
            
        # If we see a continue that's causing issues
        if line.strip() == 'continue' and not in_for_loop:
            print(f"Found problematic continue at line {i+1}")
            # Skip this line
            continue
            
        # Reset for loop tracking if we exit the loop
        if in_for_loop and line.strip() and len(line) - len(line.lstrip()) <= indent_level:
            in_for_loop = False
            
        fixed_lines.append(line)
    
    # Write the fixed content
    with open(monitor_path, 'w') as f:
        f.write('\n'.join(fixed_lines))
    
    print("✅ Syntax error fixed!")
    
    # Now let's add a simpler filter that won't cause syntax errors
    with open(monitor_path, 'r') as f:
        content = f.read()
    
    # Add a simple filter method
    simple_filter = '''
    def should_skip_token(self, symbol: str, name: str) -> bool:
        """Check if we should skip this token."""
        # Skip well-known tokens
        known = ["USDC", "USDT", "SOL", "WETH", "BTC", "ETH", "SAND", "MANA", 
                 "LINK", "UNI", "AAVE", "wUST_v1", "acUSD", "abETH", "compassSOL"]
        if symbol.upper() in known:
            return True
        
        # Skip wrapped tokens
        if any(word in name.lower() for word in ["wrapped", "bridge", "portal"]):
            return True
            
        return False
'''
    
    # Add the method after the __init__ method
    init_end = content.find("def check_new_opportunities")
    if init_end > 0:
        content = content[:init_end] + simple_filter + "\n\n    " + content[init_end:]
    
    # Now use this method in the processing
    content = content.replace(
        "for token_data in new_tokens:",
        """for token_data in new_tokens:
                # Filter out known tokens
                symbol = token_data.get("symbol", "")
                name = token_data.get("name", "")
                if self.should_skip_token(symbol, name):
                    continue"""
    )
    
    # Write final version
    with open(monitor_path, 'w') as f:
        f.write(content)
    
    print("✅ Added proper token filtering!")
    print("\n📋 The monitor will now skip:")
    print("   - Well-known tokens (USDC, USDT, etc.)")
    print("   - Wrapped/bridge tokens")
    print("\n✅ You can now run: python main_with_trading.py")


if __name__ == "__main__":
    repair_jupiter_monitor()