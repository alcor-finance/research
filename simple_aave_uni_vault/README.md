# Simple Aave + Uniswap Vault (Fork)

Сценарий поднимает `anvil` fork Ethereum mainnet, деплоит `ManagerAaveUniVault`, пополняет vault, выполняет стратегию `Aave supply/borrow + Uniswap swap` и проверяет доступы `manager/depositor`.

## Зависимости

Нужны: `anvil`, `forge`, `cast`, `jq`, `curl`, `python`, `lsof`, `pkill`.

Проверка:

```bash
anvil --version
forge --version
cast --version
jq --version
python --version
```

## Конфиг

Приоритет env-файлов:

1. `ENV_FILE=/path/to/file` (если передан явно)
2. `.env` в корне репозитория
3. `.env.safe_setup` в корне репозитория (fallback для старого имени)

Быстро подготовить локальный конфиг:

```bash
cp .env-example .env
```

Пример запуска с явным конфигом:

```bash
ENV_FILE=./configs/mainnet.env bash simple_aave_uni_vault/scripts/run_all.sh
```

Обязательные переменные:

- `MAINNET_RPC_URL`: RPC endpoint mainnet (Alchemy/Infura/свой узел).
- `FORK_BLOCK`: номер блока, на котором форкать сеть.
- `SAFE_OWNER_1`: EOA-адрес для роли `depositor` по умолчанию.
- `ZODIAC_MANAGER`: EOA-адрес для роли `manager` по умолчанию.
- `AAVE_POOL_ADDRESS`: адрес Aave V3 Pool в выбранной сети.
- `UNISWAP_V3_SWAP_ROUTER`: адрес Uniswap V3 SwapRouter в выбранной сети.
- `WBTC_TOKEN`: адрес ERC20 токена, которым будете фондить и supply.
- `AAVE_COLLATERAL_ASSET_WBTC`: адрес collateral-актива для `aaveSupply` (обычно тот же, что `WBTC_TOKEN`).
- `AAVE_BORROW_ASSET_USDC`: адрес ERC20 токена для `aaveBorrow`/`swap`.
- `WBTC_WHALE`: адрес с достаточным балансом WBTC на `FORK_BLOCK` (подойдет любой rich-holder).
- `WHITELIST_6TH_WALLET_ADDRESS`: адрес получателя для позитивного теста `managerWithdraw*`.

Часто используемые опциональные:

- `ANVIL_RPC_URL` (default `http://127.0.0.1:8545`)
- `DEPLOYER_PK` (default private key аккаунта #0 в Anvil)
- `DEPOSITOR_ADDRESS`, `MANAGER_ADDRESS` (override ролей)
- `FUND_ETH_TO_VAULT`, `FUND_WBTC_TO_VAULT`
- `SUPPLY_WBTC`, `BORROW_USDC`, `SWAP_USDC_IN`
- `MANAGER_WITHDRAW_USDC`, `DEPOSITOR_WITHDRAW_USDC`
- `NON_WHITELIST_ADDRESS` (должен отличаться от whitelist-адресов)
- `DEPOSITOR_WITHDRAW_TARGET` (куда выводить в тесте `depositorWithdraw*`)
- `SAFE_OWNER_2` (используется как fallback-цель, если `DEPOSITOR_WITHDRAW_TARGET` не задан)

Требования к адресам:

- Формат: `0x` + 40 hex-символов.
- Для ролей (`SAFE_OWNER_1`, `ZODIAC_MANAGER`) используйте обычные EOA-адреса.
- Для протокольных адресов (`AAVE_*`, `UNISWAP_*`, `WBTC_TOKEN`) в `.env-example` стоят заглушки, их обязательно заменить на реальные адреса сети.

## Запуск

Из корня репозитория:

```bash
bash simple_aave_uni_vault/scripts/run_all.sh
```

`run_all.sh` делает:

1. Останавливает прошлый `anvil` (если был).
2. Поднимает новый fork.
3. Деплоит `ManagerAaveUniVault`.
4. Выполняет funding + strategy + access checks.
5. Останавливает `anvil` в `trap` при выходе.

По шагам вручную:

```bash
bash simple_aave_uni_vault/scripts/01_start_fork.sh
bash simple_aave_uni_vault/scripts/02_deploy_contract.sh
bash simple_aave_uni_vault/scripts/03_fund_from_whale.sh
bash simple_aave_uni_vault/scripts/04_run_strategy_flow.sh
bash simple_aave_uni_vault/scripts/05_access_control_checks.sh
bash simple_aave_uni_vault/scripts/06_stop_fork.sh
```

## Логика ролей

- Все выводы токенов идут из баланса `vault`, не из баланса инициатора.
- `managerWithdrawToken/ETH` разрешены только на whitelist-адреса.
- `depositorWithdrawToken/ETH` не ограничены whitelist.
- Для strategy-методов (`aave*`, `uniswap*`) оператором может быть и `manager`, и `depositor` (`onlyOperator`).

## Артефакты

Папка `simple_aave_uni_vault/.runtime`:

- `anvil.log`
- `anvil.pid`
- `deploy.env`

## Типовые ошибки

- `execution reverted: STF` на swap: обычно в `vault` недостаточно USDC или состояние форка "грязное"; перезапустить через `run_all.sh`.
- `missing env var`: не заполнена обязательная переменная в env-файле (`.env` / `.env.safe_setup` / `ENV_FILE`).
- `missing command`: не установлен нужный инструмент.
