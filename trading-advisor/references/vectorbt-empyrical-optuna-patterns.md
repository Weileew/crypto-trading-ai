# VectorBT + Empyrical Integration Patterns (2026-07-01)

## VectorBT Backtest Integration

### `signal_validator.backtest_vectorbt()`

Vectorized replacement for the custom iterative `backtest loop with stop/target/trailing stop logic.

```python
def backtest_vectorbt(candles, signal_date, entry, stop, target, max_candles=14):
    """
    Vectorized backtest using pandas operations.
    
    Args:
        candles: list of [ts, open, high, low, close]
        signal_date: 'YYYY-MM-DD'
        entry, stop, target: float prices
        max_candles: max holding period
    
    Returns dict with: exit_price, exit_reason, exit_date, entry_open, holding_candles
    """
    import pandas as pd
    
    df = pd.DataFrame(candles, columns=['ts', 'open', 'high', 'low', 'close'])
    df['date'] = pd.to_datetime(df['ts'], unit='ms').dt.date
    df = df[df['date'] > sig_dt].head(max_candles)
    
    # Vectorized exit logic
    stop_hits = df['low'] <= stop
    target_hits = df['high'] >= target
    exit_mask = stop_hits | target_hits
    
    if exit_mask.any():
        first_exit_idx = exit_mask.idxmax()
        # ... return exit details
    
    # Timeout
    return {'exit_reason': 'timeout', ...}
```

### Key Differences from Original

| Aspect | Original Loop | VectorBT/Pandas |
|--------|---------------|-----------------|
| Stop check | `if low <= stop:` | `df['low'] <= stop` (Series) |
| Target check | `if high >= target:` | `df['high'] >= target` |
| Trailing stop | Iterative price tracking | Not yet implemented in vectorized form |
| Speed | O(n) Python loop | O(n) C-optimized pandas |

### Fallback Pattern

```python
def backtest(candles, signal_date, entry, stop, target, max_candles=14):
    try:
        return backtest_vectorbt(candles, signal_date, entry, stop, target, max_candles)
    except Exception:
        # Fall back to original implementation
        pass
    # ... original loop implementation
```

---

## Empyrical Metrics Integration

### `signal_validator.summarize()`

Extended to include empyrical industry-standard metrics:

```python
def summarize(signals):
    returns = np.array([s.get('pnl_pct', 0) / 100 for s in validated])
    
    base_summary = { ... original fields ... }
    
    if len(returns) >= 5:
        base_summary.update({
            'sharpe_ratio': round(empyrical.sharpe_ratio(returns), 3),
            'max_drawdown': round(empyrical.max_drawdown(returns) * 100, 2),
            'calmar_ratio': round(empyrical.calmar_ratio(returns), 3),
            'sortino_ratio': round(empyrical.sortino_ratio(returns), 3),
            'omega_ratio': round(empyrical.omega_ratio(returns), 3),
            'annual_return': round(empyrical.annual_return(returns, period='daily') * 100, 2),
            'annual_volatility': round(empyrical.annual_volatility(returns) * 100, 2),
        })
    
    return base_summary
```

### `portfolio_engine.journal_performance()`

Same empyrical metrics added to portfolio-level performance:

```python
def journal_performance(days=30, exclude_sources=None):
    # ... existing logic ...
    returns = np.array([o[1] / 100 for o in outcomes if o[1] is not None])
    
    if len(returns) >= 5:
        base_perf.update({
            'sharpe_ratio': round(empyrical.sharpe_ratio(returns), 3),
            'max_drawdown': round(empyrical.max_drawdown(returns) * 100, 2),
            'calmar_ratio': round(empyrical.calmar_ratio(returns), 3),
            'sortino_ratio': round(empyrical.sortino_ratio(returns), 3),
            'omega_ratio': round(empyrical.omega_ratio(returns), 3),
            'annual_return': round(empyrical.annual_return(returns, period='daily') * 100, 2),
            'annual_volatility': round(empyrical.annual_volatility(returns) * 100, 2),
        })
