import logging
from flask import request
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required

from app.extensions import get_db, limiter
from app.api.helpers import get_current_user_id

logger = logging.getLogger(__name__)

investments_ns = Namespace("investments", description="Investments and Portfolio management")

@investments_ns.route("/portfolio")
class PortfolioDetails(Resource):
    @jwt_required()
    @limiter.limit("30 per minute")
    def get(self):
        """Get user portfolio."""
        uid = get_current_user_id()
        db = get_db()
        try:
            with db.get_connection() as conn:
                rows = conn.execute(
                    "SELECT id, symbol, name, shares, avg_price, current_price FROM investments WHERE user_id = ?",
                    (uid,)
                ).fetchall()
                
                if not rows:
                    return {"total_value": 0, "day_change": 0, "day_change_percent": 0, "holdings": []}, 200
            
            total_value = 0
            day_change_abs = 0
            mapped_holdings = []
            
            for row in rows:
                c_price = row["current_price"]
                s = row["shares"]
                val = c_price * s
                # Mock a daily change value
                d_change_pct = ((c_price - row["avg_price"]) / row["avg_price"]) * 100 if row["avg_price"] > 0 else 0
                d_change_pct = round(d_change_pct, 1)
                d_change_abs = val * (d_change_pct / 100)
                
                total_value += val
                day_change_abs += d_change_abs
                
                mapped_holdings.append({
                    "symbol": row["symbol"],
                    "name": row["name"],
                    "shares": s,
                    "price": c_price,
                    "change": d_change_pct
                })
                
            day_change_percent = (day_change_abs / (total_value - day_change_abs)) * 100 if (total_value - day_change_abs) > 0 else 0

            return {
                "total_value": round(total_value, 2),
                "day_change": round(day_change_abs, 2),
                "day_change_percent": round(day_change_percent, 2),
                "holdings": mapped_holdings
            }, 200
        except Exception as e:
            logger.error("Failed to fetch investments: %s", e)
            return {"total_value": 0, "day_change": 0, "day_change_percent": 0, "holdings": []}, 200

@investments_ns.route("/trade")
class PortfolioTrade(Resource):
    @jwt_required()
    def post(self):
        """Simulate a buy/sell trade."""
        import uuid
        uid = get_current_user_id()
        payload = request.get_json() or {}
        symbol = payload.get("symbol", "UNKNOWN").upper()
        action = payload.get("action", "buy").lower()
        shares = int(payload.get("shares", 1))
        price = float(payload.get("price", 100.0))
        
        db = get_db()
        try:
            with db.get_connection() as conn:
                existing = conn.execute(
                    "SELECT id, shares, avg_price FROM investments WHERE user_id = %s AND symbol = %s",
                    (uid, symbol)
                ).fetchone()
                
                if action == "buy":
                    if existing:
                        new_shares = existing["shares"] + shares
                        new_avg = ((existing["shares"] * existing["avg_price"]) + (shares * price)) / new_shares
                        conn.execute(
                            "UPDATE investments SET shares = %s, avg_price = %s, current_price = %s WHERE id = %s",
                            (new_shares, new_avg, price, existing["id"])
                        )
                    else:
                        inv_id = f"inv_{str(uuid.uuid4())[:8]}"
                        conn.execute(
                            "INSERT INTO investments (id, user_id, symbol, name, shares, avg_price, current_price) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            (inv_id, uid, symbol, symbol, shares, price, price)
                        )
                elif action == "sell":
                    if not existing or existing["shares"] < shares:
                        return {"error": "Insufficient shares"}, 400
                    
                    new_shares = existing["shares"] - shares
                    if new_shares == 0:
                        conn.execute("DELETE FROM investments WHERE id = %s", (existing["id"],))
                    else:
                        conn.execute(
                            "UPDATE investments SET shares = %s, current_price = %s WHERE id = %s",
                            (new_shares, price, existing["id"])
                        )
                conn.commit()
                
            db.log_audit_evidence(
                action="investment_trade",
                status="ok",
                user_id=uid,
                metadata={"symbol": symbol, "action": action, "shares": shares, "price": price},
                retention_tag="transaction"
            )
            return {"success": True}, 200
        except Exception as e:
            logger.error("Trade failed: %s", e)
            return {"error": "Trade execution failed"}, 500
