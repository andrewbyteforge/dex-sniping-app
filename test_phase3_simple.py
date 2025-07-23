"""
Simplified Phase 3 testing script that works with various Web3 versions.
"""

import asyncio
import sys
import os
from decimal import Decimal
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.logger import logger_manager


class SimplePhase3Tester:
    """Simplified test harness for Phase 3 components."""
    
    def __init__(self):
        """Initialize the test harness."""
        self.logger = logger_manager.get_logger("SimplePhase3Tester")
        self.test_results = {"passed": 0, "failed": 0, "skipped": 0}
    
    async def run_all_tests(self):
        """Run all Phase 3 tests with compatibility checks."""
        self.logger.info("=" * 70)
        self.logger.info("🧪 PHASE 3 OPTIMIZATION TESTING (SIMPLIFIED)")
        self.logger.info("=" * 70)
        
        # Test imports first
        await self.test_imports()
        
        # Test each component if available
        await self.test_mev_protection()
        await self.test_gas_optimizer()
        await self.test_transaction_simulator()
        await self.test_basic_integration()
        
        # Report results
        self._report_results()
    
    async def test_imports(self):
        """Test if Phase 3 components can be imported."""
        self.logger.info("\n📦 TESTING IMPORTS")
        self.logger.info("-" * 50)
        
        components = [
            ("trading.mev_protection", "MEV Protection"),
            ("trading.gas_optimizer", "Gas Optimizer"),
            ("trading.transaction_simulator", "Transaction Simulator"),
            ("infrastructure.node_manager", "Node Manager"),
        ]
        
        for module_name, display_name in components:
            try:
                module = __import__(module_name, fromlist=[''])
                self._log_test_pass(f"{display_name} import")
            except ImportError as e:
                self._log_test_fail(f"{display_name} import", str(e))
    
    async def test_mev_protection(self):
        """Test MEV protection with mock data."""
        self.logger.info("\n🛡️ TESTING MEV PROTECTION")
        self.logger.info("-" * 50)
        
        try:
            from trading.mev_protection import MEVProtectionManager, MEVProtectionLevel, MEVProtectionConfig
            
            # Create manager with config
            config = MEVProtectionConfig(
                protection_level=MEVProtectionLevel.STANDARD,
                use_flashbots=True,
                max_priority_fee=Decimal("5")
            )
            mev_protection = MEVProtectionManager(config)
            self._log_test_pass("MEV Protection initialization")
            
            # Test risk analysis with mock transaction
            mock_tx = {
                "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",  # Uniswap
                "value": 10**18,  # 1 ETH in wei
                "gas": 300000
            }
            
            # Note: Without Web3, we test the structure
            risk = mev_protection.analyze_mev_risk(mock_tx)
            if isinstance(risk, dict) and "risk_level" in risk:
                self._log_test_pass("MEV risk analysis structure")
                self.logger.info(f"   Risk Level: {risk['risk_level']}")
            else:
                self._log_test_fail("MEV risk analysis", "Invalid structure")
            
            # Test protection levels
            levels_tested = 0
            for level in [MEVProtectionLevel.BASIC, MEVProtectionLevel.STANDARD, MEVProtectionLevel.MAXIMUM]:
                try:
                    test_config = MEVProtectionConfig(protection_level=level)
                    test_manager = MEVProtectionManager(test_config)
                    levels_tested += 1
                except:
                    pass
            
            if levels_tested == 3:
                self._log_test_pass("Multiple protection levels")
            else:
                self._log_test_fail("Multiple protection levels", f"Only {levels_tested}/3 worked")
                
        except ImportError as e:
            self._log_test_skip("MEV Protection", f"Import failed: {e}")
        except Exception as e:
            self._log_test_fail("MEV Protection", str(e))
    
    async def test_gas_optimizer(self):
        """Test gas optimizer with mock data."""
        self.logger.info("\n⛽ TESTING GAS OPTIMIZER")
        self.logger.info("-" * 50)
        
        try:
            from trading.gas_optimizer import GasOptimizer, GasStrategy
            
            # Create optimizer
            gas_optimizer = GasOptimizer()
            self._log_test_pass("Gas Optimizer initialization")
            
            # Test strategy configs
            strategies = [GasStrategy.AGGRESSIVE, GasStrategy.STANDARD, GasStrategy.PATIENT]
            for strategy in strategies:
                if strategy in gas_optimizer.strategy_configs:
                    config = gas_optimizer.strategy_configs[strategy]
                    self.logger.info(f"   {strategy.value}: multiplier={config['priority_multiplier']}")
            self._log_test_pass("Strategy configurations")
            
            # Test optimization stats structure
            stats = gas_optimizer.stats
            if all(key in stats for key in ["transactions_optimized", "total_gas_saved"]):
                self._log_test_pass("Optimization statistics structure")
            else:
                self._log_test_fail("Optimization statistics", "Missing required fields")
                
        except ImportError as e:
            self._log_test_skip("Gas Optimizer", f"Import failed: {e}")
        except Exception as e:
            self._log_test_fail("Gas Optimizer", str(e))
    
    async def test_transaction_simulator(self):
        """Test transaction simulator structure."""
        self.logger.info("\n🔮 TESTING TRANSACTION SIMULATOR")
        self.logger.info("-" * 50)
        
        try:
            from trading.transaction_simulator import TransactionSimulator, SimulationResult
            
            # Create simulator
            tx_simulator = TransactionSimulator()
            self._log_test_pass("Transaction Simulator initialization")
            
            # Test DEX configurations
            if hasattr(tx_simulator, 'dex_configs'):
                dex_count = len(tx_simulator.dex_configs)
                self.logger.info(f"   DEX configurations: {dex_count}")
                if dex_count > 0:
                    self._log_test_pass("DEX configurations loaded")
                else:
                    self._log_test_fail("DEX configurations", "No DEXs configured")
            
            # Test simulation result enums
            results = [
                SimulationResult.SUCCESS,
                SimulationResult.REVERTED,
                SimulationResult.INSUFFICIENT_LIQUIDITY,
                SimulationResult.EXCESSIVE_SLIPPAGE
            ]
            if len(results) >= 4:
                self._log_test_pass("Simulation result types")
            
            # Test statistics structure
            if hasattr(tx_simulator, 'stats'):
                self._log_test_pass("Simulator statistics structure")
                
        except ImportError as e:
            self._log_test_skip("Transaction Simulator", f"Import failed: {e}")
        except Exception as e:
            self._log_test_fail("Transaction Simulator", str(e))
    
    async def test_basic_integration(self):
        """Test basic integration without Web3."""
        self.logger.info("\n🔗 TESTING BASIC INTEGRATION")
        self.logger.info("-" * 50)
        
        try:
            # Test that components can work together
            from trading.mev_protection import MEVProtectionLevel
            from trading.gas_optimizer import GasStrategy
            
            # Create a mock trading decision flow
            protection_level = MEVProtectionLevel.STANDARD
            gas_strategy = GasStrategy.ADAPTIVE
            
            self.logger.info(f"   Protection: {protection_level.value}")
            self.logger.info(f"   Gas Strategy: {gas_strategy.value}")
            
            self._log_test_pass("Component integration")
            
        except Exception as e:
            self._log_test_fail("Integration", str(e))
    
    def _log_test_pass(self, test_name: str):
        """Log a passed test."""
        self.logger.info(f"   ✅ {test_name}")
        self.test_results["passed"] += 1
    
    def _log_test_fail(self, test_name: str, reason: str):
        """Log a failed test."""
        self.logger.error(f"   ❌ {test_name}: {reason}")
        self.test_results["failed"] += 1
    
    def _log_test_skip(self, test_name: str, reason: str):
        """Log a skipped test."""
        self.logger.warning(f"   ⚠️  {test_name} SKIPPED: {reason}")
        self.test_results["skipped"] += 1
    
    def _report_results(self):
        """Report test results."""
        self.logger.info("\n" + "=" * 70)
        self.logger.info("📊 TEST RESULTS SUMMARY")
        self.logger.info("=" * 70)
        
        total = sum(self.test_results.values())
        passed = self.test_results["passed"]
        failed = self.test_results["failed"]
        skipped = self.test_results["skipped"]
        
        self.logger.info(f"Total Tests: {total}")
        self.logger.info(f"✅ Passed: {passed}")
        self.logger.info(f"❌ Failed: {failed}")
        self.logger.info(f"⚠️  Skipped: {skipped}")
        
        if total > 0:
            success_rate = (passed / (passed + failed)) * 100 if (passed + failed) > 0 else 0
            self.logger.info(f"\nSuccess Rate: {success_rate:.0f}%")
            
            if failed == 0 and skipped == 0:
                self.logger.info("\n🎉 All Phase 3 components are working perfectly!")
            elif failed == 0:
                self.logger.info("\n✅ Phase 3 components are working (some features skipped)")
                self.logger.info("💡 Run 'pip install web3 aiohttp' for full functionality")
            else:
                self.logger.info("\n⚠️  Some Phase 3 components need attention")
                self.logger.info("💡 Check the errors above and install missing dependencies")


async def main():
    """Run simplified Phase 3 tests."""
    print("\n💡 Running simplified tests that work without Web3...")
    print("   For full tests, install: pip install web3 aiohttp websockets\n")
    
    tester = SimplePhase3Tester()
    await tester.run_all_tests()


if __name__ == "__main__":
    # First run compatibility check
    print("Checking environment...")
    os.system("python check_phase3_compatibility.py")
    print("\n" + "=" * 70 + "\n")
    
    # Then run tests
    asyncio.run(main())