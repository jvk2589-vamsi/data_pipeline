"""
Transfer Recommendation Engine
Generates optimal inventory transfer recommendations between locations
"""

import logging
from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np
from datetime import datetime
from sqlalchemy import create_engine
import os

logger = logging.getLogger(__name__)


def calculate_transfer_cost(from_location: str, to_location: str, quantity: int) -> float:
    """
    Calculate the cost of transferring inventory between locations
    
    Args:
        from_location: Source location ID
        to_location: Destination location ID
        quantity: Number of units to transfer
        
    Returns:
        Estimated transfer cost
    """
    # Simplified cost calculation - in reality, this would consider:
    # - Distance between locations
    # - Transportation mode
    # - Handling costs
    # - Urgency/priority
    base_cost_per_unit = 2.50
    distance_factor = 1.0  # Would calculate based on actual locations
    
    return quantity * base_cost_per_unit * distance_factor


def generate_transfer_recommendations(reorder_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate optimal transfer recommendations between locations to balance inventory
    
    Before placing purchase orders, checks if excess inventory exists at other
    locations that can be transferred to fulfill shortages.
    
    Args:
        reorder_data: Reorder recommendations from previous task
        
    Returns:
        Transfer recommendations to optimize inventory distribution
    """
    logger.info("Generating transfer recommendations...")
    
    try:
        # Get current inventory by location
        db_url = os.getenv('INVENTORY_DB_URL', 'postgresql://user:pass@localhost/inventory')
        engine = create_engine(db_url)
        
        location_query = """
            SELECT 
                i.product_id,
                i.location_id,
                l.location_name,
                l.location_type,
                l.region,
                i.quantity_available,
                i.quantity_reserved,
                i.quantity_available - i.quantity_reserved as transferrable_qty
            FROM inventory_current i
            JOIN locations l ON i.location_id = l.location_id
            WHERE i.is_active = true
            AND i.quantity_available > 0
        """
        
        location_df = pd.read_sql(location_query, engine)
        
        # Get items needing reorder
        reorder_df = pd.DataFrame(reorder_data['reorder_recommendations'])
        
        if len(reorder_df) == 0:
            logger.info("No reorder items to evaluate for transfers")
            return {
                'recommendation_timestamp': datetime.utcnow().isoformat(),
                'transfer_recommendations': [],
                'purchase_order_recommendations': [],
                'summary': {
                    'transfers_recommended': 0,
                    'purchase_orders_recommended': 0,
                    'units_via_transfer': 0,
                    'units_via_purchase': 0,
                    'cost_savings_from_transfers': 0.0
                }
            }
        
        # Find transfer opportunities
        transfer_recommendations = []
        updated_purchase_orders = []
        
        for _, reorder_row in reorder_df.iterrows():
            product_id = reorder_row['product_id']
            needed_qty = reorder_row['recommended_order_qty']
            shortage_qty = reorder_row['shortage_qty']
            
            # Find locations with excess inventory of this product
            product_locations = location_df[
                (location_df['product_id'] == product_id) &
                (location_df['transferrable_qty'] > 0)
            ].copy()
            
            if len(product_locations) == 0:
                # No alternative sources - keep original purchase order
                updated_purchase_orders.append(reorder_row)
                continue
            
            # Calculate excess inventory at each location
            # Excess = available qty above 1.5x of safety stock (simplified)
            avg_demand = reorder_row['avg_daily_demand']
            target_stock_per_location = avg_demand * 14  # 2 weeks of demand
            
            product_locations['excess_qty'] = (
                product_locations['transferrable_qty'] - target_stock_per_location
            ).clip(lower=0)
            
            # Sort by excess quantity (descending)
            product_locations = product_locations.sort_values('excess_qty', ascending=False)
            
            # Try to fulfill shortage through transfers
            remaining_shortage = shortage_qty
            
            for _, location_row in product_locations.iterrows():
                if remaining_shortage <= 0:
                    break
                
                available_for_transfer = min(
                    location_row['excess_qty'],
                    remaining_shortage
                )
                
                if available_for_transfer >= 10:  # Minimum transfer quantity threshold
                    transfer_cost = calculate_transfer_cost(
                        location_row['location_id'],
                        'warehouse_central',  # Simplified - would be product-specific
                        int(available_for_transfer)
                    )
                    
                    purchase_cost_avoided = available_for_transfer * reorder_row['unit_cost']
                    cost_savings = purchase_cost_avoided - transfer_cost
                    
                    # Only recommend transfer if it saves money
                    if cost_savings > 0:
                        transfer_recommendations.append({
                            'product_id': product_id,
                            'from_location_id': location_row['location_id'],
                            'from_location_name': location_row['location_name'],
                            'to_location_id': 'warehouse_central',
                            'to_location_name': 'Central Warehouse',
                            'transfer_quantity': int(available_for_transfer),
                            'transfer_cost': float(transfer_cost),
                            'purchase_cost_avoided': float(purchase_cost_avoided),
                            'cost_savings': float(cost_savings),
                            'priority': reorder_row['priority_label'],
                            'reason': 'Excess inventory available at source location',
                            'estimated_transfer_days': 2
                        })
                        
                        remaining_shortage -= available_for_transfer
            
            # If shortage still remains after transfers, create reduced purchase order
            if remaining_shortage > 0:
                updated_po = reorder_row.copy()
                updated_po['recommended_order_qty'] = int(remaining_shortage)
                updated_po['total_order_value'] = remaining_shortage * reorder_row['unit_cost']
                updated_po['notes'] = f"Reduced by {int(shortage_qty - remaining_shortage)} units due to transfers"
                updated_purchase_orders.append(updated_po)
            else:
                logger.info(f"Product {product_id}: Fully satisfied through transfers, no purchase order needed")
        
        # Calculate summary metrics
        total_transferred_units = sum(t['transfer_quantity'] for t in transfer_recommendations)
        total_transfer_cost = sum(t['transfer_cost'] for t in transfer_recommendations)
        total_cost_savings = sum(t['cost_savings'] for t in transfer_recommendations)
        
        total_purchase_units = sum(po['recommended_order_qty'] for po in updated_purchase_orders)
        total_purchase_value = sum(po['total_order_value'] for po in updated_purchase_orders)
        
        result = {
            'recommendation_timestamp': datetime.utcnow().isoformat(),
            'transfer_recommendations': transfer_recommendations,
            'purchase_order_recommendations': updated_purchase_orders,
            'summary': {
                'transfers_recommended': len(transfer_recommendations),
                'purchase_orders_recommended': len(updated_purchase_orders),
                'units_via_transfer': int(total_transferred_units),
                'units_via_purchase': int(total_purchase_units),
                'transfer_cost': float(total_transfer_cost),
                'purchase_order_value': float(total_purchase_value),
                'cost_savings_from_transfers': float(total_cost_savings),
                'original_po_count': len(reorder_df),
                'original_po_value': float(reorder_data['summary']['total_order_value'])
            }
        }
        
        logger.info(f"Generated {len(transfer_recommendations)} transfer recommendations")
        logger.info(f"Reduced to {len(updated_purchase_orders)} purchase orders")
        logger.info(f"Cost savings from transfers: ${total_cost_savings:,.2f}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error generating transfer recommendations: {str(e)}")
        raise
