from kafka import KafkaConsumer  # odbiór wiadomości z Apache Kafka
import json  # parsowanie formatu JSON
import boto3  # SDK AWS do komunikacji z S3
from datetime import datetime  # generowanie nazw plików z timestampem

# Inicjalizacja konsumenta Kafka
# - auto_offset_reset='earliest' pozwala pobrać wiadomości od początku tematu
# - value_deserializer przekształca dane z JSON do obiektu Python
consumer = KafkaConsumer(
    "crypto_prices",
    bootstrap_servers=["localhost:9092"],
    auto_offset_reset="latest",
    value_deserializer=lambda x: json.loads(x.decode("utf-8")),
)

# Inicjalizacja klienta S3
# Zakłada, że konfiguracja AWS CLI (klucz i secret) jest już ustawiona lokalnie
s3 = boto3.client("s3")

# Nazwa bucketu S3 (należy ustawić własny)
BUCKET = "kafka-realtime-crypto-bronze"

# Główna pętla odbierająca dane z Kafki
for message in consumer:
    data = message.value  # odczyt treści wiadomości (słownik z danymi o kryptowalucie)

    # Pobranie symbolu kryptowaluty (np. BTC, ETH, SOL) – do organizacji folderów
    symbol = data.get("symbol", "unknown").lower()

    # Ustalenie ścieżki w S3, np. bronze/bitcoin/2025-10-20_16-50-00.json
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"bronze/{symbol}/{timestamp}.json"

    # Zapis danych do pliku w formacie JSON w S3
    s3.put_object(Bucket=BUCKET, Key=filename, Body=json.dumps(data))

    # Log informacyjny o zapisie
    print(f"Saved to S3: {filename}")
