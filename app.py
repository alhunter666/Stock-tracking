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
st.caption("请在 '编辑表' 中修改持仓，'只读表' 将自动更新实时市值。")

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

# 桶1 的初始数据 (只包含可编辑的列)
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

# 桶3 的初始数据 (只包含可编辑的列)
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

# 定义计算函数
def calculate_market_value(df_input):
    df = df_input.copy()
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

# --- 6. 显示可交互的数据编辑器 ---
# (注意：我们先显示编辑器，*然后*才进行计算)

# --- 桶1 编辑器 ---
st.header("🪣 桶1：长期持仓核心 (在此编辑)")
edited_b1 = st.data_editor(
    st.session_state.df_b1, # 直接编辑 session state 中的原始数据
    num_rows="dynamic", # 允许添加和删除行
    column_config={
        "total_cost": st.column_config.NumberColumn("总成本", format="$ %.2f"),
        "quantity": st.column_config.NumberColumn("数量"),
    },
    use_container_width=True,
    key="editor_b1"
)
# *现在*保存编辑（这不会导致闪烁）
st.session_state.df_b1 = edited_b1
# *然后*计算处理过的数据
df_b1_processed = calculate_market_value(edited_b1)


# --- 桶2 编辑器 ---
st.header("🪣 桶2：收入机器 (在此编辑)")
edited_b2 = st.data_editor(
    st.session_state.df_b2,
    num_rows="dynamic",
    column_config={
        "margin_used": st.column_config.NumberColumn("占用保证金", format="$ %.2f"),
        "target_premium_monthly": st.column_config.NumberColumn("月目标收入", format="$ %.2f"),
    },
    use_container_width=True,
    key="editor_b2"
)
st.session_state.df_b2 = edited_b2
df_b2_processed = edited_b2 # 桶2 没有额外计算


# --- 桶3 编辑器 ---
st.header("🪣 桶3：投机交易 (在此编辑)")
edited_b3 = st.data_editor(
    st.session_state.df_b3, # 直接编辑 session state 中的原始数据
    num_rows="dynamic",
    column_config={
        "total_cost": st.column_config.NumberColumn("总成本", format="$ %.2f"),
        "quantity": st.column_config.NumberColumn("数量"),
    },
    use_container_width=True,
    key="editor_b3"
)
# *现在*保存编辑
st.session_state.df_b3 = edited_b3
# *然后*计算处理过的数据
df_b3_processed = calculate_market_value(edited_b3)


# --- 7. 计算总览指标 ---
total_b1_value = df_b1_processed['market_value'].sum()
total_b3_value = df_b3_processed['market_value'].sum()
total_b2_margin = df_b2_processed['margin_used'].sum()

total_capital = 100000.0 # 您的总资金
total_assets = total_b1_value + total_b3_value
cash_available = total_capital - total_b1_value - total_b3_value - total_b2_margin


# --- 8. 显示总览仪表板 ---
st.divider()
st.header("📊 投资组合总览 (实时)")
col1, col2, col3, col4 = st.columns(4)
col1.metric("🪣 桶1 市值", f"${total_b1_value:,.2f}", f"{(total_b1_value/total_capital)*100:.1f}%")
col2.metric("🪣 桶3 市值", f"${total_b3_value:,.2f}", f"{(total_b3_value/total_capital)*100:.1f}%")
col3.metric("🪣 桶2 占用保证金", f"${total_b2_margin:,.2f}", f"{(total_b2_margin/total_capital)*100:.1f}%")
col4.metric("💵 剩余现金", f"${cash_available:,.2f}", f"{(cash_available/total_capital)*100:.1f}%")
st.divider()

# --- 9. 显示带计算结果的只读表格 ---

st.caption("桶1 实时市值 (只读)")
st.dataframe(
    df_b1_processed,
    column_config={ # 确保这里也格式化了
        "total_cost": st.column_config.NumberColumn("总成本", format="$ %.2f"),
        "current_price": st.column_config.NumberColumn("现价", format="$ %.2f"),
        "market_value": st.column_config.NumberColumn("市值", format="$ %.2f"),
        "p_l": st.column_config.NumberColumn("浮动盈亏", format="$ %.2f"),
        "quantity": st.column_config.NumberColumn("数量"),
    },
    use_container_width=True,
    hide_index=True
)

st.caption("桶2 收入策略 (只读)")
st.dataframe(
    df_b2_processed,
    column_config={ # 确保这里也格式化了
        "margin_used": st.column_config.NumberColumn("占用保证金", format="$ %.2f"),
        "target_premium_monthly": st.column_config.NumberColumn("月目标收入", format="$ %.2f"),
    },
    use_container_width=True,
    hide_index=True
)

st.caption("桶3 实时市值 (只读)")
st.dataframe(
    df_b3_processed,
    column_config={ # 确保这里也格式化了
        "total_cost": st.column_config.NumberColumn("总成本", format="$ %.2f"),
        "current_price": st.column_config.NumberColumn("现价", format="$ %.2f"),
        "market_value": st.column_config.NumberColumn("市值", format="$ %.2f"),
        "p_l": st.column_config.NumberColumn("浮动盈亏", format="$ %.2f"),
        "quantity": st.column_config.NumberColumn("数量"),
    },
    use_container_width=True,
    hide_index=True
)

# --- 10. 刷新按钮 ---
st.divider()
if st.button("🔄 手动刷新实时价格"):
    # 清除价格缓存并重新运行
    st.cache_resource.clear()
    st.rerun()

st.caption(f"价格最后更新于: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
