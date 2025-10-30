# Real-time Pipeline: Kafka + AWS + Snowflake 

**Real-time data pipeline** do przetwarzania danych o cenach kryptowalut. Dane są pobierane z API CoinGecko, przesyłane przez **Apache Kafka**, zapisywane do chmury **AWS S3** w warstwach (bronze, silver, gold), a następnie ładowane do hurtowni danych **Snowflake** z modelowaniem wymiarowym (dimensional modeling).

---

## 🛠 Stack Technologiczny

| **Komponent**        | **Technologia**                                          | **Rola** |
|-----------------------|----------------------------------------------------------|-----------|
| **Streaming** | Apache Kafka (lokalny klaster w Dockerze), Zookeeper, Python (`kafka-python`) | Strumieniowe pobieranie i przesyłanie danych o kryptowalutach w czasie rzeczywistym |
| **Dane wejściowe**    | CoinGecko API (REST)                                   | Źródło danych – notowania i metadane kryptowalut |
| **Przechowywanie (Data Lake)** | AWS S3 (buckety: bronze, silver, gold, glue)       | Warstwy surowe, przetworzone i końcowe danych (bronze → silver → gold) |
| **Modelowanie danych**      | Model gwiazdy: `dim_coin`, `fact_market_metrics`        | Modelowanie wymiarowe |
| **ETL**               | AWS Glue (PySpark)                                     | Transformacja danych, czyszczenie, deduplikacja i zapis do S3 |
| **Orkiestracja**      | AWS Lambda, CloudFormation, S3 Events                  | Automatyzacja wywołań Glue i Snowpipe, zarządzanie infrastrukturą |
| **Hurtownia danych**  | Snowflake (Snowpipe, Stage, Warehouse)                  | Automatyczne ładowanie danych z S3 (GOLD) do tabel analitycznych |
| **Konteneryzacja**    | Docker, docker-compose                                 | Uruchamianie środowiska lokalnego i usług pomocniczych |
| **Testy & CI/CD**     | pytest, flake8, black, GitHub Actions                  | Testy jednostkowe, linting, formatowanie kodu i automatyczne wdrożenia |
| **Język**             | Python 3.11                                            | Główny język implementacji pipeline’u |

> Kod sformatowany za pomocą **Black** + **Flake8** (ignorowanie `F401`).

---

## 🚀 Jak to działa?

- **Środowisko lokalne**:

Klaster Apache Kafka uruchamiany jest lokalnie w kontenerach Dockerowych przy użyciu docker-compose.
Zookeeper pełni rolę koordynatora, a Kafka obsługuje temat z danymi o kryptowalutach.
Producer i Consumer komunikują się z tym lokalnym brokerem.

- **Streaming danych**: Producent (`producer.py`) pobiera dane co 10 sekund i wysyła do Kafki.
  
- **Przetwarzanie ETL**: Konsument (`consumer.py`) zapisuje surowe dane do S3 (bronze). Glue jobs czyści i transformuje dane (bronze → silver → gold).
  
- **Warstwy danych**: Bronze (surowe JSON), Silver (oczyszczone Parquet), Gold (modelowanie wymiarowe: dim_coin + fact_market_metrics).

- **Automatyzacja**: Lambda triggery na S3 uruchamiają Glue jobs automatycznie.
  
- **Hurtownia danych**: Snowflake z automatycznym ładowaniem (Snowpipe) z S3.
  
- **CI/CD**: GitHub Actions do testów i lintingu.

---

### 📊 Schemat przepływu danych

```text
CoinGecko API → [producer.py] → Apache Kafka (topic: crypto_prices)
                              ↓
Kafka → [consumer.py] → AWS S3 (Bronze Layer - Raw JSON)
                              ↓
S3 Bronze → [AWS Glue: bronze_to_silver_glue.py] → S3 Silver (Cleaned Parquet)
                              ↓
S3 Silver → [AWS Glue: silver_to_gold_glue.py] → S3 Gold (Dimensional Model)
                              ↓
S3 Gold → [Snowpipe + Stage] → Snowflake Data Warehouse
```

