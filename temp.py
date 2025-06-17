from src.database.database import engine
from src.database.models import HistoricalCatalyst

# Drop the old table
HistoricalCatalyst.__table__.drop(engine)

# Create the new table without the unique constraint
HistoricalCatalyst.__table__.create(engine)