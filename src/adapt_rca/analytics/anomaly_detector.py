"""
Anomaly detection engine for ADAPT-RCA.

This module provides statistical anomaly detection methods to identify
unusual patterns in event data, error rates, and system metrics.

Based on industry best practices from Datadog Watchdog, New Relic Applied Intelligence,
and open-source tools like VictoriaMetrics.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


class StatisticalMethod(str, Enum):
    """Statistical methods for anomaly detection."""
    ZSCORE = "zscore"  # Standard deviation based
    IQR = "iqr"  # Interquartile range
    MOVING_AVERAGE = "moving_average"  # Deviation from moving average
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"  # Holt-Winters


@dataclass
class AnomalyResult:
    """Result of anomaly detection analysis."""
    is_anomaly: bool
    score: float  # Anomaly score (0.0 = normal, 1.0 = highly anomalous)
    method: StatisticalMethod
    baseline_value: Optional[float] = None
    actual_value: Optional[float] = None
    threshold: Optional[float] = None
    confidence: float = 0.0  # Confidence in the detection (0.0-1.0)
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class AnomalyDetector:
    """
    Statistical anomaly detector for time-series event data.

    This detector uses multiple statistical methods to identify anomalies
    in event rates, error patterns, and service metrics. It provides
    confidence scores and contextual information for each detection.

    Example:
        >>> from adapt_rca.analytics import AnomalyDetector, StatisticalMethod
        >>> detector = AnomalyDetector(method=StatisticalMethod.ZSCORE)
        >>> result = detector.detect_error_rate_anomaly(
        ...     current_rate=150,
        ...     historical_rates=[50, 55, 48, 52, 49]
        ... )
        >>> if result.is_anomaly:
        ...     print(f"Anomaly detected! Score: {result.score:.2f}")
    """

    def __init__(
        self,
        method: StatisticalMethod = StatisticalMethod.ZSCORE,
        sensitivity: float = 2.0,
        min_historical_points: int = 10
    ):
        """
        Initialize anomaly detector.

        Args:
            method: Statistical method to use for detection
            sensitivity: Sensitivity threshold (higher = less sensitive)
                - For ZSCORE: number of standard deviations (default 2.0)
                - For IQR: multiplier for IQR (default 1.5)
            min_historical_points: Minimum historical data points required
        """
        self.method = method
        self.sensitivity = sensitivity
        self.min_historical_points = min_historical_points

    def detect_error_rate_anomaly(
        self,
        current_rate: float,
        historical_rates: List[float]
    ) -> AnomalyResult:
        """
        Detect if current error rate is anomalous.

        Args:
            current_rate: Current error rate (errors per time unit)
            historical_rates: List of historical error rates for comparison

        Returns:
            AnomalyResult with detection details
        """
        if len(historical_rates) < self.min_historical_points:
            logger.debug(
                f"Insufficient historical data: {len(historical_rates)} < {self.min_historical_points}"
            )
            return AnomalyResult(
                is_anomaly=False,
                score=0.0,
                method=self.method,
                actual_value=current_rate,
                confidence=0.0,
                details={"reason": "insufficient_data"}
            )

        if self.method == StatisticalMethod.ZSCORE:
            return self._detect_zscore(current_rate, historical_rates)
        elif self.method == StatisticalMethod.IQR:
            return self._detect_iqr(current_rate, historical_rates)
        elif self.method == StatisticalMethod.MOVING_AVERAGE:
            return self._detect_moving_average(current_rate, historical_rates)
        else:
            raise ValueError(f"Unsupported method: {self.method}")

    def _detect_zscore(
        self,
        current: float,
        historical: List[float]
    ) -> AnomalyResult:
        """
        Detect anomaly using Z-score method (standard deviations from mean).

        A Z-score measures how many standard deviations a value is from the mean.
        Values beyond the threshold are considered anomalous.
        """
        try:
            mean = statistics.mean(historical)
            if len(historical) < 2:
                stdev = 0
            else:
                stdev = statistics.stdev(historical)

            # Avoid division by zero
            if stdev == 0:
                # All historical values are the same
                is_anomaly = abs(current - mean) > 0.01  # Small epsilon
                score = 1.0 if is_anomaly else 0.0
                zscore = 0.0
            else:
                zscore = abs(current - mean) / stdev
                is_anomaly = zscore > self.sensitivity
                # Normalize score to 0-1 range (values > 5 sigma = 1.0)
                score = min(1.0, zscore / 5.0)

            return AnomalyResult(
                is_anomaly=is_anomaly,
                score=score,
                method=StatisticalMethod.ZSCORE,
                baseline_value=mean,
                actual_value=current,
                threshold=self.sensitivity,
                confidence=min(1.0, len(historical) / 100.0),  # More data = higher confidence
                details={
                    "zscore": zscore,
                    "mean": mean,
                    "stdev": stdev,
                    "historical_count": len(historical)
                }
            )

        except statistics.StatisticsError as e:
            logger.error(f"Statistics error in Z-score detection: {e}")
            return AnomalyResult(
                is_anomaly=False,
                score=0.0,
                method=StatisticalMethod.ZSCORE,
                actual_value=current,
                confidence=0.0,
                details={"error": str(e)}
            )

    def _detect_iqr(
        self,
        current: float,
        historical: List[float]
    ) -> AnomalyResult:
        """
        Detect anomaly using Interquartile Range (IQR) method.

        IQR is the range between the 25th and 75th percentiles. Values beyond
        Q3 + (IQR * sensitivity) or below Q1 - (IQR * sensitivity) are anomalous.
        More robust to outliers than Z-score.
        """
        try:
            sorted_data = sorted(historical)
            n = len(sorted_data)

            # Calculate quartiles
            q1_idx = n // 4
            q3_idx = 3 * n // 4

            q1 = sorted_data[q1_idx]
            q3 = sorted_data[q3_idx]
            iqr = q3 - q1

            # Calculate bounds
            lower_bound = q1 - (self.sensitivity * iqr)
            upper_bound = q3 + (self.sensitivity * iqr)

            is_anomaly = current < lower_bound or current > upper_bound

            # Calculate score based on distance from bounds
            if current < lower_bound:
                distance = lower_bound - current
                score = min(1.0, distance / (iqr * 3))
            elif current > upper_bound:
                distance = current - upper_bound
                score = min(1.0, distance / (iqr * 3))
            else:
                score = 0.0

            median = statistics.median(historical)

            return AnomalyResult(
                is_anomaly=is_anomaly,
                score=score,
                method=StatisticalMethod.IQR,
                baseline_value=median,
                actual_value=current,
                threshold=self.sensitivity,
                confidence=min(1.0, len(historical) / 100.0),
                details={
                    "q1": q1,
                    "q3": q3,
                    "iqr": iqr,
                    "lower_bound": lower_bound,
                    "upper_bound": upper_bound,
                    "median": median
                }
            )

        except Exception as e:
            logger.error(f"Error in IQR detection: {e}")
            return AnomalyResult(
                is_anomaly=False,
                score=0.0,
                method=StatisticalMethod.IQR,
                actual_value=current,
                confidence=0.0,
                details={"error": str(e)}
            )

    def _detect_moving_average(
        self,
        current: float,
        historical: List[float],
        window_size: int = 10
    ) -> AnomalyResult:
        """
        Detect anomaly using moving average deviation.

        Compares current value against moving average of recent historical data.
        Good for detecting sudden changes in trending data.
        """
        try:
            # Use last N points for moving average
            window = historical[-window_size:] if len(historical) > window_size else historical

            moving_avg = statistics.mean(window)

            if len(window) < 2:
                stdev = 0
            else:
                stdev = statistics.stdev(window)

            # Calculate deviation from moving average
            if stdev == 0:
                is_anomaly = abs(current - moving_avg) > 0.01
                score = 1.0 if is_anomaly else 0.0
                deviation = 0.0
            else:
                deviation = abs(current - moving_avg) / stdev
                is_anomaly = deviation > self.sensitivity
                score = min(1.0, deviation / 5.0)

            return AnomalyResult(
                is_anomaly=is_anomaly,
                score=score,
                method=StatisticalMethod.MOVING_AVERAGE,
                baseline_value=moving_avg,
                actual_value=current,
                threshold=self.sensitivity,
                confidence=min(1.0, len(historical) / 50.0),
                details={
                    "moving_average": moving_avg,
                    "window_size": len(window),
                    "stdev": stdev,
                    "deviation": deviation
                }
            )

        except Exception as e:
            logger.error(f"Error in moving average detection: {e}")
            return AnomalyResult(
                is_anomaly=False,
                score=0.0,
                method=StatisticalMethod.MOVING_AVERAGE,
                actual_value=current,
                confidence=0.0,
                details={"error": str(e)}
            )

    def detect_event_pattern_anomaly(
        self,
        event_counts: Dict[str, int],
        historical_patterns: List[Dict[str, int]]
    ) -> Dict[str, AnomalyResult]:
        """
        Detect anomalies in event type distribution patterns.

        Args:
            event_counts: Current event type counts {"ERROR": 50, "WARN": 20}
            historical_patterns: List of historical event count dictionaries

        Returns:
            Dictionary mapping event types to their anomaly results
        """
        results = {}

        # Analyze each event type
        for event_type in event_counts.keys():
            current_count = event_counts[event_type]
            historical_counts = [
                pattern.get(event_type, 0)
                for pattern in historical_patterns
            ]

            if historical_counts:
                result = self.detect_error_rate_anomaly(
                    current_count,
                    historical_counts
                )
                results[event_type] = result

        return results

    def detect_service_anomaly(
        self,
        service_metrics: Dict[str, float],
        historical_service_metrics: List[Dict[str, float]]
    ) -> Dict[str, AnomalyResult]:
        """
        Detect anomalies in service-level metrics.

        Args:
            service_metrics: Current service metrics {"api": 120.5, "db": 45.2}
            historical_service_metrics: Historical metrics for comparison

        Returns:
            Dictionary mapping services to their anomaly results
        """
        results = {}

        for service, current_value in service_metrics.items():
            historical_values = [
                metrics.get(service, 0.0)
                for metrics in historical_service_metrics
                if service in metrics
            ]

            if historical_values:
                result = self.detect_error_rate_anomaly(
                    current_value,
                    historical_values
                )
                results[service] = result

        return results
