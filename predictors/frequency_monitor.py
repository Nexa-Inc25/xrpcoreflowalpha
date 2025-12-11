#!/usr/bin/env python3
"""
PRODUCTION MONITORING & ALERTING SYSTEM
Real-time monitoring of ultra-hardened frequency detection performance
"""

import time
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import deque
import numpy as np
from dataclasses import dataclass, asdict

# Monitoring thresholds
THRESHOLDS = {
    'min_accuracy': 0.85,  # 85% minimum accuracy
    'max_false_positive_rate': 0.05,  # 5% max false positives
    'min_confidence': 70,  # 70% minimum confidence
    'max_drift': 0.1,  # 10% max frequency drift
    'max_spoofing_rate': 0.02,  # 2% max spoofing attempts
    'min_events_per_minute': 10,  # Minimum activity
    'max_latency_ms': 50  # 50ms max processing time
}


@dataclass
class PerformanceMetrics:
    """Real-time performance metrics"""
    timestamp: float
    accuracy: float
    confidence: float
    false_positive_rate: float
    true_positive_rate: float
    patterns_detected: int
    spoofing_attempts: int
    avg_latency_ms: float
    events_processed: int
    drift_detected: bool
    anomalies: List[str]
    
    def to_alert(self) -> Optional[Dict]:
        """Generate alert if metrics exceed thresholds"""
        alerts = []
        severity = 'info'
        
        if self.accuracy < THRESHOLDS['min_accuracy']:
            alerts.append(f"Accuracy below threshold: {self.accuracy:.1%} < {THRESHOLDS['min_accuracy']:.0%}")
            severity = 'critical'
            
        if self.false_positive_rate > THRESHOLDS['max_false_positive_rate']:
            alerts.append(f"High false positives: {self.false_positive_rate:.1%} > {THRESHOLDS['max_false_positive_rate']:.0%}")
            severity = 'warning' if severity == 'info' else severity
            
        if self.confidence < THRESHOLDS['min_confidence']:
            alerts.append(f"Low confidence: {self.confidence:.1f}% < {THRESHOLDS['min_confidence']}%")
            severity = 'warning' if severity == 'info' else severity
            
        if self.avg_latency_ms > THRESHOLDS['max_latency_ms']:
            alerts.append(f"High latency: {self.avg_latency_ms:.1f}ms > {THRESHOLDS['max_latency_ms']}ms")
            severity = 'warning' if severity == 'info' else severity
            
        if self.drift_detected:
            alerts.append("Frequency drift detected - recalibration may be needed")
            severity = 'warning' if severity == 'info' else severity
            
        if self.anomalies:
            alerts.append(f"Anomalies detected: {', '.join(self.anomalies)}")
            severity = 'warning' if severity == 'info' else severity
        
        if alerts:
            return {
                'timestamp': datetime.fromtimestamp(self.timestamp).isoformat(),
                'severity': severity,
                'alerts': alerts,
                'metrics': asdict(self)
            }
        
        return None


