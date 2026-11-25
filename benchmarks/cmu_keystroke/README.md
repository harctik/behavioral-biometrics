# CMU keystroke benchmark

Standalone baseline detectors, not the platform's production ensemble: `cmu_benchmark.py` builds its own scikit-learn and NumPy models and does not import the platform's code.

Public CMU dataset (Killourhy & Maxion 2009): 51 subjects, 400 reps each. Per subject: train on first 200 genuine reps, test on remaining 200 genuine + 250 impostor attempts (first 5 reps of each other subject). Hyperparameters tuned on 10 held-out subjects only; results are the mean over the other 41 subjects.

| Detector | Default EER | Tuned EER | Tuned AUC | Best params |
|---|---|---|---|---|
| Scaled Manhattan | 8.7% | 8.7% | 0.961 | {} |
| Mahalanobis | 10.4% | 10.1% | 0.953 | {'shrink': 0.3} |
| k-NN distance | 8.7% | 8.6% | 0.964 | {'k': 3} |
| Isolation Forest | 8.1% | 7.2% | 0.974 | {'n_estimators': 300, 'max_samples': 32} |
| One-Class SVM | 9.8% | 9.8% | 0.952 | {'nu': 0.2, 'gamma_mult': 1.0} |
| Autoencoder (MLP) | 11.3% | 9.9% | 0.956 | {'hidden': [16, 8, 16], 'alpha': 0.01} |

Score-fusion (Isolation Forest + k-NN distance): EER 7.3%, AUC 0.972. It did not beat the best single tuned model.

Run: `python cmu_benchmark.py DSL-StrongPasswordData.csv results.json`