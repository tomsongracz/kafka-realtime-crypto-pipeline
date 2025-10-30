import sys
from datetime import datetime
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from pyspark.context import SparkContext
from pyspark.sql.functions import col, lit, regexp_replace, upper

# --- INICJALIZACJA ---
# Pobieranie argumentów przekazanych do Glue joba (np. nazwy bucketów S3)
args = getResolvedOptions(sys.argv, ["JOB_NAME", "bronze_bucket", "silver_bucket"])

# Inicjalizacja kontekstu Spark i Glue
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

# Przypisanie nazw bucketów z argumentów Glue joba
bronze_bucket = args["bronze_bucket"]
silver_bucket = args["silver_bucket"]

# Logi informacyjne (widoczne w CloudWatch)
print(f"Starting Glue Job {args['JOB_NAME']}")
print(f"Reading data from s3://{bronze_bucket}/")
print(f"Writing cleaned data to s3://{silver_bucket}/")

# --- ODCZYTANIE plików JSON z warstwy bronze w S3 ---
bronze_df = spark.read.json(f"s3://{bronze_bucket}/bronze/*/*.json")

# --- CZYSZCZENIE DANYCH I WALIDACJA ---
cleaned_df = (
    bronze_df
    # Zachowujemy tylko rekordy, które mają niepustą cenę (price), name i symbol oraz cenę większą od 0.
    .filter(
        col("price").isNotNull()
        & (col("price") > 0)
        & col("name").isNotNull()
        & col("symbol").isNotNull()
    )
    # Zmieniamy nazwę "name" na "coin_name" dla większej przejrzystości.
    .withColumnRenamed("name", "coin_name")
    # Usuwamy znaki spoza zakresu A-Z i 0-9 oraz zamieniamy na wielkie litery.
    # Przykład: "btc" → "BTC", "eth-123" → "ETH123"
    .withColumn("symbol", upper(regexp_replace(col("symbol"), "[^A-Za-z0-9]", "")))
    # Zmiana nazw kolumn finansowych na bardziej opisowe:
    .withColumnRenamed("market_cap", "market_cap_usd")
    .withColumnRenamed("volume", "volume_24h_usd")
    # Dodanie metadanych technicznych:
    # processed_at - czas przetworzenia rekordu w Glue (UTC)
    # currency - stała wartość "USD", aby jasno określić walutę
    # source - informacja o pochodzeniu danych (CoinGecko)
    .withColumn("processed_at", lit(datetime.utcnow().isoformat() + "Z"))
    .withColumn("currency", lit("USD"))
    .withColumn("source", lit("coingecko"))
)

# Sprawdzenie liczby pominiętych rekordów i logowanie próbki danych
record_count = cleaned_df.count()
skipped_count = bronze_df.count() - record_count
print(
    f"Loaded {record_count} records after cleaning. Skipped {skipped_count} records due to NULL or invalid values in price, name, or symbol."
)
if record_count == 0:
    print("WARNING: No valid data after cleaning. Exiting job early.")
    sys.exit(0)

# Logowanie próbki danych dla debugowania
print("Sample cleaned data:")
cleaned_df.show(5)

# --- ZAPIS DO SILVER ---
# Tutaj dane są zapisywane do warstwy silver.
# Dodatkowo dane są podzielone po symbolu kryptowaluty (np. silver/bitcoin/, silver/eth/).
symbols = [
    row["symbol"].lower() for row in cleaned_df.select("symbol").distinct().collect()
]

# Iteracja po wszystkich unikalnych symbolach kryptowalut
for symbol in symbols:
    # Filtrowanie danych tylko dla danego symbolu
    df_symbol = cleaned_df.filter(col("symbol") == symbol.upper())
    # Docelowa ścieżka w S3 dla danego symbolu
    output_path = f"s3://{silver_bucket}/silver/{symbol}/"
    # Zapis w trybie "append" (dopisywanie nowych danych do istniejących)
    (df_symbol.write.mode("append").parquet(output_path))
    # Log informacyjny o zapisanych danych
    print(f"Written {symbol} data to {output_path}")

# Informacja końcowa – job zakończył się sukcesem
print(
    f"Glue job finished successfully. Data written under s3://{silver_bucket}/silver/"
)
