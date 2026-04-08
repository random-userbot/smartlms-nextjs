import nbformat as nbf
import os

notebook_path = r'c:\Users\revan\Downloads\smartlms-version2\smartlms-backend\analyze_engagement.ipynb'

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = nbf.read(f, as_version=4)

# Fix existing cells
for cell in nb.cells:
    if cell.cell_type == 'code':
        # Fix actual_engagement -> actual_ensemble
        cell.source = cell.source.replace("'actual_engagement'", "'actual_ensemble'")
        cell.source = cell.source.replace('"actual_engagement"', '"actual_ensemble"')
        # Fix forecasted_engagement -> forecast_60s
        cell.source = cell.source.replace("'forecasted_engagement'", "'forecast_60s'")
        cell.source = cell.source.replace('"forecasted_engagement"', '"forecast_60s"')

# Add new cells at the end
new_cells = [
    nbf.v4.new_markdown_cell("## 📈 Granular XGBoost Dimensions\nLooking at the individual components of the ensemble: Engagement, Boredom, Confusion, and Frustration."),
    nbf.v4.new_code_cell("""xgb_cols = ['xgb_engagement', 'xgb_boredom', 'xgb_confusion', 'xgb_frustration']
if all(c in df.columns for c in xgb_cols):
    plt.figure(figsize=(16, 6))
    for col in xgb_cols:
        plt.plot(df['elapsed_sec'], df[col], label=col.replace('xgb_', '').capitalize())
    
    plt.title('XGBoost Internal Dimensions Timeline', fontsize=16, fontweight='black')
    plt.xlabel('Time (s)')
    plt.ylabel('Score (0-100)')
    plt.legend()
    plt.show()
else:
    print("Granular XGB columns missing in CSV.")"""),
    nbf.v4.new_markdown_cell("## 🚫 Behavioral Lapses: Face Detection\nVisualizing periods where the face was not detected by MediaPipe."),
    nbf.v4.new_code_cell("""plt.figure(figsize=(16, 3))
plt.fill_between(df['elapsed_sec'], 0, 1, where=~df['face_detected'], color='salmon', alpha=0.5, label='Face Not Detected')
plt.yticks([])
plt.title('Attention Lapses & Visibility Drops', fontsize=16, fontweight='black')
plt.xlabel('Elapsed Time (seconds)')
plt.legend()
plt.show()

lapse_pct = (1 - df['face_detected'].mean()) * 100
print(f"Total visibility lapse: {round(lapse_pct, 2)}% of the session.")""")
]

nb.cells.extend(new_cells)

with open(notebook_path, 'w', encoding='utf-8') as f:
    nbf.write(nb, f)

print(f"Successfully updated {notebook_path}")
