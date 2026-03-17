# Simple Aave+Uniswap Vault Scripts

Детальная документация: `../README.md`.

Основной запуск (из корня репозитория):

```bash
cp .env-example .env
bash simple_aave_uni_vault/scripts/run_all.sh
```

По умолчанию читается `.env`, fallback: `.env.safe_setup`, либо явный путь через `ENV_FILE=...`.

`run_all.sh` выполняет:

1. Start Anvil mainnet fork.
2. Deploy `ManagerAaveUniVault`.
3. Fund vault from whale with ETH + WBTC.
4. Execute strategy flow: Aave supply -> Aave borrow -> Uniswap swap.
5. Execute access checks:
   - manager withdraw to whitelist (pass)
   - manager withdraw to non-whitelist (revert expected)
   - depositor withdraw to arbitrary address (pass)

Остановить fork вручную:

```bash
bash simple_aave_uni_vault/scripts/06_stop_fork.sh
```
