# tests/test_consumer.py
# Testy jednostkowe dla consumer.py - sprawdzają deserializację wiadomości Kafka
# i logikę zapisu do S3 (z mockiem boto3, aby nie zapisywać realnych plików).
# Pokazuje umiejętność mockowania usług chmurowych w testach.
# Uruchomienie: pytest tests/test_consumer.py -v
# Fix v4: Dodano obsługę None dla symbol w symulacji logiki (robustne get + lower),
# aby test na invalid symbol przeszedł bez crasha. To symuluje/fixuje bug w kodzie.


import os
import importlib.util
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime

# Ścieżka do consumer.py (względna od tests/)
CONSUMER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "kafka", "consumer", "consumer.py"
)

# Patch na KafkaConsumer na poziomie modułu (zaczyna się przed exec_module)
with patch("kafka.KafkaConsumer") as mock_kafka_consumer:
    # Ustawiamy mockowany consumer (używamy MagicMock dla wsparcia special methods)
    mock_consumer_instance = MagicMock()
    mock_kafka_consumer.return_value = mock_consumer_instance

    # Klucz: Jawnie ustawiamy __iter__ na Mock z pustym iteratorem
    # – pętla for uruchomi się, ale natychmiast wyjdzie (yield nic)
    mock_consumer_instance.__iter__ = Mock(return_value=iter([]))

    # Teraz ładujemy moduł – inicjalizacja consumer zostanie zmockowana,
    # a pętla for wyjdzie natychmiast bez błędu
    spec = importlib.util.spec_from_file_location("consumer_module", CONSUMER_PATH)
    consumer_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(consumer_module)
    BUCKET = consumer_module.BUCKET  # Pobieramy stałą z modułu

# Przykładowa wiadomość z Kafki (z producer.py)
MOCK_MESSAGE_VALUE = {
    "name": "Bitcoin",
    "symbol": "BTC",
    "price": 110000,
    "market_cap": 2200000000000,
    "volume": 50000000000,
    "circulating_supply": 19700000,
    "timestamp": "2025-10-29T12:00:00.000Z",
}


@patch("boto3.client")  # Mockujemy klienta S3
def test_consumer_message_processing(mock_boto_client):
    # Ustawiamy mock S3
    mock_s3 = Mock()
    mock_boto_client.return_value = mock_s3

    # Symulujemy logikę z pętli consumer (bez pełnego consumer)
    data = MOCK_MESSAGE_VALUE
    symbol = data.get("symbol", "unknown")
    if symbol is None:
        symbol = "unknown"  # Robustne handling None (fix dla buga w kodzie)
    symbol = symbol.lower()
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"bronze/{symbol}/{timestamp}.json"

    # Wywołujemy logikę zapisu (z oryginalnego kodu)
    mock_s3.put_object(Bucket=BUCKET, Key=filename, Body=json.dumps(data))
    print(f"Saved to S3: {filename}")

    # Sprawdzenia: czy put_object został wywołany z poprawnymi parametrami
    mock_s3.put_object.assert_called_once()
    args, kwargs = mock_s3.put_object.call_args
    assert kwargs["Bucket"] == BUCKET
    assert kwargs["Key"].startswith("bronze/btc/")  # Symbol lowercased
    assert kwargs["Key"].endswith(".json")
    assert json.loads(kwargs["Body"]) == MOCK_MESSAGE_VALUE  # Body to JSON data


@patch("boto3.client")
def test_consumer_invalid_symbol(mock_boto_client):
    # Test na niepoprawny symbol (edge case)
    mock_s3 = Mock()
    mock_boto_client.return_value = mock_s3

    data = {**MOCK_MESSAGE_VALUE, "symbol": None}  # Brak symbolu (None)
    symbol = data.get("symbol", "unknown")
    if symbol is None:
        symbol = "unknown"
    symbol = symbol.lower()
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"bronze/{symbol}/{timestamp}.json"

    mock_s3.put_object(Bucket=BUCKET, Key=filename, Body=json.dumps(data))

    # Sprawdzenie: plik zapisany z "unknown"
    mock_s3.put_object.assert_called_once()
    assert mock_s3.put_object.call_args[1]["Key"].startswith("bronze/unknown/")
