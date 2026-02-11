"""
Inventory Optimization Pipeline
Reduces overstock and stockouts through intelligent inventory management
"""

from datetime import datetime, timedelta
from airflow.sdk import dag, task, DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator

# Import task modules
from tasks.inventory_sync import (
    fetch_realtime_inventory,
    sync_warehouse_data,
    sync_store_data
)
from tasks.safety_stock_calculator import calculate_safety_stock
from tasks.reorder_engine import evaluate_reorder_thresholds
from tasks.transfer_recommender import generate_transfer_recommendations
from tasks.approval_workflow import submit_for_approval, notify_stakeholders


default_args = {
    'owner': 'inventory_team',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(minutes=30),
}


@dag(
    dag_id='inventory_optimization_pipeline',
    default_args=default_args,
    description='Real-time inventory optimization to reduce overstock and stockouts',
    schedule='*/15 * * * *',  # Run every 15 minutes for real-time processing
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['inventory', 'optimization', 'warehouse', 'retail'],
    max_active_runs=1,  # Prevent overlapping runs
)
def inventory_optimization_pipeline():
    """
    Inventory Optimization Pipeline DAG
    
    Flow:
    1. Real-time inventory feed ingestion
    2. Warehouse + store sync
    3. Safety stock calculation
    4. Reorder threshold evaluation
    5. Transfer recommendation engine
    6. Approval workflow
    """
    
    # Start marker
    start = EmptyOperator(task_id='start')
    
    # Task 1: Fetch real-time inventory feed
    @task(task_id='fetch_inventory_feed', retries=5)
    def fetch_inventory():
        """Fetch real-time inventory data from source systems"""
        return fetch_realtime_inventory()
    
    # Task 2a & 2b: Parallel warehouse and store sync
    @task(task_id='sync_warehouses')
    def sync_warehouses(inventory_data):
        """Sync warehouse inventory data"""
        return sync_warehouse_data(inventory_data)
    
    @task(task_id='sync_stores')
    def sync_stores(inventory_data):
        """Sync store inventory data"""
        return sync_store_data(inventory_data)
    
    # Task 3: Calculate safety stock levels
    @task(task_id='calculate_safety_stock_levels')
    def calc_safety_stock(warehouse_data, store_data):
        """Calculate safety stock based on demand variability"""
        return calculate_safety_stock(warehouse_data, store_data)
    
    # Task 4: Evaluate reorder thresholds
    @task(task_id='evaluate_reorder_thresholds')
    def evaluate_reorders(safety_stock_data):
        """Evaluate which items need reordering"""
        return evaluate_reorder_thresholds(safety_stock_data)
    
    # Task 5: Generate transfer recommendations
    @task(task_id='generate_transfer_recommendations')
    def generate_transfers(reorder_data):
        """Generate optimal transfer recommendations between locations"""
        return generate_transfer_recommendations(reorder_data)
    
    # Task 6a: Submit for approval
    @task(task_id='submit_for_approval')
    def submit_approval(transfer_recommendations):
        """Submit recommendations to approval workflow"""
        return submit_for_approval(transfer_recommendations)
    
    # Task 6b: Notify stakeholders
    @task(task_id='notify_stakeholders')
    def notify(approval_data):
        """Notify relevant stakeholders of recommendations"""
        return notify_stakeholders(approval_data)
    
    # End marker
    end = EmptyOperator(task_id='end')
    
    # Define task dependencies
    inventory = fetch_inventory()
    
    # Parallel sync operations
    warehouses = sync_warehouses(inventory)
    stores = sync_stores(inventory)
    
    # Sequential processing
    safety_stock = calc_safety_stock(warehouses, stores)
    reorders = evaluate_reorders(safety_stock)
    transfers = generate_transfers(reorders)
    approval = submit_approval(transfers)
    notifications = notify(approval)
    
    # Set up the flow
    start >> inventory
    notifications >> end


# Instantiate the DAG
inventory_dag = inventory_optimization_pipeline()
