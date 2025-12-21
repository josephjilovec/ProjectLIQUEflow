"""
Simulation Scenarios for Stress Testing
Implements three key scenarios: Happy Path, Liquidity Shock, and End-of-Day Crunch.
"""

from datetime import datetime, timedelta
from typing import List, Generator
import random
from src.message_generator.iso20022_generator import ISO20022Generator
from src.utils.models import ISO20022Message, PriorityTier, LiquiditySnapshot, PerformanceMetrics


class ScenarioGenerator:
    """Generates realistic payment scenarios for testing."""
    
    def __init__(self, initial_balance: float = 1000000000.0):
        """Initialize scenario generator."""
        self.initial_balance = initial_balance
        self.generator = ISO20022Generator()
    
    def happy_path(self, duration_minutes: int = 60, transactions_per_minute: float = 2.0) -> Generator[ISO20022Message, None, None]:
        """
        Scenario A: The Happy Path
        Steady inflow and outflow. The bot settles everything instantly.
        
        Args:
            duration_minutes: Duration of scenario in minutes
            transactions_per_minute: Average transactions per minute
            
        Yields:
            ISO20022Message objects
        """
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        current_time = start_time
        
        transaction_count = 0
        
        while current_time < end_time:
            # Generate transactions at specified rate
            if random.random() < transactions_per_minute / 60.0:  # Probability per second
                # Mix of incoming and outgoing
                is_incoming = random.random() < 0.4  # 40% incoming
                
                if is_incoming:
                    # Incoming payments (positive for balance)
                    amount = random.uniform(100000, 5000000)  # $100K to $5M
                    priority = random.choice([PriorityTier.NORMAL, PriorityTier.HIGH])
                else:
                    # Outgoing payments
                    amount = random.uniform(50000, 2000000)  # $50K to $2M
                    priority = random.choice([PriorityTier.NORMAL, PriorityTier.HIGH])
                
                message = self.generator.generate_pacs008(
                    amount=amount,
                    priority=priority,
                    cre_dt_tm=current_time
                )
                
                transaction_count += 1
                yield message
            
            current_time += timedelta(seconds=1)
    
    def liquidity_shock(
        self, 
        shock_amount: float = 500000000.0,
        current_buffer: float = 100000000.0
    ) -> List[ISO20022Message]:
        """
        Scenario B: The Liquidity Shock
        A sudden $500M outgoing payment with 'URGENT' tag when buffer is only $100M.
        The bot must decide whether to queue other payments or trigger a repo.
        
        Args:
            shock_amount: Amount of the shock payment
            current_buffer: Current available buffer
            
        Returns:
            List of ISO20022Message objects
        """
        messages = []
        base_time = datetime.now()
        
        # First, generate some normal transactions
        for i in range(5):
            message = self.generator.generate_pacs008(
                amount=random.uniform(1000000, 10000000),
                priority=PriorityTier.NORMAL,
                cre_dt_tm=base_time + timedelta(minutes=i)
            )
            messages.append(message)
        
        # Then, the liquidity shock
        shock_message = self.generator.generate_pacs008(
            amount=shock_amount,
            priority=PriorityTier.URGENT,
            is_sovereign=True,
            debtor_name="US_TREASURY",
            creditor_name="FEDERAL_RESERVE",
            cre_dt_tm=base_time + timedelta(minutes=5)
        )
        messages.append(shock_message)
        
        # Follow-up transactions to test queuing
        for i in range(3):
            message = self.generator.generate_pacs008(
                amount=random.uniform(5000000, 50000000),
                priority=PriorityTier.NORMAL,
                cre_dt_tm=base_time + timedelta(minutes=6+i)
            )
            messages.append(message)
        
        return messages
    
    def end_of_day_crunch(
        self, 
        cutoff_time: datetime = None,
        volume_multiplier: float = 5.0
    ) -> Generator[ISO20022Message, None, None]:
        """
        Scenario C: The End-of-Day Crunch
        High volume of 'NORMAL' priority payments piling up as 4:30 PM settlement cutoff approaches.
        
        Args:
            cutoff_time: Settlement cutoff time (defaults to 4:30 PM today)
            volume_multiplier: Multiplier for transaction volume
            
        Yields:
            ISO20022Message objects
        """
        if cutoff_time is None:
            now = datetime.now()
            cutoff_time = now.replace(hour=16, minute=30, second=0, microsecond=0)
            if cutoff_time < now:
                cutoff_time += timedelta(days=1)
        
        # Start 2 hours before cutoff
        start_time = cutoff_time - timedelta(hours=2)
        current_time = start_time
        
        transaction_count = 0
        
        while current_time < cutoff_time:
            # Volume increases as cutoff approaches
            time_until_cutoff = (cutoff_time - current_time).total_seconds() / 3600  # hours
            volume_factor = 1.0 + (2.0 - time_until_cutoff) * volume_multiplier
            
            # Generate transactions with increasing frequency
            probability = min(volume_factor * 0.1, 0.9)  # Cap at 90%
            
            if random.random() < probability:
                # Mostly normal priority payments
                priority = PriorityTier.NORMAL if random.random() < 0.8 else PriorityTier.HIGH
                
                amount = random.uniform(10000, 1000000)  # Smaller amounts, high volume
                
                message = self.generator.generate_pacs008(
                    amount=amount,
                    priority=priority,
                    cre_dt_tm=current_time
                )
                
                transaction_count += 1
                yield message
            
            current_time += timedelta(seconds=random.randint(1, 10))
    
    def generate_incoming_projections(
        self, 
        hours_ahead: int = 2
    ) -> dict:
        """
        Generate realistic incoming fund projections.
        
        Args:
            hours_ahead: Number of hours to project ahead
            
        Returns:
            Dictionary mapping ISO datetime strings to projected amounts
        """
        projections = {}
        base_time = datetime.now()
        
        for i in range(hours_ahead * 4):  # Every 15 minutes
            projection_time = base_time + timedelta(minutes=15 * i)
            # Simulate settlement windows (higher volumes at certain times)
            hour = projection_time.hour
            
            if 9 <= hour <= 11 or 14 <= hour <= 16:  # Peak hours
                amount = random.uniform(5000000, 50000000)
            else:
                amount = random.uniform(1000000, 10000000)
            
            projections[projection_time.isoformat()] = amount
        
        return projections


