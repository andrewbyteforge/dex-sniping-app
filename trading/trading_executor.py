#!/usr/bin/env python3
"""
Enhanced trading executor with automated execution and comprehensive risk management.

This module orchestrates the entire trading workflow from opportunity assessment
to position management and automated exit strategies.
"""

from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json

from models.token import TradingOpportunity, RiskLevel
from trading.risk_manager import RiskManager, PositionSizeResult, RiskAssessment
from trading.position_manager import PositionManager, Position, PositionStatus
from trading.execution_engine import ExecutionEngine, ExecutionResult
from utils.logger import logger_manager


class TradingMode(Enum):
    """Trading execution modes."""
    DISABLED = "disabled"
    PAPER_ONLY = "paper_only"
    LIVE_TRADING = "live_trading"
    SEMI_AUTO = "semi_auto"  # Requires confirmation for each trade


class ExecutionDecision(Enum):
    """Execution decision outcomes."""
    EXECUTE = "execute"
    SKIP = "skip"
    MONITOR = "monitor"
    REJECT = "reject"


class TradingExecutor:
    """
    Enhanced trading executor with automated execution capabilities.
    
    Orchestrates the complete trading workflow:
    1. Opportunity assessment and risk analysis
    2. Position sizing and portfolio constraints
    3. Trade execution and monitoring
    4. Position management and exit strategies
    """

    def __init__(
        self,
        risk_manager: RiskManager,
        position_manager: PositionManager,
        execution_engine: ExecutionEngine,
        trading_mode: TradingMode = TradingMode.PAPER_ONLY
    ) -> None:
        """
        Initialize the trading executor.
        
        Args:
            risk_manager: Risk management system
            position_manager: Position tracking system
            execution_engine: Order execution engine
            trading_mode: Execution mode (paper/live/disabled)
        """
        self.logger = logger_manager.get_logger("TradingExecutor")
        self.risk_manager = risk_manager
        self.position_manager = position_manager
        self.execution_engine = execution_engine
        self.trading_mode = trading_mode
        
        # Execution tracking
        self.opportunities_assessed = 0
        self.trades_executed = 0
        self.successful_trades = 0
        self.total_pnl = Decimal('0')
        self.execution_decisions: Dict[str, int] = {
            'execute': 0,
            'skip': 0,
            'monitor': 0,
            'reject': 0
        }
        
        # Configuration
        self.auto_execution_enabled = False
        self.max_concurrent_positions = 10
        self.confirmation_required = trading_mode == TradingMode.SEMI_AUTO
        
        # Monitoring and alerts
        self.position_monitoring_active = False
        self.alert_callbacks: List[callable] = []
        
        self.logger.info(f"TradingExecutor initialized in {trading_mode.value} mode")

    async def initialize(self) -> None:
        """Initialize the trading executor and all subsystems."""
        try:
            self.logger.info("Initializing trading executor...")
            
            # Initialize subsystems
            await self.execution_engine.initialize()
            await self.position_manager.initialize()
            
            # Start position monitoring
            if not self.position_monitoring_active:
                asyncio.create_task(self._monitor_positions())
                self.position_monitoring_active = True
            
            # Enable auto-execution if in live trading mode
            if self.trading_mode == TradingMode.LIVE_TRADING:
                self.auto_execution_enabled = True
                self.logger.warning("⚠️ AUTO-EXECUTION ENABLED - Live trading active")
            elif self.trading_mode == TradingMode.PAPER_ONLY:
                self.logger.info("📄 Paper trading mode - No real trades will be executed")
            
            self.logger.info("Trading executor initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize trading executor: {e}")
            raise

    async def evaluate_opportunity(self, opportunity: TradingOpportunity) -> ExecutionDecision:
        """
        Evaluate a trading opportunity and make execution decision.
        
        Args:
            opportunity: Trading opportunity to evaluate
            
        Returns:
            ExecutionDecision: Decision on whether to execute trade
        """
        try:
            self.opportunities_assessed += 1
            token_symbol = opportunity.token.symbol or "UNKNOWN"
            
            self.logger.debug(f"Evaluating opportunity: {token_symbol}")
            
            # Check if trading is enabled
            if self.trading_mode == TradingMode.DISABLED:
                return ExecutionDecision.SKIP
            
            # Assess risk and position sizing
            risk_assessment = self.risk_manager.assess_opportunity(opportunity)
            
            # Make execution decision based on risk assessment
            decision = self._make_execution_decision(opportunity, risk_assessment)
            
            # Track decision
            self.execution_decisions[decision.value] += 1
            
            # Execute if approved and auto-execution enabled
            if decision == ExecutionDecision.EXECUTE and self.auto_execution_enabled:
                await self._execute_trade(opportunity, risk_assessment)
            elif decision == ExecutionDecision.EXECUTE and self.confirmation_required:
                await self._request_trade_confirmation(opportunity, risk_assessment)
            
            return decision
            
        except Exception as e:
            self.logger.error(f"Error evaluating opportunity {token_symbol}: {e}")
            return ExecutionDecision.REJECT

    def _make_execution_decision(
        self, 
        opportunity: TradingOpportunity, 
        risk_assessment: Any  # Changed from PositionSizeResult to Any for flexibility
    ) -> ExecutionDecision:
        """
        Make execution decision based on risk assessment and portfolio state.
        
        Args:
            opportunity: Trading opportunity
            risk_assessment: Risk assessment result
            
        Returns:
            ExecutionDecision: Decision outcome
        """
        try:
            # Handle different types of risk assessments
            if hasattr(risk_assessment, 'risk_assessment'):
                assessment_value = risk_assessment.risk_assessment
            else:
                assessment_value = getattr(risk_assessment, 'risk_assessment', 'CONDITIONAL')
            
            # Convert string to enum if needed
            if isinstance(assessment_value, str):
                if assessment_value == "REJECTED":
                    return ExecutionDecision.REJECT
                elif assessment_value == "APPROVED":
                    return ExecutionDecision.EXECUTE
                elif assessment_value == "CONDITIONAL":
                    return ExecutionDecision.MONITOR
                else:
                    return ExecutionDecision.SKIP
            
            # Get risk score safely
            risk_score = getattr(risk_assessment, 'risk_score', 0.5)
            
            # Get approved amount safely
            approved_amount = getattr(risk_assessment, 'approved_amount', 0)
            if hasattr(approved_amount, '__float__'):
                approved_amount = float(approved_amount)
            
            # Check if we have sufficient approved amount
            if approved_amount <= 0:
                self.logger.debug(f"No approved amount for trade: {approved_amount}")
                return ExecutionDecision.SKIP
            
            # Simple decision logic based on risk score
            if risk_score < 0.3:  # Low risk
                return ExecutionDecision.EXECUTE
            elif risk_score < 0.6:  # Medium risk
                return ExecutionDecision.MONITOR
            else:  # High risk
                return ExecutionDecision.REJECT
                
        except Exception as e:
            self.logger.error(f"Error making execution decision: {e}")
            return ExecutionDecision.REJECT

    async def _execute_trade(
        self, 
        opportunity: TradingOpportunity, 
        risk_assessment: PositionSizeResult
    ) -> Optional[Position]:
        """
        Execute a trade with comprehensive logging and error handling.
        
        Args:
            opportunity: Trading opportunity to execute
            risk_assessment: Risk assessment with position sizing
            
        Returns:
            Position: Created position if successful, None otherwise
        """
        try:
            token_symbol = opportunity.token.symbol or "UNKNOWN"
            self.logger.info(f"🔥 EXECUTING TRADE: {token_symbol}")
            self.logger.info(f"   Amount: {risk_assessment.approved_amount}")
            self.logger.info(f"   Risk Score: {risk_assessment.risk_score:.2f}")
            self.logger.info(f"   Max Loss: ${risk_assessment.max_loss_usd:.2f}")
            
            # Paper trading simulation
            if self.trading_mode == TradingMode.PAPER_ONLY:
                position = await self._simulate_trade(opportunity, risk_assessment)
                if position:
                    self.trades_executed += 1
                    self.logger.info(f"📄 Paper trade executed: {token_symbol} - Position: {position.id}")
                return position
            
            # Live trading execution
            if self.trading_mode == TradingMode.LIVE_TRADING:
                position = await self.execution_engine.execute_buy_order(opportunity, risk_assessment)
                if position:
                    self.trades_executed += 1
                    self.successful_trades += 1
                    self.logger.info(f"💰 Live trade executed: {token_symbol} - Position: {position.id}")
                    
                    # Set up automated exit strategies
                    await self._setup_exit_strategies(position, risk_assessment)
                    
                    # Send alerts
                    await self._send_trade_alert(opportunity, position, "TRADE_EXECUTED")
                    
                return position
            
            return None
            
        except Exception as e:
            self.logger.error(f"Trade execution failed for {opportunity.token.symbol}: {e}")
            await self._send_trade_alert(opportunity, None, "TRADE_FAILED", str(e))
            return None

    async def _simulate_trade(
        self, 
        opportunity: TradingOpportunity, 
        risk_assessment: PositionSizeResult
    ) -> Optional[Position]:
        """
        Simulate a trade for paper trading mode.
        
        Args:
            opportunity: Trading opportunity
            risk_assessment: Risk assessment result
            
        Returns:
            Position: Simulated position
        """
        try:
            # Create simulated position
            position = await self.position_manager.open_position(
                opportunity=opportunity,
                entry_price=Decimal('1.0'),  # Normalized price for simulation
                entry_amount=risk_assessment.approved_amount,
                entry_tx_hash="PAPER_TRADE"
            )
            
            if position:
                # Set up paper trading parameters
                position.metadata['paper_trade'] = True
                position.metadata['simulated_price'] = float(opportunity.token.price or 0)
                
                # Set stop loss and take profit based on risk assessment
                if risk_assessment.recommended_stop_loss:
                    position.stop_loss_price = position.entry_price * (1 - Decimal(str(risk_assessment.recommended_stop_loss)))
                
                if risk_assessment.recommended_take_profit:
                    position.take_profit_price = position.entry_price * (1 + Decimal(str(risk_assessment.recommended_take_profit)))
            
            return position
            
        except Exception as e:
            self.logger.error(f"Paper trade simulation failed: {e}")
            return None

    async def _setup_exit_strategies(
        self, 
        position: Position, 
        risk_assessment: PositionSizeResult
    ) -> None:
        """
        Set up automated exit strategies for a position.
        
        Args:
            position: Position to set up exit strategies for
            risk_assessment: Risk assessment with recommended exit levels
        """
        try:
            # Set stop loss
            if risk_assessment.recommended_stop_loss:
                stop_loss_price = position.entry_price * (1 - Decimal(str(risk_assessment.recommended_stop_loss)))
                position.stop_loss_price = stop_loss_price
                self.logger.info(f"Stop loss set at {stop_loss_price} for {position.token_symbol}")
            
            # Set take profit
            if risk_assessment.recommended_take_profit:
                take_profit_price = position.entry_price * (1 + Decimal(str(risk_assessment.recommended_take_profit)))
                position.take_profit_price = take_profit_price
                self.logger.info(f"Take profit set at {take_profit_price} for {position.token_symbol}")
            
            # Set maximum hold time
            position.max_hold_time = timedelta(hours=24)  # Default 24 hour max hold
            
            # Update position in manager
            await self.position_manager.update_position(position)
            
        except Exception as e:
            self.logger.error(f"Failed to set up exit strategies for {position.token_symbol}: {e}")

    async def _monitor_positions(self) -> None:
        """Continuously monitor active positions and execute exit strategies."""
        self.logger.info("Starting position monitoring...")
        
        while self.position_monitoring_active:
            try:
                active_positions = self.position_manager.get_active_positions()
                
                for position in active_positions:
                    await self._check_position_exits(position)
                
                # Sleep between monitoring cycles
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except asyncio.CancelledError:
                self.logger.info("Position monitoring cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in position monitoring: {e}")
                await asyncio.sleep(30)

    async def _check_position_exits(self, position: Position) -> None:
        """
        Check if a position should be exited based on stop loss, take profit, or time limits.
        
        Args:
            position: Position to check for exit conditions
        """
        try:
            # Update current price (this would typically fetch from DEX)
            # For now, simulate price movement
            await self._update_position_price(position)
            
            # Check stop loss
            if position.stop_loss_price and position.current_price <= position.stop_loss_price:
                self.logger.warning(f"Stop loss triggered for {position.token_symbol}")
                await self._execute_exit(position, "STOP_LOSS")
                return
            
            # Check take profit
            if position.take_profit_price and position.current_price >= position.take_profit_price:
                self.logger.info(f"Take profit triggered for {position.token_symbol}")
                await self._execute_exit(position, "TAKE_PROFIT")
                return
            
            # Check time limit
            if position.max_hold_time:
                hold_time = datetime.now() - position.entry_time
                if hold_time >= position.max_hold_time:
                    self.logger.info(f"Max hold time reached for {position.token_symbol}")
                    await self._execute_exit(position, "TIME_LIMIT")
                    return
            
        except Exception as e:
            self.logger.error(f"Error checking exit conditions for {position.token_symbol}: {e}")

    async def _update_position_price(self, position: Position) -> None:
        """
        Update position current price.
        
        Args:
            position: Position to update
        """
        try:
            # This would typically fetch current price from DEX
            # For paper trading, simulate price movement
            if position.metadata.get('paper_trade', False):
                # Simulate random price movement
                import random
                price_change = random.uniform(-0.1, 0.1)  # ±10% movement
                new_price = position.current_price * (1 + Decimal(str(price_change)))
                position.update_current_price(new_price)
            else:
                # TODO: Implement real price fetching from DEX
                pass
                
        except Exception as e:
            self.logger.error(f"Error updating price for {position.token_symbol}: {e}")

    async def _execute_exit(self, position: Position, reason: str) -> None:
        """
        Execute position exit.
        
        Args:
            position: Position to exit
            reason: Reason for exit
        """
        try:
            self.logger.info(f"🚪 EXITING POSITION: {position.token_symbol} - Reason: {reason}")
            
            if self.trading_mode == TradingMode.PAPER_ONLY:
                # Simulate exit
                await self.position_manager.close_position(position.id, reason)
                self.logger.info(f"📄 Paper position closed: {position.token_symbol}")
            else:
                # Execute real exit
                success = await self.execution_engine.execute_sell_order(position)
                if success:
                    await self.position_manager.close_position(position.id, reason)
                    self.logger.info(f"💰 Position closed: {position.token_symbol}")
            
            # Send exit alert
            await self._send_trade_alert(None, position, f"POSITION_CLOSED_{reason}")
            
        except Exception as e:
            self.logger.error(f"Error executing exit for {position.token_symbol}: {e}")

    async def _request_trade_confirmation(
        self, 
        opportunity: TradingOpportunity, 
        risk_assessment: PositionSizeResult
    ) -> None:
        """
        Request manual confirmation for trade execution.
        
        Args:
            opportunity: Trading opportunity
            risk_assessment: Risk assessment result
        """
        try:
            token_symbol = opportunity.token.symbol or "UNKNOWN"
            self.logger.info(f"🤔 TRADE CONFIRMATION REQUIRED: {token_symbol}")
            self.logger.info(f"   Amount: {risk_assessment.approved_amount}")
            self.logger.info(f"   Risk Score: {risk_assessment.risk_score:.2f}")
            self.logger.info(f"   Reasons: {' | '.join(risk_assessment.reasons)}")
            
            # In a real implementation, this would integrate with dashboard or messaging
            # For now, just log the request
            
        except Exception as e:
            self.logger.error(f"Error requesting trade confirmation: {e}")

    async def _send_trade_alert(
        self, 
        opportunity: Optional[TradingOpportunity], 
        position: Optional[Position], 
        alert_type: str,
        error_message: Optional[str] = None
    ) -> None:
        """
        Send trade alert to registered callbacks.
        
        Args:
            opportunity: Trading opportunity (if applicable)
            position: Position (if applicable)
            alert_type: Type of alert
            error_message: Error message (if applicable)
        """
        try:
            alert_data = {
                'type': alert_type,
                'timestamp': datetime.now().isoformat(),
                'opportunity': opportunity.to_dict() if opportunity else None,
                'position': position.to_dict() if position else None,
                'error_message': error_message
            }
            
            # Send to all registered callbacks
            for callback in self.alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(alert_data)
                    else:
                        callback(alert_data)
                except Exception as e:
                    self.logger.error(f"Error in alert callback: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error sending trade alert: {e}")

    def add_alert_callback(self, callback: callable) -> None:
        """
        Add alert callback function.
        
        Args:
            callback: Function to call for trade alerts
        """
        self.alert_callbacks.append(callback)

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get portfolio performance summary.
        
        Returns:
            Dictionary containing portfolio metrics
        """
        try:
            active_positions = self.position_manager.get_active_positions()
            total_positions = len(active_positions)
            total_exposure = self.position_manager.get_total_exposure_usd()
            daily_pnl = self.position_manager.get_daily_pnl()
            
            success_rate = 0.0
            if self.trades_executed > 0:
                success_rate = (self.successful_trades / self.trades_executed) * 100
            
            return {
                'trading_mode': self.trading_mode.value,
                'opportunities_assessed': self.opportunities_assessed,
                'total_trades': self.trades_executed,
                'successful_trades': self.successful_trades,
                'success_rate': success_rate,
                'total_positions': total_positions,
                'total_exposure_usd': total_exposure,
                'daily_pnl': daily_pnl,
                'execution_decisions': self.execution_decisions.copy()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting portfolio summary: {e}")
            return {}

    async def manual_trade(
        self, 
        token_address: str, 
        amount: Decimal, 
        chain: str
    ) -> Optional[Position]:
        """
        Execute a manual trade from dashboard or API.
        
        Args:
            token_address: Token contract address
            amount: Amount to trade
            chain: Blockchain network
            
        Returns:
            Position: Created position if successful
        """
        try:
            self.logger.info(f"Manual trade requested: {token_address} on {chain}")
            
            # Create a simplified opportunity for manual trading
            # This would typically involve fetching token info
            from models.token import TokenInfo, LiquidityInfo
            
            token_info = TokenInfo(
                address=token_address,
                symbol="MANUAL",
                name="Manual Trade",
                decimals=18
            )
            
            liquidity_info = LiquidityInfo(
                liquidity_usd=10000,  # Assume sufficient liquidity
                dex_name="Manual",
                pair_address=""
            )
            
            opportunity = TradingOpportunity(
                token=token_info,
                liquidity=liquidity_info,
                timestamp=datetime.now(),
                chain=chain,
                metadata={'manual_trade': True}
            )
            
            # Create manual risk assessment
            risk_assessment = PositionSizeResult(
                approved_amount=amount,
                risk_assessment=RiskAssessment.APPROVED,
                risk_score=0.5,
                reasons=["Manual trade - user approved"],
                max_loss_usd=float(amount) * 0.2,  # 20% stop loss
                recommended_stop_loss=0.2,
                recommended_take_profit=0.3
            )
            
            # Execute the trade
            return await self._execute_trade(opportunity, risk_assessment)
            
        except Exception as e:
            self.logger.error(f"Manual trade execution failed: {e}")
            return None

    def set_trading_mode(self, mode: TradingMode) -> None:
        """
        Change trading mode.
        
        Args:
            mode: New trading mode
        """
        old_mode = self.trading_mode
        self.trading_mode = mode
        
        if mode == TradingMode.LIVE_TRADING:
            self.auto_execution_enabled = True
            self.confirmation_required = False
            self.logger.warning(f"⚠️ Trading mode changed: {old_mode.value} -> {mode.value}")
        elif mode == TradingMode.SEMI_AUTO:
            self.auto_execution_enabled = False
            self.confirmation_required = True
            self.logger.info(f"Trading mode changed: {old_mode.value} -> {mode.value}")
        else:
            self.auto_execution_enabled = False
            self.confirmation_required = False
            self.logger.info(f"Trading mode changed: {old_mode.value} -> {mode.value}")

    async def cleanup(self) -> None:
        """Cleanup trading executor and stop all monitoring."""
        try:
            self.logger.info("Cleaning up trading executor...")
            
            # Stop position monitoring
            self.position_monitoring_active = False
            
            # Close all active positions if in live trading mode
            if self.trading_mode == TradingMode.LIVE_TRADING:
                active_positions = self.position_manager.get_active_positions()
                for position in active_positions:
                    await self._execute_exit(position, "SHUTDOWN")
            
            # Cleanup subsystems
            await self.execution_engine.cleanup()
            await self.position_manager.cleanup()
            
            self.logger.info("Trading executor cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during trading executor cleanup: {e}")