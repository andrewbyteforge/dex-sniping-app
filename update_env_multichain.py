"""
Update .env to use Etherscan API key for Base monitoring.
"""

def update_env_for_multichain():
    """Update .env file to use Etherscan key for Base."""
    
    # Read current .env
    with open('.env', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Update the file
    updated_lines = []
    etherscan_key = None
    
    for line in lines:
        # Get the Etherscan key value
        if line.startswith('ETHERSCAN_API_KEY=') and '=' in line:
            etherscan_key = line.split('=', 1)[1].strip()
        
        # Update empty BASESCAN_API_KEY with Etherscan key
        if line.startswith('BASESCAN_API_KEY=') and etherscan_key:
            if not line.split('=', 1)[1].strip():  # If empty
                updated_lines.append(f'BASESCAN_API_KEY={etherscan_key}\n')
                print(f"✅ Set BASESCAN_API_KEY to use your Etherscan key")
                continue
        
        updated_lines.append(line)
    
    # Write back
    with open('.env', 'w', encoding='utf-8') as f:
        f.writelines(updated_lines)
    
    print("\n✅ Your .env is now configured!")
    print("\n📋 Etherscan Multichain API covers:")
    print("   • Ethereum ✅")
    print("   • Base ✅")
    print("   • Optimism ✅")
    print("   • Arbitrum ✅")
    print("   • BSC ✅")
    print("   • And 55+ other chains!")
    
    print("\n🎯 Your system can now monitor:")
    print("   • Ethereum - Main chain for new tokens")
    print("   • Base - Fast growing L2 with cheap gas")
    
    print("\n💡 Next steps:")
    print("   1. Run: python disable_solana.py")
    print("   2. Run: python main_with_trading.py")
    print("\n🚀 You'll start detecting new tokens immediately!")

if __name__ == "__main__":
    update_env_for_multichain()