import requests
import csv

def fetch_binance_klines(symbol, interval, limit=500):
    endpoint = "https://api.binance.com/api/v3/klines"
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }

    response = requests.get(endpoint, params=params)
    data = response.json()
    return data

def save_to_csv(data, filename):
    with open(filename, 'w', newline='') as file:
        writer = csv.writer(file)
        # Writing headers
        writer.writerow(["Open time", "Open", "High", "Low", "Close", "Volume", "Close time", "Quote asset volume", "Number of trades", "Taker buy base asset volume", "Taker buy quote asset volume", "Ignore"])
        # Writing data
        writer.writerows(data)

def main():
    # Replace 'ARBUSDT' with your desired trading pair. '1d' means daily candlesticks.
    data = fetch_binance_klines("ARBUSDT", "1d", 500)
    save_to_csv(data, 'ARB_data.csv')
    print("Data saved to ARB_data.csv")

if __name__ == "__main__":
    main()
