# План имплементации MVP: Data Engineer Agent

## 0. Цель MVP

Сделать агента, который принимает неформальный запрос на получение time series данных, выбирает подходящий открытый источник из заранее проверенного registry, формирует execution plan, выполняет Python-код в изолированной среде и возвращает JSON с данными, provenance и ограничениями.

Пример пользовательского запроса:

```text
мне нужно получить данные по средней цене на аренду за метр в районах Вены с 1го по 9ый за последние 5 лет
```

Ключевое требование MVP: агент не должен придумывать данные или API. Если точной открытой статистики нет, он должен вернуть `partial` или `no_data`, объяснив, какая размерность отсутствует.

---

## 1. Проверенные факты, на которых строится MVP

### 1.1. CKAN / data.gv.at

`data.gv.at` можно использовать как каталог открытых датасетов Австрии. CKAN Action API поддерживает работу с packages/resources через HTTP, включая поиск и чтение метаданных датасетов.

Практическое следствие для MVP:

- использовать `package_search` для discovery;
- использовать `package_show` для получения ресурсов датасета;
- не считать найденный датасет пригодным, пока не проверены resource format, dimensions и license.

Источник: CKAN API documentation — https://docs.ckan.org/en/2.9/api/

### 1.2. Eurostat API

Eurostat Statistics API является публичным REST API, возвращает данные в JSON-stat 2.0 и поддерживает фильтрацию через параметры запроса.

Практическое следствие для MVP:

- Eurostat можно использовать как стабильный API-source для европейской статистики;
- нужно писать JSON-stat parser или использовать готовую библиотеку;
- для локальных венских районов Eurostat, скорее всего, не даст нужную granularity.

Источник: Eurostat API documentation — https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-detailed-guidelines/api-statistics

### 1.3. Open Data Wien / GeoWebServices

Вена публикует OGD и GeoWebServices. GeoWebServices являются стандартизированными интерфейсами для доступа к геоданным города, включая WFS/WMS.

Практическое следствие для MVP:

- Vienna district boundaries и другие геоданные можно тянуть через WFS;
- WFS полезен для гео-слоя, но не гарантирует наличие статистических time series;
- WFS adapter нужен отдельно от CSV/Eurostat adapters.

Источник: Digitales Wien GeoWebServices — https://digitales.wien.gv.at/open-data/geowebservices/

### 1.4. STATcube API

STATcube API существует, но автоматический API-доступ требует API key и активную подписку STATcube. Бесплатный guest access не равен полноценному API-доступу для production-pipeline.

Практическое следствие для MVP:

- STATcube adapter должен существовать как `auth_required`;
- не пытаться обходить подписку;
- если у пользователя есть credentials, можно добавить authenticated mode во второй фазе.

Источник: Statistik Austria STATcube subscription access — https://www.statistik.at/en/databases/statcube-statistical-database/subscription-access

---

## 2. Главный продуктовый вывод

MVP реализуем, но не как универсальный агент “найди любые данные”.

Реалистичный MVP:

1. Понимает запрос.
2. Нормализует его в machine-readable intent.
3. Ищет источник только среди проверенных источников.
4. Возвращает `exact`, `partial`, `no_data` или `auth_required`.
5. Генерирует execution plan.
6. Выполняет контролируемый Python-код.
7. Возвращает JSON time series.
8. Всегда показывает ограничения и provenance.

Для запроса про аренду по районам Вены 1–9 за последние 5 лет ожидаемый результат, скорее всего, `partial`, потому что официальные открытые источники могут дать rent/housing-costs time series на уровне Вены/федеральной земли, но не обязательно на уровне муниципальных районов.

---

## 3. Архитектура

```text
User Query
   |
   v
Intent Extractor
   |
   v
Normalized Data Request
   |
   v
Source Planner
   |
   v
Source Registry + Dataset Index
   |
   v
Execution Plan
   |
   v
Code Planner / Template Renderer
   |
   v
Sandbox Runner
   |
   v
Result Validator
   |
   v
TimeSeries JSON Response
```

---

## 4. Компоненты

## 4.1. Intent Extractor

### Назначение

Превратить неформальный запрос в строгий JSON.

### Input