---

## 📁 Struktura Projektu

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

---

## 🧩 Wymagania

### 💻 Lokalne:
  - Python 3.11+
  - Docker & Docker Compose
  - AWS CLI (z konfiguracją: `aws configure`)

### ☁️ AWS (Free Tier):
  - Konto AWS (eu-north-1)
  - IAM Role: `glue_s3_role` z politykami `glue_s3_policy` i `snowflake_s3_policy`
  - Buckety S3: `kafka-realtime-crypto-bronze`, `kafka-realtime-crypto-silver`, `kafka-realtime-crypto-gold`, `kafka-realtime-crypto-glue`
  - Glue Jobs: `bronze-to-silver-job`, `silver-to-gold-job`
  - Lambda Functions: `s3-bronze-trigger-glue`, `s3-silver-trigger-glue`
  - CloudFormation Stacks: `bronze-glue-trigger-stack`, `silver-glue-trigger-stack`

### ❄️ Snowflake:
  - Konto Snowflake (trial/free)
  - Warehouse: `COMPUTE_WH` (XSMALL)
  - Database: `crypto_warehouse`
  - Tabele: `dim_coin`, `fact_market_metrics`
  - Storage Integration: `s3_crypto_integration`
  - Stage: `gold_stage`
  - Pipes: `dim_coin_pipe`, `fact_market_metrics_pipe`

---

## 🧠 Instalacja

### 1. **Sklonuj repozytorium:**

```bash
git clone https://github.com/tomsongracz/kafka-realtime-crypto-pipeline.git
cd kafka-realtime-crypto-pipeline
```


### 2. **Zainstaluj zależności Python:**

```bash
pip install -r requirements.txt
```

### 3. **Skonfiguruj AWS CLI:**

```bash
aws configure
```

Wpisz Access Key ID, Secret Access Key, Region: `eu-north-1`.

### 4. **Utwórz buckety S3 (jeśli nie istnieją):**

```bash
aws s3 mb s3://kafka-realtime-crypto-bronze --region eu-north-1
aws s3 mb s3://kafka-realtime-crypto-silver --region eu-north-1
aws s3 mb s3://kafka-realtime-crypto-gold --region eu-north-1
aws s3 mb s3://kafka-realtime-crypto-glue --region eu-north-1
```


### 5. **Wygeneruj i przypisz polityki IAM (użyj plików JSON z `aws/`):**
   
- Utwórz politykę:

```bash
aws iam create-policy --policy-name glue_s3_policy --policy-document file://aws/glue_s3_policy.json
```

- Utwórz rolę:
  
```bash
aws iam create-role --role-name glue_s3_role --assume-role-policy-document file://aws/trust_policy.json
```

- Przypisz politykę:

```bash
aws iam attach-role-policy --role-name glue_s3_role --policy-arn arn:aws:iam::YOUR_ACCOUNT:policy/glue_s3_policy
```

### 6. **Wrzuć skrypty Glue do S3:**

```bash
aws s3 cp aws/spark/bronze_to_silver/bronze_to_silver_glue.py s3://kafka-realtime-crypto-glue/
aws s3 cp aws/spark/silver_to_gold/silver_to_gold_glue.py s3://kafka-realtime-crypto-glue/
```


### 7. **Utwórz Glue Jobs:**

