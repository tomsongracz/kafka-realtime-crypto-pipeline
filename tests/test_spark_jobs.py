# tests/test_spark_jobs.py
# Testy dla logiki ETL w Glue jobs: bronze_to_silver_glue.py i silver_to_gold_glue.py.
# Symulujemy PySpark DataFrame na Pandas (szybkie, offline testy bez AWS/Spark cluster).
# Pokazuje testowanie czyszczenia danych, walidacji i dimensional modeling (star schema).
# Uruchomienie: pytest tests/test_spark_jobs.py -v
# Wymaganie: pandas w requirements.txt (pip install pandas==2.1.0)

import pandas as pd
from datetime import datetime
import hashlib  # Dla symulacji sha2 w fact_id


# --- SYMULACJA BRONZE TO SILVER ---
# Funkcja symulująca logikę z bronze_to_silver_glue.py (czyszczenie, walidacja, transformacje)
def simulate_bronze_to_silver(bronze_df):
    """
    Symuluje Spark DF operacje na Pandas:
    - Filtr: price > 0, non-null name/symbol/price
    - Rename: name -> coin_name, market_cap -> market_cap_usd, volume -> volume_24h_usd
    - Clean symbol: upper + remove non-alnum
    - Add: processed_at, currency='USD', source='coingecko'
    """
    # Fix dla empty DF: sprawdź czy kolumny istnieją, inaczej zwróć pusty
    if bronze_df.empty or "price" not in bronze_df.columns:
        return pd.DataFrame(
            columns=[
                "coin_name",
                "symbol",
                "price",
                "market_cap_usd",
                "volume_24h_usd",
                "circulating_supply",
                "timestamp",
                "processed_at",
                "currency",
                "source",
            ]
        )

    # Filtr (jak .filter w Spark)
    mask = (
        (bronze_df["price"].notna())
        & (bronze_df["price"] > 0)
        & (bronze_df["name"].notna())
        & (bronze_df["symbol"].notna())
    )
    cleaned_df = bronze_df[mask].copy()

    if cleaned_df.empty:
        return cleaned_df

    # Transformacje
    cleaned_df = cleaned_df.rename(
        columns={
            "name": "coin_name",
            "market_cap": "market_cap_usd",
            "volume": "volume_24h_usd",
        }
    )
    cleaned_df["symbol"] = (
        cleaned_df["symbol"]
        .astype(str)
        .str.upper()
        .str.replace(r"[^A-Za-z0-9]", "", regex=True)
    )

    # Dodanie kolumn (jak .withColumn)
    processed_at = datetime.utcnow().isoformat() + "Z"
    cleaned_df["processed_at"] = processed_at
    cleaned_df["currency"] = "USD"
    cleaned_df["source"] = "coingecko"

    return cleaned_df


# Przykładowe dane bronze (surowe JSONy z S3)
SAMPLE_BRONZE_DATA = [
    {
        "name": "Bitcoin",
        "symbol": "BTC",
        "price": 110000,
        "market_cap": 2200000000000,
        "volume": 50000000000,
        "circulating_supply": 19700000,
        "timestamp": "2025-10-29T12:00:00Z",
    },
    {
        "name": None,
        "symbol": "ETH",
        "price": -100,
        "market_cap": 480000000000,
        "volume": 30000000000,
        "circulating_supply": 120000000,
        "timestamp": "2025-10-29T12:00:00Z",
    },  # Invalid: None name, negative price
    {
        "name": "Solana",
        "symbol": "sol-123",
        "price": 200,
        "market_cap": 100000000000,
        "volume": 6000000000,
        "circulating_supply": 500000000,
        "timestamp": "2025-10-29T12:00:00Z",
    },  # Symbol z myślnikiem
    {
        "name": "Ripple",
        "symbol": "XRP",
        "price": 0.5,
        "market_cap": 50000000000,
        "volume": 1000000000,
        "circulating_supply": 100000000000,
        "timestamp": "2025-10-29T12:00:00Z",
    },
]


