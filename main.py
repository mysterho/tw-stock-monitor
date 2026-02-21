import requests
import pandas as pd
import sqlite3
import os
import sys
from datetime import datetime

# 設定環境變數
TG_TOKEN = os.getenv('TG_TOKEN')
TG_CHAT_ID = os.getenv('TG_CHAT_ID')
DB_NAME = 'stock_history.db'

def run():
    print(f"--- 任務啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    # 1. 抓取資料 (使用三大法人進出日報 API)
    url = "https://openapi.twse.com.tw/v1/investmentService/DailyCombined"
    try:
        res = requests.get(url, timeout=20)
        
        # 假日與維護判斷：如果是 HTML (以 < 開頭) 或空值，代表證交所休息中
        if res.status_code != 200 or not res.text.strip() or res.text.strip().startswith('<!DOCTYPE'):
            print("ℹ️ 證交所目前未提供資料 (可能是假日、維護中或未開盤)。")
            sys.exit(0) # 優雅結束，不回報錯誤

        data = res.json()
    except Exception as e:
        print(f"❌ 連線或解析失敗: {e}")
        sys.exit(0)

    # 2. 資料清洗
    df_raw = pd.DataFrame(data)
    def clean(x): return pd.to_numeric(str(x).replace(',', ''), errors='coerce')

    # 計算：今日總成交額(val)、今日法人淨買超(net)
    # 淨買超 = 外資 + 投信 + 自營商
    df_raw['val'] = df_raw['TradeValue'].apply(clean)
    df_raw['net'] = (df_raw['ForeignExcludingTaiwanBuyValue'].apply(clean) - df_raw['ForeignExcludingTaiwanSellValue'].apply(clean) +
                    df_raw['InvestmentTrustBuyValue'].apply(clean) - df_raw['InvestmentTrustSellValue'].apply(clean) +
                    df_raw['DealerBuyValue'].apply(clean) - df_raw['DealerSellValue'].apply(clean))
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    df_today = df_raw[['Code', 'Name', 'net', 'val']].copy()
    df_today['date'] = today_str
    df_today = df_today.dropna()

    # 3. 存入 SQLite 資料庫
    conn = sqlite3.connect(DB_NAME)
    df_today.to_sql('history', conn, if_exists='append', index=False)
    
    # 4. 計算 20 日籌碼吸納率 (核心指標)
    # 邏輯：抓取最近有資料的 20 天，計算 (20日總淨買超 / 20日總成交額)
    query = """
    SELECT Code, Name, SUM(net) as total_net, SUM(val) as total_val 
    FROM history 
    WHERE date IN (SELECT DISTINCT date FROM history ORDER BY date DESC LIMIT 20)
    GROUP BY Code
    HAVING total_val > 500000000  # 過濾掉 20 日成交不到 5 億的冷門股
    """
    summary = pd.read_sql(query, conn)
    conn.close()

    if not summary.empty:
        summary['ratio'] = (summary['total_net'] / summary['total_val'] * 100).round(2)
        top_10 = summary.sort_values('ratio', ascending=False).head(10)

        # 5. 發送 Telegram 報表
        msg = f"🎯 {today_str} | 20日籌碼吸納率榜單\n"
        msg += "----------------------------\n"
        for _, row in top_10.iterrows():
            msg += f"{row['Code']} {row['Name']}: {row['ratio']}%\n"
        
        send_url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(send_url, json={"chat_id": TG_CHAT_ID, "text": msg})
        print("✅ 報表發送成功！")
    else:
        print("⚠️ 資料庫累積不足，尚無法計算排名。")

if __name__ == "__main__":
    run()
