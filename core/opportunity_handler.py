#!/usr/bin/env python3
"""
Fixed OpportunityHandler with proper error handling and data type validation.

File: core/opportunity_handler.py
Class: OpportunityHandler  
Method: handle_opportunity - Fixed metadata.get() usage and chain validation
"""

import asyncio
import random
import json
from typing import Dict, List, Optional, Any, Union, Set
from datetime import datetime
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
            