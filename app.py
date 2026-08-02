import streamlit as st
import pandas as pd
import db
import plotly.express as px
import io

# --- 1. APP CONFIG ---
st.set_page_config(page_title="Pro Trading Journal", layout="wide")


# --- HIDE STREAMLIT BRANDING ---
# hide_st_style = """
#             <style>
#             #MainMenu {visibility: hidden;}
#             footer {visibility: hidden;}
#             header {visibility: hidden;}
#             </style>
#             """
# st.markdown(hide_st_style, unsafe_allow_html=True)


# --- 2. AUTHENTICATION SYSTEM ---
def check_login():
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
        st.session_state["user"] = None

    if st.session_state["logged_in"]:
        return True

    st.markdown("## 🔐 Login to Trading Journal (SaversPoke)")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            if username in st.secrets["passwords"] and st.secrets["passwords"][username] == password:
                st.session_state["logged_in"] = True
                st.session_state["user"] = username
                st.success(f"Welcome back, {username}!")
                st.rerun()
            else:
                st.error("❌ Invalid Username or Password")
    return False

if not check_login():
    st.stop()

# =========================================================
#  MAIN APP (User Specific)
# =========================================================

db.init_db()

# Sidebar User Info
with st.sidebar:
    st.info(f"👤 User: **{st.session_state['user']}**")
    if st.button("Logout"):
        st.session_state["logged_in"] = False
        st.rerun()

st.title("📊 Trading Journal by SaversPoke")

