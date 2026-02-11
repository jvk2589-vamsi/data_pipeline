# 📦 Inventory Optimization Pipeline

> **Reduce overstock and stockouts through intelligent, real-time inventory management**

## 🎯 Goal

This pipeline automatically optimizes inventory levels across warehouses and stores to:
- Minimize overstock (reducing holding costs)
- Prevent stockouts (avoiding lost sales)
- Maximize inventory turnover
- Reduce procurement costs through intelligent transfers

## 🔄 Pipeline Flow

```
1. Real-time Inventory Feed
   ↓
2. Warehouse + Store Sync (Parallel)
   ↓
3. Safety Stock Calculation
   ↓
4. Reorder Threshold Evaluation
   ↓
5. Transfer Recommendation Engine
   ↓
6. Approval Workflow + Notifications
```

## ✨ Key Features

### 🔄 Real-time Processing
- Runs every 15 minutes for up-to-date inventory insights
- Ingests data from multiple source systems
- Handles thousands of SKUs across multiple locations

### 📊 Intelligent Analytics
- **Safety Stock Calculation**: Uses statistical models (Z-score analysis) to determine optimal safety stock levels
- **Demand Forecasting**: Analyzes 90 days of historical data to predict future demand
- **Reorder Optimization**: Calculates Economic Order Quantity (EOQ) principles

### 🔄 Transfer Recommendations
- Identifies excess inventory at one location that can fulfill shortages at another
- Calculates transfer costs vs. purchase costs
- Only recommends transfers when cost-effective

### ✅ Approval Workflow
- Multi-tier approval system based on transaction value
- Auto-approval for low-value transactions (configurable)
- Executive escalation for high-value orders

### 📧 Stakeholder Notifications
- Automated email notifications to relevant teams
- Critical stock alerts for urgent attention
- Dashboard integration for real-time monitoring

## 🏗️ Architecture

### File Structure

```
inventory-optimization-pipeline/
├── src/
│   ├── main.py                          # Main DAG definition
│   ├── tasks/
│   │   ├── inventory_sync.py            # Data ingestion & sync
│   │   ├── safety_stock_calculator.py   # Safety stock analytics
│   │   ├── reorder_engine.py            # Reorder recommendations
│   │   ├── transfer_recommender.py      # Transfer optimization
│   │   └── approval_workflow.py         # Approval & notifications
│   └── config/
│       └── settings.py                  # Configuration management
├── requirements.txt                     # Python dependencies
├── .env.example                        # Environment variables template
└── README.md                           # This file
```

### Database Schema

**Required Tables:**

- `inventory_current` - Current inventory snapshot
- `products` - Product master data
- `suppliers` - Supplier information
- `locations` - Warehouse and store locations
- `sales_transactions` - Historical sales data
- `approval_queue` - Pending approvals
- `dashboard_alerts` - Critical alerts

## 🚀 Getting Started

### Prerequisites

- Python 3.13+
- Apache Airflow 3.1.0
- PostgreSQL database
- Access to inventory data sources

### Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd inventory-optimization-pipeline
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your actual configuration
   ```

4. **Initialize database**
   ```bash
   # Create required database tables
   # Run your database migration scripts
   ```

5. **Deploy to Airflow**
   ```bash
   # Copy DAG files to Airflow DAGs folder
   cp src/main.py $AIRFLOW_HOME/dags/
   cp -r src/tasks $AIRFLOW_HOME/dags/
   cp -r src/config $AIRFLOW_HOME/dags/
   ```

6. **Start Airflow**
   ```bash
   airflow standalone
   # or
   airflow scheduler &
   airflow webserver
   ```

### Configuration

Key environment variables (see `.env.example` for full list):

| Variable | Description | Default |
|----------|-------------|---------|
| `INVENTORY_DB_URL` | Database connection string | Required |
| `AUTO_APPROVE_THRESHOLD` | Auto-approve orders below this value | $5,000 |
| `MIN_TRANSFER_QUANTITY` | Minimum units for transfer | 10 |
| `DEFAULT_LEAD_TIME_DAYS` | Default supplier lead time | 7 days |
| `PIPELINE_SCHEDULE` | Cron schedule for pipeline | Every 15 min |

## 📊 Metrics & Monitoring

### Pipeline Metrics

The pipeline tracks:
- **Inventory Turnover Ratio**: How quickly inventory is moving
- **Stockout Risk Count**: Number of items at risk of stockout
- **Overstock Count**: Number of items with excess inventory
- **Cost Savings**: Savings from transfers vs. purchases
- **Order Fulfillment Rate**: Percentage of demand met

### Alerts

Automatic alerts for:
- Critical stock levels (< 5 units)
- High-value orders requiring approval
- Failed pipeline runs
- Data quality issues

## 🔧 Customization

### Adjusting Safety Stock Levels

Edit `src/tasks/safety_stock_calculator.py`:

```python
service_levels = {
    'standard': 0.95,   # 95% service level
    'high': 0.99,       # 99% service level
    'critical': 0.995   # 99.5% service level
}
```

### Modifying Approval Tiers

Edit `src/config/settings.py`:

```python
APPROVAL_TIERS = {
    'executive': {'threshold': 100000, 'approvers': [...]},
    'director': {'threshold': 50000, 'approvers': [...]},
    # ... add your tiers
}
```

### Changing Pipeline Schedule

Update the DAG decorator in `src/main.py`:

```python
@dag(
    schedule='*/15 * * * *',  # Change this
    # ... other config
)
```

## 📈 Example Results

**Before Pipeline:**
- 25% of products out of stock weekly
- $500K in excess inventory
- 15% of orders requiring expedited shipping

**After Pipeline:**
- 5% stockout rate (80% reduction)
- $200K in excess inventory (60% reduction)
- 3% expedited shipping (80% reduction)
- $150K annual cost savings from optimized transfers

## 🛠️ Troubleshooting

### Common Issues

**Pipeline not running:**
- Check Airflow scheduler is running: `airflow scheduler status`
- Verify DAG is visible: `airflow dags list`
- Check for syntax errors: `python src/main.py`

**Database connection errors:**
- Verify `INVENTORY_DB_URL` in `.env`
- Test connection: `psql $INVENTORY_DB_URL`
- Check firewall rules and network access

**Missing data:**
- Ensure source tables have recent data
- Check `MIN_HISTORY_DAYS` requirement (default 30 days)
- Verify data quality in sales_transactions table

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📝 License

[Your License Here]

## 📞 Support

For issues and questions:
- Create an issue in GitHub
- Contact: inventory-team@company.com
- Slack: #inventory-optimization

## 🔮 Future Enhancements

- [ ] Machine learning demand forecasting
- [ ] Multi-echelon inventory optimization
- [ ] Seasonal demand patterns
- [ ] Supplier performance tracking
- [ ] Real-time dashboard with visualizations
- [ ] Mobile app for approval workflows
- [ ] Integration with ERP systems (SAP, Oracle, etc.)

---

**Built with ❤️ using Apache Airflow 3.1.0**