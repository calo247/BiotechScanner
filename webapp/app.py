"""Flask web application for BiotechScanner catalyst viewer."""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
import os
import sys

# Add parent directory to path to import src modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.database import get_db
from src.database.models import Drug, Company, StockData, HistoricalCatalyst
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
    search_term = request.args.get('search', '')
    sort_by = request.args.get('sort_by', 'date')
    sort_dir = request.args.get('sort_dir', 'asc')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    with get_db() as db:
        # Base query - drugs with catalysts
        query = db.query(Drug).join(Company).filter(
            Drug.has_catalyst == True,
            Drug.catalyst_date.isnot(None)
        )
        
        # Filter by date - only show future catalysts
        today = datetime.now(timezone.utc).date()
        query = query.filter(
            func.date(Drug.catalyst_date) >= today
        )
        
        # Filter by stage if provided
        if stage_filter:
            query = query.filter(Drug.stage.like(f'%{stage_filter}%'))
        
        # Filter by search term if provided
        if search_term:
            search_pattern = f'%{search_term}%'
            query = query.filter(
                or_(
                    Company.ticker.ilike(search_pattern),
                    Company.name.ilike(search_pattern),
                    Drug.drug_name.ilike(search_pattern),
                    Drug.stage.ilike(search_pattern),
                    Drug.mechanism_of_action.ilike(search_pattern),
                    Drug.note.ilike(search_pattern)
                )
            )
        
        # Apply sorting
        if sort_by == 'date':
            sort_column = Drug.catalyst_date
        elif sort_by == 'ticker':
            sort_column = Company.ticker
        elif sort_by == 'company':
            sort_column = Company.name
        elif sort_by == 'stage':
            sort_column = Drug.stage
        elif sort_by == 'marketcap':
            # Join with latest stock data for market cap sorting
            latest_stock_subq = db.query(
                StockData.company_id,
                func.max(StockData.date).label('max_date')
            ).group_by(StockData.company_id).subquery()
            
            query = query.outerjoin(
                latest_stock_subq,
                Drug.company_id == latest_stock_subq.c.company_id
            ).outerjoin(
                StockData,
                and_(
                    StockData.company_id == latest_stock_subq.c.company_id,
                    StockData.date == latest_stock_subq.c.max_date
                )
            )
            sort_column = StockData.market_cap
        elif sort_by == 'price':
            # Join with latest stock data for price sorting
            latest_stock_subq = db.query(
                StockData.company_id,
                func.max(StockData.date).label('max_date')
            ).group_by(StockData.company_id).subquery()
            
            query = query.outerjoin(
                latest_stock_subq,
                Drug.company_id == latest_stock_subq.c.company_id
            ).outerjoin(
                StockData,
                and_(
                    StockData.company_id == latest_stock_subq.c.company_id,
                    StockData.date == latest_stock_subq.c.max_date
                )
            )
            sort_column = StockData.close
        else:
            sort_column = Drug.catalyst_date
        
        if sort_dir == 'desc':
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        # Get total count
        total = query.count()
        
        # Paginate
        offset = (page - 1) * per_page
        drugs = query.offset(offset).limit(per_page).all()
        
        # Get latest stock data for each company
        company_ids = [drug.company_id for drug in drugs]
        latest_prices = {}
        
        if company_ids:
            # Subquery to get latest date for each company
            subq = db.query(
                StockData.company_id,
                func.max(StockData.date).label('max_date')
            ).filter(
                StockData.company_id.in_(company_ids)
            ).group_by(StockData.company_id).subquery()
            
            # Get the actual stock data for latest dates
            stock_data = db.query(StockData).join(
                subq,
                and_(
                    StockData.company_id == subq.c.company_id,
                    StockData.date == subq.c.max_date
                )
            ).all()
            
            for sd in stock_data:
                latest_prices[sd.company_id] = {
                    'close': sd.close,
                    'market_cap': sd.market_cap,
                    'date': sd.date.isoformat() if sd.date else None
                }
        
        # Format response
        results = []
        for drug in drugs:
            company_price_data = latest_prices.get(drug.company_id, {})
            
            results.append({
                'id': drug.id,
                'drug_name': drug.drug_name,
                'company': {
                    'ticker': drug.company.ticker,
                    'name': drug.company.name,
                    'market_cap': company_price_data.get('market_cap'),
                    'stock_price': company_price_data.get('close'),
                    'price_date': company_price_data.get('date')
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
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
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
        # Base query
        query = db.query(HistoricalCatalyst).join(Company)
        
        # Filter by date range
        if days_back > 0:
            start_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            query = query.filter(HistoricalCatalyst.catalyst_date >= start_date)
        
        # Filter by stage if provided
        if stage_filter:
            query = query.filter(HistoricalCatalyst.stage.like(f'%{stage_filter}%'))
        
        # Filter by ticker if provided
        if ticker_filter:
            query = query.filter(HistoricalCatalyst.ticker == ticker_filter.upper())
        
        # Order by catalyst date descending (most recent first)
        query = query.order_by(HistoricalCatalyst.catalyst_date.desc())
        
        # Get total count
        total = query.count()
        
        # Paginate
        offset = (page - 1) * per_page
        catalysts = query.offset(offset).limit(per_page).all()
        
        # Format response
        results = []
        for catalyst in catalysts:
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
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
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
            }
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