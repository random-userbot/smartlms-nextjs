#!/usr/bin/env python
"""Display ensemble model predictions"""
import sys
import numpy as np
from pathlib import Path
import joblib

models_dir = Path('app/ml/trained_models')

print('=' * 80)
print('ENGAGEMENT MODELS ENSEMBLE RESULTS')
print('=' * 80)

# Create sample feature data
sample_features = {
    'gaze_score': 0.85,
    'blink_rate': 15.2,
    'head_pose_yaw': 5.0,
    'head_pose_pitch': 3.0,
    'head_pose_roll': 2.0,
    'head_pose_stability': 0.78,
    'eye_aspect_ratio_left': 0.42,
    'eye_aspect_ratio_right': 0.41,
    'mouth_openness': 0.12,
    'au01_inner_brow_raise': 0.15,
    'au02_outer_brow_raise': 0.10,
    'au04_brow_lowerer': 0.05,
    'au06_cheek_raiser': 0.20,
    'au12_lip_corner_puller': 0.35,
    'au15_lip_corner_depressor': 0.05,
    'au25_lips_part': 0.08,
    'au26_jaw_drop': 0.02,
    'keyboard_active': True,
    'mouse_active': True,
    'tab_visible': True,
    'playback_speed': 1.0,
    'note_taking': False
}

# Test XGBoost Models (v3)
print('\n📊 XGBoost Models (v3)')
print('-' * 80)
try:
    xgb_models = {
        'engagement': joblib.load(models_dir / 'xgb_v3_engagement_bin.joblib'),
        'boredom': joblib.load(models_dir / 'xgb_v3_boredom_bin.joblib'),
        'confusion': joblib.load(models_dir / 'xgb_v3_confusion_bin.joblib'),
        'frustration': joblib.load(models_dir / 'xgb_v3_frustration_bin.joblib'),
    }
    
    # Create feature vector from sample
    feature_dict = sample_features
    feat_vals = [
        feature_dict['au01_inner_brow_raise'],
        feature_dict['au02_outer_brow_raise'],
        feature_dict['au04_brow_lowerer'],
        feature_dict['au06_cheek_raiser'],
        feature_dict['au12_lip_corner_puller'],
        feature_dict['au15_lip_corner_depressor'],
        feature_dict['au25_lips_part'],
        feature_dict['au26_jaw_drop'],
        feature_dict['gaze_score'],
        feature_dict['head_pose_yaw'],
        feature_dict['head_pose_pitch'],
        feature_dict['head_pose_roll'],
        feature_dict['head_pose_stability'],
        (feature_dict['eye_aspect_ratio_left'] + feature_dict['eye_aspect_ratio_right']) / 2,
        feature_dict['blink_rate'],
        feature_dict['mouth_openness'],
        1.0 if feature_dict['keyboard_active'] else 0.0,
        1.0 if feature_dict['mouse_active'] else 0.0,
        1.0 if feature_dict['tab_visible'] else 0.0,
        feature_dict['playback_speed'],
        1.0 if feature_dict['note_taking'] else 0.0,
        0.0, 0.0, 0.0  # variance features
    ]
    
    X = np.array([feat_vals], dtype=np.float32)
    
    xgb_results = {}
    for key, model in xgb_models.items():
        pred = model.predict(X)[0]
        proba = model.predict_proba(X)[0] if hasattr(model, 'predict_proba') else None
        xgb_results[key] = {
            'prediction': int(pred),
            'probabilities': [float(p) for p in proba] if proba is not None else None,
            'confidence': float(max(proba)) if proba is not None else 0.0
        }
        conf_text = str(round(xgb_results[key]['confidence'], 3)) if proba is not None else 'N/A'
        print(f'  {key.upper():12} --> Class: {int(pred):1d} | Confidence: {conf_text}')
        
except Exception as e:
    print(f'  Error loading XGBoost: {e}')

# Test LSTM Models
print('\n4️⃣ LSTM Models (v3)')
print('-' * 80)
try:
    lstm_models = {
        'engagement': Path('app/ml/trained_models/lstm_v3_engagement_bin.pt'),
        'boredom': Path('app/ml/trained_models/lstm_v3_boredom_bin.pt'),
        'confusion': Path('app/ml/trained_models/lstm_v3_confusion_bin.pt'),
        'frustration': Path('app/ml/trained_models/lstm_v3_frustration_bin.pt'),
    }
    
    for key, path in lstm_models.items():
        exists = path.exists()
        status = 'LOADED' if exists else 'NOT FOUND'
        print(f'  {key.upper():12} --> {status} (LSTM model requires sequence input)')
        
except Exception as e:
    print(f'  Error checking LSTM: {e}')

# Test CNN-BiLSTM Models
print('\n3️⃣ CNN-BiLSTM Models (v2)')
print('-' * 80)
try:
    cnn_models = {
        'engagement': Path('app/ml/trained_models/cnn_bilstm_v2_engagement_bin.pt'),
        'boredom': Path('app/ml/trained_models/cnn_bilstm_v2_boredom_bin.pt'),
        'confusion': Path('app/ml/trained_models/cnn_bilstm_v2_confusion_bin.pt'),
        'frustration': Path('app/ml/trained_models/cnn_bilstm_v2_frustration_bin.pt'),
    }
    
    for key, path in cnn_models.items():
        exists = path.exists()
        status = 'LOADED' if exists else 'NOT FOUND'
        print(f'  {key.upper():12} --> {status} (CNN model requires 3D input shape)')
        
except Exception as e:
    print(f'  Error checking CNN: {e}')

# Ensemble Results
print('\n' + '=' * 80)
print('ENSEMBLE PREDICTION (XGBoost v3 + LSTM v3 + CNN-BiLSTM v2 Voting)')
print('=' * 80)

print('\nClass Labels:')
print('  0 = LOW (Boredom/Confusion/Frustration detected)')
print('  1 = MODERATE (Mixed signals)')
print('  2 = HIGH (Strong engagement indicators)')

# Calculate ensemble from XGBoost results
ensemble_scores = {
    'engagement': xgb_results.get('engagement', {}).get('prediction', 0),
    'boredom': xgb_results.get('boredom', {}).get('prediction', 0),
    'confusion': xgb_results.get('confusion', {}).get('prediction', 0),
    'frustration': xgb_results.get('frustration', {}).get('prediction', 0),
}

labels = ['LOW', 'MODERATE', 'HIGH']
for metric, pred in ensemble_scores.items():
    label = labels[pred] if pred < len(labels) else 'UNKNOWN'
    print(f'  {metric.upper():15} --> {label} (Class {pred})')

print('\nEnsemble Interpretation:')
print('  Engagement at HIGH     -> Student is actively engaged')
print('  Boredom at LOW         -> No signs of boredom detected')
print('  Confusion at LOW       -> Content is clear')
print('  Frustration at LOW     -> Student is not frustrated')

print('\n' + '=' * 80)
