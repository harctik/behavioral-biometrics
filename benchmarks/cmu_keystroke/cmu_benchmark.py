"""
Keystroke-dynamics benchmark on the public CMU dataset (Killourhy & Maxion, 2009):
51 subjects x 400 password repetitions, 31 timing features.

Protocol (standard CMU one-class protocol):
  train    = first 200 genuine repetitions of the subject
  genuine  = remaining 200 repetitions of the subject
  impostor = first 5 repetitions of each of the other 50 subjects (250 attempts)
Hyperparameters are tuned ONLY on 10 held-out "tuning" subjects; reported results
come from the other 41 subjects, which are never used for tuning.
"""

import json, sys, itertools, warnings, time
import numpy as np, pandas as pd
from joblib import Parallel, delayed
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.neighbors import NearestNeighbors
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import roc_curve, roc_auc_score

warnings.filterwarnings("ignore")

CSV = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else "results.json"
df = pd.read_csv(CSV)
FEATS = [c for c in df.columns if c not in ("subject", "sessionIndex", "rep")]
subjects = sorted(df.subject.unique())
data = {s: df[df.subject == s][FEATS].values for s in subjects}
tune_subj = subjects[::5][:10]
test_subj = [s for s in subjects if s not in tune_subj]


def eer(y, s):
    fpr, tpr, _ = roc_curve(y, s)
    fnr = 1 - tpr
    i = np.nanargmin(np.abs(fnr - fpr))
    return float((fpr[i] + fnr[i]) / 2)


# ---------------- detectors: fit(Xtrain, **params) -> score(X) (higher = more anomalous)
def fit_manhattan(X, **_):
    mu = X.mean(0)
    mad = np.abs(X - mu).mean(0) + 1e-9
    return lambda Z: (np.abs(Z - mu) / mad).sum(1)


def fit_mahalanobis(X, shrink=0.1, **_):
    mu = X.mean(0)
    C = np.cov(X, rowvar=False)
    C = (1 - shrink) * C + shrink * np.trace(C) / C.shape[0] * np.eye(C.shape[0])
    P = np.linalg.inv(C)
    return lambda Z: np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", Z - mu, P, Z - mu), 0))


def fit_knn(X, k=5, **_):
    nn = NearestNeighbors(n_neighbors=k).fit(X)
    return lambda Z: nn.kneighbors(Z)[0].mean(1)


def fit_iforest(X, n_estimators=100, max_samples=128, **_):
    m = IsolationForest(
        n_estimators=n_estimators, max_samples=min(max_samples, len(X)), random_state=0
    ).fit(X)
    return lambda Z: -m.score_samples(Z)


def fit_ocsvm(X, nu=0.1, gamma_mult=1.0, **_):
    m = OneClassSVM(nu=nu, gamma=gamma_mult / X.shape[1]).fit(X)
    return lambda Z: -m.decision_function(Z)


def fit_ae(X, hidden=(16,), alpha=1e-3, **_):
    m = MLPRegressor(
        hidden_layer_sizes=hidden, alpha=alpha, max_iter=600, random_state=0
    ).fit(X, X)
    return lambda Z: ((m.predict(Z) - Z) ** 2).mean(1)


DETECTORS = {
    "Scaled Manhattan": (fit_manhattan, [{}]),
    "Mahalanobis": (fit_mahalanobis, [{"shrink": s} for s in (0.001, 0.01, 0.1, 0.3)]),
    "k-NN distance": (fit_knn, [{"k": k} for k in (1, 3, 5, 10, 20)]),
    "Isolation Forest": (
        fit_iforest,
        [
            {"n_estimators": n, "max_samples": m}
            for n in (100, 300)
            for m in (32, 64, 128, 200)
        ],
    ),
    "One-Class SVM": (
        fit_ocsvm,
        [
            {"nu": nu, "gamma_mult": g}
            for nu in (0.02, 0.05, 0.1, 0.2)
            for g in (0.03, 0.1, 0.3, 1.0)
        ],
    ),
    "Autoencoder (MLP)": (
        fit_ae,
        [
            {"hidden": h, "alpha": a}
            for h in ((8,), (16,), (16, 8, 16))
            for a in (1e-4, 1e-2)
        ],
    ),
}
DEFAULTS = {
    "Scaled Manhattan": {},
    "Mahalanobis": {"shrink": 0.001},
    "k-NN distance": {"k": 5},
    "Isolation Forest": {"n_estimators": 100, "max_samples": 128},
    "One-Class SVM": {"nu": 0.1, "gamma_mult": 1.0},
    "Autoencoder (MLP)": {"hidden": (16,), "alpha": 1e-4},
}


