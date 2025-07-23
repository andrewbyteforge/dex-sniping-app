"""
Quick fix to ensure Base monitor uses the correct free RPC.
Run this to update the Base monitor configuration.
"""

import os

def update_base_monitor():
    """Update Base monitor to use free RPC."""
    
    # Read the current base monitor file
    monitor_path = "monitors/base_chain_monitor.py"
    
    if not os.path.exists(monitor_path):
        print(f"❌ File not found: {monitor_path}")
        return
    
    with open(monitor_path, 'r') as f:
        content = f.read()
    
    # Replace the RPC URL configuration
    old_rpc = 'rpc_url: str = "https://base-mainnet.g.alchemy.com/v2/demo"'
    new_rpc = 'rpc_url: str = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")'
    
    if old_rpc in content:
        content = content.replace(old_rpc, new_rpc)
        
        # Add import if not present
        if "import os" not in content:
            content = "import os\n" + content
        
        # Write back
        with open(monitor_path, 'w') as f:
            f.write(content)
        
        print("✅ Base monitor updated to use free RPC")
    else:
        print("⚠️  Base monitor already configured or has different format")
    
    # Also check the chain config
    chain_config_path = "config/chains.py"
    
    if os.path.exists(chain_config_path):
        with open(chain_config_path, 'r') as f:
            content = f.read()
        
        # Update Base RPC in chain config
        if 'base-mainnet.g.alchemy.com' in content:
            content = content.replace(
                'https://base-mainnet.g.alchemy.com/v2/demo',
                'https://mainnet.base.org'
            )
            
            with open(chain_config_path, 'w') as f:
                f.write(content)
            
            print("✅ Chain config updated to use free Base RPC")

if __name__ == "__main__":
    update_base_monitor()
    print("\n💡 Now restart the system:")
    print("   python main_production_enhanced.py")