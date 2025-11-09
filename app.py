import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="投资组合报告",
    page_icon="💚",
    layout="wide"
)

# --- 2. 标题 ---
st.title("🟢 当前投资组合")
st.caption("数据将从您的 Google Sheet 读取。编辑后，请在 '交易日志 & 编辑' 选项卡中点击 '保存'。")

# --- 3. Google Sheets 连接 ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"无法连接到 Google Sheets。请检查您的 secrets.toml 配置。错误: {e}")
    st.info("请严格按照 README.md 文件中的 '首次设置指南' 进行操作。")
    st.stop()

# --- 4. 实时价格获取 (带缓存) ---
@st.cache_resource(ttl=300)
def get_stock_price(ticker):
    """获取股票或ETF的实时价格"""
    if ticker in [None, "", "N/A"]:
        return 0
    try:
        stock = yf.Ticker(ticker)
        price = stock.fast_info.get('lastPrice', 0)
        if price == 0:
             price = stock.history(period="1d")['Close'].iloc[0]
        return price
    except Exception:
        return 0

# --- 5. 从 Google Sheets 加载数据 ---
def load_settings_from_gsheet():
    """🆕 从 Google Sheets 加载设置参数"""
    try:
        df_settings = conn.read(worksheet="settings", usecols=list(range(2)), ttl=600)   
        # 转换为字典
        settings = {}
        for _, row in df_settings.iterrows():
            try:  
                param_name = str(row.iloc[0])   
                param_value = row.iloc[1]
                settings[param_name] = param_value
            except Exception:   
                continue  
        return settings
    except Exception as e:
        st.warning(f"无法读取设置表: {e}. 将使用默认设置。")
        return {
            'total_capital': 100000.0,
            'monthly_income_target': 1500.0,
            'stop_loss_threshold': -20.0,
            'dte_warning_threshold': 21.0
        }

def load_data_from_gsheet():
    """从 Google Sheets 加载三个桶的数据"""
    try:
        df_b1 = conn.read(worksheet="bucket1", usecols=list(range(6)), ttl=600)
        # 桶2现在有9列 (添加了 estimated_cost_to_close)
        df_b2 = conn.read(worksheet="bucket2", usecols=list(range(9)), ttl=600)
        df_b3 = conn.read(worksheet="bucket3", usecols=list(range(6)), ttl=600)

        # 确保必要列存在
        if 'manual_market_value' not in df_b1.columns:
            df_b1['manual_market_value'] = 0.0
        if 'manual_market_value' not in df_b3.columns:
            df_b3['manual_market_value'] = 0.0
        
        # 桶2的新列
        if 'status' not in df_b2.columns:
            df_b2['status'] = "Open"
        if 'expiration_date' not in df_b2.columns:
            df_b2['expiration_date'] = None
        if 'premium_received' not in df_b2.columns:
            df_b2['premium_received'] = 0.0
        if 'cost_to_close' not in df_b2.columns:
            df_b2['cost_to_close'] = 0.0
        # 🆕 新增列：估计平仓成本（用于计算浮动盈亏）
        if 'estimated_cost_to_close' not in df_b2.columns:
            df_b2['estimated_cost_to_close'] = 0.0

        return df_b1, df_b2, df_b3
    except Exception as e:
        st.warning(f"无法从 Google Sheets 读取数据: {e}")
        st.info("将使用默认的初始数据。")
        return create_default_dfs()

def create_default_dfs():
    """创建默认的 DataFrame 结构"""
    df_b1 = pd.DataFrame({
        'ticker': ['AVGO', 'NVDA'], 
        'type': ['Stock', 'LEAP Call'], 
        'quantity': [100.0, 1.0],
        'total_cost': [16800.0, 4000.0], 
        'notes': ['明星持仓', "Dec'27 $170 Call"],
        'manual_market_value': [0.0, 4000.0]
    })
    df_b2 = pd.DataFrame({
        'status': ['Open', 'Closed'],
        'strategy': ['Bull Put Spread', 'Sell Put'], 
        'ticker': ['VST', 'SPY'], 
        'expiration_date': [pd.to_datetime('2025-12-05'), pd.to_datetime('2025-10-31')],
        'margin_used': [3000.0, 10000.0],
        'premium_received': [1000.0, 500.0],
        'cost_to_close': [0.0, 50.0],
        'estimated_cost_to_close': [0.0, 0.0], # 🆕
        'notes': ['优先级1', '已实现利润']
    })
    df_b3 = pd.DataFrame({
        'ticker': ['AMZN'], 
        'type': ['Call'], 
        'quantity': [3.0],
        'total_cost': [5000.0], 
        'notes': ['盈利中'], 
        'manual_market_value': [9288.0]
    })
    return df_b1, df_b2, df_b3

