"""
LSTM-based time-series anomaly detection for ADAPT-RCA.

LSTM (Long Short-Term Memory) networks are well-suited for time-series
anomaly detection as they can learn temporal patterns and dependencies.

This module uses an autoencoder architecture:
1. Encoder: Compresses time series into latent representation
2. Decoder: Reconstructs original time series
3. Anomalies: High reconstruction error indicates anomaly

Key advantages:
- Captures temporal dependencies
- Learns normal patterns automatically
- Effective for sequential data
- Can detect complex anomalies

Classes:
    LSTMTimeSeriesDetector: LSTM-based anomaly detector
    TimeSeriesAnomaly: Detection result with reconstruction error

Example:
    >>> from adapt_rca.ml import LSTMTimeSeriesDetector
    >>> detector = LSTMTimeSeriesDetector(sequence_length=24)
    >>>
    >>> # Train on normal time series data (hourly error rates)
    >>> historical_data = [0.01, 0.02, 0.01, 0.015, ...]  # 1000+ points
    >>> detector.train(historical_data, epochs=50)
    >>>
    >>> # Detect anomalies in new data
    >>> recent_data = [0.01, 0.02, 0.15, 0.20, ...]  # New 24 points
    >>> result = detector.detect(recent_data)
    >>> if result.is_anomaly:
    ...     print(f"Anomaly! Reconstruction error: {result.reconstruction_error:.3f}")
"""

import logging
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TimeSeriesAnomaly:
    """Result from LSTM time-series anomaly detection."""

    is_anomaly: bool
    reconstruction_error: float
    threshold: float
    sequence: List[float]
    reconstructed: List[float]
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_anomaly": self.is_anomaly,
            "reconstruction_error": float(self.reconstruction_error),
            "threshold": float(self.threshold),
            "sequence": [float(x) for x in self.sequence],
            "reconstructed": [float(x) for x in self.reconstructed],
            "timestamp": self.timestamp.isoformat()
        }


