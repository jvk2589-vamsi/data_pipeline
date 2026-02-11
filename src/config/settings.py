"""
Configuration Settings
Centralized configuration for the Inventory Optimization Pipeline
"""

import os
from typing import Dict, Any


class Config:
    """Configuration class for inventory optimization pipeline"""
    
    # Database Configuration
    INVENTORY_DB_URL = os.getenv(
        'INVENTORY_DB_URL',
        'postgresql://inventory_user:password@localhost:5432/inventory_db'
    )
    
    # Safety Stock Configuration
    SAFETY_STOCK_SERVICE_LEVELS = {
        'standard': 0.95,  # 95% service level
        'high': 0.99,      # 99% service level
        'critical': 0.995  # 99.5% service level
    }
    
    DEFAULT_LEAD_TIME_DAYS = int(os.getenv('DEFAULT_LEAD_TIME_DAYS', '7'))
    MIN_HISTORY_DAYS = int(os.getenv('MIN_HISTORY_DAYS', '30'))
    
    # Reorder Configuration
    MIN_TRANSFER_QUANTITY = int(os.getenv('MIN_TRANSFER_QUANTITY', '10'))
    TARGET_DAYS_OF_SUPPLY = int(os.getenv('TARGET_DAYS_OF_SUPPLY', '14'))
    
    # Transfer Cost Configuration
    BASE_TRANSFER_COST_PER_UNIT = float(os.getenv('BASE_TRANSFER_COST_PER_UNIT', '2.50'))
    TRANSFER_ESTIMATED_DAYS = int(os.getenv('TRANSFER_ESTIMATED_DAYS', '2'))
    
    # Approval Configuration
    AUTO_APPROVE_THRESHOLD = float(os.getenv('AUTO_APPROVE_THRESHOLD', '5000'))
    
    APPROVAL_TIERS = {
        'executive': {'threshold': 100000, 'approvers': ['vp_operations', 'cfo', 'ceo']},
        'director': {'threshold': 50000, 'approvers': ['director_supply_chain', 'director_finance']},
        'manager': {'threshold': 10000, 'approvers': ['inventory_manager', 'procurement_manager']},
        'supervisor': {'threshold': 0, 'approvers': ['inventory_supervisor']}
    }
    
    # Notification Configuration
    INVENTORY_TEAM_EMAILS = os.getenv('INVENTORY_TEAM_EMAILS', 'inventory@company.com')
    EXECUTIVE_EMAILS = os.getenv('EXECUTIVE_EMAILS', 'executives@company.com')
    PROCUREMENT_EMAILS = os.getenv('PROCUREMENT_EMAILS', 'procurement@company.com')
    
    # Email Service Configuration
    EMAIL_SERVICE_ENABLED = os.getenv('EMAIL_SERVICE_ENABLED', 'false').lower() == 'true'
    EMAIL_SERVICE_API_KEY = os.getenv('EMAIL_SERVICE_API_KEY', '')
    EMAIL_FROM_ADDRESS = os.getenv('EMAIL_FROM_ADDRESS', 'noreply@company.com')
    
    # Pipeline Configuration
    PIPELINE_SCHEDULE = os.getenv('PIPELINE_SCHEDULE', '*/15 * * * *')  # Every 15 minutes
    MAX_CONCURRENT_TASKS = int(os.getenv('MAX_CONCURRENT_TASKS', '5'))
    TASK_TIMEOUT_MINUTES = int(os.getenv('TASK_TIMEOUT_MINUTES', '30'))
    
    # Monitoring & Alerting
    ENABLE_DASHBOARD_ALERTS = os.getenv('ENABLE_DASHBOARD_ALERTS', 'true').lower() == 'true'
    CRITICAL_STOCK_THRESHOLD = int(os.getenv('CRITICAL_STOCK_THRESHOLD', '5'))
    
    # Data Retention
    HISTORY_RETENTION_DAYS = int(os.getenv('HISTORY_RETENTION_DAYS', '90'))
    
    @classmethod
    def get_approval_level(cls, total_value: float) -> Dict[str, Any]:
        """
        Determine approval level based on total value
        
        Args:
            total_value: Total value of the request
            
        Returns:
            Dictionary with approval level and required approvers
        """
        for level, config in cls.APPROVAL_TIERS.items():
            if total_value > config['threshold']:
                return {
                    'level': level,
                    'approvers': config['approvers'],
                    'threshold': config['threshold']
                }
        
        return {
            'level': 'supervisor',
            'approvers': cls.APPROVAL_TIERS['supervisor']['approvers'],
            'threshold': 0
        }
    
    @classmethod
    def validate_config(cls) -> bool:
        """
        Validate that all required configuration is present
        
        Returns:
            True if configuration is valid
        """
        required_configs = [
            'INVENTORY_DB_URL'
        ]
        
        for config_name in required_configs:
            if not getattr(cls, config_name, None):
                raise ValueError(f"Missing required configuration: {config_name}")
        
        return True


# Validate configuration on import
Config.validate_config()