# --- 6. 数据处理和计算 (桶1和桶3) ---
def calculate_market_value(df_input):
    df = df_input.copy()
    
    # 确保列存在
    if 'manual_market_value' not in df.columns:
        df['manual_market_value'] = 0.0
    
    # 转换为数字
    df['manual_market_value'] = pd.to_numeric(df['manual_market_value'], errors='coerce').fillna(0.0)
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0.0)
    df['total_cost'] = pd.to_numeric(df['total_cost'], errors='coerce').fillna(0.0)

    # 获取股票价格
    df['current_price'] = df.apply(
        lambda row: get_stock_price(row['ticker']) if row['type'] in ['Stock', 'ETF', 'Stock/ETF'] else 0,
        axis=1
    )
    
    # 计算市值
    def get_mv(row):
        if row['manual_market_value'] > 0:
            return row['manual_market_value']
        if row['type'] in ['Stock', 'ETF', 'Stock/ETF']:
            return row['quantity'] * row['current_price']
        return row['total_cost']

    df['market_value'] = df.apply(get_mv, axis=1)
    df['p_l'] = df['market_value'] - df['total_cost']
    df['p_l_pct'] = (df['p_l'] / df['total_cost'] * 100).round(2)
    
    return df

# --- 7. 加载数据到 Session State ---
if 'loaded_data' not in st.session_state:
    # 🆕 加载设置
    st.session_state.settings = load_settings_from_gsheet()
    # 加载桶数据
    df_b1_loaded, df_b2_loaded, df_b3_loaded = load_data_from_gsheet()
    
    # ------------------- 关键修复 V3.1 -------------------
    # 立即清理桶2的数据类型，防止 data_editor 因类型不匹配而崩溃
    # （桶1和桶3在 calculate_market_value 函数中已有清理）
    try:
        df_b2_loaded['margin_used'] = pd.to_numeric(df_b2_loaded['margin_used'], errors='coerce').fillna(0.0)
        df_b2_loaded['premium_received'] = pd.to_numeric(df_b2_loaded['premium_received'], errors='coerce').fillna(0.0)
        df_b2_loaded['cost_to_close'] = pd.to_numeric(df_b2_loaded['cost_to_close'], errors='coerce').fillna(0.0)
        df_b2_loaded['estimated_cost_to_close'] = pd.to_numeric(df_b2_loaded['estimated_cost_to_close'], errors='coerce').fillna(0.0)
        # 强制将 expiration_date 转换为日期时间对象，无效值（如空单元格）将变为 NaT (Not a Time)
        df_b2_loaded['expiration_date'] = pd.to_datetime(df_b2_loaded['expiration_date'], errors='coerce')
    except Exception as e:
        st.error(f"加载桶2数据时类型转换失败: {e}")
        st.info("请检查您 Google Sheet 'bucket2' 工作表中的数字和日期列。")
    # ----------------- END FIX V3.1 -----------------

    st.session_state.df_b1 = df_b1_loaded
    st.session_state.df_b2 = df_b2_loaded # ⬅️ 现在是清理过的数据
    st.session_state.df_b3 = df_b3_loaded
    st.session_state.loaded_data = True

# --- 8. 创建选项卡 ---
tab_dash, tab_journal, tab_settings = st.tabs(["当前持仓", "交易日志", "⚙️ 设置"])

