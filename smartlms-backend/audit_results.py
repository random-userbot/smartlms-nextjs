import json, os

files = [
    'app/ml/experiment_results/experiment_xgboost_openface_20260226_033021.json',
    'app/ml/experiment_results/experiment_lstm_openface_20260226_035615.json',
    'app/ml/experiment_results/experiment_cnn_bilstm_openface_20260226_040638.json',
]
for f in files:
    d = json.load(open(f))
    mode = d["mode"]
    strat = d["balance_strategy"]
    print(f"=== {mode} ({strat}) ===")
    for k, v in d['results'].items():
        acc = v.get('test_accuracy', v.get('accuracy', 0))
        f1m = v.get('test_f1_macro', v.get('f1_macro', 0))
        f1w = v.get('test_f1_weighted', v.get('f1_weighted', 0))
        thr = v.get('best_threshold', v.get('optimal_threshold', 0.5))
        print(f"  {k}: acc={acc:.3f} f1m={f1m:.3f} f1w={f1w:.3f} thr={thr:.2f}")
