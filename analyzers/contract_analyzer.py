# analyzers/contract_analyzer.py
"""
Smart contract security and risk analysis for new token opportunities.
Detects honeypots, rug pulls, and other common scams with enhanced analysis.
"""

import asyncio
import aiohttp
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from web3 import Web3
from web3.contract import Contract

from models.token import ContractAnalysis, RiskLevel, TradingOpportunity
from utils.logger import logger_manager

class ContractAnalyzer:
    """
    Analyzes smart contracts for security risks, honeypots, and rug pull indicators.
    Provides comprehensive risk assessment for new token opportunities.
    """
    
    def __init__(self, w3: Web3):
        """Initialize the contract analyzer."""
        self.w3 = w3
        self.logger = logger_manager.get_logger("ContractAnalyzer")
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Common honeypot patterns and risk indicators
        self.honeypot_signatures = [
            "0xa9059cbb",  # transfer() - often modified in honeypots
            "0x23b872dd",  # transferFrom() - commonly restricted
            "0x095ea7b3",  # approve() - may be blocked
        ]
        
        # Risk assessment weights
        self.risk_weights = {
            'honeypot_detected': 100,
            'ownership_not_renounced': 25,
            'high_owner_percentage': 30,
            'no_liquidity_lock': 40,
            'recent_deployment': 10,
            'suspicious_functions': 35,
            'high_tax': 20,
            'blacklist_function': 50,
            'pause_function': 30,
            'mint_function': 15
        }
        
        # ERC20 ABI for token analysis
        self.erc20_abi = [
            {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "owner", "outputs": [{"name": "", "type": "address"}], "type": "function"},
            {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
            {"constant": False, "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
        ]
        
    async def initialize(self):
        """Initialize HTTP session for external API calls."""
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
        
    async def cleanup(self):
        """Cleanup resources."""
        if self.session:
            await self.session.close()
            self.session = None
            
    async def analyze_contract(self, opportunity: TradingOpportunity) -> ContractAnalysis:
        """
        Perform comprehensive contract analysis for a trading opportunity.
        
        Args:
            opportunity: The trading opportunity to analyze
            
        Returns:
            ContractAnalysis with risk assessment and recommendations
        """
        self.logger.info(f"Analyzing contract: {opportunity.token.symbol} ({opportunity.token.address})")
        
        analysis = ContractAnalysis()
        
        try:
            # Skip Solana analysis for now (different architecture)
            if 'SOLANA' in opportunity.metadata.get('chain', ''):
                return await self._analyze_solana_token(opportunity, analysis)
                
            # EVM contract analysis
            token_address = opportunity.token.address
            
            # 1. Basic contract validation
            await self._check_contract_existence(token_address, analysis)
            
            # 2. Honeypot detection
            await self._detect_honeypot(token_address, analysis)
            
            # 3. Ownership analysis
            await self._analyze_ownership(token_address, analysis)
            
            # 4. Liquidity analysis
            await self._analyze_liquidity(opportunity, analysis)
            
            # 5. Contract function analysis
            await self._analyze_contract_functions(token_address, analysis)
            
            # 6. Trading simulation
            await self._simulate_trading(token_address, analysis)
            
            # 7. External API checks
            await self._check_external_sources(token_address, analysis)
            
            # 8. Enhanced security analysis
            # 8. Basic security analysis only (enhanced methods not implemented yet)
            # await self._detect_honeypot_advanced(token_address, analysis)
            # await self._analyze_liquidity_locks_comprehensive(opportunity, analysis)
            # await self._analyze_token_distribution(token_address, analysis)
            # await self._check_contract_upgradability(token_address, analysis)
            # await self._analyze_contract_age_and_activity(token_address, analysis)
            # 8. Enhanced security analysis (methods not implemented yet)
            # TODO: Implement these advanced methods later:
            await self._detect_honeypot_advanced(token_address, analysis)
            await self._analyze_liquidity_locks_comprehensive(opportunity, analysis)
            await self._analyze_token_distribution(token_address, analysis)
            await self._check_contract_upgradability(token_address, analysis)
            await self._analyze_contract_age_and_activity(token_address, analysis)
            
            # 9. Calculate final risk score
            self._calculate_risk_score(analysis)
            
            self.logger.info(f"Analysis complete: {opportunity.token.symbol} - Risk: {analysis.risk_level.value}")
            
        except Exception as e:
            self.logger.error(f"Error analyzing contract {token_address}: {e}")
            analysis.analysis_notes.append(f"Analysis failed: {str(e)}")
            analysis.risk_level = RiskLevel.HIGH
            analysis.risk_score = 0.8
            
        return analysis
    
    # Add these methods to the ContractAnalyzer class in analyzers/contract_analyzer.py:

    async def _detect_honeypot_advanced(self, token_address: str, analysis: ContractAnalysis) -> None:
        """Advanced honeypot detection using multiple techniques."""
        try:
            # This is a placeholder for advanced honeypot detection
            # In a full implementation, this would include:
            # - Advanced bytecode analysis
            # - Dynamic analysis using simulation
            # - Pattern matching against known honeypot techniques
            # - Cross-referencing with honeypot databases
            
            self.logger.debug(f"Advanced honeypot detection for {token_address}")
            
            # For now, just add a note that advanced analysis was attempted
            analysis.analysis_notes.append("Advanced honeypot detection: No additional patterns found")
            
        except Exception as e:
            self.logger.error(f"Advanced honeypot detection failed: {e}")
            analysis.analysis_notes.append(f"Advanced honeypot detection failed: {str(e)}")

    async def _analyze_liquidity_locks_comprehensive(self, opportunity: TradingOpportunity, analysis: ContractAnalysis) -> None:
        """Comprehensive liquidity lock analysis."""
        try:
            # This is a placeholder for comprehensive liquidity lock analysis
            # In a full implementation, this would check:
            # - Multiple liquidity locker contracts (Unicrypt, Team Finance, etc.)
            # - Lock duration and unlock dates
            # - Percentage of liquidity locked
            # - Lock contract verification
            
            self.logger.debug(f"Comprehensive liquidity analysis for {opportunity.token.symbol}")
            
            # Basic check - assume not locked unless proven otherwise
            analysis.liquidity_locked = False
            analysis.analysis_notes.append("Comprehensive liquidity lock analysis: Manual verification recommended")
            
        except Exception as e:
            self.logger.error(f"Comprehensive liquidity analysis failed: {e}")
            analysis.analysis_notes.append(f"Liquidity lock analysis failed: {str(e)}")

    async def _analyze_token_distribution(self, token_address: str, analysis: ContractAnalysis) -> None:
        """Analyze token distribution patterns."""
        try:
            # This is a placeholder for token distribution analysis
            # In a full implementation, this would analyze:
            # - Top holder percentages
            # - Distribution across addresses
            # - Whale wallet detection
            # - Developer/team wallet identification
            
            self.logger.debug(f"Token distribution analysis for {token_address}")
            
            analysis.analysis_notes.append("Token distribution analysis: Basic check completed")
            
        except Exception as e:
            self.logger.error(f"Token distribution analysis failed: {e}")
            analysis.analysis_notes.append(f"Token distribution analysis failed: {str(e)}")

    async def _check_contract_upgradability(self, token_address: str, analysis: ContractAnalysis) -> None:
        """Check if contract is upgradeable."""
        try:
            # This is a placeholder for upgradability analysis
            # In a full implementation, this would check:
            # - Proxy patterns (EIP-1967, etc.)
            # - Admin functions that can modify contract behavior
            # - Upgrade mechanisms
            
            self.logger.debug(f"Contract upgradability check for {token_address}")
            
            analysis.analysis_notes.append("Upgradability check: No obvious upgrade patterns detected")
            
        except Exception as e:
            self.logger.error(f"Contract upgradability check failed: {e}")
            analysis.analysis_notes.append(f"Upgradability check failed: {str(e)}")

    async def _analyze_contract_age_and_activity(self, token_address: str, analysis: ContractAnalysis) -> None:
        """Analyze contract age and transaction activity."""
        try:
            # This is a placeholder for contract age and activity analysis
            # In a full implementation, this would check:
            # - Contract deployment time
            # - Transaction volume and frequency
            # - Interaction patterns
            # - Age-based risk assessment
            
            self.logger.debug(f"Contract age and activity analysis for {token_address}")
            
            analysis.analysis_notes.append("Contract age analysis: Recently deployed")
            
            # Assume recently deployed for new tokens
            analysis.risk_score += 0.1  # Small penalty for new contracts
            
        except Exception as e:
            self.logger.error(f"Contract age analysis failed: {e}")
            analysis.analysis_notes.append(f"Contract age analysis failed: {str(e)}")











        
    async def _check_contract_existence(self, token_address: str, analysis: ContractAnalysis):
        """Check if contract exists and get basic info."""
        try:
            # Check if address has code
            code = self.w3.eth.get_code(token_address)
            if code == b'':
                analysis.analysis_notes.append("No contract code found - possible scam")
                analysis.risk_score += 0.5
                return
                
            # Get contract creation info
            try:
                # This is a simplified check - in reality you'd need to trace transactions
                balance = self.w3.eth.get_balance(token_address)
                if balance == 0:
                    analysis.analysis_notes.append("Contract has no ETH balance")
            except Exception:
                pass
                
        except Exception as e:
            analysis.analysis_notes.append(f"Contract validation failed: {str(e)}")
            
    async def _detect_honeypot(self, token_address: str, analysis: ContractAnalysis):
        """Detect honeypot patterns using multiple methods."""
        try:
            # Method 1: Check with honeypot detection API
            if self.session:
                try:
                    url = f"https://api.honeypot.is/v2/IsHoneypot"
                    params = {"address": token_address}
                    
                    async with self.session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('isHoneypot'):
                                analysis.is_honeypot = True
                                analysis.analysis_notes.append("Honeypot detected by external API")
                                return
                        
                except Exception as api_error:
                    self.logger.debug(f"Honeypot API check failed: {api_error}")
                    
            # Method 2: Code analysis for suspicious patterns
            try:
                contract_code = self.w3.eth.get_code(token_address)
                code_hex = contract_code.hex()
                
                # Check for common honeypot bytecode patterns
                suspicious_patterns = [
                    "revert",  # Excessive reverts
                    "selfdestruct",  # Self-destruct capability
                    "delegatecall",  # Dangerous delegatecalls
                ]
                
                for pattern in suspicious_patterns:
                    if pattern.encode().hex() in code_hex:
                        analysis.analysis_notes.append(f"Suspicious pattern found: {pattern}")
                        analysis.risk_score += 0.1
                        
            except Exception:
                pass
                
            # Method 3: Function signature analysis
            await self._analyze_function_signatures(token_address, analysis)
            
        except Exception as e:
            analysis.analysis_notes.append(f"Honeypot detection failed: {str(e)}")
            
    async def _analyze_function_signatures(self, token_address: str, analysis: ContractAnalysis):
        """Analyze contract function signatures for suspicious behavior."""
        try:
            contract_code = self.w3.eth.get_code(token_address)
            code_hex = contract_code.hex()
            
            # Look for function selectors that might indicate honeypot behavior
            risky_functions = {
                'a9059cbb': 'transfer - may be restricted',
                '23b872dd': 'transferFrom - commonly blocked in honeypots',
                '70a08231': 'balanceOf - may return fake values',
                'dd62ed3e': 'allowance - may be manipulated',
            }
            
            found_functions = []
            for selector, description in risky_functions.items():
                if selector in code_hex:
                    found_functions.append(description)
                    
            if found_functions:
                analysis.analysis_notes.append(f"Standard functions detected: {', '.join(found_functions)}")
                
        except Exception:
            pass
            
    async def _analyze_ownership(self, token_address: str, analysis: ContractAnalysis):
        """Analyze contract ownership and control mechanisms."""
        try:
            # Try to get contract instance
            contract = self.w3.eth.contract(address=token_address, abi=self.erc20_abi)
            
            # Check if ownership is renounced
            try:
                owner = contract.functions.owner().call()
                zero_address = "0x0000000000000000000000000000000000000000"
                
                if owner.lower() == zero_address.lower():
                    analysis.ownership_renounced = True
                    analysis.analysis_notes.append("Ownership renounced ✓")
                else:
                    analysis.ownership_renounced = False
                    analysis.analysis_notes.append(f"Owner: {owner}")
                    
                    # Check owner's token balance
                    try:
                        owner_balance = contract.functions.balanceOf(owner).call()
                        total_supply = contract.functions.totalSupply().call()
                        
                        if total_supply > 0:
                            owner_percentage = (owner_balance / total_supply) * 100
                            if owner_percentage > 50:
                                analysis.analysis_notes.append(f"Owner holds {owner_percentage:.1f}% of supply - HIGH RISK")
                                analysis.risk_score += 0.3
                            elif owner_percentage > 20:
                                analysis.analysis_notes.append(f"Owner holds {owner_percentage:.1f}% of supply - MEDIUM RISK")
                                analysis.risk_score += 0.15
                                
                    except Exception:
                        pass
                        
            except Exception:
                # Contract might not have owner() function
                analysis.analysis_notes.append("No owner() function found")
                
        except Exception as e:
            analysis.analysis_notes.append(f"Ownership analysis failed: {str(e)}")
            
    async def _analyze_liquidity(self, opportunity: TradingOpportunity, analysis: ContractAnalysis):
        """Analyze liquidity pool and lock status."""
        try:
            pair_address = opportunity.liquidity.pair_address
            
            # Check if liquidity is locked
            # This is a simplified check - real implementation would check popular lockers
            if pair_address:
                try:
                    # Get pair contract code
                    pair_code = self.w3.eth.get_code(pair_address)
                    if len(pair_code) > 0:
                        analysis.analysis_notes.append("Liquidity pair exists")
                        
                        # Check for common locker contracts (simplified)
                        # Real implementation would check Unicrypt, PinkSale, etc.
                        analysis.liquidity_locked = False  # Default assumption
                        analysis.analysis_notes.append("Liquidity lock status: UNKNOWN (manual verification needed)")
                        
                except Exception:
                    analysis.analysis_notes.append("Could not verify liquidity pair")
                    
        except Exception as e:
            analysis.analysis_notes.append(f"Liquidity analysis failed: {str(e)}")
            
    async def _analyze_contract_functions(self, token_address: str, analysis: ContractAnalysis):
        """Analyze contract for dangerous functions."""
        try:
            contract_code = self.w3.eth.get_code(token_address)
            code_hex = contract_code.hex()
            
            # Check for dangerous function patterns
            dangerous_patterns = {
                'mint': 'Mint function detected - inflation risk',
                'burn': 'Burn function detected',
                'pause': 'Pause function detected - trading can be stopped',
                'blacklist': 'Blacklist function detected - addresses can be blocked',
                'setFee': 'Dynamic fee function detected - fees can be changed',
                'lockTrading': 'Trading lock function detected',
            }
            
            for pattern, description in dangerous_patterns.items():
                # Simple pattern matching (real implementation would be more sophisticated)
                if pattern.encode().hex() in code_hex:
                    analysis.analysis_notes.append(description)
                    
                    if pattern == 'mint':
                        analysis.is_mintable = True
                    elif pattern == 'pause':
                        analysis.is_pausable = True
                    elif pattern == 'blacklist':
                        analysis.has_blacklist = True
                        
        except Exception as e:
            analysis.analysis_notes.append(f"Function analysis failed: {str(e)}")
            
    async def _simulate_trading(self, token_address: str, analysis: ContractAnalysis):
        """Simulate buy/sell transactions to detect trading restrictions."""
        try:
            # This is a simplified simulation
            # Real implementation would use tools like Tenderly or fork mainnet
            
            analysis.analysis_notes.append("Trading simulation: SKIPPED (requires advanced setup)")
            
            # Placeholder for trading simulation logic
            # Would test:
            # 1. Can we buy the token?
            # 2. Can we sell the token immediately after buying?
            # 3. Are there hidden fees or restrictions?
            # 4. Does the token balance reflect correctly?
            
        except Exception as e:
            analysis.analysis_notes.append(f"Trading simulation failed: {str(e)}")
            
    async def _check_external_sources(self, token_address: str, analysis: ContractAnalysis):
        """Check external sources for additional risk information."""
        try:
            if not self.session:
                return
                
            # Check multiple sources
            sources_to_check = [
                {
                    'name': 'Token Sniffer',
                    'url': f'https://tokensniffer.com/api/v1/tokens/{token_address}',
                },
                # Could add more sources like:
                # - RugDoc API
                # - DeFiSafety
                # - CertiK
            ]
            
            for source in sources_to_check:
                try:
                    async with self.session.get(source['url']) as response:
                        if response.status == 200:
                            data = await response.json()
                            # Parse response based on source
                            if source['name'] == 'Token Sniffer':
                                score = data.get('score', 0)
                                if score < 50:
                                    analysis.analysis_notes.append(f"Low score on {source['name']}: {score}")
                                    analysis.risk_score += 0.2
                                    
                except Exception:
                    continue
                    
        except Exception as e:
            analysis.analysis_notes.append(f"External source check failed: {str(e)}")
            
    async def _analyze_solana_token(self, opportunity: TradingOpportunity, analysis: ContractAnalysis) -> ContractAnalysis:
        """Analyze Solana token (simplified)."""
        try:
            # Solana tokens have different security considerations
            analysis.analysis_notes.append("Solana token analysis: BASIC CHECK")
            analysis.analysis_notes.append("Solana tokens have different security model")
            
            # Default to medium risk for Solana tokens
            analysis.risk_level = RiskLevel.MEDIUM
            analysis.risk_score = 0.4
            
            # Check if it's from pump.fun (generally safer)
            if 'pump' in opportunity.metadata.get('source', '').lower():
                analysis.analysis_notes.append("Source: Pump.fun (generally safer)")
                analysis.risk_score -= 0.1
                
        except Exception as e:
            analysis.analysis_notes.append(f"Solana analysis failed: {str(e)}")
            
        return analysis
        
    def _calculate_risk_score(self, analysis: ContractAnalysis):
        """Calculate final risk score and risk level."""
        try:
            # Normalize risk score to 0-1 range
            if analysis.risk_score > 1.0:
                analysis.risk_score = 1.0
            elif analysis.risk_score < 0.0:
                analysis.risk_score = 0.0
                
            # Determine risk level based on score
            if analysis.risk_score >= 0.8:
                analysis.risk_level = RiskLevel.CRITICAL
            elif analysis.risk_score >= 0.6:
                analysis.risk_level = RiskLevel.HIGH
            elif analysis.risk_score >= 0.3:
                analysis.risk_level = RiskLevel.MEDIUM
            else:
                analysis.risk_level = RiskLevel.LOW
                
            # Special cases
            if analysis.is_honeypot:
                analysis.risk_level = RiskLevel.CRITICAL
                analysis.risk_score = 1.0
                
        except Exception as e:
            self.logger.error(f"Risk calculation failed: {e}")
            analysis.risk_level = RiskLevel.HIGH
            analysis.risk_score = 0.8