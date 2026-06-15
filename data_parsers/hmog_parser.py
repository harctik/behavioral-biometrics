import os
import csv
import logging
import numpy as np
from typing import Dict, List, Any

logger = logging.getLogger("hmog_parser")

def parse_hmog(hmog_dir: str) -> Dict[str, List[Dict[str, float]]]:
    """
    Parse HMOG dataset CSV files.
    Returns a dictionary mapping subject ID to a list of feature dictionaries.
    """
    if not os.path.isdir(hmog_dir):
        logger.warning(f"HMOG directory not found: {hmog_dir}")
        return {}

    files = [f for f in os.listdir(hmog_dir) if f.endswith(".csv")]
    if not files:
        logger.warning(f"No CSV files found in {hmog_dir}")
        return {}

    logger.info(f"Parsing {len(files)} HMOG user files...")
    
    by_subject: Dict[str, List[Dict[str, float]]] = {}

    for fname in files:
        filepath = os.path.join(hmog_dir, fname)
        user_id = fname.replace(".csv", "").replace("hmog_user_", "hmog_")
        
        # We generated/downloaded CSVs where each row is a session rep containing features
        try:
            with open(filepath, "r") as f:
                reader = csv.DictReader(f)
                features_list = []
                for row in reader:
                    features = {}
                    for k, v in row.items():
                        if k not in ["user_id", "scenario", "condition", "rep"]:
                            try:
                                features[k] = float(v)
                            except ValueError:
                                pass
                    if features:
                        features_list.append(features)
                
                if features_list:
                    by_subject[user_id] = features_list
        except Exception as e:
            logger.error(f"Error reading {filepath}: {e}")

    return by_subject
