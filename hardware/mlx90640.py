import os
import logging
from typing import Optional, List, Tuple
import numpy as np

logger = logging.getLogger("nivas.hardware.mlx90640")

MLX90640_I2C_ADDR = 0x33
MLX90640_ROWS = 24
MLX90640_COLS = 32
MLX90640_PIXELS = MLX90640_ROWS * MLX90640_COLS  # 768 pixels


def is_i2c_bus_available() -> bool:
    """Check if Linux I2C bus device nodes exist on host system (/dev/i2c-1, /dev/i2c-0)."""
    return os.path.exists("/dev/i2c-1") or os.path.exists("/dev/i2c-0")


def read_mlx90640_real_frame() -> Tuple[Optional[List[List[float]]], Optional[str]]:
    """
    Attempt to communicate with physical MLX90640 thermal sensor hardware via I2C.

    Strict Hardware Compliance:
    - Queries the physical I2C bus (address 0x33).
    - If hardware sensor is missing, disconnected, or unreadable, returns (None, error_msg).
    - NEVER generates fake sensor readings, random numbers, or dummy matrices.
    """
    if not is_i2c_bus_available():
        logger.info("I2C bus device (/dev/i2c-*) not found on system. Thermal sensor hardware absent.")
        return None, "MLX90640 hardware absent: No I2C bus detected (/dev/i2c-*)."

    # Attempt Adafruit CircuitPython MLX90640 Driver
    try:
        import board
        import busio
        import adafruit_mlx90640

        i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)
        mlx = adafruit_mlx90640.MLX90640(i2c)
        mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_2_HZ

        frame = [0.0] * MLX90640_PIXELS
        mlx.getFrame(frame)

        # Reshape 768 1D array into 32x24 2D matrix
        matrix_2d = np.array(frame, dtype=np.float32).reshape((MLX90640_ROWS, MLX90640_COLS)).tolist()
        # Round values to 2 decimal places
        matrix_2d = [[round(val, 2) for val in row] for row in matrix_2d]

        logger.info("Successfully read real 32x24 thermal frame from physical MLX90640 sensor.")
        return matrix_2d, None

    except ImportError:
        logger.info("adafruit-circuitpython-mlx90640 library not installed. Checking SMBus2 fallback.")
    except Exception as err:
        logger.warning("Error reading from physical MLX90640 sensor hardware: %s", str(err))

    # Attempt smbus2 fallback check
    try:
        from smbus2 import SMBus
        bus_num = 1 if os.path.exists("/dev/i2c-1") else 0
        with SMBus(bus_num) as bus:
            # Probe device at address 0x33
            bus.read_byte(MLX90640_I2C_ADDR)
            logger.info("MLX90640 device detected at address 0x33, but full driver initialization required.")
    except Exception as err:
        logger.info("MLX90640 sensor not responding at address 0x33: %s", str(err))

    return None, f"MLX90640 hardware sensor not detected or not responding at I2C address 0x{MLX90640_I2C_ADDR:02X}."
