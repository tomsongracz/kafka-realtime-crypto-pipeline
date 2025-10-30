from kafka import KafkaProducer
import requests
import json
import time

# Inicjalizacja producenta Kafka
producer = KafkaProducer(
    bootstrap_servers=["localhost:9092"],
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)


# Funkcja pobierająca dane o wielu kryptowalutach z CoinGecko
def get_crypto_data(symbols):
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": ",".join(symbols),  # lista kryptowalut po przecinku
    }

    response = requests.get(url, params=params)
    data = response.json()

    # Przetwarzamy każdą kryptowalutę osobno
    crypto_list = []
    for coin in data:
        crypto_list.append(
            {
                "name": coin["name"],
                "symbol": coin["symbol"].upper(),
                "price": coin["current_price"],
                "market_cap": coin["market_cap"],
                "volume": coin["total_volume"],
                "circulating_supply": coin["circulating_supply"],
                "timestamp": coin["last_updated"],
            }
        )
    return crypto_list


# Główna pętla – wysyła dane o kilku kryptowalutach co 10 sekund
if __name__ == "__main__":
    topic = "crypto_prices"
    symbols = ["bitcoin", "ethereum", "ripple", "solana", "dogecoin"]

    while True:
        crypto_data = get_crypto_data(symbols)
        for data in crypto_data:
            producer.send(topic, value=data)
            print(f"Sent: {data}")
        time.sleep(10)
