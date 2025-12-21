"""
Security Guardrails and Circuit Breaker Pattern
Implements fail-safe mechanisms to prevent unauthorized or excessive transactions.
"""

from typing import Optional, Tuple
from datetime import datetime
from src.utils.models import ISO20022Message, DecisionResult
from src.utils.secrets_manager import SecretsManager


class CircuitBreaker:
    """
    Circuit Breaker pattern for transaction safety.
    Prevents autonomous agent from exceeding hard-coded limits.
    """
    
    def __init__(self):
        self.max_allowable_variance = SecretsManager.get_max_allowable_variance()
        self.max_liquidity_percentage = SecretsManager.get_max_liquidity_percentage()
        self.total_liquidity_pool = 0.0  # Will be set from initial balance
    
    def set_total_liquidity_pool(self, total_liquidity: float):
        """Set the total liquidity pool for percentage calculations."""
        self.total_liquidity_pool = total_liquidity
    
    def check_transaction(
        self, 
        message: ISO20022Message, 
        current_balance: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a transaction should be blocked by circuit breaker.
        
        Args:
            message: The ISO 20022 message to check
            current_balance: Current available balance
            
        Returns:
            Tuple of (is_allowed, reason_if_blocked)
        """
        # Check absolute amount limit
        if message.amount > self.max_allowable_variance:
            return False, f"Transaction amount ${message.amount:,.2f} exceeds maximum allowable variance ${self.max_allowable_variance:,.2f}"
        
        # Check percentage of total liquidity
        if self.total_liquidity_pool > 0:
            percentage = message.amount / self.total_liquidity_pool
            if percentage > self.max_liquidity_percentage:
                return False, f"Transaction represents {percentage*100:.2f}% of total liquidity, exceeds {self.max_liquidity_percentage*100:.0f}% limit"
        
        # Check if transaction would cause negative balance
        if message.amount > current_balance:
            # This is allowed if it's urgent/sovereign (will trigger repo)
            if message.priority == "URGENT" or message.is_sovereign:
                return True, None  # Allow urgent/sovereign even if exceeds balance
            else:
                return False, f"Insufficient balance. Current: ${current_balance:,.2f}, Required: ${message.amount:,.2f}"
        
        return True, None
    
    def should_trigger_human_override(
        self,
        message: ISO20022Message,
        current_balance: float
    ) -> bool:
        """
        Determine if transaction requires human override.
        
        Args:
            message: The ISO 20022 message
            current_balance: Current available balance
            
        Returns:
            True if human override is required
        """
        # Trigger override for very large transactions
        if message.amount > self.max_allowable_variance * 0.8:  # 80% of max
            return True
        
        # Trigger override if transaction exceeds 40% of total liquidity
        if self.total_liquidity_pool > 0:
            percentage = message.amount / self.total_liquidity_pool
            if percentage > 0.4:  # 40% threshold
                return True
        
        return False


class AuditLogger:
    """Centralized audit logging for compliance."""
    
    @staticmethod
    def log_decision(decision: DecisionResult) -> dict:
        """
        Create an audit artifact for a decision.
        
        Args:
            decision: The decision result to log
            
        Returns:
            Audit artifact as dictionary
        """
        artifact = {
            "input_message_id": decision.message_id,
            "decision": decision.decision,
            "reasoning_steps": decision.reasoning_steps,
            "timestamp": decision.timestamp.isoformat(),
            "liquidity_before": decision.liquidity_before,
            "liquidity_after": decision.liquidity_after,
            "opportunity_cost_saved": decision.opportunity_cost_saved,
            "delay_penalty": decision.delay_penalty,
            "risk_score": decision.risk_score,
            "audit_version": "1.0",
            "system": "Project-Lique-Flow"
        }
        
        return artifact