# --- 9. 交易日志 & 编辑 选项卡 ---
with tab_journal:
    st.header("❇️桶1：长期持仓核心 (在此编辑)")
    st.info("💡 对于期权 (Call/Put)，请在 'manual_market_value' 列手动填入当前市值。")
    edited_b1 = st.data_editor(
        st.session_state.df_b1,
        num_rows="dynamic",
        column_config={
            "total_cost": st.column_config.NumberColumn("总成本", format="$ %.2f"),
            "quantity": st.column_config.NumberColumn("数量"),
            "manual_market_value": st.column_config.NumberColumn("手动市值(期权)", format="$ %.2f", help="期权请手动输入当前市值")
        },
        width="stretch",
        key="editor_b1"
    )

    st.header("🍀💵桶2：收入机器 - 交易日志 (在此编辑)")
    st.caption("例如：你卖了Bull Put Spread收$1000，现在市场价格是$600，则填入600。浮动盈亏 = 1000 - 600 = +$400")
    
    edited_b2 = st.data_editor(
        st.session_state.df_b2,
        num_rows="dynamic",
        column_config={
            "status": st.column_config.SelectboxColumn("状态", options=["Open", "Closed"]),
            "expiration_date": st.column_config.DateColumn("到期日", format="YYYY-MM-DD"),
            "margin_used": st.column_config.NumberColumn("占用保证金", format="$ %.2f"),
            "premium_received": st.column_config.NumberColumn("收到权利金", format="$ %.2f"),
            "cost_to_close": st.column_config.NumberColumn("实际平仓成本", format="$ %.2f", help="只有Closed状态才填"),
            "estimated_cost_to_close": st.column_config.NumberColumn("估计平仓成本", format="$ %.2f", help="Open状态填入当前市场价格，用于计算浮动盈亏"),
        },
        width="stretch",
        key="editor_b2"
    )

    st.header("🤑桶3：投机交易 (在此编辑)")
    st.info("💡 对于期权 (Call/Put)，请在 'manual_market_value' 列手动填入当前市值。")
    edited_b3 = st.data_editor(
        st.session_state.df_b3,
        num_rows="dynamic",
        column_config={
            "total_cost": st.column_config.NumberColumn("总成本", format="$ %.2f"),
            "quantity": st.column_config.NumberColumn("数量"),
            "manual_market_value": st.column_config.NumberColumn("手动市值(期权)", format="$ %.2f", help="期权请手动输入当前市值")
        },
        width="stretch",
        key="editor_b3"
    )

    # --- 保存按钮 ---
    st.divider()
    if st.button("💾 保存全部更改到 Google Sheets", type="primary"):
        with st.spinner("正在保存..."):
            try:
                cols_b1 = ['ticker', 'type', 'quantity', 'total_cost', 'notes', 'manual_market_value']
                cols_b2 = ['status', 'strategy', 'ticker', 'expiration_date', 'margin_used', 'premium_received', 'cost_to_close', 'estimated_cost_to_close', 'notes']
                cols_b3 = ['ticker', 'type', 'quantity', 'total_cost', 'notes', 'manual_market_value']
                
                df_to_save_b1 = edited_b1.reindex(columns=cols_b1, fill_value=0.0)
                df_to_save_b2 = edited_b2.reindex(columns=cols_b2, fill_value='')
                df_to_save_b3 = edited_b3.reindex(columns=cols_b3, fill_value=0.0)

                conn.update(worksheet="bucket1", data=df_to_save_b1)
                conn.update(worksheet="bucket2", data=df_to_save_b2)
                conn.update(worksheet="bucket3", data=df_to_save_b3)
                
                st.session_state.df_b1 = edited_b1
                st.session_state.df_b2 = edited_b2
                st.session_state.df_b3 = edited_b3
                
                st.success("✅ 保存成功！数据已永久保存在您的 Google Sheet 中。")
                st.balloons()
            except Exception as e:
                st.error(f"保存失败: {e}")

# --- 10. 实时计算 ---
df_b1_processed = calculate_market_value(edited_b1)
df_b3_processed = calculate_market_value(edited_b3)

# --- 🆕 改进的桶2计算（包含浮动盈亏）---
df_b2_processed = edited_b2.copy()
try:
    # 转换为数字
    df_b2_processed['margin_used'] = pd.to_numeric(df_b2_processed['margin_used'], errors='coerce').fillna(0.0)
    df_b2_processed['premium_received'] = pd.to_numeric(df_b2_processed['premium_received'], errors='coerce').fillna(0.0)
    df_b2_processed['cost_to_close'] = pd.to_numeric(df_b2_processed['cost_to_close'], errors='coerce').fillna(0.0)
    df_b2_processed['estimated_cost_to_close'] = pd.to_numeric(df_b2_processed['estimated_cost_to_close'], errors='coerce').fillna(0.0)

    # DTE 计算
    today = pd.to_datetime(datetime.now().date())
    df_b2_processed['expiration_date'] = pd.to_datetime(df_b2_processed['expiration_date'], errors='coerce')
    df_b2_processed['days_to_expiration'] = (df_b2_processed['expiration_date'] - today).dt.days
    
    # 🆕 计算盈亏
    # Closed: 已实现盈亏 = 收到的 - 实际平仓成本
    # Open: 浮动盈亏 = 收到的 - 估计平仓成本
    def calc_pl(row):
        if row['status'] == 'Closed':
            return row['premium_received'] - row['cost_to_close']
        else:  # Open
            return row['premium_received'] - row['estimated_cost_to_close']
    
    df_b2_processed['p_l'] = df_b2_processed.apply(calc_pl, axis=1)
    
    # 分离 Open 和 Closed
    open_b2 = df_b2_processed[df_b2_processed['status'] == 'Open'].copy()
    closed_b2 = df_b2_processed[df_b2_processed['status'] == 'Closed'].copy()
    
    # 总览指标
    total_b2_margin = open_b2['margin_used'].sum()
    total_b2_realized_income = closed_b2['p_l'].sum()  # 已实现
    total_b2_unrealized_pl = open_b2['p_l'].sum()  # 🆕 浮动盈亏
    
    # 🆕 桶2总盈亏
    total_b2_pl = total_b2_realized_income + total_b2_unrealized_pl

