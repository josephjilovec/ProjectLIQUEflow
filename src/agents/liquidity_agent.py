"""
Liquidity Management Agent using LangGraph
Implements the Cash Manager decision logic with Chain of Thought reasoning.
"""

from typing import TypedDict, List, Annotated
from datetime import datetime, timedelta
import operator

try:
    from langgraph.graph import StateGraph, END
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    # Create dummy classes for when LangGraph is not available
    class StateGraph:
        def __init__(self, *args, **kwargs):
            pass
        def add_node(self, *args, **kwargs):
            return self
        def set_entry_point(self, *args, **kwargs):
            return self
        def add_edge(self, *args, **kwargs):
            return self
        def add_conditional_edges(self, *args, **kwargs):
            return self
        def compile(self):
            return DummyGraph()
    class END:
        pass
    class DummyGraph:
        def invoke(self, state):
            return state

from src.utils.models import (
    ISO20022Message, 
    LiquiditySnapshot, 
    DecisionResult, 
    PriorityTier
)
from src.utils.secrets_manager import SecretsManager
from src.security.guardrails import CircuitBreaker, AuditLogger


class AgentState(TypedDict):
    """LangGraph state definition for the liquidity agent."""
    current_balance: float
    pending_queue: Annotated[List[ISO20022Message], operator.add]
    incoming_projections: dict
    risk_score: float
    decision_log: Annotated[List[str], operator.add]
    new_message: ISO20022Message
    decision_result: DecisionResult
    total_settled_today: float
    total_delayed_today: float
    last_update: datetime


