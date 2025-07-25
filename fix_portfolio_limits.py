#!/usr/bin/env python3
"""
Quick fix script to correct the PortfolioLimits parameter names in main_production_enhanced.py

File: fix_portfolio_limits.py
"""

import re

def fix_main_production_file():
    """Fix the parameter names in main_production_enhanced.py"""
    
    filename = "main_production_enhanced.py"
    
    try:
        # Read the current file
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Make the fixes
        print("🔧 Applying fixes to main_production_enhanced.py...")
        
        # Fix 1: Import statement
        content = content.replace(
            "from trading.risk_manager import RiskManager, PortfolioLimits, RiskAssessment",
            "from trading.risk_manager import EnhancedRiskManager, PortfolioLimits, RiskAssessment"
        )
        
        # Fix 2: Type annotation
        content = content.replace(
            "self.risk_manager: Optional[RiskManager] = None",
            "self.risk_manager: Optional[EnhancedRiskManager] = None"
        )
        
        # Fix 3: Constructor call
        content = content.replace(
            "self.risk_manager = RiskManager(portfolio_limits)",
            "self.risk_manager = EnhancedRiskManager(portfolio_limits)"
        )
        
        # Fix 4: PortfolioLimits parameter names
        portfolio_limits_pattern = r'portfolio_limits = PortfolioLimits\(\s*([^)]+)\s*\)'
        
        def fix_portfolio_params(match):
            params = match.group(1)
            
            # Fix parameter names
            params = params.replace("max_total_position_usd=", "max_total_exposure_usd=")
            params = params.replace("max_position_size_usd=", "max_single_position_usd=")
            params = params.replace("max_daily_losses_usd=", "max_daily_loss_usd=")
            
            return f"portfolio_limits = PortfolioLimits(\n                {params}\n            )"
        
        content = re.sub(portfolio_limits_pattern, fix_portfolio_params, content, flags=re.MULTILINE | re.DOTALL)
        
        # Write the fixed file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Fixed main_production_enhanced.py")
        print("   - Updated import to use EnhancedRiskManager")
        print("   - Fixed PortfolioLimits parameter names")
        print("   - Updated constructor calls")
        
        return True
        
    except FileNotFoundError:
        print(f"❌ File {filename} not found")
        return False
    except Exception as e:
        print(f"❌ Error fixing file: {e}")
        return False

def verify_fixes():
    """Verify that the fixes were applied correctly"""
    
    filename = "main_production_enhanced.py"
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print("\n🔍 Verifying fixes...")
        
        # Check if fixes are present
        checks = [
            ("EnhancedRiskManager import", "from trading.risk_manager import EnhancedRiskManager" in content),
            ("max_total_exposure_usd param", "max_total_exposure_usd=" in content),
            ("max_single_position_usd param", "max_single_position_usd=" in content),
            ("max_daily_loss_usd param", "max_daily_loss_usd=" in content),
            ("EnhancedRiskManager constructor", "EnhancedRiskManager(portfolio_limits)" in content),
        ]
        
        all_good = True
        for check_name, check_result in checks:
            status = "✅" if check_result else "❌"
            print(f"   {status} {check_name}")
            if not check_result:
                all_good = False
        
        if all_good:
            print("\n🎉 All fixes verified successfully!")
            print("You can now run: python main_production_enhanced.py --mev-protection=standard")
        else:
            print("\n⚠️ Some fixes may not have been applied correctly")
        
        return all_good
        
    except Exception as e:
        print(f"❌ Error verifying fixes: {e}")
        return False

if __name__ == "__main__":
    print("🔧 PortfolioLimits Parameter Fix Script")
    print("=" * 50)
    
    if fix_main_production_file():
        verify_fixes()
    else:
        print("❌ Failed to apply fixes")
        
        print("\n📝 Manual fix instructions:")
        print("1. Open main_production_enhanced.py")
        print("2. Change import: RiskManager → EnhancedRiskManager")
        print("3. Change parameter names in PortfolioLimits constructor:")
        print("   - max_total_position_usd → max_total_exposure_usd")
        print("   - max_position_size_usd → max_single_position_usd") 
        print("   - max_daily_losses_usd → max_daily_loss_usd")
        print("4. Change constructor: RiskManager() → EnhancedRiskManager()")