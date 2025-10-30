# Real-time Pipeline: Kafka + AWS + Snowflake 

**Real-time data pipeline** do przetwarzania danych o cenach kryptowalut. Dane są pobierane z API CoinGecko, przesyłane przez Apache Kafka, zapisywane do AWS S3 w warstwach (bronze, silver, gold), a następnie ładowane do hurtowni danych Snowflake z modelowaniem wymiarowym (dimensional modeling).

---

## 🛠 Stack Technologiczny

| Kategoria       | Technologie                          |
|-----------------|--------------------------------------|
| **Streaming**   | Apache Kafka, Python (kafka-python) |
| **Dane wejściowe** | CoinGecko API (REST)               |
| **Przechowywanie** | AWS S3 (buckety: bronze, silver, gold, glue) |
| **ETL**         | AWS Glue (PySpark)                  |
| **Orkiestracja** | AWS Lambda, CloudFormation, S3 Events |
| **Hurtownia**   | Snowflake (Snowpipe, Stage, Warehouse) |
| **Konteneryzacja** | Docker, docker-compose             |
| **Testy & CI/CD** | pytest, flake8, black, GitHub Actions |
| **Język**       | Python 3.11                         |

---

**🚀Opis projektu:**

- **Streaming danych**: Producent (producer) pobiera dane co 10 sekund i wysyła do Kafki.
- **Przetwarzanie ETL**: Konsument zapisuje surowe dane do S3 (bronze). Glue jobs czyści i transformują dane (silver → gold).
- **Warstwy danych**: Bronze (surowe JSON), Silver (oczyszczone Parquet), Gold (modelowanie wymiarowe: dim_coin + fact_market_metrics).
- **Automatyzacja**: Lambda triggery na S3 uruchamiają Glue jobs automatycznie.
- **Hurtownia danych**: Snowflake z automatycznym ładowaniem (Snowpipe) z S3.
- **CI/CD**: GitHub Actions do testów i lintingu.

---

## Wymagania

- **Lokalne:**
  - Python 3.11+
  - Docker & Docker Compose
  - AWS CLI (z konfiguracją: `aws configure`)

- **AWS (Free Tier):**
  - Konto AWS (eu-north-1)
  - IAM Role: `glue_s3_role` z politykami `glue_s3_policy` i `snowflake_s3_policy`
  - Buckety S3: `kafka-realtime-crypto-bronze`, `kafka-realtime-crypto-silver`, `kafka-realtime-crypto-gold`, `kafka-realtime-crypto-glue`
  - Glue Jobs: `bronze-to-silver-job`, `silver-to-gold-job`
  - Lambda Functions: `s3-bronze-trigger-glue`, `s3-silver-trigger-glue`
  - CloudFormation Stacks: `bronze-glue-trigger-stack`, `silver-glue-trigger-stack`

- **Snowflake:**
  - Konto Snowflake (trial/free)
  - Warehouse: `COMPUTE_WH` (XSMALL)
  - Database: `crypto_warehouse`
  - Tabele: `dim_coin`, `fact_market_metrics`
  - Storage Integration: `s3_crypto_integration`
  - Stage: `gold_stage`
  - Pipes: `dim_coin_pipe`, `fact_market_metrics_pipe`

## Instalacja

1. **Sklonuj repozytorium:**

```bash
git clone https://github.com/tomsongracz/kafka-realtime-crypto-pipeline.git
   cd kafka-realtime-crypto-pipeline
```


2. **Zainstaluj zależności Python:**

```bash
pip install -r requirements.txt
```

3. **Skonfiguruj AWS CLI:**

```bash
aws configure
```

Wpisz Access Key ID, Secret Access Key, Region: `eu-north-1`.

4. **Utwórz buckety S3 (jeśli nie istnieją):**

```bash
   aws s3 mb s3://kafka-realtime-crypto-bronze --region eu-north-1
   aws s3 mb s3://kafka-realtime-crypto-silver --region eu-north-1
   aws s3 mb s3://kafka-realtime-crypto-gold --region eu-north-1
   aws s3 mb s3://kafka-realtime-crypto-glue --region eu-north-1
```


