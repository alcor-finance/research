# Архитектура (упрощенный vault)

## Контракты и зоны ответственности

- `src/core/VaultAccess.sol`
  - контроль ролей: `DEPOSITOR`, `manager`
  - whitelist для manager-вывода
  - базовые guard/modifier и ETH transfer helper

- `src/modules/AaveModule.sol`
  - хранит `aavePool`
  - операции: `supply / borrow / repay / withdraw`
  - событие и админ-обновление пула

- `src/modules/UniswapV3Module.sol`
  - хранит `uniswapV3Router`
  - операция `exactInputSingle`
  - событие и админ-обновление роутера

- `src/lib/SafeERC20Ops.sol`
  - безопасные ERC20 операции (`transfer`, `transferFrom`, `forceApprove`)

- `src/ManagerAaveUniVault.sol`
  - тонкий orchestration-слой
  - связывает модули и открывает внешний API
  - депозит/вывод + вызовы модулей

## Правила доступа

- `depositor`
  - может менять manager/whitelist/router/pool
  - может выводить токены/ETH на любой адрес

- `manager`
  - может запускать strategy actions (Aave/Uniswap)
  - может выводить только на whitelisted адреса

## Проверка

Сценарий проверки запускается через:

```bash
bash simple_aave_uni_vault/scripts/run_all.sh
```
