from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, JSON
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
import json

Base = declarative_base()

class TradeRecord(Base):
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    trade_id = Column(String(50), unique=True, index=True)
    symbol = Column(String(20))
    direction = Column(String(10))  # BUY/SELL/CALL/PUT
    stake = Column(Float)
    payout = Column(Float, default=0.0)
    profit = Column(Float, default=0.0)
    open_time = Column(DateTime, default=datetime.utcnow)
    close_time = Column(DateTime, nullable=True)
    status = Column(String(20)) # OPEN, CLOSED, WON, LOST
    metadata_json = Column(JSON, nullable=True)
    
class PerformanceMetrics(Base):
    __tablename__ = 'performance'
    
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, default=datetime.utcnow)
    total_trades = Column(Integer)
    win_rate = Column(Float)
    profit_factor = Column(Float)
    total_profit = Column(Float)

class DatabaseManager:
    def __init__(self, connection_string=None):
        if not connection_string:
            # Default to local SQLite if no DB string provided
            # In production (Docker), this would be Postgres
            db_path = os.path.expanduser("~/bot/data/sentinel.db")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self.connection_string = f"sqlite:///{db_path}"
        else:
            self.connection_string = connection_string
            
        self.engine = create_engine(self.connection_string, echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        print(f"🗄️ Database connected: {self.connection_string}")
    
    def record_trade(self, trade_data: dict):
        """Records a new trade or updates an existing one."""
        session = self.Session()
        try:
            # Check if exists
            existing = session.query(TradeRecord).filter_by(trade_id=trade_data.get('trade_id')).first()
            
            if existing:
                # Update
                for key, value in trade_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
            else:
                # Create
                # Filter keys to match model
                valid_keys = {c.name for c in TradeRecord.__table__.columns}
                filtered_data = {k: v for k, v in trade_data.items() if k in valid_keys}
                
                # Handle metadata separate if needed, or rely on JSON type
                if 'metadata' in trade_data:
                    filtered_data['metadata_json'] = trade_data['metadata']
                    
                trade = TradeRecord(**filtered_data)
                session.add(trade)
                
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"❌ DB Error: {e}")
            return False
        finally:
            session.close()

    def get_performance_summary(self):
        """Calculates basic performance stats from DB."""
        session = self.Session()
        try:
            trades = session.query(TradeRecord).filter(TradeRecord.status.in_(['WON', 'LOST', 'CLOSED'])).all()
            if not trades:
                return {"total_trades": 0, "profit": 0.0}
            
            total_profit = sum(t.profit for t in trades)
            wins = sum(1 for t in trades if t.profit > 0)
            losses = sum(1 for t in trades if t.profit <= 0) # Assuming 0 is bad or breakeven
            win_rate = (wins / len(trades)) * 100 if trades else 0.0
            
            return {
                "total_trades": len(trades),
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 2),
                "total_profit": round(total_profit, 2)
            }
        finally:
            session.close()

if __name__ == "__main__":
    # Test
    db = DatabaseManager()
    db.record_trade({
        "trade_id": "test_1", 
        "symbol": "EURUSD", 
        "direction": "CALL", 
        "stake": 10.0, 
        "status": "OPEN"
    })
    print("Record added.")
    stats = db.get_performance_summary()
    print(f"Stats: {stats}")