class FrequencyMonitor:
    """Production monitoring system for ultra-hardened frequency detection"""
    
    def __init__(self, fingerprinter=None):
        self.fingerprinter = fingerprinter
        self.metrics_history = deque(maxlen=1000)
        self.detection_log = deque(maxlen=10000)
        self.alert_history = deque(maxlen=100)
        
        # Performance tracking
        self.true_positives = 0
        self.false_positives = 0
        self.true_negatives = 0
        self.false_negatives = 0
        
        # Real-time stats
        self.latencies = deque(maxlen=100)
        self.last_calibration = time.time()
        
        # Baseline performance (learned over time)
        self.baseline_accuracy = 0.9
        self.baseline_confidence = 85
        
    def validate_detection(self, pattern: str, detected: bool, ground_truth: bool):
        """Validate a detection against ground truth"""
        if detected and ground_truth:
            self.true_positives += 1
        elif detected and not ground_truth:
            self.false_positives += 1
        elif not detected and ground_truth:
            self.false_negatives += 1
        else:
            self.true_negatives += 1
        
        # Update fingerprinter ML weights
        if self.fingerprinter and hasattr(self.fingerprinter, 'validate_detection'):
            self.fingerprinter.validate_detection(pattern, detected == ground_truth)
    
    def calculate_metrics(self) -> PerformanceMetrics:
        """Calculate current performance metrics"""
        total_positive = self.true_positives + self.false_positives
        total_negative = self.true_negatives + self.false_negatives
        total = total_positive + total_negative
        
        if total == 0:
            return PerformanceMetrics(
                timestamp=time.time(),
                accuracy=0,
                confidence=0,
                false_positive_rate=0,
                true_positive_rate=0,
                patterns_detected=0,
                spoofing_attempts=0,
                avg_latency_ms=0,
                events_processed=0,
                drift_detected=False,
                anomalies=[]
            )
        
        accuracy = (self.true_positives + self.true_negatives) / total if total > 0 else 0
        
        # False positive rate
        fpr = self.false_positives / (self.false_positives + self.true_negatives) \
              if (self.false_positives + self.true_negatives) > 0 else 0
        
        # True positive rate (sensitivity)
        tpr = self.true_positives / (self.true_positives + self.false_negatives) \
              if (self.true_positives + self.false_negatives) > 0 else 0
        
        # Average confidence from recent detections
        recent_detections = list(self.detection_log)[-100:]
        avg_confidence = np.mean([d['confidence'] for d in recent_detections]) \
                        if recent_detections else 0
        
        # Average latency
        avg_latency = np.mean(self.latencies) if self.latencies else 0
        
        # Check for drift
        drift_detected = False
        if self.fingerprinter and hasattr(self.fingerprinter, 'drift_factors'):
            max_drift = max(abs(1.0 - factor) for factor in self.fingerprinter.drift_factors.values()) \
                       if self.fingerprinter.drift_factors else 0
            drift_detected = max_drift > THRESHOLDS['max_drift']
        
        # Detect anomalies
        anomalies = []
        if accuracy < self.baseline_accuracy * 0.8:  # 20% drop from baseline
            anomalies.append('accuracy_drop')
        if avg_confidence < self.baseline_confidence * 0.7:  # 30% drop
            anomalies.append('confidence_drop')
        if len(recent_detections) > 0:
            patterns = [d['pattern'] for d in recent_detections[-10:]]
            if len(set(patterns)) == 1:  # Same pattern 10 times in a row
                anomalies.append('stuck_pattern')
        
        # Get metrics from fingerprinter
        fp_metrics = {}
        if self.fingerprinter and hasattr(self.fingerprinter, 'metrics'):
            fp_metrics = self.fingerprinter.metrics
        
        return PerformanceMetrics(
            timestamp=time.time(),
            accuracy=accuracy,
            confidence=avg_confidence,
            false_positive_rate=fpr,
            true_positive_rate=tpr,
            patterns_detected=len(set(d['pattern'] for d in recent_detections)),
            spoofing_attempts=fp_metrics.get('spoofing_attempts', 0),
            avg_latency_ms=avg_latency * 1000,
            events_processed=len(self.detection_log),
            drift_detected=drift_detected,
            anomalies=anomalies
        )
    
    def log_detection(self, pattern: str, confidence: float, frequency: float, 
                     latency: float, metadata: Optional[Dict] = None):
        """Log a detection event"""
        self.detection_log.append({
            'timestamp': time.time(),
            'pattern': pattern,
            'confidence': confidence,
            'frequency': frequency,
            'latency': latency,
            'metadata': metadata or {}
        })
        
        self.latencies.append(latency)
    
    def check_health(self) -> Dict:
        """Health check for monitoring system"""
        metrics = self.calculate_metrics()
        
        health = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'accuracy': f"{metrics.accuracy:.1%}",
            'confidence': f"{metrics.confidence:.1f}%",
            'latency': f"{metrics.avg_latency_ms:.1f}ms",
            'patterns_active': metrics.patterns_detected,
            'events_processed': metrics.events_processed,
            'issues': []
        }
        
        # Check for issues
        if metrics.accuracy < THRESHOLDS['min_accuracy']:
            health['status'] = 'degraded'
            health['issues'].append(f"Low accuracy: {metrics.accuracy:.1%}")
            
        if metrics.avg_latency_ms > THRESHOLDS['max_latency_ms']:
            health['status'] = 'degraded' if health['status'] == 'healthy' else health['status']
            health['issues'].append(f"High latency: {metrics.avg_latency_ms:.1f}ms")
            
        if metrics.drift_detected:
            health['status'] = 'degraded' if health['status'] == 'healthy' else health['status']
            health['issues'].append("Frequency drift detected")
            
        if metrics.anomalies:
            health['status'] = 'unhealthy'
            health['issues'].extend(metrics.anomalies)
        
        return health
    
    async def auto_calibrate(self):
        """Automatically calibrate system based on performance"""
        metrics = self.calculate_metrics()
        
        if not self.fingerprinter:
            return
        
        # Calibrate based on accuracy
        if metrics.accuracy < 0.7:  # Poor accuracy
            # Increase minimum events for more data
            self.fingerprinter.min_events = min(30, self.fingerprinter.min_events + 5)
            print(f"[CALIBRATE] Increased min_events to {self.fingerprinter.min_events}")
            
        elif metrics.accuracy > 0.95:  # Very high accuracy, can be more aggressive
            # Decrease minimum events for faster detection
            self.fingerprinter.min_events = max(10, self.fingerprinter.min_events - 2)
            print(f"[CALIBRATE] Decreased min_events to {self.fingerprinter.min_events}")
        
        # Calibrate based on false positives
        if metrics.false_positive_rate > 0.1:  # Too many false positives
            # Be more conservative
            if hasattr(self.fingerprinter, 'confidence_level'):
                self.fingerprinter.confidence_level = min(0.99, self.fingerprinter.confidence_level + 0.02)
                print(f"[CALIBRATE] Increased confidence_level to {self.fingerprinter.confidence_level}")
        
        # Recalibrate drift compensation
        if metrics.drift_detected and hasattr(self.fingerprinter, 'drift_factors'):
            # Reset drift factors if drift is too high
            max_drift = max(abs(1.0 - f) for f in self.fingerprinter.drift_factors.values())
            if max_drift > 0.2:  # 20% drift
                self.fingerprinter.drift_factors = {}
                self.fingerprinter.baseline_frequencies = {}
                print("[CALIBRATE] Reset drift compensation due to high drift")
        
        self.last_calibration = time.time()
    
    async def monitor_loop(self, interval: int = 60):
        """Main monitoring loop"""
        print("[MONITOR] Starting frequency detection monitoring...")
        
        while True:
            try:
                # Calculate metrics
                metrics = self.calculate_metrics()
                
                # Store metrics
                self.metrics_history.append(metrics)
                
                # Check for alerts
                alert = metrics.to_alert()
                if alert:
                    self.alert_history.append(alert)
                    await self.send_alert(alert)
                
                # Auto-calibrate every hour
                if time.time() - self.last_calibration > 3600:
                    await self.auto_calibrate()
                
                # Log status
                if metrics.accuracy > 0:
                    print(f"[MONITOR] Accuracy: {metrics.accuracy:.1%} | "
                          f"Confidence: {metrics.confidence:.1f}% | "
                          f"Latency: {metrics.avg_latency_ms:.1f}ms | "
                          f"Patterns: {metrics.patterns_detected}")
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                print(f"[MONITOR] Error: {e}")
                await asyncio.sleep(interval)
    
    async def send_alert(self, alert: Dict):
        """Send alert to monitoring system"""
        print(f"[ALERT] {alert['severity'].upper()}: {', '.join(alert['alerts'])}")
        
        # Send to Slack if configured
        try:
            from workers.slack_alerts import send_slack_alert
            
            message = {
                "text": f"🚨 Frequency Detection Alert ({alert['severity'].upper()})",
                "attachments": [{
                    "color": "danger" if alert['severity'] == 'critical' else "warning",
                    "fields": [
                        {"title": issue, "short": True}
                        for issue in alert['alerts']
                    ],
                    "footer": f"Accuracy: {alert['metrics']['accuracy']:.1%} | "
                              f"Confidence: {alert['metrics']['confidence']:.1f}%",
                    "ts": int(alert['metrics']['timestamp'])
                }]
            }
            
            await send_slack_alert(message)
        except:
            pass  # Slack not configured
    
    def get_dashboard_data(self) -> Dict:
        """Get data for monitoring dashboard"""
        metrics = self.calculate_metrics()
        health = self.check_health()
        
        # Performance over time (last 24 hours)
        recent_metrics = [m for m in self.metrics_history 
                         if m.timestamp > time.time() - 86400]
        
        if recent_metrics:
            accuracy_series = [(m.timestamp, m.accuracy) for m in recent_metrics]
            confidence_series = [(m.timestamp, m.confidence) for m in recent_metrics]
            latency_series = [(m.timestamp, m.avg_latency_ms) for m in recent_metrics]
        else:
            accuracy_series = []
            confidence_series = []
            latency_series = []
        
        # Pattern distribution
        pattern_counts = {}
        for det in list(self.detection_log)[-1000:]:  # Last 1000 detections
            pattern = det['pattern']
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
        
        return {
            'health': health,
            'current_metrics': asdict(metrics),
            'performance_charts': {
                'accuracy': accuracy_series,
                'confidence': confidence_series,
                'latency': latency_series
            },
            'pattern_distribution': pattern_counts,
            'recent_alerts': list(self.alert_history)[-10:],
            'calibration': {
                'last_calibration': datetime.fromtimestamp(self.last_calibration).isoformat(),
                'auto_calibration_enabled': True,
                'current_settings': {
                    'min_events': self.fingerprinter.min_events if self.fingerprinter else 20,
                    'confidence_level': self.fingerprinter.confidence_level if self.fingerprinter else 0.95
                }
            }
        }


# Global monitor instance
frequency_monitor = FrequencyMonitor()


async def start_monitoring(fingerprinter):
    """Start the monitoring system"""
    frequency_monitor.fingerprinter = fingerprinter
    await frequency_monitor.monitor_loop()
