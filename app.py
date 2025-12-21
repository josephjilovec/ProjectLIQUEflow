"""
Project Lique-Flow: Enhanced Streamlit Control Tower Dashboard
BIS 2025 Aligned: Project Agorá, Adversarial Stress Testing, Project Tamga Compliance
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import json
from typing import List
import io

from src.agents.liquidity_agent import LiquidityAgent
from src.ledger.unified_ledger import UnifiedLedger
from src.agents.adversarial_agent import AdversarialAgent
from src.agents.compliance_agent import ComplianceAgent
from src.utils.models import LiquiditySnapshot, PerformanceMetrics, DecisionResult
from src.simulation.scenarios import ScenarioGenerator, PerformanceTracker
from src.message_generator.iso20022_generator import ISO20022Generator
from src.security.guardrails import AuditLogger


# Page configuration
st.set_page_config(
    page_title="Project Lique-Flow | Enterprise Liquidity Optimization",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark Mode CSS (Financial Theme)
DARK_MODE_CSS = """
    <style>
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #00d4ff;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #8b949e;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #161b22;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #00d4ff;
    }
    .audit-log {
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        background-color: #0d1117;
        color: #c9d1d9;
        padding: 1rem;
        border-radius: 0.5rem;
        max-height: 400px;
        overflow-y: auto;
    }
    .stress-indicator {
        background-color: #da3633;
        color: white;
        padding: 0.5rem;
        border-radius: 0.25rem;
        font-weight: bold;
        text-align: center;
    }
    </style>