5. **Wygeneruj i przypisz polityki IAM (użyj plików JSON z `aws/`):**
- Utwórz politykę: `aws iam create-policy --policy-name glue_s3_policy --policy-document file://aws/glue_s3_policy.json`
- Utwórz rolę: `aws iam create-role --role-name glue_s3_role --assume-role-policy-document file://aws/trust_policy.json`
- Przypisz politykę: `aws iam attach-role-policy --role-name glue_s3_role --policy-arn arn:aws:iam::YOUR_ACCOUNT:policy/glue_s3_policy`

6. **Wrzuć skrypty Glue do S3:**

```bash
   aws s3 cp aws/spark/bronze_to_silver/bronze_to_silver_glue.py s3://kafka-realtime-crypto-glue/
   aws s3 cp aws/spark/silver_to_gold/silver_to_gold_glue.py s3://kafka-realtime-crypto-glue/
```


7. **Utwórz Glue Jobs:**

```bash
   aws glue create-job --region eu-north-1 --name bronze-to-silver-job --role arn:aws:iam::YOUR_ACCOUNT:role/glue_s3_role --command "Name=glueetl,ScriptLocation=s3://kafka-realtime-crypto-glue/bronze_to_silver_glue.py,PythonVersion=3" --default-arguments '{"--job-language":"python","--bronze_bucket":"kafka-realtime-crypto-bronze","--silver_bucket":"kafka-realtime-crypto-silver","--enable-continuous-cloudwatch-log":"true"}' --glue-version "4.0" --number-of-workers 2 --worker-type G.1X   aws glue create-job --region eu-north-1 --name silver-to-gold-job --role arn:aws:iam::YOUR_ACCOUNT:role/glue_s3_role --command "Name=glueetl,ScriptLocation=s3://kafka-realtime-crypto-glue/silver_to_gold_glue.py,PythonVersion=3" --default-arguments '{"--job-language":"python","--silver_bucket":"kafka-realtime-crypto-silver","--gold_bucket":"kafka-realtime-crypto-gold","--enable-continuous-cloudwatch-log":"true"}' --glue-version "4.0" --number-of-workers 2 --worker-type G.1X
```

8. **Wdróż triggery Lambda (CloudFormation):**

```bash
   aws cloudformation deploy --template-file aws/lambda_bronze_trigger.yaml --stack-name bronze-glue-trigger-stack --capabilities CAPABILITY_NAMED_IAM --region eu-north-1
   aws cloudformation deploy --template-file aws/lambda_silver_trigger.yaml --stack-name silver-glue-trigger-stack --capabilities CAPABILITY_NAMED_IAM --region eu-north-1
```

9. **Skonfiguruj S3 Notifications (dla Lambda):**

```bash
   aws s3api put-bucket-notification-configuration --bucket kafka-realtime-crypto-bronze --notification-configuration '{"LambdaFunctionConfigurations":[{"LambdaFunctionArn":"arn:aws:lambda:eu-north-1:YOUR_ACCOUNT:function:s3-bronze-trigger-glue","Events":["s3:ObjectCreated:*"],"Filter":{"Key":{"FilterRules":[{"Name":"prefix","Value":"bronze/"}]}}]}' --region eu-north-1   aws s3api put-bucket-notification-configuration --bucket kafka-realtime-crypto-silver --notification-configuration '{"LambdaFunctionConfigurations":[{"LambdaFunctionArn":"arn:aws:lambda:eu-north-1:YOUR_ACCOUNT:function:s3-silver-trigger-glue","Events":["s3:ObjectCreated:*"],"Filter":{"Key":{"FilterRules":[{"Name":"prefix","Value":"silver/"}]}}]}' --region eu-north-1
```

10. **Skonfiguruj Snowflake:**
 - Utwórz Warehouse, Database, Tabele, Stage, Pipes (patrz SQL w repozytorium lub dokumentacji Snowflake).
 - Utwórz Storage Integration i SQS Queue dla Snowpipe (zobacz `snowflake_s3_policy.json`).

## Uruchomienie Lokalne

1. **Uruchom Kafka + Zookeeper (Docker):**

```bash
 ./start-local.sh
```

Sprawdź: `docker ps` (powinny działać `zookeeper` i `kafka`).

2. **Uruchom Producer (pobiera dane z CoinGecko):**

```bash
python kafka/producer/producer.py
```

Widoczny output: `Sent: {'name': 'Bitcoin', ...}` co 10s.

3. **W innym terminalu: Uruchom Consumer (zapis do S3 bronze):**

```bash
python kafka/consumer/consumer.py
```