```

### Metric Definitions

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **Sharpe Ratio** | `(mean - rf) / std` | Risk-adjusted return (rf=0 default) |
| **Max Drawdown** | `min(cumulative_peak - cumulative)` | Worst peak-to-trough loss |
| **Calmar Ratio** | `annual_return / max_drawdown` | Return per unit of max drawdown |
| **Sortino Ratio** | `(mean - rf) / downside_std` | Downside risk-adjusted return |
| **Omega Ratio** | `sum(wins) / sum(losses)` | Probability-weighted return ratio |
| **Annual Return** | `(1 + mean)^252 - 1` | Annualized mean return |
| **Annual Volatility** | `std * sqrt(252)` | Annualized volatility |

---

## Optuna Integration Patterns

### `parameter_optimizer.optimize_with_optuna()`

Walk-forward optimization of screening thresholds:

```python
def optimize_with_optuna(coins: list[dict], n_trials: int = 50) -> dict:
    def objective(trial):
        min_change = trial.suggest_float('min_24h_change_pct', 1.0, 8.0)
        score_thresh = trial.suggest_float('score_threshold', 10.0, 50.0)
        
        # Evaluate on historical coins
        passed = 0
        wins = 0
        for c in coins:
            s, ok = score_candidate(c, min_change=min_change, score_thresh=score_thresh)
            if ok:
                passed += 1
                p = c.get('price_change_percentage_7d_in_currency') or 0
                if p > 0:
                    wins += 1
        
        if passed == 0:
            return 0.0
        
        win_rate = wins / max(passed, 1)
        signal_bonus = min(passed / 20.0, 1.0)
        return win_rate * signal_bonus
    
    study = optuna.create_study(direction='maximize')
    study.optimize(objective, n_trials=n_trials)
    
    return {
        'best_params': study.best_params,
        'best_value': round(study.best_value, 4),
        'n_trials': len(study.trials),
    }
```

### `portfolio_engine.optimize_portfolio_params()`

Optimizes portfolio-level calibration parameters:

```python
def optimize_portfolio_params(n_trials=50) -> dict:
    def objective(trial):
        params = {
            'concurrency_max': trial.suggest_int('concurrency_max', 2, 5),
            'drawdown_limit_pct': trial.suggest_float('drawdown_limit_pct', 5.0, 20.0),
            'correlation_threshold': trial.suggest_float('correlation_threshold', 0.5, 0.9),
            'correlation_exposure_penalty': trial.suggest_float('correlation_exposure_penalty', 0.2, 0.8),
            'drawdown_sizing_reduction_pct': trial.suggest_float('drawdown_sizing_reduction_pct', 25.0, 75.0),
        }
        
        score = _evaluate_portfolio_params(params)
        return -score  # Optuna minimizes
    
    study = optuna.create_study(direction='minimize')
    study.optimize(objective, n_trials=n_trials)
    
    return {
        'best_params': study.best_params,
        'best_value': -study.best_value,
        'n_trials': len(study.trials),
    }
```

### Optuna Configuration

```python
# Create study with direction
study = optuna.create_study(direction='maximize')  # or 'minimize'

# Suggest parameters
trial.suggest_float('param_name', low, high)      # Continuous
trial.suggest_int('param_name', low, high)        # Integer
trial.suggest_categorical('param_name', [a, b, c]) # Categorical

# Optimize
study.optimize(objective, n_trials=50, show_progress_bar=False)

# Results
study.best_params
study.best_value
len(study.trials)
```

### Integration in Main Functions

```python
# parameter_optimizer.main()
optuna_result = optimize_with_optuna(coins, n_trials=50)
# Adds to recommendations:
# "Optuna optimization: min_24h_change_pct=2.5%, score_threshold=15 (composite score: 0.450)"
```

---

## Testing Patterns

```python
# Quick verification
import vectorbt as vbt
import empyrical
import optuna

# VectorBT
close = pd.Series(np.random.randn(100).cumsum() + 100, index=pd.date_range('2024-01-01', periods=100, freq='1h'))
entries = pd.Series([False]*50 + [True] + [False]*49, index=close.index)
exits = pd.Series([False]*70 + [True] + [False]*29, index=close.index)
pf = vbt.Portfolio.from_signals(close, entries, exits)
print(f'Sharpe: {pf.sharpe_ratio():.2f}, Max DD: {pf.max_drawdown():.2%}')

# Empyrical
returns = np.random.randn(252) * 0.01 + 0.0005
print(f'Sharpe: {empyrical.sharpe_ratio(returns):.2f}')
print(f'Max DD: {empyrical.max_drawdown(returns):.2%}')

# Optuna
study = optuna.create_study(direction='maximize')
study.optimize(lambda t: -(t.suggest_float('x', -5, 5) - 2)**2, n_trials=20)
print(f'Best x: {study.best_params["x"]:.4f}')
```