# SPDX-License-Identifier: GPL-3.0-or-later
"""把项目根目录加入 sys.path，使测试可直接 import 各模块。"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
