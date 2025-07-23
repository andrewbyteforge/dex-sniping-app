"""
Fix how monitors are initialized in main_with_trading.py
"""

import os

def fix_monitor_initialization():
    """Fix the monitor initialization in main_with_trading.py"""
    
    main_file = "main_with_trading.py"
    
    if not os.path.exists(main_file):
        print(f"❌ File not found: {main_file}")
        return
    
    with open(main_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix any places where monitors are initialized with check_interval
    # Look for patterns like JupiterSolanaMonitor(check_interval=...)
    import re
    
    # Pattern to find monitor initialization with parameters
    pattern = r'JupiterSolanaMonitor\([^)]+\)'
    
    # Replace with simple initialization
    content = re.sub(pattern, 'JupiterSolanaMonitor()', content)
    
    # Also check for other monitors
    content = re.sub(r'SolanaMonitor\([^)]+\)', 'SolanaMonitor()', content)
    content = re.sub(r'BaseChainMonitor\([^)]+\)', 'BaseChainMonitor()', content)
    content = re.sub(r'NewTokenMonitor\([^)]+\)', 'NewTokenMonitor()', content)
    
    # Write back
    with open(main_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Fixed monitor initialization in main_with_trading.py")
    
    # Now check the actual initialization code
    print("\n🔍 Checking monitor initialization...")
    
    # Look for the _initialize_monitors method
    if "_initialize_monitors" in content:
        print("✅ Found _initialize_monitors method")
        
        # Extract the method to see how monitors are created
        start = content.find("def _initialize_monitors")
        end = content.find("\n    def", start + 1)
        if end == -1:
            end = content.find("\n\nif __name__", start)
        
        method_content = content[start:end] if end > start else ""
        
        # Check if monitors are created correctly
        if "JupiterSolanaMonitor()" in method_content:
            print("✅ Jupiter monitor initialization looks correct")
        else:
            print("⚠️  May need to check Jupiter monitor initialization")
    
    print("\n✅ Monitor initialization should now work correctly")
    print("   Run: python main_with_trading.py")

if __name__ == "__main__":
    fix_monitor_initialization()