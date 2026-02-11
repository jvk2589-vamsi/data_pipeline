"""
Reorder Engine
Evaluates reorder thresholds and generates purchase order recommendations
"""

import logging
from typing import Dict, Any, List
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine
import os

logger = logging.getLogger(__name__)


def evaluate_reorder_thresholds(safety_stock_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate which items need reordering based on safety stock and thresholds
    
    Args:
        safety_stock_data: Safety stock calculations from previous task
        
    Returns:
        Reorder recommendations with quantities and priorities
    """
    logger.info("Evaluating reorder thresholds...")
    
    try:
        safety_df = pd.DataFrame(safety_stock_data['safety_stock_data'])
        
        # Filter items that need reordering
        reorder_df = safety_df[
            (safety_df['stock_status'].isin(['critical', 'low', 'adequate'])) &
            (safety_df['total_available'] <= safety_df['reorder_point'])
        ].copy()
        
        if len(reorder_df) == 0:
            logger.info("No items require reordering at this time")
            return {
                'evaluation_timestamp': datetime.utcnow().isoformat(),
                'items_needing_reorder': 0,
                'reorder_recommendations': [],
                'summary': {
                    'total_order_value': 0.0,
                    'critical_orders': 0,
                    'high_priority_orders': 0,
                    'normal_priority_orders': 0
                }
            }
        
        # Get supplier and cost information
        db_url = os.getenv('INVENTORY_DB_URL', 'postgresql://user:pass@localhost/inventory')
        engine = create_engine(db_url)
        
        product_query = """
            SELECT 
                product_id,
                supplier_id,
                supplier_name,
                unit_cost,
                moq,  -- Minimum Order Quantity
                lead_time_days,
                pack_size
            FROM products p
            JOIN suppliers s ON p.supplier_id = s.supplier_id
        """
        
        product_df = pd.read_sql(product_query, engine)
        
        # Merge with reorder data
        reorder_df = reorder_df.merge(product_df, on='product_id', how='left')
        
        # Calculate order quantity using Economic Order Quantity (EOQ) principles
        # Simplified EOQ: considers demand, holding costs, and order costs
        reorder_df['shortage_quantity'] = (
            reorder_df['reorder_point'] - reorder_df['total_available']
        ).clip(lower=0)
        
        # Order quantity should cover: shortage + buffer for lead time demand
        reorder_df['lead_time_demand'] = (
            reorder_df['avg_daily_demand'] * reorder_df['lead_time_days']
        )
        
        reorder_df['recommended_order_qty'] = (
            reorder_df['shortage_quantity'] + 
            reorder_df['lead_time_demand'] +
            reorder_df['safety_stock_standard']
        ).round(0)
        
        # Adjust for MOQ (Minimum Order Quantity)
        reorder_df['recommended_order_qty'] = np.maximum(
            reorder_df['recommended_order_qty'],
            reorder_df['moq'].fillna(1)
        )
        
        # Round up to pack size
        reorder_df['recommended_order_qty'] = (
            np.ceil(reorder_df['recommended_order_qty'] / reorder_df['pack_size']) * 
            reorder_df['pack_size']
        ).fillna(reorder_df['recommended_order_qty'])
        
        # Calculate order value
        reorder_df['order_value'] = (
            reorder_df['recommended_order_qty'] * reorder_df['unit_cost']
        )
        
        # Assign priority based on stock status
        priority_mapping = {
            'critical': 1,
            'low': 2,
            'adequate': 3
        }
        reorder_df['priority'] = reorder_df['stock_status'].map(priority_mapping)
        reorder_df['priority_label'] = reorder_df['stock_status'].map({
            'critical': 'CRITICAL',
            'low': 'HIGH',
            'adequate': 'NORMAL'
        })
        
        # Calculate expected delivery date
        reorder_df['expected_delivery_date'] = (
            datetime.utcnow() + 
            pd.to_timedelta(reorder_df['lead_time_days'], unit='days')
        ).dt.strftime('%Y-%m-%d')
        
        # Sort by priority and value
        reorder_df = reorder_df.sort_values(['priority', 'order_value'], ascending=[True, False])
        
        # Generate order recommendations
        recommendations = []
        for _, row in reorder_df.iterrows():
            recommendations.append({
                'product_id': row['product_id'],
                'current_stock': float(row['total_available']),
                'reorder_point': float(row['reorder_point']),
                'safety_stock': float(row['safety_stock_standard']),
                'shortage_qty': float(row['shortage_quantity']),
                'recommended_order_qty': int(row['recommended_order_qty']),
                'unit_cost': float(row['unit_cost']),
                'total_order_value': float(row['order_value']),
                'supplier_id': row['supplier_id'],
                'supplier_name': row['supplier_name'],
                'priority': int(row['priority']),
                'priority_label': row['priority_label'],
                'lead_time_days': int(row['lead_time_days']),
                'expected_delivery_date': row['expected_delivery_date'],
                'avg_daily_demand': float(row['avg_daily_demand']),
                'moq': int(row['moq']) if pd.notna(row['moq']) else None
            })
        
        # Calculate summary metrics
        summary = {
            'total_order_value': float(reorder_df['order_value'].sum()),
            'total_units_to_order': int(reorder_df['recommended_order_qty'].sum()),
            'critical_orders': len(reorder_df[reorder_df['priority'] == 1]),
            'high_priority_orders': len(reorder_df[reorder_df['priority'] == 2]),
            'normal_priority_orders': len(reorder_df[reorder_df['priority'] == 3]),
            'unique_suppliers': int(reorder_df['supplier_id'].nunique()),
            'avg_order_value': float(reorder_df['order_value'].mean())
        }
        
        result = {
            'evaluation_timestamp': datetime.utcnow().isoformat(),
            'items_needing_reorder': len(recommendations),
            'reorder_recommendations': recommendations,
            'summary': summary
        }
        
        logger.info(f"Generated {len(recommendations)} reorder recommendations")
        logger.info(f"Total order value: ${summary['total_order_value']:,.2f}")
        logger.warning(f"Critical priority orders: {summary['critical_orders']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error evaluating reorder thresholds: {str(e)}")
        raise