"""

st.markdown(DARK_MODE_CSS, unsafe_allow_html=True)


def initialize_session_state():
    """Initialize Streamlit session state."""
    if "agent" not in st.session_state:
        initial_balance = st.session_state.get("initial_balance", 1000000000.0)  # $1B
        st.session_state.agent = LiquidityAgent(initial_balance=initial_balance)
    
    if "ledger" not in st.session_state:
        initial_balance = st.session_state.get("initial_balance", 1000000000.0)
        st.session_state.ledger = UnifiedLedger(initial_balance=initial_balance)
    
    if "compliance_agent" not in st.session_state:
        st.session_state.compliance_agent = ComplianceAgent()
    
    if "adversarial_agent" not in st.session_state:
        st.session_state.adversarial_agent = AdversarialAgent()
    
    if "unified_ledger_mode" not in st.session_state:
        st.session_state.unified_ledger_mode = False
    
    if "current_state" not in st.session_state:
        st.session_state.current_state = LiquiditySnapshot(
            current_balance=st.session_state.get("initial_balance", 1000000000.0),
            pending_queue=[],
            incoming_projections={},
            risk_score=0.0,
            decision_log=[],
            total_settled_today=0.0,
            total_delayed_today=0.0
        )
    
    if "performance_tracker" not in st.session_state:
        st.session_state.performance_tracker = PerformanceTracker()
    
    if "audit_log" not in st.session_state:
        st.session_state.audit_log = []
    
    if "simulation_running" not in st.session_state:
        st.session_state.simulation_running = False
    
    if "decision_history" not in st.session_state:
        st.session_state.decision_history = []
    
    if "stress_test_active" not in st.session_state:
        st.session_state.stress_test_active = False


def calculate_system_health_score(state: LiquiditySnapshot, metrics: PerformanceMetrics) -> float:
    """Calculate system health score (0-100%)."""
    score = 100.0
    
    # Deduct for high risk
    score -= state.risk_score * 30
    
    # Deduct for low liquidity
    if state.current_balance < 100000000:  # Below $100M
        score -= 20
    
    # Deduct for high queue
    if len(state.pending_queue) > 10:
        score -= 15
    
    # Deduct for failed settlements
    if metrics.total_transactions_processed > 0:
        failure_rate = (metrics.total_transactions_processed - metrics.total_settled) / metrics.total_transactions_processed
        score -= failure_rate * 25
    
    return max(0.0, min(100.0, score))


def calculate_liquidity_buffer_efficiency(state: LiquiditySnapshot, initial_balance: float) -> float:
    """Calculate liquidity buffer efficiency (0-100%)."""
    if initial_balance == 0:
        return 0.0
    
    # Efficiency = how well we're using the buffer (higher is better, but not too high)
    utilization = (initial_balance - state.current_balance) / initial_balance
    
    # Optimal utilization is around 60-80%
    if 0.6 <= utilization <= 0.8:
        return 100.0
    elif utilization < 0.6:
        # Underutilized
        return utilization / 0.6 * 100
    else:
        # Overutilized (risky)
        return max(0, 100 - (utilization - 0.8) * 500)


def render_metrics_dashboard(state: LiquiditySnapshot, metrics: PerformanceMetrics, initial_balance: float):
    """Render the enhanced metrics dashboard."""
    # Calculate new metrics
    health_score = calculate_system_health_score(state, metrics)
    buffer_efficiency = calculate_liquidity_buffer_efficiency(state, initial_balance)
    
    # Update metrics
    metrics.system_health_score = health_score
    metrics.liquidity_buffer_efficiency = buffer_efficiency
    
    # System Health Score (Large, Prominent)
    col1, col2 = st.columns([1, 3])
    with col1:
        # Health Score Gauge
        fig_health = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = health_score,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "System Health"},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 50], 'color': "lightgray"},
                    {'range': [50, 80], 'color': "gray"},
                    {'range': [80, 100], 'color': "lightgreen"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        fig_health.update_layout(height=200, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_health, use_container_width=True)
    
    with col2:
        col2a, col2b, col2c, col2d = st.columns(4)
        
        with col2a:
            st.metric(
                label="Current Balance (HQLA)",
                value=f"${state.current_balance:,.0f}",
                delta=f"${state.total_settled_today:,.0f} settled"
            )
        
        with col2b:
            avg_time = metrics.average_processing_time if metrics.average_processing_time > 0 else 0.0
            st.metric(
                label="Settlement Speed",
                value=f"{avg_time:.2f}s",
                delta=f"vs {17.5*60:.0f}s manual"
            )
        
        with col2c:
            st.metric(
                label="Risk Score",
                value=f"{state.risk_score:.2f}",
                delta="0.0 = Low, 1.0 = High"
            )
        
        with col2d:
            st.metric(
                label="Buffer Efficiency",
                value=f"{buffer_efficiency:.1f}%",
                delta="Optimal: 60-80%"
            )
    
    # Liquidity Buffer Efficiency Gauge
    st.subheader("📊 Liquidity Buffer Efficiency")
    fig_efficiency = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = buffer_efficiency,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Buffer Efficiency %"},
        delta = {'reference': 70},
        gauge = {
            'axis': {'range': [None, 100]},
            'bar': {'color': "darkgreen"},
            'steps': [
                {'range': [0, 60], 'color': "lightgray"},
                {'range': [60, 80], 'color': "lightgreen"},
                {'range': [80, 100], 'color': "green"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ))
    fig_efficiency.update_layout(height=250, margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig_efficiency, use_container_width=True)


def render_stress_indicator():
    """Render stress test indicator."""
    if st.session_state.get("stress_test_active", False):
        st.markdown('<div class="stress-indicator">⚠️ SYSTEMIC STRESS TEST ACTIVE - TRIAGE MODE ENGAGED</div>', unsafe_allow_html=True)


def run_simulation_scenario(scenario_name: str, use_unified_ledger: bool = False):
    """Run a simulation scenario with optional unified ledger mode."""
    scenario_gen = ScenarioGenerator(initial_balance=st.session_state.current_state.current_balance)
    state = st.session_state.current_state
    tracker = st.session_state.performance_tracker
    agent = st.session_state.agent
    compliance = st.session_state.compliance_agent
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    messages = []
    reduced_projections = {}
    
    try:
        if scenario_name == "Happy Path":
            messages = list(scenario_gen.happy_path(duration_minutes=5, transactions_per_minute=2.0))
        elif scenario_name == "Liquidity Shock":
            messages = scenario_gen.liquidity_shock(
                shock_amount=500000000.0,
                current_buffer=state.current_balance
            )
        elif scenario_name == "End-of-Day Crunch":
            messages = list(scenario_gen.end_of_day_crunch())
        elif scenario_name == "Systemic Liquidity Crunch":
            st.session_state.stress_test_active = True
            messages, reduced_projections = scenario_gen.systemic_liquidity_crunch(
                base_balance=state.current_balance,
                stress_level=1.0
            )
            state.incoming_projections = reduced_projections
    except Exception as e:
        st.error(f"Error generating scenario: {str(e)}")
        progress_bar.empty()
        status_text.empty()
        return
    
    total_messages = len(messages)
    
    if total_messages == 0:
        st.warning("No messages generated for this scenario.")
        progress_bar.empty()
        status_text.empty()
        return
    
    for i, message in enumerate(messages):
        progress = (i + 1) / total_messages
        progress_bar.progress(progress)
        status_text.text(f"Processing message {i+1}/{total_messages}: {message.msg_id}")
        
        try:
            # Update incoming projections if not already set
            if not state.incoming_projections:
                state.incoming_projections = scenario_gen.generate_incoming_projections(hours_ahead=2)
            
            # Process message
            start_time = time.time()
            decision_result = agent.process_message(message, state)
            processing_time = time.time() - start_time
            
            if decision_result is None:
                st.warning(f"No decision result for message {message.msg_id}")
                continue
            
            # Unified Ledger Mode: Execute atomic settlement
            if use_unified_ledger and decision_result.decision == "SETTLE":
                settlement = st.session_state.ledger.execute_atomic_settlement(
                    from_account=st.session_state.ledger.bank_id,
                    to_account="BENEFICIARY_BANK",
                    amount=message.amount,
                    message_id=message.msg_id
                )
                
                if settlement.status.value == "EXECUTED":
                    state.current_balance -= message.amount
                    state.total_settled_today += message.amount
                    tracker.record_settlement(message, decision_result.timestamp, processing_time)
                else:
                    # Settlement failed on ledger
                    decision_result.decision = "QUEUE"
                    state.pending_queue.append(message)
            
            # Standard mode
            elif not use_unified_ledger:
                if decision_result.decision == "SETTLE":
                    state.current_balance -= message.amount
                    state.total_settled_today += message.amount
                    tracker.record_settlement(message, decision_result.timestamp, processing_time)
                elif decision_result.decision == "QUEUE":
                    state.pending_queue.append(message)
                    state.total_delayed_today += message.amount
                    tracker.record_queue(message, decision_result.timestamp)
                elif decision_result.decision == "REQUIRE_HUMAN_OVERRIDE":
                    tracker.record_human_override()
            
            # Generate compliance proof
            proof = compliance.generate_proof_of_intent(decision_result, message)
            
            # Update risk score
            state.risk_score = decision_result.risk_score
            state.last_update = datetime.now()
            
            # Create audit artifact
            audit_artifact = AuditLogger.log_decision(decision_result)
            st.session_state.audit_log.append(audit_artifact)
            st.session_state.decision_history.append(decision_result)
            
            # Update performance metrics
            tracker.update_liquidity_peak(state.current_balance)
            
        except Exception as e:
            st.error(f"Error processing message {message.msg_id}: {str(e)}")
            continue
        
        # Small delay for visualization
        time.sleep(0.1)
    
    progress_bar.empty()
    status_text.empty()
    st.session_state.stress_test_active = False
    st.success(f"✅ Scenario '{scenario_name}' completed! Processed {total_messages} messages.")


def generate_regulatory_report_pdf() -> bytes:
    """Generate regulatory report as JSON (PDF simulation)."""
    compliance = st.session_state.compliance_agent
    decisions = st.session_state.decision_history
    
    # Get messages from decisions
    messages = []
    for decision in decisions:
        # Create a minimal message object for the report
        from src.utils.models import ISO20022Message, PaymentType, PriorityTier
        msg = ISO20022Message(
            msg_id=decision.message_id,
            msg_type=PaymentType.PACS_008,
            cre_dt_tm=decision.timestamp,
            priority=PriorityTier.NORMAL,
            amount=decision.liquidity_before - (decision.liquidity_after or decision.liquidity_before),
            currency="USD",
            end_to_end_id=decision.message_id
        )
        messages.append(msg)
    
    report = compliance.generate_regulatory_report(decisions, messages)
    
    # Convert to JSON string
    json_str = json.dumps(report, indent=2, default=str)
    
    # Return as bytes (simulating PDF)
    return json_str.encode('utf-8')


def main():
    """Main Streamlit application."""
    initialize_session_state()
    
    # Header
    st.markdown('<div class="main-header">💰 Project Lique-Flow</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Enterprise-Grade Autonomous Agentic Layer | BIS 2025 Aligned</div>', unsafe_allow_html=True)
    
    # Stress Indicator
    render_stress_indicator()
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Control Panel")
        
        st.subheader("Initial Configuration")
        initial_balance = st.number_input(
            "Initial Balance (USD)",
            min_value=1000000.0,
            max_value=10000000000.0,
            value=1000000000.0,
            step=10000000.0,
            format="%.0f"
        )
        
        # Unified Ledger Mode Toggle
        st.divider()
        st.subheader("🔗 Project Agorá: Unified Ledger")
        unified_ledger_mode = st.checkbox(
            "Enable Tokenized Unified Ledger Mode",
            value=st.session_state.unified_ledger_mode,
            help="Simulates atomic settlement on unified ledger where money and instructions coexist"
        )
        st.session_state.unified_ledger_mode = unified_ledger_mode
        
        if unified_ledger_mode:
            ledger_snapshot = st.session_state.ledger.get_ledger_snapshot()
            st.info(f"**Active Tokens:** {ledger_snapshot['total_tokens']}\n\n**Settlements:** {ledger_snapshot['successful_settlements']} successful")
        
        if st.button("🔄 Reset System"):
            st.session_state.agent = LiquidityAgent(initial_balance=initial_balance)
            st.session_state.ledger = UnifiedLedger(initial_balance=initial_balance)
            st.session_state.current_state = LiquiditySnapshot(
                current_balance=initial_balance,
                pending_queue=[],
                incoming_projections={},
                risk_score=0.0,
                decision_log=[],
                total_settled_today=0.0,
                total_delayed_today=0.0
            )
            st.session_state.performance_tracker = PerformanceTracker()
            st.session_state.audit_log = []
            st.session_state.decision_history = []
            st.session_state.compliance_agent = ComplianceAgent()
            st.session_state.stress_test_active = False
            st.success("System reset!")
            st.rerun()
        
        st.divider()
        
        st.subheader("📊 Simulation Scenarios")
        scenario = st.selectbox(
            "Select Scenario",
            ["Happy Path", "Liquidity Shock", "End-of-Day Crunch", "Systemic Liquidity Crunch"]
        )
        
        if st.button("▶️ Run Scenario", type="primary"):
            st.session_state.simulation_running = True
            run_simulation_scenario(scenario, use_unified_ledger=unified_ledger_mode)
            st.session_state.simulation_running = False
            st.rerun()
        
        st.divider()
        
        st.subheader("🔴 Adversarial Stress Testing")
        if st.button("⚠️ TRIGGER SYSTEMIC STRESS TEST", type="secondary"):
            st.session_state.stress_test_active = True
            run_simulation_scenario("Systemic Liquidity Crunch", use_unified_ledger=unified_ledger_mode)
            st.rerun()
        
        st.divider()
        
        st.subheader("📄 Regulatory Compliance")
        if st.session_state.decision_history:
            report_bytes = generate_regulatory_report_pdf()
            st.download_button(
                label="📥 Download Audit PDF (JSON)",
                data=report_bytes,
                file_name=f"regulatory_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        
        st.divider()
        
        st.subheader("ℹ️ System Info")
        st.info(f"**Version:** 2.0.0 (BIS 2025 Enhanced)\n\n**Status:** {'🟢 Running' if not st.session_state.simulation_running else '🟡 Processing'}")
    
    # Main content area
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "🔍 Audit Log", "📈 Performance Analytics", "🔗 Unified Ledger"])
    
    with tab1:
        st.header("Real-Time Liquidity Dashboard")
        
        # Enhanced Metrics
        render_metrics_dashboard(
            st.session_state.current_state,
            st.session_state.performance_tracker.metrics,
            initial_balance
        )
        
        st.divider()
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            # Settlement speed comparison
            manual_time = 17.5 * 60
            agent_time = metrics.average_processing_time if metrics.average_processing_time > 0 else 30.0
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=['Human Manual Review', 'Agentic Review'],
                y=[manual_time, agent_time],
                marker_color=['#d62728', '#2ca02c'],
                text=[f"{manual_time:.0f}s", f"{agent_time:.2f}s"],
                textposition='outside'
            ))
            fig.update_layout(
                title="Settlement Speed Comparison",
                yaxis_title="Time (seconds)",
                height=300,
                margin=dict(l=0, r=0, t=30, b=0)
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Transaction breakdown
            metrics = st.session_state.performance_tracker.metrics
            if metrics.total_transactions_processed > 0:
                fig = go.Figure(data=[
                    go.Pie(
                        labels=['Settled', 'Queued', 'Human Override'],
                        values=[
                            metrics.total_settled,
                            metrics.total_queued,
                            metrics.total_human_overrides
                        ],
                        hole=0.4
                    )
                ])
                fig.update_layout(
                    title="Transaction Breakdown",
                    height=300,
                    margin=dict(l=0, r=0, t=30, b=0)
                )
                st.plotly_chart(fig, use_container_width=True)
        
        # Pending queue
        if st.session_state.current_state.pending_queue:
            st.subheader("⏳ Pending Queue")
            queue_df = pd.DataFrame([
                {
                    "Message ID": msg.msg_id,
                    "Amount": f"${msg.amount:,.2f}",
                    "Priority": msg.priority,
                    "End-to-End ID": msg.end_to_end_id
                }
                for msg in st.session_state.current_state.pending_queue
            ])
            st.dataframe(queue_df, use_container_width=True, hide_index=True)
    
    with tab2:
        st.subheader("🔍 Live Audit Log (Chain of Thought)")
        with st.expander("View Full Audit Trail", expanded=True):
            log_container = st.container()
            recent_entries = st.session_state.audit_log[-50:] if len(st.session_state.audit_log) > 50 else st.session_state.audit_log
            for entry in recent_entries:
                timestamp = entry.get("timestamp", datetime.now().isoformat())
                message_id = entry.get("input_message_id", "N/A")
                decision = entry.get("decision", "N/A")
                reasoning = entry.get("reasoning_steps", [])
                log_container.markdown(f"**{timestamp}** | `{message_id}` | Decision: **{decision}**")
                if reasoning:
                    with log_container.expander("View Reasoning Steps"):
                        for i, step in enumerate(reasoning, 1):
                            log_container.markdown(f"{i}. {step}")
                log_container.divider()
    
    with tab3:
        st.header("Performance Analytics")
        
        metrics = st.session_state.performance_tracker.calculate_final_metrics(
            st.session_state.current_state
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Total Transactions", metrics.total_transactions_processed)
            st.metric("Total Settled", metrics.total_settled)
            st.metric("Total Queued", metrics.total_queued)
            st.metric("Human Overrides", metrics.total_human_overrides)
        
        with col2:
            st.metric("Avg Processing Time", f"{metrics.average_processing_time:.2f}s")
            st.metric("Avg Settlement Delay", f"{metrics.average_settlement_delay:.2f}s")
            st.metric("Time Saved vs Manual", f"{metrics.human_manual_time_saved/60:.1f} minutes")
            st.metric("Opportunity Cost Saved", f"${metrics.opportunity_cost_saved:,.2f}")
            st.metric("System Health Score", f"{metrics.system_health_score:.1f}%")
            st.metric("Buffer Efficiency", f"{metrics.liquidity_buffer_efficiency:.1f}%")
    
    with tab4:
        st.header("🔗 Unified Ledger (Project Agorá)")
        
        if unified_ledger_mode:
            ledger_snapshot = st.session_state.ledger.get_ledger_snapshot()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Tokens", ledger_snapshot['total_tokens'])
            with col2:
                st.metric("Total Settlements", ledger_snapshot['total_settlements'])
            with col3:
                st.metric("Successful", ledger_snapshot['successful_settlements'])
            with col4:
                st.metric("Failed", ledger_snapshot['failed_settlements'])
            
            # Recent Settlements
            if st.session_state.ledger.settlements:
                st.subheader("Recent Atomic Settlements")
                recent_settlements = st.session_state.ledger.settlements[-10:]
                settlement_data = []
                for s in recent_settlements:
                    settlement_data.append({
                        "Settlement ID": s.settlement_id,
                        "From": s.from_account,
                        "To": s.to_account,
                        "Amount": f"${s.amount:,.2f}",
                        "Status": s.status.value,
                        "Timestamp": s.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    })
                st.dataframe(pd.DataFrame(settlement_data), use_container_width=True, hide_index=True)
        else:
            st.info("Enable Unified Ledger Mode in the sidebar to see tokenized settlement activity.")


if __name__ == "__main__":
    main()

