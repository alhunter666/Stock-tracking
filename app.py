import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="三桶投资组合仪表板",
    page_icon="💰",
    layout="wide"
)

# --- 2. 标题 ---
st.title("💰 我的三桶投资组合仪表板 (可交互版)")
st.caption("您可以直接在下方的表格中修改您的持仓、数量和成本。")

# --- 3. 实时价格获取 (带缓存) ---
# 缓存5分钟 (300秒)
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
        # st.warning(f"无法获取 {ticker} 的价格。")
        return 0

# --- 4. 初始化 Session State (关键！) ---
# Session State 用于在 Streamlit 重新运行时“记住”您的编辑。
# 我们只在第一次运行时初始化数据。

# 桶1 的初始数据
if 'df_b1' not in st.session_state:
    b1_data = {
        'ticker': ['AVGO', 'NVDA', 'META', 'VOO', 'QQQ'],
        'type': ['Stock', 'LEAP Call', 'Stock', 'ETF (待建)', 'ETF (待建)'],
        'quantity': [100.0, 1.0, 20.0, 0.0, 0.0],
        'total_cost': [16800.0, 4000.0, 6000.0, 0.0, 0.0], # 假设的成本，请您自行修改
        'notes': ['明星持仓', "Dec'27 $170 Call", '', '目标 $15-20k', '目标 $5-10k']
    }
    st.session_state.df_b1 = pd.DataFrame(b1_data)

# 桶2 的初始数据 (策略)
if 'df_b2' not in st.session_state:
    b2_data = {
        'strategy': ['Bull Put Spread (待建)', 'Sell Put (待建)', 'Sell Put (待建)'],
        'ticker': ['VST', 'SPY', 'AAPL'],
        'margin_used': [3000.0, 10000.0, 8000.0],
        'target_premium_monthly': [1000.0, 500.0, 400.0],
        'notes': ['优先级1', '优先级2', '优先级3']
    }
    st.session_state.df_b2 = pd.DataFrame(b2_data)

# 桶3 的初始数据
if 'df_b3' not in st.session_state:
    b3_data = {
        'ticker': ['AMZN', 'VST', 'TSLL', 'AVGO', 'VST', 'NVDA', 'SIVR', 'KSA', 'BMNR'],
        'type': ['Call', 'Call', 'Stock/ETF', 'Call', 'Nov Call', 'Nov Call', 'Call', 'Stock', 'Put'],
        'quantity': [3.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 50.0, 1.0], # 数量请自行修改
        'total_cost': [5000.0, 2000.0, 1000.0, 500.0, 200.0, 200.0, 50.0, 100.0, 500.0], # 成本请自行修改
        'notes': ['盈利中', '盈利中', '盈利中', '', '', '', '❌ 待清理', '❌ 待清理', '❓ 待评估']
    }
    st.session_state.df_b3 = pd.DataFrame(b3_data)


# --- 5. 数据处理和计算 (每次运行都会执行) ---

# 复制 session state 中的数据，以免在计算时被意外修改
df_b1_processed = st.session_state.df_b1.copy()
df_b2_processed = st.session_state.df_b2.copy()
df_b3_processed = st.session_state.df_b3.copy()

# --- 计算桶1和桶3的市值 ---
def calculate_market_value(df):
    # 仅为股票/ETF获取价格
    df['current_price'] = df.apply(
        lambda row: get_stock_price(row['ticker']) if row['type'] in ['Stock', 'ETF', 'Stock/ETF'] else 0,
        axis=1
    )
    # 计算市值
    df['market_value'] = df.apply(
        lambda row: row['quantity'] * row['current_price'] if row['type'] in ['Stock', 'ETF', 'Stock/ETF'] else row['total_cost'], # 简化：期权市值暂用成本估算
        axis=1
    )
    df['p_l'] = df['market_value'] - df['total_cost']
    return df

df_b1_processed = calculate_market_value(df_b1_processed)
df_b3_processed = calculate_market_value(df_b3_processed) # 期权市值被简化了

# --- 计算总览指标 ---
total_b1_value = df_b1_processed['market_value'].sum()
total_b3_value = df_b3_processed['market_value'].sum()
total_b2_margin = df_b2_processed['margin_used'].sum()
total_b2_income = df_b2_processed['target_premium_monthly'].sum()

total_assets = total_b1_value + total_b3_value
total_capital = 100000.0 # 您的总资金
cash_available = total_capital - total_b1_value - total_b3_value - total_b2_margin


# --- 6. 显示总览仪表板 ---
st.header("📊 投资组合总览")
col1, col2, col3, col4 = st.columns(4)
col1.metric("🪣 桶1 市值", f"${total_b1_value:,.2f}", f"{(total_b1_value/total_capital)*100:.1f}%")
col2.metric("🪣 桶3 市值", f"${total_b3_value:,.2f}", f"{(total_b3_value/total_capital)*100:.1f}%")
col3.metric("🪣 桶2 占用保证金", f"${total_b2_margin:,.2f}", f"{(total_b2_margin/total_capital)*100:.1f}%")
col4.metric("💵 剩余现金", f"${cash_available:,.2f}", f"{(cash_available/total_capital)*100:.1f}%")

st.divider()

# --- 7. 显示可交互的数据编辑器 ---

# 定义列配置 (使其更美观，并禁用自动计算的列)
common_column_config = {
    "total_cost": st.column_config.NumberColumn("总成本", format="$ %.2f"),
    "current_price": st.column_config.NumberColumn("现价", format="$ %.2f", disabled=True),
    "market_value": st.column_config.NumberColumn("市值", format="$ %.2f", disabled=True),
    "p_l": st.column_config.NumberColumn("浮动盈亏", format="$ %.2f", disabled=True),
    "quantity": st.column_config.NumberColumn("数量"),
}

# --- 桶1 编辑器 ---
st.header("🪣 桶1：长期持仓核心 (可编辑)")
edited_b1 = st.data_editor(
    df_b1_processed,
    num_rows="dynamic", # 允许添加和删除行
    column_config=common_column_config,
    use_container_width=True,
    key="editor_b1"
)

# --- 桶2 编辑器 ---
st.header("🪣 桶2：收入机器 (可编辑)")
st.caption("跟踪您的现金流策略、占用保证金和目标收入。")
edited_b2 = st.data_editor(
    df_b2_processed,
    num_rows="dynamic",
    column_config={
        "margin_used": st.column_config.NumberColumn("占用保证金", format="$ %.2f"),
        "target_premium_monthly": st.column_config.NumberColumn("月目标收入", format="$ %.2f"),
    },
    use_container_width=True,
    key="editor_b2"
)

# --- 桶3 编辑器 ---
st.header("🪣 桶3：投机交易 (可编辑)")
edited_b3 = st.data_editor(
    df_b3_processed,
    num_rows="dynamic",
    column_config=common_column_config,
    use_container_width=True,
    key="editor_b3"
)


# --- 8. 保存编辑 (关键！) ---
# 在脚本末尾，我们将编辑后的数据（*不*包含自动计算的列）保存回 Session State。
# 这就完成了“编辑 -> 保存 -> 重新计算 -> 显示”的循环。

st.session_state.df_b1 = edited_b1.drop(columns=['current_price', 'market_value', 'p_l'])
st.session_state.df_b2 = edited_b2
st.session_state.df_b3 = edited_b3.drop(columns=['current_price', 'market_value', 'p_l'])


# --- 9. 刷新按钮 ---
st.divider()
if st.button("🔄 手动刷新实时价格"):
    # 清除价格缓存并重新运行
    st.cache_resource.clear()
    st.rerun()

st.caption(f"价格最后更新于: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
