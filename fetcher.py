import yfinance as yf
import requests
import pandas as pd
import numpy as np

# 常用加密貨幣代號映射表 (CoinGecko ID -> yfinance Ticker)
CRYPTO_MAP = {
    "bitcoin": "BTC-USD",
    "btc": "BTC-USD",
    "ethereum": "ETH-USD",
    "eth": "ETH-USD",
    "solana": "SOL-USD",
    "sol": "SOL-USD",
    "cardano": "ADA-USD",
    "ripple": "XRP-USD",
    "dogecoin": "DOGE-USD"
}

def get_stock_price(symbol: str) -> float:
    """取得股票即時價格 (支援美股與港股如 0700.HK)"""
    try:
        clean_symbol = symbol.strip().upper()
        ticker = yf.Ticker(clean_symbol)
        data = ticker.history(period="1d")
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except Exception as e:
        print(f"Error fetching stock {symbol}: {e}")
    return 0.0

def get_crypto_price(crypto_id: str) -> float:
    """取得加密貨幣即時價格 (CoinGecko API)"""
    try:
        clean_id = crypto_id.lower().strip()
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={clean_id}&vs_currencies=usd"
        res = requests.get(url, timeout=5).json()
        if clean_id in res:
            return float(res[clean_id]['usd'])
    except Exception as e:
        print(f"Error fetching crypto {crypto_id}: {e}")
    return 0.0

def get_historical_data(symbol: str, asset_type: str, period: str = "1y") -> pd.DataFrame:
    """
    抓取歷史價格數據，並進行日期格式正規化
    """
    try:
        clean_symbol = symbol.strip()

        if asset_type == 'stock':
            ticker_symbol = clean_symbol.upper()
        else:
            lower_symbol = clean_symbol.lower()
            if lower_symbol in CRYPTO_MAP:
                ticker_symbol = CRYPTO_MAP[lower_symbol]
            elif not lower_symbol.endswith("-usd"):
                ticker_symbol = f"{clean_symbol.upper()}-USD"
            else:
                ticker_symbol = clean_symbol.upper()

        period_map = {"1m": "1mo", "3m": "3mo", "6m": "6mo", "1y": "1y"}
        yf_period = period_map.get(period, "1y")

        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=yf_period)

        if not df.empty:
            df = df.reset_index()
            # 強制將 Date 轉換為不可帶時區的只含年月日的格式 (YYYY-MM-DD)
            df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None).dt.floor('D')
            df['MA20'] = df['Close'].rolling(window=20, min_periods=1).mean()
            df['MA60'] = df['Close'].rolling(window=60, min_periods=1).mean()
            return df

    except Exception as e:
        print(f"Error fetching historical data for {symbol}: {e}")
    
    return pd.DataFrame()

def get_portfolio_returns_df(portfolio_df: pd.DataFrame, period: str = "1y") -> pd.DataFrame:
    """
    對齊並整合投資組合中所有資產的歷史每日百分比報酬率
    修復股市與加密貨幣日期不一致導致 dropna() 後變成空資料的問題
    """
    prices_dict = {}
    
    for _, row in portfolio_df.iterrows():
        symbol = row['symbol']
        asset_type = row['asset_type']
        
        hist_df = get_historical_data(symbol, asset_type, period=period)
        if not hist_df.empty and 'Close' in hist_df.columns:
            # 建立 Date -> Close 價格序列
            series = hist_df.set_index('Date')['Close']
            # 去除重複日期
            series = series[~series.index.duplicated(keep='first')]
            prices_dict[symbol] = series

    if not prices_dict:
        return pd.DataFrame()

    # 合併所有資產價格 DataFrame
    combined_prices = pd.DataFrame(prices_dict)
    
    # 前向填補（解決休市日或加密貨幣/股市日期不對齊問題）
    combined_prices = combined_prices.ffill().bfill()
    
    # 計算日報酬率
    returns_df = combined_prices.pct_change().dropna()
    
    return returns_df

