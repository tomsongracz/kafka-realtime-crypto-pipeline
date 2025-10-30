import sys
from datetime import datetime
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from pyspark.context import SparkContext
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, monotonically_increasing_id, lit, sha2, concat_ws

# --- INICJALIZACJA ---

args = getResolvedOptions(sys.argv, ["JOB_NAME", "silver_bucket", "gold_bucket"])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

silver_bucket = args["silver_bucket"]
gold_bucket = args["gold_bucket"]

# Konfiguracja Spark
spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")

print(f"Starting Glue Job {args['JOB_NAME']}")
print(f"Reading from: s3://{silver_bucket}/silver/*")
print(f"Writing to: s3://{gold_bucket}/gold/")

# --- ODCZYT WARSTWY SILVER ---
df = spark.read.parquet(f"s3://{silver_bucket}/silver/*")

# Sprawdź, czy dane zostały odczytane (unikniesz joinu na pustym DF)
record_count = df.count()
print(f"Loaded {record_count} records from silver layer")
if record_count == 0:
    print("WARNING: No data in silver layer. Exiting job early.")
    sys.exit(0)

# --- ODCZYT ISTNIEJĄCYCH DANYCH GOLD DO USUWANIA DUPLIKATÓW ---
# Odczyt istniejących danych z gold (jeśli istnieją), aby uniknąć duplikatów przy append
dim_coin_path = f"s3://{gold_bucket}/gold/dim_coin/"
fact_market_metrics_path = f"s3://{gold_bucket}/gold/fact_market_metrics/"

try:
    existing_dim_coin = spark.read.parquet(dim_coin_path)
    print(
        f"Loaded {existing_dim_coin.count()} existing dim_coin records for deduplication"
    )
    # Upewnij się, że coin_id jest traktowany jako symbol dla spójności (bez hasha)
    existing_dim_coin = existing_dim_coin.withColumn("coin_id", col("symbol"))
except Exception as e:
    print(
        f"No existing dim_coin data found or error reading: {e}. Proceeding with all new data."
    )
    existing_dim_coin = spark.createDataFrame(
        [],
        schema="coin_id STRING, coin_name STRING, symbol STRING, source STRING, currency STRING, created_at TIMESTAMP",
    )

try:
    existing_fact = spark.read.parquet(fact_market_metrics_path)
    print(
        f"Loaded {existing_fact.count()} existing fact_market_metrics records for deduplication"
    )
except Exception as e:
    print(
        f"No existing fact_market_metrics data found or error reading: {e}. Proceeding with all new data."
    )
    existing_fact = spark.createDataFrame(
        [],
        schema="fact_id STRING, coin_id STRING, timestamp TIMESTAMP, price FLOAT, market_cap_usd FLOAT, volume_24h_usd FLOAT, circulating_supply FLOAT, processed_at TIMESTAMP",
    )

# --- WYMIAR: dim_coin (ŁADOWANIE PRZYROSTOWE – TYLKO NOWE SYMBOLE) ---
# Najpierw przygotuj kandydatów z silver (unikalne po symbolu)
# Użyj symbolu bezpośrednio jako coin_id dla spójności i prostoty (unika problemów z hashami)
candidate_dim_coin = (
    df.select("coin_name", "symbol", "source", "currency")
    .dropDuplicates(["symbol"])
    .withColumn(
        "coin_id", col("symbol")
    )  # Użycie symbolu jako coin_id (klucz biznesowy)
    .withColumn("created_at", lit(datetime.utcnow().isoformat() + "Z"))
    .select("coin_id", "coin_name", "symbol", "source", "currency", "created_at")
)

# Filtruj tylko nowe symbole (nieistniejące w existing_dim_coin)
new_dim_coin = candidate_dim_coin.join(existing_dim_coin, on="symbol", how="left_anti")

dim_coin_new_count = new_dim_coin.count()
if dim_coin_new_count > 0:
    new_dim_coin.write.mode("append").parquet(dim_coin_path)
    print(f"Wrote {dim_coin_new_count} NEW dim_coin rows to {dim_coin_path}")
else:
    print("No new dim_coin symbols to add.")

# --- FAKT: fact_market_metrics (ŁADOWANIE PRZYROSTOWE – TYLKO NOWE REKORDY) ---
# Najpierw zbuduj pełny dim_coin (połącz istniejące + nowe, aby mieć kompletne coin_id)
full_dim_coin = existing_dim_coin.union(new_dim_coin).dropDuplicates(["symbol"])

# Upewnij się, że full_dim_coin ma spójne coin_id = symbol
full_dim_coin = full_dim_coin.withColumn("coin_id", col("symbol"))

# Dołącz dane z silver i wygeneruj fact_id
candidate_fact = (
    df.join(full_dim_coin, on=["symbol"], how="left")
    .filter(col("coin_id").isNotNull())  # Upewnij się, że join się udał
    .withColumn("coin_id", col("symbol"))  # Zachowaj spójność coin_id = symbol
    .withColumn(
        "fact_id", sha2(concat_ws("-", col("symbol"), col("timestamp")), 256)
    )  # Użyj symbolu w fact_id dla spójności
    .select(
        "fact_id",
        "coin_id",
        "timestamp",
        "price",
        "market_cap_usd",
        "volume_24h_usd",
        "circulating_supply",
        "processed_at",
    )
    .dropDuplicates(
        ["fact_id"]
    )  # Usuń duplikaty w ramach tego runa (np. te same timestampy)
)

# Filtruj tylko nowe fact_id (nieistniejące w existing_fact)
# Dla existing_fact upewnij się, że coin_id jest spójne w razie potrzeby (ale ponieważ joinujemy po fact_id, jest OK)
new_fact = candidate_fact.join(existing_fact, on="fact_id", how="left_anti")

fact_new_count = new_fact.count()
if fact_new_count > 0:
    new_fact.write.mode("append").parquet(fact_market_metrics_path)
    print(
        f"Wrote {fact_new_count} NEW fact_market_metrics rows to {fact_market_metrics_path}"
    )
else:
    print("No new fact_market_metrics records to add.")

print(
    "Glue job finished successfully. Gold layer updated incrementally without duplicates."
)