# --- 3. SIDEBAR: DATA ENTRY ---
with st.sidebar:
    st.header("📝 Log New Trade")
    
    accounts_df = db.get_accounts(st.session_state['user'])
    
    if accounts_df.empty:
        st.warning("You have no accounts. Add one below.")
        account_options = {}
    else:
        account_options = dict(zip(accounts_df['name'], accounts_df['id']))
    
    selected_account_name = st.selectbox("Select Account", options=list(account_options.keys()))
    
    if selected_account_name:
        # Dynamically fetch account currency for PnL text
        acc_row = accounts_df[accounts_df['name'] == selected_account_name].iloc[0]
        acc_currency = acc_row.get('currency', '$')
        if pd.isna(acc_currency) or not acc_currency:
            acc_currency = '$'

        with st.form("trade_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            # Custom symbol input 
            s_symbol = c1.text_input("Symbol", placeholder="e.g., AAPL, XAUUSD")
            s_direction = c2.radio("Direction", ["Long", "Short"], horizontal=True)
            
            c3, c4 = st.columns(2)
            s_date = c3.date_input("Date")
            s_qty = c4.number_input("Quantity (Lots/Shares)", min_value=0.01, step=0.01, value=0.01)
            
            # Dynamic Currency text
            s_pnl = st.number_input(f"PnL ({acc_currency})", step=0.01)

            st.markdown("---")
            st.markdown("**🧠 Strategy & Context**")
            
            s_session = st.selectbox("Session", ["Pre-London", "London", "Pre-NYC", "NYC", "Asian"])
            s_setup = st.selectbox("Setup / Strategy", ["BO strat (BR)", "BO strat (Retest)", "PA strat", "CSO strat", "No Setup / Impulse"])
            s_trend = st.selectbox("Trend Context", ["UP", "DOWN", "UP but 15m Down", "DOWN but 15m UP", "Ranging"])
            
            col_a, col_b = st.columns(2)
            s_rules = col_a.radio("Rules Followed?", ["Yes", "No"], horizontal=True)
            s_proper_sl = col_b.radio("Proper SL/TSL?", ["Yes", "No"], horizontal=True)
            
            s_event = st.checkbox("Was this an Event Day?")
            s_event_str = "Yes" if s_event else "No"
            s_notes = st.text_area("Notes")
            
            submitted = st.form_submit_button("Log Trade")
            if submitted:
                # Ensure a symbol was typed
                if not s_symbol.strip():
                    st.error("Please enter a valid Symbol.")
                else:
                    status = "Win" if s_pnl > 0 else ("Loss" if s_pnl < 0 else "BE")
                    db.add_trade(
                        account_options[selected_account_name], s_symbol.upper(), s_direction, s_date, s_qty, s_pnl, status,
                        s_session, s_rules, s_trend, s_setup, s_proper_sl, s_event_str, s_notes
                    )
                    st.success("Trade Logged Successfully!")
                    st.rerun()

    st.markdown("---")
    
    with st.expander("⚙️ Manage Accounts"):
        st.caption("Add New Account")
        a_type = st.selectbox("Type", ["3-Step", "2-Step", "Instant", "Personal Broker"], key="acc_type_select")
        
        with st.form("add_account_form", clear_on_submit=True):
            a_name = st.text_input("Account Name (e.g., QT 1.25k or Personal)")
            a_currency = st.selectbox("Currency", ["$", "₹"])
            a_bal = st.number_input("Initial Balance", value=5000.0)
            
            if a_type != "Personal Broker":
                a_target = st.number_input("Target Payout/Pass Balance", value=5500.0)
                a_loss = st.number_input("Max Drawdown Level (Equity)", value=4500.0)
            else:
                a_target = 0.0
                a_loss = 0.0
            
            if st.form_submit_button("Add Account"):
                db.add_account(st.session_state['user'], a_name, a_type, a_currency, a_bal, a_target, a_loss)
                st.success("Account Added!")
                st.rerun()
        
        st.markdown("---")
        st.caption("❌ Danger Zone")
        
        if not accounts_df.empty:
            del_acc_name = st.selectbox("Select Account to Delete", options=list(account_options.keys()), key="del_select")
            if st.button("🗑️ Delete Account Permanently"):
                db.delete_account(account_options[del_acc_name])
                st.warning(f"Account '{del_acc_name}' deleted.")
                st.rerun()

# --- 4. ANALYTICS ENGINE ---

if not accounts_df.empty:
    filter_options = ["All Accounts"] + list(account_options.keys())
    view_selection = st.selectbox("View Metrics For:", filter_options)
    selected_id = account_options[view_selection] if view_selection != "All Accounts" else "All Accounts"
    
    # Establish dynamic currency for Dashboard
    if selected_id == "All Accounts":
        # Check if all accounts share the same currency
        unique_currencies = accounts_df['currency'].dropna().unique()
        disp_curr = unique_currencies[0] if len(unique_currencies) == 1 else ""
        
        user_account_ids = list(account_options.values())
        if user_account_ids:
            all_trades = db.get_trades() 
            trades = all_trades[all_trades['account_id'].isin(user_account_ids)]
        else:
            trades = pd.DataFrame()
    else:
        curr_acc = accounts_df[accounts_df['id'] == selected_id].iloc[0]
        disp_curr = curr_acc.get('currency', '$')
        if pd.isna(disp_curr) or not disp_curr:
            disp_curr = '$'
            
        trades = db.get_trades(selected_id)
    
    if not trades.empty:
        # KPI ROW
        total_pnl = trades['pnl'].sum()
        total_trades = len(trades)
        total_lots = trades['quantity'].sum()
        win_rate = len(trades[trades['pnl'] > 0]) / total_trades * 100
        
        gross_profit = trades[trades['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(trades[trades['pnl'] < 0]['pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit

        k1, k2, k3, k4, k5 = st.columns(5)
        # Apply dynamic currency to Net PnL
        k1.metric("Net PnL", f"{disp_curr}{total_pnl:,.2f}", delta_color="normal")
        k2.metric("Win Rate", f"{win_rate:.1f}%")
        k3.metric("Profit Factor", f"{profit_factor:.2f}")
        k4.metric("Total Trades", total_trades)
        k5.metric("Total Qty", f"{total_lots:.2f}")

        # PROP FIRM TRACKER (Only for Single Account View & Non-Personal Brokers)
        if view_selection != "All Accounts":
            if curr_acc.get('account_type') != "Personal Broker":
                current_equity = curr_acc['initial_balance'] + total_pnl
                
                st.markdown("### 🎯 Challenge Progress")
                p1, p2 = st.columns(2)
                
                dist_pass = curr_acc['target_payout'] - current_equity
                if dist_pass <= 0:
                    p1.success(f"🏆 PASSED! Current Equity: {disp_curr}{current_equity:,.2f}")
                else:
                    p1.info(f"Target: {disp_curr}{curr_acc['target_payout']:,.0f} | Current: {disp_curr}{current_equity:,.0f}")
                    target_gain = curr_acc['target_payout'] - curr_acc['initial_balance']
                    current_gain = current_equity - curr_acc['initial_balance']
                    progress = current_gain / target_gain if target_gain != 0 else 0
                    p1.progress(min(1.0, max(0.0, progress)))
                
                dist_breach = current_equity - curr_acc['max_drawdown_limit']
                p2.warning(f"Drawdown Buffer: {disp_curr}{dist_breach:,.2f}")

        st.markdown("---")

        # TABS FOR ANALYTICS
        tab1, tab2, tab3, tab4 = st.tabs(["📈 Overview", "🧠 Psychology", "🛠 Strategy", "⏰ Time"])
        
        with tab1:
            c1, c2 = st.columns([2, 1])
            trades['cumulative_pnl'] = trades['pnl'].cumsum()
            fig_equity = px.line(trades, x='id', y='cumulative_pnl', title=f'Equity Curve ({disp_curr})', markers=True)
            c1.plotly_chart(fig_equity, use_container_width=True)
            fig_hist = px.histogram(trades, x="pnl", nbins=20, title="PnL Distribution", color="status")
            c2.plotly_chart(fig_hist, use_container_width=True)

        with tab2:
            st.markdown("#### Are you following your plan?")
            col1, col2 = st.columns(2)
            rules_pnl = trades.groupby('rules_followed')['pnl'].sum().reset_index()
            fig_rules = px.bar(rules_pnl, x='rules_followed', y='pnl', color='rules_followed', title="PnL: Rules Followed vs Broken")
            col1.plotly_chart(fig_rules, use_container_width=True)
            sl_pnl = trades.groupby('proper_sl')['pnl'].mean().reset_index()
            fig_sl = px.bar(sl_pnl, x='proper_sl', y='pnl', color='proper_sl', title="Avg PnL: Proper SL vs No SL")
            col2.plotly_chart(fig_sl, use_container_width=True)

        with tab3:
            col1, col2 = st.columns(2)
            setup_perf = trades.groupby('setup')['pnl'].sum().sort_values(ascending=False).reset_index()
            fig_setup = px.bar(setup_perf, x='pnl', y='setup', orientation='h', title="PnL by Strategy", color='pnl')
            col1.plotly_chart(fig_setup, use_container_width=True)
            trend_perf = trades.groupby('trend')['pnl'].sum().reset_index()
            fig_trend = px.pie(trend_perf, values='pnl', names='trend', title="PnL Share by Trend Context")
            col2.plotly_chart(fig_trend, use_container_width=True)

        with tab4:
            col1, col2 = st.columns(2)
            session_perf = trades.groupby('session')['pnl'].sum().reset_index()
            fig_session = px.bar(session_perf, x='session', y='pnl', title="PnL by Session", color='pnl')
            col1.plotly_chart(fig_session, use_container_width=True)
            trades['weekday'] = trades['entry_date'].dt.day_name()
            days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            weekday_perf = trades.groupby('weekday')['pnl'].sum().reindex(days_order).fillna(0).reset_index()
            fig_weekday = px.line(weekday_perf, x='weekday', y='pnl', title="Performance by Weekday", markers=True)
            st.plotly_chart(fig_weekday, use_container_width=True)

        st.markdown("---")

        # EXPORT DATA SECTION
        with st.expander("📥 Export Trades to Excel"):
            st.markdown("#### Select Date Range to Export Data")
            ex_c1, ex_c2, ex_c3 = st.columns([2, 2, 1])
            
            min_date = trades['entry_date'].min().date() if not trades.empty else pd.Timestamp.now().date()
            max_date = trades['entry_date'].max().date() if not trades.empty else pd.Timestamp.now().date()
            
            start_date = ex_c1.date_input("Start Date", value=min_date, key="exp_start_date")
            end_date = ex_c2.date_input("End Date", value=max_date, key="exp_end_date")
            
            filtered_trades = trades[
                (trades['entry_date'].dt.date >= start_date) & 
                (trades['entry_date'].dt.date <= end_date)
            ]
            
            st.caption(f"Found **{len(filtered_trades)}** trade(s) in selected range.")
            
            if not filtered_trades.empty:
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    filtered_trades.to_excel(writer, index=False, sheet_name='Trades')
                
                ex_c3.markdown("<br>", unsafe_allow_html=True)
                ex_c3.download_button(
                    label="📥 Download Excel",
                    data=excel_buffer.getvalue(),
                    file_name=f"trades_{start_date}_to_{end_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("No trades found within the selected date range.")

        with st.expander("📄 View Detailed Trade Log"):
            st.dataframe(trades.sort_values(by='id', ascending=False))
            
    else:
        st.info("Waiting for data... Log your first trade in the sidebar!")
else:
    st.info("👈 You have no accounts yet. Add one in the sidebar!")
