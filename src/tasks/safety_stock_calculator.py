"""
Safety Stock Calculator
Calculates optimal safety stock levels based on demand variability and lead times
"""

import logging
from typing import Dict, Any
import pandas as pd
import numpy as np
from scipy import stats
from sqlalchemy import create_engine
import os

logger = logging.getLogger(__name__)


def calculate_safety_stock(warehouse_data: Dict[str, Any], 
                          store_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate safety stock levels based on demand variability
    
    Uses the formula: Safety Stock = Z-score × σ_LT × √(Lead Time)
    Where σ_LT is the standard deviation of demand during lead time
    
    Args:
        warehouse_data: Processed warehouse inventory data
        store_data: Processed store inventory data
        
    Returns:
        Safety stock recommendations for each product
    """
    logger.info("Calculating safety stock levels...")
    
    try:
        # Fetch historical demand data
        db_url = os.getenv('INVENTORY_DB_URL', 'postgresql://user:pass@localhost/inventory')
        engine = create_engine(db_url)
        
        demand_query = """
            SELECT 
                product_id,
                AVG(daily_demand) as avg_daily_demand,
                STDDEV(daily_demand) as stddev_daily_demand,
                MAX(daily_demand) as max_daily_demand,
                MIN(daily_demand) as min_daily_demand,
                COUNT(*) as days_of_history
            FROM (
                SELECT 
                    product_id,
                    DATE(transaction_date) as transaction_date,
                    SUM(quantity) as daily_demand
                FROM sales_transactions
                WHERE transaction_date >= CURRENT_DATE - INTERVAL '90 days'
                AND transaction_type = 'sale'
                GROUP BY product_id, DATE(transaction_date)
            ) daily_sales
            GROUP BY product_id
            HAVING COUNT(*) >= 30  -- Require at least 30 days of history
        """
        
        demand_df = pd.read_sql(demand_query, engine)
        
        # Get product lead times
        warehouse_df = pd.DataFrame(warehouse_data['warehouse_summary'])
        store_df = pd.DataFrame(store_data['store_summary'])
        
        # Merge data
        safety_stock_df = demand_df.copy()
        
        # Calculate safety stock for different service levels
        service_levels = {
            'standard': 0.95,  # 95% service level (Z = 1.65)
            'high': 0.99,      # 99% service level (Z = 2.33)
            'critical': 0.995  # 99.5% service level (Z = 2.58)
        }
        
        # Assume average lead time of 7 days (should be product-specific)
        lead_time_days = 7
        
        for level_name, service_level in service_levels.items():
            z_score = stats.norm.ppf(service_level)
            safety_stock_df[f'safety_stock_{level_name}'] = (
                z_score * 
                safety_stock_df['stddev_daily_demand'] * 
                np.sqrt(lead_time_days)
            ).round(0)
        
        # Calculate reorder point (ROP)
        safety_stock_df['reorder_point'] = (
            safety_stock_df['avg_daily_demand'] * lead_time_days + 
            safety_stock_df['safety_stock_standard']
        ).round(0)
        
        # Merge with current inventory levels
        safety_stock_df = safety_stock_df.merge(
            warehouse_df[['product_id', 'total_available']],
            on='product_id',
            how='left'
        )
        
        safety_stock_df = safety_stock_df.merge(
            store_df[['product_id', 'total_available']],
            on='product_id',
            how='left',
            suffixes=('_warehouse', '_store')
        )
        
        # Calculate current stock status
        safety_stock_df['total_available'] = (
            safety_stock_df['total_available_warehouse'].fillna(0) +
            safety_stock_df['total_available_store'].fillna(0)
        )
        
        safety_stock_df['stock_status'] = safety_stock_df.apply(
            lambda row: 'critical' if row['total_available'] < row['safety_stock_critical']
                       else 'low' if row['total_available'] < row['safety_stock_standard']
                       else 'adequate' if row['total_available'] < row['reorder_point']
                       else 'excess',
            axis=1
        )
        
        # Calculate metrics
        status_counts = safety_stock_df['stock_status'].value_counts().to_dict()
        
        result = {
            'calculation_timestamp': pd.Timestamp.utcnow().isoformat(),
            'products_analyzed': len(safety_stock_df),
            'lead_time_days': lead_time_days,
            'service_levels': service_levels,
            'safety_stock_data': safety_stock_df.to_dict('records'),
            'summary': {
                'critical_stock_items': status_counts.get('critical', 0),
                'low_stock_items': status_counts.get('low', 0),
                'adequate_stock_items': status_counts.get('adequate', 0),
                'excess_stock_items': status_counts.get('excess', 0),
                'avg_safety_stock_units': float(safety_stock_df['safety_stock_standard'].mean()),
                'total_safety_stock_needed': float(safety_stock_df['safety_stock_standard'].sum())
            }
        }
        
        logger.info(f"Calculated safety stock for {result['products_analyzed']} products")
        logger.warning(f"Critical stock items: {result['summary']['critical_stock_items']}, "
                      f"Low stock items: {result['summary']['low_stock_items']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error calculating safety stock: {str(e)}")
        raise
