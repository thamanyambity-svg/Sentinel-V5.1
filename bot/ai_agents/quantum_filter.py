
import numpy as np

class QuantumFilter:
    """
    Quantum Noise Filter (Kalman Filter Implementation).
    Estimates the hidden 'True State' (Price & Velocity) from noisy observations.
    
    State Vector x = [Price, Velocity]
    """
    def __init__(self, process_noise=1e-5, measurement_noise=1e-1):
        # Initial State: x = [p, v]
        self.x = np.array([[0.0], [0.0]])
        
        # State Covariance P (Uncertainty)
        self.P = np.array([[1.0, 0.0],
                           [0.0, 1.0]])
        
        # State Transition Matrix F (Physics: NewPos = OldPos + Vel*dt)
        # Assuming dt = 1 (1 candle)
        self.F = np.array([[1.0, 1.0],
                           [0.0, 1.0]])
                           
        # Measurement Matrix H (We only observe Price, not Velocity)
        self.H = np.array([[1.0, 0.0]])
        
        # Measurement Noise Covariance R (Sensor Noise)
        self.R = np.array([[measurement_noise]])
        
        # Process Noise Covariance Q (System Uncertainty)
        self.Q = np.array([[process_noise, 0.0],
                           [0.0, process_noise]])
                           
        self.initialized = False

    def update(self, measurement):
        """
        Update the filter with a new price observation.
        Returns: (Estimated Price, Estimated Velocity)
        """
        z = np.array([[measurement]])
        
        if not self.initialized:
            self.x = np.array([[measurement], [0.0]])
            self.initialized = True
            return measurement, 0.0
            
        # 1. PREDICT (Project state ahead)
        x_pred = self.F @ self.x
        P_pred = self.F @ self.P @ self.F.T + self.Q
        
        # 2. UPDATE (Correct based on measurement)
        # Innovation (Residual) y = z - Hx
        y = z - self.H @ x_pred
        
        # Innovation Covariance S = HPH' + R
        S = self.H @ P_pred @ self.H.T + self.R
        
        # Kalman Gain K = PH'S^-1
        K = P_pred @ self.H.T @ np.linalg.inv(S)
        
        # Update State x = x_pred + Ky
        self.x = x_pred + K @ y
        
        # Update Covariance P = (I - KH)P_pred
        I = np.eye(2)
        self.P = (I - K @ self.H) @ P_pred
        
        est_price = float(self.x[0][0])
        est_velocity = float(self.x[1][0])
        
        return est_price, est_velocity

    def batch_filter(self, prices):
        """Run filter on a history of prices (for backtesting)"""
        estimates = []
        for p in prices:
            est, _ = self.update(p)
            estimates.append(est)
        return estimates
