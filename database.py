from supabase import create_client, Client

# 請在此處替換你的 Supabase Project URL 與 anon/public Key
SUPABASE_URL = "https://fghqufmbgbxlhnvseevx.supabase.co/"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZnaHF1Zm1iZ2J4bGhudnNlZXZ4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTEzNTU4MTQsImV4cCI6MjEwNjkzMTgxNH0.NlXiNTSXkKHOwfyw6eLiS1-v7w2HP1bywzhyfNYG_Bw"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def add_asset(user_id: str, symbol: str, asset_type: str, quantity: float, buy_price: float):
    """將新增的資產寫入 Supabase 資料庫"""
    data = {
        "user_id": user_id,
        "symbol": symbol.upper(),
        "asset_type": asset_type,
        "quantity": quantity,
        "buy_price": buy_price
    }
    return supabase.table("portfolios").insert(data).execute()

def get_user_portfolio(user_id: str):
    """從 Supabase 讀取指定使用者的所有資產"""
    res = supabase.table("portfolios").select("*").eq("user_id", user_id).execute()
    return res.data