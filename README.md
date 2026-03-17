# research

Основной сценарий в этом репозитории: `simple_aave_uni_vault` (Foundry + Anvil fork + bash-скрипты).

## Быстрый старт

```bash
cp .env-example .env
bash simple_aave_uni_vault/scripts/run_all.sh
```

Скрипты читают переменные из `.env` в корне репозитория.
Для совместимости поддерживается старое имя `.env.safe_setup`.
Можно явно задать файл: `ENV_FILE=./configs/mainnet.env bash simple_aave_uni_vault/scripts/run_all.sh`.

## Документация

- Подробно по запуску и env: `simple_aave_uni_vault/README.md`
- Архитектура контракта: `simple_aave_uni_vault/ARCHITECTURE.md`
- Кратко по скриптам: `simple_aave_uni_vault/scripts/README.md`
