"""
Create a proper .env file with all your API keys correctly configured.
"""

def create_env_file():
    """Create a properly formatted .env file."""
    
    env_content = """# DEX Sniping System Configuration
# ========================================
# RPC ENDPOINTS
# ========================================

# Ethereum - Free RPC
ETHEREUM_RPC_URL=https://ethereum-rpc.publicnode.com

# Base Chain - Free RPC
BASE_RPC_URL=https://mainnet.base.org

# Binance Smart Chain - Free RPC
BSC_RPC_URL=https://bsc-dataseed.binance.org/

# Solana - Free RPC
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com

# ========================================
# BLOCKCHAIN EXPLORER API KEYS
# ========================================

# Etherscan - For Ethereum monitoring
ETHERSCAN_API_KEY=VZFDUWB3YGQ1YCDKTCU1D6DDSS

# Basescan - For Base chain monitoring (NEED TO GET THIS!)
BASESCAN_API_KEY=

# BSCscan - For Binance Smart Chain monitoring
BSCSCAN_API_KEY=ZM8ACMJB67C2IXKKBF8URFUNSY

# Snowscan - For Avalanche monitoring
SNOWSCAN_API_KEY=ATJQERBKV1CI3GVKNSE3Q7RGEJ

# Arbiscan - For Arbitrum monitoring
ARBISCAN_API_KEY=B6SVGA7K3YBJEQ69AFKJF4YHVX

# Optimism - For Optimism monitoring
OPTIMISM_API_KEY=66N5FRNV1ZD4I87S7MAHCJVXFJ

# ========================================
# API URLS (Usually don't need to change)
# ========================================

ETHERSCAN_API_URL=https://api.etherscan.io/api
BASESCAN_API_URL=https://api.basescan.org/api
BSCSCAN_API_URL=https://api.bscscan.com/api
SNOWSCAN_API_URL=https://api.snowscan.xyz/api
ARBISCAN_API_URL=https://api.arbiscan.io/api
OPTIMISM_API_URL=https://api-optimistic.etherscan.io/api

# ========================================
# TRADING SETTINGS
# ========================================

# Enable auto trading (USE WITH EXTREME CAUTION)
ENABLE_AUTO_TRADING=false

# Maximum position size in USD
MAX_POSITION_SIZE=100

# Slippage tolerance (0.05 = 5%)
SLIPPAGE_TOLERANCE=0.05

# ========================================
# OPTIONAL ENHANCEMENTS
# ========================================

# Telegram notifications
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# CoinGecko for price data (optional)
COINGECKO_API_KEY=
"""
    
    # Write the new .env file
    with open('.env', 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print("✅ Created proper .env file!")
    print("\n📋 Your API Keys:")
    print("   ✅ ETHERSCAN_API_KEY - Ethereum monitoring")
    print("   ❌ BASESCAN_API_KEY - Base monitoring (MISSING!)")
    print("   ✅ BSCSCAN_API_KEY - Binance Smart Chain monitoring")
    print("   ✅ ARBISCAN_API_KEY - Arbitrum monitoring")
    print("   ✅ OPTIMISM_API_KEY - Optimism monitoring")
    print("   ✅ SNOWSCAN_API_KEY - Avalanche monitoring")
    
    print("\n🔍 Key Clarification:")
    print("   • BSCSCAN = Binance Smart Chain (NOT Base)")
    print("   • BASESCAN = Base Chain (Coinbase's L2)")
    
    print("\n⚠️  YOU STILL NEED BASESCAN_API_KEY!")
    print("\n📝 To get BASESCAN_API_KEY:")
    print("   1. Go to: https://basescan.org/login")
    print("   2. Login with your Etherscan account")
    print("   3. Go to: https://basescan.org/myapikey")
    print("   4. Click '+ Add' to create key")
    print("   5. Copy and add to .env file")
    
    print("\n🎯 For this DEX sniping system, you mainly need:")
    print("   • ETHERSCAN_API_KEY ✅ (for Ethereum)")
    print("   • BASESCAN_API_KEY ❌ (for Base - MISSING!)")
    
    print("\n💡 Base chain is important because:")
    print("   • Many new memecoins launch there")
    print("   • Lower gas fees than Ethereum")
    print("   • Growing rapidly")

if __name__ == "__main__":
    create_env_file()