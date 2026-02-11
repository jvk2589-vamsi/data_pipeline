"""
Approval Workflow
Handles submission and notification for inventory recommendations
"""

import logging
from typing import Dict, Any, List
import pandas as pd
import json
from datetime import datetime
from sqlalchemy import create_engine
import os

logger = logging.getLogger(__name__)


def submit_for_approval(transfer_recommendations: Dict[str, Any]) -> Dict[str, Any]:
    """
    Submit transfer and purchase order recommendations for approval
    
    Args:
        transfer_recommendations: Transfer and PO recommendations from previous task
        
    Returns:
        Approval submission status and tracking information
    """
    logger.info("Submitting recommendations for approval...")
    
    try:
        db_url = os.getenv('INVENTORY_DB_URL', 'postgresql://user:pass@localhost/inventory')
        engine = create_engine(db_url)
        
        submission_id = f"APPROVAL_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Determine approval requirements based on total value
        total_transfer_cost = transfer_recommendations['summary']['transfer_cost']
        total_po_value = transfer_recommendations['summary']['purchase_order_value']
        total_value = total_transfer_cost + total_po_value
        
        # Define approval tiers
        if total_value > 100000:
            approval_level = 'executive'
            approvers = ['vp_operations', 'cfo', 'ceo']
        elif total_value > 50000:
            approval_level = 'director'
            approvers = ['director_supply_chain', 'director_finance']
        elif total_value > 10000:
            approval_level = 'manager'
            approvers = ['inventory_manager', 'procurement_manager']
        else:
            approval_level = 'supervisor'
            approvers = ['inventory_supervisor']
        
        # Create approval records
        approval_records = []
        
        # Transfer approvals
        for transfer in transfer_recommendations['transfer_recommendations']:
            record = {
                'submission_id': submission_id,
                'approval_type': 'transfer',
                'product_id': transfer['product_id'],
                'from_location': transfer['from_location_id'],
                'to_location': transfer['to_location_id'],
                'quantity': transfer['transfer_quantity'],
                'estimated_cost': transfer['transfer_cost'],
                'priority': transfer['priority'],
                'approval_level': approval_level,
                'status': 'pending',
                'submitted_at': datetime.utcnow().isoformat(),
                'metadata': json.dumps({
                    'cost_savings': transfer['cost_savings'],
                    'reason': transfer['reason'],
                    'estimated_days': transfer['estimated_transfer_days']
                })
            }
            approval_records.append(record)
        
        # Purchase order approvals
        for po in transfer_recommendations['purchase_order_recommendations']:
            record = {
                'submission_id': submission_id,
                'approval_type': 'purchase_order',
                'product_id': po['product_id'],
                'supplier_id': po['supplier_id'],
                'quantity': po['recommended_order_qty'],
                'estimated_cost': po['total_order_value'],
                'priority': po['priority_label'],
                'approval_level': approval_level,
                'status': 'pending',
                'submitted_at': datetime.utcnow().isoformat(),
                'metadata': json.dumps({
                    'supplier_name': po['supplier_name'],
                    'lead_time_days': po['lead_time_days'],
                    'expected_delivery': po['expected_delivery_date'],
                    'current_stock': po['current_stock'],
                    'reorder_point': po['reorder_point']
                })
            }
            approval_records.append(record)
        
        # Insert approval records into database
        if approval_records:
            approval_df = pd.DataFrame(approval_records)
            approval_df.to_sql(
                'approval_queue',
                engine,
                if_exists='append',
                index=False
            )
            
            logger.info(f"Inserted {len(approval_records)} records into approval queue")
        
        # Auto-approve low-value items if configured
        auto_approve_threshold = float(os.getenv('AUTO_APPROVE_THRESHOLD', '5000'))
        auto_approved_count = 0
        
        if total_value <= auto_approve_threshold:
            # Update records to auto-approved status
            with engine.connect() as conn:
                conn.execute(
                    """
                    UPDATE approval_queue
                    SET status = 'auto_approved',
                        approved_at = NOW(),
                        approved_by = 'system'
                    WHERE submission_id = %s
                    """,
                    (submission_id,)
                )
                conn.commit()
            
            auto_approved_count = len(approval_records)
            logger.info(f"Auto-approved {auto_approved_count} items (total value: ${total_value:,.2f})")
        
        result = {
            'submission_id': submission_id,
            'submission_timestamp': datetime.utcnow().isoformat(),
            'approval_level': approval_level,
            'approvers': approvers,
            'total_items': len(approval_records),
            'transfer_items': len(transfer_recommendations['transfer_recommendations']),
            'purchase_order_items': len(transfer_recommendations['purchase_order_recommendations']),
            'total_value': float(total_value),
            'status': 'auto_approved' if auto_approved_count > 0 else 'pending_approval',
            'auto_approved': auto_approved_count > 0,
            'approval_records': approval_records,
            'recommendations_summary': transfer_recommendations['summary']
        }
        
        logger.info(f"Submission {submission_id} created with status: {result['status']}")
        logger.info(f"Total value: ${total_value:,.2f}, Approval level: {approval_level}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error submitting for approval: {str(e)}")
        raise


