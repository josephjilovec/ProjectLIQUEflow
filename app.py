"""
Project Lique-Flow: Streamlit Control Tower Dashboard
Main entry point for the liquidity optimization system.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import json
from typing import List

from src.agents.liquidity_agent import LiquidityAgent
from src.utils.models import LiquiditySnapshot, PerformanceMetrics, DecisionResult
from src.simulation.scenarios import ScenarioGenerator, PerformanceTracker
from src.message_generator.iso20022_generator import ISO20022Generator
from src.security.guardrails import AuditLogger


# Page configuration
st.set_page_config(
    page_title="Project Lique-Flow | Liquidity Optimization Control Tower",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .audit-log {
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        background-color: #1e1e1e;
        color: #d4d4d4;
        padding: 1rem;
        border-radius: 0.5rem;
        max-height: 400px;
        overflow-y: auto;
    }
    </style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize Streamlit session state."""
    if "agent" not in st.session_state:
        initial_balance = st.session_state.get("initial_balance", 1000000000.0)  # $1B
        st.session_state.agent = LiquidityAgent(initial_balance=initial_balance)
    
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


def render_metrics_dashboard(state: LiquiditySnapshot, metrics: PerformanceMetrics):
    """Render the main metrics dashboard."""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Current Balance (HQLA)",
            value=f"${state.current_balance:,.0f}",
            delta=f"${state.total_settled_today:,.0f} settled today"
        )
    
    with col2:
        avg_time = metrics.average_processing_time if metrics.average_processing_time > 0 else 0.0
        st.metric(
            label="Settlement Speed",
            value=f"{avg_time:.2f}s",
            delta=f"vs {17.5*60:.0f}s manual"
        )
    
    with col3:
        st.metric(
            label="Liquidity Utilization",
            value=f"${metrics.liquidity_usage_peak:,.0f}",
            delta="Peak usage"
        )
    
    with col4:
        st.metric(
            label="Risk Score",
            value=f"{state.risk_score:.2f}",
            delta="0.0 = Low, 1.0 = High"
        )


def render_liquidity_chart(state_history: List[LiquiditySnapshot]):
    """Render liquidity utilization chart."""
    if not state_history:
        return
    
    timestamps = [s.last_update for s in state_history]
    balances = [s.current_balance for s in state_history]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=balances,
        mode='lines+markers',
        name='Current Balance',
        line=dict(color='#1f77b4', width=2),
        fill='tozeroy',
        fillcolor='rgba(31, 119, 180, 0.1)'
    ))
    
    fig.update_layout(
        title="Liquidity Buffer Over Time",
        xaxis_title="Time",
        yaxis_title="Balance (USD)",
        hovermode='x unified',
        height=300,
        margin=dict(l=0, r=0, t=30, b=0)
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_settlement_speed_comparison(metrics: PerformanceMetrics):
    """Render side-by-side comparison of settlement speeds."""
    manual_time = 17.5 * 60  # 17.5 minutes in seconds
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


def render_audit_log(audit_entries: List[dict]):
    """Render the live audit log."""
    st.subheader("🔍 Live Audit Log (Chain of Thought)")
    
    with st.expander("View Full Audit Trail", expanded=True):
        log_container = st.container()
        
        # Display recent entries (last 50)
        recent_entries = audit_entries[-50:] if len(audit_entries) > 50 else audit_entries
        
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


def run_simulation_scenario(scenario_name: str):
    """Run a simulation scenario."""
    scenario_gen = ScenarioGenerator(initial_balance=st.session_state.current_state.current_balance)
    state = st.session_state.current_state
    tracker = st.session_state.performance_tracker
    agent = st.session_state.agent
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    messages = []
    
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
            # Update incoming projections
            state.incoming_projections = scenario_gen.generate_incoming_projections(hours_ahead=2)
            
            # Process message
            start_time = time.time()
            decision_result = agent.process_message(message, state)
            processing_time = time.time() - start_time
            
            if decision_result is None:
                st.warning(f"No decision result for message {message.msg_id}")
                continue
            
            # Update state based on decision
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
    st.success(f"✅ Scenario '{scenario_name}' completed! Processed {total_messages} messages.")


def main():
    """Main Streamlit application."""
    initialize_session_state()
    
    # Header
    st.markdown('<div class="main-header">💰 Project Lique-Flow</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Autonomous Agentic Layer for Intraday Liquidity Optimization</div>', unsafe_allow_html=True)
    
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
        
        if st.button("🔄 Reset System"):
            st.session_state.agent = LiquidityAgent(initial_balance=initial_balance)
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
            st.success("System reset!")
            st.rerun()
        
        st.divider()
        
        st.subheader("📊 Simulation Scenarios")
        scenario = st.selectbox(
            "Select Scenario",
            ["Happy Path", "Liquidity Shock", "End-of-Day Crunch"]
        )
        
        if st.button("▶️ Run Scenario", type="primary"):
            st.session_state.simulation_running = True
            run_simulation_scenario(scenario)
            st.session_state.simulation_running = False
            st.rerun()
        
        st.divider()
        
        st.subheader("ℹ️ System Info")
        st.info(f"**Version:** 1.0.0\n\n**Status:** {'🟢 Running' if not st.session_state.simulation_running else '🟡 Processing'}")
    
    # Main content area
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "🔍 Audit Log", "📈 Performance Analytics"])
    
    with tab1:
        st.header("Real-Time Liquidity Dashboard")
        
        # Metrics
        render_metrics_dashboard(
            st.session_state.current_state,
            st.session_state.performance_tracker.metrics
        )
        
        st.divider()
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            render_settlement_speed_comparison(st.session_state.performance_tracker.metrics)
        
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
        
        # Liquidity chart
        if st.session_state.decision_history:
            # Create state history from decision history
            state_history = [st.session_state.current_state]
            render_liquidity_chart(state_history)
        
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
        render_audit_log(st.session_state.audit_log)
    
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


if __name__ == "__main__":
    main()
