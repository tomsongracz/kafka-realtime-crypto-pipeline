# tests/test_producer.py
# Testy jednostkowe dla producer.py - sprawdzają pobieranie danych z CoinGecko
# i generowanie poprawnych wiadomości Kafka. Używa mocka dla requests,
# aby uniknąć rzeczywistych API calls (szybkie i stabilne testy).
# Uruchomienie: pytest tests/test_producer.py -v
# Rozwiązanie problemu importu: Używamy importlib do bezpośredniego ładowania modułu,
# aby uniknąć konfliktu z biblioteką 'kafka' (folder projektu ma tę samą nazwę).


import os
import importlib.util
from unittest.mock import Mock, patch

# Ścieżka do producer.py (względna od tests/)
PRODUCER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "kafka", "producer", "producer.py"
)

# Ładujemy moduł bezpośrednio za pomocą importlib (bez konfliktu z biblioteką kafka)
spec = importlib.util.spec_from_file_location("producer_module", PRODUCER_PATH)
producer_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(producer_module)
get_crypto_data = producer_module.get_crypto_data  # Pobieramy funkcję

# Przykładowa odpowiedź mock z CoinGecko API (uproszczona dla testu)
MOCK_COINGECKO_RESPONSE = [
    {
        "name": "Bitcoin",
        "symbol": "btc",
        "current_price": 110000,
        "market_cap": 2200000000000,
        "total_volume": 50000000000,
        "circulating_supply": 19700000,
        "last_updated": "2025-10-29T12:00:00.000Z",
    },
    {
        "name": "Ethereum",
        "symbol": "eth",
        "current_price": 4000,
        "market_cap": 480000000000,
        "total_volume": 30000000000,
        "circulating_supply": 120000000,
        "last_updated": "2025-10-29T12:00:00.000Z",
    },
]


@patch("requests.get")  # Mockujemy requests.get, aby nie dzwonić do API
def test_get_crypto_data(mock_get):
    # Ustawiamy mockowaną odpowiedź z CoinGecko
    mock_response = Mock()
    mock_response.json.return_value = MOCK_COINGECKO_RESPONSE
    mock_get.return_value = mock_response

    # Wywołujemy funkcję z symbolami
    symbols = ["bitcoin", "ethereum"]
    result = get_crypto_data(symbols)

    # Sprawdzenia: czy zwrócono 2 rekordy z poprawnymi danymi
    assert len(result) == 2
    assert result[0]["name"] == "Bitcoin"
    assert result[0]["symbol"] == "BTC"  # Symbol powinien być uppercased
    assert result[0]["price"] == 110000
    assert result[1]["name"] == "Ethereum"
    assert result[1]["symbol"] == "ETH"


@patch("requests.get")
def test_get_crypto_data_empty_response(mock_get):
    # Test na pustą odpowiedź API (edge case)
    mock_response = Mock()
    mock_response.json.return_value = []
    mock_get.return_value = mock_response

    symbols = ["bitcoin"]
    result = get_crypto_data(symbols)

    assert len(result) == 0  # Powinno zwrócić pustą listę


# Uproszczony test dla logiki wysyłania - symulujemy bez pełnego main
@patch("kafka.KafkaProducer.send")  # Mockujemy send z biblioteki kafka
@patch("time.sleep")  # Mockujemy sleep, aby uniknąć czekania w teście
@patch("requests.get")  # Mock dla API
def test_producer_sending_logic(mock_get, mock_sleep, mock_send):
    # Ustawiamy mock dla get_crypto_data (przez requests)
    mock_response = Mock()
    mock_response.json.return_value = MOCK_COINGECKO_RESPONSE
    mock_get.return_value = mock_response

    # Tworzymy mockowany producer z biblioteki (bez konfliktu)
    from kafka import KafkaProducer

    mock_producer = Mock(spec=KafkaProducer)
    mock_producer.send = mock_send  # Podmiana send na mock

    # Symulujemy logikę z main (używamy zmiennych z modułu)
    topic = "crypto_prices"
    symbols = ["bitcoin", "ethereum"]  # Uproszczone do 2 dla testu

    crypto_data = get_crypto_data(symbols)
    for data in crypto_data:
        mock_producer.send(topic, value=data)
        print(f"Sent: {data}")  # Z oryginalnego kodu

    # Sprawdzenia: send wywołany 2 razy
    assert mock_send.call_count == 2
    # Sprawdź argumenty pierwszego wywołania (topic i value)
    call_args = mock_send.call_args_list[0]
    assert call_args[0][0] == topic  # Pierwszy arg to topic
    assert call_args[1]["value"] == crypto_data[0]  # value kwarg
