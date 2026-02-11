"""
Inventory Sync Tasks
Handles real-time inventory feed and warehouse/store synchronization
"""

import logging
from datetime import datetime
from typing import Dict, List, Any
import pandas as pd
from sqlalchemy import create_engine
import os

logger = logging.getLogger(__name__)


def fetch_realtime_inventory() -> Dict[str, Any]:
    """
    Fetch real-time inventory data from source systems
    
    Returns:
        Dictionary containing inventory snapshot data
    """
    logger.info("Fetching real-time inventory feed...")
    
    try:
        # Connect to inventory database
        db_url = os.getenv('INVENTORY_DB_URL', 'postgresql://user:pass@localhost/inventory')
        engine = create_engine(db_url)
        
        # Query for latest inventory snapshot
        query = """
            SELECT 
                i.product_id,
                i.sku,
                i.product_name,
                i.location_id,
                i.location_type,
                i.quantity_on_hand,
                i.quantity_reserved,
                i.quantity_available,
                i.last_updated,
                p.unit_cost,
                p.unit_price,
                p.supplier_id,
                p.lead_time_days
            FROM inventory_current i
            JOIN products p ON i.product_id = p.product_id
            WHERE i.is_active = true
            AND i.last_updated >= NOW() - INTERVAL '1 hour'
        """
        
        df = pd.read_sql(query, engine)
        
        inventory_data = {
            'snapshot_timestamp': datetime.utcnow().isoformat(),
            'total_skus': len(df),
            'total_locations': df['location_id'].nunique(),
            'data': df.to_dict('records'),
            'summary': {
                'total_units': int(df['quantity_on_hand'].sum()),
                'total_value': float((df['quantity_on_hand'] * df['unit_cost']).sum()),
                'warehouses': len(df[df['location_type'] == 'warehouse']),
                'stores': len(df[df['location_type'] == 'store'])
            }
        }
        
        logger.info(f"Successfully fetched inventory for {inventory_data['total_skus']} SKUs "
                   f"across {inventory_data['total_locations']} locations")
        
        return inventory_data
        
    except Exception as e:
        logger.error(f"Error fetching inventory feed: {str(e)}")
        raise


def sync_warehouse_data(inventory_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sync warehouse inventory data
    
    Args:
        inventory_data: Raw inventory data from feed
        
    Returns:
        Processed warehouse inventory data
    """
    logger.info("Syncing warehouse inventory data...")
    
    try:
        df = pd.DataFrame(inventory_data['data'])
        
        # Filter for warehouse locations
        warehouse_df = df[df['location_type'] == 'warehouse'].copy()
        
        # Calculate warehouse-specific metrics
        warehouse_df['stock_turnover_ratio'] = warehouse_df['quantity_available'] / \
                                                (warehouse_df['quantity_reserved'].replace(0, 1))
        warehouse_df['days_of_supply'] = warehouse_df['quantity_available'] / \
                                         warehouse_df.groupby('product_id')['quantity_reserved'] \
                                         .transform('mean').replace(0, 1)
        
        # Aggregate by product
        warehouse_summary = warehouse_df.groupby('product_id').agg({
            'quantity_on_hand': 'sum',
            'quantity_available': 'sum',
            'quantity_reserved': 'sum',
            'location_id': 'count'
        }).reset_index()
        
        warehouse_summary.columns = ['product_id', 'total_on_hand', 'total_available', 
                                     'total_reserved', 'warehouse_count']
        
        result = {
            'sync_timestamp': datetime.utcnow().isoformat(),
            'warehouse_count': warehouse_df['location_id'].nunique(),
            'total_products': len(warehouse_summary),
            'warehouse_details': warehouse_df.to_dict('records'),
            'warehouse_summary': warehouse_summary.to_dict('records'),
            'metrics': {
                'total_capacity_utilized': float(warehouse_df['quantity_on_hand'].sum()),
                'avg_turnover_ratio': float(warehouse_df['stock_turnover_ratio'].mean())
            }
        }
        
        logger.info(f"Synced {result['warehouse_count']} warehouses with "
                   f"{result['total_products']} products")
        
        return result
        
    except Exception as e:
        logger.error(f"Error syncing warehouse data: {str(e)}")
        raise


def sync_store_data(inventory_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sync store inventory data
    
    Args:
        inventory_data: Raw inventory data from feed
        
    Returns:
        Processed store inventory data
    """
    logger.info("Syncing store inventory data...")
    
    try:
        df = pd.DataFrame(inventory_data['data'])
        
        # Filter for store locations
        store_df = df[df['location_type'] == 'store'].copy()
        
        # Calculate store-specific metrics
        store_df['stockout_risk'] = (store_df['quantity_available'] <= 
                                     store_df['quantity_reserved']).astype(int)
        store_df['overstock_flag'] = (store_df['quantity_available'] > 
                                      store_df['quantity_reserved'] * 3).astype(int)
        
        # Aggregate by product across stores
        store_summary = store_df.groupby('product_id').agg({
            'quantity_on_hand': 'sum',
            'quantity_available': 'sum',
            'quantity_reserved': 'sum',
            'stockout_risk': 'sum',
            'overstock_flag': 'sum',
            'location_id': 'count'
        }).reset_index()
        
        store_summary.columns = ['product_id', 'total_on_hand', 'total_available',
                                'total_reserved', 'stores_at_risk', 'stores_overstocked',
                                'store_count']
        
        result = {
            'sync_timestamp': datetime.utcnow().isoformat(),
            'store_count': store_df['location_id'].nunique(),
            'total_products': len(store_summary),
            'store_details': store_df.to_dict('records'),
            'store_summary': store_summary.to_dict('records'),
            'alerts': {
                'stockout_risk_count': int(store_df['stockout_risk'].sum()),
                'overstock_count': int(store_df['overstock_flag'].sum())
            }
        }
        
        logger.info(f"Synced {result['store_count']} stores with "
                   f"{result['total_products']} products")
        logger.warning(f"Found {result['alerts']['stockout_risk_count']} stockout risks "
                      f"and {result['alerts']['overstock_count']} overstock situations")
        
        return result
        
    except Exception as e:
        logger.error(f"Error syncing store data: {str(e)}")
        raise
