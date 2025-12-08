"""
Hidden Markov Model for Dark Flow State Transitions
Optimized for XRPL-centric multi-asset correlations
"""

import numpy as np
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import pandas as pd
from scipy.stats import multivariate_normal
import logging

logger = logging.getLogger(__name__)

@dataclass
class FlowState:
    """Represents a flow state in the HMM"""
    name: str
    mean_volume: float
    volatility: float
    correlation_strength: float
    
class DarkFlowHMM:
    """
    Hidden Markov Model optimized for dark flow detection
    States: Accumulation, Distribution, Manipulation, Migration
    """
    
    def __init__(self, n_states: int = 4, n_features: int = 5):
        self.n_states = n_states
        self.n_features = n_features
        
        # State names for interpretability
        self.state_names = [
            "Accumulation",    # Quiet accumulation in dark pools
            "Distribution",    # Large distribution events
            "Manipulation",    # Active price manipulation
            "Migration"        # Capital migration to XRPL
        ]
        
        # Initialize transition matrix with bias toward migration to XRPL
        self.transition_matrix = self._init_transition_matrix()
        
        # Gaussian mixture parameters for emissions
        self.emission_means = None
        self.emission_covs = None
        
        # Higher-order chain parameters
        self.order = 2  # Second-order Markov chain
        self.history_weights = [0.6, 0.4]  # Weight recent history more
        
    def _init_transition_matrix(self) -> np.ndarray:
        """
        Initialize transition matrix with XRPL migration bias
        """
        # Base transition probabilities
        trans_mat = np.array([
            [0.70, 0.15, 0.10, 0.05],  # Accumulation -> mostly stays
            [0.10, 0.60, 0.20, 0.10],  # Distribution -> some manipulation
            [0.05, 0.25, 0.50, 0.20],  # Manipulation -> increased migration
            [0.02, 0.03, 0.05, 0.90],  # Migration -> sticky state (XRPL)
        ])
        
        return trans_mat
    
    def fit_gaussian_mixtures(self, data: np.ndarray) -> None:
        """
        Fit Gaussian mixture models for emission probabilities
        Handles non-stationary financial data
        """
        from sklearn.mixture import GaussianMixture
        
        # Fit mixture model for each state
        self.emission_means = np.zeros((self.n_states, self.n_features))
        self.emission_covs = np.zeros((self.n_states, self.n_features, self.n_features))
        
        # Use k-means initialization for stability
        gmm = GaussianMixture(
            n_components=self.n_states,
            covariance_type='full',
            init_params='k-means++',
            max_iter=200,
            random_state=42
        )
        
        gmm.fit(data)
        
        self.emission_means = gmm.means_
        self.emission_covs = gmm.covariances_
        
        logger.info(f"Fitted Gaussian mixtures for {self.n_states} states")
        
    def viterbi_decode(self, observations: np.ndarray) -> Tuple[List[int], float]:
        """
        Viterbi algorithm for most likely state sequence
        Optimized for continuous crypto data streams
        """
        T = observations.shape[0]
        
        # Initialize trellis
        trellis = np.zeros((self.n_states, T))
        backtrack = np.zeros((self.n_states, T), dtype=int)
        
        # Initial probabilities (uniform)
        initial_probs = np.ones(self.n_states) / self.n_states
        
        # First observation
        for s in range(self.n_states):
            emission_prob = self._emission_probability(observations[0], s)
            trellis[s, 0] = np.log(initial_probs[s]) + np.log(emission_prob + 1e-10)
        
        # Forward pass
        for t in range(1, T):
            for s in range(self.n_states):
                # Calculate transition probabilities
                trans_probs = np.log(self.transition_matrix[:, s] + 1e-10)
                
                # Add emission probability
                emission_prob = self._emission_probability(observations[t], s)
                emission_log_prob = np.log(emission_prob + 1e-10)
                
                # Find max probability path
                probabilities = trellis[:, t-1] + trans_probs + emission_log_prob
                backtrack[s, t] = np.argmax(probabilities)
                trellis[s, t] = np.max(probabilities)
        
        # Backward pass - reconstruct path
        states = []
        last_state = np.argmax(trellis[:, T-1])
        states.append(last_state)
        
        for t in range(T-1, 0, -1):
            last_state = backtrack[last_state, t]
            states.append(last_state)
        
        states.reverse()
        
        # Calculate path probability
        path_prob = np.max(trellis[:, T-1])
        
        return states, path_prob
    
    def _emission_probability(self, observation: np.ndarray, state: int) -> float:
        """
        Calculate emission probability using Gaussian distribution
        """
        if self.emission_means is None:
            return 1.0 / self.n_states  # Uniform if not fitted
        
        try:
            prob = multivariate_normal.pdf(
                observation,
                mean=self.emission_means[state],
                cov=self.emission_covs[state] + np.eye(self.n_features) * 1e-6
            )
            return max(prob, 1e-10)
        except:
            return 1e-10
    
    def predict_next_state(self, current_state: int, history: Optional[List[int]] = None) -> Dict[str, float]:
        """
        Predict next state probabilities with higher-order chain
        """
        if history and len(history) >= self.order:
            # Weighted combination of transition probabilities
            probs = np.zeros(self.n_states)
            
            for i, hist_state in enumerate(history[-self.order:]):
                weight = self.history_weights[i] if i < len(self.history_weights) else 0.1
                probs += self.transition_matrix[hist_state] * weight
            
            # Normalize
            probs = probs / np.sum(probs)
        else:
            # First-order transition
            probs = self.transition_matrix[current_state]
        
        return {
            self.state_names[i]: float(probs[i]) 
            for i in range(self.n_states)
        }
    
    def detect_manipulation_to_migration(self, states: List[int], window: int = 10) -> List[Dict]:
        """
        Detect patterns indicating manipulation leading to XRPL migration
        """
        alerts = []
        
        for i in range(len(states) - window):
            window_states = states[i:i+window]
            
            # Count state transitions
            manipulation_count = sum(1 for s in window_states if s == 2)
            migration_count = sum(1 for s in window_states if s == 3)
            
            # Pattern: Manipulation followed by migration
            if manipulation_count >= 3 and migration_count >= 2:
                confidence = (manipulation_count + migration_count) / window
                
                alerts.append({
                    'timestamp': i,
                    'pattern': 'manipulation_to_migration',
                    'confidence': confidence,
                    'window_states': window_states,
                    'message': f"Dark pool manipulation detected with {confidence:.0%} confidence of XRPL migration"
                })
        
        return alerts
    
    def quantum_adjustment(self, states: np.ndarray, quantum_noise: float = 0.01) -> np.ndarray:
        """
        Apply quantum-inspired adjustments for continuous crypto data
        Adds controlled stochasticity for better adaptation
        """
        # Add quantum noise to transition matrix
        quantum_trans = self.transition_matrix.copy()
        noise = np.random.normal(0, quantum_noise, quantum_trans.shape)
        quantum_trans += noise
        
        # Renormalize rows
        quantum_trans = np.abs(quantum_trans)
        quantum_trans = quantum_trans / quantum_trans.sum(axis=1, keepdims=True)
        
        return quantum_trans