class LiquidityAgent:
    """
    Autonomous Cash Manager Agent.
    Uses LangGraph for cyclic reasoning and decision-making.
    """
    
    def __init__(self, initial_balance: float = 1000000000.0):  # $1B default
        """Initialize the liquidity agent."""
        self.initial_balance = initial_balance
        self.circuit_breaker = CircuitBreaker()
        self.circuit_breaker.set_total_liquidity_pool(initial_balance)
        
        # Initialize LLM (optional - can work without it)
        self.llm = None
        if LANGGRAPH_AVAILABLE:
            provider = SecretsManager.get_model_provider()
            model_name = SecretsManager.get_model_name()
            
            if provider == "anthropic":
                api_key = SecretsManager.get_anthropic_api_key()
                if api_key:
                    try:
                        self.llm = ChatAnthropic(model=model_name, api_key=api_key, temperature=0.1)
                    except Exception:
                        pass
            
            if self.llm is None:
                api_key = SecretsManager.get_openai_api_key()
                if api_key:
                    try:
                        self.llm = ChatOpenAI(model=model_name, api_key=api_key, temperature=0.1)
                    except Exception:
                        pass
        
        # Build the graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("check_guardrails", self._check_guardrails_node)
        workflow.add_node("cash_manager", self._cash_manager_node)
        workflow.add_node("execute_settlement", self._execute_settlement_node)
        workflow.add_node("update_state", self._update_state_node)
        
        # Define edges
        workflow.set_entry_point("check_guardrails")
        workflow.add_edge("check_guardrails", "cash_manager")
        workflow.add_conditional_edges(
            "cash_manager",
            self._should_execute,
            {
                "SETTLE": "execute_settlement",
                "QUEUE": "update_state",
                "REJECT": "update_state",
                "REQUIRE_HUMAN_OVERRIDE": "update_state"
            }
        )
        workflow.add_edge("execute_settlement", "update_state")
        workflow.add_edge("update_state", END)
        
        return workflow.compile()
    
    def _check_guardrails_node(self, state: AgentState) -> AgentState:
        """Check circuit breaker and security guardrails."""
        message = state["new_message"]
        current_balance = state["current_balance"]
        
        is_allowed, reason = self.circuit_breaker.check_transaction(message, current_balance)
        
        if not is_allowed:
            state["decision_log"].append(f"GUARDRAIL: Transaction blocked - {reason}")
            state["decision_result"] = DecisionResult(
                message_id=message.msg_id,
                decision="REJECT",
                reasoning_steps=[f"Circuit breaker blocked transaction: {reason}"],
                timestamp=datetime.now(),
                liquidity_before=current_balance,
                risk_score=1.0
            )
        
        return state
    
    def _cash_manager_node(self, state: AgentState) -> AgentState:
        """
        Primary decision-making node.
        Implements BIS Working Paper 1310 (2025) decision matrix.
        """
        # If already rejected by guardrails, skip
        if "decision_result" in state and state["decision_result"] is not None:
            if state["decision_result"].decision == "REJECT":
                return state
        
        message = state["new_message"]
        current_balance = state["current_balance"]
        pending_queue = state["pending_queue"]
        incoming_projections = state["incoming_projections"]
        
        reasoning_steps = []
        decision = "QUEUE"
        
        # Step 1: Priority Check
        if message.priority == PriorityTier.URGENT or message.is_sovereign:
            reasoning_steps.append(f"Priority check: {message.priority} priority or sovereign payment detected. Attempting immediate settlement.")
            decision = "SETTLE"
        else:
            reasoning_steps.append(f"Priority check: {message.priority} priority - standard processing.")
        
        # Step 2: Liquidity Threshold Check
        daily_volume_estimate = self.initial_balance * 2  # Rough estimate
        precautionary_buffer = daily_volume_estimate * 0.20  # 20% buffer
        
        if current_balance < precautionary_buffer:
            reasoning_steps.append(f"Liquidity threshold: Current balance ${current_balance:,.2f} below precautionary buffer ${precautionary_buffer:,.2f}. Entering conservative mode.")
            if message.priority != PriorityTier.URGENT and not message.is_sovereign:
                decision = "QUEUE"
                reasoning_steps.append("Non-urgent payment queued due to low liquidity buffer.")
        
        # Step 3: Opportunity Cost Calculation
        if decision == "QUEUE" and message.amount <= current_balance:
            # Calculate if delaying saves money
            intraday_credit_rate = 0.0001  # 0.01% per hour (rough estimate)
            delay_hours = 2.0  # Assume 2-hour delay
            
            delay_cost = message.amount * intraday_credit_rate * delay_hours
            
            # Check if incoming funds expected soon
            next_inflow = self._get_next_inflow(incoming_projections)
            if next_inflow and next_inflow > message.amount:
                reasoning_steps.append(f"Opportunity cost: Delaying saves ${delay_cost:,.2f} in intraday credit. Inflow of ${next_inflow:,.2f} expected soon.")
                decision = "QUEUE"
            else:
                reasoning_steps.append(f"Opportunity cost: No significant savings from delay. Proceeding with settlement.")
                decision = "SETTLE"
        
        # Step 4: Check if settlement is possible
        if decision == "SETTLE" and message.amount > current_balance:
            reasoning_steps.append(f"Insufficient balance for immediate settlement. Amount: ${message.amount:,.2f}, Available: ${current_balance:,.2f}")
            if message.priority == PriorityTier.URGENT or message.is_sovereign:
                reasoning_steps.append("Urgent/sovereign payment requires liquidity repo. Triggering repo request.")
                decision = "SETTLE"  # Will trigger repo
            else:
                decision = "QUEUE"
        
        # Step 5: Human Override Check
        if self.circuit_breaker.should_trigger_human_override(message, current_balance):
            reasoning_steps.append("Transaction exceeds 80% of maximum allowable variance or 40% of total liquidity. Human override required.")
            decision = "REQUIRE_HUMAN_OVERRIDE"
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(current_balance, message, pending_queue)
        
        # Calculate opportunity cost saved (if queued)
        opportunity_cost_saved = None
        if decision == "QUEUE":
            intraday_credit_rate = 0.0001
            delay_hours = 2.0
            opportunity_cost_saved = message.amount * intraday_credit_rate * delay_hours
        
        # Create decision result
        state["decision_result"] = DecisionResult(
            message_id=message.msg_id,
            decision=decision,
            reasoning_steps=reasoning_steps,
            timestamp=datetime.now(),
            liquidity_before=current_balance,
            opportunity_cost_saved=opportunity_cost_saved,
            risk_score=risk_score
        )
        
        state["decision_log"].extend(reasoning_steps)
        
        return state
    
    def _should_execute(self, state: AgentState) -> str:
        """Determine next step based on decision."""
        if "decision_result" not in state or state["decision_result"] is None:
            return "QUEUE"
        return state["decision_result"].decision
    
    def _execute_settlement_node(self, state: AgentState) -> AgentState:
        """Execute the settlement and update balance."""
        message = state["new_message"]
        current_balance = state["current_balance"]
        
        # Check if repo is needed
        if message.amount > current_balance:
            # Simulate liquidity repo (borrowing)
            repo_amount = message.amount - current_balance
            state["decision_log"].append(f"LIQUIDITY REPO: Borrowing ${repo_amount:,.2f} to cover deficit.")
            current_balance = message.amount  # Balance after repo
        
        # Execute settlement
        new_balance = current_balance - message.amount
        state["current_balance"] = new_balance
        state["total_settled_today"] += message.amount
        
        if state["decision_result"]:
            state["decision_result"].liquidity_after = new_balance
        state["decision_log"].append(f"SETTLEMENT EXECUTED: ${message.amount:,.2f} settled. New balance: ${new_balance:,.2f}")
        
        return state
    
    def _update_state_node(self, state: AgentState) -> AgentState:
        """Update state after decision."""
        message = state["new_message"]
        decision = state["decision_result"].decision if "decision_result" in state and state["decision_result"] else "QUEUE"
        
        if decision == "QUEUE":
            state["pending_queue"].append(message)
            state["total_delayed_today"] += message.amount
            state["decision_log"].append(f"PAYMENT QUEUED: {message.msg_id} added to pending queue.")
        
        state["last_update"] = datetime.now()
        
        # Update risk score
        state["risk_score"] = self._calculate_risk_score(
            state["current_balance"],
            message,
            state["pending_queue"]
        )
        
        return state
    
    def _get_next_inflow(self, incoming_projections: dict) -> float:
        """Get the next expected inflow amount."""
        if not incoming_projections:
            return 0.0
        
        # Get the earliest projection
        sorted_times = sorted(incoming_projections.keys())
        if sorted_times:
            return incoming_projections[sorted_times[0]]
        return 0.0
    
    def _calculate_risk_score(
        self, 
        current_balance: float, 
        message: ISO20022Message,
        pending_queue: List[ISO20022Message]
    ) -> float:
        """
        Calculate risk score based on buffer-to-outflow ratio.
        Returns value between 0.0 (low risk) and 1.0 (high risk).
        """
        total_pending = sum(msg.amount for msg in pending_queue)
        total_outflow = message.amount + total_pending
        
        if current_balance == 0:
            return 1.0
        
        buffer_ratio = current_balance / (total_outflow + 1)  # +1 to avoid division by zero
        
        # Normalize to 0-1 scale
        if buffer_ratio >= 2.0:
            return 0.0
        elif buffer_ratio >= 1.0:
            return 0.2
        elif buffer_ratio >= 0.5:
            return 0.5
        elif buffer_ratio >= 0.2:
            return 0.7
        else:
            return 1.0
    
    def process_message(
        self, 
        message: ISO20022Message,
        current_state: LiquiditySnapshot
    ) -> DecisionResult:
        """
        Process a single ISO 20022 message through the agent.
        
        Args:
            message: The message to process
            current_state: Current liquidity snapshot
            
        Returns:
            DecisionResult with full audit trail
        """
        # Convert LiquiditySnapshot to AgentState
        initial_state: AgentState = {
            "current_balance": current_state.current_balance,
            "pending_queue": current_state.pending_queue.copy(),
            "incoming_projections": current_state.incoming_projections.copy(),
            "risk_score": current_state.risk_score,
            "decision_log": [],
            "new_message": message,
            "decision_result": None,
            "total_settled_today": current_state.total_settled_today,
            "total_delayed_today": current_state.total_delayed_today,
            "last_update": current_state.last_update
        }
        
        # Run the graph
        final_state = self.graph.invoke(initial_state)
        
        return final_state["decision_result"]