```json
{
  "raw_text": "мне нужно получить данные по средней цене на аренду за метр в районах Вены с 1го по 9ый за последние 5 лет"
}
```

### Output

```json
{
  "domain": "housing",
  "metric": "average_rent",
  "unit": "eur_per_sqm_per_month",
  "geo": {
    "country": "Austria",
    "city": "Vienna",
    "districts": [1,2,3,4,5,6,7,8,9]
  },
  "time_range": {
    "type": "relative",
    "last_years": 5
  },
  "frequency_preference": "quarterly_or_annual",
  "required_output": "timeseries"
}
```

### Implementation notes

Сделать hybrid extraction:

- regex / deterministic rules для дат, районов, числовых диапазонов;
- LLM для domain/metric/unit normalization;
- Pydantic validation после LLM;
- fallback parser, если LLM вернул невалидный JSON.

### Минимальные правила

```text
"аренда", "miete", "rent" -> metric=average_rent
"за метр", "м2", "m²", "sqm" -> unit=eur_per_sqm_per_month
"Вена", "Vienna", "Wien" -> city=Vienna
"с 1го по 9ый район" -> districts=[1,2,3,4,5,6,7,8,9]
"последние 5 лет" -> relative time range
```

---

## 4.2. Source Registry

### Назначение

Контролируемый список источников, которым агент может доверять.

### Почему это важно

Нельзя позволять LLM придумывать API endpoints. Все источники должны быть заранее описаны и верифицированы.

### Файл

```text
app/registry/sources.yaml
```

### Пример

```yaml
- id: data_gv_at
  name: data.gv.at
  type: ckan_catalog
  base_url: https://www.data.gv.at/api/3/action
  access: public
  auth_required: false
  formats:
    - csv
    - json
    - xlsx
    - ods
    - wfs
  domains:
    - government_open_data
    - statistics
    - geodata

- id: statistik_austria_open_data
  name: Statistik Austria Open Data
  type: csv_catalog
  base_url: https://data.statistik.gv.at
  access: public
  auth_required: false
  formats:
    - csv
    - ods
    - metadata_html
  domains:
    - housing
    - prices
    - demographics
    - economy

- id: statcube_api
  name: Statistik Austria STATcube API
  type: rest_api
  base_url: https://statcubeapi.statistik.at/statistik.at/ext/statcube/rest/v1
  access: subscription
  auth_required: true
  formats:
    - json
  domains:
    - housing
    - prices
    - demographics
    - economy

- id: eurostat
  name: Eurostat Statistics API
  type: jsonstat_api
  base_url: https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data
  access: public
  auth_required: false
  formats:
    - jsonstat
  domains:
    - housing
    - prices
    - demographics
    - economy

- id: vienna_open_data
  name: Open Data Wien
  type: mixed_catalog_geoservices
  base_url: https://data.wien.gv.at
  access: public
  auth_required: false
  formats:
    - csv
    - json
    - wfs
    - wms
  domains:
    - vienna
    - geodata
    - transport
    - environment
    - administration
```

---

## 4.3. Dataset Index

### Назначение

Registry описывает источники. Dataset index описывает конкретные датасеты, их размерности, формат и ограничения.

### Файл

```text
app/registry/datasets.yaml
```

### Пример

```yaml
- id: statistik_austria_housing_costs
  source_id: statistik_austria_open_data
  title: Housing costs / Wohnkosten
  verified: true
  keywords:
    - rent
    - miete
    - wohnkosten
    - housing costs
    - betriebskosten
  domain: housing
  metrics:
    - average_rent
    - operating_costs
    - housing_costs
  time_series: true
  time_granularity:
    - quarter
    - year
  geo_granularity:
    - austria
    - federal_state
  supports_vienna_districts: false
  access:
    auth_required: false
  resources:
    - format: ods
      url: null
      note: "Resource URL should be resolved/verified during registry enrichment"
  limitations:
    - "May not provide Vienna municipal district level data"

- id: eurostat_city_rents
  source_id: eurostat
  title: Average rent per month in cities by type of dwelling
  verified: true
  domain: housing
  metrics:
    - average_rent
  time_series: true
  geo_granularity:
    - city
  supports_vienna_districts: false
  access:
    auth_required: false
  limitations:
    - "City-level data, not municipal district-level data"

- id: vienna_district_boundaries
  source_id: vienna_open_data
  title: District boundaries of Vienna
  verified: true
  domain: geodata
  metrics:
    - boundaries
  time_series: false
  geo_granularity:
    - district
  supports_vienna_districts: true
  access:
    auth_required: false
  limitations:
    - "Geodata only, not rent price time series"
```

