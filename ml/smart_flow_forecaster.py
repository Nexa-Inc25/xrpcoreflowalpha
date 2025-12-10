"""
Smart Flow Forecaster - Integrates Dark Pool, Whale, and Market Data
Uses ensemble learning with real-time adaptation
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
import asyncio
import httpx

# Optional imports - don't crash if not available
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logging.warning("XGBoost not available - using alternative models")

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    logging.warning("Prophet not available - using sklearn models only")

logger = logging.getLogger(__name__)


@dataclass
class FlowSignal:
    """Dark pool or whale flow signal"""
    timestamp: datetime
    amount_usd: float
    confidence: float
    network: str
    signal_type: str  # 'whale', 'dark_pool', 'trustline', 'surge'
    direction: str  # 'in', 'out', 'neutral'
    
    @property
    def weight(self) -> float:
        """Calculate signal importance weight"""
        # Larger amounts and higher confidence = more weight
        size_weight = np.log10(max(self.amount_usd, 1000)) / 10  # Log scale
        return self.confidence * size_weight


class SmartFlowForecaster:
    """
    Advanced forecasting that combines:
    1. Dark pool and whale flow signals
    2. Market price data
    3. Cross-asset correlations
    4. Real-time learning from outcomes
    """
    
    def __init__(self):
        # Models for ensemble
        self.prophet = None
        self.xgboost = None
        self.random_forest = None
        self.gradient_boost = None
        
        # Feature engineering
        self.scaler = StandardScaler()
        self.feature_cache = {}
        
        # Real-time learning
        self.outcome_buffer = []
        self.accuracy_scores = {
            'prophet': [],
            'xgboost': [],
            'random_forest': [],
            'gradient_boost': [],
            'ensemble': []
        }
        
        # Dark pool detection thresholds
        self.dark_pool_thresholds = {
            'min_amount_usd': 10_000_000,  # $10M minimum
            'min_confidence': 0.7,
            'surge_multiplier': 3.0  # 3x normal volume
        }
        
    async def fetch_flow_signals(self, 
                                  asset: str,
                                  lookback_hours: int = 168) -> List[FlowSignal]:
        """
        Fetch real flow signals from database
        """
        from db.connection import get_async_session
        from sqlalchemy import text
        
        signals = []
        
        try:
            async with get_async_session() as session:
                query = text("""
                    SELECT 
                        detected_at,
                        amount_usd,
                        confidence,
                        network,
                        signal_type,
                        metadata
                    FROM signals
                    WHERE detected_at > NOW() - INTERVAL :hours HOUR
                    AND (
                        network = :network 
                        OR metadata->>'asset' = :asset
                        OR signal_type IN ('whale', 'dark_pool', 'surge')
                    )
                    AND amount_usd > :min_amount
                    ORDER BY detected_at DESC
                """)
                
                network = 'xrpl' if asset.lower() == 'xrp' else 'ethereum'
                result = await session.execute(query, {
                    'hours': lookback_hours,
                    'network': network,
                    'asset': asset.upper(),
                    'min_amount': 100000  # $100k minimum
                })
                
                for row in result.fetchall():
                    # Determine direction from metadata
                    metadata = row.metadata or {}
                    direction = 'neutral'
                    if 'direction' in metadata:
                        direction = metadata['direction']
                    elif row.signal_type == 'trustline':
                        direction = 'in'  # New trustlines = inflow potential
                    
                    signals.append(FlowSignal(
                        timestamp=row.detected_at,
                        amount_usd=float(row.amount_usd or 0),
                        confidence=float(row.confidence or 0),
                        network=row.network,
                        signal_type=row.signal_type,
                        direction=direction
                    ))
                    
        except Exception as e:
            logger.error(f"Failed to fetch flow signals: {e}")
        
        return signals
    
    def engineer_flow_features(self,
                                price_data: pd.DataFrame,
                                flow_signals: List[FlowSignal]) -> pd.DataFrame:
        """
        Create smart features from price and flow data
        """
        features = price_data.copy()
        
        # Price-based features
        features['returns'] = features['close'].pct_change()
        features['log_returns'] = np.log(features['close'] / features['close'].shift(1))
        features['volatility'] = features['returns'].rolling(24).std()
        features['volume_zscore'] = (features['volume'] - features['volume'].rolling(168).mean()) / features['volume'].rolling(168).std()
        
        # Price momentum
        for period in [6, 12, 24, 72]:  # hours
            features[f'momentum_{period}h'] = features['close'].pct_change(period)
            features[f'rsi_{period}h'] = self._calculate_rsi(features['close'], period)
        
        # Volume patterns
        features['volume_ma_ratio'] = features['volume'] / features['volume'].rolling(24).mean()
        features['volume_trend'] = features['volume'].rolling(24).apply(lambda x: np.polyfit(range(len(x)), x, 1)[0])
        
        # Flow signal features
        if flow_signals:
            # Aggregate flow signals by hour
            flow_df = pd.DataFrame([{
                'timestamp': s.timestamp,
                'amount': s.amount_usd,
                'confidence': s.confidence,
                'weight': s.weight,
                'is_dark': s.signal_type == 'dark_pool',
                'is_whale': s.signal_type == 'whale',
                'direction_in': s.direction == 'in',
                'direction_out': s.direction == 'out'
            } for s in flow_signals])
            
            flow_df.set_index('timestamp', inplace=True)
            flow_hourly = flow_df.resample('1H').agg({
                'amount': 'sum',
                'confidence': 'mean',
                'weight': 'sum',
                'is_dark': 'sum',
                'is_whale': 'sum',
                'direction_in': 'sum',
                'direction_out': 'sum'
            }).fillna(0)
            
            # Merge with price data
            features = features.merge(flow_hourly, left_index=True, right_index=True, how='left')
            features.fillna(0, inplace=True)
            
            # Flow momentum
            features['flow_momentum'] = features['amount'].rolling(24).sum()
            features['flow_acceleration'] = features['flow_momentum'].diff()
            
            # Dark pool ratio
            total_flow = features['amount'].rolling(24).sum()
            dark_flow = features['is_dark'].rolling(24).sum() * features['amount'].rolling(24).mean()
            features['dark_pool_ratio'] = dark_flow / (total_flow + 1)
            
            # Net flow direction
            features['net_flow'] = features['direction_in'] - features['direction_out']
            features['cumulative_net_flow'] = features['net_flow'].cumsum()
            
            # Whale activity intensity
            features['whale_intensity'] = features['is_whale'].rolling(24).sum() / 24
            
        # Technical indicators
        features['bb_upper'], features['bb_middle'], features['bb_lower'] = self._bollinger_bands(features['close'])
        features['bb_position'] = (features['close'] - features['bb_lower']) / (features['bb_upper'] - features['bb_lower'])
        
        # MACD
        features['macd'], features['macd_signal'] = self._calculate_macd(features['close'])
        features['macd_divergence'] = features['macd'] - features['macd_signal']
        
        # Market microstructure
        features['spread'] = features['high'] - features['low']
        features['spread_pct'] = features['spread'] / features['close']
        features['close_position'] = (features['close'] - features['low']) / (features['high'] - features['low'])
        
        # Time features
        features['hour'] = features.index.hour
        features['day_of_week'] = features.index.dayofweek
        features['is_weekend'] = features['day_of_week'].isin([5, 6]).astype(int)
        features['is_us_market_hours'] = features['hour'].between(14, 21).astype(int)  # UTC
        
        # Clean up
        features.replace([np.inf, -np.inf], 0, inplace=True)
        features.fillna(0, inplace=True)
        
        return features
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: int = 2):
        """Calculate Bollinger Bands"""
        middle = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return upper, middle, lower
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
        """Calculate MACD"""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal, adjust=False).mean()
        return macd, macd_signal
    
    def train_ensemble(self,
                       features: pd.DataFrame,
                       target: pd.Series,
                       test_size: float = 0.2) -> Dict[str, float]:
        """
        Train ensemble of models with time series cross-validation
        """
        # Remove non-numeric columns
        numeric_features = features.select_dtypes(include=[np.number])
        
        # Scale features
        X_scaled = self.scaler.fit_transform(numeric_features)
        y = target.values
        
        # Time series split for validation
        tscv = TimeSeriesSplit(n_splits=5)
        scores = {model: [] for model in self.accuracy_scores.keys()}
        
        # Train each model
        for train_idx, val_idx in tscv.split(X_scaled):
            X_train, X_val = X_scaled[train_idx], X_scaled[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]
            
            # XGBoost (if available)
            if XGBOOST_AVAILABLE:
                self.xgboost = xgb.XGBRegressor(
                    n_estimators=100,
                    max_depth=6,
                    learning_rate=0.1,
                    objective='reg:squarederror'
                )
                self.xgboost.fit(X_train, y_train)
                xgb_pred = self.xgboost.predict(X_val)
                scores['xgboost'].append(self._calculate_accuracy(y_val, xgb_pred))
            else:
                # Use extra trees as fallback
                from sklearn.ensemble import ExtraTreesRegressor
                self.xgboost = ExtraTreesRegressor(
                    n_estimators=100,
                    max_depth=6,
                    random_state=42
                )
                self.xgboost.fit(X_train, y_train)
                xgb_pred = self.xgboost.predict(X_val)
                scores['xgboost'].append(self._calculate_accuracy(y_val, xgb_pred))
            
            # Random Forest
            self.random_forest = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            self.random_forest.fit(X_train, y_train)
            rf_pred = self.random_forest.predict(X_val)
            scores['random_forest'].append(self._calculate_accuracy(y_val, rf_pred))
            
            # Gradient Boosting
            self.gradient_boost = GradientBoostingRegressor(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42
            )
            self.gradient_boost.fit(X_train, y_train)
            gb_pred = self.gradient_boost.predict(X_val)
            scores['gradient_boost'].append(self._calculate_accuracy(y_val, gb_pred))
            
            # Ensemble (weighted average based on performance)
            weights = self._calculate_ensemble_weights(scores)
            ensemble_pred = (
                weights['xgboost'] * xgb_pred +
                weights['random_forest'] * rf_pred +
                weights['gradient_boost'] * gb_pred
            )
            scores['ensemble'].append(self._calculate_accuracy(y_val, ensemble_pred))
        
        # Store average scores
        avg_scores = {model: np.mean(score_list) for model, score_list in scores.items()}
        
        # Update accuracy history
        for model, score in avg_scores.items():
            self.accuracy_scores[model].append(score)
        
        return avg_scores
    
    def _calculate_accuracy(self, actual: np.ndarray, predicted: np.ndarray) -> float:
        """Calculate directional accuracy (most important for trading)"""
        if len(actual) < 2:
            return 0.5
        
        actual_direction = np.sign(np.diff(actual))
        pred_direction = np.sign(np.diff(predicted))
        
        return np.mean(actual_direction == pred_direction)
    
    def _calculate_ensemble_weights(self, scores: Dict[str, List[float]]) -> Dict[str, float]:
        """Calculate optimal weights for ensemble based on recent performance"""
        recent_scores = {
            'xgboost': np.mean(scores['xgboost'][-5:]) if scores['xgboost'] else 0.33,
            'random_forest': np.mean(scores['random_forest'][-5:]) if scores['random_forest'] else 0.33,
            'gradient_boost': np.mean(scores['gradient_boost'][-5:]) if scores['gradient_boost'] else 0.34
        }
        
        # Normalize to sum to 1
        total = sum(recent_scores.values())
        if total > 0:
            weights = {k: v/total for k, v in recent_scores.items()}
        else:
            weights = {'xgboost': 0.33, 'random_forest': 0.33, 'gradient_boost': 0.34}
        
        return weights
    
    async def smart_forecast(self,
                              asset: str,
                              horizon_hours: int = 24,
                              include_dark_pools: bool = True) -> Dict[str, Any]:
        """
        Generate smart forecast incorporating all signals
        """
        from api.tuned_analytics import fetch_asset_data
        
        # Fetch price data
        price_data = await fetch_asset_data(asset, period='30d')
        
        if price_data.empty:
            return {'error': f'No price data available for {asset}'}
        
        # Fetch flow signals if requested
        flow_signals = []
        if include_dark_pools:
            flow_signals = await self.fetch_flow_signals(asset, lookback_hours=168)
        
        # Engineer features
        features = self.engineer_flow_features(price_data, flow_signals)
        
        # Prepare target (next hour price)
        target = features['close'].shift(-1)
        
        # Remove last row (no target)
        features = features[:-1]
        target = target[:-1]
        
        # Train ensemble
        accuracy_scores = self.train_ensemble(features, target)
        
        # Generate ensemble predictions
        last_features = features.tail(1)
        X_last = self.scaler.transform(last_features.select_dtypes(include=[np.number]))
        
        predictions = {
            'xgboost': float(self.xgboost.predict(X_last)[0]) if self.xgboost else None,
            'random_forest': float(self.random_forest.predict(X_last)[0]) if self.random_forest else None,
            'gradient_boost': float(self.gradient_boost.predict(X_last)[0]) if self.gradient_boost else None,
        }
        
        # Calculate ensemble prediction
        weights = self._calculate_ensemble_weights(self.accuracy_scores)
        ensemble_pred = sum(
            weights[model] * pred 
            for model, pred in predictions.items() 
            if pred is not None
        )
        
        # Analyze dark pool impact
        dark_pool_analysis = self._analyze_dark_pool_impact(flow_signals) if flow_signals else {}
        
        # Generate confidence score
        confidence = self._calculate_forecast_confidence(
            accuracy_scores,
            features,
            flow_signals
        )
        
        return {
            'asset': asset,
            'current_price': float(price_data['close'].iloc[-1]),
            'forecast': {
                'ensemble': ensemble_pred,
                'predictions': predictions,
                'confidence': confidence
            },
            'accuracy_scores': accuracy_scores,
            'dark_pool_analysis': dark_pool_analysis,
            'feature_importance': self._get_feature_importance(features),
            'recommended_action': self._generate_recommendation(
                ensemble_pred,
                price_data['close'].iloc[-1],
                confidence,
                dark_pool_analysis
            )
        }
    
    def _analyze_dark_pool_impact(self, flow_signals: List[FlowSignal]) -> Dict:
        """Analyze dark pool activity and predict impact"""
        if not flow_signals:
            return {'detected': False}
        
        # Filter for dark pool and large whale signals
        dark_signals = [s for s in flow_signals if s.signal_type == 'dark_pool' or 
                         (s.signal_type == 'whale' and s.amount_usd > 10_000_000)]
        
        if not dark_signals:
            return {'detected': False}
        
        # Calculate metrics
        total_volume = sum(s.amount_usd for s in dark_signals)
        avg_confidence = np.mean([s.confidence for s in dark_signals])
        
        # Predict impact
        impact_score = min((total_volume / 100_000_000) * avg_confidence, 1.0)
        
        return {
            'detected': True,
            'total_volume_usd': total_volume,
            'signal_count': len(dark_signals),
            'avg_confidence': avg_confidence,
            'impact_score': impact_score,
            'predicted_move_pct': impact_score * 5.0,  # Up to 5% move
            'recommendation': 'BULLISH' if impact_score > 0.6 else 'NEUTRAL'
        }
    
    def _calculate_forecast_confidence(self,
                                        accuracy_scores: Dict,
                                        features: pd.DataFrame,
                                        flow_signals: List[FlowSignal]) -> float:
        """Calculate overall confidence in forecast"""
        confidence = 0.0
        
        # Model accuracy contribution (40%)
        avg_accuracy = np.mean(list(accuracy_scores.values()))
        confidence += avg_accuracy * 0.4
        
        # Data quality contribution (30%)
        data_completeness = 1.0 - (features.isna().sum().sum() / features.size)
        confidence += data_completeness * 0.3
        
        # Signal strength contribution (30%)
        if flow_signals:
            signal_strength = min(len(flow_signals) / 100, 1.0)
            avg_signal_confidence = np.mean([s.confidence for s in flow_signals])
            confidence += (signal_strength * avg_signal_confidence) * 0.3
        else:
            confidence += 0.15
        
        return min(confidence, 1.0)
    
    def _get_feature_importance(self, features: pd.DataFrame) -> Dict[str, float]:
        """Get feature importance from trained models"""
        if not self.xgboost:
            return {}
        
        importance = {}
        feature_names = features.select_dtypes(include=[np.number]).columns.tolist()
        
        # Get feature importance from best available model
        if hasattr(self.xgboost, 'feature_importances_'):
            feature_importance = self.xgboost.feature_importances_
        elif hasattr(self.random_forest, 'feature_importances_'):
            feature_importance = self.random_forest.feature_importances_
        else:
            return {}
        
        for i, name in enumerate(feature_names[:len(feature_importance)]):
            importance[name] = float(feature_importance[i])
        
        # Sort by importance
        importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10])
        
        return importance
    
    def _generate_recommendation(self,
                                  predicted_price: float,
                                  current_price: float,
                                  confidence: float,
                                  dark_pool_analysis: Dict) -> Dict:
        """Generate trading recommendation"""
        price_change_pct = ((predicted_price - current_price) / current_price) * 100
        
        # Base recommendation on price change
        if price_change_pct > 2 and confidence > 0.7:
            action = 'STRONG_BUY'
        elif price_change_pct > 1 and confidence > 0.6:
            action = 'BUY'
        elif price_change_pct < -2 and confidence > 0.7:
            action = 'STRONG_SELL'
        elif price_change_pct < -1 and confidence > 0.6:
            action = 'SELL'
        else:
            action = 'HOLD'
        
        # Adjust for dark pool activity
        if dark_pool_analysis.get('detected'):
            if dark_pool_analysis['impact_score'] > 0.7:
                if action in ['HOLD', 'BUY']:
                    action = 'STRONG_BUY'
                elif action == 'SELL':
                    action = 'HOLD'
        
        return {
            'action': action,
            'predicted_change_pct': price_change_pct,
            'confidence': confidence,
            'reasoning': self._explain_recommendation(action, price_change_pct, confidence, dark_pool_analysis)
        }
    
    def _explain_recommendation(self, action: str, change_pct: float, confidence: float, dark_pool: Dict) -> str:
        """Explain the recommendation"""
        reasons = []
        
        if abs(change_pct) > 2:
            reasons.append(f"Expecting {abs(change_pct):.1f}% {'rise' if change_pct > 0 else 'drop'}")
        
        if confidence > 0.8:
            reasons.append("High model confidence")
        elif confidence < 0.5:
            reasons.append("Low confidence - be cautious")
        
        if dark_pool.get('detected'):
            reasons.append(f"Dark pool activity detected (${dark_pool['total_volume_usd']/1e6:.1f}M)")
        
        return ". ".join(reasons) if reasons else "Based on current market conditions"
