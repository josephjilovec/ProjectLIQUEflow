"""
Adversarial Stress Tester Agent (Chaos Monkey)
Purposefully attacks liquidity to test system resilience under extreme stress.
Implements Herstatt Risk scenarios and Bank Run simulations.
"""

from datetime import datetime, timedelta
from typing import List, Dict
import random
from src.message_generator.iso20022_generator import ISO20022Generator
from src.utils.models import ISO20022Message, PriorityTier


class AdversarialAgent:
    """
    Adversarial agent that generates stress scenarios:
    - Delays incoming payments
    - Triggers bank run scenarios
    - Creates systemic liquidity crunches
    """
    
    def __init__(self):
        """Initialize adversarial agent."""
        self.generator = ISO20022Generator()
        self.attack_mode = False
        self.attack_log: List[Dict] = []
    
    def trigger_systemic_stress(
        self,
        base_balance: float,
        stress_level: float = 1.0
    ) -> List[ISO20022Message]:
        """
        Generate systemic liquidity crunch scenario.
        400% increase in URGENT payments with 50% drop in projected inflows.
        
        Args:
            base_balance: Current balance
            stress_level: Multiplier for stress (1.0 = normal stress, 2.0 = extreme)
            
        Returns:
            List of ISO20022Message objects representing the stress scenario
        """
        self.attack_mode = True
        messages = []
        base_time = datetime.now()
        
        # Phase 1: Sudden surge of URGENT payments (400% increase)
        urgent_count = int(20 * stress_level)  # Normally 5, now 20+
        for i in range(urgent_count):
            # Large urgent payments
            amount = random.uniform(base_balance * 0.05, base_balance * 0.25) * stress_level
            message = self.generator.generate_pacs008(
                amount=amount,
                priority=PriorityTier.URGENT,
                is_sovereign=random.random() < 0.3,  # 30% are sovereign
                cre_dt_tm=base_time + timedelta(minutes=i * 2)
            )
            messages.append(message)
        
        # Phase 2: Bank Run scenario - everyone withdraws at once
        run_count = int(15 * stress_level)
        for i in range(run_count):
            # Smaller but numerous withdrawals
            amount = random.uniform(1000000, 10000000) * stress_level
            message = self.generator.generate_pacs008(
                amount=amount,
                priority=PriorityTier.HIGH,
                debtor_name="CUSTOMER_BANK_RUN",
                creditor_name="EXTERNAL_BANK",
                cre_dt_tm=base_time + timedelta(minutes=urgent_count * 2 + i)
            )
            messages.append(message)
        
        # Phase 3: Delayed incoming payments (simulating counterparty failures)
        # This is handled by reducing projected inflows in the scenario
        
        self.attack_log.append({
            "type": "SYSTEMIC_STRESS",
            "timestamp": datetime.now().isoformat(),
            "urgent_payments": urgent_count,
            "bank_run_withdrawals": run_count,
            "stress_level": stress_level
        })
        
        return messages
    
    def delay_incoming_payment(self, message: ISO20022Message, delay_minutes: int = 60) -> ISO20022Message:
        """
        Simulate delayed incoming payment (counterparty failure scenario).
        
        Args:
            message: Original incoming payment message
            delay_minutes: Minutes to delay
            
        Returns:
            Modified message with delayed timestamp
        """
        delayed_message = ISO20022Message(
            **message.dict(),
            cre_dt_tm=message.cre_dt_tm + timedelta(minutes=delay_minutes)
        )
        
        self.attack_log.append({
            "type": "DELAY_INCOMING",
            "message_id": message.msg_id,
            "delay_minutes": delay_minutes,
            "timestamp": datetime.now().isoformat()
        })
        
        return delayed_message
    
    def trigger_herstatt_risk_scenario(self, base_balance: float) -> List[ISO20022Message]:
        """
        Generate Herstatt Risk scenario where one party pays but counterparty fails.
        
        Args:
            base_balance: Current balance
            
        Returns:
            List of messages representing Herstatt Risk
        """
        messages = []
        base_time = datetime.now()
        
        # Large outgoing payment
        outgoing = self.generator.generate_pacs008(
            amount=base_balance * 0.4,
            priority=PriorityTier.URGENT,
            is_sovereign=True,
            debtor_name="OUR_BANK",
            creditor_name="COUNTERPARTY_BANK",
            cre_dt_tm=base_time
        )
        messages.append(outgoing)
        
        # Expected incoming payment that never arrives (simulated by not generating it)
        # This creates the Herstatt Risk: we paid out but didn't receive
        
        self.attack_log.append({
            "type": "HERSTATT_RISK",
            "timestamp": datetime.now().isoformat(),
            "outgoing_amount": base_balance * 0.4,
            "expected_incoming": "FAILED"
        })
        
        return messages
    
    def get_attack_summary(self) -> Dict:
        """Get summary of adversarial attacks."""
        return {
            "total_attacks": len(self.attack_log),
            "attack_types": [log["type"] for log in self.attack_log],
            "latest_attack": self.attack_log[-1] if self.attack_log else None
        }

