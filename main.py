import requests
import pandas as pd
import os

def get_market_flow():
    # 1. 抓取證交所產業成交統計 API
    url = "https://openapi.twse.com.tw/v1/exchangeReport/BFT41U"
    response = requests.get(url)
    data = response.json()
    
    # 2. 轉換為 DataFrame 進行分析
    df = pd.DataFrame(data)
    # 欄位：TradeValue(成交金額), IndustryName(產業名稱)
    df['TradeValue'] = pd.to_numeric(df['TradeValue'].str.replace(',', ''))
    
    # 計算成交佔比
    total_value = df['TradeValue'].sum()
    df['Percentage'] = (df['TradeValue'] / total_value * 100).round(2)
    
    # 排序取得前 5 名資金流入產業
    top_5 = df.sort_values(by='Percentage', ascending=False).head(5)
    
    msg = "📊 台股資金流向日報\n"
    for _, row in top_5.iterrows():
        msg += f"🔹 {row['IndustryName']}: {row['Percentage']}%\n"
    return msg

def send_telegram(message):
    token = os.getenv('TG_TOKEN')
    chat_id = os.getenv('TG_CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    requests.post(url, json=payload)

if __name__ == "__main__":
    report = get_market_flow()
    send_telegram(report)
