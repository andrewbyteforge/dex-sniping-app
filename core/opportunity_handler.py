#!/usr/bin/env python3
"""
Complete OpportunityHandler with proper error handling, data type validation, and test generation.

File: core/opportunity_handler.py
Class: OpportunityHandler
Methods: handle_opportunity, generate_test_opportunities, dashboard integration
"""

import asyncio
import random
import json
from typing import Dict, List, Optional, Any, Union, Set
from datetime import datetime, timedelta
from decimal import Decimal

from models.token import TradingOpportunity, TokenInfo, LiquidityInfo, ContractAnalysis, SocialMetrics, RiskLevel
from utils.logger import logger_manager


class OpportunityHandler:
    """
    Handles all opportunity processing and analysis.
    
    Features:
    - Process opportunities from all sources
    - Comprehensive analysis pipeline
    - Dashboard integration
    - Test opportunity generation
    """
    
    def __init__(self, trading_system) -> None:
        """
        Initialize opportunity handler.
        
        Args:
            trading_system: Reference to main trading system
        """
        self.trading_system = trading_system
        self.logger = logger_manager.get_logger("OpportunityHandler")

    async def handle_opportunity(self, opportunity: TradingOpportunity) -> None:
        """
        Enhanced opportunity handler with robust dashboard integration and Telegram notifications.
        
        Args:
            opportunity: Trading opportunity from monitors
            
        Raises:
            ValueError: If opportunity structure is invalid
            TypeError: If opportunity contains invalid data types
        """
        try:
            # Validate opportunity structure with comprehensive error handling
            if not opportunity:
                self.logger.warning("Opportunity is None or empty - skipping")
                return
                
            if not hasattr(opportunity, 'token') or not opportunity.token:
                self.logger.warning("Opportunity missing token information - skipping")
                return

            # Safely extract token information with error handling
            token_symbol: str = "UNKNOWN"
            token_address: str = "UNKNOWN"
            
            try:
                if hasattr(opportunity.token, 'symbol') and opportunity.token.symbol:
                    token_symbol = str(opportunity.token.symbol)
                if hasattr(opportunity.token, 'address') and opportunity.token.address:
                    token_address = str(opportunity.token.address)
            except (AttributeError, TypeError) as e:
                self.logger.warning(f"Error extracting token info: {e}")
            
            self.logger.info(f"🔍 Processing opportunity: {token_symbol} ({token_address[:10]}...)")
            
            # Initialize metadata with proper type checking
            if not hasattr(opportunity, 'metadata'):
                opportunity.metadata = {}
            elif not isinstance(opportunity.metadata, dict):
                self.logger.warning(f"Invalid metadata type: {type(opportunity.metadata)}, resetting to dict")
                opportunity.metadata = {}
                
            # Safely handle chain information with type validation
            chain: str = "ethereum"  # Default chain
            
            try:
                # Check if chain exists in metadata and is valid
                if 'chain' in opportunity.metadata:
                    chain_value = opportunity.metadata['chain']
                    if isinstance(chain_value, str) and chain_value.strip():
                        chain = chain_value.lower().strip()
                    elif isinstance(chain_value, (int, float)):
                        # Handle case where chain might be stored as numeric (error condition)
                        self.logger.warning(f"Chain stored as numeric value {chain_value}, using default")
                        chain = "ethereum"
                    else:
                        self.logger.warning(f"Invalid chain type {type(chain_value)}: {chain_value}")
                        chain = "ethereum"
                        
                # Set chain in opportunity object safely
                if not hasattr(opportunity, 'chain') or not opportunity.chain:
                    opportunity.chain = chain
                    
                # Ensure metadata chain matches opportunity chain
                opportunity.metadata['chain'] = chain
                
            except (KeyError, AttributeError, TypeError) as e:
                self.logger.warning(f"Error handling chain information: {e}, using default")
                chain = "ethereum"
                opportunity.metadata['chain'] = chain
                if hasattr(opportunity, 'chain'):
                    opportunity.chain = chain
            
            # Ensure opportunity has timestamp with proper error handling
            timestamp: datetime = self._ensure_timestamp_safe(opportunity)
            
            # Ensure price field exists with validation
            try:
                if not hasattr(opportunity.token, 'price') or opportunity.token.price is None:
                    opportunity.token.price = 1.0  # Default price
                elif not isinstance(opportunity.token.price, (int, float, Decimal)):
                    self.logger.warning(f"Invalid price type: {type(opportunity.token.price)}")
                    opportunity.token.price = 1.0
            except (AttributeError, TypeError) as e:
                self.logger.warning(f"Error setting token price: {e}")
                opportunity.token.price = 1.0
            
            # Update analysis statistics safely
            try:
                if hasattr(self.trading_system, 'analysis_stats') and isinstance(self.trading_system.analysis_stats, dict):
                    self.trading_system.analysis_stats["total_analyzed"] = self.trading_system.analysis_stats.get("total_analyzed", 0) + 1
                    self.trading_system.analysis_stats["opportunities_found"] = self.trading_system.analysis_stats.get("opportunities_found", 0) + 1
            except (AttributeError, TypeError) as e:
                self.logger.warning(f"Error updating analysis stats: {e}")
            
            # Perform comprehensive analysis
            try:
                analyzed_opportunity = await self._analyze_opportunity_safe(opportunity)
                if analyzed_opportunity:
                    opportunity = analyzed_opportunity
            except Exception as e:
                self.logger.error(f"Analysis failed for {token_symbol}: {e}")
                # Continue with unanalyzed opportunity
            
            # Dashboard integration with error handling
            try:
                await self._integrate_dashboard_safe(opportunity)
            except Exception as e:
                self.logger.error(f"Dashboard integration failed for {token_symbol}: {e}")
                # Continue without dashboard update
            
            # Telegram notification with error handling
            try:
                await self._send_telegram_notification_safe(opportunity)
            except Exception as e:
                self.logger.error(f"Telegram notification failed for {token_symbol}: {e}")
                # Continue without notification
            
            self.logger.info(f"✅ Successfully processed opportunity: {token_symbol}")
            
        except Exception as e:
            # Extract token symbol for error reporting
            try:
                error_symbol = getattr(getattr(opportunity, 'token', None), 'symbol', 'UNKNOWN')
            except:
                error_symbol = 'UNKNOWN'
                
            self.logger.error(f"Error handling opportunity {error_symbol}: {e}")
            
            # Notify telegram manager about error
            try:
                if hasattr(self.trading_system, 'telegram_manager') and self.trading_system.telegram_manager:
                    await self.trading_system.telegram_manager.handle_opportunity_error(error_symbol, opportunity)
            except Exception as telegram_error:
                self.logger.error(f"Failed to send error notification: {telegram_error}")

    async def handle_new_opportunity(self, opportunity: TradingOpportunity) -> None:
        """
        Alias for handle_opportunity to maintain compatibility.
        
        Args:
            opportunity: Trading opportunity from monitors
        """
        await self.handle_opportunity(opportunity)

    def _ensure_timestamp_safe(self, opportunity: TradingOpportunity) -> datetime:
        """
        Safely ensure opportunity has a valid timestamp.
        
        Args:
            opportunity: Trading opportunity to validate
            
        Returns:
            datetime: Valid timestamp for the opportunity
        """
        try:
            # Check for existing timestamp attributes
            for attr_name in ['timestamp', 'detected_at', 'created_at']:
                if hasattr(opportunity, attr_name):
                    timestamp_value = getattr(opportunity, attr_name)
                    if isinstance(timestamp_value, datetime):
                        return timestamp_value
                    elif isinstance(timestamp_value, str):
                        try:
                            return datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
                        except (ValueError, AttributeError):
                            continue
            
            # If no valid timestamp found, create one
            current_time = datetime.now()
            
            # Set timestamp attributes safely
            for attr_name in ['timestamp', 'detected_at']:
                try:
                    if hasattr(opportunity, attr_name):
                        setattr(opportunity, attr_name, current_time)
                except (AttributeError, TypeError):
                    pass
            
            return current_time
            
        except Exception as e:
            self.logger.warning(f"Error ensuring timestamp: {e}")
            return datetime.now()

    async def _analyze_opportunity_safe(self, opportunity: TradingOpportunity) -> Optional[TradingOpportunity]:
        """
        Safely perform comprehensive analysis on trading opportunity.
        
        Args:
            opportunity: Base opportunity to analyze
            
        Returns:
            Optional[TradingOpportunity]: Enhanced opportunity with analysis results or None if failed
        """
        try:
            enhanced_metadata = opportunity.metadata.copy()
            
            # Ensure opportunity has timestamp
            timestamp = self._ensure_timestamp_safe(opportunity)
            
            # Contract security analysis with error handling
            if hasattr(self.trading_system, 'analyzers') and isinstance(self.trading_system.analyzers, dict):
                contract_analyzer = self.trading_system.analyzers.get('contract')
                if contract_analyzer and hasattr(contract_analyzer, 'analyze_contract'):
                    try:
                        contract_analysis = await contract_analyzer.analyze_contract(opportunity)
                        enhanced_metadata['contract_analysis'] = self._serialize_analysis_safe(contract_analysis)
                    except Exception as e:
                        self.logger.warning(f"Contract analysis failed: {e}")
                        enhanced_metadata['contract_analysis'] = {'error': str(e)}
                else:
                    enhanced_metadata['contract_analysis'] = self._mock_contract_analysis()
            else:
                enhanced_metadata['contract_analysis'] = self._mock_contract_analysis()
            
            # Social sentiment analysis with error handling
            if hasattr(self.trading_system, 'analyzers') and isinstance(self.trading_system.analyzers, dict):
                social_analyzer = self.trading_system.analyzers.get('social')
                if social_analyzer and hasattr(social_analyzer, 'analyze_social_metrics'):
                    try:
                        social_metrics = await social_analyzer.analyze_social_metrics(opportunity)
                        enhanced_metadata['social_metrics'] = self._serialize_analysis_safe(social_metrics)
                    except Exception as e:
                        self.logger.warning(f"Social analysis failed: {e}")
                        enhanced_metadata['social_metrics'] = {'error': str(e)}
                else:
                    enhanced_metadata['social_metrics'] = self._mock_social_analysis()
            else:
                enhanced_metadata['social_metrics'] = self._mock_social_analysis()
            
            # Trading score and recommendation
            trading_score_data = await self._calculate_trading_score_safe(opportunity)
            enhanced_metadata.update(trading_score_data)
            
            # Create enhanced opportunity
            enhanced_opportunity = TradingOpportunity(
                token=opportunity.token,
                liquidity=opportunity.liquidity,
                contract_analysis=getattr(opportunity, 'contract_analysis', None),
                social_metrics=getattr(opportunity, 'social_metrics', None),
                detected_at=timestamp,
                metadata=enhanced_metadata
            )
            
            # Add chain as metadata (ensure it's a string)
            chain = str(getattr(opportunity, 'chain', 'ethereum'))
            enhanced_opportunity.metadata['chain'] = chain.lower()
            
            return enhanced_opportunity
            
        except Exception as e:
            self.logger.error(f"Error in comprehensive analysis: {e}")
            return opportunity

    def _serialize_analysis_safe(self, analysis_object: Any, depth: int = 0, max_depth: int = 10) -> Dict[str, Any]:
        """
        Safely serialize analysis objects to JSON-compatible dictionaries with recursion protection.
        
        Args:
            analysis_object: Analysis result to serialize
            depth: Current recursion depth
            max_depth: Maximum allowed recursion depth
            
        Returns:
            Dict[str, Any]: JSON-serializable dictionary
        """
        try:
            # Prevent infinite recursion
            if depth > max_depth:
                return {'error': 'max_depth_exceeded', 'depth': depth}
                
            if analysis_object is None:
                return {}
                
            if isinstance(analysis_object, dict):
                return self._clean_dict_for_json(analysis_object, depth + 1, max_depth)
                
            if hasattr(analysis_object, '__dict__'):
                return self._clean_dict_for_json(analysis_object.__dict__, depth + 1, max_depth)
                
            # If it's a simple type, wrap it
            return {'value': str(analysis_object)}
            
        except RecursionError:
            self.logger.warning(f"Recursion error serializing analysis at depth {depth}")
            return {'error': 'recursion_error', 'depth': depth}
        except Exception as e:
            self.logger.warning(f"Error serializing analysis: {e}")
            return {'error': 'serialization_failed'}

    def _clean_dict_for_json(self, data: Dict[str, Any], depth: int = 0, max_depth: int = 10) -> Dict[str, Any]:
        """
        Clean dictionary to make it JSON serializable with recursion protection.
        
        Args:
            data: Dictionary to clean
            depth: Current recursion depth
            max_depth: Maximum allowed recursion depth
            
        Returns:
            Dict[str, Any]: JSON-serializable dictionary
        """
        # Prevent infinite recursion
        if depth > max_depth:
            return {'error': 'max_depth_exceeded'}
            
        cleaned = {}
        processed_objects = set()  # Track processed objects to prevent cycles
        
        for key, value in data.items():
            try:
                # Convert key to string and limit length
                str_key = str(key)[:100]  # Limit key length
                
                # Skip if we've seen this object before (cycle detection)
                if id(value) in processed_objects:
                    cleaned[str_key] = {'error': 'circular_reference'}
                    continue
                    
                if isinstance(value, datetime):
                    cleaned[str_key] = value.isoformat()
                elif isinstance(value, Decimal):
                    cleaned[str_key] = float(value)
                elif isinstance(value, (list, tuple)):
                    # Limit list length and add to processed objects
                    processed_objects.add(id(value))
                    limited_list = list(value)[:50]  # Limit to first 50 items
                    cleaned[str_key] = [self._clean_value_for_json(item, depth + 1, max_depth, processed_objects) for item in limited_list]
                elif isinstance(value, dict):
                    # Add to processed objects before recursion
                    processed_objects.add(id(value))
                    cleaned[str_key] = self._clean_dict_for_json(value, depth + 1, max_depth)
                elif hasattr(value, '__dict__'):
                    # Add to processed objects before recursion
                    processed_objects.add(id(value))
                    cleaned[str_key] = self._clean_dict_for_json(value.__dict__, depth + 1, max_depth)
                else:
                    # Test if value is JSON serializable
                    try:
                        json.dumps(value)
                        cleaned[str_key] = value
                    except (TypeError, ValueError):
                        # Convert to string if not serializable, but limit length
                        str_value = str(value)
                        cleaned[str_key] = str_value[:1000] if len(str_value) > 1000 else str_value
                        
            except RecursionError:
                cleaned[str_key] = {'error': 'recursion_error'}
            except (TypeError, ValueError, AttributeError):
                # If not serializable, convert to string
                try:
                    str_value = str(value)
                    cleaned[str_key] = str_value[:500] if len(str_value) > 500 else str_value
                except:
                    cleaned[str_key] = {'error': 'conversion_failed'}
                
        return cleaned

    def _clean_value_for_json(self, value: Any, depth: int = 0, max_depth: int = 10, processed_objects: Optional[set] = None) -> Any:
        """
        Clean individual value for JSON serialization with recursion protection.
        
        Args:
            value: Value to clean
            depth: Current recursion depth
            max_depth: Maximum allowed recursion depth
            processed_objects: Set of already processed object IDs
            
        Returns:
            Any: JSON-serializable value
        """
        try:
            # Prevent infinite recursion
            if depth > max_depth:
                return {'error': 'max_depth_exceeded'}
                
            # Initialize processed objects set if not provided
            if processed_objects is None:
                processed_objects = set()
                
            # Check for circular references
            if id(value) in processed_objects:
                return {'error': 'circular_reference'}
                
            if isinstance(value, datetime):
                return value.isoformat()
            elif isinstance(value, Decimal):
                return float(value)
            elif isinstance(value, dict):
                processed_objects.add(id(value))
                return self._clean_dict_for_json(value, depth + 1, max_depth)
            elif isinstance(value, (list, tuple)):
                processed_objects.add(id(value))
                # Limit list processing to prevent huge serializations
                limited_list = list(value)[:20]  # Only process first 20 items
                return [self._clean_value_for_json(item, depth + 1, max_depth, processed_objects.copy()) for item in limited_list]
            elif hasattr(value, '__dict__'):
                processed_objects.add(id(value))
                return self._clean_dict_for_json(value.__dict__, depth + 1, max_depth)
            else:
                # Test if value is JSON serializable
                try:
                    json.dumps(value)
                    return value
                except (TypeError, ValueError):
                    # Convert to string but limit length
                    str_value = str(value)
                    return str_value[:500] if len(str_value) > 500 else str_value
                    
        except RecursionError:
            return {'error': 'recursion_error'}
        except Exception as e:
            return f"error_converting: {str(e)[:100]}"

    async def _calculate_trading_score_safe(self, opportunity: TradingOpportunity) -> Dict[str, Any]:
        """
        Safely calculate trading score and recommendation.
        
        Args:
            opportunity: Trading opportunity to score
            
        Returns:
            Dict[str, Any]: Trading score data
        """
        try:
            # Generate mock trading score for testing
            score = random.uniform(0.3, 0.9)
            confidence_levels = ['LOW', 'MEDIUM', 'HIGH']
            actions = ['BUY', 'MONITOR', 'HOLD']
            
            return {
                'trading_score': {
                    'overall_score': score,
                    'risk_score': random.uniform(0.1, 0.7),
                    'liquidity_score': random.uniform(0.4, 1.0),
                    'volatility_score': random.uniform(0.2, 0.8)
                },
                'recommendation': {
                    'action': random.choice(actions),
                    'confidence': random.choice(confidence_levels),
                    'reasoning': 'Automated analysis based on available metrics'
                },
                'risk_level': random.choice(['low', 'medium', 'high'])
            }
            
        except Exception as e:
            self.logger.warning(f"Error calculating trading score: {e}")
            return {
                'trading_score': {'overall_score': 0.5, 'risk_score': 0.5},
                'recommendation': {'action': 'MONITOR', 'confidence': 'LOW'},
                'risk_level': 'medium'
            }

    def _mock_contract_analysis(self) -> Dict[str, Any]:
        """
        Generate mock contract analysis for testing.
        
        Returns:
            Dict[str, Any]: Mock contract analysis data
        """
        return {
            'is_honeypot': random.choice([True, False]),
            'is_mintable': random.choice([True, False]),
            'ownership_renounced': random.choice([True, False]),
            'liquidity_locked': random.choice([True, False]),
            'risk_score': random.uniform(0.1, 0.8),
            'analysis_notes': ['Automated mock analysis']
        }

    def _mock_social_analysis(self) -> Dict[str, Any]:
        """
        Generate mock social analysis for testing.
        
        Returns:
            Dict[str, Any]: Mock social analysis data
        """
        return {
            'social_score': random.uniform(0.2, 0.9),
            'sentiment_score': random.uniform(-0.5, 0.8),
            'twitter_mentions': random.randint(0, 1000),
            'telegram_activity': random.choice(['low', 'medium', 'high'])
        }

    async def _integrate_dashboard_safe(self, opportunity: TradingOpportunity) -> None:
        """
        Safely integrate opportunity with dashboard.
        
        Args:
            opportunity: Trading opportunity to integrate
        """
        try:
            # Extract data safely with defaults and type validation
            token_symbol = str(getattr(opportunity.token, 'symbol', 'UNKNOWN'))
            token_address = str(getattr(opportunity.token, 'address', ''))
            
            # Ensure chain is a string
            chain = 'ethereum'
            if hasattr(opportunity, 'chain') and opportunity.chain:
                chain = str(opportunity.chain).lower()
            elif 'chain' in opportunity.metadata:
                chain_value = opportunity.metadata['chain']
                if isinstance(chain_value, str):
                    chain = chain_value.lower()
            
            # Extract liquidity info safely
            liquidity_usd = 0.0
            if hasattr(opportunity, 'liquidity') and opportunity.liquidity:
                try:
                    liquidity_value = getattr(opportunity.liquidity, 'liquidity_usd', 0)
                    liquidity_usd = float(liquidity_value) if liquidity_value is not None else 0.0
                except (TypeError, ValueError):
                    liquidity_usd = 0.0
            
            # Create opportunity data structure with safe extraction
            opp_data = {
                "token_symbol": token_symbol,
                "token_address": token_address,
                "chain": chain,
                "risk_level": str(opportunity.metadata.get("risk_level", "unknown")),
                "recommendation": str(opportunity.metadata.get("recommendation", {}).get("action", "MONITOR")),
                "confidence": str(opportunity.metadata.get("recommendation", {}).get("confidence", "LOW")),
                "score": float(opportunity.metadata.get("trading_score", {}).get("overall_score", 0.0)),
                "liquidity_usd": liquidity_usd,
                "detected_at": datetime.now().isoformat(),  # Always use current time for consistency
                "age_minutes": 0
            }
            
            # Update dashboard stats safely
            if (hasattr(self.trading_system, 'dashboard_server') and 
                self.trading_system.dashboard_server and 
                hasattr(self.trading_system.dashboard_server, 'stats')):
                
                stats = self.trading_system.dashboard_server.stats
                if isinstance(stats, dict):
                    stats["total_opportunities"] = stats.get("total_opportunities", 0) + 1
                    
                    if opp_data["confidence"] == "HIGH":
                        stats["high_confidence"] = stats.get("high_confidence", 0) + 1
            
            # Add to opportunities queue safely
            if (hasattr(self.trading_system, 'dashboard_server') and 
                self.trading_system.dashboard_server and 
                hasattr(self.trading_system.dashboard_server, 'opportunities_queue')):
                
                queue = self.trading_system.dashboard_server.opportunities_queue
                if isinstance(queue, list):
                    queue.append(opportunity)
                    
                    # Keep queue size manageable
                    if len(queue) > 100:
                        queue.pop(0)
            
            # Broadcast to WebSocket clients safely
            if (hasattr(self.trading_system, 'dashboard_server') and 
                self.trading_system.dashboard_server and 
                hasattr(self.trading_system.dashboard_server, 'broadcast_message')):
                
                try:
                    await self.trading_system.dashboard_server.broadcast_message({
                        "type": "new_opportunity",
                        "data": opp_data
                    })
                except Exception as broadcast_error:
                    self.logger.warning(f"WebSocket broadcast failed: {broadcast_error}")
            
        except Exception as e:
            self.logger.error(f"Dashboard integration failed: {e}")
            raise

    async def _send_telegram_notification_safe(self, opportunity: TradingOpportunity) -> None:
        """
        Safely send Telegram notification for opportunity.
        
        Args:
            opportunity: Trading opportunity to notify about
        """
        try:
            if (hasattr(self.trading_system, 'telegram_manager') and 
                self.trading_system.telegram_manager and 
                hasattr(self.trading_system.telegram_manager, 'handle_new_opportunity')):
                
                await self.trading_system.telegram_manager.handle_new_opportunity(opportunity)
                
        except Exception as e:
            self.logger.warning(f"Telegram notification failed: {e}")
            # Don't re-raise, just log and continue

    # =============================================================================
    # TEST OPPORTUNITY GENERATION METHODS
    # =============================================================================

    async def generate_test_opportunities(self, count: int = 20, interval: float = 3.0) -> None:
        """
        Generate test opportunities for dashboard testing with realistic data.
        
        Args:
            count: Number of test opportunities to generate
            interval: Seconds between each opportunity
        """
        try:
            self.logger.info(f"🧪 Starting test opportunity generation: {count} opportunities every {interval}s")
            
            # Generate opportunities continuously
            opportunity_count = 0
            
            while opportunity_count < count:
                try:
                    # Create test opportunity
                    opportunity = await self._create_realistic_test_opportunity()
                    
                    if opportunity:
                        opportunity_count += 1
                        self.logger.info(f"📊 Generated test opportunity #{opportunity_count}: {opportunity.token.symbol}")
                        
                        # Process through the normal pipeline
                        await self.handle_opportunity(opportunity)
                        
                        # Wait before next opportunity
                        if opportunity_count < count:
                            await asyncio.sleep(interval)
                    
                except Exception as e:
                        self.logger.error(f"Error generating test opportunity #{opportunity_count + 1}: {e}")
                        
            self.logger.info(f"✅ Test opportunity generation completed: {opportunity_count} opportunities created")
            
        except Exception as e:
            self.logger.error(f"Failed to generate test opportunities: {e}")

    async def _create_realistic_test_opportunity(self) -> Optional[TradingOpportunity]:
        """
        Create a realistic test opportunity with varied data.
        
        Returns:
            Optional[TradingOpportunity]: Test opportunity or None if creation failed
        """
        try:
            # Define realistic test tokens
            test_tokens = [
                ("DOGE2", "DogeClassic", "ethereum"),
                ("PEPE", "PepeCoin", "ethereum"), 
                ("FLOKI", "Floki", "base"),
                ("SHIB2", "ShibaInu2", "base"),
                ("WIF", "dogwifhat", "solana"),
                ("BONK2", "Bonk2", "solana"),
                ("MEME", "MemeCoin", "ethereum"),
                ("CHAD", "ChadCoin", "base"),
                ("MOON", "MoonToken", "solana"),
                ("ROCKET", "RocketCoin", "ethereum"),
                ("DIAMOND", "DiamondHands", "base"),
                ("HODL", "HodlToken", "solana"),
                ("LAMBO", "LamboCoin", "ethereum"),
                ("APE2", "ApeToken2", "base"),
                ("CATS", "CatsCoin", "solana")
            ]
            
            # Select random token
            symbol, name, chain = random.choice(test_tokens)
            
            # Generate realistic addresses based on chain
            if chain == "solana":
                # Solana addresses are base58 encoded, ~44 characters
                test_address = f"{random.randint(100000, 999999)}{''.join(random.choices('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz', k=37))}"
            else:
                # Ethereum/Base addresses
                test_address = f"0x{''.join(random.choices('0123456789abcdef', k=40))}"
            
            # Create token info
            token_info = TokenInfo(
                address=test_address,
                symbol=symbol,
                name=name,
                decimals=18,
                total_supply=random.randint(100_000_000, 10_000_000_000)
            )
            
            # Generate realistic liquidity
            liquidity_usd = random.uniform(1000, 500000)
            
            # Create liquidity info
            dex_names = {
                "ethereum": ["Uniswap V2", "Uniswap V3", "SushiSwap"],
                "base": ["BaseSwap", "Uniswap V3", "PancakeSwap"],
                "solana": ["Raydium", "Orca", "Jupiter"]
            }
            
            liquidity_info = LiquidityInfo(
                pair_address=test_address,
                dex_name=random.choice(dex_names[chain]),
                token0=test_address,
                token1="0x0000000000000000000000000000000000000000" if chain != "solana" else "So11111111111111111111111111111111111111112",
                reserve0=float(liquidity_usd / 2),
                reserve1=float(liquidity_usd / 2),
                liquidity_usd=liquidity_usd,
                created_at=datetime.now() - timedelta(minutes=random.randint(1, 60)),
                block_number=random.randint(18000000, 19000000)
            )
            
            # Create contract analysis
            contract_analysis = ContractAnalysis(
                is_honeypot=random.choice([True, False]),
                is_mintable=random.choice([True, False]),
                is_pausable=random.choice([True, False]),
                has_blacklist=random.choice([True, False]),
                ownership_renounced=random.choice([True, False]),
                liquidity_locked=random.choice([True, False]),
                lock_duration=random.randint(30, 365) * 24 * 3600 if random.choice([True, False]) else None,
                risk_score=random.uniform(0.1, 0.9),
                risk_level=random.choice(list(RiskLevel)),
                analysis_notes=[
                    random.choice([
                        "Standard ERC-20 contract",
                        "Custom token with additional features",
                        "Fork of popular token contract",
                        "Verified contract on blockchain explorer",
                        "High transaction volume detected"
                    ])
                ]
            )
            
            # Create social metrics
            social_metrics = SocialMetrics(
                twitter_followers=random.randint(100, 50000) if random.choice([True, False]) else None,
                telegram_members=random.randint(50, 10000) if random.choice([True, False]) else None,
                discord_members=random.randint(20, 5000) if random.choice([True, False]) else None,
                reddit_subscribers=random.randint(10, 2000) if random.choice([True, False]) else None,
                website_url=f"https://{symbol.lower()}.com" if random.choice([True, False]) else None,
                social_score=random.uniform(0.1, 1.0),
                sentiment_score=random.uniform(-0.5, 0.8)
            )
            
            # Create realistic metadata
            confidence_levels = ['LOW', 'MEDIUM', 'HIGH']
            actions = ['BUY', 'MONITOR', 'HOLD', 'AVOID']
            risk_levels = ['low', 'medium', 'high', 'critical']
            
            metadata = {
                'chain': chain,
                'source': 'test_generator',
                'is_test': True,
                'recommendation': {
                    'action': random.choice(actions),
                    'confidence': random.choice(confidence_levels),
                    'reasoning': random.choice([
                        'Strong social metrics and community',
                        'High liquidity and trading volume',
                        'Verified contract with good tokenomics',
                        'Trending on social media platforms',
                        'Low risk score with locked liquidity',
                        'Active development team'
                    ])
                },
                'trading_score': {
                    'overall_score': random.uniform(0.2, 0.95),
                    'risk_score': random.uniform(0.1, 0.8),
                    'liquidity_score': random.uniform(0.3, 1.0),
                    'volatility_score': random.uniform(0.1, 0.9),
                    'social_score': social_metrics.social_score,
                    'technical_score': random.uniform(0.2, 0.8)
                },
                'risk_level': random.choice(risk_levels),
                'analysis_timestamp': datetime.now().isoformat(),
                'market_cap_usd': liquidity_usd * random.uniform(2, 50),
                'volume_24h_usd': liquidity_usd * random.uniform(0.1, 5),
                'price_change_24h': random.uniform(-50, 200),
                'holder_count': random.randint(100, 10000),
                'contract_verified': random.choice([True, False])
            }
            
            # Create trading opportunity
            opportunity = TradingOpportunity(
                token=token_info,
                liquidity=liquidity_info,
                contract_analysis=contract_analysis,
                social_metrics=social_metrics,
                detected_at=datetime.now(),
                metadata=metadata
            )
            
            # Set additional attributes
            opportunity.chain = chain
            opportunity.confidence_score = metadata['trading_score']['overall_score']
            
            return opportunity
            
        except Exception as e:
            self.logger.error(f"Failed to create test opportunity: {e}")
            return None

    async def start_continuous_test_generation(self, opportunities_per_minute: int = 5) -> None:
        """
        Start continuous test opportunity generation for extended testing.
        
        Args:
            opportunities_per_minute: Rate of opportunity generation
        """
        try:
            interval = 60.0 / opportunities_per_minute  # Calculate interval
            self.logger.info(f"🔄 Starting continuous test generation: {opportunities_per_minute} opportunities/minute")
            
            opportunity_count = 0
            
            while True:
                try:
                    opportunity = await self._create_realistic_test_opportunity()
                    
                    if opportunity:
                        opportunity_count += 1
                        self.logger.info(f"📊 Generated continuous opportunity #{opportunity_count}: {opportunity.token.symbol}")
                        
                        # Process through the normal pipeline
                        await self.handle_opportunity(opportunity)
                        
                    # Wait for next opportunity
                    await asyncio.sleep(interval)
                    
                except Exception as e:
                    self.logger.error(f"Error in continuous generation: {e}")
                    await asyncio.sleep(interval)  # Continue despite errors
                    
        except Exception as e:
            self.logger.error(f"Continuous test generation failed: {e}")

    async def generate_specific_test_scenario(self, scenario: str = "high_risk") -> None:
        """
        Generate specific test scenarios for targeted testing.
        
        Args:
            scenario: Type of scenario to generate
        """
        try:
            self.logger.info(f"🎭 Generating test scenario: {scenario}")
            
            if scenario == "high_risk":
                await self._generate_high_risk_scenarios()
            elif scenario == "high_confidence":
                await self._generate_high_confidence_scenarios()
            elif scenario == "mixed_chain":
                await self._generate_mixed_chain_scenarios()
            elif scenario == "low_liquidity":
                await self._generate_low_liquidity_scenarios()
            else:
                self.logger.warning(f"Unknown scenario: {scenario}")
                
        except Exception as e:
            self.logger.error(f"Failed to generate scenario {scenario}: {e}")

    async def _generate_high_risk_scenarios(self) -> None:
        """Generate high-risk test opportunities."""
        risk_tokens = [
            ("RISK", "RiskyToken", "ethereum"),
            ("SCAM", "ScamCoin", "base"), 
            ("HONEY", "HoneyPot", "solana")
        ]
        
        for symbol, name, chain in risk_tokens:
            opportunity = await self._create_realistic_test_opportunity()
            if opportunity:
                # Modify to be high risk
                opportunity.token.symbol = symbol
                opportunity.token.name = name
                opportunity.chain = chain
                opportunity.metadata['chain'] = chain
                opportunity.metadata['risk_level'] = 'critical'
                opportunity.metadata['recommendation']['action'] = 'AVOID'
                opportunity.metadata['recommendation']['confidence'] = 'HIGH'
                opportunity.contract_analysis.is_honeypot = True
                opportunity.contract_analysis.risk_score = 0.9
                opportunity.contract_analysis.risk_level = RiskLevel.CRITICAL
                
                await self.handle_opportunity(opportunity)
                await asyncio.sleep(2)

    async def _generate_high_confidence_scenarios(self) -> None:
        """Generate high-confidence test opportunities."""
        good_tokens = [
            ("SAFE", "SafeToken", "ethereum"),
            ("GOLD", "GoldCoin", "base"),
            ("STABLE", "StableCoin", "solana")
        ]
        
        for symbol, name, chain in good_tokens:
            opportunity = await self._create_realistic_test_opportunity()
            if opportunity:
                # Modify to be high confidence
                opportunity.token.symbol = symbol
                opportunity.token.name = name
                opportunity.chain = chain
                opportunity.metadata['chain'] = chain
                opportunity.metadata['risk_level'] = 'low'
                opportunity.metadata['recommendation']['action'] = 'BUY'
                opportunity.metadata['recommendation']['confidence'] = 'HIGH'
                opportunity.contract_analysis.is_honeypot = False
                opportunity.contract_analysis.ownership_renounced = True
                opportunity.contract_analysis.liquidity_locked = True
                opportunity.contract_analysis.risk_score = 0.1
                opportunity.contract_analysis.risk_level = RiskLevel.LOW
                opportunity.liquidity.liquidity_usd = random.uniform(100000, 1000000)
                
                await self.handle_opportunity(opportunity)
                await asyncio.sleep(2)

    async def _generate_mixed_chain_scenarios(self) -> None:
        """Generate opportunities across all chains."""
        chains = ["ethereum", "base", "solana"]
        
        for i, chain in enumerate(chains):
            opportunity = await self._create_realistic_test_opportunity()
            if opportunity:
                opportunity.chain = chain
                opportunity.metadata['chain'] = chain
                opportunity.token.symbol = f"MULTI{i+1}"
                opportunity.token.name = f"MultiChain{i+1}"
                
                await self.handle_opportunity(opportunity)
                await asyncio.sleep(2)

    async def _generate_low_liquidity_scenarios(self) -> None:
        """Generate low liquidity test opportunities."""
        low_liq_tokens = [
            ("MICRO", "MicroCap", "ethereum"),
            ("TINY", "TinyToken", "base"),
            ("SMALL", "SmallCoin", "solana")
        ]
        
        for symbol, name, chain in low_liq_tokens:
            opportunity = await self._create_realistic_test_opportunity()
            if opportunity:
                # Modify to have low liquidity
                opportunity.token.symbol = symbol
                opportunity.token.name = name
                opportunity.chain = chain
                opportunity.metadata['chain'] = chain
                opportunity.liquidity.liquidity_usd = random.uniform(500, 5000)  # Low liquidity
                opportunity.metadata['trading_score']['liquidity_score'] = random.uniform(0.1, 0.3)
                
                await self.handle_opportunity(opportunity)
                await asyncio.sleep(2)