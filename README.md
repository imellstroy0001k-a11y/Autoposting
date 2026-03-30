# Social Video Poster

Отдельный автозаливщик видео для YouTube и TikTok.

Что умеет:
- держать хоть 7 аккаунтов, хоть больше;
- раз в 4 часа выкладывать по 1 новому видео на каждый аккаунт;
- брать видео из папки, которую ты сам наполняешь;
- не повторять уже опубликованные видео;
- вести состояние в `SQLite`, чтобы не терять очередь после перезапуска.

## Как работает

1. Ты кладёшь видео в папку `videos/youtube` или `videos/tiktok`.
2. Скрипт раз в цикл смотрит, для какого аккаунта уже прошло 4 часа.
3. Для каждого такого аккаунта он берёт следующий ещё неиспользованный ролик.
4. После успешной публикации ролик помечается как использованный и больше не берётся повторно.

По умолчанию dedupe глобальный:
- если ролик уже ушёл на один аккаунт, на другой он больше не пойдёт.

## Структура

- `config.example.toml` — пример конфига.
- `state.sqlite3` — база состояния, создаётся автоматически.
- `videos/` — папка для роликов.
- `social_video_poster/` — код.

## Быстрый старт

```bash
cd /Users/temp/Documents/Playground/Autoposting
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.toml config.toml
python -m social_video_poster list-pending --config config.toml
python -m social_video_poster run --config config.toml
```

Если сейчас нужен только TikTok:

```bash
cp config.tiktok.example.toml config.toml
```

Для 7 аккаунтов:
- просто дублируй блок `[[accounts]]` в `config.toml`;
- у каждого аккаунта должен быть свой `id` и свой набор токенов;
- если все 7 аккаунтов должны брать ролики из одной общей очереди, оставь им один и тот же `video_dir`.

## Формат видео

Видео кладутся в папку аккаунта или общую папку платформы:

- `./videos/youtube`
- `./videos/tiktok`

Поддерживаемые расширения:
- `.mp4`
- `.mov`
- `.m4v`
- `.webm`

## Sidecar-файлы

Для каждого видео можно положить рядом:

- `video_name.txt` — описание
- `video_name.json` — метаданные

Пример `video_name.json`:

```json
{
  "title": "Мой заголовок",
  "description": "Описание ролика",
  "tags": ["tag1", "tag2"]
}
```

## Важные замечания

### YouTube

Нужно:
- Google Cloud OAuth client;
- scope `youtube.upload`;
- отдельный refresh token на каждый аккаунт.

### TikTok

Нужно:
- TikTok app с доступом к Content Posting API;
- scope `video.publish`;
- refresh token на каждый аккаунт.

Для TikTok скрипт использует Direct Post через официальный API. Если у приложения нет нужного уровня доступа, TikTok может ограничить публикации приватным режимом.

Практический рабочий сценарий для 7 аккаунтов:
- создаёшь одно TikTok app в TikTok for Developers;
- подключаешь Login Kit и Content Posting API;
- для каждого из 7 аккаунтов один раз проходишь OAuth и получаешь `refresh_token`;
- вставляешь эти 7 `refresh_token` в `config.toml`;
- после этого scheduler сам сможет обновлять `access_token` и публиковать дальше без ручного логина каждый цикл.

Helper для OAuth уже добавлен:

```bash
python -m social_video_poster.tiktok_oauth auth-url \
  --client-key YOUR_CLIENT_KEY \
  --redirect-uri https://your-domain.com/tiktok/callback \
  --state acc1
```

После возврата `code` с твоего `redirect_uri`:

```bash
python -m social_video_poster.tiktok_oauth exchange-code \
  --client-key YOUR_CLIENT_KEY \
  --client-secret YOUR_CLIENT_SECRET \
  --redirect-uri https://your-domain.com/tiktok/callback \
  --code PASTE_CODE_HERE
```

И если нужно вручную освежить токен:

```bash
python -m social_video_poster.tiktok_oauth refresh-token \
  --client-key YOUR_CLIENT_KEY \
  --client-secret YOUR_CLIENT_SECRET \
  --refresh-token YOUR_REFRESH_TOKEN
```

Ещё удобнее для desktop-сценария без отдельного сайта:

```bash
python -m social_video_poster.tiktok_bootstrap \
  --client-key YOUR_CLIENT_KEY \
  --client-secret YOUR_CLIENT_SECRET \
  --account-id tiktok_1
```

Этот helper:
- поднимет локальный callback на `http://127.0.0.1:8765/callback/`;
- откроет окно авторизации TikTok;
- поймает `code`;
- сам обменяет его на токены;
- сохранит JSON в `runtime/tiktok_tokens/tiktok_1.json`.

Сейчас скрипт уже умеет читать `tiktok_token_file` напрямую, так что можно вообще не копировать токены руками: просто укажи путь к JSON в `config.toml`.

## Полезные команды

Посмотреть, какой ролик пойдёт следующим:

```bash
python -m social_video_poster list-pending --config config.toml
```

Сделать один прогон без вечного цикла:

```bash
python -m social_video_poster run-once --config config.toml
```

Запустить постоянный scheduler:

```bash
python -m social_video_poster run --config config.toml
```

Фоновый запуск через `tmux`:

```bash
cd /Users/temp/Documents/Playground/Autoposting
tmux new-session -d -s social_poster './.venv/bin/python -m social_video_poster run --config config.toml'
tmux attach -t social_poster
```
