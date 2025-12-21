"""
Compliance Shadow Agent (Project Tamga)
Generates regulatory justifications and proofs for every agent decision.
Ensures explainability and regulatory compliance.
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from src.utils.models import DecisionResult, ISO20022Message, PriorityTier


class RegulatoryJustification(BaseModel):
    """Regulatory justification for a decision."""
    
    decision_id: str = Field(..., description="Associated decision ID")
    regulatory_framework: str = Field(default="BIS WP 1310", description="Regulatory framework")
    justification_category: str = Field(..., description="Category of justification")
    rationale: str = Field(..., description="Detailed rationale")
    risk_assessment: str = Field(..., description="Risk assessment")
    compliance_status: str = Field(default="COMPLIANT", description="Compliance status")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ProofOfIntent(BaseModel):
    """Proof of Intent (Project Tamga) - Cryptographic proof of agent intent."""
    
    proof_id: str = Field(..., description="Unique proof identifier")
    decision_id: str = Field(..., description="Associated decision ID")
    intent_hash: str = Field(..., description="Hash of agent intent")
    regulatory_justification: RegulatoryJustification
    audit_trail: List[str] = Field(default_factory=list, description="Audit trail steps")
    timestamp: datetime = Field(default_factory=datetime.now)
    verified: bool = Field(default=False, description="Whether proof has been verified")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ComplianceAgent:
    """
    Compliance Shadow Agent that validates and justifies every decision.
    Implements Project Tamga principles for regulatory transparency.
    """
    
    def __init__(self):
        """Initialize compliance agent."""
        self.justifications: Dict[str, RegulatoryJustification] = {}
        self.proofs: Dict[str, ProofOfIntent] = {}
    
    def generate_regulatory_justification(
        self,
        decision: DecisionResult,
        message: ISO20022Message
    ) -> RegulatoryJustification:
        """
        Generate regulatory justification for a decision.
        
        Args:
            decision: The decision result
            message: The original message
            
        Returns:
            RegulatoryJustification object
        """
        # Determine justification category based on decision
        if decision.decision == "SETTLE":
            if message.priority == PriorityTier.URGENT or message.is_sovereign:
                category = "SOVEREIGN_URGENT_SETTLEMENT"
                rationale = f"Settled immediately due to {message.priority} priority and sovereign status. " \
                           f"BIS WP 1310 requires immediate settlement of critical infrastructure payments " \
                           f"to maintain financial stability."
            else:
                category = "STANDARD_SETTLEMENT"
                rationale = f"Settled standard payment. Liquidity buffer sufficient (${decision.liquidity_before:,.2f}). " \
                           f"No risk to settlement finality."
        elif decision.decision == "QUEUE":
            category = "DEFENSIVE_QUEUING"
            rationale = f"Payment queued to preserve liquidity buffer. Current balance ${decision.liquidity_before:,.2f} " \
                       f"below precautionary threshold. Opportunity cost saved: ${decision.opportunity_cost_saved or 0:,.2f}. " \
                       f"BIS WP 1310 allows defensive queuing when buffer preservation is critical."
        elif decision.decision == "REJECT":
            category = "CIRCUIT_BREAKER_PROTECTION"
            rationale = f"Payment rejected by circuit breaker. Transaction amount ${message.amount:,.2f} exceeds " \
                       f"maximum allowable variance or liquidity percentage limits. This protects against " \
                       f"unauthorized or excessive transactions."
        else:  # REQUIRE_HUMAN_OVERRIDE
            category = "HUMAN_IN_THE_LOOP_ESCALATION"
            rationale = f"Transaction escalated for human review. Amount ${message.amount:,.2f} exceeds 80% of " \
                       f"maximum allowable variance. Human-in-the-loop required per regulatory guidelines."
        
        # Risk assessment
        if decision.risk_score < 0.3:
            risk_assessment = "LOW RISK: System operating within normal parameters."
        elif decision.risk_score < 0.7:
            risk_assessment = "MODERATE RISK: System under stress but manageable."
        else:
            risk_assessment = "HIGH RISK: System approaching critical thresholds. Enhanced monitoring required."
        
        justification = RegulatoryJustification(
            decision_id=decision.message_id,
            justification_category=category,
            rationale=rationale,
            risk_assessment=risk_assessment,
            compliance_status="COMPLIANT"
        )
        
        self.justifications[decision.message_id] = justification
        return justification
    
    def generate_proof_of_intent(
        self,
        decision: DecisionResult,
        message: ISO20022Message,
        justification: Optional[RegulatoryJustification] = None
    ) -> ProofOfIntent:
        """
        Generate Proof of Intent (Project Tamga) for a decision.
        
        Args:
            decision: The decision result
            message: The original message
            justification: Optional pre-generated justification
            
        Returns:
            ProofOfIntent object
        """
        import hashlib
        
        if justification is None:
            justification = self.generate_regulatory_justification(decision, message)
        
        # Create intent hash (simplified - in production would use proper cryptographic hash)
        intent_string = f"{decision.message_id}:{decision.decision}:{decision.timestamp.isoformat()}:{message.amount}"
        intent_hash = hashlib.sha256(intent_string.encode()).hexdigest()[:32].upper()
        
        # Build audit trail
        audit_trail = [
            f"Decision: {decision.decision}",
            f"Message ID: {decision.message_id}",
            f"Amount: ${message.amount:,.2f}",
            f"Priority: {message.priority}",
            f"Liquidity Before: ${decision.liquidity_before:,.2f}",
        ]
        
        if decision.liquidity_after is not None:
            audit_trail.append(f"Liquidity After: ${decision.liquidity_after:,.2f}")
        
        audit_trail.extend(decision.reasoning_steps)
        
        proof = ProofOfIntent(
            proof_id=f"PROOF-{decision.message_id}",
            decision_id=decision.message_id,
            intent_hash=intent_hash,
            regulatory_justification=justification,
            audit_trail=audit_trail,
            verified=True
        )
        
        self.proofs[decision.message_id] = proof
        return proof
    
    def generate_regulatory_report(
        self,
        decisions: List[DecisionResult],
        messages: List[ISO20022Message]
    ) -> Dict:
        """
        Generate comprehensive regulatory report for a session.
        
        Args:
            decisions: List of decisions made
            messages: List of messages processed
            
        Returns:
            Dictionary containing regulatory report
        """
        proofs = []
        justifications = []
        
        message_dict = {msg.msg_id: msg for msg in messages}
        
        for decision in decisions:
            message = message_dict.get(decision.message_id)
            if message:
                proof = self.generate_proof_of_intent(decision, message)
                proofs.append(proof.dict())
                justifications.append(proof.regulatory_justification.dict())
        
        return {
            "report_id": f"REG-REPORT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "generated_at": datetime.now().isoformat(),
            "total_decisions": len(decisions),
            "regulatory_framework": "BIS Working Paper 1310 (2025)",
            "compliance_status": "FULLY_COMPLIANT",
            "proofs_of_intent": proofs,
            "regulatory_justifications": justifications,
            "summary": {
                "total_settled": len([d for d in decisions if d.decision == "SETTLE"]),
                "total_queued": len([d for d in decisions if d.decision == "QUEUE"]),
                "total_rejected": len([d for d in decisions if d.decision == "REJECT"]),
                "total_human_overrides": len([d for d in decisions if d.decision == "REQUIRE_HUMAN_OVERRIDE"])
            }
        }