---

## 4.4. Source Planner

### Назначение

Выбрать лучший источник или набор источников на основе normalized request.

### Output statuses

```text
exact         источник покрывает metric + time + geo + unit
partial       источник покрывает часть запроса, но есть missing dimensions
no_data       проверенный источник не найден
auth_required источник найден, но нужен API key / подписка
error         техническая ошибка
```

### Scoring

```text
+40 domain match
+30 metric match
+20 time_series support
+20 geo exact match
+10 unit exact match
-50 auth required and no credentials
-30 missing requested geo granularity
-20 unknown license/access
```

### Пример для аренды по районам Вены

```json
{
  "status": "partial",
  "selected_candidates": [
    {
      "dataset_id": "statistik_austria_housing_costs",
      "source_id": "statistik_austria_open_data",
      "match_score": 70,
      "missing_dimensions": ["vienna_district"],
      "reason": "Official housing/rent time series exists, but district-level support is not verified"
    },
    {
      "dataset_id": "eurostat_city_rents",
      "source_id": "eurostat",
      "match_score": 65,
      "missing_dimensions": ["vienna_district"],
      "reason": "City-level rent data may be available, but not municipal districts"
    }
  ],
  "rejected_candidates": [
    {
      "dataset_id": "statcube_housing",
      "source_id": "statcube_api",
      "reason": "auth_required"
    }
  ]
}
```

---

## 4.5. Formal Execution Plan

### Назначение

LLM или planner не должен сразу писать свободный Python. Он должен создать execution plan, из которого система соберет код через templates.

### Пример

```json
{
  "plan_id": "vienna_rent_proxy_001",
  "status": "partial",
  "adapter": "ods_resource",
  "source_id": "statistik_austria_open_data",
  "dataset_id": "statistik_austria_housing_costs",
  "resource": {
    "url": "TO_BE_RESOLVED",
    "format": "ods"
  },
  "filters": {
    "geo": ["Vienna"],
    "time": {
      "last_years": 5
    },
    "metric": "average_rent"
  },
  "transform_steps": [
    "download_resource",
    "parse_ods",
    "detect_time_columns",
    "normalize_to_tidy_timeseries",
    "filter_last_5_years",
    "attach_limitations"
  ],
  "expected_output": {
    "date": "string",
    "region": "string",
    "metric": "string",
    "value": "number",
    "unit": "string",
    "source": "string"
  },
  "limitations": [
    "Requested Vienna districts 1-9 are not available in the selected open dataset",
    "Returned data is a city/federal-state level proxy"
  ]
}
```

---

## 4.6. Code Planner

### MVP rule

Не генерировать произвольный полный Python-скрипт. Использовать templates.

### Templates

```text
app/sandbox/templates/csv_timeseries.py.j2
app/sandbox/templates/ods_timeseries.py.j2
app/sandbox/templates/eurostat_jsonstat.py.j2
app/sandbox/templates/wfs_feature.py.j2
```

### Разрешенный dynamic block

Если нужен LLM-generated transform, ограничить его функцией:

```python
def transform(df: pd.DataFrame) -> pd.DataFrame:
    ...
```

Запретить:

- `subprocess`
- `os.system`
- arbitrary file reads
- dynamic pip install
- network calls outside adapter
- writing outside `/work/output`

---

## 4.7. Sandbox Runner

### Назначение

Выполнить сгенерированный скрипт в изолированной среде.

### Docker image

```dockerfile
FROM python:3.12-slim

RUN pip install --no-cache-dir \
    requests \
    pandas \
    pyarrow \
    openpyxl \
    odfpy \
    lxml \
    python-dateutil \
    pydantic

WORKDIR /work
USER nobody
```

### Runtime constraints

