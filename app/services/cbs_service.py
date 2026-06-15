"""
Mock Core Banking System (CBS) Service.
Simulates a real Indian banking ledger and handles Maker-Checker logic for corporate accounts.
"""

import logging
from typing import Dict, List, Optional
import time

logger = logging.getLogger(__name__)

class MockCBSService:
    """
    In a real bank (like SBI/HDFC), the Netbanking portal is just a frontend that 
    talks to the CBS (e.g., Finacle or TCS BaNCS) via SOAP/REST APIs.
    This mock service simulates the CBS ledger and Maker-Checker logic.
    """
    
    # In-memory mock ledger. In a real app, this would be a dedicated CBS database.
    # Format: { user_id: { "account_number": str, "balance": float, "is_corporate": bool } }
    _ledger: Dict[int, Dict] = {}
    
    # In-memory pending approvals for Maker-Checker
    # Format: { txn_id: { "maker_id": int, "amount": float, "beneficiary": str, "timestamp": float } }
    _pending_approvals: Dict[str, Dict] = {}
    
    @classmethod
    def get_account_details(cls, user_id: int) -> Dict:
        """Fetch account details from the CBS ledger."""
        if user_id not in cls._ledger:
            # Auto-provision mock account
            cls._ledger[user_id] = {
                "account_number": f"0000{user_id}12345",
                "balance": 250000.00,  # Default 2.5 Lakhs
                "is_corporate": user_id % 2 == 0  # Even user IDs are corporate for demo purposes
            }
        return cls._ledger[user_id]

    @classmethod
    def initiate_transfer(cls, maker_id: int, amount: float, beneficiary: str, is_corporate: bool = False) -> Dict:
        """
        Initiate a transfer.
        If retail, process immediately.
        If corporate (Maker), park in pending approvals for Checker.
        """
        account = cls.get_account_details(maker_id)
        
        if amount > account["balance"]:
            return {"status": "failed", "reason": "Insufficient funds in CBS"}
            
        if is_corporate or account["is_corporate"]:
            # Park in Maker-Checker queue
            import uuid
            txn_id = str(uuid.uuid4())
            cls._pending_approvals[txn_id] = {
                "maker_id": maker_id,
                "amount": amount,
                "beneficiary": beneficiary,
                "timestamp": time.time(),
                "status": "pending_checker_approval"
            }
            return {
                "status": "pending_approval", 
                "txn_id": txn_id,
                "message": "Transaction initiated by Maker. Pending Checker approval."
            }
            
        # Retail transaction: process immediately
        cls._ledger[maker_id]["balance"] -= amount
        return {
            "status": "success",
            "message": f"Successfully transferred Rs {amount:,.2f} to {beneficiary}"
        }

    @classmethod
    def get_pending_approvals(cls, checker_id: int) -> List[Dict]:
        """Fetch all pending transactions for Corporate Banking Checkers."""
        # In a real app, we'd filter by corporate entity ID.
        # Here we return all pending that were NOT made by this user (Maker != Checker).
        pending = []
        for txn_id, txn in cls._pending_approvals.items():
            if txn["maker_id"] != checker_id and txn["status"] == "pending_checker_approval":
                pending.append({
                    "txn_id": txn_id,
                    "maker_id": txn["maker_id"],
                    "amount": txn["amount"],
                    "beneficiary": txn["beneficiary"],
                    "timestamp": txn["timestamp"]
                })
        return pending

    @classmethod
    def approve_transfer(cls, checker_id: int, txn_id: str) -> Dict:
        """
        Checker approves a transfer.
        Note: The actual Behavioral Biometric check (Siamese Network) happens BEFORE this in the API layer.
        """
        if txn_id not in cls._pending_approvals:
            return {"status": "failed", "reason": "Transaction not found or already processed"}
            
        txn = cls._pending_approvals[txn_id]
        
        if txn["maker_id"] == checker_id:
            return {"status": "failed", "reason": "Maker and Checker cannot be the same user ID"}
            
        # Process the ledger deduction
        maker_account = cls.get_account_details(txn["maker_id"])
        if txn["amount"] > maker_account["balance"]:
            txn["status"] = "failed_insufficient_funds"
            return {"status": "failed", "reason": "Maker has insufficient funds"}
            
        cls._ledger[txn["maker_id"]]["balance"] -= txn["amount"]
        txn["status"] = "approved"
        txn["checker_id"] = checker_id
        
        return {
            "status": "success",
            "message": f"Transaction approved by Checker. Rs {txn['amount']:,.2f} transferred to {txn['beneficiary']}"
        }
