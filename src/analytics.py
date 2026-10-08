"""Market analytics: returns, volatility, drawdown, curve and FX moves."""
import numpy as np
import pandas as pd

TRADING_DAYS = 252


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Simple daily returns: today / yesterday - 1. The first day has no return, so it is dropped."""
    return prices.pct_change().dropna()


def annualised_volatility(returns: pd.DataFrame) -> pd.Series:
    """Standard deviation of daily returns, scaled to one year with sqrt(252)."""
    return returns.std() * np.sqrt(TRADING_DAYS)


def rolling_volatility(returns: pd.DataFrame, window: int = 21) -> pd.DataFrame:
    """Annualised volatility over a moving window (21 trading days = about one month)."""
    return returns.rolling(window).std() * np.sqrt(TRADING_DAYS)
def drawdown(prices: pd.DataFrame) -> pd.DataFrame:
    """How far each price is below its highest level so far (0 = at a peak, -0.10 = 10% below)."""
    running_peak = prices.cummax()
    return prices / running_peak - 1


def max_drawdown(prices: pd.DataFrame) -> pd.Series:
    """The worst fall from a peak over the whole period (a negative number)."""
    return drawdown(prices).min()


def correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """How strongly daily returns move together: +1 same direction, 0 unrelated, -1 opposite."""
    return returns.corr()
def curve_changes_bp(curves: pd.DataFrame) -> pd.DataFrame:
    """Daily change of each yield, in basis points (yields are stored in %)."""
    return (curves.diff() * 100).dropna()


def curve_spread_bp(curves: pd.DataFrame, long: str = "10Y", short: str = "2Y") -> pd.Series:
    """Long yield minus short yield, in basis points. Positive = normal curve, negative = inverted."""
    return (curves[long] - curves[short]) * 100


def curve_shape(spread_bp: pd.Series) -> pd.Series:
    """Label each day's curve as 'normal' or 'inverted' from the spread."""
    return pd.Series(np.where(spread_bp >= 0, "normal", "inverted"), index=spread_bp.index)


def pip_size(pair: str) -> float:
    """1 pip = 0.01 for JPY pairs, 0.0001 for most others."""
    return 0.01 if "JPY" in pair else 0.0001


def fx_moves_pips(fx: pd.DataFrame) -> pd.DataFrame:
    """Daily change of each FX rate, in pips."""
    changes = fx.diff().dropna()
    return changes.apply(lambda col: col / pip_size(col.name))
