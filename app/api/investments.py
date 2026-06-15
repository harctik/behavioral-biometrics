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
        """Get user portfolio. Returns seed data when DB has no investments."""
        uid = get_current_user_id()
        db = get_db()
        try:
            with db.get_connection() as conn:
                rows = conn.execute(
                    "SELECT id, symbol, name, shares, avg_price, current_price FROM investments WHERE user_id = ?",
                    (uid,)
                ).fetchall()

                if rows:
                    total_value = 0
                    day_change_abs = 0
                    mapped_holdings = []

                    for row in rows:
                        c_price = row["current_price"]
                        s = row["shares"]
                        val = c_price * s
                        d_change_pct = ((c_price - row["avg_price"]) / row["avg_price"]) * 100 if row["avg_price"] > 0 else 0
                        d_change_pct = round(d_change_pct, 1)
                        d_change_abs_val = val * (d_change_pct / 100)

                        total_value += val
                        day_change_abs += d_change_abs_val

                        mapped_holdings.append({
                            "id": row["id"],
                            "symbol": row["symbol"],
                            "name": row["name"],
                            "type": "equity",
                            "units": s,
                            "avgCost": row["avg_price"],
                            "value": round(val, 2),
                            "change": d_change_pct,
                        })

                    day_change_percent = (day_change_abs / (total_value - day_change_abs)) * 100 if (total_value - day_change_abs) > 0 else 0
                    return {
                        "total_value": round(total_value, 2),
                        "day_change": round(day_change_abs, 2),
                        "day_change_percent": round(day_change_percent, 2),
                        "holdings": mapped_holdings
                    }, 200
        except Exception as e:
            logger.debug("Investments table query failed (expected if table not created): %s", e)

        # ── Seed portfolio — realistic Indian market holdings ──
        seed_holdings = [
            {"id": "h1", "name": "Reliance Industries",       "symbol": "RELIANCE",  "type": "equity", "value": 145200, "change": 2.4,  "units": 50,  "avgCost": 2650},
            {"id": "h2", "name": "HDFC Bank Ltd",              "symbol": "HDFCBANK",  "type": "equity", "value": 84300,  "change": -0.8, "units": 50,  "avgCost": 1720},
            {"id": "h3", "name": "Infosys Ltd",                "symbol": "INFY",      "type": "equity", "value": 62400,  "change": 1.2,  "units": 40,  "avgCost": 1480},
            {"id": "h4", "name": "SBI Bluechip Fund — Direct", "symbol": "SBIBLUE",   "type": "mf",     "value": 125000, "change": 0.6,  "units": 1850, "avgCost": 64.5},
            {"id": "h5", "name": "Axis Long Term Equity Fund", "symbol": "AXISLTEF",  "type": "mf",     "value": 78500,  "change": 1.1,  "units": 950,  "avgCost": 78.2},
            {"id": "h6", "name": "ICICI Prudential Bond Fund", "symbol": "ICICIBOND", "type": "bond",   "value": 50000,  "change": 0.2,  "units": 500,  "avgCost": 98.5},
            {"id": "h7", "name": "SBI 5-Year FD @ 7.1%",      "symbol": "SBIFD5Y",   "type": "fd",     "value": 200000, "change": 0.0,  "units": 1,    "avgCost": 200000},
            {"id": "h8", "name": "Tata Motors Ltd",            "symbol": "TATAMOTORS","type": "equity", "value": 38600,  "change": 3.8,  "units": 60,   "avgCost": 580},
        ]
        total_value = sum(h["value"] for h in seed_holdings)
        total_cost = sum(h["avgCost"] * h["units"] for h in seed_holdings)
        total_gain = total_value - total_cost
        return {
            "total_value": total_value,
            "day_change": round(total_gain * 0.003, 2),
            "day_change_percent": round((total_gain / max(total_cost, 1)) * 100, 2),
            "holdings": seed_holdings,
        }, 200

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
                    "SELECT id, shares, avg_price FROM investments WHERE user_id = ? AND symbol = ?",
                    (uid, symbol)
                ).fetchone()
                
                if action == "buy":
                    if existing:
                        new_shares = existing["shares"] + shares
                        new_avg = ((existing["shares"] * existing["avg_price"]) + (shares * price)) / new_shares
                        conn.execute(
                            "UPDATE investments SET shares = ?, avg_price = ?, current_price = ? WHERE id = ?",
                            (new_shares, new_avg, price, existing["id"])
                        )
                    else:
                        inv_id = f"inv_{str(uuid.uuid4())[:8]}"
                        conn.execute(
                            "INSERT INTO investments (id, user_id, symbol, name, shares, avg_price, current_price) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (inv_id, uid, symbol, symbol, shares, price, price)
                        )
                elif action == "sell":
                    if not existing or existing["shares"] < shares:
                        return {"error": "Insufficient shares"}, 400
                    
                    new_shares = existing["shares"] - shares
                    if new_shares == 0:
                        conn.execute("DELETE FROM investments WHERE id = ?", (existing["id"],))
                    else:
                        conn.execute(
                            "UPDATE investments SET shares = ?, current_price = ? WHERE id = ?",
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