```bash
aws glue create-job --region eu-north-1 --name bronze-to-silver-job --role arn:aws:iam::YOUR_ACCOUNT:role/glue_s3_role --command "Name=glueetl,ScriptLocation=s3://kafka-realtime-crypto-glue/bronze_to_silver_glue.py,PythonVersion=3" --default-arguments '{"--job-language":"python","--bronze_bucket":"kafka-realtime-crypto-bronze","--silver_bucket":"kafka-realtime-crypto-silver","--enable-continuous-cloudwatch-log":"true"}' --glue-version "4.0" --number-of-workers 2 --worker-type G.1X   aws glue create-job --region eu-north-1 --name silver-to-gold-job --role arn:aws:iam::YOUR_ACCOUNT:role/glue_s3_role --command "Name=glueetl,ScriptLocation=s3://kafka-realtime-crypto-glue/silver_to_gold_glue.py,PythonVersion=3" --default-arguments '{"--job-language":"python","--silver_bucket":"kafka-realtime-crypto-silver","--gold_bucket":"kafka-realtime-crypto-gold","--enable-continuous-cloudwatch-log":"true"}' --glue-version "4.0" --number-of-workers 2 --worker-type G.1X
```

### 8. **Wdróż triggery Lambda (CloudFormation):**

```bash
aws cloudformation deploy --template-file aws/lambda_bronze_trigger.yaml --stack-name bronze-glue-trigger-stack --capabilities CAPABILITY_NAMED_IAM --region eu-north-1
aws cloudformation deploy --template-file aws/lambda_silver_trigger.yaml --stack-name silver-glue-trigger-stack --capabilities CAPABILITY_NAMED_IAM --region eu-north-1
```

### 9. **Skonfiguruj S3 Notifications (dla Lambda):**

```bash
aws s3api put-bucket-notification-configuration --bucket kafka-realtime-crypto-bronze --notification-configuration '{"LambdaFunctionConfigurations":[{"LambdaFunctionArn":"arn:aws:lambda:eu-north-1:YOUR_ACCOUNT:function:s3-bronze-trigger-glue","Events":["s3:ObjectCreated:*"],"Filter":{"Key":{"FilterRules":[{"Name":"prefix","Value":"bronze/"}]}}]}' --region eu-north-1   aws s3api put-bucket-notification-configuration --bucket kafka-realtime-crypto-silver --notification-configuration '{"LambdaFunctionConfigurations":[{"LambdaFunctionArn":"arn:aws:lambda:eu-north-1:YOUR_ACCOUNT:function:s3-silver-trigger-glue","Events":["s3:ObjectCreated:*"],"Filter":{"Key":{"FilterRules":[{"Name":"prefix","Value":"silver/"}]}}]}' --region eu-north-1
```

### 10. **Skonfiguruj Snowflake:**
 - Utwórz Warehouse, Database, Tabele, Stage, Pipes (patrz SQL w repozytorium lub dokumentacji Snowflake).
 - Utwórz Storage Integration i SQS Queue dla Snowpipe (zobacz `snowflake_s3_policy.json`).

---

## 🐳 Uruchomienie 

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
---

## 🧪 Testy

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

---

## ✅ Gotowe!

**Po poprawnej konfiguracji:**

- Apache Kafka strumieniuje dane o kryptowalutach w czasie rzeczywistym z CoinGecko API.

- AWS Glue automatycznie przetwarza dane w warstwach S3 (bronze → silver → gold).

- AWS Lambda orchestruje wywołania Glue i ładowanie danych do Snowflake (Snowpipe).

- Pipeline działa w pełni automatycznie – od pobrania danych po modelowanie wymiarowe w Snowflake.

- Możesz rozwijać i testować pipeline lokalnie w Dockerze lub w środowisku produkcyjnym AWS.

---

## 🔄 CI/CD

- **GitHub Actions**: Automatyczne testy + linting na push/PR do `main` (patrz `.github/workflows/ci.yml`).
- **Deployment**: Ręczne via AWS CLI lub GitHub Actions (można rozszerzyć o CD).

---

## 🌟 Rozszerzenia i przemyślenia

- Można dodać więcej kryptowalut lub źródeł API.
- Implementacja monitoringu (CloudWatch Alerts).
- Dodanie dashboardu (np. QuickSight na Snowflake).

---

## 👤 Autor
Projekt przygotowany w celach edukacyjnych i demonstracyjnych.
Możesz mnie znaleźć na GitHubie: [tomsongracz](https://github.com/tomsongracz)



