except Exception as e:
    st.error(f"处理桶2数据时出错: {e}")
    total_b2_margin = 0.0
    total_b2_realized_income = 0.0
    total_b2_unrealized_pl = 0.0
    total_b2_pl = 0.0
    open_b2 = pd.DataFrame(columns=df_b2_processed.columns)
    closed_b2 = pd.DataFrame(columns=df_b2_processed.columns)

# --- 🆕 整体计算 ---
# 🆕 从设置表读取参数
total_capital = float(st.session_state.settings.get('total_capital', 100000.0))
monthly_target = float(st.session_state.settings.get('monthly_income_target', 1500.0))
stop_loss_threshold = float(st.session_state.settings.get('stop_loss_threshold', -20.0))
dte_warning_threshold = int(st.session_state.settings.get('dte_warning_threshold', 21))

total_b1_value = df_b1_processed['market_value'].sum()
total_b1_cost = df_b1_processed['total_cost'].sum()
total_b1_pl = df_b1_processed['p_l'].sum()

total_b3_value = df_b3_processed['market_value'].sum()
total_b3_cost = df_b3_processed['total_cost'].sum()
total_b3_pl = df_b3_processed['p_l'].sum()

# 总投资和总市值
total_invested = total_b1_cost + total_b3_cost + total_b2_margin
total_portfolio_value = total_b1_value + total_b3_value + total_b2_margin + total_b2_unrealized_pl
cash_available = total_capital - total_invested

# 🆕 整体盈亏和回报率
total_pl = total_b1_pl + total_b2_pl + total_b3_pl
total_return_pct = (total_pl / total_invested * 100) if total_invested > 0 else 0

