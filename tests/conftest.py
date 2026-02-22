"""
Pytest configuration and fixtures for serial_ctrl_py logic tests.

This file is intentionally minimal — all mocking is done inline in test_serial_ctrl_py_logic.py
to ensure tests are self-contained and reproducible.
"""

import pytest

# No global fixtures needed — tests are pure logic and stateless.