Widoczny output: `Saved to S3: bronze/btc/2025-10-30_12-00-00.json`.

4. **Ręczne uruchomienie Glue Jobs (testowo):**

```bash
   aws glue start-job-run --job-name bronze-to-silver-job --region eu-north-1
   aws glue start-job-run --job-name silver-to-gold-job --region eu-north-1
```

5. **Sprawdź dane w Snowflake:**

```sql
   SELECT * FROM crypto_warehouse.public.dim_coin LIMIT 5;
   SELECT * FROM crypto_warehouse.public.fact_market_metrics LIMIT 5;
```

## Testy

Uruchom testy jednostkowe i integracyjne:

```bash
./dev_tools.sh test
```
Lub bezpośrednio:

```bash
pytest tests/ -v
```

- `test_producer.py`: Mock API CoinGecko, sprawdza serializację Kafka.
- `test_consumer.py`: Mock S3, sprawdza zapis JSON.
- `test_spark_jobs.py`: Symulacja PySpark na Pandas, testy ETL i dimensional modeling.

Linting i formatowanie:

```bash
./dev_tools.sh lint
```

## CI/CD

- **GitHub Actions**: Automatyczne testy + linting na push/PR do `main` (patrz `.github/workflows/ci.yml`).
- **Deployment**: Ręczne via AWS CLI lub GitHub Actions (można rozszerzyć o CD).

## Struktura Projektu

```bash
kafka-realtime-crypto-pipeline/
│
├── aws/                                      # Komponenty chmurowe (Spark jobs, konfiguracje AWS)
│   ├── spark/
│   │   ├── bronze_to_silver/                 # ETL: przetwarzanie danych z warstwy bronze → silver
│   │   │   ├── bronze_to_silver_glue.py      # Kod Spark (PySpark / Glue): czyszczenie, walidacja i standaryzacja danych
│   │   │   └── job_config.json               # Konfiguracja Glue Job (parametry, rola, lokalizacja skryptu)
│   │   │
│   │   └── silver_to_gold/                   # ETL: przetwarzanie danych z warstwy silver → gold
│   │       ├── silver_to_gold_glue.py        # Kod Spark (PySpark / Glue): modelowanie wymiarowe (fact + dim)
│   │       └── job_config.json               # Konfiguracja Glue Job dla silver → gold
│   │
│   ├── trust_policy.json                     # Część IAM Role
│   ├── snowflake_s3_policy.json              # Czytanie Snowflake z S3
│   └── glue_s3_policy.json                   # Polityka IAM nadająca Glue Jobowi dostęp do bucketów S3 i CloudWatch
│
├── kafka/
│   ├── producer/
│   │   └── producer.py                       # Skrypt producenta: pobiera dane z CoinGecko i wysyła do Apache Kafka
│   ├── consumer/
│   │   └── consumer.py                       # Skrypt konsumenta: odbiera dane z Kafki i zapisuje do AWS S3 (bronze)
│   └── docker-compose.yml                    # Konfiguracja Kafki i Zookeepera w środowisku lokalnym
│
├── tests/                                    # Testy jednostkowe i integracyjne
│   ├── test_producer.py                      # Testy dla producer.py
│   ├── test_consumer.py                      # Testy dla consumer.py
│   └── test_spark_jobs.py                    # Testy dla jobów Spark (mockowane)
│
├── .github/
│   └── workflows/                    
│       └── ci.yaml                           # CI
│
├── .gitignore                                # Plik ignorowania Git
├── requirements.txt                          # Lista zależności Pythona
├── lambda_bronze_trigger.yaml                # Szablon CloudFormation (Lambda trigger na bronze)
├── lambda_silver_trigger.yaml                # Szablon CloudFormation (Lambda trigger na silver)
├── dev_tools.sh                              # Skrypt umożliwiający łatwe testy i linting 
├── start-local.sh                            # Skrypt restartujący kontenery z opcją buildu obrazu
└── README.md                                 # Dokumentacja projektu
```

## Rozszerzenia i przemyślenia

- Można dodać więcej kryptowalut lub źródeł API.
- Implementacja monitoringu (CloudWatch Alerts).
- Dodanie dashboardu (np. QuickSight na Snowflake).

## 👤 Autor
Projekt przygotowany w celach edukacyjnych i demonstracyjnych.
Możesz mnie znaleźć na GitHubie: [tomsongracz](https://github.com/tomsongracz)







