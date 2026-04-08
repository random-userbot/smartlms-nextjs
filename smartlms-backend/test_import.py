try:
    from app.ml.engagement_model import EngagementModel
    print("Import successful")
    em = EngagementModel()
    print("Instance created")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
