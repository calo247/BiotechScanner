"""Flask web application for BiotechScanner catalyst viewer."""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
import os
import sys

# Add parent directory to path to import src modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.database import get_db
from src.database.models import Drug, Company, StockData, HistoricalCatalyst, CatalystReport
from src.queries import CatalystQuery, CompanyQuery
from src.queries.catalyst_queries import HistoricalCatalystQuery
from sqlalchemy import and_, or_, func

app = Flask(__name__)
CORS(app)  # Enable CORS for API access

@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')

@app.route('/catalyst/<int:catalyst_id>')
def catalyst_detail(catalyst_id):
    """Serve the catalyst detail page."""
    return render_template('catalyst_detail.html')

@app.route('/api/catalysts/upcoming', methods=['GET'])
def get_upcoming_catalysts():
    """Get upcoming catalyst events."""
    # Get query parameters
    stage_filter = request.args.get('stage', '')
    days_filter = request.args.get('days', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    search_term = request.args.get('search', '')
    sort_by = request.args.get('sort_by', 'date')
    sort_dir = request.args.get('sort_dir', 'asc')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    # Get market cap range parameters
    min_marketcap = request.args.get('min_marketcap', type=float)
    max_marketcap = request.args.get('max_marketcap', type=float)
    
    # Get stock price range parameters
    min_stockprice = request.args.get('min_stockprice', type=float)
    max_stockprice = request.args.get('max_stockprice', type=float)
    
    with get_db() as db:
        # Build query using the new CatalystQuery builder
        query = CatalystQuery(db).with_stock_data()
        
        # Apply time range filter
        if start_date or end_date:
            # Custom date range
            from datetime import datetime
            start_dt = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None
            # Add one day to end_date to include the entire end day
            if end_dt:
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
            query = query.date_range(start_dt, end_dt)
        elif days_filter:
            query = query.upcoming(days=int(days_filter))
        else:
            query = query.upcoming()  # All future catalysts
        
        # Apply stage filter
        if stage_filter:
            query = query.by_stage(stage_filter)
        
        # Apply market cap range filter
        if min_marketcap is not None or max_marketcap is not None:
            query = query.by_market_cap_range(min_marketcap, max_marketcap)
        
        # Apply stock price range filter
        if min_stockprice is not None or max_stockprice is not None:
            query = query.by_stock_price_range(min_stockprice, max_stockprice)
        
        # Apply search filter
        if search_term:
            query = query.search(search_term)
        
        # Apply sorting
        query = query.order_by(sort_by, sort_dir)
        
        # Get paginated results
        result = query.paginate(page=page, per_page=per_page)
        
        # Format response
        results = []
        for drug in result['results']:
            company_stock = result['stock_data'].get(drug.company_id, {})
            
            results.append({
                'id': drug.id,
                'drug_name': drug.drug_name,
                'company': {
                    'ticker': drug.company.ticker,
                    'name': drug.company.name,
                    'market_cap': company_stock.get('market_cap'),
                    'stock_price': company_stock.get('close'),
                    'price_date': company_stock.get('date')
                },
                'stage': drug.stage,
                'catalyst_date': drug.catalyst_date.isoformat() if drug.catalyst_date else None,
                'catalyst_date_text': drug.catalyst_date_text,
                'indications': drug.indications or [],
                'mechanism_of_action': drug.mechanism_of_action,
                'note': drug.note,
                'market_info': drug.market_info
            })
        
        return jsonify({
            'results': results,
            'total': result['pagination']['total'],
            'page': result['pagination']['page'],
            'per_page': result['pagination']['per_page'],
            'total_pages': result['pagination']['total_pages']
        })

@app.route('/api/catalysts/historical', methods=['GET'])
def get_historical_catalysts():
    """Get historical catalyst events."""
    # Get query parameters
    days_back = int(request.args.get('days', 90))
    stage_filter = request.args.get('stage', '')
    ticker_filter = request.args.get('ticker', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    with get_db() as db:
        # Build query using the new HistoricalCatalystQuery builder
        query = HistoricalCatalystQuery(db)
        
        # Apply filters
        if days_back > 0:
            query = query.past_days(days_back)
        
        if stage_filter:
            query = query.by_stage(stage_filter)
        
        if ticker_filter:
            query = query.by_ticker(ticker_filter)
        
        # Order by date descending (most recent first)
        query = query.order_by_date(ascending=False)
        
        # Get paginated results
        result = query.paginate(page=page, per_page=per_page)
        
        # Format response
        results = []
        for catalyst in result['results']:
            results.append({
                'id': catalyst.id,
                'ticker': catalyst.ticker,
                'company_name': catalyst.company.name,
                'drug_name': catalyst.drug_name,
                'drug_indication': catalyst.drug_indication,
                'stage': catalyst.stage,
                'catalyst_date': catalyst.catalyst_date.isoformat() if catalyst.catalyst_date else None,
                'catalyst_text': catalyst.catalyst_text,
                'catalyst_source': catalyst.catalyst_source
            })
        
        return jsonify({
            'results': results,
            'total': result['total'],
            'page': result['page'],
            'per_page': result['per_page'],
            'total_pages': result['total_pages']
        })

@app.route('/api/catalysts/<int:catalyst_id>', methods=['GET'])
def get_catalyst_detail(catalyst_id):
    """Get detailed information for a specific catalyst."""
    with get_db() as db:
        # Get the drug with catalyst details
        drug = db.query(Drug).join(Company).filter(
            Drug.id == catalyst_id,
            Drug.has_catalyst == True
        ).first()
        
        if not drug:
            return jsonify({'error': 'Catalyst not found'}), 404
        
        # Get latest stock data
        latest_stock = db.query(StockData).filter(
            StockData.company_id == drug.company_id
        ).order_by(StockData.date.desc()).first()
        
        # Get recent stock data (last 30 days)
        recent_stock_data = []
        if latest_stock:
            recent_data = db.query(StockData).filter(
                StockData.company_id == drug.company_id,
                StockData.date >= (latest_stock.date - timedelta(days=30))
            ).order_by(StockData.date.asc()).all()
            
            recent_stock_data = [{
                'date': sd.date.isoformat(),
                'close': sd.close,
                'volume': sd.volume,
                'market_cap': sd.market_cap
            } for sd in recent_data]
        
        # Get the most recent cash balance using the query module
        cash_data = CompanyQuery(db).get_latest_cash_balance(drug.company_id)
        
        if cash_data:
            cash_balance = cash_data['value']
            cash_balance_date = cash_data['date']
            cash_balance_period = cash_data['period']
        else:
            cash_balance = None
            cash_balance_date = None
            cash_balance_period = None
        
        # Get the most recent AI analysis report for this catalyst
        latest_report = db.query(CatalystReport).filter(
            CatalystReport.drug_id == drug.id
        ).order_by(CatalystReport.created_at.desc()).first()
        
        # Format AI report for response
        formatted_report = None
        if latest_report:
            formatted_report = {
                'id': latest_report.id,
                'created_at': latest_report.created_at.isoformat() if latest_report.created_at else None,
                'report_type': latest_report.report_type,
                'model_used': latest_report.model_used,
                'report_markdown': latest_report.report_markdown,
                'report_summary': latest_report.report_summary,
                'success_probability': latest_report.success_probability,
                'recommendation': latest_report.recommendation,
                'price_target_upside': latest_report.price_target_upside,
                'price_target_downside': latest_report.price_target_downside,
                'risk_level': latest_report.risk_level,
                'generation_time_ms': latest_report.generation_time_ms
            }
        
        # Format response with comprehensive details
        result = {
            'id': drug.id,
            'drug_name': drug.drug_name,
            'mechanism_of_action': drug.mechanism_of_action,
            'stage': drug.stage,
            'stage_event_label': drug.stage_event_label,
            'catalyst_date': drug.catalyst_date.isoformat() if drug.catalyst_date else None,
            'catalyst_date_text': drug.catalyst_date_text,
            'indications': drug.indications or [],
            'indications_text': drug.indications_text,
            'note': drug.note,
            'market_info': drug.market_info,
            'catalyst_source': drug.catalyst_source,
            'last_update_name': drug.last_update_name,
            'api_last_updated': drug.api_last_updated.isoformat() if drug.api_last_updated else None,
            'company': {
                'id': drug.company.id,
                'ticker': drug.company.ticker,
                'name': drug.company.name,
                'biopharma_id': drug.company.biopharma_id
            },
            'stock_data': {
                'current': {
                    'price': latest_stock.close if latest_stock else None,
                    'volume': latest_stock.volume if latest_stock else None,
                    'market_cap': latest_stock.market_cap if latest_stock else None,
                    'date': latest_stock.date.isoformat() if latest_stock else None,
                    'pe_ratio': latest_stock.pe_ratio if latest_stock else None,
                    'week_52_high': latest_stock.week_52_high if latest_stock else None,
                    'week_52_low': latest_stock.week_52_low if latest_stock else None
                },
                'recent_history': recent_stock_data
            },
            'financial_data': {
                'cash_balance': cash_balance,
                'cash_balance_date': cash_balance_date,
                'cash_balance_period': cash_balance_period
            },
            'ai_report': formatted_report
        }
        
        return jsonify(result)

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get database statistics."""
    with get_db() as db:
        # Get counts
        total_drugs = db.query(Drug).count()
        drugs_with_catalysts = db.query(Drug).filter(Drug.has_catalyst == True).count()
        total_companies = db.query(Company).count()
        
        # Get upcoming catalysts count (next 90 days)
        today = datetime.now(timezone.utc).date()
        end_date = today + timedelta(days=90)
        upcoming_catalysts = db.query(Drug).filter(
            Drug.has_catalyst == True,
            Drug.catalyst_date.isnot(None),
            func.date(Drug.catalyst_date) >= today,
            func.date(Drug.catalyst_date) <= end_date
        ).count()
        
        # Stage distribution for upcoming catalysts
        stage_dist = db.query(
            Drug.stage,
            func.count(Drug.id).label('count')
        ).filter(
            Drug.has_catalyst == True,
            Drug.catalyst_date.isnot(None),
            func.date(Drug.catalyst_date) >= today,
            func.date(Drug.catalyst_date) <= end_date
        ).group_by(Drug.stage).all()
        
        return jsonify({
            'total_drugs': total_drugs,
            'drugs_with_catalysts': drugs_with_catalysts,
            'total_companies': total_companies,
            'upcoming_catalysts_90d': upcoming_catalysts,
            'stage_distribution': [
                {'stage': stage, 'count': count} 
                for stage, count in stage_dist
            ]
        })

if __name__ == '__main__':
    app.run(debug=True, port=5678)