# --- 11. 仪表板 选项卡 ---
with tab_dash:
    st.header("📊 投资组合总览")
    st.caption(f"最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 🆕 改进的指标面板
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "💰 总投资",
            f"${total_invested:,.0f}",
            f"{(total_invested/total_capital)*100:.1f}% of capital"
        )
        st.metric(
            "📈 总盈亏",
            f"${total_pl:,.0f}",
            f"{total_return_pct:.1f}%"
        )
    
    with col2:
        st.metric(
            "🪣 桶1 市值",
            f"${total_b1_value:,.0f}",
            f"P/L: ${total_b1_pl:,.0f}"
        )
        st.metric(
            "🪣 桶3 市值",
            f"${total_b3_value:,.0f}",
            f"P/L: ${total_b3_pl:,.0f}"
        )
    
    with col3:
        st.metric(
            "🪣 桶2 占用保证金",
            f"${total_b2_margin:,.0f}",
            f"{(total_b2_margin/total_capital)*100:.1f}%"
        )
        st.metric(
            "💵 剩余现金",
            f"${cash_available:,.0f}",
            f"{(cash_available/total_capital)*100:.1f}%"
        )
    
    with col4:
        st.metric(
            "✅ 桶2 已实现收入",
            f"${total_b2_realized_income:,.0f}",
            "Closed trades"
        )
        st.metric(
            "⏳ 桶2 浮动盈亏",
            f"${total_b2_unrealized_pl:,.0f}",
            "Open positions"
        )
    
    st.divider()
    
    # 🆕 桶2月收入目标进度
    st.subheader("🎯 桶2 月收入目标")
    current_month_income = total_b2_pl  # 简化版：用总盈亏作为本月收入
    progress = min(current_month_income / monthly_target, 1.0) if monthly_target > 0 else 0
    
    col_prog1, col_prog2 = st.columns([3, 1])
    with col_prog1:
        st.progress(progress, text=f"进度: ${current_month_income:.0f} / ${monthly_target:.0f}")
    with col_prog2:
        st.metric("完成度", f"{progress*100:.0f}%")
    
    st.caption(f"💡 提示: 在 Google Sheet 的'设置'工作表中修改月收入目标 (当前: ${monthly_target:.0f})")
    
    st.divider()

    # --- 桶1详情 ---
    st.subheader("🪣 桶1：长期持仓核心")
    st.dataframe(
        df_b1_processed,
        column_config={
            "total_cost": st.column_config.NumberColumn("总成本", format="$ %.2f"),
            "current_price": st.column_config.NumberColumn("现价", format="$ %.2f"),
            "manual_market_value": st.column_config.NumberColumn("手动市值", format="$ %.2f"),
            "market_value": st.column_config.NumberColumn("市值", format="$ %.2f"),
            "p_l": st.column_config.NumberColumn("盈亏", format="$ %.2f"),
            "p_l_pct": st.column_config.NumberColumn("盈亏%", format="%.2f%%"),
            "quantity": st.column_config.NumberColumn("数量"),
        },
        width="stretch",
        hide_index=True
    )

    # --- 桶2 Open持仓 ---
    st.subheader("🪣 桶2：当前持仓 (Open)")
    st.caption("💡 '浮动盈亏' = 收到权利金 - 估计平仓成本")
    
    # 🆕 添加DTE警告
    if not open_b2.empty:
        dte_warning = open_b2[open_b2['days_to_expiration'] < dte_warning_threshold]
        if not dte_warning.empty:
            st.warning(f"⚠️ 有 {len(dte_warning)} 个持仓的DTE < {dte_warning_threshold}天，请注意管理！")
    
    st.dataframe(
        open_b2,
        column_config={
            "status": st.column_config.TextColumn("状态"),
            "expiration_date": st.column_config.DateColumn("到期日", format="YYYY-MM-DD"),
            "days_to_expiration": st.column_config.NumberColumn("DTE", format="%d"),
            "margin_used": st.column_config.NumberColumn("保证金", format="$ %.2f"),
            "premium_received": st.column_config.NumberColumn("收到权利金", format="$ %.2f"),
            "estimated_cost_to_close": st.column_config.NumberColumn("估计平仓成本", format="$ %.2f"),
            "p_l": st.column_config.NumberColumn("浮动盈亏", format="$ %.2f"),
        },
        column_order=("status", "strategy", "ticker", "expiration_date", "days_to_expiration", "margin_used", "premium_received", "estimated_cost_to_close", "p_l", "notes"),
        width="stretch",
        hide_index=True
    )

    # --- 桶3详情 ---
    st.subheader("🪣 桶3：投机交易")
    
    # 🆕 添加止损警告
    if not df_b3_processed.empty:
        loss_warning = df_b3_processed[df_b3_processed['p_l_pct'] < stop_loss_threshold]
        if not loss_warning.empty:
            st.error(f"🚨 有 {len(loss_warning)} 个持仓亏损 > {abs(stop_loss_threshold):.0f}%，建议考虑止损！")
    
    st.dataframe(
        df_b3_processed,
        column_config={
            "total_cost": st.column_config.NumberColumn("总成本", format="$ %.2f"),
            "current_price": st.column_config.NumberColumn("现价", format="$ %.2f"),
            "manual_market_value": st.column_config.NumberColumn("手动市值", format="$ %.2f"),
            "market_value": st.column_config.NumberColumn("市值", format="$ %.2f"),
            "p_l": st.column_config.NumberColumn("盈亏", format="$ %.2f"),
            "p_l_pct": st.column_config.NumberColumn("盈亏%", format="%.2f%%"),
            "quantity": st.column_config.NumberColumn("数量"),
        },
        width="stretch",
        hide_index=True
    )