```text
timeout: 60-120 sec
memory: 512MB-1GB
cpu: 1 core
write access: /work/output only
network: allowlist only
max output size: 10MB
```

### Network allowlist

```text
data.statistik.gv.at
www.data.gv.at
data.wien.gv.at
ec.europa.eu
```

### Runner input

```json
{
  "execution_plan": {},
  "script": "..."
}
```

### Runner output

```json
{
  "exit_code": 0,
  "stdout": "...",
  "stderr": "...",
  "result_json_path": "/work/output/result.json",
  "duration_ms": 1234
}
```

---

## 4.8. Result Validator

### Назначение

Проверить, что результат соответствует контракту и не содержит ложных утверждений.

### Required fields per data row

```json
{
  "date": "2022-Q1",
  "region": "Vienna",
  "metric": "average_rent_per_sqm",
  "value": 9.12,
  "unit": "EUR/m2/month",
  "source": "Statistik Austria",
  "dataset_id": "statistik_austria_housing_costs"
}
```

### Validation rules

1. JSON валиден.
2. `status` один из `success`, `partial`, `no_data`, `auth_required`, `error`.
3. Если `status=success`, `data` не пустой.
4. Если запрошены districts, а возвращен только `Vienna`, выставить `granularity_match=proxy`.
5. Если `granularity_match=proxy`, обязательно заполнить `limitations`.
6. Если нет time dimension, нельзя возвращать `success` для time series запроса.
7. Каждая точка данных должна иметь `source` и `dataset_id`.

---

## 5. Структура репозитория

```text
data-engineer-agent/
  README.md
  pyproject.toml
  .env.example
  docker/
    Dockerfile.runner
  app/
    main.py
    config.py

    schemas/
      request_schema.py
      source_schema.py
      plan_schema.py
      result_schema.py

    agents/
      intent_extractor.py
      source_planner.py
      code_planner.py

    registry/
      sources.yaml
      datasets.yaml
      loader.py

    adapters/
      base.py
      ckan.py
      csv_resource.py
      ods_resource.py
      eurostat.py
      wfs.py
      statcube.py

    sandbox/
      runner.py
      templates/
        csv_timeseries.py.j2
        ods_timeseries.py.j2
        eurostat_jsonstat.py.j2
        wfs_feature.py.j2

    validation/
      result_validator.py
      data_quality.py

    prompts/
      intent_extraction.md
      source_selection.md
      code_generation.md

  examples/
    vienna_rent_request.json
    austria_hpi_request.json
    vienna_boundaries_request.json

  tests/
    test_intent_extractor.py
    test_source_planner.py
    test_result_validator.py
    test_registry_loader.py
```

---

## 6. API MVP

Использовать FastAPI.

### 6.1. `POST /query`

Полный pipeline: intent → source plan → execution → validation.

Request:

```json
{
  "query": "мне нужно получить данные по средней цене на аренду за метр в районах Вены с 1го по 9ый за последние 5 лет"
}
```

Response:

```json
{
  "status": "partial",
  "interpreted_request": {},
  "source_plan": {},
  "execution_result": {},
  "data": [],
  "metadata": {
    "granularity_match": "proxy",
    "limitations": [],
    "sources": []
  }
}
```

### 6.2. `POST /dry-run`

Только interpretation + source planning, без запуска sandbox.

Request:

```json
{
  "query": "индекс цен на жилье в Австрии поквартально за 10 лет"
}
```

Response:

```json
{
  "interpreted_request": {},
  "source_plan": {}
}
```

### 6.3. `GET /sources`

Возвращает registry sources.

### 6.4. `GET /datasets`

Возвращает dataset index.

---

## 7. Пошаговый план имплементации для Codex

## Phase 1 — Bootstrap проекта

### 1.1. Создать структуру

```bash
mkdir data-engineer-agent
cd data-engineer-agent

mkdir -p app/{schemas,agents,registry,adapters,sandbox/templates,validation,prompts}
mkdir -p docker examples tests
touch app/main.py app/config.py
```

### 1.2. Создать `pyproject.toml`

Dependencies:

```toml
[project]
name = "data-engineer-agent"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi",
  "uvicorn",
  "pydantic",
  "pyyaml",
  "requests",
  "pandas",
  "pyarrow",
  "openpyxl",
  "odfpy",
  "lxml",
  "python-dateutil",
  "jinja2"
]
```

### 1.3. Создать Dockerfile runner

Файл:

```text
docker/Dockerfile.runner
```

---

## Phase 2 — Schemas

### 2.1. `request_schema.py`

Создать модели:

```python
class GeoRequest(BaseModel):
    country: str | None = None
    city: str | None = None
    districts: list[int] | None = None
    region: str | None = None

class TimeRange(BaseModel):
    type: Literal["relative", "absolute"]
    last_years: int | None = None
    start_date: str | None = None
    end_date: str | None = None

class UserDataRequest(BaseModel):
    raw_text: str
    domain: str
    metric: str
    unit: str | None = None
    geo: GeoRequest
    time_range: TimeRange
    frequency_preference: str | None = None
    required_output: Literal["timeseries"]
```

### 2.2. `source_schema.py`

Создать модели:

```python
class SourceDefinition(BaseModel):
    id: str
    name: str
    type: str
    base_url: str
    access: str
    auth_required: bool
    formats: list[str]
    domains: list[str]

class DatasetDefinition(BaseModel):
    id: str
    source_id: str
    title: str
    verified: bool
    domain: str
    metrics: list[str]
    time_series: bool
    geo_granularity: list[str]
    supports_vienna_districts: bool | None = None
    limitations: list[str] = []
```

### 2.3. `plan_schema.py`

Создать:

```python
class SourceCandidate(BaseModel):
    source_id: str
    dataset_id: str
    match_score: int
    missing_dimensions: list[str]
    reason: str

class SourcePlan(BaseModel):
    status: Literal["exact", "partial", "no_data", "auth_required", "error"]
    selected_candidates: list[SourceCandidate]
    rejected_candidates: list[dict] = []
    limitations: list[str] = []
```

### 2.4. `result_schema.py`

Создать:

```python
class TimeSeriesPoint(BaseModel):
    date: str
    region: str
    metric: str
    value: float
    unit: str | None = None
    source: str
    dataset_id: str

class TimeSeriesResult(BaseModel):
    status: Literal["success", "partial", "no_data", "auth_required", "error"]
    data: list[TimeSeriesPoint] = []
    metadata: dict
    warnings: list[str] = []
    errors: list[str] = []
```

---

## Phase 3 — Registry loader

### 3.1. Создать `sources.yaml`

Использовать список из раздела 4.2.

### 3.2. Создать `datasets.yaml`

Начать с:

```text
statistik_austria_housing_costs
eurostat_city_rents
vienna_district_boundaries
statistik_austria_hpi
statistik_austria_ooh_price_index
```

### 3.3. Реализовать `app/registry/loader.py`

Методы:

```python
def load_sources() -> list[SourceDefinition]
def load_datasets() -> list[DatasetDefinition]
def get_source(source_id: str) -> SourceDefinition
def find_datasets(domain: str, metric: str) -> list[DatasetDefinition]
```

---

## Phase 4 — Intent Extractor

### 4.1. Создать `app/agents/intent_extractor.py`

Минимальная реализация:

```python
class IntentExtractor:
    def extract(self, raw_text: str) -> UserDataRequest:
        ...
```

### 4.2. Deterministic helpers

```python
def parse_district_range(text: str) -> list[int] | None
def parse_last_years(text: str) -> int | None
def normalize_city(text: str) -> str | None
def normalize_metric(text: str) -> str
def normalize_unit(text: str) -> str | None
```

### 4.3. Тесты

Файл:

```text
tests/test_intent_extractor.py
```

Проверить:

```text
"с 1го по 9ый район" -> [1..9]
"последние 5 лет" -> last_years=5
"аренда за метр" -> average_rent + eur_per_sqm_per_month
```

---

## Phase 5 — Source Planner

### 5.1. Создать `app/agents/source_planner.py`

```python
class SourcePlanner:
    def plan(self, request: UserDataRequest) -> SourcePlan:
        ...
```

### 5.2. Реализовать scoring

Правила:

```python
if dataset.domain == request.domain:
    score += 40

if request.metric in dataset.metrics:
    score += 30

if dataset.time_series:
    score += 20

if request.geo.districts and dataset.supports_vienna_districts:
    score += 20
elif request.geo.districts and not dataset.supports_vienna_districts:
    score -= 30
    missing_dimensions.append("vienna_district")

if source.auth_required:
    score -= 50
```

### 5.3. Status decision

```python
if no candidates:
    status = "no_data"
elif all candidates auth_required:
    status = "auth_required"
elif top_candidate.missing_dimensions:
    status = "partial"
else:
    status = "exact"
```

### 5.4. Обязательный тест

Для запроса:

```text
аренда за метр в районах Вены с 1го по 9ый за последние 5 лет
```

ожидается:

```text
status == "partial"
missing_dimensions includes "vienna_district"
```

---

## Phase 6 — Adapters

## 6.1. Base adapter

Файл:

```text
app/adapters/base.py
```

```python
class BaseAdapter(Protocol):
    def build_request(self, plan: ExecutionPlan) -> dict:
        ...

    def fetch(self, request: dict) -> Any:
        ...

    def normalize(self, raw: Any) -> pd.DataFrame:
        ...
```

## 6.2. CKAN adapter

Файл:

```text
app/adapters/ckan.py
```

Методы:

```python
def package_search(query: str, rows: int = 10) -> dict
def package_show(package_id: str) -> dict
def extract_resources(package: dict) -> list[dict]
```

Endpoints:

```text
/api/3/action/package_search
/api/3/action/package_show
```

## 6.3. CSV adapter

Файл:

```text
app/adapters/csv_resource.py
```

Методы:

```python
def download_csv(url: str) -> bytes
def read_csv_safely(content: bytes) -> pd.DataFrame
def normalize_timeseries(df: pd.DataFrame, plan: ExecutionPlan) -> pd.DataFrame
```

Нужно поддержать:

- `,`
- `;`
- tab
- UTF-8
- Latin-1 fallback

## 6.4. ODS adapter

Файл:

```text
app/adapters/ods_resource.py
```

Методы:

```python
def download_ods(url: str) -> bytes
def read_ods_sheets(content: bytes) -> dict[str, pd.DataFrame]
def detect_relevant_sheet(sheets: dict, keywords: list[str]) -> pd.DataFrame
```

## 6.5. Eurostat adapter

Файл:

```text
app/adapters/eurostat.py
```

Методы:

```python
def build_url(dataset_code: str, filters: dict) -> str
def fetch_jsonstat(url: str) -> dict
def jsonstat_to_dataframe(payload: dict) -> pd.DataFrame
```

## 6.6. WFS adapter

Файл:

```text
app/adapters/wfs.py
```

Методы:

```python
def get_capabilities(base_url: str) -> str
def get_feature(type_name: str, output_format: str = "json") -> dict
```

## 6.7. STATcube adapter

Файл:

```text
app/adapters/statcube.py
```

MVP behavior:

```python
class StatcubeAuthRequired(Exception):
    pass

def fetch(...):
    if not api_key:
        raise StatcubeAuthRequired("STATcube API requires subscription API key")
```

---

## Phase 7 — Code Planner and Templates

### 7.1. Создать `app/agents/code_planner.py`

```python
class CodePlanner:
    def build_script(self, source_plan: SourcePlan, request: UserDataRequest) -> str:
        ...
```

### 7.2. Template selection

```text
source.type == jsonstat_api -> eurostat_jsonstat.py.j2
resource.format == csv -> csv_timeseries.py.j2
resource.format == ods -> ods_timeseries.py.j2
source.type contains wfs -> wfs_feature.py.j2
```

### 7.3. Script output contract

Каждый script должен писать:

```text
/work/output/result.json
```

Формат:

```json
{
  "status": "success",
  "data": [],
  "metadata": {
    "source_id": "...",
    "dataset_id": "...",
    "limitations": []
  }
}
```

---

## Phase 8 — Sandbox Runner

### 8.1. Создать `app/sandbox/runner.py`

```python
class SandboxRunner:
    def run(self, script: str, timeout_seconds: int = 90) -> SandboxResult:
        ...
```