def test_bronze_to_silver_cleaning():
    """Test czyszczenia i walidacji: filtruje invalid, dodaje kolumny, czyści symbol."""
    bronze_df = pd.DataFrame(SAMPLE_BRONZE_DATA)
    silver_df = simulate_bronze_to_silver(bronze_df)

    # Asserty: 3 rekordy po filtrze (z 4, pomija invalid)
    assert len(silver_df) == 3
    assert "coin_name" in silver_df.columns
    assert silver_df["symbol"].iloc[0] == "BTC"  # Uppercased
    assert silver_df["symbol"].iloc[1] == "SOL123"  # Oczyszczony z myślnika
    assert silver_df["processed_at"].iloc[0].endswith("Z")  # UTC timestamp
    assert silver_df["currency"].unique()[0] == "USD"
    assert all(silver_df["price"] > 0)  # Tylko pozytywne ceny
    assert silver_df["source"].iloc[0] == "coingecko"


def test_bronze_to_silver_empty_input():
    """Edge case: pusta ramka – zwraca pustą bez crasha."""
    empty_df = pd.DataFrame()
    silver_df = simulate_bronze_to_silver(empty_df)
    assert len(silver_df) == 0


# --- SYMULACJA SILVER TO GOLD ---
# Funkcja symulująca logikę z silver_to_gold_glue.py (dimensional modeling: dim + fact)
def simulate_silver_to_gold(silver_df, existing_dim=None, existing_fact=None):
    """
    Symuluje incremental load:
    - dim_coin: unikalne po symbol, coin_id = symbol, append nowych
    - fact_market_metrics: join z dim, fact_id = sha2(symbol + timestamp), append nowych (no dups)
    Zwraca nowe dim i fact DF dla assertów.
    Fix: Akceptuje DFs bezpośrednio (nie paths), dla offline testów.
    """
    # Symulacja odczytu existing (puste na start, jeśli None)
    if existing_dim is None:
        existing_dim = pd.DataFrame(
            columns=[
                "coin_id",
                "coin_name",
                "symbol",
                "source",
                "currency",
                "created_at",
            ]
        )
    if existing_fact is None:
        existing_fact = pd.DataFrame(
            columns=[
                "fact_id",
                "coin_id",
                "timestamp",
                "price",
                "market_cap_usd",
                "volume_24h_usd",
                "circulating_supply",
                "processed_at",
            ]
        )

    # Dim: kandydaci z silver
    candidate_dim = (
        silver_df[["coin_name", "symbol", "source", "currency"]]
        .drop_duplicates(subset=["symbol"])
        .copy()
    )
    candidate_dim["coin_id"] = candidate_dim["symbol"]
    candidate_dim["created_at"] = datetime.utcnow().isoformat() + "Z"

    # Nowe dim (anti-join po symbol)
    new_dim = candidate_dim[~candidate_dim["symbol"].isin(existing_dim["symbol"])]

    # Full dim dla joinu
    full_dim = pd.concat([existing_dim, new_dim]).drop_duplicates(subset=["symbol"])
    full_dim["coin_id"] = full_dim["symbol"]

    # Fact: join + generuj fact_id (sha2 symulowany)
    def generate_fact_id(row):
        key = f"{row['symbol']}-{row['timestamp']}"
        return hashlib.sha256(key.encode()).hexdigest()

    candidate_fact = silver_df.merge(
        full_dim[["symbol", "coin_id"]], on="symbol", how="left"
    )
    candidate_fact["fact_id"] = candidate_fact.apply(generate_fact_id, axis=1)
    candidate_fact = candidate_fact[
        [
            "fact_id",
            "coin_id",
            "timestamp",
            "price",
            "market_cap_usd",
            "volume_24h_usd",
            "circulating_supply",
            "processed_at",
        ]
    ].drop_duplicates(subset=["fact_id"])

    # Nowe fact (anti-join po fact_id)
    new_fact = candidate_fact[~candidate_fact["fact_id"].isin(existing_fact["fact_id"])]

    return new_dim, new_fact


