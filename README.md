# LeadPipe

**Из поисковой выдачи — в персональное сообщение в форме на сайте. Автоматически.**

Playwright собирает лиды из Google, Yandex и Яндекс.Карт.  
LLM отсеивает мусор и пишет текст под конкретный сайт.  
Playwright снова — заполняет лучшую форму и отправляет.

```
поиск → enrich → форма → qualify → outreach → submit
```

FastAPI · Supabase · прокси + Apify fallback · LLM · n8n · Swagger

---

## Возможности

- **SERP & Maps** — Google, Yandex, Яндекс.Карты; batch по городам из `data/cities.json`
- **Enrichment** — email, телефоны, мессенджеры, флаги форм/виджетов, `raw_text`
- **Формы** — все `<form>` на сайте → одна лучшая с CSS-селекторами и `purpose` полей
- **LLM** — квалификация лида + персонализированный outreach-текст
- **Submit** — автозаполнение формы; `dry_run` для безопасных тестов
- **Pipeline** — весь цикл одним `POST /pipeline/site/{id}` или batch + cron в n8n

---

## Быстрый старт

### 1. Установка

```powershell
git clone <repo-url> playWright_scr
cd playWright_scr
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Chrome из системы используется по умолчанию (`BROWSER_CHANNEL = "chrome"`).  
Bundled Chromium: `python -m playwright install chromium`

### 2. База и `.env`

1. SQL из `bd_structure.md` → Supabase SQL Editor  
2. Миграции: `migrations/001_site_forms.sql`, `migrations/002_llm_qualify.sql`  
3. `.env.example` → `.env`:

```env
DATABASE_URL=postgresql://...
OPENAI_API_KEY=sk-...          # OpenAI-compatible API
OPENAI_MODEL=gpt-4o-mini
PROXY_LIST=                    # опционально
APIFY_API_TOKEN=               # опционально
```

### 3. Запуск

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# или: .\run.bat
```

Swagger: **http://127.0.0.1:8000/docs**  
Проверка: `GET /health` → `database_configured`, `llm_configured`

### 4. Один сайт — полный цикл

`site_id` возьмите из `GET /sites` или после поиска с `save_to_db: true`.

```json
POST /pipeline/site/{site_id}
{
  "offer_description": "Помогаем стоматологиям получать больше заявок через SEO.",
  "sender_name": "Иван Петров",
  "sender_company": "Dental Marketing",
  "sender_phone": "+7 (999) 123-45-67",
  "sender_email": "ivan@example.com",
  "dry_run_submit": true,
  "headless": true,
  "skip_unqualified": true
}
```

`dry_run_submit: true` — заполнит форму **без** клика Submit. Для боевой отправки: `false`.

### 5. Batch: поиск + N сайтов

```json
POST /pipeline/batch
{
  "search_query": "стоматология",
  "search_cities": ["Казань"],
  "search_max_pages": 1,
  "sites_limit": 5,
  "scrape_status": "pending",
  "offer_description": "...",
  "sender_name": "Иван Петров",
  "sender_company": "Dental Marketing",
  "dry_run_submit": true
}
```

Без `search_query` — обработает уже существующие сайты в БД.

---

## Пайплайн данных

```
search_queries → search_runs → sites → serp_results
                                    ↓
                            site_enrichments (+ llm_*)
                                    ↓
                              site_forms (1 лучшая)
                                    ↓
                              site_outreach
```

| Этап | Эндпойнт | Результат |
|------|----------|-----------|
| Поиск | `POST /search/google` · `/yandex` · `/yandex-maps` | Сайты в БД |
| Batch | `POST /search/{source}/batch` | Несколько городов |
| Enrich | `POST /enrich/sites` · `/enrich/site/{id}` | Контакты, `raw_text` |
| Формы | `POST /forms/collect` · `/forms/collect/site/{id}` | 1 форма / сайт |
| Qualify | `POST /outreach/qualify` | `llm_is_fit`, `llm_fit_score` |
| Outreach | `POST /outreach/generate` | `message_text` → `site_outreach` |
| Submit | `POST /outreach/submit/site/{id}` | Заполнение + отправка |
| **Всё** | `POST /pipeline/site/{id}` · `/pipeline/batch` | Цикл целиком |