### 8.2. Алгоритм

1. Создать temp dir.
2. Записать `script.py`.
3. Создать output dir.
4. Запустить Docker container.
5. Примонтировать temp dir read-only, output dir writable.
6. Ограничить memory/cpu.
7. Прочитать `result.json`.
8. Вернуть stdout/stderr/result.

### 8.3. Не делать в MVP

- dynamic pip install;
- unrestricted network;
- arbitrary shell commands;
- long-running jobs.

---

## Phase 9 — Result Validator

### 9.1. Создать `app/validation/result_validator.py`

```python
class ResultValidator:
    def validate(
        self,
        raw_result: dict,
        request: UserDataRequest,
        plan: SourcePlan
    ) -> TimeSeriesResult:
        ...
```

### 9.2. Основная логика

```python
if request.required_output == "timeseries" and not has_time_dimension(raw_result):
    return error

if request.geo.districts and returned_only_city_level(raw_result):
    status = "partial"
    metadata["granularity_match"] = "proxy"
    metadata["limitations"].append(
        "Requested district-level data was not available; returned city-level proxy"
    )
```

---

## Phase 10 — FastAPI integration

### 10.1. `app/main.py`

Endpoints:

```python
@app.post("/query")
def query(request: QueryInput):
    ...

@app.post("/dry-run")
def dry_run(request: QueryInput):
    ...

@app.get("/sources")
def sources():
    ...

@app.get("/datasets")
def datasets():
    ...
```

### 10.2. `/query` pipeline

```python
interpreted = intent_extractor.extract(input.query)
source_plan = source_planner.plan(interpreted)

if source_plan.status in ["no_data", "auth_required"]:
    return response_without_execution(...)

script = code_planner.build_script(source_plan, interpreted)
raw_execution = sandbox_runner.run(script)
validated = result_validator.validate(raw_execution.result_json, interpreted, source_plan)

return validated
```

---

## Phase 11 — Demo scenarios

### Scenario 1 — Partial match: Vienna rent districts

Input:

```text
мне нужно получить данные по средней цене на аренду за метр в районах Вены с 1го по 9ый за последние 5 лет
```

Expected:

```json
{
  "status": "partial",
  "metadata": {
    "granularity_match": "proxy",
    "requested_geo": "Vienna districts 1-9",
    "returned_geo": "Vienna city or federal-state level",
    "limitations": [
      "No verified official open dataset with district-level rent time series was found"
    ]
  }
}
```

### Scenario 2 — Housing price index

Input:

```text
получи индекс цен на жилье в Австрии поквартально за последние 10 лет
```

Expected:

```json
{
  "status": "success",
  "data": [
    {
      "date": "2016-Q1",
      "region": "Austria",
      "metric": "house_price_index",
      "value": 100.0,
      "unit": "index",
      "source": "Statistik Austria",
      "dataset_id": "statistik_austria_hpi"
    }
  ]
}
```

### Scenario 3 — Vienna district boundaries

Input:

```text
получи границы районов Вены
```

Expected:

```json
{
  "status": "success",
  "data_type": "geospatial",
  "format": "geojson"
}
```

### Scenario 4 — No data

Input:

```text
получи цены аренды по каждому дому Вены за последние 20 лет
```

Expected:

```json
{
  "status": "no_data",
  "limitations": [
    "No verified official open dataset provides building-level rent time series for Vienna"
  ]
}
```

---

## 8. Anti-hallucination rules

Codex должен явно реализовать эти правила.

### 8.1. Нельзя возвращать `success`, если отсутствует требуемая geo granularity

Если пользователь просит районы, а источник содержит только город:

```text
status = partial
granularity_match = proxy
```

### 8.2. Нельзя придумывать resource URL

Если URL не проверен:

```text
verified = false
status = no_data или registry_needs_enrichment
```

### 8.3. Нельзя использовать STATcube без credentials

Если dataset доступен только через STATcube API:

```text
status = auth_required
```

### 8.4. Нельзя скрывать limitations

Если результат partial:

```text
metadata.limitations must be non-empty
```

### 8.5. Нельзя смешивать private/commercial scraping с open data MVP

