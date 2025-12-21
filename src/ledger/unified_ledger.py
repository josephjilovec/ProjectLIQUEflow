"""
Tokenized Unified Ledger Implementation (Project Agorá)
Simulates atomic settlement on a unified ledger where money and instructions coexist.
"""

from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from enum import Enum
import uuid


class SettlementStatus(str, Enum):
    """Status of an atomic settlement."""
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    REVERTED = "REVERTED"


class TokenizedDeposit(BaseModel):
    """Represents a tokenized deposit on the unified ledger."""
    
    token_id: str = Field(default_factory=lambda: f"TKN-{uuid.uuid4().hex[:16].upper()}")
    owner: str = Field(..., description="Owner of the deposit")
    amount: float = Field(..., gt=0, description="Tokenized amount in USD")
    currency: str = Field(default="USD", description="Currency code")
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = Field(default="ACTIVE", description="Token status")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AtomicSettlement(BaseModel):
    """Represents an atomic settlement transaction on the unified ledger."""
    
    settlement_id: str = Field(default_factory=lambda: f"SETTLE-{uuid.uuid4().hex[:16].upper()}")
    from_account: str = Field(..., description="Debtor account")
    to_account: str = Field(..., description="Creditor account")
    amount: float = Field(..., gt=0, description="Settlement amount")
    currency: str = Field(default="USD")
    status: SettlementStatus = Field(default=SettlementStatus.PENDING)
    timestamp: datetime = Field(default_factory=datetime.now)
    message_id: Optional[str] = Field(None, description="Associated ISO 20022 message ID")
    instruction_hash: Optional[str] = Field(None, description="Hash of the smart contract instruction")
    executed_at: Optional[datetime] = Field(None, description="Execution timestamp")
    failure_reason: Optional[str] = Field(None, description="Reason for failure if status is FAILED")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UnifiedLedger:
    """
    Unified Ledger implementation following Project Agorá principles.
    Simulates atomic settlement where money and instructions coexist.
    """
    
    def __init__(self, initial_balance: float = 1000000000.0, bank_id: str = "BANK-001"):
        """Initialize the unified ledger."""
        self.bank_id = bank_id
        self.ledger_state: Dict[str, float] = {bank_id: initial_balance}
        self.tokenized_deposits: Dict[str, TokenizedDeposit] = {}
        self.settlements: List[AtomicSettlement] = []
        self.instruction_log: List[Dict] = []
        
        # Initialize with tokenized deposits
        self._mint_initial_deposits(initial_balance)
    
    def _mint_initial_deposits(self, amount: float):
        """Mint initial tokenized deposits."""
        deposit = TokenizedDeposit(
            owner=self.bank_id,
            amount=amount,
            currency="USD"
        )
        self.tokenized_deposits[deposit.token_id] = deposit
    
    def get_total_tokenized_balance(self, account: str) -> float:
        """Get total tokenized balance for an account."""
        total = 0.0
        for token in self.tokenized_deposits.values():
            if token.owner == account and token.status == "ACTIVE":
                total += token.amount
        return total
    
    def mint_deposit(self, owner: str, amount: float, currency: str = "USD") -> TokenizedDeposit:
        """
        Mint new tokenized deposits (simulating incoming payment).
        
        Args:
            owner: Account owner
            amount: Amount to mint
            currency: Currency code
            
        Returns:
            Created TokenizedDeposit
        """
        deposit = TokenizedDeposit(
            owner=owner,
            amount=amount,
            currency=currency
        )
        self.tokenized_deposits[deposit.token_id] = deposit
        
        # Update ledger state
        if owner not in self.ledger_state:
            self.ledger_state[owner] = 0.0
        self.ledger_state[owner] += amount
        
        # Log instruction
        self.instruction_log.append({
            "type": "MINT",
            "token_id": deposit.token_id,
            "owner": owner,
            "amount": amount,
            "timestamp": datetime.now().isoformat()
        })
        
        return deposit
    
    def burn_deposit(self, owner: str, amount: float) -> List[str]:
        """
        Burn tokenized deposits (simulating outgoing payment).
        Uses FIFO (First In First Out) for token selection.
        
        Args:
            owner: Account owner
            amount: Amount to burn
            
        Returns:
            List of burned token IDs
        """
        available_tokens = [
            (token_id, token) 
            for token_id, token in self.tokenized_deposits.items()
            if token.owner == owner and token.status == "ACTIVE"
        ]
        
        # Sort by creation time (FIFO)
        available_tokens.sort(key=lambda x: x[1].created_at)
        
        burned_tokens = []
        remaining_amount = amount
        
        for token_id, token in available_tokens:
            if remaining_amount <= 0:
                break
            
            if token.amount <= remaining_amount:
                # Burn entire token
                token.status = "BURNED"
                remaining_amount -= token.amount
                burned_tokens.append(token_id)
            else:
                # Partial burn - split token
                remaining_token_amount = token.amount - remaining_amount
                token.amount = remaining_token_amount
                # Create new token for remaining amount
                new_token = TokenizedDeposit(
                    owner=owner,
                    amount=remaining_token_amount,
                    currency=token.currency
                )
                self.tokenized_deposits[new_token.token_id] = new_token
                burned_tokens.append(token_id)
                remaining_amount = 0
        
        # Update ledger state
        if owner in self.ledger_state:
            self.ledger_state[owner] -= amount
        
        # Log instruction
        self.instruction_log.append({
            "type": "BURN",
            "owner": owner,
            "amount": amount,
            "burned_tokens": burned_tokens,
            "timestamp": datetime.now().isoformat()
        })
        
        return burned_tokens
    
    def execute_atomic_settlement(
        self,
        from_account: str,
        to_account: str,
        amount: float,
        message_id: Optional[str] = None
    ) -> AtomicSettlement:
        """
        Execute atomic settlement on the unified ledger.
        This is an all-or-nothing operation (atomicity guarantee).
        
        Args:
            from_account: Debtor account
            to_account: Creditor account
            amount: Settlement amount
            message_id: Associated ISO 20022 message ID
            
        Returns:
            AtomicSettlement object
        """
        settlement = AtomicSettlement(
            from_account=from_account,
            to_account=to_account,
            amount=amount,
            message_id=message_id,
            instruction_hash=f"HASH-{uuid.uuid4().hex[:16].upper()}"
        )
        
        # Check if sufficient balance
        available_balance = self.get_total_tokenized_balance(from_account)
        
        if available_balance < amount:
            settlement.status = SettlementStatus.FAILED
            settlement.failure_reason = f"Insufficient balance. Available: ${available_balance:,.2f}, Required: ${amount:,.2f}"
            self.settlements.append(settlement)
            return settlement
        
        try:
            # Atomic operation: Burn from sender, Mint to receiver
            burned_tokens = self.burn_deposit(from_account, amount)
            minted_deposit = self.mint_deposit(to_account, amount)
            
            # Mark settlement as executed
            settlement.status = SettlementStatus.EXECUTED
            settlement.executed_at = datetime.now()
            
            # Log instruction
            self.instruction_log.append({
                "type": "ATOMIC_SETTLEMENT",
                "settlement_id": settlement.settlement_id,
                "from": from_account,
                "to": to_account,
                "amount": amount,
                "burned_tokens": burned_tokens,
                "minted_token": minted_deposit.token_id,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            settlement.status = SettlementStatus.FAILED
            settlement.failure_reason = str(e)
        
        self.settlements.append(settlement)
        return settlement
    
    def get_ledger_snapshot(self) -> Dict:
        """Get current ledger state snapshot."""
        return {
            "ledger_state": self.ledger_state.copy(),
            "total_tokens": len([t for t in self.tokenized_deposits.values() if t.status == "ACTIVE"]),
            "total_settlements": len(self.settlements),
            "successful_settlements": len([s for s in self.settlements if s.status == SettlementStatus.EXECUTED]),
            "failed_settlements": len([s for s in self.settlements if s.status == SettlementStatus.FAILED]),
            "instruction_count": len(self.instruction_log)
        }