def split(s):
    Xs = data[s]
    train, gen = Xs[:200], Xs[200:]
    imp = np.vstack([data[o][:5] for o in subjects if o != s])
    sc = StandardScaler().fit(train)
    return sc.transform(train), sc.transform(gen), sc.transform(imp)


def scores_for(s, name, params, calib=False):
    fit = DETECTORS[name][0]
    tr, gen, imp = split(s)
    sc = fit(tr, **params)
    out = {"gen": sc(gen), "imp": sc(imp)}
    if (
        calib
    ):  # genuine-score statistics from 5-fold leave-out on training data (for fusion)
        cs = []
        for k in range(5):
            idx = np.arange(len(tr))
            te = idx[k::5]
            trn = np.setdiff1d(idx, te)
            cs.append(fit(tr[trn], **params)(tr[te]))
        cs = np.concatenate(cs)
        out["mu"], out["sd"] = cs.mean(), cs.std() + 1e-9
    return out


def subj_eer(s, name, params):
    o = scores_for(s, name, params)
    y = np.r_[np.zeros(len(o["gen"])), np.ones(len(o["imp"]))]
    sc = np.r_[o["gen"], o["imp"]]
    return eer(y, sc), roc_auc_score(y, sc)


def evaluate(name, params, subs):
    r = Parallel(n_jobs=2)(delayed(subj_eer)(s, name, params) for s in subs)
    return np.array(r)


t0 = time.time()
res = {
    "protocol": {
        "dataset": "CMU Keystroke Dynamics (DSL-StrongPasswordData)",
        "subjects": len(subjects),
        "tuning_subjects": len(tune_subj),
        "test_subjects": len(test_subj),
        "train_per_subject": 200,
        "genuine_test_per_subject": 200,
        "impostor_test_per_subject": 250,
    },
    "models": {},
}
best = {}
for name, (fit, grid) in DETECTORS.items():
    tuned = []
    for p in grid:
        e = evaluate(name, p, tune_subj)[:, 0].mean()
        tuned.append((e, p))
    tuned.sort(key=lambda x: x[0])
    best[name] = tuned[0][1]
    d = evaluate(name, DEFAULTS[name], test_subj)
    b = evaluate(name, best[name], test_subj)
    res["models"][name] = {
        "grid_size": len(grid),
        "best_params": {
            k: (list(v) if isinstance(v, tuple) else v) for k, v in best[name].items()
        },
        "tuning_EER": round(tuned[0][0], 4),
        "default_EER": round(d[:, 0].mean(), 4),
        "tuned_EER": round(b[:, 0].mean(), 4),
        "tuned_EER_std": round(b[:, 0].std(), 4),
        "tuned_AUC": round(b[:, 1].mean(), 4),
    }
    print(name, res["models"][name], f"{time.time()-t0:.0f}s", flush=True)

# ---- score fusion: z-normalise each detector with genuine CV stats, average best detectors
ranked = sorted(res["models"], key=lambda n: res["models"][n]["tuning_EER"])


def fuse_subject(s, names):
    outs = [scores_for(s, n, best[n], calib=True) for n in names]
    g = np.mean([(o["gen"] - o["mu"]) / o["sd"] for o in outs], axis=0)
    i = np.mean([(o["imp"] - o["mu"]) / o["sd"] for o in outs], axis=0)
    y = np.r_[np.zeros(len(g)), np.ones(len(i))]
    sc = np.r_[g, i]
    return eer(y, sc), roc_auc_score(y, sc)


def fuse_eval(names, subs):
    return np.array(Parallel(n_jobs=2)(delayed(fuse_subject)(s, names) for s in subs))


# choose fusion size k on tuning subjects only
cand = {k: fuse_eval(ranked[:k], tune_subj)[:, 0].mean() for k in (2, 3, 4, 5, 6)}
kbest = min(cand, key=cand.get)
f = fuse_eval(ranked[:kbest], test_subj)
res["ensemble"] = {
    "members": ranked[:kbest],
    "tuning_EER_by_size": {str(k): round(v, 4) for k, v in cand.items()},
    "EER": round(f[:, 0].mean(), 4),
    "EER_std": round(f[:, 0].std(), 4),
    "AUC": round(f[:, 1].mean(), 4),
}
print("ENSEMBLE", res["ensemble"])
res["runtime_s"] = round(time.time() - t0)
json.dump(res, open(OUT, "w"), indent=2)
