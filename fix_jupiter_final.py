"""
Final fix for Jupiter monitor to work with the base class.
"""

import os

def fix_jupiter_monitor():
    """Apply final fixes to Jupiter monitor."""
    
    monitor_path = "monitors/jupiter_solana_monitor.py"
    
    # Read the current content
    with open(monitor_path, 'r') as f:
        content = f.read()
    
    # Remove the line with check_interval
    content = content.replace("self.check_interval = 10  # 10 seconds\n        ", "")
    
    # Make sure we have the required abstract methods
    if "_check(self)" not in content:
        # Add the required methods before the last line
        methods_to_add = '''
    async def _check(self) -> List[TradingOpportunity]:
        """Internal check method required by base class."""
        return await self.check_new_opportunities()
    
    async def _cleanup(self):
        """Internal cleanup method required by base class."""
        await self.cleanup()
    
    async def _initialize(self) -> bool:
        """Internal initialize method required by base class."""
        return await self.initialize()
'''
        # Insert before the last line
        content = content.rstrip() + methods_to_add
    
    # Write back
    with open(monitor_path, 'w') as f:
        f.write(content)
    
    print("✅ Jupiter monitor fixed!")
    print("   - Removed check_interval from __init__")
    print("   - Added required abstract methods")
    print("\n✅ You can now run: python main_with_trading.py")

if __name__ == "__main__":
    fix_jupiter_monitor()