class LSTMTimeSeriesDetector:
    """
    LSTM autoencoder for time-series anomaly detection.

    Uses TensorFlow/Keras to build an LSTM autoencoder that learns
    normal patterns in time series data. Anomalies are detected by
    high reconstruction error.

    Args:
        sequence_length: Length of input sequences (e.g., 24 for hourly data)
        lstm_units: Number of LSTM units in encoder/decoder
        threshold_percentile: Percentile for anomaly threshold (e.g., 95)

    Example:
        >>> detector = LSTMTimeSeriesDetector(sequence_length=24)
        >>> detector.train(historical_error_rates, epochs=50)
        >>> result = detector.detect(recent_error_rates)
    """

    def __init__(
        self,
        sequence_length: int = 24,
        lstm_units: int = 64,
        threshold_percentile: float = 95.0,
        random_state: int = 42
    ):
        """Initialize LSTM detector."""
        self.sequence_length = sequence_length
        self.lstm_units = lstm_units
        self.threshold_percentile = threshold_percentile
        self.random_state = random_state

        self.model: Optional[Any] = None
        self.threshold: Optional[float] = None
        self.is_trained: bool = False
        self.scaler: Optional[Any] = None
        self.training_stats: Dict[str, Any] = {}

        # Set random seeds
        np.random.seed(random_state)

    def train(
        self,
        data: List[float],
        epochs: int = 50,
        batch_size: int = 32,
        validation_split: float = 0.2,
        verbose: int = 0
    ) -> Dict[str, Any]:
        """
        Train LSTM autoencoder on time series data.

        Args:
            data: Time series data (normal behavior only)
            epochs: Number of training epochs
            batch_size: Batch size for training
            validation_split: Fraction of data for validation
            verbose: Verbosity level (0=silent, 1=progress, 2=detailed)

        Returns:
            Training statistics

        Raises:
            ValueError: If data is invalid
            ImportError: If TensorFlow is not installed

        Example:
            >>> # Train on 1000 hourly error rate samples
            >>> error_rates = [0.01, 0.02, 0.015, ...]  # 1000 points
            >>> stats = detector.train(error_rates, epochs=50)
            >>> print(f"Trained with loss: {stats['final_loss']:.4f}")
        """
        try:
            import tensorflow as tf
            from sklearn.preprocessing import StandardScaler
        except ImportError:
            raise ImportError(
                "TensorFlow and scikit-learn required for LSTM detector. "
                "Install with: pip install tensorflow scikit-learn"
            )

        # Validate data
        if len(data) < self.sequence_length * 2:
            raise ValueError(
                f"Need at least {self.sequence_length * 2} data points "
                f"for training (got {len(data)})"
            )

        logger.info(
            f"Training LSTM autoencoder on {len(data)} samples "
            f"with sequence length {self.sequence_length}"
        )

        # Prepare data
        data_array = np.array(data).reshape(-1, 1)

        # Normalize data
        self.scaler = StandardScaler()
        data_scaled = self.scaler.fit_transform(data_array)

        # Create sequences
        X = self._create_sequences(data_scaled.flatten())

        logger.info(f"Created {len(X)} training sequences")

        # Build model
        self.model = self._build_model()

        # Train model
        history = self.model.fit(
            X, X,  # Autoencoder: input = output
            epochs=epochs,
            batch_size=batch_size,
            validation_split=validation_split,
            verbose=verbose,
            shuffle=True
        )

        # Calculate reconstruction errors on training data
        X_reconstructed = self.model.predict(X, verbose=0)
        reconstruction_errors = np.mean(np.abs(X - X_reconstructed), axis=(1, 2))

        # Set threshold at specified percentile
        self.threshold = np.percentile(
            reconstruction_errors,
            self.threshold_percentile
        )

        self.is_trained = True

        # Store training stats
        self.training_stats = {
            "sample_count": len(data),
            "sequence_count": len(X),
            "sequence_length": self.sequence_length,
            "lstm_units": self.lstm_units,
            "epochs": epochs,
            "final_loss": float(history.history['loss'][-1]),
            "final_val_loss": float(history.history.get('val_loss', [0])[-1]),
            "threshold": float(self.threshold),
            "threshold_percentile": self.threshold_percentile,
            "trained_at": datetime.now().isoformat()
        }

        logger.info(
            f"Training complete. Loss: {self.training_stats['final_loss']:.4f}, "
            f"Threshold: {self.threshold:.4f}"
        )

        return self.training_stats

    def detect(
        self,
        sequence: List[float],
        custom_threshold: Optional[float] = None
    ) -> TimeSeriesAnomaly:
        """
        Detect if time series sequence is anomalous.

        Args:
            sequence: Time series sequence (must be sequence_length long)
            custom_threshold: Custom threshold for anomaly detection

        Returns:
            TimeSeriesAnomaly result

        Raises:
            RuntimeError: If model is not trained
            ValueError: If sequence length is incorrect

        Example:
            >>> recent_data = [0.01, 0.02, 0.15, 0.20, ...]  # 24 points
            >>> result = detector.detect(recent_data)
            >>> if result.is_anomaly:
            ...     print(f"Anomaly detected! Error: {result.reconstruction_error:.3f}")
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model is not trained. Call train() first.")

        if len(sequence) != self.sequence_length:
            raise ValueError(
                f"Sequence must be {self.sequence_length} long "
                f"(got {len(sequence)})"
            )

        # Normalize sequence
        sequence_array = np.array(sequence).reshape(-1, 1)
        sequence_scaled = self.scaler.transform(sequence_array).flatten()

        # Reshape for model input
        X = sequence_scaled.reshape(1, self.sequence_length, 1)

        # Reconstruct
        X_reconstructed = self.model.predict(X, verbose=0)

        # Calculate reconstruction error
        reconstruction_error = float(np.mean(np.abs(X - X_reconstructed)))

        # Use custom or default threshold
        threshold = custom_threshold if custom_threshold is not None else self.threshold

        # Determine if anomaly
        is_anomaly = reconstruction_error > threshold

        # Inverse transform for results
        reconstructed = self.scaler.inverse_transform(
            X_reconstructed[0]
        ).flatten().tolist()

        result = TimeSeriesAnomaly(
            is_anomaly=is_anomaly,
            reconstruction_error=reconstruction_error,
            threshold=threshold,
            sequence=sequence,
            reconstructed=reconstructed,
            timestamp=datetime.now()
        )

        if is_anomaly:
            logger.warning(
                f"Anomaly detected! Reconstruction error: {reconstruction_error:.4f} "
                f"(threshold: {threshold:.4f})"
            )
        else:
            logger.debug(
                f"Normal behavior. Reconstruction error: {reconstruction_error:.4f}"
            )

        return result

    def detect_online(
        self,
        new_value: float,
        historical_sequence: List[float]
    ) -> TimeSeriesAnomaly:
        """
        Detect anomaly in online/streaming mode.

        Takes a new value and sliding window of historical values,
        creates a sequence, and detects if anomalous.

        Args:
            new_value: Latest value
            historical_sequence: Previous sequence_length - 1 values

        Returns:
            TimeSeriesAnomaly result

        Example:
            >>> # Sliding window detection
            >>> window = recent_data[-23:]  # Last 23 values
            >>> new_value = latest_error_rate
            >>> result = detector.detect_online(new_value, window)
        """
        if len(historical_sequence) != self.sequence_length - 1:
            raise ValueError(
                f"Historical sequence must be {self.sequence_length - 1} long "
                f"(got {len(historical_sequence)})"
            )

        # Create full sequence
        full_sequence = historical_sequence + [new_value]

        return self.detect(full_sequence)

    def save(self, path: str | Path) -> None:
        """
        Save trained model to disk.

        Args:
            path: Directory path to save model (creates model.h5 and metadata.pkl)

        Example:
            >>> detector.train(data)
            >>> detector.save("models/lstm_detector")
        """
        if not self.is_trained:
            raise RuntimeError("Cannot save untrained model")

        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save Keras model
        model_path = path / "model.h5"
        self.model.save(model_path)

        # Save metadata
        metadata = {
            "sequence_length": self.sequence_length,
            "lstm_units": self.lstm_units,
            "threshold_percentile": self.threshold_percentile,
            "random_state": self.random_state,
            "threshold": self.threshold,
            "scaler": self.scaler,
            "training_stats": self.training_stats
        }

        metadata_path = path / "metadata.pkl"
        with open(metadata_path, 'wb') as f:
            pickle.dump(metadata, f)

        logger.info(f"Model saved to {path}")

    def load(self, path: str | Path) -> None:
        """
        Load trained model from disk.

        Args:
            path: Directory path containing model.h5 and metadata.pkl

        Example:
            >>> detector = LSTMTimeSeriesDetector()
            >>> detector.load("models/lstm_detector")
            >>> result = detector.detect(recent_data)
        """
        try:
            import tensorflow as tf
        except ImportError:
            raise ImportError("TensorFlow required to load model")

        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Model directory not found: {path}")

        # Load Keras model
        model_path = path / "model.h5"
        self.model = tf.keras.models.load_model(model_path)

        # Load metadata
        metadata_path = path / "metadata.pkl"
        with open(metadata_path, 'rb') as f:
            metadata = pickle.load(f)

        self.sequence_length = metadata["sequence_length"]
        self.lstm_units = metadata["lstm_units"]
        self.threshold_percentile = metadata["threshold_percentile"]
        self.random_state = metadata["random_state"]
        self.threshold = metadata["threshold"]
        self.scaler = metadata["scaler"]
        self.training_stats = metadata["training_stats"]
        self.is_trained = True

        logger.info(f"Model loaded from {path}")

    def _build_model(self) -> Any:
        """Build LSTM autoencoder model."""
        import tensorflow as tf
        from tensorflow.keras import layers, models

        # Encoder
        encoder_inputs = layers.Input(shape=(self.sequence_length, 1))
        encoder_lstm = layers.LSTM(self.lstm_units, return_sequences=False)(encoder_inputs)

        # Decoder
        decoder_lstm = layers.RepeatVector(self.sequence_length)(encoder_lstm)
        decoder_lstm = layers.LSTM(self.lstm_units, return_sequences=True)(decoder_lstm)
        decoder_outputs = layers.TimeDistributed(layers.Dense(1))(decoder_lstm)

        # Autoencoder
        model = models.Model(encoder_inputs, decoder_outputs)

        # Compile
        model.compile(
            optimizer='adam',
            loss='mae'  # Mean Absolute Error
        )

        logger.debug(f"Built LSTM autoencoder: {self.lstm_units} units")

        return model

    def _create_sequences(self, data: np.ndarray) -> np.ndarray:
        """Create overlapping sequences from time series data."""
        sequences = []

        for i in range(len(data) - self.sequence_length + 1):
            sequence = data[i:i + self.sequence_length]
            sequences.append(sequence)

        return np.array(sequences).reshape(-1, self.sequence_length, 1)

    def get_training_stats(self) -> Dict[str, Any]:
        """Get training statistics."""
        if not self.is_trained:
            return {"is_trained": False}

        return {
            "is_trained": True,
            **self.training_stats
        }