Если источник — портал недвижимости без официального API/license:

```text
reject reason = not_open_data_or_license_unknown
```

---

## 9. Tests

### 9.1. Unit tests

```text
test_intent_extractor.py
test_source_planner.py
test_registry_loader.py
test_result_validator.py
```

### 9.2. Integration tests

```text
test_query_dry_run.py
test_query_no_data.py
test_query_partial_vienna_rent.py
```

### 9.3. Critical assertions

```python
def test_vienna_rent_districts_is_partial():
    request = extractor.extract(
        "средняя аренда за метр в районах Вены с 1го по 9ый за последние 5 лет"
    )
    plan = planner.plan(request)
    assert plan.status == "partial"
    assert "vienna_district" in plan.selected_candidates[0].missing_dimensions
```

```python
def test_statcube_requires_auth_without_key():
    result = statcube_adapter.fetch(...)
    assert result.status == "auth_required"
```

```python
def test_validator_does_not_allow_fake_district_success():
    request.geo.districts = [1,2,3]
    raw_result.data[0].region = "Vienna"
    validated = validator.validate(raw_result, request, plan)
    assert validated.status == "partial"
    assert validated.metadata["granularity_match"] == "proxy"
```

---

## 10. Definition of Done

MVP считается готовым, если:

1. `/dry-run` работает для всех demo scenarios.
2. `/query` возвращает валидный JSON.
3. Источники берутся только из registry.
4. Для запроса по аренде в районах Вены возвращается `partial`, а не ложный `success`.
5. Для хотя бы одного статистического time series запроса возвращается настоящий `success`.
6. Для STATcube без ключа возвращается `auth_required`.
7. Для неподдерживаемого запроса возвращается `no_data`.
8. Все responses имеют `metadata.sources` и `metadata.limitations`, если результат не exact.
9. Sandbox ограничивает execution.
10. Unit/integration tests проходят.

---

## 11. Recommended implementation order

1. Schemas.
2. Registry loader.
3. Hardcoded datasets.
4. Intent extractor.
5. Source planner.
6. Dry-run API.
7. Result validator.
8. One working adapter: Eurostat or CSV/ODS.
9. Sandbox runner.
10. `/query` full path.
11. Add CKAN discovery.
12. Add WFS.
13. Add STATcube authenticated mode only if credentials are available.

---

## 12. Что не входит в MVP

Не делать на первом этапе:

- autonomous internet-wide search on every query;
- scraping real estate portals;
- dynamic package installation inside sandbox;
- paid STATcube access without explicit credentials;
- arbitrary code execution without templates;
- automatic guarantee that requested data exists;
- district-level rent estimation from listings unless legal/data source is separately approved.

---

## 13. Самый важный acceptance test

Запрос:

```text
мне нужно получить данные по средней цене на аренду за метр в районах Вены с 1го по 9ый за последние 5 лет
```

Корректный MVP response:

```json
{
  "status": "partial",
  "interpreted_request": {
    "domain": "housing",
    "metric": "average_rent",
    "unit": "eur_per_sqm_per_month",
    "geo": {
      "city": "Vienna",
      "districts": [1,2,3,4,5,6,7,8,9]
    },
    "time_range": {
      "last_years": 5
    }
  },
  "metadata": {
    "granularity_match": "proxy",
    "requested_geo": "Vienna districts 1-9",
    "returned_geo": "Vienna city/federal-state level if available",
    "limitations": [
      "No verified official open dataset with district-level rent time series for Vienna districts 1-9 was found in the MVP registry",
      "Returned data must not be interpreted as district-level rent data"
    ]
  },
  "data": []
}
```

Если adapter уже подключен к city-level source, `data` может быть непустым, но статус всё равно должен оставаться `partial`.

---

## 14. Notes for Codex

При имплементации не пытаться “улучшить” архитектуру через магический autonomous browsing. На первом этапе нужна надежная система с контролируемым registry и честными статусами.

Главная ценность MVP — не в том, что агент всегда находит данные, а в том, что он:

- понимает запрос;
- проверяет доступность данных;
- выбирает источник;
- выполняет воспроизводимый extraction;
- возвращает structured time series;
- честно сообщает, чего не хватает.