def notify_stakeholders(approval_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Notify relevant stakeholders about inventory recommendations
    
    Args:
        approval_data: Approval submission data
        
    Returns:
        Notification status
    """
    logger.info("Notifying stakeholders...")
    
    try:
        notifications_sent = []
        
        # Prepare notification content
        submission_id = approval_data['submission_id']
        total_value = approval_data['total_value']
        status = approval_data['status']
        
        # Determine notification recipients
        recipients = []
        
        # Always notify inventory team
        recipients.append({
            'role': 'inventory_team',
            'emails': os.getenv('INVENTORY_TEAM_EMAILS', 'inventory@company.com').split(','),
            'notification_type': 'summary'
        })
        
        # Notify approvers if pending approval
        if status == 'pending_approval':
            for approver in approval_data['approvers']:
                recipients.append({
                    'role': approver,
                    'emails': [f"{approver}@company.com"],
                    'notification_type': 'approval_required'
                })
        
        # Notify critical items to executives
        critical_count = sum(
            1 for r in approval_data['approval_records'] 
            if r.get('priority') == 'CRITICAL'
        )
        
        if critical_count > 0:
            recipients.append({
                'role': 'executives',
                'emails': os.getenv('EXECUTIVE_EMAILS', 'executives@company.com').split(','),
                'notification_type': 'critical_alert'
            })
        
        # Send notifications
        for recipient in recipients:
            notification = {
                'notification_id': f"{submission_id}_{recipient['role']}",
                'recipient_role': recipient['role'],
                'recipient_emails': recipient['emails'],
                'notification_type': recipient['notification_type'],
                'subject': generate_notification_subject(recipient['notification_type'], approval_data),
                'body': generate_notification_body(recipient['notification_type'], approval_data),
                'sent_at': datetime.utcnow().isoformat(),
                'status': 'sent'
            }
            
            # In production, integrate with email service (SendGrid, SES, etc.)
            # For now, just log the notification
            logger.info(f"Notification sent to {recipient['role']}: {notification['subject']}")
            
            notifications_sent.append(notification)
        
        # Create dashboard alert for critical items
        if critical_count > 0:
            create_dashboard_alert(approval_data)
        
        result = {
            'notification_timestamp': datetime.utcnow().isoformat(),
            'submission_id': submission_id,
            'notifications_sent': len(notifications_sent),
            'notification_details': notifications_sent,
            'summary': {
                'total_recipients': len(recipients),
                'approval_notifications': sum(
                    1 for n in notifications_sent 
                    if n['notification_type'] == 'approval_required'
                ),
                'alert_notifications': sum(
                    1 for n in notifications_sent 
                    if n['notification_type'] == 'critical_alert'
                ),
                'summary_notifications': sum(
                    1 for n in notifications_sent 
                    if n['notification_type'] == 'summary'
                )
            }
        }
        
        logger.info(f"Sent {len(notifications_sent)} notifications for submission {submission_id}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error notifying stakeholders: {str(e)}")
        raise


def generate_notification_subject(notification_type: str, approval_data: Dict[str, Any]) -> str:
    """Generate email subject based on notification type"""
    submission_id = approval_data['submission_id']
    
    if notification_type == 'approval_required':
        return f"ACTION REQUIRED: Inventory Approval Request {submission_id}"
    elif notification_type == 'critical_alert':
        return f"URGENT: Critical Inventory Items Require Attention - {submission_id}"
    else:
        return f"Inventory Optimization Summary - {submission_id}"


def generate_notification_body(notification_type: str, approval_data: Dict[str, Any]) -> str:
    """Generate email body based on notification type"""
    summary = approval_data['recommendations_summary']
    
    body = f"""
Inventory Optimization Pipeline Results
Submission ID: {approval_data['submission_id']}
Status: {approval_data['status']}
Total Value: ${approval_data['total_value']:,.2f}

SUMMARY:
- Transfer Recommendations: {summary['transfers_recommended']}
- Purchase Orders: {summary['purchase_orders_recommended']}
- Units via Transfer: {summary['units_via_transfer']}
- Units via Purchase: {summary['units_via_purchase']}
- Cost Savings from Transfers: ${summary['cost_savings_from_transfers']:,.2f}

"""
    
    if notification_type == 'approval_required':
        body += f"""
ACTION REQUIRED:
Please review and approve the recommendations in the approval dashboard.
Approval Level: {approval_data['approval_level']}

"""
    
    if notification_type == 'critical_alert':
        critical_items = [
            r for r in approval_data['approval_records']
            if r.get('priority') == 'CRITICAL'
        ]
        body += f"""
CRITICAL ALERT:
{len(critical_items)} items are at critical stock levels and require immediate attention.

"""
    
    body += """
For detailed information, please log in to the Inventory Management Dashboard.
    """
    
    return body.strip()


def create_dashboard_alert(approval_data: Dict[str, Any]) -> None:
    """Create alert in monitoring dashboard for critical items"""
    try:
        db_url = os.getenv('INVENTORY_DB_URL', 'postgresql://user:pass@localhost/inventory')
        engine = create_engine(db_url)
        
        alert = {
            'alert_id': f"ALERT_{approval_data['submission_id']}",
            'alert_type': 'critical_inventory',
            'severity': 'high',
            'message': f"Critical inventory items in submission {approval_data['submission_id']}",
            'created_at': datetime.utcnow(),
            'status': 'active',
            'metadata': json.dumps(approval_data['recommendations_summary'])
        }
        
        alert_df = pd.DataFrame([alert])
        alert_df.to_sql('dashboard_alerts', engine, if_exists='append', index=False)
        
        logger.info(f"Dashboard alert created: {alert['alert_id']}")
        
    except Exception as e:
        logger.warning(f"Failed to create dashboard alert: {str(e)}")