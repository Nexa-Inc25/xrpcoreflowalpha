"""
Fine-tuned Prophet Forecasting Engine for Dark Flow Prediction
Includes Neural Prophet integration and hyperparameter optimization
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics
import logging
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

# Try to import Neural Prophet (optional enhancement)
try:
    from neuralprophet import NeuralProphet
    NEURAL_PROPHET_AVAILABLE = True
except ImportError:
    NEURAL_PROPHET_AVAILABLE = False
    logger.warning("Neural Prophet not available - using standard Prophet only")


class TunedProphetForecaster:
    """
    Fine-tuned Prophet model for multi-asset dark flow forecasting
    Optimized for crypto volatility and cross-market correlations
    """
    
    def __init__(self, 
                 use_neural: bool = False,
                 optimization_metric: str = 'mape'):
        
        self.use_neural = use_neural and NEURAL_PROPHET_AVAILABLE
        self.optimization_metric = optimization_metric
        
        # Hyperparameter search space
        self.param_grid = {
            'changepoint_prior_scale': [0.001, 0.01, 0.05, 0.1, 0.5],
            'seasonality_prior_scale': [0.01, 0.1, 1.0, 10.0],
            'seasonality_mode': ['additive', 'multiplicative'],
            'changepoint_range': [0.8, 0.85, 0.9, 0.95],
            'n_changepoints': [15, 25, 35, 50]
        }
        
        # Crypto-specific seasonalities
        self.crypto_seasonalities = {
            'hourly': {'period': 1/24, 'fourier_order': 3},
            'four_hourly': {'period': 4/24, 'fourier_order': 2},
            'daily': {'period': 1, 'fourier_order': 5},
            'weekly': {'period': 7, 'fourier_order': 3},
            'monthly': {'period': 30.5, 'fourier_order': 2}
        }
        
        # Market events and holidays
        self.market_events = self._create_market_events()
        
        # Best parameters cache
        self.best_params = {}
        self.models = {}
        
    def _create_market_events(self) -> pd.DataFrame:
        """
        Create custom holidays/events for crypto markets
        """
        events = []
        
        # Major crypto events
        events.extend([
            {'holiday': 'btc_halving', 'ds': '2024-04-20', 'lower_window': -30, 'upper_window': 30},
            {'holiday': 'eth_merge', 'ds': '2022-09-15', 'lower_window': -14, 'upper_window': 14},
            {'holiday': 'options_expiry', 'ds': '2025-01-31', 'lower_window': -2, 'upper_window': 2},
            {'holiday': 'quarterly_futures', 'ds': '2025-03-28', 'lower_window': -3, 'upper_window': 3},
        ])
        
        # Add monthly options expiries (last Friday of each month)
        for year in [2024, 2025]:
            for month in range(1, 13):
                last_friday = self._get_last_friday(year, month)
                events.append({
                    'holiday': 'monthly_options',
                    'ds': last_friday.strftime('%Y-%m-%d'),
                    'lower_window': -1,
                    'upper_window': 1
                })
        
        return pd.DataFrame(events)
    
    def _get_last_friday(self, year: int, month: int) -> datetime:
        """Get last Friday of a month"""
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        last_date = datetime(year, month, last_day)
        
        while last_date.weekday() != 4:  # Friday
            last_date -= timedelta(days=1)
        
        return last_date
    
    def optimize_hyperparameters(self, 
                                  df: pd.DataFrame,
                                  horizon: str = '24 hours',
                                  initial: str = '7 days',
                                  period: str = '1 days') -> Dict:
        """
        Grid search with cross-validation for optimal hyperparameters
        """
        best_score = float('inf') if self.optimization_metric in ['mae', 'mape', 'rmse'] else -float('inf')
        best_params = {}
        
        # Sample parameter combinations (full grid search would be too slow)
        n_samples = 20
        param_combinations = self._sample_param_combinations(n_samples)
        
        for i, params in enumerate(param_combinations):
            logger.info(f"Testing parameter combination {i+1}/{n_samples}")
            
            try:
                # Create model with current parameters
                model = self._create_prophet_model(**params)
                
                # Fit model
                model.fit(df)
                
                # Cross-validation
                df_cv = cross_validation(
                    model,
                    initial=initial,
                    period=period,
                    horizon=horizon,
                    parallel="threads"
                )
                
                # Calculate metrics
                df_p = performance_metrics(df_cv)
                score = df_p[self.optimization_metric].mean()
                
                # Update best parameters
                if self.optimization_metric in ['mae', 'mape', 'rmse']:
                    if score < best_score:
                        best_score = score
                        best_params = params
                else:
                    if score > best_score:
                        best_score = score
                        best_params = params
                
            except Exception as e:
                logger.warning(f"Failed to evaluate parameters {params}: {e}")
                continue
        
        self.best_params = best_params
        logger.info(f"Best parameters: {best_params}, Score: {best_score}")
        
        return {
            'best_params': best_params,
            'best_score': float(best_score),
            'metric': self.optimization_metric
        }
    
    def _sample_param_combinations(self, n_samples: int) -> List[Dict]:
        """Sample parameter combinations for grid search"""
        import itertools
        import random
        
        # Generate all combinations
        keys = list(self.param_grid.keys())
        values = [self.param_grid[k] for k in keys]
        all_combinations = list(itertools.product(*values))
        
        # Sample if too many
        if len(all_combinations) > n_samples:
            sampled = random.sample(all_combinations, n_samples)
        else:
            sampled = all_combinations
        
        # Convert to dict format
        param_dicts = []
        for combo in sampled:
            param_dict = {keys[i]: combo[i] for i in range(len(keys))}
            param_dicts.append(param_dict)
        
        return param_dicts
    
    def _create_prophet_model(self, **params) -> Prophet:
        """Create Prophet model with given parameters"""
        # Default parameters
        model_params = {
            'changepoint_prior_scale': 0.05,
            'seasonality_prior_scale': 10.0,
            'seasonality_mode': 'multiplicative',
            'changepoint_range': 0.9,
            'n_changepoints': 25,
            'yearly_seasonality': False,
            'weekly_seasonality': True,
            'daily_seasonality': True,
            'holidays': self.market_events
        }
        
        # Update with provided parameters
        model_params.update(params)
        
        # Create model
        model = Prophet(**model_params)
        
        # Add custom seasonalities
        for name, config in self.crypto_seasonalities.items():
            model.add_seasonality(
                name=name,
                period=config['period'],
                fourier_order=config['fourier_order']
            )
        
        return model
    
    def create_neural_prophet(self, **params) -> 'NeuralProphet':
        """Create Neural Prophet model with deep learning layers"""
        if not NEURAL_PROPHET_AVAILABLE:
            raise ImportError("Neural Prophet not installed")
        
        model_params = {
            'n_forecasts': 24,  # 24 hour ahead forecast
            'n_lags': 168,      # 7 days of hourly lags
            'yearly_seasonality': False,
            'weekly_seasonality': True,
            'daily_seasonality': True,
            'batch_size': 64,
            'epochs': 100,
            'learning_rate': 0.01,
            'num_hidden_layers': 2,
            'hidden_units': 64
        }
        
        model_params.update(params)
        
        model = NeuralProphet(**model_params)
        
        # Add custom seasonalities
        for name, config in self.crypto_seasonalities.items():
            model.add_seasonality(
                name=name,
                period=config['period'],
                fourier_order=config['fourier_order']
            )
        
        return model
    
    def forecast_with_confidence(self,
                                  df: pd.DataFrame,
                                  periods: int = 24,
                                  confidence_level: float = 0.95,
                                  use_optimized: bool = True) -> pd.DataFrame:
        """
        Generate forecasts with confidence intervals
        """
        # Use optimized parameters if available
        if use_optimized and self.best_params:
            model = self._create_prophet_model(**self.best_params)
        else:
            model = self._create_prophet_model()
        
        # Fit model
        model.fit(df)
        
        # Create future dataframe
        future = model.make_future_dataframe(periods=periods, freq='H')
        
        # Generate forecast
        forecast = model.predict(future)
        
        # Add custom confidence metrics
        forecast['confidence_score'] = self._calculate_confidence_score(
            forecast, confidence_level
        )
        
        # Add trend strength
        forecast['trend_strength'] = self._calculate_trend_strength(forecast)
        
        # Store model for later use
        self.models['latest'] = model
        
        return forecast
    
    def multi_asset_correlation_forecast(self,
                                          xrp_df: pd.DataFrame,
                                          btc_df: pd.DataFrame,
                                          eth_df: pd.DataFrame,
                                          spy_df: pd.DataFrame,
                                          periods: int = 24) -> Dict:
        """
        Forecast with cross-asset correlations for XRP migration prediction
        """
        forecasts = {}
        
        # Forecast each asset
        for name, df in [('XRP', xrp_df), ('BTC', btc_df), ('ETH', eth_df), ('SPY', spy_df)]:
            if self.use_neural and NEURAL_PROPHET_AVAILABLE:
                model = self.create_neural_prophet()
                model.fit(df, freq='H')
                future = model.make_future_dataframe(df, periods=periods)
                forecast = model.predict(future)
            else:
                forecast = self.forecast_with_confidence(df, periods=periods)
            
            forecasts[name] = forecast
        
        # Calculate correlation predictions
        correlations = self._predict_correlations(forecasts)
        
        # Identify XRP migration signals
        migration_signals = self._identify_migration_signals(forecasts, correlations)
        
        return {
            'forecasts': forecasts,
            'correlations': correlations,
            'migration_signals': migration_signals,
            'xrp_dominance_score': self._calculate_xrp_dominance(forecasts),
            'manipulation_risk': self._assess_manipulation_risk(forecasts)
        }
    
    def _calculate_confidence_score(self, forecast: pd.DataFrame, confidence_level: float) -> np.ndarray:
        """Calculate confidence score based on prediction intervals"""
        yhat = forecast['yhat'].values
        yhat_lower = forecast['yhat_lower'].values
        yhat_upper = forecast['yhat_upper'].values
        
        # Confidence based on interval width (narrower = more confident)
        interval_width = yhat_upper - yhat_lower
        mean_width = np.mean(interval_width)
        
        # Normalize to 0-1 scale (inverse of width)
        confidence = 1.0 - (interval_width / (2 * mean_width))
        confidence = np.clip(confidence, 0, 1)
        
        return confidence
    
    def _calculate_trend_strength(self, forecast: pd.DataFrame) -> np.ndarray:
        """Calculate strength of trend component"""
        trend = forecast['trend'].values
        trend_change = np.diff(trend, prepend=trend[0])
        
        # Rolling window for smoothing
        window = 24  # 24 hour window
        trend_strength = pd.Series(trend_change).rolling(window, min_periods=1).mean().abs()
        
        # Normalize to 0-1
        max_strength = trend_strength.max()
        if max_strength > 0:
            trend_strength = trend_strength / max_strength
        
        return trend_strength.values
    
    def _predict_correlations(self, forecasts: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """Predict future correlations between assets"""
        correlations = {}
        
        # Get forecast values
        forecast_values = {
            name: forecast['yhat'].values[-24:]  # Last 24 hours of forecast
            for name, forecast in forecasts.items()
        }
        
        # Calculate pairwise correlations
        for asset1 in forecast_values:
            for asset2 in forecast_values:
                if asset1 < asset2:
                    corr = np.corrcoef(
                        forecast_values[asset1],
                        forecast_values[asset2]
                    )[0, 1]
                    
                    correlations[f"{asset1}-{asset2}"] = float(corr) if not np.isnan(corr) else 0.0
        
        # Special focus on XRP correlations
        xrp_correlations = {
            k: v for k, v in correlations.items() if 'XRP' in k
        }
        
        correlations['xrp_average_correlation'] = np.mean(list(xrp_correlations.values()))
        
        return correlations
    
    def _identify_migration_signals(self, 
                                     forecasts: Dict[str, pd.DataFrame],
                                     correlations: Dict[str, float]) -> List[Dict]:
        """Identify signals indicating flow migration to XRP"""
        signals = []
        
        # Check for divergence patterns (XRP rising while others fall)
        xrp_trend = forecasts['XRP']['trend'].values[-24:]
        btc_trend = forecasts['BTC']['trend'].values[-24:]
        eth_trend = forecasts['ETH']['trend'].values[-24:]
        
        xrp_rising = np.mean(np.diff(xrp_trend)) > 0
        others_falling = np.mean(np.diff(btc_trend)) < 0 and np.mean(np.diff(eth_trend)) < 0
        
        if xrp_rising and others_falling:
            signals.append({
                'type': 'divergence',
                'strength': 0.8,
                'message': 'XRP rising while BTC/ETH falling - potential migration',
                'timestamp': datetime.now().isoformat()
            })
        
        # Check for decorrelation (XRP breaking from pack)
        if correlations.get('XRP-BTC', 1.0) < 0.3 and correlations.get('XRP-ETH', 1.0) < 0.3:
            signals.append({
                'type': 'decorrelation',
                'strength': 0.7,
                'message': 'XRP decorrelating from major cryptos - independent movement',
                'timestamp': datetime.now().isoformat()
            })
        
        # Check for volatility reduction in XRP (stability)
        xrp_confidence = forecasts['XRP']['confidence_score'][-24:] if 'confidence_score' in forecasts['XRP'].columns else None
        if xrp_confidence is not None and np.mean(xrp_confidence) > 0.8:
            signals.append({
                'type': 'stability',
                'strength': 0.6,
                'message': 'XRP showing stability - attractive for institutional flows',
                'timestamp': datetime.now().isoformat()
            })
        
        return signals
    
    def _calculate_xrp_dominance(self, forecasts: Dict[str, pd.DataFrame]) -> float:
        """Calculate XRP dominance score based on forecasts"""
        # Get trend strengths
        xrp_strength = np.mean(forecasts['XRP']['trend_strength'][-24:]) if 'trend_strength' in forecasts['XRP'].columns else 0
        btc_strength = np.mean(forecasts['BTC']['trend_strength'][-24:]) if 'trend_strength' in forecasts['BTC'].columns else 0
        eth_strength = np.mean(forecasts['ETH']['trend_strength'][-24:]) if 'trend_strength' in forecasts['ETH'].columns else 0
        
        # XRP dominance = XRP strength relative to others
        total_strength = xrp_strength + btc_strength + eth_strength
        
        if total_strength > 0:
            dominance = xrp_strength / total_strength
        else:
            dominance = 0.33  # Equal weight if no trend
        
        # Boost score if XRP has highest confidence
        xrp_conf = np.mean(forecasts['XRP'].get('confidence_score', [0.5])[-24:])
        btc_conf = np.mean(forecasts['BTC'].get('confidence_score', [0.5])[-24:])
        eth_conf = np.mean(forecasts['ETH'].get('confidence_score', [0.5])[-24:])
        
        if xrp_conf > max(btc_conf, eth_conf):
            dominance = min(dominance * 1.2, 1.0)
        
        return float(dominance)
    
    def _assess_manipulation_risk(self, forecasts: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """Assess manipulation risk for each asset"""
        risks = {}
        
        for asset, forecast in forecasts.items():
            risk = 0.0
            
            # High volatility in confidence = manipulation risk
            if 'confidence_score' in forecast.columns:
                conf_volatility = np.std(forecast['confidence_score'][-24:])
                risk += conf_volatility * 0.3
            
            # Extreme movements predicted
            yhat = forecast['yhat'].values[-24:]
            pct_change = np.abs(np.diff(yhat) / yhat[:-1])
            if np.max(pct_change) > 0.1:  # >10% move predicted
                risk += 0.3
            
            # Wide prediction intervals = uncertainty/manipulation
            interval_width = forecast['yhat_upper'].values[-24:] - forecast['yhat_lower'].values[-24:]
            relative_width = interval_width / np.abs(yhat)
            if np.mean(relative_width) > 0.2:  # >20% relative width
                risk += 0.2
            
            # Unusual seasonality patterns
            if 'weekly' in forecast.columns:
                weekly_component = forecast['weekly'].values[-24:]
                if np.std(weekly_component) > np.mean(np.abs(weekly_component)):
                    risk += 0.2
            
            risks[asset] = min(risk, 1.0)
        
        return risks
    
    def backtest_forecast_accuracy(self,
                                    df: pd.DataFrame,
                                    cutoff_date: str,
                                    horizon: int = 24) -> Dict:
        """
        Backtest forecast accuracy on historical data
        """
        # Split data
        train_df = df[df['ds'] < cutoff_date].copy()
        test_df = df[df['ds'] >= cutoff_date].head(horizon).copy()
        
        if len(test_df) == 0:
            return {'error': 'No test data available'}
        
        # Generate forecast
        forecast = self.forecast_with_confidence(train_df, periods=horizon)
        
        # Align forecast with test data
        forecast_subset = forecast.tail(horizon)
        
        # Calculate metrics
        actual = test_df['y'].values
        predicted = forecast_subset['yhat'].values[:len(actual)]
        
        mae = np.mean(np.abs(actual - predicted))
        mape = np.mean(np.abs((actual - predicted) / actual)) * 100
        rmse = np.sqrt(np.mean((actual - predicted) ** 2))
        
        # Direction accuracy (important for trading)
        actual_direction = np.sign(np.diff(actual, prepend=actual[0]))
        predicted_direction = np.sign(np.diff(predicted, prepend=predicted[0]))
        direction_accuracy = np.mean(actual_direction == predicted_direction)
        
        return {
            'mae': float(mae),
            'mape': float(mape),
            'rmse': float(rmse),
            'direction_accuracy': float(direction_accuracy),
            'within_confidence': self._calculate_coverage(actual, forecast_subset),
            'cutoff_date': cutoff_date,
            'horizon': horizon
        }
    
    def _calculate_coverage(self, actual: np.ndarray, forecast: pd.DataFrame) -> float:
        """Calculate percentage of actual values within prediction intervals"""
        lower = forecast['yhat_lower'].values[:len(actual)]
        upper = forecast['yhat_upper'].values[:len(actual)]
        
        within = np.sum((actual >= lower) & (actual <= upper))
        coverage = within / len(actual)
        
        return float(coverage)