# Przykładowe dane silver (po bronze_to_silver)
SAMPLE_SILVER_DATA = [
    {
        "coin_name": "Bitcoin",
        "symbol": "BTC",
        "price": 110000,
        "market_cap_usd": 2200000000000,
        "volume_24h_usd": 50000000000,
        "circulating_supply": 19700000,
        "timestamp": "2025-10-29T12:00:00Z",
        "processed_at": "2025-10-29T12:01:00Z",
        "source": "coingecko",
        "currency": "USD",
    },
    {
        "coin_name": "Ethereum",
        "symbol": "ETH",
        "price": 4000,
        "market_cap_usd": 480000000000,
        "volume_24h_usd": 30000000000,
        "circulating_supply": 120000000,
        "timestamp": "2025-10-29T12:00:00Z",
        "processed_at": "2025-10-29T12:01:00Z",
        "source": "coingecko",
        "currency": "USD",
    },
    {
        "coin_name": "Bitcoin",
        "symbol": "BTC",
        "price": 110500,
        "market_cap_usd": 2210000000000,
        "volume_24h_usd": 51000000000,
        "circulating_supply": 19700000,
        "timestamp": "2025-10-29T12:05:00Z",
        "processed_at": "2025-10-29T12:01:00Z",
        "source": "coingecko",
        "currency": "USD",
    },
]


def test_silver_to_gold_dimensional_modeling():
    """Test budowania dim/fact: nowe symbole, incremental append, no dups po fact_id."""
    silver_df = pd.DataFrame(SAMPLE_SILVER_DATA)
    new_dim, new_fact = simulate_silver_to_gold(silver_df)

    # Asserty dim: 2 nowe (BTC, ETH)
    assert len(new_dim) == 2
    assert new_dim["coin_id"].iloc[0] == "BTC"
    assert (new_dim["coin_id"] == new_dim["symbol"]).all()  # Spójność coin_id = symbol

    # Asserty fact: 3 unikalne (ETH + dwa BTC z różnymi ts; fact_id unikalne po symbol+ts)
    assert len(new_fact) == 3
    assert new_fact["fact_id"].notna().all()  # Hash wygenerowany
    assert new_fact["coin_id"].iloc[0] == "BTC"
    # Sprawdź różne fact_id dla różnych timestampów
    assert new_fact["fact_id"].nunique() == 3  # Wszystkie unikalne


def test_silver_to_gold_incremental_load():
    """Test incremental: z existing dim/fact, dodaje tylko nowe."""
    silver_df = pd.DataFrame(SAMPLE_SILVER_DATA)

    # Symuluj existing (np. z poprzedniego runa)
    existing_dim = pd.DataFrame(
        [
            {
                "coin_id": "BTC",
                "coin_name": "Bitcoin",
                "symbol": "BTC",
                "source": "coingecko",
                "currency": "USD",
                "created_at": "2025-10-29T11:00:00Z",
            }
        ]
    )
    existing_fact = pd.DataFrame(
        [
            {
                "fact_id": hashlib.sha256(
                    "BTC-2025-10-29T12:00:00Z".encode()
                ).hexdigest(),
                "coin_id": "BTC",
                "timestamp": "2025-10-29T12:00:00Z",
                "price": 110000,
                "market_cap_usd": 2200000000000,
                "volume_24h_usd": 50000000000,
                "circulating_supply": 19700000,
                "processed_at": "2025-10-29T12:01:00Z",
            }
        ]
    )

    new_dim, new_fact = simulate_silver_to_gold(
        silver_df, existing_dim=existing_dim, existing_fact=existing_fact
    )

    # Asserty: 1 nowy dim (ETH), 2 nowe fact (drugi BTC + ETH)
    assert len(new_dim) == 1  # Tylko ETH nowy
    assert new_dim["symbol"].iloc[0] == "ETH"
    assert len(new_fact) == 2  # Nowy BTC ts + ETH
    # Fix: Nie polegaj na kolejności iloc; sprawdź set timestampów i coin_id
    assert set(new_fact["timestamp"].tolist()) == {
        "2025-10-29T12:05:00Z",
        "2025-10-29T12:00:00Z",
    }
    assert set(new_fact["coin_id"].tolist()) == {"BTC", "ETH"}
