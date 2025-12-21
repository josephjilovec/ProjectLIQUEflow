"""
Pydantic Models for ISO 20022 Messages and System State
Ensures strict type safety and validation for all banking data structures.
"""

from datetime import datetime
from typing import List, Optional, Dict, Literal
from pydantic import BaseModel, Field, validator
from enum import Enum


class PriorityTier(str, Enum):
    """Payment priority tiers based on ISO 20022 standards."""
    URGENT = "URGENT"  # Sovereign debt, critical infrastructure
    HIGH = "HIGH"  # Interbank settlements
    NORMAL = "NORMAL"  # Retail, standard transfers
    LOW = "LOW"  # Non-critical, can be queued


class PaymentType(str, Enum):
    """Types of ISO 20022 payment messages."""
    PACS_008 = "pacs.008"  # Customer Credit Transfer
    PACS_009 = "pacs.009"  # Financial Institution Credit Transfer
    CAMT_052 = "camt.052"  # Bank to Customer Account Report (Intraday)
    CAMT_053 = "camt.053"  # Bank to Customer Statement


class ISO20022Message(BaseModel):
    """Base model for ISO 20022 messages with strict validation."""
    
    msg_id: str = Field(..., description="Unique message identification")
    msg_type: PaymentType = Field(..., description="Type of ISO 20022 message")
    cre_dt_tm: datetime = Field(..., description="Creation date and time")
    priority: PriorityTier = Field(default=PriorityTier.NORMAL, description="Payment priority tier")
    amount: float = Field(..., gt=0, description="Transaction amount in USD")
    currency: str = Field(default="USD", description="Currency code (ISO 4217)")
    end_to_end_id: str = Field(..., description="End-to-end identification")
    debtor_name: Optional[str] = Field(None, description="Debtor/Originator name")
    creditor_name: Optional[str] = Field(None, description="Creditor/Beneficiary name")
    is_sovereign: bool = Field(default=False, description="Whether this is a sovereign payment")
    raw_xml: Optional[str] = Field(None, description="Original XML representation")
    
    @validator('amount')
    def validate_amount(cls, v):
        """Ensure amount is positive and reasonable."""
        if v <= 0:
            raise ValueError("Amount must be positive")
        if v > 1e12:  # $1 trillion cap
            raise ValueError("Amount exceeds maximum allowable limit")
        return v
    
    @validator('currency')
    def validate_currency(cls, v):
        """Validate currency code."""
        if len(v) != 3:
            raise ValueError("Currency code must be 3 characters (ISO 4217)")
        return v.upper()
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LiquiditySnapshot(BaseModel):
    """Represents the current state of bank liquidity."""
    
    current_balance: float = Field(..., description="Current HQLA (High Quality Liquid Assets) in USD")
    pending_queue: List[ISO20022Message] = Field(default_factory=list, description="Payments waiting for settlement")
    incoming_projections: Dict[str, float] = Field(
        default_factory=dict, 
        description="Expected inflows by time window (ISO format keys)"
    )
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Calculated risk score (0=low, 1=high)")
    decision_log: List[str] = Field(default_factory=list, description="Chain of thought decision log")
    total_settled_today: float = Field(default=0.0, description="Total amount settled today")
    total_delayed_today: float = Field(default=0.0, description="Total amount delayed today")
    last_update: datetime = Field(default_factory=datetime.now, description="Last state update timestamp")
    
    @validator('current_balance')
    def validate_balance(cls, v):
        """Ensure balance is non-negative."""
        if v < 0:
            raise ValueError("Balance cannot be negative")
        return v


class DecisionResult(BaseModel):
    """Result of an agent decision with full audit trail."""
    
    message_id: str = Field(..., description="Input message ID")
    decision: Literal["SETTLE", "QUEUE", "REJECT", "REQUIRE_HUMAN_OVERRIDE"] = Field(..., description="Decision made")
    reasoning_steps: List[str] = Field(default_factory=list, description="Step-by-step reasoning")
    timestamp: datetime = Field(default_factory=datetime.now, description="Decision timestamp")
    liquidity_before: float = Field(..., description="Liquidity before decision")
    liquidity_after: Optional[float] = Field(None, description="Liquidity after decision (if settled)")
    opportunity_cost_saved: Optional[float] = Field(None, description="Interest saved by optimization (USD)")
    delay_penalty: Optional[float] = Field(None, description="Cost of delaying payment (USD)")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Risk score at decision time")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PerformanceMetrics(BaseModel):
    """Performance metrics for the liquidity optimization system."""
    
    liquidity_usage_peak: float = Field(default=0.0, description="Maximum peak of cash used")
    average_settlement_delay: float = Field(default=0.0, description="Average time payments spent in queue (seconds)")
    opportunity_cost_saved: float = Field(default=0.0, description="Total interest saved by keeping lower buffer (USD)")
    total_transactions_processed: int = Field(default=0, description="Total transactions processed")
    total_settled: int = Field(default=0, description="Total transactions settled")
    total_queued: int = Field(default=0, description="Total transactions queued")
    total_human_overrides: int = Field(default=0, description="Total human override triggers")
    average_processing_time: float = Field(default=0.0, description="Average processing time per transaction (seconds)")
    human_manual_time_saved: float = Field(default=0.0, description="Estimated time saved vs manual processing (seconds)")
