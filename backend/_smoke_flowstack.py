"""临时冒烟测试：验证 FlowStack 模型能否在当前依赖版本下加载与预测。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.flowstack.model import FlowStackModel  # noqa: E402

MODEL_DIR = ROOT / "artifacts" / "flowstack" / "current" / "model"

try:
    model = FlowStackModel.load(MODEL_DIR)
    print("LOAD OK")
    print("model_version:", model.metadata.get("model_version"))
    print("selected_features:", len(model.selected_features_))
    print("base_learners:", list(model.base_learners.keys()))
    print("fill_values count:", len(model.fill_values_))
    print("feature_names_raw:", len(model.feature_names_raw))
    print("meta_weights:", model.meta_weights_)
except Exception as exc:  # noqa: BLE001
    import traceback
    print("LOAD FAILED")
    traceback.print_exc()
    sys.exit(1)