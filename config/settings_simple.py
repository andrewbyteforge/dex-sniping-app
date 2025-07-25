
"""
Simple settings configuration for the enhanced production system.
"""

class NetworkSettings:
    def __init__(self):
        self.ethereum_rpc_url = "https://ethereum-rpc.publicnode.com"
        self.base_rpc_url = "https://mainnet.base.org"
        self.bsc_rpc_url = "https://bsc-dataseed.binance.org"

class ChainSettings:
    def __init__(self):
        self.enabled = True

class ChainsSettings:
    def __init__(self):
        self.ethereum = ChainSettings()
        self.base = ChainSettings()
        self.solana = ChainSettings()
        self.solana.enabled = False  # Disable Solana by default

class Settings:
    def __init__(self):
        self.networks = NetworkSettings()
        self.chains = ChainsSettings()

# Create global settings instance
settings = Settings()