# --- 12. 在交易日志选项卡中显示已平仓记录 ---
with tab_journal:
    st.divider()
    st.header("🪣 桶2：已平仓记录 (复盘)")
    st.dataframe(
        closed_b2,
        column_config={
            "status": st.column_config.TextColumn("状态"),
            "expiration_date": st.column_config.DateColumn("到期日", format="YYYY-MM-DD"),
            "premium_received": st.column_config.NumberColumn("收到权利金", format="$ %.2f"),
            "cost_to_close": st.column_config.NumberColumn("平仓成本", format="$ %.2f"),
            "p_l": st.column_config.NumberColumn("已实现利润", format="$ %.2f"),
        },
        column_order=("status", "strategy", "ticker", "expiration_date", "premium_received", "cost_to_close", "p_l", "notes"),
        width="stretch",
        hide_index=True
    )
    
    # 🆕 已平仓交易统计
    if not closed_b2.empty:
        st.caption("📊 已平仓交易统计")
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        col_stat1.metric("总交易数", len(closed_b2))
        col_stat2.metric("总已实现收入", f"${closed_b2['p_l'].sum():,.2f}")
        winning_trades = len(closed_b2[closed_b2['p_l'] > 0])
        win_rate = (winning_trades / len(closed_b2) * 100) if len(closed_b2) > 0 else 0
        col_stat3.metric("胜率", f"{win_rate:.0f}%")

# --- 13. 刷新按钮 ---
st.divider()
col_refresh1, col_refresh2 = st.columns([1, 4])
with col_refresh1:
    if st.button("🔄 刷新价格", type="secondary"):
        st.cache_resource.clear()
        st.rerun()
with col_refresh2:
    st.caption(f"💡 提示：股票价格每5分钟自动更新。期权价格需要手动在'交易日志'中更新。")

# --- 🆕 14. 设置选项卡 ---
with tab_settings:
    st.header("⚙️ 投资组合设置")
    st.info("💡 在这里修改您的投资组合参数。这些设置会保存到 Google Sheet，不会因为代码更新而丢失。")
    
    # 创建设置DataFrame
    settings_data = {
        '参数名称': ['total_capital', 'monthly_income_target', 'stop_loss_threshold', 'dte_warning_threshold'],
        '当前值': [
            st.session_state.settings.get('total_capital', 100000.0),
            st.session_state.settings.get('monthly_income_target', 1500.0),
            st.session_state.settings.get('stop_loss_threshold', -20.0),
            st.session_state.settings.get('dte_warning_threshold', 21)
        ],
        '说明': [
            '总投资资金（美元）',
            '桶2月收入目标（美元）',
            '桶3止损阈值（百分比，负数）',
            '桶2到期日警告天数'
        ]
    }
    df_settings = pd.DataFrame(settings_data)
    
    st.subheader("📝 编辑设置参数")
    st.caption("修改下面的值，然后点击'保存设置'按钮")
    
    edited_settings = st.data_editor(
        df_settings,
        column_config={
            "参数名称": st.column_config.TextColumn("参数名称", disabled=True),
            "当前值": st.column_config.NumberColumn("当前值", format="%.2f"),
            "说明": st.column_config.TextColumn("说明", disabled=True)
        },
        width="stretch",
        hide_index=True,
        key="settings_editor"
    )
    
    st.divider()
    
    col_save, col_explain = st.columns([1, 3])
    
    with col_save:
        if st.button("💾 保存设置", type="primary"):
            try:
                # 准备保存的数据
                settings_to_save = pd.DataFrame({
                    'parameter_name': edited_settings['parameter_name'],
                    'value': edited_settings['value']
                })
                
                # 保存到Google Sheet
                conn.update(worksheet="setting", data=settings_to_save)
                
                # 更新session state
                for _, row in edited_settings.iterrows():
                    param_name = row['参数名称']
                    param_value = row['当前值']
                    st.session_state.settings[param_name] = param_value
                
                st.success("✅ 设置已保存！")
                st.balloons()
                st.rerun()  # 重新加载以应用新设置
                
            except Exception as e:
                st.error(f"保存设置失败: {e}")
    
    with col_explain:
        st.caption("""
        **参数说明：**
        - **total_capital**: 您的总投资金额，增加资金时修改这个值
        - **monthly_income_target**: 桶2的月收入目标，用于显示进度条
        - **stop_loss_threshold**: 桶3持仓亏损超过这个百分比会显示警告（负数，如-20表示20%）
        - **dte_warning_threshold**: 桶2持仓剩余天数少于这个值会显示警告
        """)
    
    st.divider()
    st.subheader("📊 当前设置总览")
    
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    col_s1.metric("💰 总资金", f"${total_capital:,.0f}")
    col_s2.metric("🎯 月目标", f"${monthly_target:,.0f}")
    col_s3.metric("🛑 止损线", f"{stop_loss_threshold:.0f}%")
    col_s4.metric("⏰ DTE警告", f"{dte_warning_threshold} 天")

# --- 15. 页脚说明 ---
st.divider()
st.caption("💡 **使用提示**: 所有数据保存在您的 Google Sheet 中。即使更新代码，数据也不会丢失。")