Список: `GET /sites` · `GET /forms` · `GET /outreach`

---

## Поиск

### Google / Yandex

```json
POST /search/google
{
  "query": "стоматология",
  "city": "Казань",
  "max_pages": 2,
  "headless": true,
  "save_to_db": true
}
```

Yandex: `POST /search/yandex` — тот же формат.  
Batch: `POST /search/google/batch` · `POST /search/yandex/batch`

```json
{
  "query": "стоматология",
  "cities": ["Москва", "Казань"],
  "max_pages": 2,
  "save_to_db": true
}
```

Справочник городов: `GET /cities` · все города: `"use_all_cities": true`

### Яндекс.Карты

Кликает карточки, читает **внешний сайт** из детальной панели.

```json
POST /search/yandex-maps
{
  "query": "стоматология",
  "city": "Москва",
  "max_pages": 3,
  "save_to_db": true
}
```

В `snippet` — адрес и телефон. Batch: `POST /search/yandex-maps/batch`

---

## LLM Outreach

Требует `OPENAI_API_KEY` и миграцию `002_llm_qualify.sql`.

**Квалификация** — отсекает агрегаторы, блоги, нерелевант:

```json
POST /outreach/qualify
{
  "limit": 10,
  "target_query": "стоматология",
  "target_description": "стоматологическая клиника"
}
```

**Генерация** — персональный текст в `site_outreach`:

```json
POST /outreach/generate
{
  "limit": 5,
  "offer_description": "Помогаем стоматологиям...",
  "sender_name": "Иван Петров",
  "sender_company": "Dental Marketing",
  "auto_qualify": true,
  "skip_unqualified": true
}
```

**Form-fill** — `{selector, value}` для нестандартных полей:

`POST /outreach/form-fill/site/{site_id}`

**Submit** — заполнение + клик (или dry-run):

```json
POST /outreach/submit/site/{site_id}
{
  "sender_name": "Иван Петров",
  "sender_phone": "+7 (999) 123-45-67",
  "sender_email": "ivan@example.com",
  "dry_run": true
}
```

Формы с капчей → `sent_status: skipped`.

---

## n8n

Главный workflow: **`n8n/unified-pipeline.json`** — Manual · Schedule · Webhook, три режима запуска, Google Sheets.

Legacy-файлы в `n8n/` тоже можно импортировать. Подробнее: [`n8n/README.md`](n8n/README.md)

---

## Прокси и Apify

```env
PROXY_LIST=http://user:pass@proxy1:8000,http://user:pass@proxy2:8000
PROXY_USE_DIRECT=true
APIFY_API_TOKEN=apify_api_...
APIFY_FALLBACK_THRESHOLD=5
```

1. CAPTCHA/блок → следующий прокси  
2. Все прокси заблокированы 5 раз подряд → **Apify** (если есть токен)  
3. В ответе: `scrape_source` (`playwright` / `apify`), `proxy_server`

Actors: `apify/google-search-scraper` · `johnvc/Scrape-Yandex` · `zen-studio/yandex-maps-scraper`

---

## CLI

```powershell
python run_search.py "стоматология" "Казань" --max-pages 2
python run_search.py "стоматология" "Казань" --headed
```

---

## Стек

| | |
|---|---|
| API | FastAPI, Pydantic, Swagger |
| Scrape | Playwright (Chrome), proxy rotation |
| Fallback | Apify actors |
| DB | Supabase / PostgreSQL |
| LLM | OpenAI-compatible API, structured JSON |
| Orchestration | n8n (опционально) |

---

## Ограничения

- Google/Yandex могут показать CAPTCHA — используйте прокси, `headless: false` или Apify
- Apify — платный сервис
- Автосабмит не обходит капчу на формах
- Соблюдайте robots.txt, GDPR и антиспам-законы вашей юрисдикции

---

## License

[MIT](LICENSE) — свободно использовать, форкать и встраивать в другие проекты.