class FlowStateAnalyzer:
    """
    Analyzes flow states across multiple assets for correlations
    """
    
    def __init__(self):
        self.hmm = DarkFlowHMM()
        self.asset_states = {}
        
    def analyze_multi_asset_flows(self, 
                                   xrp_data: pd.DataFrame,
                                   eth_data: pd.DataFrame,
                                   btc_data: pd.DataFrame,
                                   spy_data: pd.DataFrame) -> Dict:
        """
        Analyze state transitions across assets to predict XRPL migrations
        """
        results = {
            'correlations': {},
            'migration_signals': [],
            'state_transitions': {}
        }
        
        # Extract features for each asset
        assets = {
            'XRP': self._extract_features(xrp_data),
            'ETH': self._extract_features(eth_data),
            'BTC': self._extract_features(btc_data),
            'SPY': self._extract_features(spy_data)
        }
        
        # Fit HMM for each asset
        for asset_name, features in assets.items():
            self.hmm.fit_gaussian_mixtures(features)
            states, prob = self.hmm.viterbi_decode(features)
            self.asset_states[asset_name] = states
            
            # Detect manipulation patterns
            alerts = self.hmm.detect_manipulation_to_migration(states)
            if alerts:
                results['migration_signals'].extend([
                    {**alert, 'asset': asset_name} for alert in alerts
                ])
        
        # Calculate cross-asset correlations
        for asset1 in assets.keys():
            for asset2 in assets.keys():
                if asset1 < asset2:
                    corr = self._calculate_state_correlation(
                        self.asset_states[asset1],
                        self.asset_states[asset2]
                    )
                    results['correlations'][f"{asset1}-{asset2}"] = corr
        
        # Focus on XRP migration patterns
        xrp_migration_prob = self._calculate_xrp_migration_probability()
        results['xrp_migration_score'] = xrp_migration_prob
        
        return results
    
    def _extract_features(self, data: pd.DataFrame) -> np.ndarray:
        """
        Extract features for HMM: volume, price change, volatility, etc.
        """
        features = []
        
        # Volume (normalized)
        features.append((data['volume'] / data['volume'].mean()).values)
        
        # Price change
        features.append(data['close'].pct_change().fillna(0).values)
        
        # Volatility (rolling std)
        features.append(data['close'].pct_change().rolling(20).std().fillna(0).values)
        
        # RSI as momentum indicator
        features.append(self._calculate_rsi(data['close']).values)
        
        # Volume-weighted average price deviation
        vwap = (data['close'] * data['volume']).cumsum() / data['volume'].cumsum()
        features.append(((data['close'] - vwap) / vwap).values)
        
        return np.column_stack(features)
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI for momentum"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)
    
    def _calculate_state_correlation(self, states1: List[int], states2: List[int]) -> float:
        """
        Calculate correlation between state sequences
        """
        if len(states1) != len(states2):
            min_len = min(len(states1), len(states2))
            states1 = states1[:min_len]
            states2 = states2[:min_len]
        
        # Count matching transitions
        matches = sum(1 for s1, s2 in zip(states1, states2) if s1 == s2)
        
        # Weight migration states higher
        weighted_matches = sum(
            2 if (s1 == s2 == 3) else 1 
            for s1, s2 in zip(states1, states2) 
            if s1 == s2
        )
        
        correlation = weighted_matches / (len(states1) + len(states1) * 0.5)
        return min(correlation, 1.0)
    
    def _calculate_xrp_migration_probability(self) -> float:
        """
        Calculate probability of flows migrating to XRPL
        """
        if 'XRP' not in self.asset_states:
            return 0.0
        
        xrp_states = self.asset_states['XRP']
        migration_ratio = sum(1 for s in xrp_states if s == 3) / len(xrp_states)
        
        # Boost score if other assets show manipulation
        manipulation_scores = []
        for asset, states in self.asset_states.items():
            if asset != 'XRP':
                manip_ratio = sum(1 for s in states if s == 2) / len(states)
                manipulation_scores.append(manip_ratio)
        
        # Combined score
        if manipulation_scores:
            avg_manipulation = np.mean(manipulation_scores)
            migration_probability = migration_ratio * 0.7 + avg_manipulation * 0.3
        else:
            migration_probability = migration_ratio
        
        return min(migration_probability, 1.0)
