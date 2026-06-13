# hotsalestotg 🔥

Телеграм-бот, который автоматически публикует горячие скидки с [pepper.pl](https://www.pepper.pl/najgoretsze) в канал [@rradom](https://t.me/rradom).

Основан на проекте [otmt](https://github.com/oriuma/otmt), переделан под pepper.pl.

## Как работает

1. GitHub Actions запускает скрипт каждые **15 минут**
2. Скрипт делает запрос к pepper.pl GraphQL API и получает список горячих предложений (`/najgoretsze`)
3. Фильтрует только сделки с температурой ≥ `MIN_TEMPERATURE` (по умолчанию 100°)
4. Публикует новые (ранее не отправленные) предложения в Telegram-канал с фото и деталями
5. Сохраняет ID уже отправленных предложений в `data/seen_ids.json`

## Структура проекта

```
hotsalestotg/
├── main.py                  # Основной скрипт (standalone)
├── requirements.txt
├── data/
│   └── seen_ids.json        # Состояние (автообновляется)
├── src/
│   ├── config.py            # Настройки из env vars
│   ├── pepper_client.py     # GraphQL клиент pepper.pl
│   ├── formatter.py         # Форматирование сообщений Telegram
│   ├── state.py             # Сохранение/загрузка состояния
│   └── telegram_client.py  # Отправка в Telegram
└── .github/
    └── workflows/
        └── pepper.yml       # GitHub Actions workflow
```

## Настройка

### 1. Secrets (Settings → Secrets → Actions)

| Secret | Значение |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен бота от @BotFather |
| `TELEGRAM_CHAT_ID` | `@rradom` или числовой ID канала |

### 2. Переменные окружения (опционально)

| Переменная | По умолчанию | Описание |
|---|---|---|
| `MIN_TEMPERATURE` | `100` | Минимальная температура сделки |
| `MAX_PAGES` | `3` | Кол-во страниц для парсинга |
| `TELEGRAM_SLEEP_SECONDS` | `0.5` | Пауза между сообщениями |

## Запуск локально

```bash
pip install requests
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_CHAT_ID=@rradom
python main.py
```
