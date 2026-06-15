import numpy as np

def unify_and_cross_fill(cmu_data, balabit_data, hmog_data):
    """
    Merges CMU, Balabit, and HMOG datasets.
    Cross-fills missing modalities using population statistics from the real data.
    """
    unified_users = {}
    
    # --- Step 1: Compute Population Statistics ---
    
    # 1.1 CMU (Keystroke)
    cmu_all_features = []
    for samples in cmu_data.values():
        cmu_all_features.extend(samples)
    
    cmu_stats = {}
    if cmu_all_features:
        keys = cmu_all_features[0].keys()
        for k in keys:
            vals = [f[k] for f in cmu_all_features if k in f]
            cmu_stats[k] = {"mean": np.mean(vals), "std": np.std(vals)}

    # 1.2 Balabit (Mouse)
    balabit_all_features = []
    for samples in balabit_data.values():
        balabit_all_features.extend(samples)
        
    balabit_stats = {}
    if balabit_all_features:
        keys = balabit_all_features[0].keys()
        for k in keys:
            vals = [f[k] for f in balabit_all_features if k in f]
            balabit_stats[k] = {"mean": np.mean(vals), "std": np.std(vals)}

    # 1.3 HMOG (Touch + Sensor)
    hmog_all_features = []
    for samples in hmog_data.values():
        hmog_all_features.extend(samples)
        
    hmog_stats = {}
    if hmog_all_features:
        keys = hmog_all_features[0].keys()
        for k in keys:
            vals = [f[k] for f in hmog_all_features if k in f]
            hmog_stats[k] = {"mean": np.mean(vals), "std": np.std(vals)}

    rng = np.random.default_rng(42)

    def fill_missing(features, required_keys, stats_dict):
        for k, stats in stats_dict.items():
            if k not in features and k in required_keys:
                # Use real population stats to fill missing modalities
                features[k] = max(0.0, rng.normal(stats["mean"], stats["std"] * 0.5))

    # We define the full target schema based on what models expect.
    # We'll use a reference full list.
    target_keys = set(cmu_stats.keys()).union(set(balabit_stats.keys())).union(set(hmog_stats.keys()))

    # --- Step 2: Unify Users ---
    
    # CMU users get missing mouse from Balabit stats, missing touch from HMOG stats
    for user, samples in cmu_data.items():
        unified = []
        for f in samples:
            new_f = f.copy()
            fill_missing(new_f, target_keys, balabit_stats)
            fill_missing(new_f, target_keys, hmog_stats)
            unified.append(new_f)
        unified_users[user] = unified

    # Balabit users get missing keystroke from CMU, missing touch from HMOG
    for user, samples in balabit_data.items():
        unified = []
        for f in samples:
            new_f = f.copy()
            fill_missing(new_f, target_keys, cmu_stats)
            fill_missing(new_f, target_keys, hmog_stats)
            unified.append(new_f)
        unified_users[user] = unified
        
    # HMOG users get missing keystroke from CMU, missing mouse from Balabit
    for user, samples in hmog_data.items():
        unified = []
        for f in samples:
            new_f = f.copy()
            fill_missing(new_f, target_keys, cmu_stats)
            fill_missing(new_f, target_keys, balabit_stats)
            unified.append(new_f)
        unified_users[user] = unified

    return unified_users
