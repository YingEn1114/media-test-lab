import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 单测强制使用临时数据库，绝不碰真实的 platform.db
_TMP = tempfile.mkdtemp(prefix="zgqa-unit-")
os.environ["ZG_DB"] = os.path.join(_TMP, "platform.db")
