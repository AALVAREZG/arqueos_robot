"""
Unit tests for config.py module.

Tests cover:
- Environment variable loading
- Default values
- Configuration validation
"""

import pytest
import os
from unittest.mock import patch


class TestConfigDefaults:
    """Tests for default configuration values."""

    @pytest.mark.unit
    def test_default_rabbitmq_host(self):
        """Test that RABBITMQ_HOST defaults to 'localhost'."""
        with patch.dict(os.environ, {}, clear=True):
            # Re-import config to get fresh values
            import importlib
            import config
            importlib.reload(config)

            assert config.RABBITMQ_HOST == 'localhost'

    @pytest.mark.unit
    def test_default_rabbitmq_port(self):
        """Test that RABBITMQ_PORT defaults to 5672."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import config
            importlib.reload(config)

            assert config.RABBITMQ_PORT == 5672

    @pytest.mark.unit
    def test_default_rabbitmq_user(self):
        """Test that RABBITMQ_USER defaults to 'guest'."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import config
            importlib.reload(config)

            assert config.RABBITMQ_USER == 'guest'

    @pytest.mark.unit
    def test_default_rabbitmq_password(self):
        """Test that RABBITMQ_PASS defaults to 'guest'."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import config
            importlib.reload(config)

            assert config.RABBITMQ_PASS == 'guest'


class TestConfigEnvironmentVariables:
    """Tests for environment variable override."""

    @pytest.mark.unit
    def test_custom_rabbitmq_host(self):
        """Test that RABBITMQ_HOST can be set via environment."""
        with patch.dict(os.environ, {'RABBITMQ_HOST': 'rabbitmq.example.com'}):
            import importlib
            import config
            importlib.reload(config)

            assert config.RABBITMQ_HOST == 'rabbitmq.example.com'

    @pytest.mark.unit
    def test_custom_rabbitmq_port(self):
        """Test that RABBITMQ_PORT can be set via environment."""
        with patch.dict(os.environ, {'RABBITMQ_PORT': '15672'}):
            import importlib
            import config
            importlib.reload(config)

            assert config.RABBITMQ_PORT == 15672

    @pytest.mark.unit
    def test_custom_rabbitmq_credentials(self):
        """Test that RabbitMQ credentials can be set via environment."""
        with patch.dict(os.environ, {
            'RABBITMQ_USER': 'admin',
            'RABBITMQ_PASS': 'secure_password'
        }):
            import importlib
            import config
            importlib.reload(config)

            assert config.RABBITMQ_USER == 'admin'
            assert config.RABBITMQ_PASS == 'secure_password'

    @pytest.mark.unit
    def test_all_custom_values(self):
        """Test that all config values can be customized."""
        with patch.dict(os.environ, {
            'RABBITMQ_HOST': 'custom.host.com',
            'RABBITMQ_PORT': '5673',
            'RABBITMQ_USER': 'custom_user',
            'RABBITMQ_PASS': 'custom_pass'
        }):
            import importlib
            import config
            importlib.reload(config)

            assert config.RABBITMQ_HOST == 'custom.host.com'
            assert config.RABBITMQ_PORT == 5673
            assert config.RABBITMQ_USER == 'custom_user'
            assert config.RABBITMQ_PASS == 'custom_pass'