def calculate_portfolio_risk_metrics(portfolio_df: pd.DataFrame, risk_free_rate: float = 0.02) -> dict:
    """
    計算投資組合量化風險指標
    """
    try:
        returns_df = get_portfolio_returns_df(portfolio_df, period="1y")
        
        if returns_df.empty or len(returns_df) < 5:
            return {}

        total_value = portfolio_df['current_value'].sum()
        if total_value == 0:
            return {}

        # 匹配有效報酬率欄位的權重
        weights = []
        valid_symbols = returns_df.columns.tolist()
        
        for symbol in valid_symbols:
            val = portfolio_df[portfolio_df['symbol'] == symbol]['current_value'].values[0]
            weights.append(val / total_value)

        weights = np.array(weights)
        # 重新歸一化權重（以防有部分標的沒抓到歷史數據）
        weights = weights / np.sum(weights)

        portfolio_daily_return = returns_df.dot(weights)

        mean_daily_return = portfolio_daily_return.mean()
        annualized_return = mean_daily_return * 252
        
        daily_volatility = portfolio_daily_return.std()
        annualized_volatility = daily_volatility * np.sqrt(252)

        sharpe_ratio = (annualized_return - risk_free_rate) / annualized_volatility if annualized_volatility > 0 else 0

        cum_returns = (1 + portfolio_daily_return).cumprod()
        peak = cum_returns.cummax()
        drawdown = (cum_returns - peak) / peak
        max_drawdown = drawdown.min()

        return {
            "annualized_return": annualized_return * 100,
            "annualized_volatility": annualized_volatility * 100,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown * 100,
            "returns_df": returns_df,
            "weights": weights
        }

    except Exception as e:
        print(f"Error calculating risk metrics: {e}")
        return {}

def run_monte_carlo(returns_df: pd.DataFrame, weights: np.ndarray, num_simulations: int = 500, time_horizon: int = 252, initial_portfolio_value: float = 100000.0):
    """
    執行蒙地卡羅模擬 (Monte Carlo Simulation)
    """
    if returns_df.empty or len(weights) == 0:
        return None, None

    portfolio_mean = np.sum(returns_df.mean() * weights)
    cov_matrix = returns_df.cov()
    portfolio_stdev = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

    simulation_results = np.zeros((time_horizon, num_simulations))
    simulation_results[0] = initial_portfolio_value

    for t in range(1, time_horizon):
        random_shocks = np.random.normal(0, 1, num_simulations)
        drift = (portfolio_mean - 0.5 * (portfolio_stdev ** 2))
        diffusion = portfolio_stdev * random_shocks
        simulation_results[t] = simulation_results[t - 1] * np.exp(drift + diffusion)

    final_values = simulation_results[-1, :]
    var_95 = initial_portfolio_value - np.percentile(final_values, 5)

    summary_stats = {
        "mean_final_value": np.mean(final_values),
        "median_final_value": np.median(final_values),
        "percentile_5": np.percentile(final_values, 5),
        "percentile_95": np.percentile(final_values, 95),
        "var_95": var_95
    }

    return simulation_results, summary_stats

def calculate_efficient_frontier(returns_df: pd.DataFrame, num_portfolios: int = 2000, risk_free_rate: float = 0.02):
    """
    計算 Markowitz 效率前緣與最佳資產配置權重
    """
    if returns_df.empty or returns_df.shape[1] < 2:
        return None

    mean_returns = returns_df.mean() * 252
    cov_matrix = returns_df.cov() * 252
    num_assets = len(mean_returns)

    results = np.zeros((3 + num_assets, num_portfolios))
    
    for i in range(num_portfolios):
        weights = np.random.random(num_assets)
        weights /= np.sum(weights)

        portfolio_return = np.sum(mean_returns * weights)
        portfolio_std_dev = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        sharpe_ratio = (portfolio_return - risk_free_rate) / portfolio_std_dev

        results[0, i] = portfolio_return
        results[1, i] = portfolio_std_dev
        results[2, i] = sharpe_ratio
        for j in range(len(weights)):
            results[3 + j, i] = weights[j]

    columns = ['return', 'stdev', 'sharpe'] + list(returns_df.columns)
    results_df = pd.DataFrame(results.T, columns=columns)

    max_sharpe_idx = results_df['sharpe'].idxmax()
    min_vol_idx = results_df['stdev'].idxmin()

    return {
        "simulated_portfolios": results_df,
        "max_sharpe": results_df.iloc[max_sharpe_idx],
        "min_volatility": results_df.iloc[min_vol_idx],
        "asset_names": list(returns_df.columns)
    }