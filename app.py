import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from database import add_asset, get_user_portfolio
from fetcher import (
    get_stock_price, 
    get_crypto_price, 
    get_historical_data, 
    calculate_portfolio_risk_metrics,
    run_monte_carlo,
    calculate_efficient_frontier
)

# 頁面配置
st.set_page_config(
    page_title="Quant Portfolio Tracker", 
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入 3D 質感、動態流光與暖橘主題 CSS
custom_css = """
<style>
    /* 1. 3D 立體與流光動畫定義 */
    @keyframes orangeFlow {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    @keyframes glowPulse {
        0% { box-shadow: 0 8px 20px rgba(255, 107, 0, 0.15), inset 0 1px 1px rgba(255,255,255,0.1); }
        50% { box-shadow: 0 8px 28px rgba(255, 107, 0, 0.35), inset 0 1px 1px rgba(255,255,255,0.2); }
        100% { box-shadow: 0 8px 20px rgba(255, 107, 0, 0.15), inset 0 1px 1px rgba(255,255,255,0.1); }
    }

    /* 2. 數據卡片 (Metric Card) 3D 浮雕與光流微邊框 */
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #1A1D26, #12141A);
        padding: 20px 24px;
        border-radius: 16px;
        border: 1px solid rgba(255, 107, 0, 0.3);
        animation: glowPulse 4s infinite ease-in-out;
        transform: translateY(-2px);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    
    [data-testid="stMetric"]:hover {
        transform: translateY(-6px);
        border-color: #FF6B00;
        box-shadow: 0 12px 30px rgba(255, 107, 0, 0.4);
    }
    
    [data-testid="stMetricValue"] {
        font-size: 2rem !important;
        font-weight: 800;
        background: linear-gradient(90deg, #FFFFFF, #FFB800);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    [data-testid="stMetricLabel"] {
        font-size: 1.05rem !important;
        font-weight: 600;
        color: #B0B7C3 !important;
    }

    /* 3. 頂部動態流光條 */
    .stAppViewMainViewContainer::before {
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 4px;
        background: linear-gradient(90deg, #FF3E00, #FF6B00, #FFB800, #FF3E00);
        background-size: 200% 200%;
        animation: orangeFlow 3s ease infinite;
        z-index: 9999;
    }

    /* 4. 側邊欄與介面邊界強化 */
    [data-testid="stSidebar"] {
        background-color: #12141A !important;
        border-right: 2px solid rgba(255, 107, 0, 0.25) !important;
        box-shadow: 5px 0 20px rgba(0,0,0,0.5);
    }

    /* 5. 3D 按鈕樣式 */
    .stButton > button {
        background: linear-gradient(135deg, #FF6B00, #D94800);
        color: white;
        font-weight: bold;
        border-radius: 10px;
        border: none;
        box-shadow: 0 4px 12px rgba(255, 107, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.3);
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 18px rgba(255, 107, 0, 0.5);
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# 頁面標題
st.markdown("""
<h1 style='display: flex; align-items: center; gap: 12px; margin-bottom: 20px;'>
    <span style='font-size: 2.2rem; filter: drop-shadow(0px 4px 8px rgba(255,107,0,0.6));'>⚡</span>
    個人化加密貨幣/股票量化儀表板
</h1>
""", unsafe_allow_html=True)

# --- 側邊欄：新增持倉表單 ---
st.sidebar.header("➕ 新增持倉紀錄")
user_id = st.sidebar.text_input("用戶 ID", value="demo_user")
asset_type = st.sidebar.selectbox("資產類別", ["stock", "crypto"], help="stock 代表美股或港股 (如 0700.HK), crypto 代表加密貨幣")
symbol = st.sidebar.text_input("代號", help="美股輸入 AAPL, TSLA；港股輸入 0700.HK；加密貨幣輸入 BTC, ETH (或 bitcoin)")
quantity = st.sidebar.number_input("持有數量", min_value=0.0001, value=1.0, format="%.4f")
buy_price = st.sidebar.number_input("買入均價 (USD)", min_value=0.0, value=100.0, format="%.2f")

if st.sidebar.button("加入投資組合"):
    if symbol:
        try:
            add_asset(user_id, symbol, asset_type, quantity, buy_price)
            st.sidebar.success(f"成功新增 {symbol.upper()}！")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"新增失敗: {e}")
    else:
        st.sidebar.warning("請輸入資產代號！")

# --- 主畫面：多功能 Tab 頁籤 ---
tab1, tab2, tab3 = st.tabs(["📊 持倉總覽與風險分析", "🎲 蒙地卡羅未來模擬", "📈 效率前緣資產最佳化"])

records = get_user_portfolio(user_id)

if records:
    df = pd.DataFrame(records)
    
    with st.spinner("正從金融 API 抓取最新即時價格..."):
        current_prices = []
        for _, row in df.iterrows():
            if row['asset_type'] == 'stock':
                price = get_stock_price(row['symbol'])
            else:
                price = get_crypto_price(row['symbol'])
            current_prices.append(price)

    df['current_price'] = current_prices
    df['total_cost'] = df['quantity'] * df['buy_price']
    df['current_value'] = df['quantity'] * df['current_price']
    df['pnl'] = df['current_value'] - df['total_cost']
    df['pnl_%'] = (df['pnl'] / df['total_cost']) * 100

    # 計算風險指標
    risk_metrics = calculate_portfolio_risk_metrics(df)

    # ==================== TAB 1: 持倉總覽與風險分析 ====================
    with tab1:
        st.header(f"📊 {user_id} 的投資組合總覽")

        # --- KPI 關鍵指標卡片 ---
        total_val = df['current_value'].sum()
        total_cost = df['total_cost'].sum()
        total_pnl = total_val - total_cost
        pnl_rate = (total_pnl / total_cost * 100) if total_cost > 0 else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("投資組合總價值", f"${total_val:,.2f}")
        col2.metric("總投入成本", f"${total_cost:,.2f}")
        col3.metric("未實現總盈虧", f"${total_pnl:,.2f}", delta=f"{pnl_rate:.2f}%")

        st.markdown("---")

        # --- 量化風險指標區塊 ---
        st.subheader("🛡️ 投資組合量化風險分析 (近 1 年數據估計)")

        if risk_metrics:
            r_col1, r_col2, r_col3, r_col4 = st.columns(4)
            r_col1.metric("夏普比率 (Sharpe Ratio)", f"{risk_metrics['sharpe_ratio']:.2f}", 
                            help="高於 1.0 代表風險調整後收益優異；高於 2.0 代表非常卓越")
            r_col2.metric("歷史最大回撤 (Max Drawdown)", f"{risk_metrics['max_drawdown']:.2f}%", 
                            help="過去一年從最高點跌到最低點的最大可能虧損百分比")
            r_col3.metric("年化波動率 (Annualized Volatility)", f"{risk_metrics['annualized_volatility']:.2f}%")
            r_col4.metric("預估年化報酬率", f"{risk_metrics['annualized_return']:.2f}%")
        else:
            st.info("數據不足，無法計算歷史風險指標。")

        st.markdown("---")

        # --- 圓餅圖與明細表格 ---
        chart_col, data_col = st.columns([1, 1])

        with chart_col:
            st.subheader("🍕 資產配置比例")
            fig = px.pie(df, values='current_value', names='symbol', hole=0.4, title="Asset Distribution (USD)")
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#F0F2F5'))
            st.plotly_chart(fig, use_container_width=True)

        with data_col:
            st.subheader("📋 持倉明細表格")
            display_df = df[['symbol', 'asset_type', 'quantity', 'buy_price', 'current_price', 'current_value', 'pnl', 'pnl_%']].copy()
            display_df.columns = ['代號', '類別', '數量', '買入均價', '現價', '當前總值', '盈虧(USD)', '報酬率(%)']
            st.dataframe(
                display_df.style.format({
                    '數量': '{:,.4f}', '買入均價': '${:,.2f}', '現價': '${:,.2f}',
                    '當前總值': '${:,.2f}', '盈虧(USD)': '${:,.2f}', '報酬率(%)': '{:+.2f}%'
                }),
                use_container_width=True
            )

        st.markdown("---")

        # --- 技術分析與 K 線圖區塊 ---
        st.subheader("📉 單一資產技術分析 (K線圖 & MA20 / MA60)")
        asset_list = df['symbol'].tolist()
        selected_symbol = st.selectbox("選擇要分析的資產：", asset_list)
        time_period = st.radio("選擇時間範圍：", ["1m", "3m", "6m", "1y"], index=2, horizontal=True)

        if selected_symbol:
            selected_row = df[df['symbol'] == selected_symbol].iloc[0]
            hist_df = get_historical_data(selected_symbol, selected_row['asset_type'], period=time_period)

            if not hist_df.empty:
                fig_tech = go.Figure()
                fig_tech.add_trace(go.Candlestick(
                    x=hist_df['Date'], open=hist_df['Open'], high=hist_df['High'],
                    low=hist_df['Low'], close=hist_df['Close'], name="K線 (Price)"
                ))
                fig_tech.add_trace(go.Scatter(x=hist_df['Date'], y=hist_df['MA20'], line=dict(color='#FFB800', width=1.5), name="MA20"))
                fig_tech.add_trace(go.Scatter(x=hist_df['Date'], y=hist_df['MA60'], line=dict(color='#00D1B2', width=1.5), name="MA60"))
                fig_tech.update_layout(
                    title=f"{selected_symbol.upper()} 歷史走勢與技術指標",
                    yaxis_title="價格 (USD)", xaxis_rangeslider_visible=False,
                    template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=500
                )
                st.plotly_chart(fig_tech, use_container_width=True)

    # ==================== TAB 2: 蒙地卡羅未來模擬 ====================
    with tab2:
        st.header("🎲 蒙地卡羅模擬（未來 252 交易日資產走勢）")
        
        if risk_metrics and "returns_df" in risk_metrics:
            returns_df = risk_metrics["returns_df"]
            weights = risk_metrics["weights"]
            current_total_val = df['current_value'].sum()

            mc_col1, mc_col2 = st.columns([1, 3])
            
            with mc_col1:
                sim_count = st.slider("模擬次數", min_value=100, max_value=2000, value=500, step=100)
                init_val = st.number_input("初始模擬金額 ($)", value=float(current_total_val), step=1000.0)
            
            sim_data, summary = run_monte_carlo(returns_df, weights, num_simulations=sim_count, initial_portfolio_value=init_val)

            with mc_col2:
                fig_mc = go.Figure()
                time_axis = np.arange(sim_data.shape[0])
                
                # 隨機繪製最多 100 條軌跡
                for i in range(min(sim_count, 100)):
                    fig_mc.add_trace(go.Scatter(x=time_axis, y=sim_data[:, i], mode='lines', line=dict(width=1, color='#FF6B00'), opacity=0.2, showlegend=False))
                
                fig_mc.update_layout(
                    title="Monte Carlo Asset Value Simulation Paths",
                    xaxis_title="Trading Days", yaxis_title="Portfolio Value ($)",
                    template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_mc, use_container_width=True)

            st.markdown("### 📊 模擬結果預測指標")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("預期資產均值", f"${summary['mean_final_value']:,.2f}")
            m2.metric("資產中位數", f"${summary['median_final_value']:,.2f}")
            m3.metric("95% 最佳情況 (Top 5%)", f"${summary['percentile_95']:,.2f}")
            m4.metric("95% 蒙地卡羅 VaR (風險值)", f"${summary['var_95']:,.2f}")
        else:
            st.info("數據不足，無法執行蒙地卡羅模擬。")

    # ==================== TAB 3: 效率前緣資產最佳化 ====================
    with tab3:
        st.header("📈 馬可維茲效率前緣 (Markowitz Efficient Frontier)")
        
        if risk_metrics and "returns_df" in risk_metrics and risk_metrics["returns_df"].shape[1] >= 2:
            returns_df = risk_metrics["returns_df"]
            ef_result = calculate_efficient_frontier(returns_df, num_portfolios=2000)

            if ef_result:
                df_sim = ef_result["simulated_portfolios"]
                max_s = ef_result["max_sharpe"]
                min_v = ef_result["min_volatility"]
                asset_names = ef_result["asset_names"]

                fig_ef = px.scatter(
                    df_sim, x="stdev", y="return", color="sharpe",
                    color_continuous_scale="Viridis",
                    labels={"stdev": "年化標準差 (風險)", "return": "年化預期報酬率", "sharpe": "夏普比率"},
                    title="Efficient Frontier Portfolio Optimization"
                )
                fig_ef.add_trace(go.Scatter(
                    x=[max_s['stdev']], y=[max_s['return']], mode='markers+text',
                    name='Max Sharpe', text=['⭐ Max Sharpe'], textposition="top center",
                    marker=dict(size=14, color='#FF6B00', symbol='star')
                ))
                fig_ef.add_trace(go.Scatter(
                    x=[min_v['stdev']], y=[min_v['return']], mode='markers+text',
                    name='Min Volatility', text=['🛡️ Min Volatility'], textposition="bottom center",
                    marker=dict(size=14, color='#00D1B2', symbol='diamond')
                ))
                fig_ef.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_ef, use_container_width=True)

                st.markdown("### ⚖️ 最佳化資產配置建議比率")
                alloc_df = pd.DataFrame({
                    "資產代碼": asset_names,
                    "Max Sharpe 建議權重": [f"{max_s[col]*100:.2f}%" for col in asset_names],
                    "Min Volatility 建議權重": [f"{min_v[col]*100:.2f}%" for col in asset_names]
                })
                st.dataframe(alloc_df, use_container_width=True)
        else:
            st.info("請確保投資組合中包含 **至少 2 種以上** 的不同資產，以計算效率前緣優化配置。")

else:
    st.info("👋 目前尚無持倉紀錄！請在左側選單輸入你的第一個資產。")