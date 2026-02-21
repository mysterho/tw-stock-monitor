import requests
import pandas as pd
import sqlite3
import os
from datetime import datetime

# 設定區
DB_NAME = 'stock_history.db'
TG_TOKEN = os.getenv('TG_TOKEN')
TG_CHAT_ID = os.getenv('TG_CHAT_ID')

def process_data():
    # 1. 抓取證交所三大法人數據
    url = "https://openapi.twse.com.tw/v1/investmentService/DailyCombined"
    res = requests.get(url)
    if res.status_code != 200: return
    
    df_raw = pd.DataFrame(res.json())
    today = datetime.now().strftime('%Y-%m-%d')

    # 2. 資料清洗
    def clean_num(x): return float(str(x).replace(',', '')) if x else 0
    
    df_raw['net_buy'] = df_raw['ForeignExcludingTaiwanBuyValue'].apply(clean_num) - \
                        df_raw['ForeignExcludingTaiwanSellValue'].apply(clean_num) + \
                        df_raw['InvestmentTrustBuyValue'].apply(clean_num)
    df_raw['volume'] = df_raw['TradeValue'].apply(clean_num)
    
    df_final = df_raw[['Code', 'Name', 'net_buy', 'volume']].copy()
    df_final['date'] = today

    # 3. 存入 SQLite
    conn = sqlite3.connect(DB_NAME)
    df_final.to_sql('daily_stats', conn, if_exists='append', index=False)
    
    # 4. 計算 20 日集中度
    # 取最近 20 個交易日的代碼資料
    query = """
    SELECT Code, Name, SUM(net_buy) as total_net, SUM(volume) as total_vol 
    FROM daily_stats 
    WHERE date IN (SELECT DISTINCT date FROM daily_stats ORDER BY date DESC LIMIT 20)
    GROUP BY Code
    HAVING total_vol > 0
    """
    summary = pd.read_sql(query, conn)
    summary['ratio'] = (summary['total_net'] / summary['total_vol'] * 100).round(2)
    
    # 5. 篩選前 50 名並準備訊息 (訊息只列前10免得過長)
    top_50 = summary.sort_values('ratio', ascending=False).head(50)
    top_10_msg = "\n".join([f"{i+1}. {r.Code} {r.Name}: {r.ratio}%" for i, r in top_50.head(10).iterrows()])
    
    conn.close()
    return top_10_msg

def send_tg(msg):
    if not msg: return
    full_msg = f"🚀 20日籌碼吸納率排行：\n{msg}"
    requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                  json={"chat_id": TG_CHAT_ID, "text": full_msg})

if __name__ == "__main__":
    result = process_data()
    send_tg(result)