class PerformanceTracker:
    """Tracks performance metrics during simulation."""
    
    def __init__(self):
        """Initialize performance tracker."""
        self.metrics = PerformanceMetrics()
        self.settlement_times = []
        self.queue_times = {}
        self.start_time = datetime.now()
    
    def record_settlement(
        self, 
        message: ISO20022Message, 
        decision_time: datetime,
        processing_time_seconds: float
    ):
        """Record a settlement event."""
        self.metrics.total_transactions_processed += 1
        self.metrics.total_settled += 1
        self.settlement_times.append(processing_time_seconds)
        if self.settlement_times:
            self.metrics.average_processing_time = sum(self.settlement_times) / len(self.settlement_times)
    
    def record_queue(
        self, 
        message: ISO20022Message,
        decision_time: datetime
    ):
        """Record a queued payment."""
        self.metrics.total_transactions_processed += 1
        self.metrics.total_queued += 1
        self.queue_times[message.msg_id] = decision_time
    
    def record_human_override(self):
        """Record a human override trigger."""
        self.metrics.total_human_overrides += 1
    
    def update_liquidity_peak(self, current_balance: float):
        """Update peak liquidity usage."""
        if current_balance > self.metrics.liquidity_usage_peak:
            self.metrics.liquidity_usage_peak = current_balance
    
    def calculate_final_metrics(
        self, 
        final_state: LiquiditySnapshot
    ) -> PerformanceMetrics:
        """Calculate final performance metrics."""
        # Calculate average settlement delay
        if self.queue_times:
            now = datetime.now()
            delays = [
                (now - queue_time).total_seconds() 
                for queue_time in self.queue_times.values()
            ]
            self.metrics.average_settlement_delay = sum(delays) / len(delays) if delays else 0.0
        
        # Estimate human manual time saved
        # Assume 15-20 minutes per complex transaction manually
        manual_time_per_transaction = 17.5 * 60  # 17.5 minutes in seconds
        total_manual_time = self.metrics.total_transactions_processed * manual_time_per_transaction
        total_agent_time = sum(self.settlement_times) if self.settlement_times else 0.0
        self.metrics.human_manual_time_saved = max(0, total_manual_time - total_agent_time)
        
        return self.metrics
