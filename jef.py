#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
═══════════════════════════════════════════════════════════════════════════
         ADVANCED TRADING BOT v24.3 - QUANT MAX
═══════════════════════════════════════════════════════════════════════════

✅ خودکامل‌گر کامل - تمام پارامترها را خودش تنظیم می‌کند
✅ ML Auto-Pilot - خودش تصمیم می‌گیرد روشن شود یا نه
✅ گزارش کامل هر ۳۰ دقیقه با تمام تغییرات و دلایل
✅ هدف: رسیدن به بالاترین وین‌ریت ممکن
✅ بدون نیاز به هیچ دخالت انسانی

نسخه 24.3 QUANT MAX - EV Gate | Drift | Experiment Log | Purged ML | Feature Store | Ops harden
"""

# ============================================================================
# بخش 1: ایمپورت کتابخانه‌ها
# ============================================================================

import os
import sys
import time
import json
import math
import threading
import traceback
import shutil
import copy
from typing import List, Dict, Any, Optional, Tuple
from collections import deque
from datetime import datetime
from functools import wraps
from dataclasses import dataclass, field
from enum import Enum

import requests
_PROCESS_START_TS = time.time()
import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier, ExtraTreesClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import roc_auc_score, accuracy_score, brier_score_loss
    import joblib
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
    try:
        import xgboost as _xgb
        XGBOOST_VERSION = getattr(_xgb, "__version__", "unknown")
    except Exception:
        XGBOOST_VERSION = "unknown"
except Exception:
    XGBClassifier = None
    XGBOOST_AVAILABLE = False
    XGBOOST_VERSION = "not-installed"

try:
    from catboost import CatBoostClassifier
    CATBOOST_AVAILABLE = True
except Exception:
    CatBoostClassifier = None
    CATBOOST_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except Exception:
    Image = ImageDraw = ImageFont = None
    PIL_AVAILABLE = False

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ============================================================================
# بخش 2: تنظیمات اصلی (CONFIG) - نسخه 18.0 - حداقل اولیه
# ============================================================================

KLINE_INTERVAL = sys.argv[1].strip() if len(sys.argv) > 1 else "15m"
_raw_cli_mode = sys.argv[2].strip().lower() if len(sys.argv) > 2 else "medium"
if _raw_cli_mode.isdigit():
    RUN_MODE = "medium"
    LEVERAGE = max(1, int(_raw_cli_mode))
else:
    RUN_MODE = _raw_cli_mode if _raw_cli_mode in {"soft", "medium", "hard"} else "medium"
    try:
        LEVERAGE = max(1, int(sys.argv[3].strip())) if len(sys.argv) > 3 else 10
    except ValueError:
        LEVERAGE = 10

def get_default_data_dir() -> str:
    env_dir = os.environ.get("DATA_DIR")
    if env_dir:
        return env_dir
    try:
        if os.name == 'nt':
            return os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'TradingBot')
        elif hasattr(os, 'uname') and os.uname().sysname == 'Darwin':
            return os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'TradingBot')
        else:
            if os.path.exists('/sdcard/Download/'):
                return '/sdcard/Download/'
            return os.path.join(os.path.expanduser('~'), '.tradingbot')
    except Exception as e:
        print(f"❌ خطا در تشخیص مسیر داده: {e}")
        return os.path.join(os.path.expanduser('~'), '.tradingbot')

DATA_DIR = get_default_data_dir()
os.makedirs(DATA_DIR, exist_ok=True)
print(f"📁 مسیر داده: {DATA_DIR}")

PATHS = {
    "HISTORY_FILE": os.path.join(DATA_DIR, "coin_history.json"),
    "SIGNAL_HISTORY_FILE": os.path.join(DATA_DIR, "signal_history.json"),
    "FINAL_SIGNAL_FILE": os.path.join(DATA_DIR, "final_signals.json"),
    "ANALYZER_OUTPUT_FILE": os.path.join(DATA_DIR, "pro_analyzer_output.json"),
    "FILTER_JSON": os.path.join(DATA_DIR, "symbols_filter.json"),
    "OPTIMIZED_PARAMS_FILE": os.path.join(DATA_DIR, "optimized_params.json"),
    "FEATURE_WEIGHTS_FILE": os.path.join(DATA_DIR, "feature_weights.json"),
    "PATTERNS_FILE": os.path.join(DATA_DIR, "learned_patterns.json"),
    "AUTO_LEARN_QUEUE": os.path.join(DATA_DIR, "auto_learn_queue.json"),
    "PERFORMANCE_REPORT": os.path.join(DATA_DIR, "performance_report.json"),
    "ML_MODEL_FILE": os.path.join(DATA_DIR, "ml_model.joblib"),
    "DEBUG_LOG": os.path.join(DATA_DIR, "debug.log"),
    "ARCHIVE_FILE": os.path.join(DATA_DIR, "trades_archive.json"),
    "AUTOPILOT_STATE": os.path.join(DATA_DIR, "autopilot_state.json"),
    "SIGNAL_DIAGNOSTICS": os.path.join(DATA_DIR, "signal_diagnostics.json"),
    "CONFIG_BACKUP_DIR": os.path.join(DATA_DIR, "config_backups"),
    "EVOLUTION_HISTORY": os.path.join(DATA_DIR, "evolution_history.json"),
    "ML_DECISION_HISTORY": os.path.join(DATA_DIR, "ml_decision_history.json"),
    "PARAMETER_OPTIMIZATION_HISTORY": os.path.join(DATA_DIR, "parameter_optimization_history.json"),
    "REPORT_HISTORY": os.path.join(DATA_DIR, "report_history.json"),
    "RUNTIME_TELEMETRY": os.path.join(DATA_DIR, "runtime_telemetry.json"),
    "SENT_SIGNALS_LOG": os.path.join(DATA_DIR, "sent_signals_log.json"),
    "OUTCOME_REPORT_STATE": os.path.join(DATA_DIR, "outcome_report_state.json"),
}

# حداقل تنظیمات اولیه - سیستم خودش بقیه را بهینه می‌کند
CONFIG = {
    "CHECK_INTERVAL": 120,
    "KLINE_INTERVAL": KLINE_INTERVAL,
    
    "PUMP_THRESHOLD": 1.00,
    "DUMP_THRESHOLD": -1.00,
    "MIN_CONFIDENCE_SCORE": 5.6,
    "WEIGHT_SHARPEN_EXPONENT_MAX": 1.5,
    "WEIGHT_SHARPEN_MIN_TRADES": 50,
    "WEIGHT_SHARPEN_FULL_TRADES": 250,

    "ML_MAX_INFLUENCE": 0.08,
    "ML_ALLOW_PROVISIONAL_MODEL": True,
    "ML_MIN_TRADES_TO_TRAIN": 100,
    "ML_RETRAIN_INTERVAL": 25,
    "ML_FULL_MATURITY_TRADES": 350,
    "ML_MIN_AUC_FOR_INFLUENCE": 0.54,
    "ML_FULL_AUC_FOR_INFLUENCE": 0.64,
    "ML_MIN_WF_FOLDS": 4,
    "ML_MIN_WF_AUC": 0.54,
    # std خام فقط سقف خیلی شل برای رد فولدهای واقعاً بی‌ثبات
    "ML_MAX_WF_AUC_STD": 0.30,
    # معیار اصلی پایداری: SEM = std / sqrt(folds) — با داده بیشتر واقعاً کم می‌شود
    "ML_MAX_WF_AUC_SEM": 0.055,
    "ML_MIN_TRAIN_SAMPLES": 80,
    # FIX v21.2: block=15 واریانس AUC را مصنوعی بالا می‌برد؛ 32 پایدارتر است
    "ML_TEST_BLOCK": 32,
    "ML_WF_GAP": 6,
    "ML_HOLDOUT_FRACTION": 0.18,
    "ML_MIN_HOLDOUT_SAMPLES": 25,
    "ML_MODEL_VERSION": 10,
    "ML_AUTO_HEAL": True,
    "ML_REQUIRE_BRIER_MAX": 0.26,
    "ML_PROVISIONAL_INFLUENCE": 0.015,
    "ML_DISABLE_IF_LAST_AUC_BELOW": 0.48,
    "ML_EDGE_MIN_TRADES": 200,
    
    "REGIME_CONFIDENCE_ADJUSTMENT": {
        "VOLATILE": 0.0,
        "TRENDING": 0.0,
        "UNKNOWN": 0.0,
    },
    "REGIME_MIN_TRADES_FOR_ADJUST": 20,
    "REGIME_MAX_ADJUSTMENT": 0.50,
    "REGIME_ADJUSTMENT_STEP": 0.05,
    "REGIME_ADJUSTMENT_SENSITIVITY": 0.10,
    
    "ADAPTIVE_PUMP_THRESHOLD": True,
    "PUMP_THRESHOLD_BASE": 1.00,
    "PUMP_THRESHOLD_MIN": 0.6,
    "PUMP_THRESHOLD_MAX": 2.5,
    
    "KLINE_LIMIT": 400,
    "MIN_QUOTE_VOLUME": 200000,
    "MAX_SPREAD_PCT": 0.003,
    "MAX_24H_CHANGE": 100.0,
    
    "ACCOUNT_BALANCE": 1000.0,
    "RISK_PERCENT": 0.55,
    "LEVERAGE": LEVERAGE,
    "MAX_RISK_PER_DAY": 10.0,
    "MIN_RISK_PERCENT": 0.2,
    "MAX_RISK_PERCENT": 2.0,
    
    "COMMISSION_PCT": 0.0004,
    "SLIPPAGE_PCT": 0.0005,
    
    "EMA_SHORT": 10,
    "EMA_MED": 30,
    "EMA_LONG": 80,
    "RSI_PERIOD": 10,
    "ATR_PERIOD": 10,
    
    "ATR_MULT_SL": 1.45,
    "ATR_MULT_MIN": 0.8,
    "ATR_MULT_MAX": 3.0,
    # کمی نزدیک‌تر از قبل → TP زودتر قابل دسترس (کاهش خیلی ملایم)
    "TP_ATR_MULTS": [1.65, 2.40, 3.70],
    
    "BACKTEST_CANDLES": 400,
    "BACKTEST_MIN_REQUIRED": 35,
    
    "VOLATILITY_REGIME_ATR_RATIO": 0.015,
    "VOLATILITY_LOW_THRESHOLD": 0.003,
    "VOLATILITY_HIGH_THRESHOLD": 0.045,
    
    "WF_TRAIN_RATIO": 0.7,
    "LEARNING_WINDOW": 70,
    "ADAPTIVE_UPDATE_INTERVAL": 8,
    "MIN_TRADES_FOR_LEARNING": 15,
    "MIN_TRADES_FOR_CORRELATION": 10,
    "LEARNING_RATE": 0.15,
    "MIN_WF_TEST_TRADES": 6,
    "LEARNING_REPORT_INTERVAL_HOURS": 0.5,
    "REPORT_INTERVAL_SEC": 1800,
    "REPORT_VERSION": "24.3-QUANT",
    "BOT_VERSION": "24.3-QUANT",
    "PRO_MIN_CONFIDENCE": 5.9,
    "PRO_MIN_RR_TP1": 0.80,
    # میانگین pre-move تاریخی ~3.8% بود؛ 2.6 باعث رد زیاد entry_too_late می‌شد.
    "PRO_MAX_PRE_SIGNAL_MOVE_PCT": 3.5,
    "PRO_MIN_BACKTEST_WR": 44.0,
    "PRO_MIN_ML_PROBABILITY": 0.52,
    # weak_ml فقط با influence معنادار + edge غیرمنفی (در pro_signal_quality_gate)
    "PRO_ML_GATE_MIN_INFLUENCE": 0.03,
    "PRO_ML_GATE_REQUIRE_POSITIVE_EDGE": True,
    "PRO_ENABLE_FINAL_QUALITY_GATE": True,
    "PRO_ENABLE_EV_GATE": True,
    "PRO_MIN_EV_R": 0.05,
    "PRO_DISABLE_STARVATION_LOOSENING": False,
    
    "GRID_SEARCH_ENABLED": True,
    "GRID_PARAMS": {
        "ATR_MULT_SL": [0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0],
        "EMA_SHORT": [5, 8, 10, 12, 15],
        "EMA_MED": [20, 25, 30, 35, 40, 50],
    },
    
    "REQUIRE_VOLUME_SPIKE": True,
    "MIN_VOLUME_RATIO": 1.10,
    "MAX_CONSECUTIVE_LOSSES": 5,
    "LOSS_STREAK_COOLDOWN_SEC": 900,
    "COOLDOWN_AFTER_LOSS": 1500,
    
    "MAX_HOLD_MINUTES": 48,
    "AUTO_LEARN_ENABLED": True,
    "AUTO_LEARN_PATH_BASED": True,
    "AUTO_LEARN_DEDUP_WINDOW_SEC": 300,
    "AUTO_LEARN_MAX_RETRIES": 5,

    "CCI_PERIOD": 12,
    "WILLIAMS_R_PERIOD": 10,
    "MFI_PERIOD": 10,
    "SUPERTREND_PERIOD": 8,
    "SUPERTREND_MULT": 2.5,
    "ADX_TREND_MIN": 16,
    
    # FIX #4: توکن قبلی هاردکد بود و توی سورس لو رفته بود.
    # باید توکن قبلی رو از BotFather ری‌ووک (Revoke) کنی و توکن جدید رو
    # فقط به‌صورت متغیر محیطی TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID ست کنی.
    "TELEGRAM_BOT_TOKEN": "",
    "TELEGRAM_CHAT_ID": "",
    # کانال دوم: گزارش ۳۰دقیقه + خلاصه outcome هر ۲ ساعت
    "TELEGRAM_REPORT_CHAT_ID": "",
    "OUTCOME_REPORT_INTERVAL_SEC": 7200,       # خلاصه جزئی هر ۲ ساعت
    "OUTCOME_SUMMARY_INTERVAL_SEC": 21600,   # خلاصه جمع هر ۶ ساعت
    "OUTCOME_REPORT_ENABLED": True,
    "OUTCOME_SIGNAL_MATCH_WINDOW_SEC": 7200, # حداکثر فاصله سیگنال→نتیجه برای match
    # کارت گرافیکی سیگنال (نیاز به Pillow) — پیش‌فرض PNG خوانا
    "SIGNAL_GIF_ENABLED": True,          # False = فقط متن
    "SIGNAL_CARD_MODE": "png",            # "png" خوانا | "gif" متحرک (تلگرام ممکن است محو کند)
    "SIGNAL_GIF_FRAMES": 10,
    "SIGNAL_GIF_FRAME_MS": 100,
    
    "MEMORY_MAX_SIZE": 2000,
    "ARCHIVE_MAX_SIZE": 100000,
    "ML_PROBABILITY_FLOOR": 0.05,
    "ML_PROBABILITY_CEILING": 0.95,
    "ML_DIRECTION_MIN_SAMPLES": 20,
    "ML_REGIME_MIN_SAMPLES": 20,
    "REGIME_BAD_WINRATE": 0.44,
    "REGIME_GOOD_WINRATE": 0.56,
    "SYMBOL_COOLDOWN_SEC": 2700,          # 45 دقیقه — ضد تکرار هم‌نماد
    "MAX_PENDING_PER_SYMBOL": 1,
    "MAX_NEW_SIGNALS_PER_CYCLE": 4,
    "MAX_NEW_SIGNALS_PER_HOUR": 24,
    "MAX_NEW_SIGNALS_PER_HOUR_BUSY": 30,  # فقط اگر PF اخیر قوی باشد
    "MAX_SAME_DIRECTION_RATIO": 0.70,
    "MAX_OPEN_SIGNALS_TOTAL": 16,
    "MAX_OPEN_SAME_DIRECTION": 10,
    "MAX_OPEN_PER_SYMBOL": 1,             # حداکثر ۱ سیگنال باز per symbol
    "MIN_SYMBOL_RESHIFT_SEC": 2700,       # فاصله حداقل بین دو سیگنال هم‌نماد (~45m)

    # --- Portfolio / execution (هدف ۱۰) ---
    "EXECUTION_MODE": "paper",            # paper | signal_only  (live orders جدا و نیاز به API key)
    "MAX_DAILY_LOSS_PCT": 4.0,            # توقف سیگنال اگر ضرر روز از این % بگذرد
    "MAX_PORTFOLIO_RISK_PCT": 8.0,        # فقط paper_open × RISK% (نه صف یادگیری)
    "POSITION_SIZE_FROM_RISK": True,
    "PAPER_TRADES_FILE": "",              # خالی = DATA_DIR/paper_trades.json
    "OUTCOME_PREFER_SENT_ONLY": True,
    "PAPER_EXPIRE_MINUTES": 100,          # پاک‌سازی paper باز بعد از این مدت
    "QUEUE_RISK_MAX_AGE_SEC": 5400,       # صف قدیمی در سقف باز شمرده نشود
    "AUTO_HEAL_INTERVAL_SEC": 120,
    "MAX_EFFECTIVE_CONFIDENCE": 6.6,
    "SIGNAL_STARVATION_MINUTES": 14,
    "SIGNAL_STARVATION_THRESHOLD_MIN": 0.7,
    "SIGNAL_STARVATION_THRESHOLD_MAX": 1.8,
    "SIGNAL_STARVATION_RECOVERY_STEP": 0.08,
    "AUTO_HEAL_MIN_TRADES": 25,
    "ROLLBACK_IF_PF_DROP": 0.20,
    "ROLLBACK_IF_WR_DROP": 0.12,
    "RECENT_PERFORMANCE_WINDOW": 40,
    "DIRECTION_WINDOW": 70,
    "REGIME_WINDOW": 90,
    "DEDUP_WINDOW_SEC": 1400,
    # کول‌داون ارسال تلگرام per symbol+direction (ثانیه) — قبلاً پیش‌فرض ۶۰۰ بود و نصف سیگنال‌ها را می‌کشت
    "SIGNAL_COOLDOWN_SECONDS": 320,
    "REQUIRE_CLOSED_CANDLE": True,
    # تنظیم خودکار نهایی با حداقل نمونه و محافظ rollback
    "SELF_TUNING_ENABLED": True,
    "SELF_TUNING_MIN_SAMPLE": 80,
    "SELF_TUNING_MIN_OOS_SAMPLE": 25,
    "SELF_TUNING_MIN_PF_GAIN": 0.05,
    "SELF_TUNING_MIN_WR_GAIN": 1.5,
    "SELF_TUNING_MAX_DAILY_RISK": 2.0,
    # FIX #8: این کلید قبلاً هیچ‌جا توی CONFIG تعریف نشده بود و فقط با
    # مقدار پیش‌فرض .get(..., True) کار می‌کرد.
    "RISK_INCREASE_REQUIRES_POSITIVE_EDGE": True,
    "FALLBACK_SCAN_AFTER_MINUTES": 10,
    "FALLBACK_CANDIDATES": 10,
    "FALLBACK_MIN_CONFIDENCE": 5.1,
    "RUN_MODE": RUN_MODE,
    "REPORT_MAX_TELEGRAM_CHARS": 3800,
    "HEALTH_MAX_CYCLE_AGE_SEC": 300,
    "HEALTH_MAX_FETCH_LATENCY_MS": 8000,
    "HEALTH_MAX_CYCLE_ERROR_RATE": 0.05,
    "HEALTH_MAX_ANALYSIS_ERROR_RATE": 0.50,
    "AUDIT_ON_START": True,
    "AUDIT_STRICT": False,
    "TELEGRAM_STARTUP_TEST": False,
    "ML_MIN_OOS_SAMPLES": 20,
    "ML_REQUIRE_HOLDOUT": True,
    "ML_MAX_TRAINING_AGE_HOURS": 168,
}

BASE_CONFIG = CONFIG.copy()
# امنیت: توکن تلگرام فقط از Environment خوانده می‌شود؛ هرگز داخل سورس ذخیره نکنید.
CONFIG["TELEGRAM_BOT_TOKEN"] = os.environ.get("TELEGRAM_BOT_TOKEN") or CONFIG.get("TELEGRAM_BOT_TOKEN", "")
CONFIG["TELEGRAM_CHAT_ID"] = os.environ.get("TELEGRAM_CHAT_ID") or CONFIG.get("TELEGRAM_CHAT_ID", "")
CONFIG["TELEGRAM_REPORT_CHAT_ID"] = (
    os.environ.get("TELEGRAM_REPORT_CHAT_ID")
    or CONFIG.get("TELEGRAM_REPORT_CHAT_ID", "")
).strip()
CONFIG_LOCK = threading.Lock()


def _min_confidence_floor() -> float:
    """کف واحد برای MIN_CONFIDENCE تا با PRO_MIN تناقض نداشته باشد."""
    try:
        pro = float(CONFIG.get("PRO_MIN_CONFIDENCE", 5.9))
        return max(5.0, round(pro * 0.97, 2))
    except Exception:
        return 5.7


_MODE_PROFILES = {
    "soft": {"MIN_CONFIDENCE_SCORE": 5.1, "PRO_MIN_CONFIDENCE": 5.4, "PRO_MIN_BACKTEST_WR": 42.0, "PRO_MIN_RR_TP1": 0.70, "MIN_VOLUME_RATIO": 1.05},
    "medium": {"MIN_CONFIDENCE_SCORE": 5.6, "PRO_MIN_CONFIDENCE": 5.9, "PRO_MIN_BACKTEST_WR": 44.0, "PRO_MIN_RR_TP1": 0.80, "MIN_VOLUME_RATIO": 1.10},
    "hard": {"MIN_CONFIDENCE_SCORE": 6.1, "PRO_MIN_CONFIDENCE": 6.3, "PRO_MIN_BACKTEST_WR": 48.0, "PRO_MIN_RR_TP1": 0.95, "MIN_VOLUME_RATIO": 1.20},
}
for _k, _v in _MODE_PROFILES.get(RUN_MODE, _MODE_PROFILES["medium"]).items():
    CONFIG[_k] = _v
CONFIG["RUN_MODE"] = RUN_MODE


# ============================================================================
# بخش 3: سیستم لاگینگ و خطایابی - کامل
# ============================================================================

class DebugLogger:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info_logs = []
        self.debug_logs = []
        self.log_file = PATHS["DEBUG_LOG"]
        self._clear_old_log()
    
    def _clear_old_log(self):
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    lines = f.readlines()
                if len(lines) > 2000:
                    with open(self.log_file, 'w') as f:
                        f.writelines(lines[-1000:])
        except Exception:
            pass
    
    def _write_to_file(self, level: str, message: str):
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                f.write(f"[{timestamp}] [{level}] {message}\n")
        except Exception:
            pass
    
    def _safe_print(self, text: str):
        try:
            print(text)
        except UnicodeEncodeError:
            try:
                enc = sys.stdout.encoding or "utf-8"
                print(text.encode(enc, errors="replace").decode(enc, errors="replace"))
            except Exception:
                pass
        except Exception:
            pass

    def error(self, message: str, show_traceback: bool = True):
        self.errors.append({"time": time.time(), "message": message})
        self._write_to_file("ERROR", message)
        self._safe_print(f"\n❌ خطا: {message}")
        if show_traceback:
            try:
                traceback.print_exc()
            except Exception:
                pass
    
    def warning(self, message: str):
        self.warnings.append({"time": time.time(), "message": message})
        self._write_to_file("WARNING", message)
        self._safe_print(f"⚠️ اخطار: {message}")
    
    def info(self, message: str):
        self.info_logs.append({"time": time.time(), "message": message})
        self._write_to_file("INFO", message)
        self._safe_print(f"ℹ️ {message}")
    
    def debug(self, message: str):
        self.debug_logs.append({"time": time.time(), "message": message})
        self._write_to_file("DEBUG", message)

    def exception(self, message: str):
        # FIX #1: این متد قبلاً وجود نداشت و هر بار صدا زده می‌شد
        # (مثلاً موقع fail شدن آموزش ML) خودش AttributeError می‌داد و
        # دلیل واقعی خطا رو قایم می‌کرد. الان traceback واقعی رو هم لاگ می‌کنه.
        full_message = message
        try:
            tb = traceback.format_exc()
            if tb and tb.strip() != "NoneType: None":
                full_message = f"{message}\n{tb}"
        except Exception:
            pass
        self.errors.append({"time": time.time(), "message": full_message})
        self._write_to_file("ERROR", full_message)
        self._safe_print(f"\n❌ خطا (exception): {message}")
        try:
            traceback.print_exc()
        except Exception:
            pass
    
    def get_report(self) -> dict:
        return {
            "total_errors": len(self.errors),
            "total_warnings": len(self.warnings),
            "total_debug": len(self.debug_logs),
            "last_error": self.errors[-1] if self.errors else None,
            "last_warning": self.warnings[-1] if self.warnings else None,
            "errors": self.errors[-20:],
            "warnings": self.warnings[-20:],
        }
    
    def print_summary(self):
        print("\n" + "="*50)
        print("📊 خلاصه خطاها:")
        print(f"   خطاها: {len(self.errors)}")
        print(f"   اخطارها: {len(self.warnings)}")
        if self.errors:
            print(f"   آخرین خطا: {self.errors[-1]['message']}")
        if self.warnings:
            print(f"   آخرین اخطار: {self.warnings[-1]['message']}")
        print("="*50 + "\n")

logger = DebugLogger()


def _atomic_write_json(path: str, obj) -> bool:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp_path = f"{path}.tmp{os.getpid()}"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        return True
    except Exception as e:
        logger.error(f"خطا در نوشتن اتمیک {path}: {e}")
        return False


# ============================================================================
# بخش 4: تست اتصال به بایننس - کامل
# ============================================================================

def test_binance_connection() -> dict:
    logger.info("🔍 در حال تست اتصال به بایننس...")
    
    result = {
        "success": False,
        "api_status": None,
        "fapi_status": None,
        "symbols_count": 0,
        "usdt_count": 0,
        "sample_data": None,
        "error": None,
        "latency": None
    }
    
    try:
        start_time = time.time()
        resp = requests.get("https://api.binance.com/api/v3/time", timeout=10)
        result["latency"] = round((time.time() - start_time) * 1000, 2)
        result["api_status"] = resp.status_code
        
        if resp.status_code != 200:
            result["error"] = f"API ناموفق: {resp.status_code}"
            logger.error(result["error"])
            return result
        
        resp2 = requests.get("https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=15)
        result["fapi_status"] = resp2.status_code
        
        if resp2.status_code != 200:
            result["error"] = f"FAPI ناموفق: {resp2.status_code}"
            logger.error(result["error"])
            return result
        
        data = resp2.json()
        result["symbols_count"] = len(data)
        
        usdt_symbols = []
        for d in data:
            sym = d.get("symbol", "")
            if sym.endswith("USDT"):
                usdt_symbols.append(d)
        
        result["usdt_count"] = len(usdt_symbols)
        
        if result["usdt_count"] > 0:
            sample = usdt_symbols[0]
            result["sample_data"] = {
                "symbol": sample.get("symbol"),
                "price": sample.get("lastPrice"),
                "change_24h": sample.get("priceChangePercent"),
                "volume": sample.get("volume"),
                "high": sample.get("highPrice"),
                "low": sample.get("lowPrice"),
            }
        
        result["success"] = True
        logger.info("✅ اتصال به بایننس با موفقیت برقرار شد")
        
        print("\n" + "="*60)
        print("📊 نتیجه تست اتصال به بایننس:")
        print(f"   وضعیت: {'✅ موفق' if result['success'] else '❌ ناموفق'}")
        print(f"   API وضعیت: {result['api_status']}")
        print(f"   FAPI وضعیت: {result['fapi_status']}")
        print(f"   تأخیر: {result['latency']}ms")
        print(f"   تعداد کل نمادها: {result['symbols_count']}")
        print(f"   تعداد نمادهای USDT: {result['usdt_count']}")
        if result.get("sample_data"):
            print(f"   نمونه: {result['sample_data']['symbol']} = {result['sample_data']['change_24h']}%")
        print("="*60 + "\n")
        
    except requests.exceptions.Timeout:
        result["error"] = "تایم اوت - اتصال اینترنت خود را بررسی کنید یا از VPN استفاده کنید"
        logger.error(result["error"])
    except requests.exceptions.ConnectionError:
        result["error"] = "خطا در اتصال - ممکن است نیاز به VPN داشته باشید"
        logger.error(result["error"])
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"خطای غیرمنتظره: {e}")
    
    return result


# ============================================================================
# بخش 5: کلاس حافظه عملکرد پیشرفته (PerformanceMemory) - کامل
# ============================================================================

class PerformanceMemory:
    def __init__(self, max_size: int = 200, short_term_size: int = 50):
        self.trades: deque = deque(maxlen=max(2000, max_size))
        self.short_term_trades: deque = deque(maxlen=max(100, short_term_size))
        self.signal_features: deque = deque(maxlen=max_size)
        self.param_performance: dict = {}
        self.performance_history: list = []
        self.last_analysis_time: float = 0
        self.analysis_interval: int = 3600
        self._load_history()
        self._load_archive_into_memory_if_needed()
        logger.debug(f"PerformanceMemory راه‌اندازی شد - ظرفیت: {max_size}")

    def _load_history(self):
        try:
            if os.path.exists(PATHS["PERFORMANCE_REPORT"]):
                with open(PATHS["PERFORMANCE_REPORT"], "r") as f:
                    data = json.load(f)
                    if "trades" in data:
                        for trade in data["trades"][-self.trades.maxlen:]:
                            self.trades.append(trade)
                            self.short_term_trades.append(trade)
                logger.info(f"{len(self.trades)} معامله از تاریخچه بارگذاری شد")
        except Exception as e:
            logger.warning(f"خطا در بارگذاری تاریخچه: {e}")

    def _save_history(self):
        payload = {"trades": list(self.trades), "timestamp": time.time(), "memory_limit": self.trades.maxlen}
        _atomic_write_json(PATHS["PERFORMANCE_REPORT"], payload)
        try:
            archive = []
            if os.path.exists(PATHS["ARCHIVE_FILE"]):
                with open(PATHS["ARCHIVE_FILE"], "r", encoding="utf-8") as f:
                    obj = json.load(f)
                    archive = obj.get("trades", obj if isinstance(obj, list) else [])
            seen = {(str(t.get("timestamp")), t.get("symbol"), t.get("direction"), t.get("which_target")) for t in archive[-100000:]}
            for t in list(self.trades)[-20:]:
                key = (str(t.get("timestamp")), t.get("symbol"), t.get("direction"), t.get("which_target"))
                if key not in seen:
                    archive.append(t); seen.add(key)
            archive = archive[-CONFIG.get("ARCHIVE_MAX_SIZE", 100000):]
            _atomic_write_json(PATHS["ARCHIVE_FILE"], {"trades": archive, "timestamp": time.time()})
        except Exception as e:
            logger.warning(f"Archive save failed: {e}")

    def _load_archive_into_memory_if_needed(self):
        try:
            p = PATHS["ARCHIVE_FILE"]
            if os.path.exists(p) and len(self.trades) < 20:
                with open(p, "r", encoding="utf-8") as f:
                    obj = json.load(f)
                archive = obj.get("trades", obj if isinstance(obj, list) else [])
                for t in archive[-self.trades.maxlen:]:
                    self.trades.append(t)
                    if len(self.short_term_trades) < self.short_term_trades.maxlen:
                        self.short_term_trades.append(t)
                logger.info(f"📚 آرشیو دائمی بارگذاری شد: {len(archive)} معامله")
        except Exception as e:
            logger.warning(f"Archive load failed: {e}")

    def add_trade_result(self, trade_data: dict) -> None:
        try:
            trade_record = {
                "timestamp": time.time(),
                "symbol": trade_data.get("symbol"),
                "direction": trade_data.get("direction"),
                "entry_price": trade_data.get("entry"),
                "exit_price": trade_data.get("exit"),
                "return_pct": trade_data.get("return_pct", 0.0),
                "win": trade_data.get("return_pct", 0.0) > 0,
                "features": trade_data.get("features", {}),
                "signal_confidence": trade_data.get("confidence", 0),
                "holding_time": trade_data.get("holding_time", 0),
                "max_favorable": trade_data.get("max_favorable", 0),
                "max_adverse": trade_data.get("max_adverse", 0),
                "which_target": trade_data.get("which_target"),
                "outcome_label": trade_data.get("outcome_label"),
                "auto_learned": bool(trade_data.get("auto_learned", False)),
                "pre_signal_change_15m": trade_data.get("pre_signal_change_15m"),
                "time_to_result_min": trade_data.get("time_to_result_min"),
                "mfe_pct": trade_data.get("mfe_pct"),
                "mae_pct": trade_data.get("mae_pct"),
                "ml_used": trade_data.get("ml_used", False),
                "ml_probability": trade_data.get("ml_probability"),
                "market_regime": trade_data.get("features", {}).get("market_regime", "UNKNOWN"),
            }
            self.trades.append(trade_record)
            self.short_term_trades.append(trade_record)
            self._save_history()
            self._update_param_stats(trade_record)
            
            win_emoji = "✅" if trade_record["win"] else "❌"
            ml_tag = " 🤖" if trade_record.get("ml_used", False) else ""
            logger.info(f"معامله ثبت شد: {trade_record['symbol']} {trade_record['direction']}{ml_tag} {win_emoji} {trade_record['return_pct']:.2f}%")
            
        except Exception as e:
            logger.error(f"خطا در ثبت معامله: {e}")

    def _update_param_stats(self, trade: dict) -> None:
        try:
            features = trade.get("features", {})
            params = features.get("params_used", {})
            if params and trade.get("win", False):
                for key, value in params.items():
                    if key not in self.param_performance:
                        self.param_performance[key] = {"values": [], "wins": 0, "total": 0}
                    self.param_performance[key]["values"].append(value)
                    self.param_performance[key]["wins"] += 1
                    self.param_performance[key]["total"] += 1
        except Exception as e:
            logger.error(f"خطا در به‌روزرسانی آمار پارامترها: {e}")

    def get_winrate(self, window: Optional[int] = None) -> float:
        try:
            if not self.trades:
                return 0.0
            window = window or len(self.trades)
            recent = list(self.trades)[-window:]
            if not recent:
                return 0.0
            wins = sum(1 for t in recent if t.get("win", False))
            return (wins / len(recent)) * 100.0
        except Exception as e:
            logger.error(f"خطا در محاسبه وین‌ریت: {e}")
            return 0.0

    def get_short_term_winrate(self) -> float:
        try:
            if not self.short_term_trades:
                return 0.0
            wins = sum(1 for t in self.short_term_trades if t.get("win", False))
            return (wins / len(self.short_term_trades)) * 100.0
        except Exception as e:
            logger.error(f"خطا در محاسبه وین‌ریت کوتاه‌مدت: {e}")
            return 0.0

    def get_average_return(self, window: Optional[int] = None) -> float:
        try:
            trades = list(self.trades)
            if window:
                trades = trades[-window:]
            if not trades:
                return 0.0
            returns = [t.get("return_pct", 0) for t in trades]
            return sum(returns) / len(returns)
        except Exception as e:
            logger.error(f"خطا در محاسبه میانگین بازده: {e}")
            return 0.0

    def get_profit_factor(self, window: Optional[int] = None) -> float:
        try:
            trades = list(self.trades)
            if window:
                trades = trades[-window:]
            total_profit = sum(t.get("return_pct", 0) for t in trades if t.get("return_pct", 0) > 0)
            total_loss = abs(sum(t.get("return_pct", 0) for t in trades if t.get("return_pct", 0) < 0))
            if total_loss == 0:
                return total_profit if total_profit > 0 else 1.0
            return total_profit / total_loss
        except Exception as e:
            logger.error(f"خطا در محاسبه فاکتور سود: {e}")
            return 1.0

    def get_sharpe_ratio(self, window: Optional[int] = None, risk_free_rate: float = 0.02) -> float:
        try:
            trades = list(self.trades)
            if window:
                trades = trades[-window:]
            if len(trades) < 2:
                return 0.0
            returns = [t.get("return_pct", 0) for t in trades]
            avg_return = sum(returns) / len(returns)
            std_return = np.std(returns) if len(returns) > 1 else 1.0
            if std_return == 0:
                return 0.0
            annualized_return = avg_return * 252
            annualized_std = std_return * (252 ** 0.5)
            return (annualized_return - risk_free_rate) / annualized_std
        except Exception as e:
            logger.error(f"خطا در محاسبه نسبت شارپ: {e}")
            return 0.0

    def get_calmar_ratio(self, window: Optional[int] = None) -> float:
        try:
            trades = list(self.trades)
            if window:
                trades = trades[-window:]
            if not trades:
                return 0.0
            returns = [t.get("return_pct", 0) for t in trades]
            avg_return = sum(returns) / len(returns)
            cumulative = 0
            peak = 0
            max_drawdown = 0
            for r in returns:
                cumulative += r
                if cumulative > peak:
                    peak = cumulative
                drawdown = (peak - cumulative) if peak > 0 else 0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            if max_drawdown == 0:
                return avg_return * 100 if avg_return > 0 else 0
            return avg_return / max_drawdown
        except Exception as e:
            logger.error(f"خطا در محاسبه نسبت کالمار: {e}")
            return 0.0

    def get_expectancy(self, window: Optional[int] = None) -> float:
        try:
            trades = list(self.trades)
            if window:
                trades = trades[-window:]
            if not trades:
                return 0.0
            avg_win = 0.0
            avg_loss = 0.0
            win_count = 0
            loss_count = 0
            for t in trades:
                ret = t.get("return_pct", 0)
                if ret > 0:
                    avg_win += ret
                    win_count += 1
                elif ret < 0:
                    avg_loss += ret
                    loss_count += 1
            if win_count > 0:
                avg_win /= win_count
            if loss_count > 0:
                avg_loss /= loss_count
            win_rate = win_count / len(trades) if trades else 0
            loss_rate = loss_count / len(trades) if trades else 0
            return (win_rate * avg_win) + (loss_rate * avg_loss)
        except Exception as e:
            logger.error(f"خطا در محاسبه امید ریاضی: {e}")
            return 0.0

    def get_feature_correlation(self, feature_name: str, window: Optional[int] = None) -> float:
        try:
            min_samples = CONFIG.get("MIN_TRADES_FOR_CORRELATION", 10)
            trades_source = list(self.trades)[-window:] if window else list(self.trades)
            if len(trades_source) < min_samples:
                return 0.0
            feature_values = []
            outcomes = []
            for trade in trades_source:
                feat_val = trade.get("features", {}).get(feature_name)
                if feat_val is not None and isinstance(feat_val, (int, float)):
                    feature_values.append(float(feat_val))
                    outcomes.append(1 if trade.get("win", False) else 0)
            if len(feature_values) < min_samples:
                return 0.0
            feature_values = np.array(feature_values)
            outcomes = np.array(outcomes)
            if np.std(feature_values) == 0 or np.std(outcomes) == 0:
                return 0.0
            corr = np.corrcoef(feature_values, outcomes)[0, 1]
            return float(corr) if not np.isnan(corr) else 0.0
        except Exception as e:
            logger.error(f"خطا در محاسبه همبستگی {feature_name}: {e}")
            return 0.0

    def get_feature_importance(self) -> dict:
        try:
            importance = {}
            all_features = set()
            for trade in self.trades:
                all_features.update(trade.get("features", {}).keys())
            for feature in all_features:
                corr = self.get_feature_correlation(feature)
                importance[feature] = abs(corr)
            return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
        except Exception as e:
            logger.error(f"خطا در محاسبه اهمیت ویژگی‌ها: {e}")
            return {}

    def get_best_params_history(self, trades_override: Optional[list] = None) -> dict:
        param_history: dict = {}
        try:
            trades_source = trades_override if trades_override is not None else self.trades
            for trade in trades_source:
                features = trade.get("features", {})
                params = features.get("params_used", {})
                if params and trade.get("win", False):
                    for key, value in params.items():
                        if key not in param_history:
                            param_history[key] = []
                        param_history[key].append(value)
        except Exception as e:
            logger.error(f"خطا در استخراج تاریخچه پارامترها: {e}")
        return param_history

    def get_optimal_params(self, param_name: str) -> Optional[float]:
        try:
            if param_name not in self.param_performance:
                return None
            stats = self.param_performance[param_name]
            if not stats["values"]:
                return None
            return float(np.median(stats["values"]))
        except Exception as e:
            logger.error(f"خطا در دریافت پارامتر بهینه {param_name}: {e}")
            return None

    def get_performance_trend(self, window: int = 20) -> str:
        try:
            if len(self.performance_history) < window:
                return "INSUFFICIENT_DATA"
            recent = self.performance_history[-window:]
            winrates = [p.get("winrate_short", 0) for p in recent]
            if len(winrates) < 3:
                return "STABLE"
            x = list(range(len(winrates)))
            slope = np.polyfit(x, winrates, 1)[0]
            if slope > 0.5:
                return "IMPROVING"
            elif slope < -0.5:
                return "DECLINING"
            else:
                return "STABLE"
        except Exception as e:
            logger.error(f"خطا در تحلیل روند عملکرد: {e}")
            return "UNKNOWN"

    def get_market_regime_performance(self) -> dict:
        regime_performance = {}
        try:
            for trade in self.trades:
                features = trade.get("features", {})
                regime = features.get("market_regime", "UNKNOWN")
                win = trade.get("win", False)
                if regime not in regime_performance:
                    regime_performance[regime] = {"wins": 0, "total": 0}
                regime_performance[regime]["total"] += 1
                if win:
                    regime_performance[regime]["wins"] += 1
            for regime in regime_performance:
                total = regime_performance[regime]["total"]
                wins = regime_performance[regime]["wins"]
                regime_performance[regime]["winrate"] = (wins / total * 100) if total > 0 else 0
        except Exception as e:
            logger.error(f"خطا در محاسبه عملکرد رژیم بازار: {e}")
        return regime_performance

    def get_summary(self) -> dict:
        return {
            "total_trades": len(self.trades),
            "short_term_trades": len(self.short_term_trades),
            "long_term_winrate": self.get_winrate(),
            "short_term_winrate": self.get_short_term_winrate(),
            "profit_factor": self.get_profit_factor(),
            "sharpe_ratio": self.get_sharpe_ratio(),
            "calmar_ratio": self.get_calmar_ratio(),
            "expectancy": self.get_expectancy(),
            "performance_trend": self.get_performance_trend(),
            "best_features": list(self.get_feature_importance().keys())[:5],
            "market_regimes": self.get_market_regime_performance()
        }

    def get_entry_timing_stats(self) -> dict:
        try:
            auto_trades = [t for t in self.trades if t.get("auto_learned") and t.get("pre_signal_change_15m") is not None]
            if len(auto_trades) < 5:
                return {"available": False, "sample_size": len(auto_trades)}
            
            pre_moves = [abs(t["pre_signal_change_15m"]) for t in auto_trades]
            tp1_hits = [t for t in auto_trades if t.get("which_target") == "TP1"]
            sl_hits = [t for t in auto_trades if t.get("which_target") == "SL"]
            timeout_hits = [
                t for t in auto_trades
                if str(t.get("which_target") or t.get("outcome_label") or "").upper() == "TIMEOUT"
            ]
            # زمان تا نتیجه فقط برای TP/SL (نه TIMEOUT که سقف MAX_HOLD است و میانگین را مصنوعی محدود می‌کند)
            times_to_result = [
                t["time_to_result_min"] for t in auto_trades
                if t.get("time_to_result_min")
                and str(t.get("which_target") or t.get("outcome_label") or "").upper() != "TIMEOUT"
            ]
            mfe_on_losses = [t["mfe_pct"] for t in sl_hits if t.get("mfe_pct") is not None]
            mfe_on_timeouts = [t["mfe_pct"] for t in timeout_hits if t.get("mfe_pct") is not None]
            timeout_rate = (len(timeout_hits) / len(auto_trades)) * 100 if auto_trades else 0.0
            
            return {
                "available": True,
                "sample_size": len(auto_trades),
                "avg_pre_signal_move_pct": float(np.mean(pre_moves)) if pre_moves else None,
                "tp1_hit_rate_pct": (len(tp1_hits) / len(auto_trades)) * 100,
                "sl_hit_rate_pct": (len(sl_hits) / len(auto_trades)) * 100,
                "timeout_rate_pct": float(timeout_rate),
                "n_timeout": len(timeout_hits),
                "avg_time_to_result_min": float(np.mean(times_to_result)) if times_to_result else None,
                "avg_mfe_on_losses_pct": float(np.mean(mfe_on_losses)) if mfe_on_losses else None,
                "avg_mfe_on_timeout_pct": float(np.mean(mfe_on_timeouts)) if mfe_on_timeouts else None,
            }
        except Exception as e:
            logger.error(f"خطا در محاسبه آمار زمان‌بندی ورود: {e}")
            return {"available": False, "sample_size": 0}

    def get_ml_performance(self) -> dict:
        """عملکرد معاملات با و بدون ML (+ جداسازی auto_learn)"""
        with_ml = [t for t in self.trades if t.get("ml_used", False)]
        without_ml = [t for t in self.trades if not t.get("ml_used", False)]
        live = [t for t in self.trades if not t.get("auto_learned", False)]
        auto = [t for t in self.trades if t.get("auto_learned", False)]
        
        def calc_stats(trades):
            if not trades:
                return {"trades": 0, "wins": 0, "winrate": 0, "avg_return": 0, "profit_factor": 0}
            wins = sum(1 for t in trades if t.get("win", False))
            returns = [t.get("return_pct", 0) for t in trades]
            total_profit = sum(r for r in returns if r > 0)
            total_loss = abs(sum(r for r in returns if r < 0))
            return {
                "trades": len(trades),
                "wins": wins,
                "winrate": (wins / len(trades) * 100) if trades else 0,
                "avg_return": sum(returns) / len(returns) if returns else 0,
                "profit_factor": total_profit / total_loss if total_loss > 0 else (total_profit if total_profit > 0 else 1.0)
            }
        
        return {
            "with_ml": calc_stats(with_ml),
            "without_ml": calc_stats(without_ml),
            "total_with_ml": len(with_ml),
            "total_without_ml": len(without_ml),
            "live_only": calc_stats(live),
            "auto_learn_only": calc_stats(auto),
        }

    def clear(self) -> None:
        self.trades.clear()
        self.short_term_trades.clear()
        self.signal_features.clear()
        self.param_performance.clear()
        self.performance_history.clear()
        logger.info("حافظه عملکرد پاک شد")


# ============================================================================
# بخش 6: کلاس بهینه‌ساز پارامتر تطبیقی - کامل
# ============================================================================

class AdaptiveParameterOptimizer:
    def __init__(self, memory: PerformanceMemory):
        self.memory = memory
        self.last_update_time: int = 0
        self.learning_rate: float = 0.15
        self.momentum: float = 0.6
        self.previous_updates: dict = {}
        self.performance_history: list = []
        self.optimization_history: list = []
        self.param_constraints = {
            "ATR_MULT_SL": (0.8, 3.0),
            "EMA_SHORT": (5, 25),
            "EMA_MED": (20, 80),
            "RISK_PERCENT": (0.2, 2.5),
            "PUMP_THRESHOLD": (0.6, 2.5),
            "DUMP_THRESHOLD": (-2.5, -0.6),
            # کف پویا در apply/_clamp_min_confidence اعمال می‌شود (PRO_MIN*0.97)
            "MIN_CONFIDENCE_SCORE": (5.0, 6.6),
            "MAX_HOLD_MINUTES": (25, 90),
            "ADX_TREND_MIN": (10, 30),
            "RSI_PERIOD": (8, 20),
            "MIN_VOLUME_RATIO": (1.0, 2.5),
        }
        self.optimized_params: dict = self._load_saved_params()
        logger.debug("AdaptiveParameterOptimizer راه‌اندازی شد")

    def _load_saved_params(self) -> dict:
        try:
            if os.path.exists(PATHS["OPTIMIZED_PARAMS_FILE"]):
                with open(PATHS["OPTIMIZED_PARAMS_FILE"], "r") as f:
                    loaded = json.load(f)
                    validated = {}
                    for key, value in loaded.items():
                        if key in self.param_constraints:
                            min_val, max_val = self.param_constraints[key]
                            if isinstance(value, (int, float)):
                                clamped = max(min_val, min(max_val, value))
                                validated[key] = int(clamped) if isinstance(value, int) else clamped
                        else:
                            validated[key] = value
                    logger.info(f"پارامترهای ذخیره شده بارگذاری شد: {validated}")
                    return validated
        except Exception as e:
            logger.warning(f"خطا در بارگذاری پارامترها: {e}")
        return self._get_default_params()

    def _get_default_params(self) -> dict:
        return {
            "ATR_MULT_SL": CONFIG.get("ATR_MULT_SL", 1.4),
            "EMA_SHORT": CONFIG.get("EMA_SHORT", 10),
            "EMA_MED": CONFIG.get("EMA_MED", 30),
            "RISK_MULTIPLIER": 1.0,
            "LEARNING_RATE": 0.15,
            "PUMP_THRESHOLD": CONFIG.get("PUMP_THRESHOLD", 1.2),
            "DUMP_THRESHOLD": CONFIG.get("DUMP_THRESHOLD", -1.2),
            "MIN_CONFIDENCE_SCORE": CONFIG.get("MIN_CONFIDENCE_SCORE", 5.5),
            "MAX_HOLD_MINUTES": CONFIG.get("MAX_HOLD_MINUTES", 45),
            "ADX_TREND_MIN": CONFIG.get("ADX_TREND_MIN", 16),
            "RSI_PERIOD": CONFIG.get("RSI_PERIOD", 10),
            "MIN_VOLUME_RATIO": CONFIG.get("MIN_VOLUME_RATIO", 1.2),
        }

    def _save_params(self) -> None:
        if _atomic_write_json(PATHS["OPTIMIZED_PARAMS_FILE"], self.optimized_params):
            logger.debug("پارامترهای بهینه شده ذخیره شد")

    def _save_optimization_history(self, change: dict) -> None:
        try:
            self.optimization_history.append(change)
            if len(self.optimization_history) > 500:
                self.optimization_history = self.optimization_history[-500:]
            _atomic_write_json(PATHS["PARAMETER_OPTIMIZATION_HISTORY"], self.optimization_history)
        except Exception as e:
            logger.error(f"خطا در ذخیره تاریخچه بهینه‌سازی: {e}")

    def optimize(self, force: bool = False) -> dict:
        try:
            current_hour = int(time.time() / 3600)
            
            if not force and (current_hour - self.last_update_time) < CONFIG["ADAPTIVE_UPDATE_INTERVAL"]:
                logger.debug("زمان کافی برای بهینه‌سازی مجدد نگذشته است")
                return self.optimized_params
            
            if len(self.memory.trades) < CONFIG["MIN_TRADES_FOR_LEARNING"]:
                logger.info(f"داده کافی برای بهینه‌سازی وجود ندارد (حداقل {CONFIG['MIN_TRADES_FOR_LEARNING']} معامله)")
                return self.optimized_params
            
            logger.info("🔄 شروع بهینه‌سازی خودکار پارامترها...")
            old_params = self.optimized_params.copy()

            trades_sorted = sorted(self.memory.trades, key=lambda t: t.get("timestamp", 0))
            split_idx = int(len(trades_sorted) * CONFIG.get("WF_TRAIN_RATIO", 0.7))
            train_trades = trades_sorted[:split_idx]
            test_trades = trades_sorted[split_idx:]
            min_wf_test = CONFIG.get("MIN_WF_TEST_TRADES", 6)
            wf_active = len(test_trades) >= min_wf_test and len(train_trades) >= min_wf_test

            if wf_active:
                train_wr = (sum(1 for t in train_trades if t.get("win")) / len(train_trades)) * 100.0
                test_wr = (sum(1 for t in test_trades if t.get("win")) / len(test_trades)) * 100.0
                if test_wr < train_wr - 12:
                    logger.warning(f"⚠️ Walk-forward: تست {test_wr:.1f}% < train {train_wr:.1f}% - رد بهینه‌سازی")
                    self.last_update_time = current_hour
                    return self.optimized_params
            
            param_history = self.memory.get_best_params_history(train_trades if wf_active else None)
            changes_made = []
            
            # ============================================================
            # 1. بهینه‌سازی ATR_MULT_SL
            # ============================================================
            if "ATR_MULT_SL" in param_history and len(param_history["ATR_MULT_SL"]) > 5:
                optimal_atr = np.median(param_history["ATR_MULT_SL"])
                old_val = self.optimized_params.get("ATR_MULT_SL", CONFIG["ATR_MULT_SL"])
                new_val = self._apply_learning_rate("ATR_MULT_SL", optimal_atr)
                if abs(new_val - old_val) > 0.05:
                    self.optimized_params["ATR_MULT_SL"] = new_val
                    changes_made.append({
                        "parameter": "ATR_MULT_SL",
                        "old": old_val,
                        "new": new_val,
                        "reason": f"بهینه از {len(param_history['ATR_MULT_SL'])} معامله موفق"
                    })
                    logger.info(f"   📊 ATR_MULT_SL: {old_val:.2f} → {new_val:.2f}")
            
            # ============================================================
            # 2. بهینه‌سازی EMA_SHORT
            # ============================================================
            if "EMA_SHORT" in param_history and len(param_history["EMA_SHORT"]) > 5:
                optimal_ema_s = int(np.median(param_history["EMA_SHORT"]))
                old_val = self.optimized_params.get("EMA_SHORT", CONFIG["EMA_SHORT"])
                new_val = self._apply_learning_rate("EMA_SHORT", optimal_ema_s, is_int=True)
                if new_val != old_val:
                    self.optimized_params["EMA_SHORT"] = new_val
                    changes_made.append({
                        "parameter": "EMA_SHORT",
                        "old": old_val,
                        "new": new_val,
                        "reason": f"بهینه از {len(param_history['EMA_SHORT'])} معامله موفق"
                    })
                    logger.info(f"   📊 EMA_SHORT: {old_val} → {new_val}")
            
            # ============================================================
            # 3. بهینه‌سازی EMA_MED
            # ============================================================
            if "EMA_MED" in param_history and len(param_history["EMA_MED"]) > 5:
                optimal_ema_m = int(np.median(param_history["EMA_MED"]))
                old_val = self.optimized_params.get("EMA_MED", CONFIG["EMA_MED"])
                new_val = self._apply_learning_rate("EMA_MED", optimal_ema_m, is_int=True)
                if new_val != old_val:
                    self.optimized_params["EMA_MED"] = new_val
                    changes_made.append({
                        "parameter": "EMA_MED",
                        "old": old_val,
                        "new": new_val,
                        "reason": f"بهینه از {len(param_history['EMA_MED'])} معامله موفق"
                    })
                    logger.info(f"   📊 EMA_MED: {old_val} → {new_val}")
            
            # ============================================================
            # 4. بهینه‌سازی آستانه‌ها بر اساس عملکرد
            # ============================================================
            current_wr = self.memory.get_winrate(30)
            current_pf = self.memory.get_profit_factor(30)
            
            # تنظیم MIN_CONFIDENCE_SCORE — هرگز زیر کف PRO (PRO_MIN*0.97) نرود
            conf_tuned_this_cycle = False
            conf_floor = _min_confidence_floor()
            if current_wr > 55 and current_pf > 1.2:
                old_val = self.optimized_params.get("MIN_CONFIDENCE_SCORE", CONFIG["MIN_CONFIDENCE_SCORE"])
                new_val = max(conf_floor, old_val - 0.10)
                if abs(new_val - old_val) >= 0.05:
                    self.optimized_params["MIN_CONFIDENCE_SCORE"] = new_val
                    conf_tuned_this_cycle = True
                    changes_made.append({
                        "parameter": "MIN_CONFIDENCE_SCORE",
                        "old": old_val,
                        "new": new_val,
                        "reason": f"عملکرد خوب (WR={current_wr:.0f}%) - کاهش آستانه (کف={conf_floor:.2f})"
                    })
                    logger.info(f"   📊 MIN_CONFIDENCE_SCORE: {old_val:.1f} → {new_val:.1f}")
            elif current_wr < 45 and current_pf < 0.9:
                old_val = self.optimized_params.get("MIN_CONFIDENCE_SCORE", CONFIG["MIN_CONFIDENCE_SCORE"])
                new_val = min(6.6, old_val + 0.10)
                if abs(new_val - old_val) >= 0.05:
                    self.optimized_params["MIN_CONFIDENCE_SCORE"] = new_val
                    conf_tuned_this_cycle = True
                    changes_made.append({
                        "parameter": "MIN_CONFIDENCE_SCORE",
                        "old": old_val,
                        "new": new_val,
                        "reason": f"عملکرد ضعیف (WR={current_wr:.0f}%) - افزایش آستانه"
                    })
                    logger.info(f"   📊 MIN_CONFIDENCE_SCORE: {old_val:.1f} → {new_val:.1f}")
            
            # ============================================================
            # 5. بهینه‌سازی MAX_HOLD_MINUTES
            # معیار غیر self-capped: نرخ TIMEOUT + MFE روی TIMEOUT
            # (avg_time با TIMEOUT سقف MAX_HOLD می‌شد و افزایش را غیرممکن می‌کرد)
            # ============================================================
            timing = self.memory.get_entry_timing_stats()
            if timing.get("available") and timing.get("sample_size", 0) >= 15:
                old_val = float(self.optimized_params.get("MAX_HOLD_MINUTES", CONFIG.get("MAX_HOLD_MINUTES", 45)))
                timeout_rate = float(timing.get("timeout_rate_pct") or 0.0)
                avg_mfe_to = timing.get("avg_mfe_on_timeout_pct")
                avg_time = timing.get("avg_time_to_result_min")  # فقط TP/SL
                new_val = old_val
                reason = None

                # TIMEOUT زیاد + حرکت مطلوب بعد از پنجره → hold را زیاد کن
                if timeout_rate >= 45 and old_val < 90:
                    step = 15 if timeout_rate >= 60 else 10
                    # اگر MFE روی TIMEOUT مثبت باشد، سیگنال هنوز edge داشته
                    if avg_mfe_to is None or avg_mfe_to >= 0.3:
                        new_val = min(90, old_val + step)
                        reason = (
                            f"TIMEOUT={timeout_rate:.0f}%"
                            + (f" | MFE_TO={avg_mfe_to:.2f}%" if avg_mfe_to is not None else "")
                            + " - افزایش hold"
                        )
                # TIMEOUT کم و نتیجه سریع (بدون TIMEOUT در میانگین) → کمی کم کن
                elif timeout_rate <= 25 and avg_time is not None and avg_time < 20 and old_val > 30:
                    new_val = max(25, old_val - 5)
                    reason = f"TIMEOUT={timeout_rate:.0f}% | avg_TP/SL={avg_time:.0f}m - کاهش hold"

                if new_val != old_val and reason:
                    self.optimized_params["MAX_HOLD_MINUTES"] = int(new_val)
                    changes_made.append({
                        "parameter": "MAX_HOLD_MINUTES",
                        "old": old_val,
                        "new": int(new_val),
                        "reason": reason,
                    })
                    logger.info(f"   📊 MAX_HOLD_MINUTES: {old_val} → {int(new_val)} | {reason}")
            
            # ============================================================
            # 6. بهینه‌سازی ADX_TREND_MIN
            # ============================================================
            if "adx_strength" in param_history and len(param_history.get("adx_strength", [])) > 5:
                old_val = self.optimized_params.get("ADX_TREND_MIN", CONFIG["ADX_TREND_MIN"])
                median_adx = np.median([t.get("features", {}).get("adx_strength", 0) for t in train_trades if t.get("win")])
                if median_adx > 0:
                    new_val = max(10, min(30, int(median_adx * 15)))
                    if new_val != old_val:
                        self.optimized_params["ADX_TREND_MIN"] = new_val
                        changes_made.append({
                            "parameter": "ADX_TREND_MIN",
                            "old": old_val,
                            "new": new_val,
                            "reason": f"بهینه از داده‌های موفق"
                        })
                        logger.info(f"   📊 ADX_TREND_MIN: {old_val} → {new_val}")
            
            # ============================================================
            # 7. بهینه‌سازی RSI_PERIOD
            # ============================================================
            if "rsi_momentum" in param_history and len(param_history.get("rsi_momentum", [])) > 5:
                old_val = self.optimized_params.get("RSI_PERIOD", CONFIG["RSI_PERIOD"])
                old_periods = self.optimized_params.get("RSI_PERIOD", CONFIG["RSI_PERIOD"])
                # تحلیل همبستگی RSI با موفقیت
                corr = self.memory.get_feature_correlation("rsi_momentum", window=50)
                if corr > 0.15 and old_periods > 8:
                    new_val = max(8, old_periods - 1)
                    if new_val != old_periods:
                        self.optimized_params["RSI_PERIOD"] = new_val
                        changes_made.append({
                            "parameter": "RSI_PERIOD",
                            "old": old_periods,
                            "new": new_val,
                            "reason": f"همبستگی مثبت RSI ({corr:.2f}) - کاهش دوره"
                        })
                        logger.info(f"   📊 RSI_PERIOD: {old_periods} → {new_val}")
                elif corr < -0.05 and old_periods < 18:
                    new_val = min(20, old_periods + 1)
                    if new_val != old_periods:
                        self.optimized_params["RSI_PERIOD"] = new_val
                        changes_made.append({
                            "parameter": "RSI_PERIOD",
                            "old": old_periods,
                            "new": new_val,
                            "reason": f"همبستگی منفی RSI ({corr:.2f}) - افزایش دوره"
                        })
                        logger.info(f"   📊 RSI_PERIOD: {old_periods} → {new_val}")
            
            # ============================================================
            # 8. بهینه‌سازی فیلتر حجم
            # ============================================================
            if "MIN_VOLUME_RATIO" in param_history and len(param_history.get("MIN_VOLUME_RATIO", [])) >= 8:
                vals = [float(v) for v in param_history["MIN_VOLUME_RATIO"] if isinstance(v, (int, float))]
                if vals:
                    old_val = float(self.optimized_params.get("MIN_VOLUME_RATIO", CONFIG.get("MIN_VOLUME_RATIO", 1.2)))
                    target = float(np.median(vals))
                    new_val = self._apply_learning_rate("MIN_VOLUME_RATIO", target)
                    if abs(new_val - old_val) >= 0.03:
                        self.optimized_params["MIN_VOLUME_RATIO"] = round(float(new_val), 2)
                        changes_made.append({
                            "parameter": "MIN_VOLUME_RATIO",
                            "old": old_val,
                            "new": round(float(new_val), 2),
                            "reason": f"میانه مقدار فیلتر در {len(vals)} معامله موفق"
                        })

            # ============================================================
            # 9. کنترل ضد-گرسنگی سیگنال
            # فقط اگر در همین سیکل آستانه را به‌خاطر WR بالا نبرده باشیم
            # و ارزیابی‌های کافی بدون قبول وجود داشته باشد (گام کوچک).
            # ============================================================
            if CONFIG.get("SELF_TUNING_ENABLED", True) and not conf_tuned_this_cycle:
                try:
                    snap = _diag_snapshot()
                    gate = snap.get("window") or snap.get("hourly", {})
                    evaluated = sum(int(v.get("count", 0)) for v in gate.values() if v.get("stage") == "GATE_EVALUATED")
                    accepted = sum(int(v.get("count", 0)) for v in gate.values() if v.get("stage") == "ACCEPTED")
                    tech_ok = sum(int(v.get("count", 0)) for v in gate.values() if v.get("stage") == "TECHNICAL_ACCEPTED")
                    # اگر تکنیکال قبول شده ولی final صفر است، مشکل اغلب PRO gate است نه conf base
                    if evaluated >= 40 and accepted == 0 and tech_ok < 3:
                        old_val = float(self.optimized_params.get("MIN_CONFIDENCE_SCORE", CONFIG["MIN_CONFIDENCE_SCORE"]))
                        new_val = max(_min_confidence_floor(), old_val - 0.08)
                        if abs(new_val - old_val) >= 0.05:
                            self.optimized_params["MIN_CONFIDENCE_SCORE"] = new_val
                            changes_made.append({
                                "parameter": "MIN_CONFIDENCE_SCORE",
                                "old": old_val,
                                "new": new_val,
                                "reason": f"Signal starvation: {evaluated} gate eval, 0 accept, tech_ok={tech_ok}"
                            })
                except Exception:
                    pass

            self._optimize_risk_parameters()
            
            # ============================================================
            # ثبت تغییرات
            # ============================================================
            if changes_made:
                for change in changes_made:
                    change["timestamp"] = time.time()
                    change["winrate"] = self.memory.get_winrate()
                    change["pf"] = self.memory.get_profit_factor()
                    self._save_optimization_history(change)
            
            self.last_update_time = current_hour
            self._save_params()
            # اعمال فوری به CONFIG تا MAX_HOLD و بقیه از همین سیکل اثر کنند
            try:
                self.apply_optimized_params()
            except Exception as apply_err:
                logger.warning(f"apply_optimized_params after optimize failed: {apply_err}")
            
            self.performance_history.append({
                "timestamp": current_hour,
                "params": self.optimized_params.copy(),
                "winrate": self.memory.get_winrate(20),
            })
            
            if len(self.performance_history) > 50:
                self.performance_history = self.performance_history[-50:]
            
            if changes_made:
                logger.info(f"✅ {len(changes_made)} پارامتر بهینه شد")
            
            return self.optimized_params
            
        except Exception as e:
            logger.error(f"خطا در بهینه‌سازی: {e}")
            return self.optimized_params

    def _apply_learning_rate(self, param_name: str, target_value, is_int: bool = False):
        try:
            current = self.optimized_params.get(param_name)
            if current is None:
                return target_value
            
            change = target_value - current
            
            if param_name in self.previous_updates:
                change = change * (1 - self.momentum) + self.previous_updates[param_name] * self.momentum
            
            self.previous_updates[param_name] = change
            new_value = current + change * self.learning_rate
            
            if param_name in self.param_constraints:
                min_val, max_val = self.param_constraints[param_name]
                new_value = max(min_val, min(max_val, new_value))
            
            return int(new_value) if is_int else new_value
        except Exception as e:
            logger.error(f"خطا در اعمال نرخ یادگیری: {e}")
            return target_value

    def _optimize_risk_parameters(self) -> None:
        try:
            winrate = self.memory.get_winrate(20)
            profit_factor = self.memory.get_profit_factor(20)
            sharpe = self.memory.get_sharpe_ratio(20)
            
            confidence_score = min(1.0, max(0.0, (winrate - 44) / 35))
            
            expectancy = self.memory.get_expectancy(20)
            # قفل حرفه‌ای ریسک: تا وقتی Edge مثبت و پایدار ثابت نشده، افزایش ریسک ممنوع است.
            if CONFIG.get("RISK_INCREASE_REQUIRES_POSITIVE_EDGE", True) and (profit_factor < 1.0 or expectancy <= 0.0 or sharpe <= 0.0):
                multiplier = 0.50
            elif winrate > 55 and profit_factor > 1.2 and sharpe > 0.5 and expectancy > 0:
                multiplier = min(1.15, 1.0 + (winrate - 55) / 140 + (profit_factor - 1.2) / 8)
            elif winrate < 45 or profit_factor < 0.90 or expectancy < 0:
                multiplier = max(0.35, 0.6 * confidence_score)
            else:
                multiplier = 0.75
            
            short_term_winrate = self.memory.get_short_term_winrate()
            if short_term_winrate < 45:
                multiplier *= 0.7
            elif short_term_winrate > 65:
                multiplier *= 1.3
            
            multiplier = max(0.3, min(1.8, multiplier))
            self.optimized_params["RISK_MULTIPLIER"] = multiplier
            
            # FIX #7: قبلاً base_risk از CONFIG زنده (که خودش نتیجه‌ی همین محاسبه
            # توی سیکل قبلی بود) خونده می‌شد، یعنی هر بار multiplier روی نتیجه‌ی
            # قبلی ضرب می‌شد (compounding) نه روی baseline ثابت.
            base_risk = BASE_CONFIG.get("RISK_PERCENT", 0.6)
            new_risk = base_risk * multiplier
            new_risk = max(CONFIG.get("MIN_RISK_PERCENT", 0.2), min(CONFIG.get("MAX_RISK_PERCENT", 2.5), new_risk))
            self.optimized_params["RISK_PERCENT"] = new_risk
            
            logger.info(f"   📊 ریسک جدید: {new_risk:.2f}% (ضریب: {multiplier:.2f})")
            
        except Exception as e:
            logger.error(f"خطا در بهینه‌سازی ریسک: {e}")

    def apply_optimized_params(self) -> None:
        try:
            if not self.optimized_params:
                return
            
            with CONFIG_LOCK:
                for key in ["ATR_MULT_SL", "EMA_SHORT", "EMA_MED", "RISK_PERCENT", 
                           "PUMP_THRESHOLD", "DUMP_THRESHOLD", "MIN_CONFIDENCE_SCORE",
                           "MAX_HOLD_MINUTES", "ADX_TREND_MIN", "RSI_PERIOD", "MIN_VOLUME_RATIO"]:
                    if key in self.optimized_params:
                        CONFIG[key] = self.optimized_params[key]
                # قفل کف confidence نسبت به PRO gate
                floor = _min_confidence_floor()
                if float(CONFIG.get("MIN_CONFIDENCE_SCORE", 5.6)) < floor:
                    CONFIG["MIN_CONFIDENCE_SCORE"] = floor
                    self.optimized_params["MIN_CONFIDENCE_SCORE"] = floor
            
            logger.info("✅ پارامترهای بهینه شده اعمال شدند")
            
        except Exception as e:
            logger.error(f"خطا در اعمال پارامترهای بهینه شده: {e}")

    def optimize_regime_thresholds(self) -> None:
        try:
            min_samples = CONFIG.get("REGIME_MIN_TRADES_FOR_ADJUST", 20)
            max_adjustment = CONFIG.get("REGIME_MAX_ADJUSTMENT", 0.50)
            step = CONFIG.get("REGIME_ADJUSTMENT_STEP", 0.05)
            sensitivity = CONFIG.get("REGIME_ADJUSTMENT_SENSITIVITY", 0.10)
            
            regime_perf = self.memory.get_market_regime_performance()
            overall_winrate = self.memory.get_winrate()
            if not overall_winrate:
                return
            
            current_adj = CONFIG.get("REGIME_CONFIDENCE_ADJUSTMENT", {}).copy()
            changed = False
            adjustments = []
            
            for regime, stats in regime_perf.items():
                # FIX #2: قبلاً RANGING از حلقه‌ی self-tuning حذف شده بود و
                # ضریب اطمینانش هیچ‌وقت آپدیت نمی‌شد. الان مثل بقیه‌ی رژیم‌ها یاد می‌گیره.
                total = stats.get("total", 0)
                if total < min_samples:
                    continue
                
                regime_wr = stats.get("winrate", 0.0)
                gap = overall_winrate - regime_wr
                target_adj = max(0.0, min(max_adjustment, gap * sensitivity))
                current = current_adj.get(regime, 0.0)
                
                if abs(target_adj - current) < 0.03:
                    continue
                
                new_adj = current + step if target_adj > current else current - step
                new_adj = max(0.0, min(max_adjustment, new_adj))
                if abs(target_adj - current) < step:
                    new_adj = target_adj
                
                current_adj[regime] = round(new_adj, 2)
                changed = True
                adjustments.append({
                    "regime": regime,
                    "old": current,
                    "new": new_adj,
                    "reason": f"WR={regime_wr:.0f}% vs کل={overall_winrate:.0f}%"
                })
                logger.info(f"🎯 آستانه رژیم {regime}: {current:.2f} → {new_adj:.2f}")
            
            if changed:
                with CONFIG_LOCK:
                    CONFIG["REGIME_CONFIDENCE_ADJUSTMENT"] = current_adj
                    
                # ثبت تغییرات
                for adj in adjustments:
                    adj["timestamp"] = time.time()
                    self._save_optimization_history(adj)
                    
        except Exception as e:
            logger.error(f"خطا در تنظیم خودکار آستانه‌ی رژیم: {e}")


# ============================================================================
# بخش 7: کلاس یادگیری وزن ویژگی (FeatureWeightLearner) - کامل
# ============================================================================

class FeatureWeightLearner:
    def __init__(self, memory: PerformanceMemory):
        self.memory = memory
        self.feature_weights: dict = {
            "trend_alignment": 1.0,
            "volume_confirmation": 1.0,
            "multi_tf_alignment": 1.0,
            "price_action_quality": 1.0,
            "backtest_winrate": 1.0,
            "rsi_momentum": 1.0,
            "volatility_regime": 1.0,
            "adx_strength": 1.0,
            "cci_signal": 1.0,
            "williams_signal": 1.0,
            "mfi_signal": 1.0,
            "supertrend_alignment": 1.0,
        }
        self.short_term_weights: dict = self.feature_weights.copy()
        self.weights_history: list = []
        self.learning_rate: float = 0.08
        self.momentum: float = 0.35
        self.weight_changes: dict = {}
        self.correlation_threshold_positive: float = 0.08
        self.correlation_threshold_negative: float = -0.05
        self._load_weights()
        logger.debug("FeatureWeightLearner راه‌اندازی شد")

    def _load_weights(self):
        try:
            if os.path.exists(PATHS["FEATURE_WEIGHTS_FILE"]):
                with open(PATHS["FEATURE_WEIGHTS_FILE"], "r") as f:
                    saved = json.load(f)
                if isinstance(saved, dict) and saved.get("version") == 8 and isinstance(saved.get("weights"), dict):
                    for key, value in saved["weights"].items():
                        if key in self.feature_weights and isinstance(value, (int, float)):
                            self.feature_weights[key] = max(0.30, min(1.70, float(value)))
                    logger.debug(f"وزن‌های ویژگی نسخه 8 بارگذاری شد")
                else:
                    logger.info("🧠 وزن‌های قدیمی شناسایی شد؛ وزن‌ها روی 1.0 reset شدند")
        except Exception as e:
            logger.warning(f"خطا در بارگذاری وزن ویژگی‌ها: {e}")

    def _save_weights(self):
        try:
            _atomic_write_json(PATHS["FEATURE_WEIGHTS_FILE"], {"version": 8, "weights": self.feature_weights})
            self.weights_history.append({
                "timestamp": time.time(),
                "weights": self.feature_weights.copy()
            })
            if len(self.weights_history) > 100:
                self.weights_history = self.weights_history[-100:]
        except Exception as e:
            logger.error(f"خطا در ذخیره وزن ویژگی‌ها: {e}")

    def update_weights(self) -> None:
        try:
            if len(self.memory.trades) < CONFIG.get("MIN_TRADES_FOR_CORRELATION", 10):
                return
            
            logger.info("🎓 شروع به‌روزرسانی وزن ویژگی‌ها...")
            old_weights = self.feature_weights.copy()
            window = CONFIG.get("LEARNING_WINDOW", 70)
            
            for feature_name in list(self.feature_weights.keys()):
                correlation = self.memory.get_feature_correlation(feature_name, window=window)
                current = self.feature_weights[feature_name]

                if correlation > self.correlation_threshold_positive:
                    raw_delta = self.learning_rate * correlation
                elif correlation < self.correlation_threshold_negative:
                    raw_delta = self.learning_rate * correlation
                else:
                    raw_delta = 0.0

                max_step = 0.04 * max(0.5, current)
                raw_delta = max(-max_step, min(max_step, raw_delta))
                new_weight = current + raw_delta
                new_weight = max(0.30, min(1.70, new_weight))

                new_weight = current * (1.0 - self.momentum) + new_weight * self.momentum
                self.weight_changes[feature_name] = new_weight - current
                self.feature_weights[feature_name] = new_weight
                
                status = "📈" if new_weight > old_weights[feature_name] else "📉" if new_weight < old_weights[feature_name] else "➖"
                logger.info(f"   {status} {feature_name}: {old_weights[feature_name]:.2f} → {new_weight:.2f} (corr: {correlation:.2f})")
            
            self._save_weights()
            
            # ثبت تغییرات
            changes = []
            for key in self.feature_weights:
                if key in old_weights:
                    change = self.feature_weights[key] - old_weights[key]
                    if abs(change) > 0.01:
                        changes.append({
                            "feature": key,
                            "old": old_weights[key],
                            "new": self.feature_weights[key],
                            "change": change,
                            "timestamp": time.time()
                        })
            
            if changes:
                _atomic_write_json(os.path.join(DATA_DIR, "feature_weight_changes.json"), changes[-50:])
            
            logger.info(f"✅ وزن ویژگی‌ها به‌روزرسانی شد - {len(changes)} تغییر")
            
        except Exception as e:
            logger.error(f"خطا در به‌روزرسانی وزن ویژگی‌ها: {e}")

    def _get_current_sharpen_exponent(self) -> float:
        n = len(self.memory.trades)
        min_t = CONFIG.get("WEIGHT_SHARPEN_MIN_TRADES", 50)
        full_t = CONFIG.get("WEIGHT_SHARPEN_FULL_TRADES", 250)
        max_exp = min(CONFIG.get("WEIGHT_SHARPEN_EXPONENT_MAX", 1.5), 1.25)
        if n < min_t:
            return 1.0
        if n >= full_t:
            return max_exp
        progress = (n - min_t) / max(1, (full_t - min_t))
        return 1.0 + progress * (max_exp - 1.0)

    def calculate_weighted_confidence(self, signal_features: dict) -> float:
        try:
            total_score = 0.0
            total_weight = 0.0
            sharpen_exp = self._get_current_sharpen_exponent()
            
            for feature_name, weight in self.feature_weights.items():
                feature_value = float(signal_features.get(feature_name, 0.0))
                effective_weight = weight ** sharpen_exp
                
                if weight > 1.5:
                    feature_value = min(1.0, feature_value * 1.05)
                elif weight < 0.5:
                    feature_value = max(0.0, feature_value * 0.95)
                
                total_score += feature_value * effective_weight
                total_weight += effective_weight
            
            if total_weight == 0:
                return 0.0
            
            return (total_score / total_weight) * 10.0
            
        except Exception as e:
            logger.error(f"خطا در محاسبه اطمینان وزنی: {e}")
            return 5.0


# ============================================================================
# بخش 8: مدل یادگیری ماشین (MLConfidenceModel) - نسخه 8
# ============================================================================

class MLConfidenceModel:
    FEATURE_NAMES = [
        "trend_alignment", "volume_confirmation", "multi_tf_alignment",
        "price_action_quality", "backtest_winrate", "rsi_momentum",
        "volatility_regime", "adx_strength", "cci_signal", "williams_signal",
        "mfi_signal", "supertrend_alignment",
    ]
    MODEL_VERSION = int(CONFIG.get("ML_MODEL_VERSION", 9))

    def __init__(self, memory: "PerformanceMemory"):
        self.memory = memory
        self.model = None
        self.is_trained = False
        self.trained_on_n_trades = 0
        self.last_test_auc = None
        self.last_test_accuracy = None
        self.last_brier = None
        self.wf_auc_mean = None
        self.wf_auc_std = None
        self.wf_auc_sem = None
        self.wf_folds = 0
        self.selected_model_name = None
        self.last_train_time = 0.0
        self.model_version = self.MODEL_VERSION
        self.dataset_n = 0
        self.class_balance = None
        self.health = "INIT"
        self.performance_history = []
        self.training_history = []
        self._load_training_history()
        if SKLEARN_AVAILABLE:
            self._load_model()

    def _load_training_history(self):
        try:
            p = os.path.join(DATA_DIR, "ml_training_history.json")
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self.training_history = data[-100:]
        except Exception as e:
            logger.debug(f"ML training history load failed: {e}")

    def _backup_model_file(self):
        try:
            p = PATHS["ML_MODEL_FILE"]
            if os.path.exists(p):
                shutil.copy2(p, p + ".bak")
        except Exception as e:
            logger.debug(f"ML backup failed: {e}")

    def _quarantine_corrupt_model(self):
        try:
            p = PATHS["ML_MODEL_FILE"]
            if os.path.exists(p):
                bad = p + f".bad.{int(time.time())}"
                os.replace(p, bad)
                logger.warning(f"🤖 ML model quarantined: {bad}")
        except Exception as e:
            logger.debug(f"ML quarantine failed: {e}")

    def _load_model(self):
        try:
            p = PATHS["ML_MODEL_FILE"]
            if not os.path.exists(p):
                return
            saved = joblib.load(p)
            if saved.get("model_version") != self.MODEL_VERSION:
                logger.info("🤖 ML model version changed; rebuilding automatically")
                return
            model = saved.get("model")
            if model is None:
                return
            self.model = model
            self.trained_on_n_trades = int(saved.get("trained_on_n_trades", 0))
            self.dataset_n = int(saved.get("dataset_n", self.trained_on_n_trades))
            self.last_test_auc = saved.get("last_test_auc")
            self.last_test_accuracy = saved.get("last_test_accuracy")
            self.last_brier = saved.get("last_brier")
            self.wf_auc_mean = saved.get("wf_auc_mean")
            self.wf_auc_std = saved.get("wf_auc_std")
            self.wf_folds = int(saved.get("wf_folds", 0))
            saved_sem = saved.get("wf_auc_sem")
            if saved_sem is not None:
                self.wf_auc_sem = saved_sem
            elif self.wf_auc_std is not None and self.wf_folds > 0:
                # مدل‌های قدیمی این فیلد را ندارند؛ از std/فولدهای ذخیره‌شده بازسازی می‌شود.
                self.wf_auc_sem = round(float(self.wf_auc_std) / math.sqrt(self.wf_folds), 4)
            self.selected_model_name = saved.get("selected_model_name")
            self.class_balance = saved.get("class_balance")
            self.health = saved.get("health", "LOADED")
            self.is_trained = True
            logger.info(f"🤖 ML AutoPilot v8 loaded | {self.selected_model_name} | WF AUC={self.wf_auc_mean}")
        except Exception as e:
            logger.warning(f"🤖 ML model load failed; auto-recovering: {e}")
            self._quarantine_corrupt_model()
            self.model = None
            self.is_trained = False

    def _save_model(self):
        if self.model is None:
            return
        try:
            self._backup_model_file()
            payload = {
                "model_version": self.MODEL_VERSION,
                "model": self.model,
                "trained_on_n_trades": self.trained_on_n_trades,
                "dataset_n": self.dataset_n,
                "last_test_auc": self.last_test_auc,
                "last_test_accuracy": self.last_test_accuracy,
                "last_brier": self.last_brier,
                "wf_auc_mean": self.wf_auc_mean,
                "wf_auc_std": self.wf_auc_std,
                "wf_auc_sem": self.wf_auc_sem,
                "wf_folds": self.wf_folds,
                "selected_model_name": self.selected_model_name,
                "class_balance": self.class_balance,
                "health": self.health,
            }
            tmp = PATHS["ML_MODEL_FILE"] + ".tmp"
            joblib.dump(payload, tmp, compress=3)
            os.replace(tmp, PATHS["ML_MODEL_FILE"])
        except Exception as e:
            logger.error(f"🤖 ML save failed; live model kept: {e}")
            try:
                if os.path.exists(PATHS["ML_MODEL_FILE"] + ".tmp"):
                    os.remove(PATHS["ML_MODEL_FILE"] + ".tmp")
            except Exception:
                pass

    def _build_dataset(self):
        X, y = [], []
        for trade in self.memory.trades:
            label = trade.get("outcome_label")
            if label not in ("TP1", "TP2", "TP3", "SL", "TIMEOUT"):
                continue
            y_label = 1 if label in ("TP1", "TP2", "TP3") else 0
            feats = trade.get("features") or {}
            row = []
            for name in self.FEATURE_NAMES:
                v = feats.get(name, np.nan)
                try:
                    v = float(v)
                    if not np.isfinite(v):
                        v = np.nan
                except Exception:
                    v = np.nan
                row.append(v)
            X.append(row)
            y.append(y_label)
        if not X:
            return np.empty((0, len(self.FEATURE_NAMES)), dtype=float), np.empty(0, dtype=int)
        return np.asarray(X, dtype=float), np.asarray(y, dtype=int)

    def should_retrain(self) -> bool:
        if not SKLEARN_AVAILABLE:
            return False
        X, y = self._build_dataset()
        n = len(y)
        min_n = CONFIG.get("ML_MIN_TRADES_TO_TRAIN", 50)
        if n < min_n or len(np.unique(y)) < 2:
            return False
        if not self.is_trained:
            return True
        return (n - self.trained_on_n_trades) >= CONFIG.get("ML_RETRAIN_INTERVAL", 15)

    @staticmethod
    def _make_models():
        # Regularization قوی‌تر برای کاهش Overfitting روی داده‌های noisy بازار
        models = {
            "logistic": Pipeline([
                ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                ("scale", StandardScaler()),
                ("model", LogisticRegression(C=0.15, max_iter=1500, class_weight="balanced", random_state=42)),
            ]),
            "hist_gradient": Pipeline([
                ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                ("model", HistGradientBoostingClassifier(
                    max_iter=120, max_leaf_nodes=6, learning_rate=0.025, max_depth=3,
                    l2_regularization=3.0, min_samples_leaf=12,
                    early_stopping=True, random_state=42
                )),
            ]),
            "extra_trees": Pipeline([
                ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                ("model", ExtraTreesClassifier(
                    n_estimators=180, max_depth=4, min_samples_leaf=8,
                    max_features=0.6, class_weight="balanced_subsample", random_state=42, n_jobs=1
                )),
            ]),
        }
        if XGBOOST_AVAILABLE:
            models["xgboost"] = Pipeline([
                ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                ("model", XGBClassifier(
                    n_estimators=140, max_depth=3, learning_rate=0.025,
                    min_child_weight=6, subsample=0.75, colsample_bytree=0.7,
                    reg_alpha=0.4, reg_lambda=5.0, gamma=0.05,
                    objective="binary:logistic", eval_metric="logloss",
                    tree_method="hist", n_jobs=1, random_state=42,
                )),
            ])
        if CATBOOST_AVAILABLE:
            models["catboost"] = Pipeline([
                ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                ("model", CatBoostClassifier(iterations=160, depth=4, learning_rate=0.025,
                    loss_function="Logloss", eval_metric="AUC", verbose=False, random_seed=42,
                    l2_leaf_reg=6.0, thread_count=1)),
            ])
        return models

    @staticmethod
    def _fit_calibrated(base, X, y):
        n = len(y)
        if n < 80:
            base.fit(X, y)
            return base
        splits = min(3, max(2, n // 35))
        return CalibratedClassifierCV(base, method="sigmoid", cv=TimeSeriesSplit(n_splits=splits)).fit(X, y)

    def _walk_forward(self, X, y):
        min_train = CONFIG.get("ML_MIN_TRAIN_SAMPLES", 50)
        block = CONFIG.get("ML_TEST_BLOCK", 15)
        gap = CONFIG.get("ML_WF_GAP", 5)
        results = {name: {"auc": [], "brier": [], "accuracy": []} for name in self._make_models()}
        n = len(y)
        if n < min_train + block * 2 + gap:
            return results
        for train_end in range(min_train, n - block + 1, block):
            test_start = train_end + gap
            test_end = min(test_start + block, n)
            if test_end > n or test_start >= n:
                continue
            Xtr, ytr = X[:train_end], y[:train_end]
            Xte, yte = X[test_start:test_end], y[test_start:test_end]
            if len(np.unique(ytr)) < 2 or len(np.unique(yte)) < 2:
                continue
            for name, base in self._make_models().items():
                try:
                    fitted = self._fit_calibrated(base, Xtr, ytr)
                    proba = fitted.predict_proba(Xte)[:, 1]
                    pred = (proba >= 0.5).astype(int)
                    results[name]["auc"].append(float(roc_auc_score(yte, proba)))
                    results[name]["brier"].append(float(brier_score_loss(yte, proba)))
                    results[name]["accuracy"].append(float(accuracy_score(yte, pred)))
                except Exception as e:
                    logger.debug(f"ML WF {name} failed: {e}")
        return results

    @staticmethod
    def _score_candidate(auc_mean, auc_std, brier_mean):
        return float(auc_mean - 0.4 * auc_std - 0.25 * max(0.0, brier_mean - 0.22))

    def train(self, force: bool = False) -> Optional[dict]:
        if not SKLEARN_AVAILABLE:
            self.health = "NO_SKLEARN"
            return None
        if not force and not self.should_retrain():
            return None
        try:
            X, y = self._build_dataset()
            n = len(y)
            min_n = CONFIG.get("ML_MIN_TRADES_TO_TRAIN", 50)
            if n < min_n or len(np.unique(y)) < 2:
                self.health = "WAITING_FOR_VALID_DATA"
                return None

            wf = self._walk_forward(X, y)
            candidates = []
            for name, m in wf.items():
                if len(m["auc"]) >= CONFIG.get("ML_MIN_WF_FOLDS", 4):
                    auc_mean = float(np.mean(m["auc"]))
                    auc_std = float(np.std(m["auc"]))
                    brier = float(np.mean(m["brier"]))
                    acc = float(np.mean(m["accuracy"]))
                    score = self._score_candidate(auc_mean, auc_std, brier)
                    candidates.append((score, name, auc_mean, auc_std, brier, acc, len(m["auc"])))
            if not candidates:
                self.health = "NO_VALID_WF"
                return None

            candidates.sort(key=lambda z: (-z[0], -z[2], z[3], z[4]))
            _, best_name, wf_auc, wf_std, wf_brier, wf_acc, folds = candidates[0]

            # Hold-out واقعی: آخرین 18% داده (حداقل 25 نمونه) فقط برای Last AUC
            holdout_frac = float(CONFIG.get("ML_HOLDOUT_FRACTION", 0.18))
            min_holdout = int(CONFIG.get("ML_MIN_HOLDOUT_SAMPLES", 25))
            gap = int(CONFIG.get("ML_WF_GAP", 6))
            holdout_n = max(min_holdout, int(n * holdout_frac))
            holdout_n = min(holdout_n, max(min_holdout, n // 4))
            test_start = max(int(CONFIG.get("ML_MIN_TRAIN_SAMPLES", 80)), n - holdout_n)
            train_end = max(int(CONFIG.get("ML_MIN_TRAIN_SAMPLES", 80)), test_start - gap)
            if train_end >= test_start:
                train_end = max(int(CONFIG.get("ML_MIN_TRAIN_SAMPLES", 80)), test_start - 1)
            base = self._make_models()[best_name]
            test_model = self._fit_calibrated(base, X[:train_end], y[:train_end])
            X_test, y_test = X[test_start:], y[test_start:]
            if len(X_test) >= 10 and len(np.unique(y_test)) > 1:
                test_proba = test_model.predict_proba(X_test)[:, 1]
                test_pred = (test_proba >= 0.5).astype(int)
                last_auc = float(roc_auc_score(y_test, test_proba))
                last_acc = float(accuracy_score(y_test, test_pred))
                last_brier = float(brier_score_loss(y_test, test_proba))
            else:
                last_auc = None
                last_acc = None
                last_brier = None

            # مدل عملیاتی روی داده تا قبل از holdout (جلوگیری از leakage روی last AUC)
            op_end = train_end if train_end >= int(CONFIG.get("ML_MIN_TRAIN_SAMPLES", 80)) else n
            operational = self._fit_calibrated(self._make_models()[best_name], X[:op_end], y[:op_end])

            probe = operational.predict_proba(X[max(0, op_end - min(5, op_end)):op_end])[:, 1]
            if not np.all(np.isfinite(probe)):
                raise ValueError("operational model produced non-finite probabilities")

            self.model = operational
            self.is_trained = True
            self.trained_on_n_trades = n
            self.dataset_n = n
            self.last_test_auc = round(last_auc, 3) if last_auc is not None else None
            self.last_test_accuracy = round(last_acc, 3) if last_acc is not None else None
            self.last_brier = round(last_brier, 4) if last_brier is not None else round(wf_brier, 4)
            self.wf_auc_mean = round(wf_auc, 3)
            self.wf_auc_std = round(wf_std, 3)
            wf_sem = wf_std / math.sqrt(max(1, folds))
            self.wf_auc_sem = round(wf_sem, 4)
            self.wf_folds = folds
            self.selected_model_name = best_name
            self.class_balance = {"wins": int(np.sum(y == 1)), "losses": int(np.sum(y == 0))}
            self.last_train_time = time.time()

            disable_below = float(CONFIG.get("ML_DISABLE_IF_LAST_AUC_BELOW", 0.48))
            oos_ok = (last_auc is None) or (last_auc >= disable_below)
            stable = (
                wf_auc >= CONFIG.get("ML_MIN_WF_AUC", 0.54) and
                wf_sem <= CONFIG.get("ML_MAX_WF_AUC_SEM", 0.055) and
                wf_std <= CONFIG.get("ML_MAX_WF_AUC_STD", 0.30) and
                oos_ok and
                (last_auc is None or last_auc >= float(CONFIG.get("ML_MIN_AUC_FOR_INFLUENCE", 0.54)) * 0.92)
            )
            if last_auc is not None and last_auc < disable_below:
                self.health = "DISABLED_WEAK_OOS"
            else:
                self.health = "ACTIVE" if stable else "PROVISIONAL"
            self._save_model()

            # ذخیره تاریخچه آموزش
            train_record = {
                "timestamp": time.time(),
                "n_trades": n,
                "wf_auc": wf_auc,
                "wf_std": wf_std,
                "wf_sem": round(wf_sem, 4),
                "wf_folds": folds,
                "brier": wf_brier,
                "model": best_name,
                "health": self.health,
                "last_test_auc": last_auc,
                "last_test_acc": last_acc
            }
            self.training_history.append(train_record)
            _atomic_write_json(os.path.join(DATA_DIR, "ml_training_history.json"), self.training_history[-100:])
            # Experiment tracking (append-only JSONL)
            try:
                exp_path = os.path.join(DATA_DIR, "ml_experiments.jsonl")
                train_record_exp = dict(train_record)
                train_record_exp["ts"] = time.time()
                train_record_exp["version"] = CONFIG.get("BOT_VERSION", "24.2")
                with open(exp_path, "a", encoding="utf-8") as _ef:
                    _ef.write(json.dumps(train_record_exp, ensure_ascii=False) + "\n")
            except Exception as _expe:
                logger.debug(f"experiment log failed: {_expe}")

            logger.info(f"🤖 ML: {n} samples | {best_name} | WF AUC={wf_auc:.3f}±{wf_std:.3f} (SEM={wf_sem:.3f}) | {folds} folds")
            return train_record
            
        except Exception as e:
            logger.exception(f"🤖 ML training failed: {e}")
            self.health = "ERROR_ROLLBACK"
            return None

    def predict_win_probability(self, features: dict) -> Optional[float]:
        if not self.is_trained or self.model is None:
            return None
        try:
            row = []
            for name in self.FEATURE_NAMES:
                v = features.get(name, np.nan)
                try:
                    v = float(v)
                    if not np.isfinite(v):
                        v = np.nan
                except Exception:
                    v = np.nan
                row.append(v)
            p = float(self.model.predict_proba([row])[0][1])
            return p if np.isfinite(p) else None
        except Exception as e:
            logger.debug(f"ML prediction failed: {e}")
            return None

    def get_influence_weight(self) -> float:
        if CONFIG.get("ML_MAX_INFLUENCE", 0.0) == 0.0:
            return 0.0
        if not self.is_trained or self.wf_auc_mean is None:
            return 0.0
        if self.health in ("DISABLED_WEAK_OOS", "ERROR_ROLLBACK", "NO_SKLEARN", "DRIFT"):
            return 0.0
        # Soft drift: if recent OOS AUC collapsed vs train-time WF AUC
        try:
            if self.last_test_auc is not None and self.wf_auc_mean is not None:
                if self.last_test_auc + 0.08 < float(self.wf_auc_mean):
                    self.health = "DRIFT"
                    logger.warning(f"🤖 ML drift detected: last_auc={self.last_test_auc} << wf={self.wf_auc_mean}")
                    return 0.0
        except Exception:
            pass

        min_auc = float(CONFIG.get("ML_MIN_AUC_FOR_INFLUENCE", 0.54))
        full_auc = float(CONFIG.get("ML_FULL_AUC_FOR_INFLUENCE", 0.64))
        wf_auc = float(self.wf_auc_mean)
        folds = int(self.wf_folds or 0)
        brier = float(self.last_brier) if self.last_brier is not None else 0.30

        if folds < int(CONFIG.get("ML_MIN_WF_FOLDS", 4)):
            return 0.0
        if wf_auc < min_auc:
            return 0.0
        if brier > float(CONFIG.get("ML_REQUIRE_BRIER_MAX", 0.26)):
            return 0.0

        # Last AUC خیلی ضعیف → بدون تأثیر
        if self.last_test_auc is not None and self.last_test_auc < float(CONFIG.get("ML_DISABLE_IF_LAST_AUC_BELOW", 0.48)):
            return 0.0

        wf_sem = float(self.wf_auc_sem) if self.wf_auc_sem is not None else (
            float(self.wf_auc_std or 0.0) / math.sqrt(max(1, folds))
        )
        sem_cap = float(CONFIG.get("ML_MAX_WF_AUC_SEM", 0.055))
        stability = max(0.0, min(1.0, 1.0 - (wf_sem / max(sem_cap, 1e-6))))

        quality = max(0.0, min(1.0, (wf_auc - min_auc) / max(0.01, full_auc - min_auc)))
        maturity = min(1.0, float(self.trained_on_n_trades) / max(1, int(CONFIG.get("ML_FULL_MATURITY_TRADES", 350))))

        holdout_factor = 1.0
        if self.last_test_auc is not None:
            if self.last_test_auc < 0.50:
                holdout_factor = 0.20
            elif self.last_test_auc < min_auc:
                holdout_factor = 0.45
            elif self.last_test_auc < full_auc:
                holdout_factor = 0.75

        # Edge واقعی: اگر روی نمونه کافی، WR با ML بدتر از بدون ML باشد → کاهش influence
        edge_factor = 1.0
        try:
            perf = self.memory.get_ml_performance()
            with_ml = perf.get("with_ml", {}) or {}
            without_ml = perf.get("without_ml", {}) or {}
            n_with = int(with_ml.get("trades", 0) or 0)
            n_wo = int(without_ml.get("trades", 0) or 0)
            min_edge_n = int(CONFIG.get("ML_EDGE_MIN_TRADES", 200))
            if n_with >= min_edge_n and n_wo >= max(80, min_edge_n // 3):
                wr_w = float(with_ml.get("winrate", 0) or 0)
                wr_o = float(without_ml.get("winrate", 0) or 0)
                if wr_w + 1.0 < wr_o:
                    edge_factor = 0.30
                elif wr_w + 0.3 < wr_o:
                    edge_factor = 0.55
                elif wr_w >= wr_o + 0.5:
                    edge_factor = 1.0
                else:
                    edge_factor = 0.85
        except Exception:
            edge_factor = 1.0

        max_inf = float(CONFIG.get("ML_MAX_INFLUENCE", 0.0))
        if self.health == "PROVISIONAL":
            base = float(CONFIG.get("ML_PROVISIONAL_INFLUENCE", 0.015))
            return min(max_inf, base * max(0.4, quality) * max(0.5, stability) * holdout_factor * edge_factor)

        return min(max_inf, maturity * quality * max(0.5, stability) * holdout_factor * edge_factor * max_inf)

    def get_training_summary(self) -> dict:
        if not self.training_history:
            return {"total_trainings": 0, "best_auc": 0, "last_training": None}
        
        best = max(self.training_history, key=lambda x: x.get("wf_auc", 0))
        last = self.training_history[-1] if self.training_history else None
        
        return {
            "total_trainings": len(self.training_history),
            "best_auc": best.get("wf_auc", 0),
            "best_model": best.get("model", "N/A"),
            "last_training": last,
            "current_health": self.health,
            "is_trained": self.is_trained
        }


# ============================================================================
# بخش 9: کلاس AutoPilot و Self-Healing - کامل
# ============================================================================

class SelfHealingAutoPilot:
    def __init__(self, memory):
        self.memory = memory
        self.last_run = 0.0
        self.state = self._load()
        self.lock = threading.Lock()
        os.makedirs(PATHS["CONFIG_BACKUP_DIR"], exist_ok=True)

    def _load(self):
        try:
            with open(PATHS["AUTOPILOT_STATE"], "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"last_good": {}, "last_good_wr": None, "last_good_pf": None}

    def _save(self):
        _atomic_write_json(PATHS["AUTOPILOT_STATE"], self.state)

    def snapshot(self, tag="auto"):
        try:
            ts = int(time.time())
            path = os.path.join(PATHS["CONFIG_BACKUP_DIR"], f"{tag}_{ts}.json")
            _atomic_write_json(path, {"config": dict(CONFIG), "state": self.state, "time": ts})
            return path
        except Exception:
            return None

    def metrics(self, trades=None):
        tr = list(trades if trades is not None else self.memory.trades)
        if not tr:
            return {"wr": 0, "pf": 1, "n": 0}
        wr = sum(bool(t.get("win")) for t in tr) / len(tr)
        gp = sum(max(0, float(t.get("return_pct", 0))) for t in tr)
        gl = abs(sum(min(0, float(t.get("return_pct", 0))) for t in tr))
        return {"wr": wr, "pf": gp / gl if gl else 99.0, "n": len(tr)}

    def regime_adjust(self):
        regimes = {}
        for t in list(self.memory.trades)[-CONFIG["REGIME_WINDOW"]:]:
            r = t.get("features", {}).get("market_regime", "UNKNOWN")
            regimes.setdefault(r, []).append(t)
        changed = False
        adj = CONFIG.get("REGIME_CONFIDENCE_ADJUSTMENT", {}).copy()
        for r, tr in regimes.items():
            if len(tr) < CONFIG["REGIME_MIN_TRADES_FOR_ADJUST"]:
                continue
            wr = sum(bool(t.get("win")) for t in tr) / len(tr)
            cur = float(adj.get(r, 0))
            if wr < CONFIG["REGIME_BAD_WINRATE"]:
                cur = min(CONFIG["REGIME_MAX_ADJUSTMENT"], cur + CONFIG["REGIME_ADJUSTMENT_STEP"])
                changed = True
            elif wr > CONFIG["REGIME_GOOD_WINRATE"]:
                cur = max(0.0, cur - CONFIG["REGIME_ADJUSTMENT_STEP"])
                changed = True
            adj[r] = round(min(0.50, max(0.0, cur)), 2)
        if changed:
            CONFIG["REGIME_CONFIDENCE_ADJUSTMENT"] = adj
        return changed

    def run(self, force=False):
        with self.lock:
            now = time.time()
            if not force and now - self.last_run < CONFIG["AUTO_HEAL_INTERVAL_SEC"]:
                return
            self.last_run = now
            tr = list(self.memory.trades)
            m = self.metrics(tr)
            if len(tr) < CONFIG["AUTO_HEAL_MIN_TRADES"]:
                return
            self.snapshot("before_autopilot")
            recent = tr[-CONFIG["RECENT_PERFORMANCE_WINDOW"]:]
            rm = self.metrics(recent)
            # FIX #3: قبلاً این بخش فقط با self.lock محافظت می‌شد، نه CONFIG_LOCK
            # مشترکی که بقیه‌ی توابع (apply_optimized_params، self_diagnose_and_repair،
            # optimize_regime_thresholds) استفاده می‌کنن. این باعث race condition
            # واقعی روی دیکشنری CONFIG بین ترد‌های مختلف می‌شد.
            with CONFIG_LOCK:
                if rm["pf"] >= 1.02 and rm["wr"] >= 0.52:
                    self.state["last_good"] = {
                        "MIN_CONFIDENCE_SCORE": CONFIG["MIN_CONFIDENCE_SCORE"],
                        "PUMP_THRESHOLD": CONFIG["PUMP_THRESHOLD"],
                        "DUMP_THRESHOLD": CONFIG["DUMP_THRESHOLD"],
                        "REGIME_CONFIDENCE_ADJUSTMENT": dict(CONFIG.get("REGIME_CONFIDENCE_ADJUSTMENT", {})),
                    }
                    self.state["last_good_wr"] = rm["wr"]
                    self.state["last_good_pf"] = rm["pf"]
                if rm["pf"] < 0.85 or rm["wr"] < 0.44:
                    last_wr = self.state.get("last_good_wr")
                    last_pf = self.state.get("last_good_pf")
                    if last_wr is not None and last_pf is not None and (
                        last_wr - rm["wr"] >= CONFIG["ROLLBACK_IF_WR_DROP"] or
                        last_pf - rm["pf"] >= CONFIG["ROLLBACK_IF_PF_DROP"]
                    ):
                        good = self.state.get("last_good", {})
                        for k, v in good.items():
                            CONFIG[k] = v
                        logger.warning("🛡️ AutoPilot: افت شدید تشخیص داده شد؛ rollback شد")
                    else:
                        CONFIG["MIN_CONFIDENCE_SCORE"] = min(6.8, CONFIG["MIN_CONFIDENCE_SCORE"] + 0.05)
                        CONFIG["PUMP_THRESHOLD"] = min(1.8, CONFIG["PUMP_THRESHOLD"] + 0.05)
                        CONFIG["DUMP_THRESHOLD"] = -CONFIG["PUMP_THRESHOLD"]
                elif rm["pf"] > 1.1 and rm["wr"] > 0.56:
                    floor = _min_confidence_floor()
                    CONFIG["MIN_CONFIDENCE_SCORE"] = max(floor, CONFIG["MIN_CONFIDENCE_SCORE"] - 0.05)
                # تنظیم رژیم فقط توسط optimize_regime_thresholds انجام می‌شود
                # تا آستانه در هر چند دقیقه چند بار افزایش پیدا نکند.
                self.state["last_metrics"] = m
                self.state["recent_metrics"] = rm
                self.state["config"] = {
                    k: CONFIG.get(k) for k in (
                        "MIN_CONFIDENCE_SCORE",
                        "PUMP_THRESHOLD",
                        "DUMP_THRESHOLD",
                        "REGIME_CONFIDENCE_ADJUSTMENT"
                    )
                }
            self._save()

    def symbol_blocked(self, symbol, direction):
        now = time.time()
        window = max(
            float(CONFIG.get("DEDUP_WINDOW_SEC", 1400)),
            float(CONFIG.get("SYMBOL_COOLDOWN_SEC", 2700)),
            float(CONFIG.get("MIN_SYMBOL_RESHIFT_SEC", 3600)),
        )
        # FIX #14 + v21.4: cooldown قوی‌تر برای جلوگیری از چند سیگنال روی یک نماد
        target_is_long = _is_long_direction(direction)
        recent = [
            t for t in list(self.memory.trades)
            if str(t.get("symbol", "")).upper() == str(symbol).upper() and
            _is_long_direction(t.get("direction", "")) == target_is_long and
            now - float(t.get("timestamp", 0)) < window
        ]
        if len(recent) >= int(CONFIG.get("MAX_PENDING_PER_SYMBOL", 1)):
            return True
        # هر جهت: اگر اخیراً روی همین نماد سیگنال/معامله بوده، بلاک
        any_recent = [
            t for t in list(self.memory.trades)
            if str(t.get("symbol", "")).upper() == str(symbol).upper()
            and now - float(t.get("timestamp", 0)) < float(CONFIG.get("MIN_SYMBOL_RESHIFT_SEC", 3600))
        ]
        return len(any_recent) >= 1

    def consecutive_losses(self):
        n = 0
        for t in reversed(list(self.memory.trades)):
            if t.get("win"):
                break
            n += 1
        return n

    def emergency_gate(self, symbol, direction):
        # محافظت در برابر زنجیره ضرر، اما بدون قفل دائمی ربات.
        # بعد از یک توقف کوتاه، اجازه یک سیگنال recovery داده می‌شود.
        streak = self.consecutive_losses()
        if streak >= CONFIG["MAX_CONSECUTIVE_LOSSES"]:
            trades = list(self.memory.trades)
            last_ts = float(trades[-1].get("timestamp", 0)) if trades else 0.0
            cooldown = float(CONFIG.get("LOSS_STREAK_COOLDOWN_SEC", 900))
            if time.time() - last_ts < cooldown:
                return False, "consecutive_losses"
        if self.symbol_blocked(symbol, direction):
            return False, "symbol_cooldown"
        return True, "ok"


# ============================================================================
# بخش 10: کلاس الگویاب (PatternRecognizer) - کامل
# ============================================================================

class PatternRecognizer:
    def __init__(self, memory: PerformanceMemory):
        self.memory = memory
        self.successful_patterns: list = []
        self.failed_patterns: list = []
        self.pattern_weights: dict = {"successful": {}, "failed": {}}
        self.match_statistics: dict = {"total_matches": 0, "successful_matches": 0}
        self.similarity_threshold_success: float = 0.58
        self.similarity_threshold_fail: float = 0.48
        self.max_patterns: int = 50
        self._load_patterns()
        logger.debug("PatternRecognizer راه‌اندازی شد")

    def _load_patterns(self):
        try:
            if os.path.exists(PATHS["PATTERNS_FILE"]):
                with open(PATHS["PATTERNS_FILE"], "r") as f:
                    data = json.load(f)
                    self.successful_patterns = data.get("successful_patterns", [])
                    self.failed_patterns = data.get("failed_patterns", [])
                    self.pattern_weights = data.get("pattern_weights", {"successful": {}, "failed": {}})
                    self.match_statistics = data.get("match_statistics", {"total_matches": 0, "successful_matches": 0})
                logger.info(f"{len(self.successful_patterns)} الگوی موفق و {len(self.failed_patterns)} الگوی ناموفق بارگذاری شد")
        except Exception as e:
            logger.warning(f"خطا در بارگذاری الگوها: {e}")

    def _save_patterns(self):
        try:
            data = {
                "successful_patterns": self.successful_patterns,
                "failed_patterns": self.failed_patterns,
                "pattern_weights": self.pattern_weights,
                "match_statistics": self.match_statistics,
                "timestamp": time.time()
            }
            _atomic_write_json(PATHS["PATTERNS_FILE"], data)
        except Exception as e:
            logger.error(f"خطا در ذخیره الگوها: {e}")

    def learn_patterns(self) -> None:
        try:
            if len(self.memory.trades) < 15:
                return
            
            logger.info("🔄 شروع یادگیری الگوهای موفق و ناموفق...")
            
            window = CONFIG.get("LEARNING_WINDOW", 70)
            recent_trades = list(self.memory.trades)[-window:]
            
            self.pattern_weights = {"successful": {}, "failed": {}}
            
            successful_patterns = []
            failed_patterns = []
            
            for trade in recent_trades:
                pattern = self._extract_pattern(trade)
                if trade.get("win", False):
                    successful_patterns.append(pattern)
                    self._update_pattern_weight(pattern, "successful")
                else:
                    failed_patterns.append(pattern)
                    self._update_pattern_weight(pattern, "failed")
            
            self.successful_patterns = successful_patterns[-self.max_patterns:]
            self.failed_patterns = failed_patterns[-self.max_patterns:]
            self._save_patterns()
            
            logger.info(f"✅ یادگیری الگوها کامل شد: {len(self.successful_patterns)} الگوی موفق, {len(self.failed_patterns)} الگوی ناموفق")
            
        except Exception as e:
            logger.error(f"خطا در یادگیری الگوها: {e}")

    def _extract_pattern(self, trade: dict) -> dict:
        features = trade.get("features", {})
        return {
            "trend": features.get("trend_type", ""),
            "volatility": features.get("volatility", 0.0),
            "volume_ratio": features.get("volume_ratio", 0.0),
            "rsi": features.get("rsi", 50.0),
            "pattern": features.get("price_action", ""),
            "market_regime": features.get("market_regime", "UNKNOWN"),
        }

    def _update_pattern_weight(self, pattern: dict, category: str) -> None:
        key = f"{pattern['trend']}_{pattern.get('market_regime', 'UNKNOWN')}_{pattern.get('pattern', 'NONE')}"
        if key not in self.pattern_weights[category]:
            self.pattern_weights[category][key] = {"count": 0}
        self.pattern_weights[category][key]["count"] += 1

    def _calculate_similarity(self, pattern1: dict, pattern2: dict) -> float:
        try:
            weights = {
                "trend": 0.25,
                "market_regime": 0.15,
                "pattern": 0.20,
                "volatility": 0.10,
                "volume_ratio": 0.10,
                "rsi": 0.20,
            }
            
            total_score = 0.0
            total_weight = 0.0
            
            for feature, weight in weights.items():
                total_weight += weight
                val1 = pattern1.get(feature)
                val2 = pattern2.get(feature)
                
                if feature in ("trend", "market_regime", "pattern"):
                    if val1 == val2:
                        total_score += weight
                else:
                    try:
                        num1 = float(val1) if val1 is not None else 0
                        num2 = float(val2) if val2 is not None else 0
                        if num1 == 0 and num2 == 0:
                            total_score += weight
                        elif max(abs(num1), abs(num2)) > 0:
                            diff_pct = abs(num1 - num2) / max(abs(num1), abs(num2), 0.001)
                            similarity = max(0, 1 - diff_pct)
                            total_score += similarity * weight
                    except Exception:
                        pass
            
            return total_score / total_weight if total_weight > 0 else 0.0
            
        except Exception as e:
            logger.error(f"خطا در محاسبه شباهت: {e}")
            return 0.0

    def matches_successful_pattern(self, current_features: dict) -> bool:
        try:
            current_pattern = {
                "trend": current_features.get("trend_type", ""),
                "volatility": current_features.get("volatility", 0.0),
                "volume_ratio": current_features.get("volume_ratio", 0.0),
                "rsi": current_features.get("rsi", 50.0),
                "pattern": current_features.get("price_action", ""),
                "market_regime": current_features.get("market_regime", "UNKNOWN"),
            }
            
            best_similarity = 0.0
            for pattern in self.successful_patterns:
                similarity = self._calculate_similarity(current_pattern, pattern)
                key = f"{pattern['trend']}_{pattern.get('market_regime', 'UNKNOWN')}_{pattern.get('pattern', 'NONE')}"
                weight_factor = min(1.5, 1 + (self.pattern_weights["successful"].get(key, {}).get("count", 0) / 20))
                adjusted_similarity = similarity * weight_factor
                if adjusted_similarity > best_similarity:
                    best_similarity = adjusted_similarity
            
            self.match_statistics["total_matches"] += 1
            is_match = best_similarity > self.similarity_threshold_success
            if is_match:
                self.match_statistics["successful_matches"] += 1
            
            return is_match
            
        except Exception as e:
            logger.error(f"خطا در بررسی الگوی موفق: {e}")
            return False

    def matches_failed_pattern(self, current_features: dict) -> bool:
        try:
            current_pattern = {
                "trend": current_features.get("trend_type", ""),
                "volatility": current_features.get("volatility", 0.0),
                "volume_ratio": current_features.get("volume_ratio", 0.0),
                "rsi": current_features.get("rsi", 50.0),
                "pattern": current_features.get("price_action", ""),
                "market_regime": current_features.get("market_regime", "UNKNOWN"),
            }
            
            for pattern in self.failed_patterns:
                similarity = self._calculate_similarity(current_pattern, pattern)
                if similarity > self.similarity_threshold_fail:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"خطا در بررسی الگوی ناموفق: {e}")
            return False


# ============================================================================
# بخش 11: خودآموزی خودکار (Auto-Learning System) - کامل
# ============================================================================

class AutoLearningSystem:
    def __init__(self, memory: PerformanceMemory):
        self.memory = memory
        self.learning_queue: deque = deque(maxlen=100)
        self.learning_thread: Optional[threading.Thread] = None
        self.running = False
        self._load_queue()
        logger.debug("AutoLearningSystem راه‌اندازی شد")

    def _load_queue(self):
        try:
            if os.path.exists(PATHS["AUTO_LEARN_QUEUE"]):
                with open(PATHS["AUTO_LEARN_QUEUE"], "r") as f:
                    data = json.load(f)
                    for item in data:
                        self.learning_queue.append(item)
                logger.info(f"{len(self.learning_queue)} سیگنال در صف یادگیری")
        except Exception as e:
            logger.warning(f"خطا در بارگذاری صف یادگیری: {e}")

    def _save_queue(self):
        _atomic_write_json(PATHS["AUTO_LEARN_QUEUE"], list(self.learning_queue))

    def add_signal_for_learning(self, signal: dict):
        if not CONFIG.get("AUTO_LEARN_ENABLED", True):
            return
        
        try:
            symbol = signal.get("symbol")
            dedup_window = CONFIG.get("AUTO_LEARN_DEDUP_WINDOW_SEC", 300)
            now = time.time()
            for item in self.learning_queue:
                if item.get("symbol") == symbol and (now - item.get("timestamp", 0)) < dedup_window:
                    return
            
            self.learning_queue.append({
                "signal": signal,
                "timestamp": now,
                "symbol": symbol,
                "direction": signal.get("direction"),
                "entry": signal.get("entry"),
                "confidence": signal.get("confidence", 0),
                "retry_count": 0,
                "ml_used": signal.get("ml_used", False),
            })
            self._save_queue()
            logger.info(f"📚 {symbol} به صف خودآموزی اضافه شد (صف: {len(self.learning_queue)})")
        except Exception as e:
            logger.error(f"خطا در افزودن سیگنال به صف: {e}")

    def _simulate_outcome(self, signal_data: dict):
        try:
            signal = signal_data.get("signal", {})
            symbol = signal.get("symbol")
            direction = signal.get("direction")
            entry = signal.get("entry")
            sl = signal.get("sl")
            tps = signal.get("tps") or []
            
            if not symbol or not entry or sl is None or not tps:
                return {"_unresolved": True, "reason": "incomplete_signal", "symbol": symbol}
            
            hold_candles = get_max_hold_candles()
            minutes_per_candle = _interval_to_minutes(CONFIG.get("KLINE_INTERVAL", "15m")) or 15
            
            candle_ts = signal.get("signal_candle_ts")
            if candle_ts:
                signal_time = pd.to_datetime(float(candle_ts), unit="s")
                df = fetch_klines_df(symbol, interval=CONFIG["KLINE_INTERVAL"], limit=hold_candles + 20, use_cache=False)
                if df is None or df.empty:
                    return {"_unresolved": True, "reason": "fetch_failed", "symbol": symbol}
                path = df[df.index > signal_time]
                if len(path) < hold_candles:
                    return {"_unresolved": True, "reason": "not_enough_elapsed_candles", "symbol": symbol}
                path = path.head(hold_candles)
            else:
                df = fetch_klines_df(symbol, interval=CONFIG["KLINE_INTERVAL"], limit=hold_candles + 15)
                if df is None or len(df) < hold_candles:
                    return {"_unresolved": True, "reason": "fetch_failed_legacy", "symbol": symbol}
                path = df.tail(hold_candles)
            
            is_long = bool(direction and "LONG" in direction)
            future_price = float(path["close"].iloc[-1]) if len(path) > 0 else float(df["close"].iloc[-1])
            slippage = CONFIG.get("SLIPPAGE_PCT", 0.0005)
            result = None
            exit_price = None
            which_target = "TIMEOUT"
            candles_to_result = None
            
            mfe_pct = 0.0
            mae_pct = 0.0
            
            for candle_num, (_, row) in enumerate(path.iterrows(), start=1):
                hi, lo = row["high"], row["low"]
                if is_long:
                    favorable = (hi - entry) / entry * 100
                    adverse = (entry - lo) / entry * 100
                else:
                    favorable = (entry - lo) / entry * 100
                    adverse = (hi - entry) / entry * 100
                mfe_pct = max(mfe_pct, favorable)
                mae_pct = max(mae_pct, adverse)
                
                if not CONFIG.get("AUTO_LEARN_PATH_BASED", True) or result is not None:
                    continue
                
                if is_long:
                    if lo <= sl:
                        result = "loss"
                        exit_price = sl * (1 - slippage)
                        which_target = "SL"
                        candles_to_result = candle_num
                    else:
                        hit_tps = [(idx, tp) for idx, tp in enumerate(tps) if hi >= tp]
                        if hit_tps:
                            best_idx, exit_price = min(hit_tps, key=lambda x: x[0])
                            result = "win"
                            which_target = f"TP{best_idx + 1}"
                            candles_to_result = candle_num
                else:
                    if hi >= sl:
                        result = "loss"
                        exit_price = sl * (1 + slippage)
                        which_target = "SL"
                        candles_to_result = candle_num
                    else:
                        hit_tps = [(idx, tp) for idx, tp in enumerate(tps) if lo <= tp]
                        if hit_tps:
                            best_idx, exit_price = min(hit_tps, key=lambda x: x[0])
                            result = "win"
                            which_target = f"TP{best_idx + 1}"
                            candles_to_result = candle_num
            
            if result is None:
                exit_price = future_price
                result = "win" if ((future_price > entry) == is_long) else "loss"
                which_target = "TIMEOUT"
                candles_to_result = len(path)
            
            if is_long:
                return_pct = (exit_price - entry) / entry * 100
            else:
                return_pct = (entry - exit_price) / entry * 100
            
            return_pct -= CONFIG["COMMISSION_PCT"] * 2 * 100
            
            is_win = result == "win"
            
            trade_result = {
                "symbol": symbol,
                "direction": direction,
                "entry": entry,
                "exit": exit_price,
                "return_pct": return_pct,
                "win": is_win,
                "which_target": which_target,
                "outcome_label": which_target if which_target in ("TP1", "TP2", "TP3", "SL") else "TIMEOUT",
                "time_to_result_min": (candles_to_result * minutes_per_candle) if candles_to_result else None,
                "mfe_pct": round(mfe_pct, 3),
                "mae_pct": round(mae_pct, 3),
                "pre_signal_change_15m": signal.get("pre_signal_change_15m"),
                "features": signal.get("learning_features", {}),
                "signal_confidence": signal.get("confidence", 0),
                "auto_learned": True,
                "ml_used": signal.get("ml_used", False),
                "ml_probability": signal.get("ml_probability"),
                "market_regime": signal.get("market_regime", "UNKNOWN"),
            }
            
            return trade_result
            
        except Exception as e:
            logger.error(f"خطا در شبیه‌سازی نتیجه {signal_data.get('symbol')}: {e}")
            return {"_unresolved": True, "reason": f"exception: {e}", "symbol": signal_data.get("symbol")}

    def _process_learning_queue(self):
        logger.info("شروع پردازش صف یادگیری...")
        max_retries = CONFIG.get("AUTO_LEARN_MAX_RETRIES", 5)
        
        while self.running:
            try:
                if len(self.learning_queue) == 0:
                    time.sleep(15)
                    continue
                
                minutes_per_candle = _interval_to_minutes(CONFIG.get("KLINE_INTERVAL", "15m")) or 15
                wait_seconds = int(get_max_hold_candles() * minutes_per_candle * 60 * 1.1)
                now = time.time()
                
                processed_count = 0
                hard_expiry_seconds = wait_seconds * 4
                
                while len(self.learning_queue) > 0:
                    signal_data = self.learning_queue[0]
                    signal_time = signal_data.get("timestamp", 0)
                    age = now - signal_time
                    
                    if age >= hard_expiry_seconds:
                        self.learning_queue.popleft()
                        logger.error(f"🔴 {signal_data.get('symbol')} پس از {age/60:.0f} دقیقه بدون پردازش حذف شد")
                        continue
                    
                    if age < wait_seconds:
                        break
                    
                    self.learning_queue.popleft()
                    result = self._simulate_outcome(signal_data)
                    
                    if result and not result.get("_unresolved"):
                        self.memory.add_trade_result(result)
                        win_emoji = "✅" if result["win"] else "❌"
                        ml_tag = " 🤖" if result.get("ml_used", False) else ""
                        logger.info(f"🎓 خودآموزی: {result['symbol']}{ml_tag} {result['direction']} → {result['return_pct']:.2f}% {win_emoji}")
                        processed_count += 1
                        
                        # به‌روزرسانی سیستم یادگیری
                        if len(self.memory.trades) % 3 == 0 and len(self.memory.trades) > 0:
                            logger.info("به‌روزرسانی سیستم یادگیری بر اساس معاملات جدید...")
                            try:
                                weight_learner.update_weights()
                                pattern_recognizer.learn_patterns()
                                param_optimizer.optimize(force=True)
                                param_optimizer.apply_optimized_params()
                                ml_model.train()
                                param_optimizer.optimize_regime_thresholds()
                            except Exception as learn_err:
                                logger.error(f"خطا در به‌روزرسانی یادگیری: {learn_err}")
                    else:
                        reason = result.get("reason", "unknown") if result else "unknown"
                        retry_count = signal_data.get("retry_count", 0) + 1
                        if retry_count <= max_retries:
                            signal_data["retry_count"] = retry_count
                            signal_data["timestamp"] = now
                            self.learning_queue.append(signal_data)
                            logger.warning(f"⚠️ {signal_data.get('symbol')} حل نشد ({reason}) - تلاش مجدد {retry_count}/{max_retries}")
                        else:
                            logger.warning(f"❌ {signal_data.get('symbol')} پس از {max_retries} تلاش رد شد")
                
                if processed_count > 0:
                    self._save_queue()
                
                time.sleep(15)
                
            except Exception as e:
                logger.error(f"خطا در پردازش صف یادگیری: {e}")
                time.sleep(30)

    def start(self):
        if self.running:
            return
        self.running = True
        self.learning_thread = threading.Thread(target=self._run_queue_supervised, daemon=True)
        self.learning_thread.start()
        logger.info("🧠 سیستم خودآموزی خودکار راه‌اندازی شد")

    def _run_queue_supervised(self):
        while self.running:
            try:
                self._process_learning_queue()
            except Exception as e:
                logger.error(f"⚠️ ترد یادگیری متوقف شد، راه‌اندازی مجدد: {e}")
                time.sleep(10)

    def stop(self):
        self.running = False
        logger.info("سیستم خودآموزی متوقف شد")

    def is_healthy(self) -> bool:
        return bool(self.learning_thread and self.learning_thread.is_alive())

    def get_queue_status(self) -> dict:
        return {
            "queue_size": len(self.learning_queue),
            "is_running": self.running,
            "first_signal": self.learning_queue[0] if self.learning_queue else None
        }

    def get_pending_status(self, price_map: Dict[str, float]) -> dict:
        result = {
            "total_pending": len(self.learning_queue),
            "tp1_hit": 0,
            "sl_hit": 0,
            "still_open": 0,
            "unknown": 0,
            "items": [],
            "regime_counts": {},
            "ml_used_count": 0
        }
        try:
            for item in self.learning_queue:
                signal = item.get("signal", {})
                symbol = signal.get("symbol")
                direction = signal.get("direction", "")
                entry = signal.get("entry")
                sl = signal.get("sl")
                tps = signal.get("tps") or []
                regime = signal.get("market_regime", "UNKNOWN")
                ml_used = signal.get("ml_used", False)
                
                result["regime_counts"][regime] = result["regime_counts"].get(regime, 0) + 1
                if ml_used:
                    result["ml_used_count"] += 1
                    
                current_price = price_map.get(symbol)

                if current_price is None or entry is None or sl is None or not tps:
                    result["unknown"] += 1
                    continue

                is_long = "LONG" in direction
                tp1 = tps[0]
                status = "OPEN"
                if is_long:
                    if current_price <= sl:
                        status = "SL_HIT"
                    elif current_price >= tp1:
                        status = "TP1_HIT"
                else:
                    if current_price >= sl:
                        status = "SL_HIT"
                    elif current_price <= tp1:
                        status = "TP1_HIT"

                if status == "TP1_HIT":
                    result["tp1_hit"] += 1
                elif status == "SL_HIT":
                    result["sl_hit"] += 1
                else:
                    result["still_open"] += 1

                elapsed_min = int((time.time() - item.get("timestamp", time.time())) / 60)
                result["items"].append({
                    "symbol": symbol,
                    "direction": direction,
                    "status": status,
                    "confidence": item.get("confidence", 0),
                    "elapsed_min": elapsed_min,
                    "regime": regime,
                    "ml_used": ml_used
                })
        except Exception as e:
            logger.error(f"خطا در بررسی وضعیت صف انتظار: {e}")
        return result


# ============================================================================
# بخش 12: توابع کمکی (Utilities) - کامل
# ============================================================================

_KLINES_CACHE: Dict[Tuple[str, str, int], Tuple[pd.DataFrame, float]] = {}
_KLINES_CACHE_TTL = 30.0
_KLINES_CACHE_MAX = 80  # FIX v24.1: prevent unbounded memory growth
_KLINES_CACHE_LOCK = threading.Lock()  # FIX v24.3: main + auto_learn thread safety
LAST_SIGNAL_TIMES = {}

def _interval_to_minutes(s: str) -> Optional[int]:
    try:
        t = s.strip().lower()
        if t.endswith("min"):
            return int(t[:-3])
        if t.endswith("m") and not t.endswith(("am", "pm")):
            return int(t[:-1])
        if t.endswith("h"):
            return int(t[:-1]) * 60
        if t.endswith("d"):
            return int(t[:-1]) * 60 * 24
        if t.endswith("w"):
            return int(t[:-1]) * 60 * 24 * 7
        return int(t) if t.isdigit() else None
    except Exception as e:
        logger.error(f"خطا در تبدیل تایم‌فریم {s}: {e}")
        return None

def get_max_hold_candles() -> int:
    minutes_per_candle = _interval_to_minutes(CONFIG.get("KLINE_INTERVAL", "15m")) or 15
    return max(1, round(CONFIG.get("MAX_HOLD_MINUTES", 45) / minutes_per_candle))

def _telegram_config(channel: str = "signal") -> tuple[str, str]:
    """channel: 'signal' (سیگنال زنده) یا 'report' (گزارش/outcome)."""
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or CONFIG.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if channel == "report":
        chat_id = (
            os.environ.get("TELEGRAM_REPORT_CHAT_ID")
            or CONFIG.get("TELEGRAM_REPORT_CHAT_ID")
            or os.environ.get("TELEGRAM_CHAT_ID")
            or CONFIG.get("TELEGRAM_CHAT_ID")
            or ""
        ).strip()
    else:
        chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or CONFIG.get("TELEGRAM_CHAT_ID") or "").strip()
    return token, chat_id


def send_telegram_message(
    text: str,
    message_type: str = "message",
    retries: int = 3,
    channel: str = "signal",
) -> bool:
    token, chat_id = _telegram_config(channel=channel)
    if not token or not chat_id:
        logger.error(f"❌ Telegram {message_type}: TOKEN یا CHAT_ID تنظیم نشده است (channel={channel})")
        return False

    payload_text = str(text)
    # Telegram sendMessage text limit is 4096 chars. Keep a safety margin.
    chunks = [payload_text[i:i+3900] for i in range(0, len(payload_text), 3900)] or [""]
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    for chunk_index, chunk in enumerate(chunks, 1):
        sent = False
        for attempt in range(1, retries + 1):
            try:
                response = requests.post(
                    url,
                    json={"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
                    timeout=20,
                )
                try:
                    body = response.json()
                except Exception:
                    body = {}
                if response.status_code == 200 and body.get("ok") is True:
                    sent = True
                    break

                description = body.get("description", response.text[:500])
                logger.error(f"❌ Telegram {message_type} | بخش {chunk_index}/{len(chunks)} | HTTP={response.status_code} | {description}")
                # 400/401/403 are deterministic; retrying won't repair them.
                if response.status_code in (400, 401, 403):
                    return False
            except requests.exceptions.Timeout:
                logger.warning(f"⚠️ Telegram {message_type}: timeout | تلاش {attempt}/{retries}")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"⚠️ Telegram {message_type}: خطای اتصال | تلاش {attempt}/{retries}: {e}")
            except Exception as e:
                logger.warning(f"⚠️ Telegram {message_type}: {e} | تلاش {attempt}/{retries}")
            if attempt < retries:
                time.sleep(2 * attempt)
        if not sent:
            logger.error(f"❌ Telegram {message_type}: بخش {chunk_index} ارسال نشد")
            return False

    logger.info(f"✅ Telegram {message_type} ارسال شد ({len(chunks)} بخش)")
    return True


def test_telegram_connection() -> bool:
    token, chat_id = _telegram_config()
    if not token or not chat_id:
        logger.error("❌ Telegram: TOKEN یا CHAT_ID تنظیم نشده است")
        return False
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=15)
        try:
            data = r.json()
        except Exception:
            data = {}
        if r.status_code != 200 or not data.get("ok"):
            desc = data.get("description", r.text[:500])
            if r.status_code == 401:
                logger.error("❌ Telegram HTTP=401 Unauthorized: این Bot Token توسط Telegram معتبر شناخته نشد. باید Token جدید از @BotFather بگیری.")
            else:
                logger.error(f"❌ اتصال Telegram Bot ناموفق | HTTP={r.status_code} | {desc}")
            return False

        bot_name = data.get("result", {}).get("username", "unknown")
        logger.info(f"✅ Bot معتبر است: @{bot_name}")

        # FIX v24.1: فقط اگر TELEGRAM_STARTUP_TEST=1 پیام واقعی بفرست (جلوگیری از spam روی restart)
        do_live_test = str(os.environ.get("TELEGRAM_STARTUP_TEST", CONFIG.get("TELEGRAM_STARTUP_TEST", "0"))).lower() in ("1", "true", "yes")
        if not do_live_test:
            logger.info("ℹ️ Startup message test skipped (set TELEGRAM_STARTUP_TEST=1 to enable)")
            report_chat = (_telegram_config(channel="report")[1] or "").strip()
            if not report_chat:
                logger.info("ℹ️ TELEGRAM_REPORT_CHAT_ID تنظیم نشده؛ گزارش‌ها به همان کانال سیگنال می‌روند")
            return True

        test = send_telegram_message(
            "🟢 Cezartrading 24 QUANT\n✅ اتصال کانال سیگنال با موفقیت تست شد.",
            message_type="startup test signal",
            retries=2,
            channel="signal",
        )
        if not test:
            logger.error("❌ Token معتبر است اما ارسال به کانال سیگنال انجام نشد؛ Chat ID و دسترسی Bot را بررسی کن")
            return False
        logger.info(f"✅ پیام تست به کانال سیگنال {chat_id} ارسال شد")

        report_token, report_chat = _telegram_config(channel="report")
        if report_chat and report_chat != chat_id:
            test_r = send_telegram_message(
                "🟢 Cezartrading 24 QUANT\n✅ اتصال کانال گزارش با موفقیت تست شد.\n(گزارش‌ها و خلاصه ۲ساعته اینجا می‌آیند)",
                message_type="startup test report",
                retries=2,
                channel="report",
            )
            if test_r:
                logger.info(f"✅ پیام تست به کانال گزارش {report_chat} ارسال شد")
            else:
                logger.warning("⚠️ کانال گزارش تنظیم شده ولی ارسال تست ناموفق بود — گزارش‌ها ممکن است نرسند")
        elif not report_chat:
            logger.info("ℹ️ TELEGRAM_REPORT_CHAT_ID تنظیم نشده؛ گزارش‌ها به همان کانال سیگنال می‌روند")
        return True

    except requests.exceptions.Timeout:
        logger.error("❌ Telegram getMe timeout؛ اتصال اینترنت/VPN را بررسی کن")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"❌ Telegram connection error: {e}")
    except Exception as e:
        logger.error(f"❌ خطا در تست Telegram Bot: {e}")
    return False


def send_telegram_message_with_cooldown(symbol: str, direction: str, text: str, cooldown: int = 600) -> bool:
    global LAST_SIGNAL_TIMES
    now = time.time()
    key = f"{symbol.upper()}_{direction.upper()}"
    if now - LAST_SIGNAL_TIMES.get(key, 0) < cooldown:
        return False
    sent = send_telegram_message(text, message_type=f"signal {symbol} {direction}")
    if sent:
        LAST_SIGNAL_TIMES[key] = now
    return sent

TELEGRAM_DELIVERY_STATS = {"ATTEMPT": 0, "SENT": 0, "COOLDOWN": 0, "CONFIG_MISSING": 0, "FAILED": 0, "EXCEPTION": 0}


# ---------------------------------------------------------------------------
# کارت سیگنال گرافیکی — فونت اجباری (دانلود یک‌بار اگر روی سرور نبود)
# ---------------------------------------------------------------------------
_EMBEDDED_SIGNAL_FONT_B64 = None  # moved to assets/DejaVuSans-Bold.ttf (FIX v24: no more 2MB inline base64)
_SIGNAL_FONT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "DejaVuSans-Bold.ttf")


_SIGNAL_FONT_PATH = None
_SIGNAL_FONT_LOCK = threading.Lock()

def _ensure_signal_font_file() -> Optional[str]:
    """مسیر TTF Bold: ۱) assets کنار کد ۲) کش DATA_DIR ۳) سیستم ۴) دانلود.
    FIX v24: فونت ۲MB base64 از سورس حذف شد → assets/DejaVuSans-Bold.ttf
    """
    global _SIGNAL_FONT_PATH
    if _SIGNAL_FONT_PATH and os.path.exists(_SIGNAL_FONT_PATH) and os.path.getsize(_SIGNAL_FONT_PATH) > 10000:
        return _SIGNAL_FONT_PATH
    with _SIGNAL_FONT_LOCK:
        if _SIGNAL_FONT_PATH and os.path.exists(_SIGNAL_FONT_PATH) and os.path.getsize(_SIGNAL_FONT_PATH) > 10000:
            return _SIGNAL_FONT_PATH

        # 1) bundled assets next to this file (preferred)
        for candidate in (
            _SIGNAL_FONT_FILE,
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "DejaVuSans-Bold.ttf"),
            os.path.join(os.getcwd(), "assets", "DejaVuSans-Bold.ttf"),
        ):
            if candidate and os.path.exists(candidate) and os.path.getsize(candidate) > 10000:
                _SIGNAL_FONT_PATH = candidate
                return candidate

        font_dir = os.path.join(DATA_DIR, "fonts")
        try:
            os.makedirs(font_dir, exist_ok=True)
        except Exception:
            font_dir = "/tmp/cezar_fonts"
            os.makedirs(font_dir, exist_ok=True)
        dest = os.path.join(font_dir, "DejaVuSans-Bold.ttf")

        # 2) already cached in DATA_DIR
        if os.path.exists(dest) and os.path.getsize(dest) > 10000:
            _SIGNAL_FONT_PATH = dest
            return dest

        # 3) system fonts
        for pth in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        ):
            if os.path.exists(pth) and os.path.getsize(pth) > 10000:
                _SIGNAL_FONT_PATH = pth
                return pth

        # 4) last resort download
        urls = [
            "https://cdn.jsdelivr.net/gh/dejavu-fonts/dejavu-fonts@version_2_37/ttf/DejaVuSans-Bold.ttf",
            "https://github.com/dejavu-fonts/dejavu-fonts/raw/version_2_37/ttf/DejaVuSans-Bold.ttf",
        ]
        for url in urls:
            try:
                r = requests.get(url, timeout=30)
                if r.status_code == 200 and len(r.content) > 10000:
                    with open(dest, "wb") as f:
                        f.write(r.content)
                    _SIGNAL_FONT_PATH = dest
                    logger.info(f"✅ Signal font downloaded: {dest}")
                    return dest
            except Exception as e:
                logger.warning(f"font download failed: {e}")

        logger.error("❌ No TrueType font — card disabled, text fallback")
        return None


def _signal_gif_font(size: int, bold: bool = False):
    """همیشه TrueType واقعی؛ هرگز load_default (که روی Railway متن را محو می‌کند)."""
    if not PIL_AVAILABLE:
        return None
    path = _ensure_signal_font_file()
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception as e:
            logger.warning(f"truetype load failed: {e}")
    # آخرین تلاش: هر فونت سیستمی
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _signal_gif_fmt_price(x) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    if abs(v) >= 1000:
        return f"{v:.2f}"
    if abs(v) >= 1:
        return f"{v:.4f}".rstrip("0").rstrip(".")
    s = f"{v:.8f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _draw_text_bold(d, xy, text, font, fill):
    """کانتور مشکی ضخیم + متن روشن — مقاوم در برابر فشرده‌سازی تلگرام."""
    x, y = xy
    for dx in (-2, -1, 0, 1, 2):
        for dy in (-2, -1, 0, 1, 2):
            if dx == 0 and dy == 0:
                continue
            d.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0))
    d.text((x, y), text, font=font, fill=fill)


def render_signal_gif(summary: dict, out_path: Optional[str] = None) -> Optional[str]:
    """ساخت GIF پالس‌دار با متن درشت و کنتراست بالا (خوانا در موبایل)."""
    if not PIL_AVAILABLE:
        return None
    try:
        # رزولوشن بالاتر → بعد از فشرده‌سازی تلگرام هنوز خوانا بماند
        W, H = 720, 1100
        n_frames = int(CONFIG.get("SIGNAL_GIF_FRAMES", 10))
        frame_ms = int(CONFIG.get("SIGNAL_GIF_FRAME_MS", 100))
        symbol = str(summary.get("symbol") or "?").upper()
        direction = str(summary.get("direction") or "LONG").upper()
        if direction in ("BUY", "L"):
            direction = "LONG"
        elif direction in ("SELL", "S"):
            direction = "SHORT"
        entry = summary.get("entry", summary.get("price", 0))
        sl = summary.get("sl", 0)
        tps = list(summary.get("tps") or [])
        while len(tps) < 3:
            tps.append(None)
        conf = max(0.0, min(10.0, float(summary.get("confidence") or 0)))
        regime = str(summary.get("market_regime") or "—").upper()
        is_long = direction == "LONG"

        def lerp(a, b, t):
            return int(a + (b - a) * t)

        def pulse(t, lo=0.45, hi=1.0):
            s = 0.5 - 0.5 * math.cos(2 * math.pi * t)
            return lo + (hi - lo) * s

        f_title = _signal_gif_font(52, True)
        f_sym = _signal_gif_font(56, True)
        f_label = _signal_gif_font(30, True)
        f_val = _signal_gif_font(34, True)

        WHITE = (255, 255, 255)
        LABEL = (200, 210, 220)
        entry_s = _signal_gif_fmt_price(entry)
        sl_s = _signal_gif_fmt_price(sl)
        tp_s = [_signal_gif_fmt_price(x) if x is not None else "—" for x in tps[:3]]

        # رنگ اعداد ثابت و روشن (فقط آیکون‌ها پالس می‌کنند)
        if is_long:
            val_colors = [
                WHITE,
                (255, 110, 110),   # SL
                (80, 255, 160),    # TP1
                (80, 255, 160),
                (80, 255, 160),
            ]
            icon_base = [
                (80, 170, 255),
                (255, 70, 70),
                (0, 230, 140),
                (0, 210, 130),
                (0, 190, 120),
            ]
        else:
            val_colors = [
                WHITE,
                (110, 255, 140),
                (255, 110, 110),
                (255, 110, 110),
                (255, 110, 110),
            ]
            icon_base = [
                (80, 170, 255),
                (0, 220, 120),
                (255, 70, 70),
                (240, 70, 70),
                (220, 70, 70),
            ]
        labels = ["Entry", "Stop Loss", "TP1", "TP2", "TP3"]
        values = [entry_s, sl_s, tp_s[0], tp_s[1], tp_s[2]]

        frames = []
        for i in range(n_frames):
            t = i / max(1, n_frames)
            p = pulse(t)
            p2 = pulse((t + 0.33) % 1)
            p3 = pulse((t + 0.66) % 1)
            phases = [p2, p, p, p2, p3]

            img = Image.new("RGB", (W, H), (10, 12, 16))
            d = ImageDraw.Draw(img)

            outline = (0, lerp(80, 220, p3), lerp(100, 160, p3)) if is_long else (lerp(80, 220, p3), lerp(40, 90, p3), lerp(40, 90, p3))
            d.rounded_rectangle([28, 32, W - 28, H - 32], radius=40, fill=(16, 20, 28), outline=outline, width=4)

            # بج جهت — متن سفید تا بعد از فشرده‌سازی محو نشود
            if is_long:
                badge_col = (0, lerp(160, 255, p), lerp(100, 190, p))
            else:
                badge_col = (lerp(170, 255, p), lerp(50, 100, p), lerp(50, 100, p))
            badge_txt = (255, 255, 255)
            d.rounded_rectangle([W // 2 - 100, 60, W // 2 + 100, 125], radius=28, fill=badge_col)
            tw = d.textlength(direction, font=f_title)
            _draw_text_bold(d, ((W - tw) / 2, 70), direction, f_title, badge_txt)

            # نماد — سفید خالص درشت
            tw = d.textlength(symbol, font=f_sym)
            _draw_text_bold(d, ((W - tw) / 2, 150), symbol, f_sym, WHITE)

            d.line([80, 230, W - 80, 230], fill=outline, width=3)

            y = 260
            for idx in range(5):
                phase = phases[idx]
                icon_col = tuple(max(0, min(255, int(c * (0.55 + 0.45 * phase)))) for c in icon_base[idx])
                d.rounded_rectangle([55, y - 6, W - 55, y + 62], radius=18, fill=(28, 32, 42))

                r, cx, cy = 18, 100, y + 28
                for g in range(3, 0, -1):
                    col = tuple(max(0, min(255, int(c * (0.3 + 0.25 * g * phase)))) for c in icon_col)
                    d.ellipse([cx - r - g * 4, cy - r - g * 4, cx + r + g * 4, cy + r + g * 4], outline=col, width=2)
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=icon_col)

                _draw_text_bold(d, (140, y + 12), labels[idx], f_label, LABEL)
                tw = d.textlength(values[idx], font=f_val)
                _draw_text_bold(d, (W - 70 - tw, y + 10), values[idx], f_val, val_colors[idx])
                y += 90

            # Confidence
            d.line([80, y + 8, W - 80, y + 8], fill=(50, 58, 70), width=2)
            y += 28
            _draw_text_bold(d, (80, y), "Confidence", f_label, LABEL)
            conf_s = f"{conf:.1f}/10"
            tw = d.textlength(conf_s, font=f_val)
            conf_col = (100, 255, 180) if is_long else (255, 140, 140)
            _draw_text_bold(d, (W - 80 - tw, y), conf_s, f_val, conf_col)

            bar_y = y + 48
            d.rounded_rectangle([80, bar_y, W - 80, bar_y + 22], radius=11, fill=(35, 42, 52))
            fill_w = int((W - 160) * (conf / 10.0))
            bar_col = (0, lerp(160, 255, p3), lerp(120, 200, p3)) if is_long else (lerp(160, 255, p3), lerp(70, 130, p3), lerp(70, 130, p3))
            if fill_w > 0:
                d.rounded_rectangle([80, bar_y, 80 + fill_w, bar_y + 22], radius=11, fill=bar_col)
                shim_x = 80 + int(max(0, fill_w - 36) * t)
                d.rectangle(
                    [shim_x, bar_y + 3, min(80 + fill_w, shim_x + 28), bar_y + 19],
                    fill=(220, 255, 240) if is_long else (255, 220, 220),
                )

            y = bar_y + 50
            _draw_text_bold(d, (80, y), "Regime", f_label, LABEL)
            tw = d.textlength(regime, font=f_val)
            reg_col = (100, 255, 180) if is_long else (255, 150, 150)
            _draw_text_bold(d, (W - 80 - tw, y), regime, f_val, reg_col)

            frames.append(img)

        if not out_path:
            gif_dir = os.path.join(DATA_DIR, "signal_gifs")
            os.makedirs(gif_dir, exist_ok=True)
            out_path = os.path.join(gif_dir, f"signal_{symbol}_{direction}_{int(time.time() * 1000)}.gif")

        # quantize با پالت مشترک + بدون dither تا سفید/سبز/قرمز محو نشوند
        master = frames[0].quantize(colors=256, method=Image.FASTOCTREE, dither=Image.NONE)
        quantized = [master]
        for fr in frames[1:]:
            quantized.append(
                fr.quantize(colors=256, method=Image.FASTOCTREE, palette=master, dither=Image.NONE)
            )
        quantized[0].save(
            out_path,
            save_all=True,
            append_images=quantized[1:],
            duration=frame_ms,
            loop=0,
            optimize=False,
            disposal=2,
        )
        return out_path
    except Exception as e:
        logger.warning(f"render_signal_gif failed: {e}")
        return None


def render_signal_card_png(summary: dict, out_path: Optional[str] = None) -> Optional[str]:
    """کارت سیگنال PNG باکیفیت (خوانا در تلگرام) — یک فریم ثابت."""
    if not PIL_AVAILABLE:
        return None
    try:
        font_path = _ensure_signal_font_file()
        if not font_path:
            logger.error("render_signal_card_png: no TTF font — skip card, text fallback")
            return None

        W, H = 720, 1100
        symbol = str(summary.get("symbol") or "?").upper()
        direction = str(summary.get("direction") or "LONG").upper()
        if direction in ("BUY", "L"):
            direction = "LONG"
        elif direction in ("SELL", "S"):
            direction = "SHORT"
        entry = summary.get("entry", summary.get("price", 0))
        sl = summary.get("sl", 0)
        tps = list(summary.get("tps") or [])
        while len(tps) < 3:
            tps.append(None)
        conf = max(0.0, min(10.0, float(summary.get("confidence") or 0)))
        regime = str(summary.get("market_regime") or "—").upper()
        is_long = direction == "LONG"

        f_title = ImageFont.truetype(font_path, 56)
        f_sym = ImageFont.truetype(font_path, 58)
        f_label = ImageFont.truetype(font_path, 32)
        f_val = ImageFont.truetype(font_path, 36)
        WHITE = (255, 255, 255)
        LABEL = (220, 228, 240)

        entry_s = _signal_gif_fmt_price(entry)
        sl_s = _signal_gif_fmt_price(sl)
        tp_s = [_signal_gif_fmt_price(x) if x is not None else "—" for x in tps[:3]]

        if is_long:
            val_colors = [WHITE, (255, 100, 100), (90, 255, 170), (90, 255, 170), (90, 255, 170)]
            icon_cols = [(90, 180, 255), (255, 70, 70), (0, 230, 140), (0, 210, 130), (0, 190, 120)]
            outline = (0, 210, 150)
            badge_col = (0, 220, 150)
            bar_col = (0, 230, 160)
            conf_col = (100, 255, 180)
        else:
            val_colors = [WHITE, (100, 255, 140), (255, 100, 100), (255, 100, 100), (255, 100, 100)]
            icon_cols = [(90, 180, 255), (0, 220, 120), (255, 70, 70), (240, 70, 70), (220, 70, 70)]
            outline = (220, 80, 80)
            badge_col = (230, 70, 70)
            bar_col = (230, 90, 90)
            conf_col = (255, 150, 150)

        labels = ["Entry", "Stop Loss", "TP1", "TP2", "TP3"]
        values = [entry_s, sl_s, tp_s[0], tp_s[1], tp_s[2]]

        img = Image.new("RGB", (W, H), (10, 12, 16))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([28, 32, W - 28, H - 32], radius=40, fill=(16, 20, 28), outline=outline, width=4)
        d.rounded_rectangle([W // 2 - 100, 60, W // 2 + 100, 125], radius=28, fill=badge_col)
        tw = d.textlength(direction, font=f_title)
        _draw_text_bold(d, ((W - tw) / 2, 70), direction, f_title, WHITE)
        tw = d.textlength(symbol, font=f_sym)
        _draw_text_bold(d, ((W - tw) / 2, 150), symbol, f_sym, WHITE)
        d.line([80, 230, W - 80, 230], fill=outline, width=3)

        y = 260
        for idx in range(5):
            d.rounded_rectangle([55, y - 6, W - 55, y + 62], radius=18, fill=(28, 32, 42))
            r, cx, cy = 18, 100, y + 28
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=icon_cols[idx])
            _draw_text_bold(d, (140, y + 12), labels[idx], f_label, LABEL)
            tw = d.textlength(values[idx], font=f_val)
            _draw_text_bold(d, (W - 70 - tw, y + 10), values[idx], f_val, val_colors[idx])
            y += 90

        d.line([80, y + 8, W - 80, y + 8], fill=(50, 58, 70), width=2)
        y += 28
        _draw_text_bold(d, (80, y), "Confidence", f_label, LABEL)
        conf_s = f"{conf:.1f}/10"
        tw = d.textlength(conf_s, font=f_val)
        _draw_text_bold(d, (W - 80 - tw, y), conf_s, f_val, conf_col)
        bar_y = y + 48
        d.rounded_rectangle([80, bar_y, W - 80, bar_y + 22], radius=11, fill=(35, 42, 52))
        fill_w = int((W - 160) * (conf / 10.0))
        if fill_w > 0:
            d.rounded_rectangle([80, bar_y, 80 + fill_w, bar_y + 22], radius=11, fill=bar_col)
        y = bar_y + 50
        _draw_text_bold(d, (80, y), "Regime", f_label, LABEL)
        tw = d.textlength(regime, font=f_val)
        _draw_text_bold(d, (W - 80 - tw, y), regime, f_val, conf_col)

        if not out_path:
            card_dir = os.path.join(DATA_DIR, "signal_gifs")
            os.makedirs(card_dir, exist_ok=True)
            out_path = os.path.join(card_dir, f"signal_{symbol}_{direction}_{int(time.time() * 1000)}.png")
        img.save(out_path, format="PNG", optimize=False)
        return out_path
    except Exception as e:
        logger.warning(f"render_signal_card_png failed: {e}")
        return None


def render_6h_report_card(
    data: dict,
    since_ts: float,
    until_ts: float,
    out_path: Optional[str] = None,
) -> Optional[str]:
    """کارت تصویری خلاصه ۶ ساعته — استایل تیره شبیه نمونه عمومی."""
    if not PIL_AVAILABLE:
        return None
    try:
        font_path = _ensure_signal_font_file()
        paths_try = [font_path] if font_path else []
        paths_try += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        fp = next((p for p in paths_try if p and os.path.exists(p)), None)
        if not fp:
            logger.error("render_6h_report_card: no font")
            return None

        def F(sz):
            return ImageFont.truetype(fp, sz)

        f_title, f_sub, f_big, f_num, f_lab, f_small = F(34), F(20), F(48), F(32), F(18), F(15)
        W, H = 900, 1100
        bg, card = (12, 16, 28), (22, 28, 44)
        accent, red, yellow = (0, 210, 140), (255, 90, 90), (255, 190, 70)
        muted, white = (140, 150, 170), (240, 244, 250)

        n_sent = int(data.get("n_sent") or 0)
        n_closed = int(data.get("closed") or 0)
        n_open = int(data.get("n_open") or 0)
        n_win = int(data.get("n_win") or 0)
        n_sl = int(data.get("n_sl") or 0)
        n_to = int(data.get("n_timeout") or 0)
        decided = int(data.get("decided") or 0)
        wr_def = float(data.get("wr_decided") or 0.0)
        wr_all = float(data.get("wr_all_closed") or 0.0)
        to_tp = int(data.get("n_to_toward_tp") or 0)
        to_sl = int(data.get("n_to_toward_sl") or 0)
        to_flat = int(data.get("n_to_flat") or 0)

        start_txt = time.strftime("%H:%M", time.localtime(since_ts))
        end_txt = time.strftime("%H:%M", time.localtime(until_ts))
        date_txt = time.strftime("%Y-%m-%d", time.localtime(until_ts))
        wr_txt = f"{wr_def:.1f}%" if decided else "—"
        wr_color = accent if (decided and wr_def >= 70) else (yellow if decided and wr_def >= 50 else red)

        img = Image.new("RGB", (W, H), bg)
        d = ImageDraw.Draw(img)

        d.rounded_rectangle([30, 30, W - 30, 160], radius=20, fill=card)
        d.text((55, 50), "CEZARTRADING", fill=accent, font=f_title)
        d.text((55, 100), "6-Hour Performance Report", fill=muted, font=f_sub)
        d.text((W - 300, 55), f"{start_txt} — {end_txt}", fill=white, font=f_sub)
        d.text((W - 300, 90), date_txt, fill=muted, font=f_small)

        sum_closed = float(data.get("sum_return_closed_pct") or 0.0)
        sum_decided = float(data.get("sum_return_decided_pct") or 0.0)
        avg_closed = float(data.get("avg_return_closed_pct") or 0.0)
        pnl_color = accent if sum_closed >= 0 else red

        d.rounded_rectangle([30, 185, W - 30, 400], radius=20, fill=card)
        d.text((55, 205), "Win Rate (closed definitive)", fill=muted, font=f_lab)
        d.text((55, 235), wr_txt, fill=wr_color, font=f_big)
        d.text((300, 255), f"{n_win} TP  /  {n_sl} SL", fill=white, font=f_num)
        if n_closed:
            d.text((55, 305), f"With TIMEOUT:  {wr_all:.1f}%   ({n_win} / {n_closed})", fill=muted, font=f_sub)
            d.text((55, 340), f"Sum PnL (closed):  {sum_closed:+.2f}%", fill=pnl_color, font=f_sub)
            d.text((55, 368), f"Avg / trade:  {avg_closed:+.2f}%   |   TP/SL only:  {sum_decided:+.2f}%", fill=muted, font=f_small)
        else:
            d.text((55, 320), "With TIMEOUT / PnL:  —", fill=muted, font=f_sub)

        boxes = [
            (30, 405, 290, 560, "Sent", str(n_sent), white),
            (310, 405, 570, 560, "Closed", str(n_closed), white),
            (590, 405, 870, 560, "Still Open", str(n_open), yellow),
            (30, 580, 290, 735, "TP1+", str(n_win), accent),
            (310, 580, 570, 735, "SL", str(n_sl), red),
            (590, 580, 870, 735, "TIMEOUT", str(n_to), yellow),
        ]
        for x1, y1, x2, y2, lab, val, col in boxes:
            d.rounded_rectangle([x1, y1, x2, y2], radius=16, fill=card)
            d.text((x1 + 24, y1 + 28), lab, fill=muted, font=f_lab)
            d.text((x1 + 24, y1 + 70), val, fill=col, font=f_big)

        d.rounded_rectangle([30, 760, W - 30, 980], radius=20, fill=card)
        d.text((55, 790), "Notes", fill=muted, font=f_lab)
        if n_to:
            d.text((55, 830), f"• TIMEOUT: {to_tp} toward TP, {to_sl} toward SL, {to_flat} flat", fill=white, font=f_sub)
        else:
            d.text((55, 830), "• No TIMEOUT in this window", fill=white, font=f_sub)
        d.text((55, 870), "• Algorithmic futures signals (15m)", fill=white, font=f_sub)
        d.text((55, 910), "• Not financial advice — capital at risk", fill=muted, font=f_sub)
        d.text((55, 1020), "LEVEL 5 AUTONOMOUS  •  Public Results", fill=muted, font=f_small)

        if not out_path:
            card_dir = os.path.join(DATA_DIR, "signal_gifs")
            os.makedirs(card_dir, exist_ok=True)
            out_path = os.path.join(card_dir, f"report_6h_{int(until_ts)}.png")
        img.save(out_path, format="PNG", optimize=False)
        return out_path
    except Exception as e:
        logger.warning(f"render_6h_report_card failed: {e}")
        return None


def send_telegram_photo(photo_path: str, caption: str = "", retries: int = 2, channel: str = "signal") -> bool:
    token, chat_id = _telegram_config(channel=channel)
    if not token or not chat_id or not photo_path or not os.path.exists(photo_path):
        return False
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    for attempt in range(1, retries + 1):
        try:
            with open(photo_path, "rb") as f:
                r = requests.post(
                    url,
                    data={"chat_id": chat_id, "caption": (caption or "")[:1024]},
                    files={"photo": f},
                    timeout=60,
                )
            body = {}
            try:
                body = r.json()
            except Exception:
                pass
            if r.status_code == 200 and body.get("ok") is True:
                return True
            logger.error(f"❌ Telegram photo [{channel}] HTTP={r.status_code} | {body.get('description', r.text[:300])}")
            if r.status_code in (400, 401, 403):
                return False
        except Exception as e:
            logger.warning(f"⚠️ Telegram photo [{channel}] attempt {attempt}: {e}")
        if attempt < retries:
            time.sleep(2 * attempt)
    return False


def send_telegram_document(doc_path: str, caption: str = "", retries: int = 2, channel: str = "signal") -> bool:
    token, chat_id = _telegram_config(channel=channel)
    if not token or not chat_id or not doc_path or not os.path.exists(doc_path):
        return False
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    for attempt in range(1, retries + 1):
        try:
            with open(doc_path, "rb") as f:
                r = requests.post(
                    url,
                    data={"chat_id": chat_id, "caption": (caption or "")[:1024]},
                    files={"document": f},
                    timeout=120,
                )
            body = {}
            try:
                body = r.json()
            except Exception:
                pass
            if r.status_code == 200 and body.get("ok") is True:
                return True
            logger.error(f"❌ Telegram document [{channel}] HTTP={r.status_code} | {body.get('description', r.text[:300])}")
            if r.status_code in (400, 401, 403):
                return False
        except Exception as e:
            logger.warning(f"⚠️ Telegram document [{channel}] attempt {attempt}: {e}")
        if attempt < retries:
            time.sleep(2 * attempt)
    return False


def run_data_backup_to_telegram_once() -> bool:
    """
    یک‌بار بک‌آپ فایل‌های مهم DATA_DIR → zip → تلگرام.
    فعال‌سازی: متغیر محیطی RUN_DATA_BACKUP=1
    بعد از دریافت فایل، حتماً Variable را 0/حذف کن.
    """
    flag = str(os.environ.get("RUN_DATA_BACKUP", "") or CONFIG.get("RUN_DATA_BACKUP", "")).strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return False

    marker = os.path.join(DATA_DIR, ".backup_sent_marker")
    # اگر بخواهی با وجود marker هم دوباره بفرستد: RUN_DATA_BACKUP_FORCE=1
    force = str(os.environ.get("RUN_DATA_BACKUP_FORCE", "")).strip().lower() in ("1", "true", "yes")
    if os.path.exists(marker) and not force:
        logger.info("ℹ️ بک‌آپ قبلاً ارسال شده (.backup_sent_marker). برای تکرار: RUN_DATA_BACKUP_FORCE=1")
        return False

    important = [
        "ml_model.joblib",
        "performance_report.json",
        "trades_archive.json",
        "feature_weights.json",
        "learned_patterns.json",
        "optimized_params.json",
        "sent_signals_log.json",
        "auto_learn_queue.json",
        "outcome_report_state.json",
        "autopilot_state.json",
        "paper_trades.json",
        "ml_training_history.json",
        "ml_decision_history.json",
        "parameter_optimization_history.json",
        "feature_weight_changes.json",
        "signal_diagnostics.json",
        "runtime_telemetry.json",
        "evolution_history.json",
        "report_history.json",
        "coin_history.json",
        "signal_history.json",
        "final_signals.json",
        "symbols_filter.json",
    ]

    import zipfile
    import tempfile

    ts = time.strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(tempfile.gettempdir(), f"jef_data_backup_{ts}.zip")
    added = 0
    total_bytes = 0
    try:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name in important:
                fp = os.path.join(DATA_DIR, name)
                if os.path.isfile(fp):
                    zf.write(fp, arcname=name)
                    added += 1
                    total_bytes += os.path.getsize(fp)
            # config_backups folder (optional, capped)
            cb = os.path.join(DATA_DIR, "config_backups")
            if os.path.isdir(cb):
                for root, _dirs, files in os.walk(cb):
                    for fn in files[:30]:
                        full = os.path.join(root, fn)
                        rel = os.path.relpath(full, DATA_DIR)
                        try:
                            zf.write(full, arcname=rel)
                            added += 1
                        except Exception:
                            pass

        size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        logger.info(f"📦 بک‌آپ آماده: {added} فایل، {size_mb:.2f} MB → {zip_path}")

        # محدودیت عملی ربات تلگرام ~50MB
        if size_mb > 48:
            logger.error(f"❌ بک‌آپ خیلی بزرگ است ({size_mb:.1f} MB). فایل‌های غیرضروری را کم کن یا از PC استفاده کن.")
            try:
                os.remove(zip_path)
            except Exception:
                pass
            return False

        caption = (
            f"🛡 JEF data backup\n"
            f"files={added} | ~{size_mb:.2f} MB\n"
            f"DATA_DIR={DATA_DIR}\n"
            f"time={ts}\n"
            f"Save this file. Then set RUN_DATA_BACKUP=0"
        )

        ok = False
        for ch in ("signal", "report"):
            if send_telegram_document(zip_path, caption=caption, channel=ch):
                ok = True
                logger.info(f"✅ بک‌آپ به کانال {ch} ارسال شد")

        if ok:
            try:
                with open(marker, "w", encoding="utf-8") as f:
                    f.write(ts + "\n")
            except Exception:
                pass
            print(f"✅ بک‌آپ داده به تلگرام ارسال شد ({added} فایل، {size_mb:.2f} MB)")
        else:
            print("❌ ارسال بک‌آپ به تلگرام ناموفق بود")

        try:
            os.remove(zip_path)
        except Exception:
            pass
        return ok
    except Exception as e:
        logger.error(f"❌ run_data_backup_to_telegram_once: {e}")
        print(f"❌ بک‌آپ ناموفق: {e}")
        try:
            if os.path.exists(zip_path):
                os.remove(zip_path)
        except Exception:
            pass
        return False


def send_telegram_animation(gif_path: str, caption: str = "", retries: int = 2) -> bool:
    token, chat_id = _telegram_config(channel="signal")
    if not token or not chat_id or not gif_path or not os.path.exists(gif_path):
        return False
    url = f"https://api.telegram.org/bot{token}/sendAnimation"
    for attempt in range(1, retries + 1):
        try:
            with open(gif_path, "rb") as f:
                r = requests.post(
                    url,
                    data={"chat_id": chat_id, "caption": caption or ""},
                    files={"animation": f},
                    timeout=60,
                )
            body = {}
            try:
                body = r.json()
            except Exception:
                pass
            if r.status_code == 200 and body.get("ok") is True:
                return True
            logger.error(f"❌ Telegram animation HTTP={r.status_code} | {body.get('description', r.text[:300])}")
            if r.status_code in (400, 401, 403):
                return False
        except Exception as e:
            logger.warning(f"⚠️ Telegram animation attempt {attempt}: {e}")
        if attempt < retries:
            time.sleep(2 * attempt)
    return False


def deliver_signal_to_telegram(summary: dict, source: str = "normal") -> str:
    symbol = str(summary.get("symbol", "")).upper()
    direction = str(summary.get("direction", "UNKNOWN"))
    token, chat_id = _telegram_config(channel="signal")
    TELEGRAM_DELIVERY_STATS["ATTEMPT"] += 1
    if not token or not chat_id:
        TELEGRAM_DELIVERY_STATS["CONFIG_MISSING"] += 1
        logger.error(f"❌ Telegram delivery | source={source} | {symbol} | CONFIG_MISSING")
        return "CONFIG_MISSING"
    key = f"{symbol}_{direction.upper()}"
    now = time.time()
    # کول‌داون کوتاه‌تر + استثنای confidence خیلی بالا (فرصت قوی را از دست نده)
    cooldown = int(CONFIG.get("SIGNAL_COOLDOWN_SECONDS", 320))
    last_ts = float(LAST_SIGNAL_TIMES.get(key, 0) or 0)
    elapsed = now - last_ts
    conf = float(summary.get("confidence") or 0)
    # اگر اطمینان ≥ 6.4 باشد، کول‌داون را تا 55% کوتاه کن
    effective_cd = cooldown
    if conf >= 6.4:
        effective_cd = max(120, int(cooldown * 0.55))
    elif conf >= 6.0:
        effective_cd = max(150, int(cooldown * 0.75))
    if elapsed < effective_cd:
        TELEGRAM_DELIVERY_STATS["COOLDOWN"] += 1
        logger.info(
            f"⏳ Telegram delivery | source={source} | {symbol} {direction} | "
            f"COOLDOWN ({elapsed:.0f}s/{effective_cd}s conf={conf:.1f})"
        )
        return "COOLDOWN"
    try:
        ml_tag = " 🤖+ML" if summary.get("ml_used", False) else ""
        regime_tag = f" [{summary.get('market_regime', 'UNKNOWN')}]"
        line = f"{symbol}{regime_tag}{ml_tag}\n\n📊 {direction}\n\n"
        line += f"🎯 ENTRY: {summary.get('entry')}\n🛑 SL: {summary.get('sl')}\n"
        for i, tp in enumerate(summary.get("tps", [])[:3]):
            line += f"🎯 TP{i+1}: {tp}\n"
        line += f"🎓 اطمینان: {float(summary.get('confidence', 0)):.1f}/10"

        sent = False
        media_path = None
        # پیش‌فرض: PNG خوانا (تلگرام GIF را خراب می‌کند)
        # برای GIF دوباره: SIGNAL_CARD_MODE=gif
        card_mode = str(CONFIG.get("SIGNAL_CARD_MODE", "png")).lower()
        use_card = bool(CONFIG.get("SIGNAL_GIF_ENABLED", True)) and PIL_AVAILABLE
        if use_card:
            try:
                if card_mode == "gif":
                    media_path = render_signal_gif(summary)
                    if media_path:
                        sent = send_telegram_animation(media_path, caption="")
                else:
                    media_path = render_signal_card_png(summary)
                    if media_path:
                        sent = send_telegram_photo(media_path, caption="")
            except Exception as card_err:
                logger.warning(f"Signal card failed, fallback to text: {card_err}")
                sent = False
            finally:
                if media_path:
                    try:
                        os.remove(media_path)
                    except OSError:
                        pass

        if not sent:
            sent = send_telegram_message(line, message_type=f"signal {symbol} {direction}", channel="signal")

        if sent:
            LAST_SIGNAL_TIMES[key] = now
            TELEGRAM_DELIVERY_STATS["SENT"] += 1
            try:
                _record_sent_signal(summary)
            except Exception as rec_err:
                logger.debug(f"record sent signal failed: {rec_err}")
            mode_tag = f" ({card_mode})" if use_card else ""
            logger.info(f"📨 Telegram delivery | source={source} | {symbol} {direction} | SENT{mode_tag}")
            return "SENT"
        TELEGRAM_DELIVERY_STATS["FAILED"] += 1
        logger.error(f"❌ Telegram delivery | source={source} | {symbol} {direction} | FAILED")
        return "FAILED"
    except Exception as e:
        TELEGRAM_DELIVERY_STATS["EXCEPTION"] += 1
        logger.exception(f"❌ Telegram delivery | source={source} | {symbol} | EXCEPTION: {e}")
        return "EXCEPTION"

def load_json_file(path: str):
    """FIX v24: on JSONDecodeError rename to .corrupt instead of delete (prevent data loss)."""
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return json.loads(content) if content else None
    except json.JSONDecodeError:
        logger.warning(f"فایل JSON خراب: {path}")
        try:
            corrupt = f"{path}.corrupt.{int(time.time())}"
            os.replace(path, corrupt)
            logger.warning(f"JSON corrupt archived → {corrupt}")
        except Exception as e2:
            logger.error(f"failed to archive corrupt JSON {path}: {e2}")
        return None
    except Exception as e:
        logger.error(f"خطا در خواندن {path}: {e}")
    return None

def save_json_file(path: str, obj) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        def convert(item):
            if isinstance(item, (np.integer, np.int64)):
                return int(item)
            if isinstance(item, (np.floating, np.float64)):
                return float(item)
            if isinstance(item, (np.bool_, bool)):
                return bool(item)
            if isinstance(item, (np.ndarray, pd.Series)):
                return item.tolist()
            if isinstance(item, pd.DataFrame):
                return item.to_dict(orient="records")
            if isinstance(item, dict):
                return {k: convert(v) for k, v in item.items()}
            if isinstance(item, (list, tuple)):
                return [convert(i) for i in item]
            if isinstance(item, datetime):
                return item.isoformat()
            return item
        
        return _atomic_write_json(path, convert(obj))
    except Exception as e:
        logger.error(f"خطا در ذخیره {path}: {e}")
        return False


# ============================================================================
# بخش 13: مدیریت داده (Data Management) - کامل
# ============================================================================

def load_history() -> dict:
    data = load_json_file(PATHS["HISTORY_FILE"])
    return data if isinstance(data, dict) else {}

def save_history(history: dict) -> None:
    save_json_file(PATHS["HISTORY_FILE"], history)

_HISTORY_LAST_SAVE = 0.0

def update_history_with_coins(history: dict, coins: List[dict]) -> None:
    global _HISTORY_LAST_SAVE
    try:
        now = int(time.time())
        for coin in coins:
            symbol = coin.get("symbol", "").lower()
            if not symbol:
                continue
            try:
                price = float(coin.get("current_price") or 0.0)
            except Exception:
                price = 0.0
            change_1h = coin.get("price_change_percentage_1h")
            
            if symbol not in history:
                history[symbol] = []
            
            history[symbol].append({
                "time": now,
                "price": price,
                "change_1h": change_1h,
            })
            
            history[symbol] = [x for x in history[symbol] if now - x.get("time", 0) <= 14400]
        
        now_hs = time.time()
        if now_hs - _HISTORY_LAST_SAVE >= 60:
            save_history(history)
            _HISTORY_LAST_SAVE = now_hs
    except Exception as e:
        logger.error(f"خطا در به‌روزرسانی تاریخچه: {e}")

def get_change_from_history(history: dict, symbol: str, interval_seconds: int) -> Optional[float]:
    try:
        key = symbol.lower()
        if key not in history or not history[key]:
            return None
        
        now = int(time.time())
        entries = sorted(history[key], key=lambda x: x.get("time", 0))
        target_time = now - interval_seconds
        
        past_entry = None
        for entry in entries:
            if entry.get("time", 0) <= target_time:
                past_entry = entry
        
        if not past_entry:
            return None
        
        price_now = entries[-1].get("price", 0.0)
        price_past = past_entry.get("price", 0.0)
        
        if not price_now or not price_past or price_past <= 0:
            return None
        
        return ((price_now - price_past) / price_past) * 100.0
    except Exception as e:
        logger.error(f"خطا در محاسبه تغییر {symbol}: {e}")
        return None

def fetch_binance_all_ticker() -> List[dict]:
    """دریافت تیکر با retry و backoff برای 418/429."""
    last_err = None
    for attempt in range(4):
        try:
            resp = requests.get("https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=30)
            if resp.status_code in (418, 429):
                wait = min(30, (2 ** attempt) * 2 + (attempt * 0.5))
                logger.warning(f"Rate limit/418 از بایننس (status={resp.status_code}) — صبر {wait:.1f}s")
                time.sleep(wait)
                last_err = f"status={resp.status_code}"
                continue
            resp.raise_for_status()
            data = resp.json()
            ret = []
            for d in data:
                sym = d.get("symbol", "")
                if not sym.endswith("USDT"):
                    continue
                try:
                    last = float(d.get("lastPrice", 0.0))
                except Exception:
                    last = 0.0
                try:
                    change_pct = float(d.get("priceChangePercent", 0.0))
                except Exception:
                    change_pct = 0.0
                ret.append({
                    "symbol": sym.upper(),
                    "current_price": last,
                    "price_change_percentage_1h": change_pct,
                })
            logger.debug(f"{len(ret)} تیکر USDT دریافت شد")
            return ret
        except Exception as e:
            last_err = e
            wait = min(20, (2 ** attempt) + 1)
            logger.warning(f"خطا در دریافت تیکرها (تلاش {attempt+1}/4): {e} — صبر {wait}s")
            time.sleep(wait)
    logger.error(f"خطا در دریافت تیکرها پس از retry: {last_err}")
    return []

def _validate_and_clean_klines_df(df: pd.DataFrame, interval: str) -> Optional[pd.DataFrame]:
    if df is None or df.empty:
        return None
    
    df = df.copy()
    
    if not isinstance(df.index, pd.DatetimeIndex):
        if "time" in df.columns:
            df = df.set_index(pd.to_datetime(df["time"]))
            df = df.drop(columns=["time"], errors='ignore')
        else:
            return None
    
    df = df.sort_index()
    df = df[~df.index.duplicated(keep='last')]
    
    required_cols = ["open", "high", "low", "close", "volume"]
    for c in required_cols:
        if c not in df.columns:
            logger.error(f"ستون {c} در دیتافریم وجود ندارد")
            return None
    
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df[(df["volume"] > 0) & (df["close"] > 0)]
    
    minutes = _interval_to_minutes(interval) or 15
    if minutes > 0:
        diffs = df.index.to_series().diff().dropna()
        expected_delta = pd.Timedelta(minutes=minutes)
        big_gaps = diffs[diffs > expected_delta * 3]
        if not big_gaps.empty:
            logger.debug(f"{len(big_gaps)} gap بزرگ در کندل‌های {interval}")
    
    return df

def fetch_klines_df(symbol: str, interval: str = None, limit: int = None, use_cache: bool = True) -> Optional[pd.DataFrame]:
    try:
        if interval is None:
            interval = CONFIG.get("KLINE_INTERVAL", "15m")
        if limit is None:
            limit = CONFIG.get("KLINE_LIMIT", 400)
        
        key = (symbol.upper(), interval, int(limit))
        now_ts = time.time()
        
        if use_cache:
            with _KLINES_CACHE_LOCK:
                if key in _KLINES_CACHE:
                    df_cached, ts = _KLINES_CACHE[key]
                    if now_ts - ts < _KLINES_CACHE_TTL:
                        logger.debug(f"کش برای {symbol} ({interval}) - HIT")
                        return df_cached.copy()
        
        logger.debug(f"دریافت کندل‌های {symbol} ({interval})...")
        # FIX #13: اگه REQUIRE_CLOSED_CANDLE فعاله، یه کندل اضافه می‌گیریم چون
        # قراره آخرین کندلِ هنوز باز رو (در صورت وجود) حذف کنیم و بازم به
        # تعداد limit کندلِ کامل برسیم.
        require_closed = CONFIG.get("REQUIRE_CLOSED_CANDLE", True)
        fetch_limit = limit + 1 if require_closed else limit
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol.upper()}&interval={interval}&limit={fetch_limit}"
        
        for attempt in range(3):
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                
                rows = []
                for x in data:
                    try:
                        rows.append({
                            "time": pd.to_datetime(int(x[0]), unit='ms'),
                            "open": float(x[1]),
                            "high": float(x[2]),
                            "low": float(x[3]),
                            "close": float(x[4]),
                            "volume": float(x[5]),
                            # close_time (x[6]) به میلی‌ثانیه‌ست؛ برای تشخیص
                            # اینکه آیا کندل واقعاً بسته شده یا هنوز در حال شکل‌گیریه.
                            "close_time": pd.to_datetime(int(x[6]), unit='ms') if len(x) > 6 else None,
                        })
                    except Exception:
                        continue
                
                df = pd.DataFrame(rows).set_index("time").sort_index()

                if require_closed and not df.empty and "close_time" in df.columns:
                    last_close_time = df["close_time"].iloc[-1]
                    if pd.notna(last_close_time) and last_close_time > pd.Timestamp.now("UTC").tz_localize(None):
                        # آخرین کندل هنوز بسته نشده - حذفش می‌کنیم تا هیچ تحلیلی
                        # روی داده‌ی نصفه‌کاره انجام نشه.
                        df = df.iloc[:-1]

                if "close_time" in df.columns:
                    df = df.drop(columns=["close_time"])
                if len(df) > limit:
                    df = df.tail(limit)

                df = _validate_and_clean_klines_df(df, interval)
                
                if df is not None and not df.empty:
                    with _KLINES_CACHE_LOCK:
                        _KLINES_CACHE[key] = (df.copy(), now_ts)
                        if len(_KLINES_CACHE) > _KLINES_CACHE_MAX:
                            oldest = sorted(_KLINES_CACHE.items(), key=lambda kv: kv[1][1])[:len(_KLINES_CACHE) - _KLINES_CACHE_MAX]
                            for ok, _ in oldest:
                                _KLINES_CACHE.pop(ok, None)
                    logger.debug(f"دریافت {len(df)} کندل برای {symbol}")
                    return df
                
            except requests.exceptions.HTTPError as he:
                code = getattr(getattr(he, "response", None), "status_code", None)
                if code in (418, 429) and attempt < 2:
                    wait = min(25, (2 ** attempt) * 2)
                    logger.warning(f"Klines rate limit {code} برای {symbol} — صبر {wait}s")
                    time.sleep(wait)
                elif attempt == 2:
                    logger.error(f"خطا در دریافت کندل {symbol}: {he}")
                else:
                    time.sleep(2)
            except requests.exceptions.Timeout:
                if attempt < 2:
                    logger.debug(f"تایم اوت، تلاش مجدد {attempt+2}/3...")
                    time.sleep(2)
            except Exception as e:
                if attempt == 2:
                    logger.error(f"خطا در دریافت کندل {symbol}: {e}")
                else:
                    time.sleep(2)
        
        return None
        
    except Exception as e:
        logger.error(f"خطا در fetch_klines_df {symbol}: {e}")
        return None


# ============================================================================
# بخش 14: اندیکاتورهای تکنیکال (Technical Indicators) - کامل
# ============================================================================

def sma_pd(series: pd.Series, period: int) -> pd.Series:
    if period <= 0 or len(series) < period:
        return pd.Series(index=series.index, dtype=float).fillna(series.mean() if len(series) > 0 else 0)
    return series.rolling(period, min_periods=min(period, len(series))).mean()

def ema_pd(series: pd.Series, period: int) -> pd.Series:
    if period <= 0 or len(series) == 0:
        return pd.Series(index=series.index, dtype=float).fillna(0)
    return series.ewm(span=period, adjust=False, min_periods=1).mean()

def macd_pd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = ema_pd(series, fast)
    ema_slow = ema_pd(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema_pd(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def rsi_pd(series: pd.Series, period=14) -> pd.Series:
    if len(series) < period:
        return pd.Series(index=series.index, dtype=float).fillna(50)
    
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=1).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=1).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def true_range_pd(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    if high.empty or low.empty or close.empty:
        return pd.Series(dtype=float)
    
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.fillna(tr1)

def atr_pd(high: pd.Series, low: pd.Series, close: pd.Series, period=14) -> pd.Series:
    tr = true_range_pd(high, low, close)
    return tr.ewm(alpha=1/period, adjust=False, min_periods=1).mean()

def bollinger_pd(series: pd.Series, period=20, mult=2.0):
    mid = sma_pd(series, period)
    std = series.rolling(period, min_periods=period).std()
    upper = mid + mult * std
    lower = mid - mult * std
    return upper, mid, lower

def stochastic_pd(high: pd.Series, low: pd.Series, close: pd.Series, k_period=14, d_period=3):
    lowest_low = low.rolling(k_period).min()
    highest_high = high.rolling(k_period).max()
    denom = (highest_high - lowest_low).replace(0, np.nan)
    k = 100 * (close - lowest_low) / denom
    k = k.fillna(50)
    d = k.rolling(d_period, min_periods=1).mean().fillna(50)
    return k, d

def adx_pd(high: pd.Series, low: pd.Series, close: pd.Series, period=14) -> pd.Series:
    if len(high) < period:
        return pd.Series(index=high.index, dtype=float).fillna(25)
    
    up_move = high.diff()
    down_move = -low.diff()
    
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    
    tr = true_range_pd(high, low, close)
    atr = tr.ewm(alpha=1/period, adjust=False, min_periods=1).mean()
    
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False, min_periods=1).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False, min_periods=1).mean() / atr.replace(0, np.nan))
    
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1/period, adjust=False, min_periods=1).mean()

def obv_pd(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff().fillna(0))
    return (direction * volume).fillna(0).cumsum()

def cci_pd(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    typical_price = (high + low + close) / 3.0
    sma_tp = typical_price.rolling(period, min_periods=1).mean()
    mean_dev = typical_price.rolling(period, min_periods=1).apply(
        lambda x: np.mean(np.abs(x - x.mean())), raw=True
    )
    cci = (typical_price - sma_tp) / (0.015 * mean_dev.replace(0, np.nan))
    return cci.fillna(0)

def williams_r_pd(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    highest_high = high.rolling(period, min_periods=1).max()
    lowest_low = low.rolling(period, min_periods=1).min()
    denom = (highest_high - lowest_low).replace(0, np.nan)
    wr = -100 * (highest_high - close) / denom
    return wr.fillna(-50)

def mfi_pd(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int = 14) -> pd.Series:
    typical_price = (high + low + close) / 3.0
    money_flow = typical_price * volume
    tp_diff = typical_price.diff()
    positive_flow = money_flow.where(tp_diff > 0, 0.0)
    negative_flow = money_flow.where(tp_diff < 0, 0.0)
    pos_sum = positive_flow.rolling(period, min_periods=1).sum()
    neg_sum = negative_flow.rolling(period, min_periods=1).sum()
    money_ratio = pos_sum / neg_sum.replace(0, np.nan)
    mfi = 100 - (100 / (1 + money_ratio))
    return mfi.fillna(50)

def vwap_pd(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    typical_price = (high + low + close) / 3.0
    cum_vol = volume.cumsum().replace(0, np.nan)
    cum_tp_vol = (typical_price * volume).cumsum()
    return (cum_tp_vol / cum_vol).bfill().fillna(close)

def supertrend_pd(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 10, mult: float = 3.0):
    atr = atr_pd(high, low, close, period)
    hl2 = (high + low) / 2.0
    upper_band = hl2 + mult * atr
    lower_band = hl2 - mult * atr

    n = len(close)
    final_upper = upper_band.copy()
    final_lower = lower_band.copy()
    direction = pd.Series(1, index=close.index, dtype=int)
    supertrend = pd.Series(0.0, index=close.index)

    if n == 0:
        return supertrend, direction

    close_vals = close.values
    upper_vals = final_upper.values.copy()
    lower_vals = final_lower.values.copy()
    dir_vals = np.ones(n, dtype=int)
    st_vals = np.zeros(n)

    st_vals[0] = upper_vals[0]
    for i in range(1, n):
        if close_vals[i - 1] <= upper_vals[i - 1]:
            upper_vals[i] = min(upper_vals[i], upper_vals[i - 1])
        if close_vals[i - 1] >= lower_vals[i - 1]:
            lower_vals[i] = max(lower_vals[i], lower_vals[i - 1])

        if st_vals[i - 1] == upper_vals[i - 1]:
            dir_vals[i] = -1 if close_vals[i] <= upper_vals[i] else 1
        else:
            dir_vals[i] = 1 if close_vals[i] >= lower_vals[i] else -1

        st_vals[i] = lower_vals[i] if dir_vals[i] == 1 else upper_vals[i]

    return pd.Series(st_vals, index=close.index), pd.Series(dir_vals, index=close.index)


# ============================================================================
# بخش 15: تشخیص الگوهای پرایس اکشن - کامل
# ============================================================================

def detect_price_action_signals(df: pd.DataFrame) -> List[str]:
    if df.shape[0] < 3:
        return []
    
    signals = []
    try:
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        body = abs(last["close"] - last["open"])
        total_range = max(last["high"] - last["low"], 1e-9)
        upper_wick = last["high"] - max(last["close"], last["open"])
        lower_wick = min(last["close"], last["open"]) - last["low"]
        
        if body <= 0.25 * total_range:
            if upper_wick >= 2 * body and upper_wick >= 0.3 * total_range:
                signals.append("Pin Bar - rejection بالاتر")
            if lower_wick >= 2 * body and lower_wick >= 0.3 * total_range:
                signals.append("Pin Bar - rejection پایین")
        
        if last["high"] <= prev["high"] and last["low"] >= prev["low"]:
            signals.append("Inside Bar")
        
        prev_body = abs(prev["close"] - prev["open"])
        if prev["close"] < prev["open"] and last["close"] > last["open"] and body > prev_body:
            signals.append("Engulfing صعودی")
        if prev["close"] > prev["open"] and last["close"] < last["open"] and body > prev_body:
            signals.append("Engulfing نزولی")
        
        highs = df["high"].values
        lows = df["low"].values
        
        if len(highs) >= 3:
            if highs[-1] > highs[-2] > highs[-3]:
                signals.append("Higher Highs")
            if highs[-1] < highs[-2] < highs[-3]:
                signals.append("Lower Highs")
        
        if len(lows) >= 3:
            if lows[-1] > lows[-2] > lows[-3]:
                signals.append("Higher Lows")
            if lows[-1] < lows[-2] < lows[-3]:
                signals.append("Lower Lows")
        
    except Exception as e:
        logger.error(f"خطا در تشخیص پرایس اکشن: {e}")
    
    return signals

def find_swing_levels_pd(df: pd.DataFrame, lookback: int = 8) -> dict:
    try:
        highs = df["high"].values
        lows = df["low"].values
        n = len(df)
        swings = {"highs": [], "lows": []}
        
        if n < (2 * lookback + 1):
            return swings
        
        for i in range(lookback, n - lookback):
            if highs[i] == np.max(highs[i - lookback:i + lookback + 1]):
                swings["highs"].append((i, float(highs[i])))
            if lows[i] == np.min(lows[i - lookback:i + lookback + 1]):
                swings["lows"].append((i, float(lows[i])))
        
        swings["highs"] = swings["highs"][-5:]
        swings["lows"] = swings["lows"][-5:]
        return swings
    except Exception as e:
        logger.error(f"خطا در یافتن سطوح سوئینگ: {e}")
        return {"highs": [], "lows": []}

def detect_market_regime(df: pd.DataFrame) -> str:
    try:
        if df.empty or len(df) < 20:
            return "UNKNOWN"
        
        atr_ratio = (df["atr"].iloc[-1] / df["close"].iloc[-1]) if "atr" in df.columns else 0
        adx_val = adx_pd(df["high"], df["low"], df["close"]).iloc[-1] if len(df) > 14 else 0
        
        if adx_val < 20:
            return "RANGING"
        elif atr_ratio > 0.025:
            return "VOLATILE"
        else:
            return "TRENDING"
    except Exception as e:
        logger.error(f"خطا در تشخیص رژیم بازار: {e}")
        return "UNKNOWN"

def volatility_filter(df: pd.DataFrame, threshold: float = 3.0) -> bool:
    try:
        if len(df) < 20:
            return True
        
        returns = df["close"].pct_change().abs()
        volatility = returns.rolling(20).std()
        current_vol = returns.iloc[-1] if not returns.empty else 0.0
        ref_vol = volatility.iloc[-1] if not volatility.empty else 0.0
        
        if pd.isna(ref_vol) or ref_vol == 0:
            return True
        
        return current_vol <= (ref_vol * threshold)
    except Exception as e:
        logger.error(f"خطا در فیلتر نوسان: {e}")
        return True

def symbol_quality_check(symbol: str) -> bool:
    try:
        url = f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code != 200:
            return False
        
        ticker = resp.json()
        
        quote_volume = float(ticker.get("quoteVolume", 0))
        if quote_volume < CONFIG["MIN_QUOTE_VOLUME"]:
            return False
        
        bid_price = float(ticker.get("bidPrice", 0))
        ask_price = float(ticker.get("askPrice", 0))
        if bid_price > 0 and ask_price > 0:
            spread = (ask_price - bid_price) / ask_price
            if spread > CONFIG["MAX_SPREAD_PCT"]:
                return False
        
        price_change = float(ticker.get("priceChangePercent", 0))
        if abs(price_change) > CONFIG["MAX_24H_CHANGE"]:
            return False
        
        return True
    except Exception as e:
        logger.debug(f"خطا در بررسی کیفیت {symbol}: {e}")
        return False

def detect_false_breakout(df: pd.DataFrame, swing_levels: dict) -> bool:
    try:
        if len(df) < 3:
            return False
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        if swing_levels.get("highs"):
            resistance = swing_levels["highs"][-1][1]
            if prev["high"] > resistance and last["close"] < resistance:
                return True
        
        if swing_levels.get("lows"):
            support = swing_levels["lows"][-1][1]
            if prev["low"] < support and last["close"] > support:
                return True
        
        return False
    except Exception as e:
        logger.error(f"خطا در تشخیص شکست فیک: {e}")
        return False

def dynamic_risk_management(symbol: str, df: pd.DataFrame) -> float:
    try:
        if len(df) < 14 or "atr" not in df.columns:
            return CONFIG["RISK_PERCENT"]
        
        close = df["close"].iloc[-1]
        atr_val = df["atr"].iloc[-1]
        atr_percent = (atr_val / close) * 100 if close else 0.0
        
        if atr_percent > 5:
            return CONFIG["RISK_PERCENT"] * 0.5
        elif atr_percent < 1:
            return CONFIG["RISK_PERCENT"] * 1.5
        else:
            return CONFIG["RISK_PERCENT"]
    except Exception as e:
        logger.error(f"خطا در مدیریت ریسک {symbol}: {e}")
        return CONFIG["RISK_PERCENT"]


# ============================================================================
# بخش 16: توابع سیگنال و بک‌تست - کامل
# ============================================================================

def compute_confirmation_signals(df: pd.DataFrame, require_volume: bool = True) -> pd.DataFrame:
    try:
        df = df.copy()
        df["ema_s"] = ema_pd(df["close"], CONFIG["EMA_SHORT"])
        df["ema_m"] = ema_pd(df["close"], CONFIG["EMA_MED"])
        df["ema_l"] = ema_pd(df["close"], CONFIG["EMA_LONG"])
        
        df["trend_up"] = (df["ema_s"] > df["ema_m"]) & (df["ema_m"] > df["ema_l"])
        df["trend_down"] = (df["ema_s"] < df["ema_m"]) & (df["ema_m"] < df["ema_l"])
        
        df["rsi"] = rsi_pd(df["close"], CONFIG["RSI_PERIOD"])
        macd, macd_sig, _ = macd_pd(df["close"])
        df["macd"] = macd
        df["macd_sig"] = macd_sig
        
        df["momentum_pos"] = (df["rsi"] > 52) & (df["macd"] > df["macd_sig"])
        df["momentum_neg"] = (df["rsi"] < 48) & (df["macd"] < df["macd_sig"])
        
        df["vol_sma20"] = df["volume"].rolling(20, min_periods=1).mean()
        df["volume_spike"] = df["volume"] > (df["vol_sma20"] * CONFIG["MIN_VOLUME_RATIO"])

        df["adx"] = adx_pd(df["high"], df["low"], df["close"])
        df["cci"] = cci_pd(df["high"], df["low"], df["close"], CONFIG.get("CCI_PERIOD", 12))
        df["williams_r"] = williams_r_pd(df["high"], df["low"], df["close"], CONFIG.get("WILLIAMS_R_PERIOD", 10))
        df["mfi"] = mfi_pd(df["high"], df["low"], df["close"], df["volume"], CONFIG.get("MFI_PERIOD", 10))
        _, st_dir = supertrend_pd(df["high"], df["low"], df["close"],
                                   CONFIG.get("SUPERTREND_PERIOD", 8), CONFIG.get("SUPERTREND_MULT", 2.5))
        df["supertrend_dir"] = st_dir

        trending_enough = df["adx"] >= CONFIG.get("ADX_TREND_MIN", 16)

        bull_votes = (
            (df["cci"] > 0).astype(int)
            + (df["williams_r"] > -50).astype(int)
            + (df["mfi"] > 50).astype(int)
            + (df["supertrend_dir"] > 0).astype(int)
        )
        bear_votes = (
            (df["cci"] < 0).astype(int)
            + (df["williams_r"] < -50).astype(int)
            + (df["mfi"] < 50).astype(int)
            + (df["supertrend_dir"] < 0).astype(int)
        )
        df["confluence_bull"] = bull_votes >= 3
        df["confluence_bear"] = bear_votes >= 3
        
        base_long = df["trend_up"] & df["momentum_pos"] & trending_enough & df["confluence_bull"]
        base_short = df["trend_down"] & df["momentum_neg"] & trending_enough & df["confluence_bear"]
        
        if require_volume:
            df["long_confirm"] = base_long & df["volume_spike"]
            df["short_confirm"] = base_short & df["volume_spike"]
        else:
            df["long_confirm"] = base_long
            df["short_confirm"] = base_short
        
        return df[["long_confirm", "short_confirm", "adx", "cci", "williams_r", "mfi", "supertrend_dir"]]
    except Exception as e:
        logger.error(f"خطا در محاسبه سیگنال‌های تأیید: {e}")
        return pd.DataFrame({"long_confirm": [False], "short_confirm": [False]})

def backtest_symbol_realistic(symbol: str, candles: int = None) -> dict:
    try:
        if candles is None:
            candles = CONFIG["BACKTEST_CANDLES"]
        
        df = fetch_klines_df(symbol, interval=CONFIG["KLINE_INTERVAL"], limit=candles)
        if df is None or df.empty or df.shape[0] < CONFIG["BACKTEST_MIN_REQUIRED"]:
            return {"symbol": symbol, "total": 0, "wins": 0, "losses": 0, "winrate": None}
        
        df = df.copy().reset_index(drop=True)
        df["atr"] = atr_pd(df["high"], df["low"], df["close"], CONFIG["ATR_PERIOD"])

        conf = compute_confirmation_signals(df, require_volume=CONFIG.get("REQUIRE_VOLUME_SPIKE", True))
        long_signal = conf["long_confirm"].values
        short_signal = conf["short_confirm"].values
        
        atrs = df["atr"].values
        wins = losses = total = 0
        gross_returns = []
        net_returns = []
        n = len(df)
        min_idx = CONFIG["BACKTEST_MIN_REQUIRED"]
        max_hold = get_max_hold_candles()
        round_trip_commission_pct = CONFIG["COMMISSION_PCT"] * 2 * 100
        
        for i in range(min_idx, n - 1):
            atr_v = atrs[i]
            if pd.isna(atr_v) or atr_v == 0:
                continue
            
            if long_signal[i]:
                signal_direction = "LONG"
            elif short_signal[i]:
                signal_direction = "SHORT"
            else:
                continue
            
            entry_idx = i + 1
            if entry_idx >= n:
                continue
            
            entry_price = df.loc[entry_idx, "open"]
            slippage = CONFIG["SLIPPAGE_PCT"]
            
            if signal_direction == "LONG":
                entry_price = entry_price * (1 + slippage)
                sl = entry_price - CONFIG["ATR_MULT_SL"] * atr_v
                tps = [entry_price + m * atr_v for m in CONFIG["TP_ATR_MULTS"]]
            else:
                entry_price = entry_price * (1 - slippage)
                sl = entry_price + CONFIG["ATR_MULT_SL"] * atr_v
                tps = [entry_price - m * atr_v for m in CONFIG["TP_ATR_MULTS"]]
            
            result = None
            exit_price = None
            for j in range(1, max_hold + 1):
                idx = entry_idx + j
                if idx >= n:
                    break
                
                hi, lo = df.loc[idx, "high"], df.loc[idx, "low"]
                
                if signal_direction == "LONG":
                    if lo <= sl:
                        result = "loss"
                        exit_price = sl * (1 - slippage)
                        break
                    hit_tps = [tp for tp in tps if hi >= tp]
                    if hit_tps:
                        result = "win"
                        exit_price = min(hit_tps)
                        break
                else:
                    if hi >= sl:
                        result = "loss"
                        exit_price = sl * (1 + slippage)
                        break
                    hit_tps = [tp for tp in tps if lo <= tp]
                    if hit_tps:
                        result = "win"
                        exit_price = max(hit_tps)
                        break
            
            if result is None:
                exit_price = df.loc[min(entry_idx + max_hold, n - 1), "close"]
                # FIX #11: قبلاً timeout همیشه "loss" حساب می‌شد، ولی
                # _simulate_outcome (یادگیری واقعی) timeout رو بر اساس جهت
                # واقعی قیمت حساب می‌کنه؛ این ناهماهنگی backtest_winrate رو
                # سیستماتیک کمتر از واقعیت نشون می‌داد.
                if signal_direction == "LONG":
                    result = "win" if exit_price > entry_price else "loss"
                else:
                    result = "win" if exit_price < entry_price else "loss"
            
            if signal_direction == "LONG":
                gross_pct = (exit_price - entry_price) / entry_price * 100
            else:
                gross_pct = (entry_price - exit_price) / entry_price * 100
            net_pct = gross_pct - round_trip_commission_pct
            
            gross_returns.append(gross_pct)
            net_returns.append(net_pct)
            
            if result == "win":
                wins += 1
            else:
                losses += 1
            total += 1
        
        winrate = (wins / total * 100.0) if total > 0 else None
        avg_net_return = float(np.mean(net_returns)) if net_returns else None
        gross_profit = sum(r for r in net_returns if r > 0)
        gross_loss = abs(sum(r for r in net_returns if r < 0))
        net_profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else None)
        return {
            "symbol": symbol, "total": total, "wins": wins, "losses": losses, "winrate": winrate,
            "avg_net_return_pct": avg_net_return, "net_profit_factor": net_profit_factor,
        }
    except Exception as e:
        logger.error(f"خطا در بک‌تست {symbol}: {e}")
        return {"symbol": symbol, "total": 0, "wins": 0, "losses": 0, "winrate": None}

def adaptive_parameters_from_df(df: pd.DataFrame) -> dict:
    try:
        if df is None or df.empty:
            return {"ATR_MULT_SL": CONFIG["ATR_MULT_SL"]}
        
        latest = df.iloc[-1]
        atr_ratio = (latest.get("atr", np.nan) / latest.get("close", np.nan)) if latest.get("atr", np.nan) and latest.get("close", np.nan) else 0.0
        
        if pd.isna(atr_ratio):
            atr_ratio = 0.0
        
        params = {}
        if atr_ratio > CONFIG["VOLATILITY_REGIME_ATR_RATIO"]:
            params["ATR_MULT_SL"] = max(1.0, CONFIG["ATR_MULT_SL"] * 1.1)
        else:
            params["ATR_MULT_SL"] = max(0.8, CONFIG["ATR_MULT_SL"] * 0.9)
        
        return params
    except Exception as e:
        logger.error(f"خطا در تنظیم پارامترهای تطبیقی: {e}")
        return {"ATR_MULT_SL": CONFIG["ATR_MULT_SL"]}


# ============================================================================
# بخش 17: کامپوننت‌های سراسری
# ============================================================================

performance_memory = PerformanceMemory(max_size=500, short_term_size=50)
param_optimizer = AdaptiveParameterOptimizer(performance_memory)
weight_learner = FeatureWeightLearner(performance_memory)
pattern_recognizer = PatternRecognizer(performance_memory)
ml_model = MLConfidenceModel(performance_memory)
auto_learning = AutoLearningSystem(performance_memory)
self_healing_autopilot = SelfHealingAutoPilot(performance_memory)


class PortfolioRiskManager:
    """ریسک پرتفوی + سایز پوزیشن + دفتر paper (بدون سفارش واقعی صرافی)."""

    def __init__(self, memory: "PerformanceMemory"):
        self.memory = memory
        self.paper_open: list = []
        self._day_key = ""
        self._day_realized_pct = 0.0
        self._load_paper()
        self._prune_expired()

    def _paper_path(self) -> str:
        p = CONFIG.get("PAPER_TRADES_FILE") or ""
        if p:
            return p
        return os.path.join(DATA_DIR, "paper_trades.json")

    def _load_paper(self):
        try:
            path = self._paper_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    obj = json.load(f)
                self.paper_open = list(obj.get("open", []) or [])[-200:]
                self._day_key = str(obj.get("day_key") or "")
                self._day_realized_pct = float(obj.get("day_realized_pct") or 0)
        except Exception as e:
            logger.debug(f"paper load: {e}")

    def _save_paper(self):
        try:
            _atomic_write_json(self._paper_path(), {
                "open": self.paper_open[-200:],
                "day_key": self._day_key,
                "day_realized_pct": self._day_realized_pct,
                "timestamp": time.time(),
            })
        except Exception as e:
            logger.debug(f"paper save: {e}")

    def _roll_day(self):
        key = time.strftime("%Y-%m-%d", time.localtime())
        if key != self._day_key:
            self._day_key = key
            self._day_realized_pct = 0.0

    def _prune_expired(self) -> None:
        """حذف paperهای منقضی‌شده تا شمارش ریسک باد نکند."""
        try:
            max_age = float(CONFIG.get("PAPER_EXPIRE_MINUTES", 100)) * 60.0
            now = time.time()
            before = len(self.paper_open)
            self.paper_open = [
                p for p in self.paper_open
                if isinstance(p, dict) and (now - float(p.get("ts") or 0)) <= max_age
            ]
            if len(self.paper_open) != before:
                self._save_paper()
        except Exception:
            pass

    def _paper_symbols(self) -> set:
        self._prune_expired()
        return {
            str(p.get("symbol") or "").upper()
            for p in self.paper_open
            if isinstance(p, dict) and p.get("symbol")
        }

    def _queue_symbols_fresh(self) -> set:
        """فقط آیتم‌های تازهٔ صف یادگیری (نه کل تاریخچهٔ outcome)."""
        syms = set()
        max_age = float(CONFIG.get("QUEUE_RISK_MAX_AGE_SEC", 5400))
        now = time.time()
        try:
            for item in list(getattr(auto_learning, "learning_queue", []) or []):
                if not isinstance(item, dict):
                    continue
                ts = float(item.get("timestamp") or 0)
                if ts and (now - ts) > max_age:
                    continue
                s = str(item.get("symbol") or (item.get("signal") or {}).get("symbol") or "").upper()
                if s:
                    syms.add(s)
        except Exception:
            pass
        return syms

    def _unique_open_symbols(self) -> set:
        """اتحاد paper + صف تازه (برای گزارش)."""
        return self._paper_symbols() | self._queue_symbols_fresh()

    def daily_loss_breach(self) -> bool:
        self._roll_day()
        try:
            start = time.mktime(time.strptime(self._day_key, "%Y-%m-%d"))
            day_rets = [
                float(t.get("return_pct") or 0)
                for t in self.memory.trades
                if float(t.get("timestamp") or 0) >= start
            ]
            # فقط اگر نمونه کافی امروز باشد؛ وگرنه قفل نکن
            if len(day_rets) < 8:
                return False
            realized = sum(day_rets)
        except Exception:
            realized = self._day_realized_pct
        limit = -abs(float(CONFIG.get("MAX_DAILY_LOSS_PCT", 4.0)))
        return realized <= limit

    def portfolio_risk_breach(self) -> bool:
        """
        قفل ریسک فقط بر اساس paper_open واقعی.
        صف auto-learn برای outcome است و نباید موتور سیگنال را خفه کند.
        سقف تعداد باز در _portfolio_open_gate جداگانه کنترل می‌شود.
        """
        try:
            paper_syms = self._paper_symbols()
            n = len(paper_syms)
            risk_each = float(CONFIG.get("RISK_PERCENT", 0.55))
            total = n * risk_each
            return total > float(CONFIG.get("MAX_PORTFOLIO_RISK_PCT", 8.0))
        except Exception:
            return False

    def compute_notional(self, entry: float, sl: float) -> dict:
        balance = float(CONFIG.get("ACCOUNT_BALANCE", 1000.0))
        risk_pct = float(CONFIG.get("RISK_PERCENT", 0.55)) / 100.0
        lev = max(1.0, float(CONFIG.get("LEVERAGE", 10)))
        entry_f = float(entry or 0)
        sl_f = float(sl or 0)
        if entry_f <= 0 or sl_f <= 0:
            return {"notional": 0.0, "qty": 0.0, "risk_usd": 0.0, "stop_pct": 0.0}
        stop_pct = abs(entry_f - sl_f) / entry_f
        risk_usd = balance * risk_pct
        if stop_pct < 1e-6:
            notional = 0.0
        else:
            notional = risk_usd / stop_pct
        max_notional = balance * lev * 0.95
        notional = min(notional, max_notional)
        qty = notional / entry_f if entry_f > 0 else 0.0
        return {
            "notional": round(notional, 4),
            "qty": round(qty, 8),
            "risk_usd": round(risk_usd, 4),
            "stop_pct": round(stop_pct * 100, 4),
            "balance": balance,
            "leverage": lev,
        }

    def register_signal(self, summary: dict) -> dict:
        """ثبت paper position — یک رکورد per symbol (جایگزین قبلی)."""
        mode = str(CONFIG.get("EXECUTION_MODE", "paper")).lower()
        sizing = self.compute_notional(summary.get("entry"), summary.get("sl"))
        sym = str(summary.get("symbol", "")).upper()
        rec = {
            "id": summary.get("candidate_id") or f"{sym}-{int(time.time()*1000)}",
            "ts": time.time(),
            "symbol": sym,
            "direction": str(summary.get("direction", "")).upper(),
            "entry": summary.get("entry"),
            "sl": summary.get("sl"),
            "tps": summary.get("tps"),
            "confidence": summary.get("confidence"),
            "sizing": sizing,
            "mode": mode,
            "status": "OPEN",
        }
        # همیشه در paper/signal_only ثبت کن تا شمارش پرتفوی واقعی باشد
        if mode in ("paper", "signal_only") or CONFIG.get("POSITION_SIZE_FROM_RISK", True):
            self._prune_expired()
            if sym:
                self.paper_open = [p for p in self.paper_open if str(p.get("symbol") or "").upper() != sym]
            self.paper_open.append(rec)
            if len(self.paper_open) > 200:
                self.paper_open = self.paper_open[-200:]
            self._save_paper()
        summary["position_sizing"] = sizing
        summary["execution_mode"] = mode
        return rec

    def summary(self) -> dict:
        self._roll_day()
        unique = self._unique_open_symbols()
        risk_est = len(unique) * float(CONFIG.get("RISK_PERCENT", 0.55))
        return {
            "mode": CONFIG.get("EXECUTION_MODE", "paper"),
            "paper_open": len(self.paper_open),
            "unique_open": len(unique),
            "risk_est_pct": round(risk_est, 2),
            "daily_loss_breach": self.daily_loss_breach(),
            "portfolio_risk_breach": self.portfolio_risk_breach(),
            "day_key": self._day_key,
        }


portfolio_risk = PortfolioRiskManager(performance_memory)


# ============================================================================
# بخش 18: توابع بهبود سیگنال با یادگیری و ML
# ============================================================================

def self_diagnose_and_repair() -> None:
    try:
        with CONFIG_LOCK:
            min_c = float(CONFIG.get("MIN_CONFIDENCE_SCORE", 5.5))
            max_c = float(CONFIG.get("MAX_EFFECTIVE_CONFIDENCE", 6.8))
            if max_c < 5.5:
                max_c = 5.5
                CONFIG["MAX_EFFECTIVE_CONFIDENCE"] = max_c
            floor = _min_confidence_floor()
            if min_c > max_c:
                CONFIG["MIN_CONFIDENCE_SCORE"] = max_c
            elif min_c < floor:
                CONFIG["MIN_CONFIDENCE_SCORE"] = floor

            adj = dict(CONFIG.get("REGIME_CONFIDENCE_ADJUSTMENT", {}))
            for regime in ("TRENDING", "VOLATILE", "RANGING", "UNKNOWN"):
                v = float(adj.get(regime, 0.0))
                adj[regime] = round(max(0.0, min(0.50, v)), 2)
            CONFIG["REGIME_CONFIDENCE_ADJUSTMENT"] = adj

            if float(CONFIG.get("PUMP_THRESHOLD", 1.2)) < 0.6:
                CONFIG["PUMP_THRESHOLD"] = 0.6
            if float(CONFIG.get("PUMP_THRESHOLD", 1.2)) > 2.5:
                CONFIG["PUMP_THRESHOLD"] = 2.5
            CONFIG["DUMP_THRESHOLD"] = -abs(float(CONFIG["PUMP_THRESHOLD"]))

            # ML فعال/غیرفعال توسط سیستم مدیریت می‌شود
            # اگر ML_MAX_INFLUENCE صفر است، غیرفعال است
            if CONFIG.get("ML_MAX_INFLUENCE", 0.0) > 0.12:
                CONFIG["ML_MAX_INFLUENCE"] = 0.12
    except Exception as e:
        logger.error(f"Self-diagnostic failed: {e}")


# FIX #9/#10: کدهای زیر به labelهای دقیق detect_price_action_signals وابسته‌ست.
_BULLISH_PA_LABELS = ("Pin Bar - rejection پایین", "Engulfing صعودی", "Higher Highs", "Higher Lows")
_BEARISH_PA_LABELS = ("Pin Bar - rejection بالاتر", "Engulfing نزولی", "Lower Highs", "Lower Lows")


def _is_long_direction(direction_value: str) -> bool:
    return "LONG" in str(direction_value or "")


def _trend_aligned_score(trend: str, is_long: bool) -> int:
    """FIX #9: قبلاً هر روند قوی (فارغ از جهت معامله) +3 امتیاز می‌گرفت.
    الان فقط وقتی روند هم‌جهت با signal_direction باشه امتیاز کامل می‌گیره؛
    روند مخالف (counter-trend / همون سیگنال‌های ⚠️) امتیاز منفی می‌گیره
    تا این ریسک اضافه واقعاً توی confidence دیده بشه."""
    strong = "STRONG LONG" if is_long else "STRONG SHORT"
    weak = "LONG" if is_long else "SHORT"
    opposite_strong = "STRONG SHORT" if is_long else "STRONG LONG"
    opposite_weak = "SHORT" if is_long else "LONG"
    if trend == strong:
        return 3
    if trend == weak:
        return 2
    if trend == "NEUTRAL":
        return 1
    if trend == opposite_weak:
        return -1
    if trend == opposite_strong:
        return -2
    return 0


def _direction_aligned_pa_count(pa_signals: list, is_long: bool) -> int:
    """FIX #10: قبلاً هر الگوی پرایس‌اکشن (صعودی یا نزولی، فرقی نمی‌کرد) شمارش
    می‌شد. الان فقط الگوهای هم‌جهت با signal_direction امتیاز می‌گیرن."""
    aligned_labels = _BULLISH_PA_LABELS if is_long else _BEARISH_PA_LABELS
    return sum(1 for p in (pa_signals or []) if p in aligned_labels)


def calculate_signal_confidence_with_learning(signal_data: dict, current_features: dict) -> float:
    try:
        score = 0
        
        is_long = _is_long_direction(signal_data.get("direction", ""))
        trend = signal_data.get("trend", "")
        score += _trend_aligned_score(trend, is_long)
        
        if signal_data.get("confirmed", False):
            score += 2
        
        if signal_data.get("multi_tf_aligned", False):
            score += 1
        
        pa_signals = signal_data.get("pa_signals", [])
        score += min(_direction_aligned_pa_count(pa_signals, is_long), 2)
        
        backtest = signal_data.get("backtest", {})
        winrate = backtest.get("winrate", 0)
        if winrate and winrate > 55:
            score += 2
        elif winrate and winrate > 48:
            score += 1
        
        if pattern_recognizer.matches_successful_pattern(current_features):
            score += 2
        
        if pattern_recognizer.matches_failed_pattern(current_features):
            score -= 3
        
        weighted_score = weight_learner.calculate_weighted_confidence(current_features)
        n_trades = len(performance_memory.trades)
        min_t = CONFIG.get("WEIGHT_SHARPEN_MIN_TRADES", 50)
        full_t = CONFIG.get("WEIGHT_SHARPEN_FULL_TRADES", 250)
        if n_trades < min_t:
            learned_share = 0.15
        elif n_trades >= full_t:
            learned_share = 0.32
        else:
            progress = (n_trades - min_t) / max(1, (full_t - min_t))
            learned_share = 0.15 + progress * (0.32 - 0.15)
        final_score = (score * (1 - learned_share)) + (weighted_score * learned_share)
        
        # ML: فقط influence واقعی مدل (نه سقف CONFIG) اعمال می‌شود.
        # مدل PROVISIONAL با influence نزدیک صفر نباید ml_used=True بگذارد
        # وگرنه PRO gate با weak_ml_probability سیگنال‌ها را خفه می‌کند.
        signal_data["ml_used"] = False
        signal_data["ml_probability"] = None
        try:
            actual_ml_influence = float(ml_model.get_influence_weight()) if (
                ml_model is not None and getattr(ml_model, "is_trained", False)
            ) else 0.0
        except Exception:
            actual_ml_influence = 0.0
        # سقف ایمنی: هیچ‌وقت بیشتر از ML_MAX_INFLUENCE اثر ندهد
        max_cap = float(CONFIG.get("ML_MAX_INFLUENCE", 0.0) or 0.0)
        actual_ml_influence = max(0.0, min(actual_ml_influence, max_cap))

        # فقط اگر influence معنادار باشد ml_used=True تا weak_ml بی‌دلیل سیگنال نکشد
        if actual_ml_influence >= 0.015 and ml_model is not None and ml_model.is_trained:
            ml_proba = ml_model.predict_win_probability(current_features)
            if ml_proba is not None and math.isfinite(float(ml_proba)):
                ml_proba = float(ml_proba)
                ml_score_0_10 = ml_proba * 10.0
                final_score = (final_score * (1.0 - actual_ml_influence)) + (ml_score_0_10 * actual_ml_influence)
                signal_data["ml_used"] = True
                signal_data["ml_probability"] = ml_proba
                signal_data["ml_influence_applied"] = actual_ml_influence
        
        return max(0.0, min(10.0, final_score))
        
    except Exception as e:
        logger.error(f"خطا در محاسبه اطمینان: {e}")
        return 5.0


def enhance_signal_with_learning(signal: dict, df: pd.DataFrame) -> dict:
    if signal is None:
        return None
    
    try:
        current_features = {
            "trend_alignment": 1.0 if signal.get("confirmed", False) else 0.35,
            "volume_confirmation": 1.0 if signal.get("volume_spike", False) else 0.3,
            "multi_tf_alignment": 1.0 if signal.get("multi_tf_aligned", False) else 0.4,
            "price_action_quality": min(
                _direction_aligned_pa_count(signal.get("pa_signals", []), _is_long_direction(signal.get("direction", ""))), 3
            ) / 3.0,
            "backtest_winrate": (signal.get("backtest", {}).get("winrate", 0) or 0) / 100.0,
            "rsi_momentum": 0.0,
            "volatility_regime": 0.0,
            "trend_type": signal.get("trend", "NEUTRAL"),
            "volatility": 0.0,
            "volume_ratio": 0.0,
            "rsi": 50,
            "price_action": signal.get("pa_signals", [""])[0] if signal.get("pa_signals") else "",
            "market_regime": signal.get("market_regime", "UNKNOWN"),
            "adx_strength": 0.0,
            "cci_signal": 0.0,
            "williams_signal": 0.0,
            "mfi_signal": 0.0,
            "supertrend_alignment": 0.0,
        }
        
        if df is not None and len(df) > 0:
            if "rsi" in df.columns:
                current_features["rsi"] = float(df["rsi"].iloc[-1]) if not pd.isna(df["rsi"].iloc[-1]) else 50
                current_features["rsi_momentum"] = abs(50 - current_features["rsi"]) / 50.0
            if "atr_ratio" in df.columns:
                current_features["volatility_regime"] = min(1.0, float(df["atr_ratio"].iloc[-1]) / 0.035) if not pd.isna(df["atr_ratio"].iloc[-1]) else 0.5
            if "volume_ratio" in df.columns:
                current_features["volume_ratio"] = min(2.0, float(df["volume_ratio"].iloc[-1])) if not pd.isna(df["volume_ratio"].iloc[-1]) else 1.0
            if "volatility_20" in df.columns:
                current_features["volatility"] = float(df["volatility_20"].iloc[-1]) if not pd.isna(df["volatility_20"].iloc[-1]) else 0.0
            if "adx" in df.columns and not pd.isna(df["adx"].iloc[-1]):
                current_features["adx_strength"] = min(1.0, float(df["adx"].iloc[-1]) / 45.0)
            is_long = "LONG" in str(signal.get("direction", ""))
            if "cci" in df.columns and not pd.isna(df["cci"].iloc[-1]):
                cci_v = float(df["cci"].iloc[-1])
                current_features["cci_signal"] = 1.0 if (cci_v > 0) == is_long else 0.0
            if "williams_r" in df.columns and not pd.isna(df["williams_r"].iloc[-1]):
                wr_v = float(df["williams_r"].iloc[-1])
                current_features["williams_signal"] = 1.0 if (wr_v > -50) == is_long else 0.0
            if "mfi" in df.columns and not pd.isna(df["mfi"].iloc[-1]):
                mfi_v = float(df["mfi"].iloc[-1])
                current_features["mfi_signal"] = 1.0 if (mfi_v > 50) == is_long else 0.0
            if "supertrend_dir" in df.columns and not pd.isna(df["supertrend_dir"].iloc[-1]):
                st_v = float(df["supertrend_dir"].iloc[-1])
                current_features["supertrend_alignment"] = 1.0 if (st_v > 0) == is_long else 0.0
        
        confidence = calculate_signal_confidence_with_learning(signal, current_features)
        signal["confidence"] = confidence
        signal["learning_features"] = current_features
        signal["ml_used"] = signal.get("ml_used", False)
        
        return signal
        
    except Exception as e:
        logger.error(f"خطا در بهبود سیگنال: {e}")
        signal["confidence"] = 5.0
        return signal


def analyze_symbol_full(symbol: str, direction_hint: Optional[str] = None, use_multi_tf: bool = True) -> Optional[dict]:
    try:
        df = fetch_klines_df(symbol, interval=CONFIG["KLINE_INTERVAL"], limit=CONFIG["KLINE_LIMIT"])
        if df is None or df.empty or df.shape[0] < CONFIG["BACKTEST_MIN_REQUIRED"]:
            return None
        
        # FIX #12: قبلاً create_ml_features (۲۰+ ستون اندیکاتور سنگین) روی هر
        # نماد کاندید صدا زده می‌شد فقط برای اینکه یه نسبت atr/close ازش
        # گرفته بشه (adaptive_parameters_from_df)، در حالی که کل خروجی دیگه‌ش
        # هیچ‌جا استفاده نمی‌شد. الان فقط atr رو یک‌بار محاسبه می‌کنیم و
        # همون رو هم برای adaptive و هم برای بقیه‌ی تحلیل استفاده می‌کنیم.
        df["atr"] = atr_pd(df["high"], df["low"], df["close"], CONFIG["ATR_PERIOD"])
        adaptive = adaptive_parameters_from_df(df)
        
        df["ema_short"] = ema_pd(df["close"], CONFIG["EMA_SHORT"])
        df["ema_med"] = ema_pd(df["close"], CONFIG["EMA_MED"])
        df["ema_long"] = ema_pd(df["close"], CONFIG["EMA_LONG"])
        df["atr_ratio"] = df["atr"] / df["close"].replace(0, np.nan)
        df["rsi"] = rsi_pd(df["close"], CONFIG["RSI_PERIOD"])
        df["volume_ratio"] = df["volume"] / df["volume"].rolling(20, min_periods=1).mean()
        df["volatility_20"] = df["close"].pct_change().rolling(20).std()
        market_regime = detect_market_regime(df)
        
        atr_v = float(df["atr"].iloc[-1]) if not df["atr"].isna().all() else None
        if atr_v is None or atr_v == 0:
            return None
        
        ema_s, ema_m, ema_l = df["ema_short"].iloc[-1], df["ema_med"].iloc[-1], df["ema_long"].iloc[-1]
        if ema_s > ema_m > ema_l:
            trend = "STRONG LONG"
        elif ema_s > ema_m:
            trend = "LONG"
        elif ema_s < ema_m < ema_l:
            trend = "STRONG SHORT"
        elif ema_s < ema_m:
            trend = "SHORT"
        else:
            trend = "NEUTRAL"
        
        hint, price = (direction_hint or "").lower().strip(), float(df["close"].iloc[-1])
        
        if hint.startswith("bull") or hint == "bull":
            signal_direction, is_warning = "LONG", trend not in ["LONG", "STRONG LONG"]
        elif hint.startswith("bear") or hint == "bear":
            signal_direction, is_warning = "SHORT", trend not in ["SHORT", "STRONG SHORT"]
        else:
            if trend in ["LONG", "STRONG LONG"]:
                signal_direction, is_warning = "LONG", False
            elif trend in ["SHORT", "STRONG SHORT"]:
                signal_direction, is_warning = "SHORT", False
            else:
                return None
        
        atr_mult = adaptive.get("ATR_MULT_SL", CONFIG["ATR_MULT_SL"])
        
        if signal_direction == "LONG":
            entry = price
            sl = round(price - atr_mult * atr_v, 8)
            tps = [round(price + m * atr_v, 8) for m in CONFIG["TP_ATR_MULTS"]]
            direction_text = "LONG" + (" ⚠️" if is_warning else "")
        else:
            entry = price
            sl = round(price + atr_mult * atr_v, 8)
            tps = [round(price - m * atr_v, 8) for m in CONFIG["TP_ATR_MULTS"]]
            direction_text = "SHORT" + (" ⚠️" if is_warning else "")
        
        conf = compute_confirmation_signals(df, require_volume=CONFIG.get("REQUIRE_VOLUME_SPIKE", True))
        long_conf = conf["long_confirm"].iloc[-1] if len(conf) > 0 else False
        short_conf = conf["short_confirm"].iloc[-1] if len(conf) > 0 else False
        confirmed = (signal_direction == "LONG" and bool(long_conf)) or (signal_direction == "SHORT" and bool(short_conf))
        volume_spike = bool(df["volume_ratio"].iloc[-1] > CONFIG["MIN_VOLUME_RATIO"]) if "volume_ratio" in df.columns else False
        df["adx"] = conf["adx"]
        df["cci"] = conf["cci"]
        df["williams_r"] = conf["williams_r"]
        df["mfi"] = conf["mfi"]
        df["supertrend_dir"] = conf["supertrend_dir"]
        
        mtf_ok = True
        if use_multi_tf:
            try:
                higher_int = "4h" if CONFIG["KLINE_INTERVAL"].endswith("m") else "1d"
                df_higher = fetch_klines_df(symbol, interval=higher_int, limit=200)
                if df_higher is not None:
                    hema_s = ema_pd(df_higher["close"], CONFIG["EMA_SHORT"]).iloc[-1]
                    hema_m = ema_pd(df_higher["close"], CONFIG["EMA_MED"]).iloc[-1]
                    if signal_direction == "LONG" and not (hema_s > hema_m):
                        mtf_ok = False
                    if signal_direction == "SHORT" and not (hema_s < hema_m):
                        mtf_ok = False
            except Exception as e:
                logger.debug(f"خطا در MTF {symbol}: {e}")
                mtf_ok = True
        
        pa_signals = detect_price_action_signals(df)
        swings = find_swing_levels_pd(df)
        backtest_res = backtest_symbol_realistic(symbol)
        
        with CONFIG_LOCK:
            params_used_snapshot = {
                "ATR_MULT_SL": CONFIG["ATR_MULT_SL"],
                "EMA_SHORT": CONFIG["EMA_SHORT"],
                "EMA_MED": CONFIG["EMA_MED"],
                "EMA_LONG": CONFIG.get("EMA_LONG", 100),
                "PUMP_THRESHOLD": CONFIG.get("PUMP_THRESHOLD", 1.8),
                "MIN_CONFIDENCE_SCORE": CONFIG.get("MIN_CONFIDENCE_SCORE", 6.0),
                "MAX_HOLD_MINUTES": CONFIG.get("MAX_HOLD_MINUTES", 30),
                "ADX_TREND_MIN": CONFIG.get("ADX_TREND_MIN", 20),
                "RSI_PERIOD": CONFIG.get("RSI_PERIOD", 14),
                "MIN_VOLUME_RATIO": CONFIG.get("MIN_VOLUME_RATIO", 1.2),
                "REQUIRE_VOLUME_SPIKE": bool(CONFIG.get("REQUIRE_VOLUME_SPIKE", True)),
                "TP_ATR_MULTS": list(CONFIG.get("TP_ATR_MULTS", [2.0, 3.0, 4.0])),
            }
        
        signal = {
            "symbol": symbol.upper(),
            "price": price,
            "direction": direction_text,
            "entry": entry,
            "sl": sl,
            "tps": tps,
            "trend": trend,
            "atr": atr_v,
            "atr_mult_used": atr_mult,
            "swings": swings,
            "pa_signals": pa_signals,
            "confirmed": confirmed,
            "volume_spike": volume_spike,
            "multi_tf_ok": mtf_ok,
            "multi_tf_aligned": mtf_ok,
            "market_regime": market_regime,
            "indicators": {
                "adx": float(df["adx"].iloc[-1]) if not pd.isna(df["adx"].iloc[-1]) else None,
                "cci": float(df["cci"].iloc[-1]) if not pd.isna(df["cci"].iloc[-1]) else None,
                "williams_r": float(df["williams_r"].iloc[-1]) if not pd.isna(df["williams_r"].iloc[-1]) else None,
                "mfi": float(df["mfi"].iloc[-1]) if not pd.isna(df["mfi"].iloc[-1]) else None,
                "supertrend_dir": int(df["supertrend_dir"].iloc[-1]) if not pd.isna(df["supertrend_dir"].iloc[-1]) else None,
            },
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "signal_candle_ts": df.index[-1].timestamp(),
            "backtest": backtest_res,
            "features_snapshot": {
                "rsi": float(df["rsi"].iloc[-1]) if not pd.isna(df["rsi"].iloc[-1]) else None,
                "atr_ratio": float(df["atr_ratio"].iloc[-1]) if not pd.isna(df["atr_ratio"].iloc[-1]) else None,
                "volume_ratio": float(df["volume_ratio"].iloc[-1]) if not pd.isna(df["volume_ratio"].iloc[-1]) else None,
                "volatility_20": float(df["volatility_20"].iloc[-1]) if not pd.isna(df["volatility_20"].iloc[-1]) else None,
            },
            "params_used": params_used_snapshot
        }
        
        signal = enhance_signal_with_learning(signal, df)
        return signal
        
    except Exception as e:
        logger.error(f"خطا در تحلیل {symbol}: {e}")
        return None


# ============================================================================
# بخش 18.5: موتور تشخیص مسیر سیگنال (Signal Funnel) - پایدار و قابل بازیابی
# ============================================================================
_SIGNAL_DIAG_LOCK = threading.Lock()
_REGIME_GATE_LOCK = threading.Lock()  # FIX v24.3: defined before enhanced_analysis uses it
_REGIME_GATE_STATS: Dict[str, Dict[str, int]] = {"evaluated": {}, "passed": {}}
_SIGNAL_DIAG_STATE = {
    "hour_started": int(time.time() // 3600),
    "window_started": time.time(),
    "cumulative": {},
    "hourly": {},
    "window": {},
    "last_events": []
}

def _load_signal_diag():
    global _SIGNAL_DIAG_STATE
    try:
        p = PATHS.get("SIGNAL_DIAGNOSTICS")
        if p and os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, dict):
                _SIGNAL_DIAG_STATE.update(obj)
    except Exception:
        pass
    current = int(time.time() // 3600)
    if _SIGNAL_DIAG_STATE.get("hour_started") != current:
        _SIGNAL_DIAG_STATE["hour_started"] = current
        _SIGNAL_DIAG_STATE["hourly"] = {}
    if not _SIGNAL_DIAG_STATE.get("window_started"):
        _SIGNAL_DIAG_STATE["window_started"] = time.time()
    _SIGNAL_DIAG_STATE.setdefault("window", {})

_load_signal_diag()

_DIAG_LAST_SAVE = 0.0
_DIAG_SAVE_INTERVAL_SEC = 30.0  # FIX: prevent hundreds of JSON writes per cycle on Railway

def _diag_inc(stage: str, reason: str = "", regime: str = "UNKNOWN", accepted: bool = False):
    """ثبت دائمی مسیر هر کاندید تا گزارش دقیقاً نشان دهد کجا سیگنال‌ها حذف شده‌اند.
    FIX v24: disk write throttled to every 30s (was every call → I/O storm on Railway).
    """
    global _DIAG_LAST_SAVE
    try:
        now_hour = int(time.time() // 3600)
        mirror_key = None
        with _SIGNAL_DIAG_LOCK:
            if _SIGNAL_DIAG_STATE.get("hour_started") != now_hour:
                _SIGNAL_DIAG_STATE["hour_started"] = now_hour
                _SIGNAL_DIAG_STATE["hourly"] = {}
            key = f"{stage}:{reason or 'ok'}"
            for bucket_name in ("cumulative", "hourly", "window"):
                bucket = _SIGNAL_DIAG_STATE.setdefault(bucket_name, {})
                rec = bucket.setdefault(key, {"count": 0, "stage": stage, "reason": reason or "ok"})
                rec["count"] = int(rec.get("count", 0)) + 1
            if accepted:
                for bucket_name in ("cumulative", "hourly", "window"):
                    _SIGNAL_DIAG_STATE.setdefault(bucket_name, {}).setdefault("ACCEPTED:ok", {"count": 0, "stage": "ACCEPTED", "reason": "ok"})["count"] += 1
            # Diagnostics are the authoritative event stream. Mirror only the
            # core funnel stages into runtime telemetry so the two views cannot
            # silently disagree.
            mirror_keys = {
                "TRIGGER": "triggered",
                "ANALYSIS_ENTERED": "analysis_calls",
                "ANALYSIS_OK": "analysis_success",
                "GATE_EVALUATED": "gate_evaluated",
            }
            mirror_key = mirror_keys.get(stage)
            events = _SIGNAL_DIAG_STATE.setdefault("last_events", [])
            events.append({"ts": time.time(), "stage": stage, "reason": reason or "ok", "regime": regime})
            if len(events) > 100:
                del events[:-100]
            # Throttled persist
            now = time.time()
            if now - _DIAG_LAST_SAVE >= _DIAG_SAVE_INTERVAL_SEC:
                _atomic_write_json(PATHS["SIGNAL_DIAGNOSTICS"], _SIGNAL_DIAG_STATE)
                _DIAG_LAST_SAVE = now
        # runtime_inc OUTSIDE diag lock to avoid lock-order issues
        if mirror_key:
            try:
                _runtime_inc(mirror_key, 1)
            except Exception:
                pass
    except Exception:
        pass

def _diag_reset_window_after_report():
    try:
        with _SIGNAL_DIAG_LOCK:
            current = int(time.time() // 3600)
            _SIGNAL_DIAG_STATE["hour_started"] = current
            _SIGNAL_DIAG_STATE["window_started"] = time.time()
            _SIGNAL_DIAG_STATE["hourly"] = {}
            _SIGNAL_DIAG_STATE["window"] = {}
            _atomic_write_json(PATHS["SIGNAL_DIAGNOSTICS"], _SIGNAL_DIAG_STATE)
    except Exception:
        pass

def _diag_reset_hour_after_report():
    _diag_reset_window_after_report()

def _diag_snapshot():
    try:
        with _SIGNAL_DIAG_LOCK:
            return json.loads(json.dumps(_SIGNAL_DIAG_STATE))
    except Exception:
        return {"hourly": {}, "cumulative": {}}


def _safe_float(v, default=0.0):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def pro_signal_quality_gate(signal: dict) -> Tuple[bool, str, dict]:
    """Final safety/quality gate: fewer signals, stronger evidence, no starvation trading."""
    diagnostics = {}
    try:
        if not CONFIG.get("PRO_ENABLE_FINAL_QUALITY_GATE", True):
            return True, "disabled", diagnostics
        conf = _safe_float(signal.get("confidence"), 0.0)
        diagnostics["confidence"] = conf
        # FIX #6: به‌جای یه آستانه‌ی مستقل ثابت (که با آستانه‌ی پویای
        # enhanced_analysis تناقض داشت و باعث رد بی‌دلیل سیگنال‌های
        # قبول‌شده می‌شد)، همون آستانه‌ای که واقعاً روی این سیگنال اعمال شده
        # رو چک می‌کنیم.
        required_conf = _safe_float(signal.get("required_confidence"), float(CONFIG.get("PRO_MIN_CONFIDENCE", 5.9)))
        if conf < required_conf:
            return False, f"pro_confidence<{required_conf:.2f}", diagnostics

        pre_move = signal.get("pre_signal_change_15m")
        if pre_move is not None:
            pre_move_abs = abs(_safe_float(pre_move))
            diagnostics["pre_signal_move_pct"] = pre_move_abs
            if pre_move_abs > float(CONFIG.get("PRO_MAX_PRE_SIGNAL_MOVE_PCT", 2.5)):
                return False, "entry_too_late_pre_signal_move", diagnostics

        backtest = signal.get("backtest") or {}
        bt_wr = backtest.get("winrate")
        if bt_wr is not None:
            bt_wr = _safe_float(bt_wr, 0.0)
            diagnostics["backtest_wr"] = bt_wr
            if bt_wr > 0 and bt_wr < float(CONFIG.get("PRO_MIN_BACKTEST_WR", 45.0)) and conf < 7.0:
                return False, "weak_backtest_quality", diagnostics

        entry = _safe_float(signal.get("entry"), 0.0)
        sl = _safe_float(signal.get("sl"), 0.0)
        tps = signal.get("tps") or []
        tp1 = _safe_float(tps[0], 0.0) if tps else 0.0
        if entry > 0 and sl > 0 and tp1 > 0:
            risk = abs(entry - sl)
            reward = abs(tp1 - entry)
            rr = reward / risk if risk > 0 else 0.0
            diagnostics["rr_tp1"] = rr
            if rr < float(CONFIG.get("PRO_MIN_RR_TP1", 0.8)):
                return False, f"poor_rr_tp1<{CONFIG.get('PRO_MIN_RR_TP1',0.8):.2f}", diagnostics

            # FIX v24.2: Expected Value gate (cost-aware)
            # EV ≈ p_win * RR - (1-p_win) - costs_in_R
            try:
                commission = float(CONFIG.get("COMMISSION_PCT", 0.0004))
                slippage = float(CONFIG.get("SLIPPAGE_PCT", 0.0005))
                # round-trip cost in price fraction → convert to R units
                cost_pct = 2.0 * (commission + slippage)
                risk_pct = risk / entry if entry > 0 else 0.01
                cost_R = (cost_pct / risk_pct) if risk_pct > 1e-9 else 0.15
                # p_win estimate: prefer ml_probability, else conf mapped, else 0.55
                ml_p0 = signal.get("ml_probability")
                if ml_p0 is not None:
                    p_win = float(np.clip(_safe_float(ml_p0, 0.55), 0.05, 0.95))
                else:
                    p_win = float(np.clip(0.40 + (conf - 5.0) * 0.08, 0.35, 0.75))
                ev_R = p_win * rr - (1.0 - p_win) - cost_R
                diagnostics["ev_R"] = round(ev_R, 4)
                diagnostics["p_win_est"] = round(p_win, 4)
                diagnostics["cost_R"] = round(cost_R, 4)
                min_ev = float(CONFIG.get("PRO_MIN_EV_R", 0.05))
                if CONFIG.get("PRO_ENABLE_EV_GATE", True) and ev_R < min_ev and conf < 7.2:
                    return False, f"negative_ev<{min_ev:.2f}", diagnostics
            except Exception as _eve:
                diagnostics["ev_error"] = str(_eve)

        # ML gate فقط وقتی مدل واقعاً اثر دارد و ACTIVE است.
        # مدل PROVISIONAL / influence نزدیک صفر نباید سیگنال را رد کند.
        ml_p = signal.get("ml_probability")
        try:
            actual_ml_influence = float(ml_model.get_influence_weight()) if (
                ml_model is not None and getattr(ml_model, "is_trained", False)
            ) else 0.0
        except Exception:
            actual_ml_influence = float(signal.get("ml_influence_applied") or 0.0)
        ml_health = str(getattr(ml_model, "health", "UNKNOWN") if ml_model is not None else "UNKNOWN")
        diagnostics["ml_influence"] = actual_ml_influence
        diagnostics["ml_health"] = ml_health
        min_infl_for_gate = float(CONFIG.get("PRO_ML_GATE_MIN_INFLUENCE", 0.03))
        ml_edge_ok = True
        if CONFIG.get("PRO_ML_GATE_REQUIRE_POSITIVE_EDGE", True):
            try:
                _mp = performance_memory.get_ml_performance()
                _w = (_mp.get("with_ml") or {})
                _o = (_mp.get("without_ml") or {})
                if int(_w.get("trades", 0) or 0) >= 150 and int(_o.get("trades", 0) or 0) >= 80:
                    if float(_w.get("winrate", 0) or 0) + 0.3 < float(_o.get("winrate", 0) or 0):
                        ml_edge_ok = False
            except Exception:
                ml_edge_ok = True
        diagnostics["ml_edge_ok"] = ml_edge_ok
        # weak_ml فقط وقتی ML واقعاً وزن دارد و edge تاریخی‌اش منفی نیست
        if (
            signal.get("ml_used")
            and ml_p is not None
            and actual_ml_influence >= min_infl_for_gate
            and ml_health == "ACTIVE"
            and ml_edge_ok
        ):
            ml_p = _safe_float(ml_p, 0.0)
            diagnostics["ml_probability"] = ml_p
            if ml_p < float(CONFIG.get("PRO_MIN_ML_PROBABILITY", 0.52)):
                return False, "weak_ml_probability", diagnostics
        elif signal.get("ml_used") and ml_p is not None:
            diagnostics["ml_probability"] = _safe_float(ml_p, 0.0)
            diagnostics["ml_gate_skipped"] = (
                f"health={ml_health}|infl={actual_ml_influence:.4f}|edge_ok={ml_edge_ok}"
            )

        # Edge منفی، ریسک را قفل می‌کند اما به‌تنهایی کل موتور سیگنال را خفه نمی‌کند.
        # کیفیت همچنان با Confidence/BT/RR/ML کنترل می‌شود.
        pf30 = performance_memory.get_profit_factor(30) if len(performance_memory.trades) >= 10 else 1.0
        exp30 = performance_memory.get_expectancy(30) if len(performance_memory.trades) >= 10 else 0.0
        diagnostics["pf30"] = pf30
        diagnostics["expectancy30"] = exp30
        diagnostics["edge_state"] = "NEGATIVE" if (pf30 < 0.85 or exp30 < 0) else "OK"

        return True, "accepted", diagnostics
    except Exception as e:
        logger.error(f"PRO quality gate error: {e}")
        return False, "quality_gate_exception", {"error": str(e)}


def _pro_risk_state() -> dict:
    """FIX v24: require n>=30 before locking risk (n=10 was too aggressive)."""
    try:
        n = len(performance_memory.trades)
        min_n = 30
        pf = performance_memory.get_profit_factor(30) if n >= min_n else None
        exp = performance_memory.get_expectancy(30) if n >= min_n else None
        sharpe = performance_memory.get_sharpe_ratio(30) if n >= min_n else None
        locked = bool(
            n >= min_n and (
                (pf is not None and pf < 1.0) or
                (exp is not None and exp <= 0) or
                (sharpe is not None and sharpe <= 0)
            )
        )
        return {
            "risk_percent": _safe_float(CONFIG.get("RISK_PERCENT")),
            "min_risk": _safe_float(CONFIG.get("MIN_RISK_PERCENT")),
            "max_risk": _safe_float(CONFIG.get("MAX_RISK_PERCENT")),
            "pf": pf,
            "expectancy": exp,
            "sharpe": sharpe,
            "locked": locked,
            "sample_n": n,
            "min_n_for_lock": min_n,
        }
    except Exception as e:
        return {"error": str(e), "locked": False}  # fail-open on error (safer than fail-closed crash)


def enhanced_analysis(symbol: str, direction_hint: Optional[str] = None, recovery_mode: bool = False) -> Optional[dict]:
    try:
        _diag_inc("ANALYSIS_ENTERED", "start")
        df = fetch_klines_df(symbol, interval=CONFIG["KLINE_INTERVAL"], limit=CONFIG["KLINE_LIMIT"])
        if df is None or df.empty or df.shape[0] < CONFIG["BACKTEST_MIN_REQUIRED"]:
            _diag_inc("REJECT", "insufficient_klines")
            return None
        _diag_inc("KLINES_OK", "ok")

        if not symbol_quality_check(symbol):
            _diag_inc("REJECT", "symbol_quality")
            logger.debug(f"{symbol}: رد شد (کیفیت)")
            return None
        _diag_inc("QUALITY_OK", "ok")

        if not volatility_filter(df):
            _diag_inc("REJECT", "volatility_filter")
            logger.debug(f"{symbol}: رد شد (نوسان)")
            return None
        _diag_inc("VOLATILITY_OK", "ok")

        swing_levels = find_swing_levels_pd(df)
        if detect_false_breakout(df, swing_levels):
            _diag_inc("REJECT", "false_breakout")
            logger.debug(f"{symbol}: رد شد (شکست فیک)")
            return None
        _diag_inc("BREAKOUT_OK", "ok")

        df_regime = df.copy()
        df_regime["atr"] = atr_pd(df_regime["high"], df_regime["low"], df_regime["close"], CONFIG["ATR_PERIOD"])
        regime = detect_market_regime(df_regime)
        if regime == "RANGING":
            _diag_inc("REJECT", "ranging", regime)
            logger.debug(f"{symbol}: رد شد (بازار رنج)")
            return None
        _diag_inc("REGIME_OK", regime, regime)

        signal = analyze_symbol_full(symbol, direction_hint)
        if not signal:
            _diag_inc("REJECT", "technical_analysis", regime)
            return None
        _diag_inc("ANALYSIS_OK", "ok", regime)

        hard_cap = float(CONFIG.get("MAX_EFFECTIVE_CONFIDENCE", 6.9))
        # منبع واحد: MIN_CONFIDENCE_SCORE پایه است؛ PRO_MIN کف سخت‌گیرانه‌تر در مسیر عادی
        base_conf = float(CONFIG.get("MIN_CONFIDENCE_SCORE", 5.6))
        pro_min = float(CONFIG.get("PRO_MIN_CONFIDENCE", 5.9))
        # جلوگیری از واگرایی: اگر AutoPilot MIN را زیر PRO آورده، در مسیر عادی از PRO پیروی کن
        if not recovery_mode:
            base_conf = max(base_conf, pro_min * 0.97)
        regime_adj = float(CONFIG.get("REGIME_CONFIDENCE_ADJUSTMENT", {}).get(regime, 0.0))
        min_confidence = min(hard_cap, base_conf + regime_adj)

        if recovery_mode:
            min_confidence = min(min_confidence, float(CONFIG.get("FALLBACK_MIN_CONFIDENCE", 5.1)))

        # FIX #5: کف pro فقط قبل از starvation؛ بعد از بی‌سیگنال طولانی اجازه کاهش واقعی
        if not recovery_mode:
            min_confidence = max(min_confidence, pro_min * 0.97)

        # Starvation recovery ملایم: بعد از بی‌سیگنال ماندن، آستانه کم‌کم پایین می‌آید؛
        # اما هرگز از 5.0 پایین‌تر نمی‌رود.
        if not CONFIG.get("PRO_DISABLE_STARVATION_LOOSENING", False):
            idle_min = max(0.0, (time.time() - _LAST_ACCEPTED_SIGNAL_TS) / 60.0)
            starvation_start = float(CONFIG.get("SIGNAL_STARVATION_MINUTES", 14))
            if idle_min >= starvation_start:
                steps = int((idle_min - starvation_start) // 12) + 1
                recovery = min(0.55, steps * float(CONFIG.get("SIGNAL_STARVATION_RECOVERY_STEP", 0.08)))
                min_confidence = max(5.0, min_confidence - recovery)

        min_confidence = min(min_confidence, hard_cap)

        _diag_inc("GATE_EVALUATED", f"{regime}|required={min_confidence:.2f}", regime)
        with _REGIME_GATE_LOCK:
            _REGIME_GATE_STATS["evaluated"][regime] = _REGIME_GATE_STATS["evaluated"].get(regime, 0) + 1

        actual_conf = float(signal.get("confidence", 0) or 0)
        if actual_conf >= min_confidence:
            # FIX #6: آستانه‌ی نهایی رو روی خودِ سیگنال ذخیره می‌کنیم تا
            # pro_signal_quality_gate دیگه یه آستانه‌ی مستقل و متناقض دوباره
            # چک نکنه (قبلاً همون سیگنال می‌تونست اینجا قبول بشه ولی چند خط
            # پایین‌تر با یه عدد متفاوت رد بشه).
            signal["required_confidence"] = min_confidence
            with _REGIME_GATE_LOCK:
                _REGIME_GATE_STATS["passed"][regime] = _REGIME_GATE_STATS["passed"].get(regime, 0) + 1
            # Quant feature enrichment (if bridge loaded)
            try:
                qcf = globals().get("quant_create_features")
                if callable(qcf) and df is not None:
                    qfeats = qcf(symbol, df)
                    if qfeats:
                        feats = signal.get("features") or {}
                        feats.update(qfeats)
                        signal["features"] = feats
            except Exception as _qe:
                logger.debug(f"quant enrich in enhanced_analysis: {_qe}")
            _diag_inc("TECHNICAL_ACCEPTED", f"{regime}|conf={actual_conf:.2f}|required={min_confidence:.2f}", regime)
            return signal

        _diag_inc("REJECT", f"confidence|{regime}|{actual_conf:.2f}<{min_confidence:.2f}", regime)
        return None

    except Exception as e:
        _diag_inc("ERROR", type(e).__name__)
        logger.error(f"خطا در enhanced_analysis {symbol}: {e}")
        return None


# ============================================================================
# بخش 19: توابع ذخیره‌سازی و گزارش
# ============================================================================

def create_ml_features(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if df is None or df.empty:
            return pd.DataFrame()
        
        df = df.copy()
        features = pd.DataFrame(index=df.index)
        
        features["price"] = df["close"]
        
        for period in [1, 5, 10]:
            features[f"returns_{period}"] = df["close"].pct_change(period)
        
        for period in [5, 10, 20]:
            features[f"volatility_{period}"] = df["close"].pct_change().rolling(period).std()
        
        vol_sma_20 = df["volume"].rolling(20, min_periods=1).mean()
        features["volume_ratio"] = df["volume"] / vol_sma_20.replace(0, np.nan)
        
        for period in [7, 10, 14]:
            features[f"rsi_{period}"] = rsi_pd(df["close"], period)
        
        macd, macd_signal, macd_hist = macd_pd(df["close"])
        features["macd"] = macd
        features["macd_signal"] = macd_signal
        features["macd_hist"] = macd_hist
        
        features["ema_short"] = ema_pd(df["close"], CONFIG["EMA_SHORT"])
        features["ema_long"] = ema_pd(df["close"], CONFIG["EMA_LONG"])
        features["ema_ratio"] = features["ema_short"] / features["ema_long"].replace(0, np.nan)
        
        features["atr"] = atr_pd(df["high"], df["low"], df["close"], CONFIG["ATR_PERIOD"])
        features["atr_ratio"] = features["atr"] / df["close"].replace(0, np.nan)
        
        bb_upper, _, bb_lower = bollinger_pd(df["close"])
        features["bb_position"] = (df["close"] - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)
        
        k, d = stochastic_pd(df["high"], df["low"], df["close"])
        features["stoch_k"] = k
        features["stoch_d"] = d
        
        features["adx"] = adx_pd(df["high"], df["low"], df["close"])
        features["cci"] = cci_pd(df["high"], df["low"], df["close"], CONFIG.get("CCI_PERIOD", 12))
        features["williams_r"] = williams_r_pd(df["high"], df["low"], df["close"], CONFIG.get("WILLIAMS_R_PERIOD", 10))
        features["mfi"] = mfi_pd(df["high"], df["low"], df["close"], df["volume"], CONFIG.get("MFI_PERIOD", 10))
        obv = obv_pd(df["close"], df["volume"])
        features["obv_slope"] = obv.diff(5) / df["volume"].rolling(5, min_periods=1).mean().replace(0, np.nan)
        _, st_dir = supertrend_pd(df["high"], df["low"], df["close"],
                                   CONFIG.get("SUPERTREND_PERIOD", 8), CONFIG.get("SUPERTREND_MULT", 2.5))
        features["supertrend_dir"] = st_dir
        features["vwap_dist"] = (df["close"] - vwap_pd(df["high"], df["low"], df["close"], df["volume"])) / df["close"].replace(0, np.nan)
        
        features["body_size"] = (df["close"] - df["open"]).abs()
        features["total_range"] = df["high"] - df["low"]
        features["body_ratio"] = features["body_size"] / features["total_range"].replace(0, np.nan)
        
        features = features.replace([np.inf, -np.inf], np.nan)
        features = features.ffill().bfill().fillna(0)
        
        return features
        
    except Exception as e:
        logger.error(f"خطا در ساخت ویژگی‌های ML: {e}")
        return pd.DataFrame()


def save_signal_json_overwrite(signals: List[dict]) -> None:
    save_json_file(PATHS["FINAL_SIGNAL_FILE"], signals)


def save_signal_history(signal: Dict[str, Any]) -> None:
    try:
        history = load_json_file(PATHS["SIGNAL_HISTORY_FILE"]) or []
        if not isinstance(history, list):
            history = []
        
        signal["ts"] = int(time.time())
        history.append(signal)
        
        if len(history) > 100:
            history = history[-100:]
        
        save_json_file(PATHS["SIGNAL_HISTORY_FILE"], history)
    except Exception as e:
        logger.error(f"خطا در ذخیره تاریخچه سیگنال: {e}")


def update_learning_system() -> None:
    logger.info("\n🔄 شروع به‌روزرسانی سیستم یادگیری...")
    
    param_optimizer.optimize()
    param_optimizer.apply_optimized_params()
    weight_learner.update_weights()
    pattern_recognizer.learn_patterns()
    ml_model.train(force=True)
    param_optimizer.optimize_regime_thresholds()
    
    summary = performance_memory.get_summary()
    logger.info(f"✅ خلاصه عملکرد: {summary['total_trades']} معامله, وین‌ریت: {summary['long_term_winrate']:.1f}%")
    logger.info("✅ سیستم یادگیری به‌روزرسانی شد\n")


# ============================================================================
# بخش 20: گزارش‌سازی کامل - هر ۳۰ دقیقه
# ============================================================================

_LAST_REPORTED_WEIGHTS: Dict[str, float] = {}
_REPORT_HISTORY: List[dict] = []

# ---------------------------------------------------------------------------
# Runtime observability: persistent 30-minute window, independent of process
# uptime. This is deliberately separate from Signal Diagnostics so a report
# can answer BOTH "why no signal?" and "is the program itself healthy?".
# ---------------------------------------------------------------------------
_RUNTIME_LOCK = threading.Lock()
_RUNTIME_STATE = {
    "window_started": time.time(),
    "last_cycle_started": None,
    "last_cycle_finished": None,
    "last_cycle_duration_sec": None,
    "cycles": 0,
    "cycle_errors": 0,
    "empty_ticker_cycles": 0,
    "symbols_seen": 0,
    "usdt_symbols_seen": 0,
    "triggered": 0,
    "pump_triggers": 0,
    "dump_triggers": 0,
    "analysis_calls": 0,
    "analysis_success": 0,
    "gate_evaluated": 0,
    "normal_signals": 0,
    "telemetry_repairs": 0,
    "telemetry_integrity_failures": 0,
    "last_telemetry_repair": None,
    "fallback_attempts": 0,
    "fallback_signals": 0,
    "telegram_signal_ok": 0,
    "telegram_signal_fail": 0,
    "telegram_report_ok": 0,
    "telegram_report_fail": 0,
    "last_ticker_count": 0,
    "last_price_map_count": 0,
    "last_fetch_latency_ms": None,
    "fetch_latency_ms_sum": 0.0,
    "fetch_latency_samples": 0,
    "last_learning_update": None,
    "learning_updates": 0,
    "ml_retrain_attempts": 0,
    "ml_retrain_success": 0,
    "ml_retrain_fail": 0,
    "last_ml_train": None,
    "last_ml_result": None,
    "notes": [],
    # Post-gate delivery pipeline observability
    "accepted_candidates": 0,
    "signal_build_started": 0,
    "signal_build_ok": 0,
    "signal_build_failed": 0,
    "risk_checks": 0,
    "risk_approved": 0,
    "risk_rejected": 0,
    "signal_created": 0,
    "telegram_attempts": 0,
    "telegram_sent": 0,
    "telegram_failed": 0,
    "telegram_cooldown": 0,
    "self_repair_runs": 0,
    "self_repair_actions": 0,
    "self_repair_failures": 0,
    "last_self_repair": None,
    "last_post_gate_failure": None,
    "candidate_events": [],
}

def _runtime_load():
    global _RUNTIME_STATE
    try:
        p = PATHS.get("RUNTIME_TELEMETRY")
        if p and os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, dict):
                _RUNTIME_STATE.update(obj)
    except Exception:
        pass
    # A persisted state must never make the new report window look ancient.
    if not _RUNTIME_STATE.get("window_started"):
        _RUNTIME_STATE["window_started"] = time.time()

_runtime_load()
# Backward-compatible defaults for state files created by older versions.
with _RUNTIME_LOCK:
    for _k, _v in {
        "accepted_candidates": 0, "signal_build_started": 0, "signal_build_ok": 0,
        "signal_build_failed": 0, "risk_checks": 0, "risk_approved": 0,
        "risk_rejected": 0, "signal_created": 0, "telegram_attempts": 0,
        "telegram_sent": 0, "telegram_failed": 0, "telegram_cooldown": 0,
        "self_repair_runs": 0, "self_repair_actions": 0,
        "self_repair_failures": 0, "last_self_repair": None,
        "last_post_gate_failure": None, "candidate_events": []
    }.items():
        _RUNTIME_STATE.setdefault(_k, _v)

_RUNTIME_LAST_SAVE = 0.0
_RUNTIME_SAVE_INTERVAL_SEC = 20.0  # FIX v24: throttle disk writes (was every inc/event)

def _runtime_save_locked(force: bool = False):
    """Must be called while holding _RUNTIME_LOCK (except force from outside with lock)."""
    global _RUNTIME_LAST_SAVE
    try:
        now = time.time()
        if not force and (now - _RUNTIME_LAST_SAVE) < _RUNTIME_SAVE_INTERVAL_SEC:
            return
        _atomic_write_json(PATHS["RUNTIME_TELEMETRY"], _RUNTIME_STATE)
        _RUNTIME_LAST_SAVE = now
    except Exception as e:
        logger.debug(f"runtime_save failed: {e}")

def _runtime_update(**kwargs):
    try:
        with _RUNTIME_LOCK:
            for k, v in kwargs.items():
                if k in _RUNTIME_STATE:
                    _RUNTIME_STATE[k] = v
            _runtime_save_locked(force=False)
    except Exception:
        pass

def _runtime_event(event: str, candidate_id: str = "", symbol: str = "", reason: str = "", **extra):
    """Append a compact, bounded event record for post-gate forensic debugging."""
    try:
        rec = {"ts": time.time(), "event": str(event), "candidate_id": str(candidate_id or ""),
               "symbol": str(symbol or ""), "reason": str(reason or "")}
        rec.update(extra)
        with _RUNTIME_LOCK:
            events = _RUNTIME_STATE.setdefault("candidate_events", [])
            if not isinstance(events, list):
                events = []
                _RUNTIME_STATE["candidate_events"] = events
            events.append(rec)
            _RUNTIME_STATE["candidate_events"] = events[-200:]
            _runtime_save_locked(force=False)
    except Exception:
        pass


def _runtime_inc(key: str, amount=1):
    try:
        with _RUNTIME_LOCK:
            _RUNTIME_STATE[key] = _safe_int(_RUNTIME_STATE.get(key, 0)) + amount
            _runtime_save_locked(force=False)
    except Exception:
        pass

def _safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default

def _runtime_reset_window():
    try:
        with _RUNTIME_LOCK:
            keep = {
                "last_cycle_started": _RUNTIME_STATE.get("last_cycle_started"),
                "last_cycle_finished": _RUNTIME_STATE.get("last_cycle_finished"),
                "last_cycle_duration_sec": _RUNTIME_STATE.get("last_cycle_duration_sec"),
                "last_ticker_count": _RUNTIME_STATE.get("last_ticker_count", 0),
                "last_price_map_count": _RUNTIME_STATE.get("last_price_map_count", 0),
                "last_fetch_latency_ms": _RUNTIME_STATE.get("last_fetch_latency_ms"),
                "last_learning_update": _RUNTIME_STATE.get("last_learning_update"),
                "last_ml_train": _RUNTIME_STATE.get("last_ml_train"),
                "last_ml_result": _RUNTIME_STATE.get("last_ml_result"),
                "notes": [],
                "candidate_events": [],
                "last_post_gate_failure": None,
            }
            for k in list(_RUNTIME_STATE.keys()):
                if k not in ("window_started", *keep.keys()):
                    _RUNTIME_STATE[k] = 0 if isinstance(_RUNTIME_STATE.get(k), (int, float)) else _RUNTIME_STATE[k]
            _RUNTIME_STATE.update(keep)
            _RUNTIME_STATE["window_started"] = time.time()
            _runtime_save_locked()
    except Exception:
        pass

def _system_health_snapshot() -> dict:
    result = {"status": "UNKNOWN", "python": sys.version.split()[0], "pid": os.getpid()}
    try:
        result["uptime_sec"] = max(0, time.time() - float(_PROCESS_START_TS))
    except Exception:
        result["uptime_sec"] = None
    try:
        if hasattr(os, "getloadavg"):
            result["loadavg"] = tuple(round(x, 2) for x in os.getloadavg())
    except Exception:
        result["loadavg"] = None
    try:
        if os.path.exists("/proc/meminfo"):
            mem = {}
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        mem[parts[0].rstrip(":")] = int(parts[1]) * 1024
            if mem.get("MemTotal"):
                result["ram_total_mb"] = round(mem["MemTotal"] / 1048576, 1)
                result["ram_available_mb"] = round(mem.get("MemAvailable", 0) / 1048576, 1)
                result["ram_used_pct"] = round((1 - mem.get("MemAvailable", 0) / mem["MemTotal"]) * 100, 1)
    except Exception:
        pass
    try:
        st = os.statvfs(DATA_DIR)
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        result["disk_total_gb"] = round(total / 1e9, 2)
        result["disk_free_gb"] = round(free / 1e9, 2)
        result["disk_used_pct"] = round((1 - free / total) * 100, 1) if total else None
    except Exception:
        pass
    result["status"] = "OK"
    if result.get("ram_used_pct", 0) >= 90 or result.get("disk_used_pct", 0) >= 90:
        result["status"] = "WARNING"
    return result


def _pro_report_appendix(price_map: Dict[str, float]) -> List[str]:
    lines = []
    try:
        # Take a consistent runtime snapshot for the entire appendix.
        # This function is called independently from the main report builder,
        # so relying on an outer/local `runtime` variable causes a NameError.
        with _RUNTIME_LOCK:
            runtime = copy.deepcopy(_RUNTIME_STATE)

        risk = _pro_risk_state()
        errors = logger.get_report()
        diag = _diag_snapshot()
        cumulative = diag.get("cumulative", {})
        hourly = diag.get("window", diag.get("hourly", {}))
        total_diag = sum(int(v.get("count", 0)) for v in hourly.values())
        rejects = sorted([(v.get("reason", ""), int(v.get("count", 0))) for v in hourly.values() if v.get("stage") == "REJECT"], key=lambda x: x[1], reverse=True)
        accepted = sum(int(v.get("count", 0)) for v in hourly.values() if v.get("stage") == "ACCEPTED")
        gate_eval = sum(int(v.get("count", 0)) for v in hourly.values() if v.get("stage") == "GATE_EVALUATED")
        lines += ["", "🛡️ **CEZARTRADING 20 PRO — سلامت و کنترل ریسک:**"]
        _edge_n = 30
        _edge_note = " ⚠️ n=30 نمونه کوچک – با احتیاط تفسیر شود" if _edge_n < 50 else ""
        lines.append(
            f"  • Edge 30 معامله: PF={risk.get('pf') if risk.get('pf') is not None else 'N/A'} | "
            f"Exp={risk.get('expectancy') if risk.get('expectancy') is not None else 'N/A'}% | "
            f"Sharpe={risk.get('sharpe') if risk.get('sharpe') is not None else 'N/A'}{_edge_note}"
        )
        lines.append(f"  • Risk: {risk.get('risk_percent',0):.2f}% | سقف: {risk.get('max_risk',0):.2f}% | قفل افزایش ریسک: {'🔒 بله' if risk.get('locked') else '🔓 خیر'}")
        lines.append(f"  • PRO Quality Gate: {'فعال' if CONFIG.get('PRO_ENABLE_FINAL_QUALITY_GATE') else 'خاموش'} | حداقل Confidence: {CONFIG.get('PRO_MIN_CONFIDENCE',6.2):.2f}")
        lines.append(f"  • RR حداقل TP1: {CONFIG.get('PRO_MIN_RR_TP1',0.8):.2f} | حداکثر حرکت قبل ورود: {CONFIG.get('PRO_MAX_PRE_SIGNAL_MOVE_PCT',2.5):.2f}%")
        lines.append(f"  • Diagnostic: evaluated={gate_eval} | accepted={accepted} | acceptance={((accepted/gate_eval)*100 if gate_eval else 0):.1f}%")

        lines += ["", "🧪 **ML / Validation:**"]
        lines.append(f"  • WF AUC: {getattr(ml_model,'wf_auc_mean',None)} ± {getattr(ml_model,'wf_auc_std',None)} (SEM={getattr(ml_model,'wf_auc_sem',None)}) | folds={getattr(ml_model,'wf_folds',0)}")
        lines.append(f"  • Last AUC: {getattr(ml_model,'last_test_auc',None)} | Brier: {getattr(ml_model,'last_brier',None)} | Health: {getattr(ml_model,'health','UNKNOWN')}")
        lines.append(f"  • ML influence فعلی: {(ml_model.get_influence_weight()*100 if getattr(ml_model,'is_trained',False) else 0):.1f}% | Dataset={getattr(ml_model,'dataset_n',0)}")
        lines.append("  • قانون PRO: ML ضعیف در Shadow/بدون اثر می‌ماند و افزایش Risk را کنترل نمی‌کند.")

        lines += ["", "🚦 **گلوگاه‌های سیگنال:**"]
        if rejects:
            for reason, count in rejects[:15]:
                lines.append(f"  • {reason}: {count}")
        else:
            lines.append("  • ردشده‌ای ثبت نشده است.")

        lines += ["", "🩺 **خطاها و هشدارها:**"]
        lines.append(f"  • Errors={errors.get('total_errors',0)} | Warnings={errors.get('total_warnings',0)} | Debug={errors.get('total_debug',0)}")
        try:
            ws = _safe_float(_RUNTIME_STATE.get("window_started"), time.time())
            win_errors = [x for x in logger.errors if _safe_float(x.get("time"),0) >= ws]
            win_warnings = [x for x in logger.warnings if _safe_float(x.get("time"),0) >= ws]
            lines.append(f"  • در همین بازه: ERROR={len(win_errors)} | WARNING={len(win_warnings)}")
        except Exception:
            pass
        if errors.get("last_error"):
            lines.append(f"  • آخرین ERROR: {errors['last_error'].get('message','')}")
        if errors.get("last_warning"):
            lines.append(f"  • آخرین WARNING: {errors['last_warning'].get('message','')}")
        recent_errs = errors.get("errors", [])[-5:]
        if recent_errs:
            lines.append("  • ۵ خطای اخیر:")
            for e in recent_errs:
                lines.append(f"     - {e.get('message','')}")

        # ============================
        # 13. Post-gate forensic pipeline
        # ============================
        lines += ["", "🔬 **Post-Gate Forensic Pipeline:**"]
        lines.append(f"  • Accepted candidates: {_safe_int(runtime.get('accepted_candidates'))}")
        lines.append(f"  • Signal build: started={_safe_int(runtime.get('signal_build_started'))} | ok={_safe_int(runtime.get('signal_build_ok'))} | failed={_safe_int(runtime.get('signal_build_failed'))}")
        lines.append(f"  • Risk check: total={_safe_int(runtime.get('risk_checks'))} | approved={_safe_int(runtime.get('risk_approved'))} | rejected={_safe_int(runtime.get('risk_rejected'))}")
        lines.append(f"  • Signal created: {_safe_int(runtime.get('signal_created'))}")
        lines.append(f"  • Telegram: attempts={_safe_int(runtime.get('telegram_attempts'))} | sent={_safe_int(runtime.get('telegram_sent'))} | failed={_safe_int(runtime.get('telegram_failed'))} | cooldown={_safe_int(runtime.get('telegram_cooldown'))}")
        if runtime.get('last_post_gate_failure'):
            lines.append(f"  • آخرین توقف بعد از ACCEPTED: {runtime.get('last_post_gate_failure')}")
        events = runtime.get('candidate_events') or []
        if events:
            lines.append("  • آخرین رویدادهای post-gate:")
            for ev in events[-8:]:
                lines.append(f"     - {ev.get('event')} | {ev.get('symbol')} | {ev.get('reason','')}")

        lines += ["", "🛠️ **Self-Repair Controller:**"]
        lines.append(f"  • اجرا: {_safe_int(runtime.get('self_repair_runs'))} | اقدامات: {_safe_int(runtime.get('self_repair_actions'))} | failure: {_safe_int(runtime.get('self_repair_failures'))}")
        lines.append(f"  • آخرین repair: {runtime.get('last_self_repair') or 'ندارد'}")

        lines += ["", "📋 **کنترل کیفیت داده:**"]
        lines.append(f"  • Symbols/price map: {len(price_map)}")
        lines.append(f"  • KLINE interval: {CONFIG.get('KLINE_INTERVAL')} | KLINE limit: {CONFIG.get('KLINE_LIMIT')}")
        lines.append(f"  • Commission: {CONFIG.get('COMMISSION_PCT',0)*100:.3f}% | Slippage: {CONFIG.get('SLIPPAGE_PCT',0)*100:.3f}%")
        lines.append(f"  • Report interval: {CONFIG.get('REPORT_INTERVAL_SEC',1800)//60} دقیقه")

        lines += ["", "🔧 **اقدام پیشنهادی برای اصلاح:**"]
        if risk.get("locked"):
            lines.append("  • 🔴 Edge منفی است: افزایش ریسک ممنوع؛ ابتدا PF/Expectancy را مثبت کنید.")
        if getattr(ml_model,'last_test_auc',None) is not None and _safe_float(ml_model.last_test_auc,0) < 0.50:
            lines.append("  • 🔴 Last AUC < 0.50: ML فعلاً قابل اعتماد نیست؛ در Shadow نگه دارید و داده/OOS را بررسی کنید.")
        if rejects:
            top_reason = rejects[0][0]
            lines.append(f"  • 🟠 بیشترین رد: {top_reason} — قبل از تغییر پارامتر، outcome سیگنال‌های ردشده را بررسی کنید.")
        if not risk.get("locked") and accepted > 0:
            lines.append("  • 🟢 Edge مثبت/قابل قبول گزارش شده؛ تغییرات را فقط با OOS و نمونه کافی اعمال کنید.")
    except Exception as e:
        lines.append(f"  • ❌ PRO report appendix error: {e}")
    return lines



# ---------------------------------------------------------------------------
# LEVEL-5 TELEMETRY INTEGRITY + SAFE SELF-REPAIR
# ---------------------------------------------------------------------------
def _diag_stage_count(diag: dict, stage: str) -> int:
    bucket = diag.get("window", {}) if isinstance(diag, dict) else {}
    return sum(_safe_int(v.get("count"), 0) for v in bucket.values()
               if isinstance(v, dict) and v.get("stage") == stage)


def _telemetry_integrity_check(repair: bool = True) -> dict:
    """Verify funnel invariants and repair telemetry only.
    Never changes trading thresholds, risk, ML influence, or strategy state.
    """
    result = {"status": "PASS", "issues": [], "repairs": [],
              "verified": False, "timestamp": time.time()}
    try:
        diag = _diag_snapshot()
        expected = {
            "triggered": _diag_stage_count(diag, "TRIGGER"),
            "analysis_calls": _diag_stage_count(diag, "ANALYSIS_ENTERED"),
            "analysis_success": _diag_stage_count(diag, "ANALYSIS_OK"),
            "gate_evaluated": _diag_stage_count(diag, "GATE_EVALUATED"),
        }
        with _RUNTIME_LOCK:
            actual = {k: _safe_int(_RUNTIME_STATE.get(k), 0) for k in expected}
        for key, exp in expected.items():
            if actual[key] != exp:
                result["issues"].append(f"{key}:{actual[key]}!={exp}")
        if expected["analysis_success"] > expected["analysis_calls"]:
            result["issues"].append("analysis_success>analysis_calls")
        # GATE_EVALUATED includes both the technical confidence gate and the
        # downstream PRO quality gate, so it can legitimately exceed ANALYSIS_OK.

        if result["issues"]:
            result["status"] = "REPAIR_REQUIRED"
            if repair:
                with _RUNTIME_LOCK:
                    for key, exp in expected.items():
                        _RUNTIME_STATE[key] = exp
                    actions = len(result["issues"])
                    _RUNTIME_STATE["telemetry_repairs"] = _safe_int(_RUNTIME_STATE.get("telemetry_repairs"), 0) + actions
                    _RUNTIME_STATE["self_repair_actions"] = _safe_int(_RUNTIME_STATE.get("self_repair_actions"), 0) + actions
                    _RUNTIME_STATE["self_repair_runs"] = _safe_int(_RUNTIME_STATE.get("self_repair_runs"), 0) + 1
                    _RUNTIME_STATE["telemetry_integrity_failures"] = _safe_int(_RUNTIME_STATE.get("telemetry_integrity_failures"), 0) + 1
                    _RUNTIME_STATE["last_telemetry_repair"] = time.time()
                    _RUNTIME_STATE["last_self_repair"] = time.time()
                    _runtime_save_locked()
                result["repairs"] = list(result["issues"])
                with _RUNTIME_LOCK:
                    after = {k: _safe_int(_RUNTIME_STATE.get(k), 0) for k in expected}
                result["verified"] = all(after[k] == expected[k] for k in expected)
                result["status"] = "REPAIRED" if result["verified"] else "REPAIR_FAILED"
        else:
            result["verified"] = True
        return result
    except Exception as exc:
        result["status"] = "CHECK_ERROR"
        result["issues"].append(str(exc))
        return result


def _safe_self_heal_observability() -> dict:
    _runtime_inc("self_repair_runs")
    result = _telemetry_integrity_check(repair=True)
    if result.get("status") in ("REPAIRED", "REPAIR_FAILED", "CHECK_ERROR"):
        try:
            note = {"ts": time.time(), "status": result["status"],
                    "issues": result.get("issues", [])[:10],
                    "repairs": result.get("repairs", [])[:10]}
            with _RUNTIME_LOCK:
                notes = _RUNTIME_STATE.setdefault("notes", [])
                if not isinstance(notes, list):
                    notes = []
                    _RUNTIME_STATE["notes"] = notes
                notes.append(note)
                _RUNTIME_STATE["notes"] = notes[-20:]
                _runtime_save_locked()
        except Exception:
            pass
    return result


def build_complete_report(price_map: Dict[str, float], reset_window: bool = True) -> str:
    """گزارش کامل ۳۰ دقیقه‌ای با عملکرد، ML، گیت‌ها، خطاها و ریسک"""
    global _LAST_REPORTED_WEIGHTS, _REPORT_HISTORY
    
    try:
        summary = performance_memory.get_summary()
        pending = auto_learning.get_pending_status(price_map)
        ml_summary = ml_model.get_training_summary()
        ml_perf = performance_memory.get_ml_performance()
        regime_perf = performance_memory.get_market_regime_performance()
        timing = performance_memory.get_entry_timing_stats()
        _safe_self_heal_observability()
        with _RUNTIME_LOCK:
            runtime = copy.deepcopy(_RUNTIME_STATE)
        
        # دریافت آخرین تغییرات پارامترها (فقط بازهٔ همین گزارش ~۳۵ دقیقه)
        param_changes = []
        report_window_sec = float(CONFIG.get("REPORT_INTERVAL_SECONDS", 1800)) + 300.0
        cutoff_ts = time.time() - report_window_sec
        try:
            if os.path.exists(PATHS["PARAMETER_OPTIMIZATION_HISTORY"]):
                with open(PATHS["PARAMETER_OPTIMIZATION_HISTORY"], "r") as f:
                    all_hist = json.load(f) or []
                recent = []
                for ch in all_hist:
                    ts = ch.get("timestamp")
                    try:
                        ts = float(ts) if ts is not None else 0.0
                    except (TypeError, ValueError):
                        ts = 0.0
                    if ts >= cutoff_ts:
                        recent.append(ch)
                param_changes = recent[-10:]
        except Exception:
            pass
        
        # دریافت آخرین تغییرات وزن فیچرها (همان فیلتر زمانی)
        weight_changes = []
        try:
            if os.path.exists(os.path.join(DATA_DIR, "feature_weight_changes.json")):
                with open(os.path.join(DATA_DIR, "feature_weight_changes.json"), "r") as f:
                    all_w = json.load(f) or []
                recent_w = []
                for ch in all_w:
                    ts = ch.get("timestamp")
                    try:
                        ts = float(ts) if ts is not None else 0.0
                    except (TypeError, ValueError):
                        ts = 0.0
                    if ts >= cutoff_ts:
                        recent_w.append(ch)
                weight_changes = recent_w[-10:]
        except Exception:
            pass
        
        lines = []
        lines.append("=" * 60)
        lines.append("📊 **گزارش جامع ۳۰ دقیقه‌ای - QUANT MAX v24.2**")
        lines.append(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 60)
        
        # ============================
        # 1. خلاصه عملکرد
        # ============================
        lines.append("")
        lines.append("📈 **خلاصه عملکرد:**")
        lines.append(f"  • تعداد کل معاملات: {summary['total_trades']}")
        lines.append(f"  • وین‌ریت کل: {summary['long_term_winrate']:.1f}%")
        lines.append(f"  • وین‌ریت اخیر (50 معامله): {summary['short_term_winrate']:.1f}%")
        lines.append(f"  • فاکتور سود: {summary.get('profit_factor', 0):.2f}")
        lines.append(f"  • نسبت شارپ: {summary.get('sharpe_ratio', 0):.2f}")
        lines.append(f"  • امید ریاضی: {summary.get('expectancy', 0):.2f}%")
        lines.append(f"  • روند عملکرد: {summary.get('performance_trend', 'UNKNOWN')}")

        # معاملات واقعاً بسته‌شده در ۶۰ دقیقه اخیر؛ مستقل از ری‌استارت برنامه
        try:
            cutoff = time.time() - 3600
            recent_hour_trades = [t for t in list(performance_memory.trades) if float(t.get("timestamp", 0)) >= cutoff]
            hour_wins = sum(1 for t in recent_hour_trades if t.get("win"))
            hour_n = len(recent_hour_trades)
            hour_pf = performance_memory.get_profit_factor(hour_n) if recent_hour_trades else 0.0
            hour_note = " ⚠️ نمونه کوچک – غیرقابل اتکا" if hour_n < 25 else ""
            lines.append(
                f"  • ۶۰ دقیقه اخیر: {hour_n} معامله بسته‌شده | "
                f"WR {((hour_wins/hour_n)*100 if hour_n else 0):.1f}% | PF {hour_pf:.2f}{hour_note}"
            )
        except Exception:
            lines.append("  • این ساعت: داده قابل محاسبه نیست")

        # ============================
        # 2. عملکرد ML
        # ============================
        configured_ml_influence = float(CONFIG.get("ML_MAX_INFLUENCE", 0.0))
        actual_ml_influence = ml_model.get_influence_weight() if ml_model.is_trained else 0.0
        ml_enabled = actual_ml_influence > 0.0
        lines.append("")
        lines.append("🧠 **وضعیت ML:**")
        lines.append(f"  • وضعیت: {'✅ فعال' if ml_enabled else '⏸️ آماده/بدون اثر فعلی'}")
        lines.append(f"  • سهم واقعی فعلی: {actual_ml_influence*100:.1f}% | سقف: {configured_ml_influence*100:.0f}%")
        lines.append(f"  • آموزش‌دیده: {'بله' if ml_model.is_trained else 'خیر'}")
        if ml_model.is_trained:
            sem_txt = f"{ml_model.wf_auc_sem:.3f}" if ml_model.wf_auc_sem is not None else "N/A"
            lines.append(f"  • WF AUC: {ml_model.wf_auc_mean:.3f} ± {ml_model.wf_auc_std:.3f} (SEM={sem_txt})")
            lines.append(f"  • آخرین تست AUC: {ml_model.last_test_auc}")
            lines.append(f"  • وضعیت مدل: {ml_model.health}")
            lines.append(f"  • تعداد آموزش: {ml_summary.get('total_trainings', 0)}")
        
        # ============================
        # 3. عملکرد با/بدون ML
        # ============================
        lines.append("")
        lines.append("📊 **مقایسه با/بدون ML:**")
        with_ml = ml_perf.get("with_ml", {})
        without_ml = ml_perf.get("without_ml", {})
        lines.append(f"  • با ML: {with_ml.get('trades', 0)} معامله, وین‌ریت {with_ml.get('winrate', 0):.1f}%")
        lines.append(f"  • بدون ML: {without_ml.get('trades', 0)} معامله, وین‌ریت {without_ml.get('winrate', 0):.1f}%")
        improvement = with_ml.get('winrate', 0) - without_ml.get('winrate', 0)
        if with_ml.get('trades', 0) > 0 and without_ml.get('trades', 0) > 0:
            lines.append(f"  • تفاوت: {improvement:+.1f}%")
        live_s = ml_perf.get("live_only") or {}
        auto_s = ml_perf.get("auto_learn_only") or {}
        if live_s.get("trades") or auto_s.get("trades"):
            lines.append(
                f"  • Live/non-auto: {live_s.get('trades', 0)} | WR {live_s.get('winrate', 0):.1f}% | "
                f"Auto-learn: {auto_s.get('trades', 0)} | WR {auto_s.get('winrate', 0):.1f}%"
            )
        try:
            pr = portfolio_risk.summary()
            paper_n = int(pr.get("paper_open") or 0)
            risk_paper = round(paper_n * float(CONFIG.get("RISK_PERCENT", 0.55)), 2)
            lines.append(
                f"  • Portfolio: mode={pr.get('mode')} | paper={paper_n} | "
                f"unique_open={pr.get('unique_open')} | risk_paper≈{risk_paper}% | "
                f"daily_loss_lock={'🔒' if pr.get('daily_loss_breach') else '🔓'} | "
                f"port_risk_lock={'🔒' if pr.get('portfolio_risk_breach') else '🔓'}"
            )
        except Exception:
            pass
        
        # ============================
        # 4. عملکرد رژیم‌های بازار
        # ============================
        lines.append("")
        lines.append("🌐 **عملکرد رژیم‌های بازار:**")
        for regime, stats in sorted(regime_perf.items()):
            if regime in ("RANGING",):
                continue
            adj = float(CONFIG.get("REGIME_CONFIDENCE_ADJUSTMENT", {}).get(regime, 0))
            gate_base = float(CONFIG.get("MIN_CONFIDENCE_SCORE", 5.5))
            hard_cap = float(CONFIG.get("MAX_EFFECTIVE_CONFIDENCE", 6.6))
            effective_gate = min(hard_cap, gate_base + adj)
            lines.append(f"  • {regime}: {stats['wins']}/{stats['total']} برد ({stats.get('winrate', 0):.0f}%) | آستانه: {effective_gate:.1f}")
        
        # ============================
        # 5. تغییرات اخیر پارامترها (فقط همین بازهٔ گزارش)
        # ============================
        lines.append("")
        lines.append("🔄 **تغییرات اخیر پارامترها:**")
        if param_changes:
            seen_changes = set()
            unique_changes = []
            for change in reversed(param_changes):
                parameter_key = change.get("parameter") or f"REGIME_CONFIDENCE_ADJUSTMENT[{change.get('regime')}]"
                key = (parameter_key, str(change.get("old")), str(change.get("new")), str(change.get("reason")))
                if key not in seen_changes:
                    seen_changes.add(key)
                    unique_changes.append(change)
                if len(unique_changes) >= 5:
                    break
            for change in reversed(unique_changes):
                parameter = change.get("parameter")
                if not parameter and change.get("regime"):
                    parameter = f"REGIME_CONFIDENCE_ADJUSTMENT[{change.get('regime')}]"
                parameter = parameter or "UNKNOWN_PARAMETER"
                lines.append(f"  • {parameter}: {change.get('old', '?')} → {change.get('new', '?')}")
                lines.append(f"    دلیل: {change.get('reason', 'بهینه‌سازی خودکار')}")
        else:
            lines.append("  • بدون تغییر پارامتر در این بازه")
        
        # ============================
        # 6. تغییرات وزن فیچرها
        # ============================
        if weight_changes:
            lines.append("")
            lines.append("⚖️ **تغییرات وزن فیچرها:**")
            for change in weight_changes[-5:]:
                feat = change.get('feature', '?')
                old = change.get('old', 1.0)
                new = change.get('new', 1.0)
                arrow = "📈" if new > old else "📉" if new < old else "➖"
                lines.append(f"  {arrow} {feat}: {old:.2f} → {new:.2f}")
        
        # ============================
        # 7. وزن‌های فعلی فیچرها
        # ============================
        lines.append("")
        lines.append("⚖️ **وزن فیچرها (یادگیری):**")
        for feat, weight in sorted(weight_learner.feature_weights.items(), key=lambda x: -x[1])[:5]:
            lines.append(f"  • {feat}: {weight:.2f}")
        
        # ============================
        # 8. کیفیت زمان‌بندی ورود
        # ============================
        lines.append("")
        lines.append("⏱️ **کیفیت زمان‌بندی ورود:**")
        if timing.get("available"):
            lines.append(f"  • حرکت قبل از سیگنال: {timing['avg_pre_signal_move_pct']:.2f}%")
            lines.append(f"  • احتمال TP1: {timing['tp1_hit_rate_pct']:.0f}%")
            lines.append(f"  • احتمال SL: {timing['sl_hit_rate_pct']:.0f}%")
            if timing.get("avg_time_to_result_min"):
                lines.append(f"  • زمان تا نتیجه: {timing['avg_time_to_result_min']:.0f} دقیقه")
        else:
            lines.append(f"  • داده کافی نیست ({timing.get('sample_size', 0)}/5 نمونه)")
        
        # ============================
        # 9. الگوهای یاد گرفته‌شده
        # ============================
        lines.append("")
        lines.append("🎯 **الگوهای یاد گرفته‌شده:**")
        lines.append(f"  • موفق: {len(pattern_recognizer.successful_patterns)}")
        lines.append(f"  • ناموفق: {len(pattern_recognizer.failed_patterns)}")
        
        # ============================
        # 10. وضعیت صف انتظار
        # ============================
        lines.append("")
        lines.append(f"⏳ **صف انتظار:** {pending['total_pending']} سیگنال")
        if pending["total_pending"] > 0:
            lines.append(f"  • TP1: {pending['tp1_hit']} | SL: {pending['sl_hit']} | باز: {pending['still_open']}")
            if pending.get("regime_counts"):
                counts = ", ".join(f"{r}: {c}" for r, c in sorted(pending["regime_counts"].items()))
                lines.append(f"  • رژیم‌ها: {counts}")
            if pending.get("ml_used_count", 0) > 0:
                lines.append(f"  • با ML: {pending['ml_used_count']}")
        
        # ============================
        # 11. تنظیمات فعلی مهم
        # ============================
        lines.append("")
        lines.append("⚙️ **تنظیمات فعلی:**")
        lines.append(f"  • آستانه پامپ: {CONFIG.get('PUMP_THRESHOLD', 1.2):.2f}%")
        lines.append(f"  • آستانه دامپ: {CONFIG.get('DUMP_THRESHOLD', -1.2):.2f}%")
        lines.append(f"  • حداقل اطمینان: {CONFIG.get('MIN_CONFIDENCE_SCORE', 5.5):.1f}")
        lines.append(f"  • ATR_MULT_SL: {CONFIG.get('ATR_MULT_SL', 1.4):.2f}")
        lines.append(f"  • MAX_HOLD: {CONFIG.get('MAX_HOLD_MINUTES', 45)} دقیقه")
        lines.append(f"  • RISK: {CONFIG.get('RISK_PERCENT', 0.6):.2f}%")
        lines.append(f"  • Max Signals/Cycle: {CONFIG.get('MAX_NEW_SIGNALS_PER_CYCLE', 4)}")
        
        # ============================
        # 12. تشخیص مسیر سیگنال
        # ============================
        diag = _diag_snapshot()
        hourly_diag = diag.get("window", diag.get("hourly", {}))
        if hourly_diag:
            lines.append("")
            lines.append("🧭 **تشخیص مسیر سیگنال در این بازه ۳۰ دقیقه‌ای:**")
            stage_order = ["TRIGGER", "ANALYSIS_ENTERED", "KLINES_OK", "QUALITY_OK", "VOLATILITY_OK", "BREAKOUT_OK", "REGIME_OK", "ANALYSIS_OK", "GATE_EVALUATED", "TECHNICAL_ACCEPTED", "ACCEPTED"]
            shown = []
            for stage in stage_order:
                rows = [v for k,v in hourly_diag.items() if v.get("stage") == stage]
                count = sum(int(v.get("count",0)) for v in rows)
                if count:
                    shown.append((stage, count))
            for stage, count in shown:
                lines.append(f"  • {stage}: {count}")
            technical_accepted = sum(int(v.get("count", 0)) for v in hourly_diag.values() if v.get("stage") == "TECHNICAL_ACCEPTED")
            final_accepted = sum(int(v.get("count", 0)) for v in hourly_diag.values() if v.get("stage") == "ACCEPTED")
            if technical_accepted or final_accepted:
                lines.append(f"  • 🎯 Technical accepted → Final accepted: {technical_accepted} → {final_accepted}")
            rejects = [(v.get("reason",""), int(v.get("count",0))) for v in hourly_diag.values() if v.get("stage") == "REJECT"]
            rejects.sort(key=lambda x: x[1], reverse=True)
            if rejects:
                lines.append("  • مهم‌ترین علت‌های رد:")
                for reason, count in rejects[:10]:
                    lines.append(f"     - {reason}: {count}")

        # ============================
        # 13. سلامت Runtime / تشخیص واقعی وضعیت برنامه
        # ============================
        runtime = dict(_RUNTIME_STATE)
        health = _system_health_snapshot()
        window_sec = max(1.0, time.time() - _safe_float(runtime.get("window_started"), time.time()))
        avg_fetch = (_safe_float(runtime.get("fetch_latency_ms_sum"), 0.0) / max(1, _safe_int(runtime.get("fetch_latency_samples"), 0)))
        analysis_calls = _safe_int(runtime.get("analysis_calls"), 0)
        analysis_success = _safe_int(runtime.get("analysis_success"), 0)
        triggered = _safe_int(runtime.get("triggered"), 0)
        normal_sig = _safe_int(runtime.get("normal_signals"), 0)
        fallback_sig = _safe_int(runtime.get("fallback_signals"), 0)
        lines.append("")
        lines.append("🩺 **سلامت Runtime / این بازه ۳۰ دقیقه‌ای:**")
        lines.append(f"  • وضعیت کلی: {'🟢 سالم' if health.get('status') == 'OK' and _safe_int(runtime.get('cycle_errors'),0) == 0 else '🟠 نیازمند بررسی'} | Uptime: {health.get('uptime_sec',0)/3600:.1f}h")
        lines.append(f"  • سیکل‌ها: {_safe_int(runtime.get('cycles'))} | خطای سیکل: {_safe_int(runtime.get('cycle_errors'))} | سیکل خالی API: {_safe_int(runtime.get('empty_ticker_cycles'))}")
        lines.append(f"  • Symbols: {_safe_int(runtime.get('symbols_seen'))} بررسی تجمعی | آخرین batch: {_safe_int(runtime.get('last_ticker_count'))}")
        lines.append(f"  • Trigger: {triggered} | Pump: {_safe_int(runtime.get('pump_triggers'))} | Dump: {_safe_int(runtime.get('dump_triggers'))}")
        lines.append(f"  • Analysis: {analysis_success}/{analysis_calls} موفق ({(analysis_success/analysis_calls*100 if analysis_calls else 0):.1f}%)")
        lines.append(f"  • Signal: normal={normal_sig} | fallback={fallback_sig} | total={normal_sig+fallback_sig}")
        lines.append(f"  • Fetch latency: avg={avg_fetch:.0f}ms | last={_safe_float(runtime.get('last_fetch_latency_ms'),0):.0f}ms")
        last_finished = _safe_float(runtime.get("last_cycle_finished"), 0.0)
        cycle_age = (time.time() - last_finished) if last_finished > 0 else None
        lines.append(f"  • آخرین سیکل: {runtime.get('last_cycle_duration_sec','N/A')}s | age={cycle_age:.0f}s" if cycle_age is not None else "  • آخرین سیکل: هنوز اجرا نشده")
        lines.append(f"  • RAM: {health.get('ram_used_pct','N/A')}% | Disk: {health.get('disk_used_pct','N/A')}% | Load: {health.get('loadavg','N/A')}")
        lines.append(f"  • Telegram signal delivery: OK={_safe_int(runtime.get('telegram_signal_ok'))} | FAIL={_safe_int(runtime.get('telegram_signal_fail'))}")
        lines.append(f"  • Telegram report: OK={_safe_int(runtime.get('telegram_report_ok'))} | FAIL={_safe_int(runtime.get('telegram_report_fail'))}")
        try:
            td = dict(TELEGRAM_DELIVERY_STATS)
            lines.append(f"  • Telegram signals: attempts={td.get('ATTEMPT',0)} | sent={td.get('SENT',0)} | failed={td.get('FAILED',0)} | cooldown={td.get('COOLDOWN',0)} | config_missing={td.get('CONFIG_MISSING',0)} | exceptions={td.get('EXCEPTION',0)}")
        except Exception:
            lines.append("  • Telegram signals: telemetry unavailable")

        # Explicit post-gate diagnosis: ACCEPTED must have a traceable outcome.
        try:
            accepted_rt = _safe_int(runtime.get("accepted_candidates"))
            created_rt = _safe_int(runtime.get("signal_created"))
            tg_attempts = _safe_int(runtime.get("telegram_attempts"))
            tg_sent = _safe_int(runtime.get("telegram_sent"))
            if accepted_rt > created_rt:
                lines.append(f"  • 🔴 Post-gate gap: {accepted_rt-created_rt} accepted candidate(s) did not reach SIGNAL_CREATED")
            elif created_rt > tg_attempts:
                lines.append(f"  • 🟠 Delivery gap: {created_rt-tg_attempts} created signal(s) had no Telegram attempt")
            elif tg_attempts > tg_sent:
                lines.append(f"  • 🟠 Telegram gap: {tg_attempts-tg_sent} attempt(s) not confirmed sent (failure/cooldown may explain)")
            elif accepted_rt > 0:
                lines.append("  • 🟢 Post-gate chain consistent through Telegram attempts")
        except Exception:
            pass

        lines.append("")
        lines.append("🧠 **یادگیری واقعی / شواهد یادگیری:**")
        lines.append(f"  • ML retrain: attempts={_safe_int(runtime.get('ml_retrain_attempts'))} | success={_safe_int(runtime.get('ml_retrain_success'))} | fail={_safe_int(runtime.get('ml_retrain_fail'))}")
        lines.append(f"  • آخرین آموزش: {datetime.fromtimestamp(_safe_float(runtime.get('last_ml_train'),0)).strftime('%Y-%m-%d %H:%M:%S') if _safe_float(runtime.get('last_ml_train'),0) > 0 else 'نداشته'}")
        last_ml_result = runtime.get('last_ml_result') or {}
        if isinstance(last_ml_result, dict):
            lines.append(f"  • آخرین نتیجه ML: status={'SUCCESS' if last_ml_result.get('wf_auc') is not None else last_ml_result.get('status','UNKNOWN')} | n={last_ml_result.get('n_trades', getattr(ml_model,'dataset_n',0))} | WF AUC={last_ml_result.get('wf_auc', getattr(ml_model,'wf_auc_mean',None))}")
        lines.append(f"  • تغییرات یادگیری ۸ساعته: {_safe_int(runtime.get('learning_updates'))} | آخرین تغییر: {datetime.fromtimestamp(_safe_float(runtime.get('last_learning_update'),0)).strftime('%Y-%m-%d %H:%M:%S') if _safe_float(runtime.get('last_learning_update'),0) > 0 else 'نداشته'}")
        lines.append(f"  • Pattern memory: موفق={len(pattern_recognizer.successful_patterns)} | ناموفق={len(pattern_recognizer.failed_patterns)} | Feature weights={len(weight_learner.feature_weights)}")
        lines.append(f"  • ML dataset={getattr(ml_model,'dataset_n',0)} | trained_on={getattr(ml_model,'trained_on_n_trades',0)} | health={getattr(ml_model,'health','UNKNOWN')} | influence={actual_ml_influence*100:.2f}%")

        lines.append("")
        lines.append("🔐 **یکپارچگی تنظیمات/محیط:**")
        dep_status = f"sklearn={'OK' if SKLEARN_AVAILABLE else 'MISSING'} | xgboost={'OK' if XGBOOST_AVAILABLE else 'NO'} | catboost={'OK' if CATBOOST_AVAILABLE else 'NO'}"
        lines.append(f"  • Dependencies: {dep_status}")
        lines.append(f"  • Python={sys.version.split()[0]} | PID={os.getpid()} | DATA_DIR={DATA_DIR}")
        lines.append(f"  • Interval={CONFIG.get('KLINE_INTERVAL')} | check={CONFIG.get('CHECK_INTERVAL')}s | report={CONFIG.get('REPORT_INTERVAL_SEC')}s")
        lines.append(f"  • PRO gate={'ON' if CONFIG.get('PRO_ENABLE_FINAL_QUALITY_GATE') else 'OFF'} | closed candle={CONFIG.get('REQUIRE_CLOSED_CANDLE', True)}")

        # ============================
        # Level-5 telemetry integrity / self-healing evidence
        # ============================
        try:
            integrity = _telemetry_integrity_check(repair=True)
            with _RUNTIME_LOCK:
                runtime = copy.deepcopy(_RUNTIME_STATE)
            lines.append("")
            lines.append("🛠️ **یکپارچگی Telemetry / Self-Repair:**")
            lines.append(f"  • وضعیت: {integrity.get('status', 'UNKNOWN')}")
            if integrity.get("issues"):
                lines.append(f"  • اختلاف‌های کشف‌شده: {len(integrity['issues'])}")
                for issue in integrity["issues"][:8]:
                    lines.append(f"     - {issue}")
            if integrity.get("repairs"):
                lines.append(f"  • تعمیرات انجام‌شده: {len(integrity['repairs'])}")
            lines.append(f"  • تأیید پس از تعمیر: {'PASS' if integrity.get('verified') else 'FAIL'}")
            lines.append(f"  • Telemetry repair actions: {_safe_int(runtime.get('telemetry_repairs'))}")
            lines.append(f"  • Self-Repair runs: {_safe_int(runtime.get('self_repair_runs'))} | actions: {_safe_int(runtime.get('self_repair_actions'))} | failures: {_safe_int(runtime.get('self_repair_failures'))}")
            lines.append(f"  • Integrity failures: {_safe_int(runtime.get('telemetry_integrity_failures'))}")
            lines.append("  • محدوده تعمیر: فقط Telemetry/Observability؛ بدون تغییر Risk/Threshold/ML influence.")
        except Exception as e:
            lines.append(f"  • ⚠️ Telemetry integrity unavailable: {e}")

        # ============================
        # تشخیص خودکار گلوگاه — مهم‌ترین بخش برای زمانی که سیگنال صفر است
        # ============================
        try:
            total_candidates = sum(int(v.get("count", 0)) for v in hourly_diag.values() if v.get("stage") == "REJECT" and v.get("reason") == "trigger_not_reached")
            gate_evals = sum(int(v.get("count", 0)) for v in hourly_diag.values() if v.get("stage") == "GATE_EVALUATED")
            accepted_diag = sum(int(v.get("count", 0)) for v in hourly_diag.values() if v.get("stage") == "ACCEPTED")
            trigger_count = _diag_stage_count(diag, "TRIGGER")
            authoritative_analysis = _diag_stage_count(diag, "ANALYSIS_OK")
            authoritative_analysis_calls = _diag_stage_count(diag, "ANALYSIS_ENTERED")
            if normal_sig + fallback_sig == 0:
                lines.append("")
                lines.append("🚨 **تشخیص خودکار سیگنال صفر:**")
                if trigger_count == 0:
                    lines.append("  • 🔴 هیچ Triggerای در این بازه ثبت نشده؛ گلوگاه قبل از تحلیل است (حرکت ۱۵m/threshold/history).")
                elif authoritative_analysis_calls > 0 and authoritative_analysis == 0:
                    lines.append("  • 🔴 Trigger وجود داشته ولی هیچ تحلیل موفقی عبور نکرده؛ گلوگاه داخل فیلترهای تحلیل است.")
                elif gate_evals > 0 and accepted_diag == 0:
                    lines.append("  • 🔴 تحلیل به Gate رسیده ولی هیچ موردی قبول نشده؛ Confidence/PRO Gate را بررسی کنید.")
                else:
                    lines.append("  • 🟠 Trigger وجود داشته اما سیگنال نهایی صفر است؛ جدول علت‌های REJECT بالاتر مرجع اصلی است.")
                lines.append(f"  • Funnel: trigger={trigger_count} | analysis={authoritative_analysis}/{authoritative_analysis_calls} | gate={gate_evals} | accepted={accepted_diag}")
            else:
                lines.append("")
                lines.append(f"🟢 **سیگنال‌سازی سالم:** {normal_sig + fallback_sig} سیگنال نهایی در این بازه ثبت شده است.")
        except Exception as e:
            lines.append(f"  • ⚠️ خطا در تشخیص خودکار funnel: {e}")

        # ============================
        # 14. CEZARTRADING 20 PRO diagnostics
        # ============================
        lines.extend(_pro_report_appendix(price_map))

        # ============================
        # 14. گیت سیگنال
        # ============================
        with _REGIME_GATE_LOCK:
            evaluated = dict(_REGIME_GATE_STATS.get("evaluated", {}))
            passed_map = dict(_REGIME_GATE_STATS.get("passed", {}))
            _REGIME_GATE_STATS["evaluated"] = {}
            _REGIME_GATE_STATS["passed"] = {}
        if evaluated:
            lines.append("")
            lines.append("🔍 **گیت سیگنال (قبول/کل):**")
            for regime in sorted(evaluated.keys()):
                ev = evaluated.get(regime, 0)
                passed = passed_map.get(regime, 0)
                lines.append(f"  • {regime}: {passed}/{ev} قبول شد")
        if reset_window:
            try:
                with _RUNTIME_LOCK:
                    _runtime_save_locked(force=True)
            except Exception as _fe:
                logger.debug(f"runtime force flush before report reset: {_fe}")
            _diag_reset_window_after_report()
            _runtime_reset_window()
        
        lines.append("")
        lines.append("=" * 60)
        
        report_text = "\n".join(lines)
        
        # ذخیره گزارش
        try:
            _REPORT_HISTORY.append({
                "timestamp": time.time(),
                "winrate": summary['long_term_winrate'],
                "pf": summary.get('profit_factor', 0),
                "trades": summary['total_trades'],
                "ml_enabled": ml_enabled
            })
            if len(_REPORT_HISTORY) > 100:
                _REPORT_HISTORY = _REPORT_HISTORY[-100:]
            _atomic_write_json(PATHS["REPORT_HISTORY"], _REPORT_HISTORY)
        except Exception:
            pass
        
        return report_text
        
    except Exception as e:
        logger.error(f"خطا در ساخت گزارش: {e}")
        return f"⚠️ خطا در ساخت گزارش: {e}"


# ============================================================================
# Level-5 reliable report delivery
# ============================================================================
def _split_telegram_text(text: str, max_chars: int = 3800) -> List[str]:
    text = str(text or "").strip()
    if not text:
        return []
    max_chars = max(1000, int(max_chars))
    if len(text) <= max_chars:
        return [text]
    chunks, current = [], ""
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        candidate = block if not current else current + "\n\n" + block
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            while len(block) > max_chars:
                cut = block.rfind("\n", 0, max_chars)
                if cut < max_chars // 2:
                    cut = max_chars
                chunks.append(block[:cut].rstrip())
                block = block[cut:].lstrip()
            current = block
    if current:
        chunks.append(current)
    return chunks

def _parse_trade_ts(trade: dict) -> float:
    ts = trade.get("timestamp", 0)
    try:
        if isinstance(ts, (int, float)):
            return float(ts)
        if isinstance(ts, str) and ts.strip():
            # ISO or numeric string
            try:
                return float(ts)
            except ValueError:
                from datetime import datetime
                return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        pass
    return 0.0


# ============================================================================
# Outcome reports: checkpoint-based 2h detail + 6h aggregate
# ============================================================================
_SENT_SIGNALS_LOCK = threading.Lock()
_SENT_SIGNALS: list = []  # {id, ts, symbol, direction, entry}
_OUTCOME_STATE = {"last_2h_ts": 0.0, "last_6h_ts": 0.0}


def _load_sent_signals_log() -> None:
    global _SENT_SIGNALS
    path = PATHS.get("SENT_SIGNALS_LOG")
    try:
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            items = obj.get("signals", obj if isinstance(obj, list) else [])
            _SENT_SIGNALS = [x for x in items if isinstance(x, dict)][-2000:]
    except Exception as e:
        logger.warning(f"load sent_signals_log failed: {e}")
        _SENT_SIGNALS = []


def _save_sent_signals_log() -> None:
    path = PATHS.get("SENT_SIGNALS_LOG")
    if not path:
        return
    try:
        with _SENT_SIGNALS_LOCK:
            payload = {"signals": list(_SENT_SIGNALS)[-2000:], "timestamp": time.time()}
        _atomic_write_json(path, payload)
    except Exception as e:
        logger.warning(f"save sent_signals_log failed: {e}")


def _load_outcome_report_state() -> None:
    global _OUTCOME_STATE
    path = PATHS.get("OUTCOME_REPORT_STATE")
    try:
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, dict):
                _OUTCOME_STATE["last_2h_ts"] = float(obj.get("last_2h_ts") or 0)
                _OUTCOME_STATE["last_6h_ts"] = float(obj.get("last_6h_ts") or 0)
    except Exception as e:
        logger.warning(f"load outcome_report_state failed: {e}")


def _save_outcome_report_state() -> None:
    path = PATHS.get("OUTCOME_REPORT_STATE")
    if not path:
        return
    try:
        _atomic_write_json(path, dict(_OUTCOME_STATE))
    except Exception as e:
        logger.warning(f"save outcome_report_state failed: {e}")


def _record_sent_signal(summary: dict) -> None:
    """ثبت سیگنال واقعاً ارسال‌شده به تلگرام برای گزارش‌های outcome."""
    sym = str(summary.get("symbol", "")).upper().strip()
    direction = str(summary.get("direction", "")).upper().strip()
    if not sym or not direction:
        return
    now = time.time()
    entry = summary.get("entry") or summary.get("price")
    sig_id = f"{sym}|{direction}|{int(now * 1000)}"
    rec = {
        "id": sig_id,
        "ts": now,
        "symbol": sym,
        "direction": direction,
        "entry": entry,
    }
    with _SENT_SIGNALS_LOCK:
        _SENT_SIGNALS.append(rec)
        # نگه داشتن حداکثر ~۷ روز با فرض حجم متوسط
        if len(_SENT_SIGNALS) > 2000:
            del _SENT_SIGNALS[:-2000]
    _save_sent_signals_log()


def _outcome_label_of(t: dict) -> str:
    lab = (t.get("outcome_label") or t.get("which_target") or "").strip().upper()
    if lab in ("TP1", "TP2", "TP3", "SL", "TIMEOUT"):
        return lab
    if t.get("win") is True:
        return "TP?"
    if t.get("win") is False:
        return "SL?"
    return "OTHER"


def _match_outcome_for_signal(sig: dict, trades: list, match_window: float) -> Optional[dict]:
    """اولین outcome هم‌نماد/هم‌جهت بعد از زمان سیگنال (در پنجره مجاز)."""
    sym = sig.get("symbol")
    direction = (sig.get("direction") or "").upper()
    sent_ts = float(sig.get("ts") or 0)
    best = None
    best_ts = None
    for t in trades:
        if str(t.get("symbol", "")).upper() != sym:
            continue
        if (t.get("direction") or "").upper() != direction:
            continue
        tts = _parse_trade_ts(t)
        if tts < sent_ts - 30:  # کمی تلورانس ساعت
            continue
        if tts - sent_ts > match_window:
            continue
        if best is None or tts < best_ts:
            best = t
            best_ts = tts
    return best


def _live_open_tag(direction: str, entry, price) -> tuple:
    """برای سیگنال هنوز باز: جهت لحظه‌ای نسبت به ورود (رو به TP / رو به SL)."""
    try:
        entry_f = float(entry) if entry is not None else None
        price_f = float(price) if price is not None else None
    except (TypeError, ValueError):
        return "OPEN", ""
    if entry_f is None or price_f is None or entry_f <= 0 or price_f <= 0:
        return "OPEN", ""
    d = (direction or "").upper()
    is_long = d in ("LONG", "BUY", "L")
    if is_long:
        ret = (price_f - entry_f) / entry_f * 100.0
    else:
        ret = (entry_f - price_f) / entry_f * 100.0
    ret_s = f" | {ret:+.2f}%"
    if ret > 0.05:
        return "OPEN → رو به TP", ret_s
    if ret < -0.05:
        return "OPEN → رو به SL", ret_s
    return "OPEN → خنثی", ret_s


def _resolve_signals_in_window(since_ts: float, until_ts: float, price_map: Optional[dict] = None) -> dict:
    """سیگنال‌های ارسال‌شده در [since, until) را با outcome مچ می‌کند (بدون تکرار id)."""
    match_window = float(CONFIG.get("OUTCOME_SIGNAL_MATCH_WINDOW_SEC", 7200))
    with _SENT_SIGNALS_LOCK:
        signals = [s for s in _SENT_SIGNALS if since_ts <= float(s.get("ts") or 0) < until_ts]

    # dedupe by id
    seen_ids = set()
    unique_sigs = []
    for s in signals:
        sid = s.get("id") or f"{s.get('symbol')}|{s.get('direction')}|{s.get('ts')}"
        if sid in seen_ids:
            continue
        seen_ids.add(sid)
        unique_sigs.append(s)

    trades = []
    try:
        trades = list(getattr(performance_memory, "trades", []) or [])
    except Exception:
        trades = []

    if price_map is None:
        price_map = {}
        try:
            coins = fetch_binance_all_ticker() or []
            price_map = {
                str(c.get("symbol", "")).upper(): float(c.get("current_price") or c.get("last") or 0)
                for c in coins
                if c.get("symbol")
            }
        except Exception as e:
            logger.debug(f"price_map for OPEN status failed: {e}")
            price_map = {}

    rows = []
    n_tp1 = n_tp2 = n_tp3 = n_sl = n_timeout = n_other = n_open = 0
    n_win = n_loss = 0
    n_to_toward_tp = n_to_toward_sl = n_to_flat = 0
    n_open_toward_tp = n_open_toward_sl = n_open_flat = 0
    sum_return_closed = 0.0
    sum_return_decided = 0.0
    n_ret_closed = 0
    n_ret_decided = 0

    for sig in unique_sigs:
        trade = _match_outcome_for_signal(sig, trades, match_window)
        sym = sig.get("symbol") or "?"
        direction = (sig.get("direction") or "?").upper()
        if trade is None:
            n_open += 1
            px = price_map.get(str(sym).upper())
            tag, ret_s = _live_open_tag(direction, sig.get("entry"), px)
            if "رو به TP" in tag:
                n_open_toward_tp += 1
            elif "رو به SL" in tag:
                n_open_toward_sl += 1
            else:
                n_open_flat += 1
            rows.append({"emoji": "⏳", "sym": sym, "direction": direction, "tag": tag, "ret_s": ret_s})
            continue
        lab = _outcome_label_of(trade)
        ret = trade.get("return_pct")
        try:
            ret_f = float(ret) if ret is not None else None
        except Exception:
            ret_f = None
        try:
            ret_s = f" | {ret_f:+.2f}%" if ret_f is not None else ""
        except Exception:
            ret_s = ""
        if lab == "TP1":
            n_tp1 += 1
            n_win += 1
            emoji, tag = "✅", "TP1"
        elif lab == "TP2":
            n_tp2 += 1
            n_win += 1
            emoji, tag = "✅", "TP2"
        elif lab == "TP3":
            n_tp3 += 1
            n_win += 1
            emoji, tag = "✅", "TP3"
        elif lab in ("SL", "SL?"):
            n_sl += 1
            n_loss += 1
            emoji, tag = "❌", "SL"
        elif lab == "TIMEOUT":
            n_timeout += 1
            # از نظر ورود: مثبت = رو به TP | منفی = رو به SL
            if ret_f is None:
                n_to_flat += 1
                emoji, tag = "⏱️", "TIMEOUT | نامشخص"
            elif ret_f > 0.05:
                n_to_toward_tp += 1
                emoji, tag = "⏱️", "TIMEOUT → رو به TP"
            elif ret_f < -0.05:
                n_to_toward_sl += 1
                emoji, tag = "⏱️", "TIMEOUT → رو به SL"
            else:
                n_to_flat += 1
                emoji, tag = "⏱️", "TIMEOUT → خنثی"
        else:
            n_other += 1
            emoji, tag = "▫️", lab or "OTHER"
        if ret_f is not None:
            sum_return_closed += ret_f
            n_ret_closed += 1
            if lab in ("TP1", "TP2", "TP3", "SL", "SL?"):
                sum_return_decided += ret_f
                n_ret_decided += 1
        rows.append({"emoji": emoji, "sym": sym, "direction": direction, "tag": tag, "ret_s": ret_s})

    closed = n_win + n_loss + n_timeout + n_other
    decided = n_win + n_loss
    return {
        "signals": unique_sigs,
        "rows": rows,
        "n_sent": len(unique_sigs),
        "n_tp1": n_tp1,
        "n_tp2": n_tp2,
        "n_tp3": n_tp3,
        "n_sl": n_sl,
        "n_timeout": n_timeout,
        "n_to_toward_tp": n_to_toward_tp,
        "n_to_toward_sl": n_to_toward_sl,
        "n_to_flat": n_to_flat,
        "n_other": n_other,
        "n_open": n_open,
        "n_open_toward_tp": n_open_toward_tp,
        "n_open_toward_sl": n_open_toward_sl,
        "n_open_flat": n_open_flat,
        "n_win": n_win,
        "n_loss": n_loss,
        "closed": closed,
        "decided": decided,
        "wr_decided": (n_win / decided * 100.0) if decided > 0 else 0.0,
        "wr_all_closed": (n_win / closed * 100.0) if closed > 0 else 0.0,
        "sum_return_closed_pct": round(sum_return_closed, 2),
        "sum_return_decided_pct": round(sum_return_decided, 2),
        "avg_return_closed_pct": round(sum_return_closed / n_ret_closed, 3) if n_ret_closed else 0.0,
        "avg_return_decided_pct": round(sum_return_decided / n_ret_decided, 3) if n_ret_decided else 0.0,
    }


def build_2h_outcome_report(since_ts: Optional[float] = None, until_ts: Optional[float] = None) -> str:
    """فقط سیگنال‌های ارسال‌شده از آخرین checkpoint تا الان (نه کل حافظه غلتان)."""
    now = float(until_ts or time.time())
    # اگر checkpoint نبود، حداکثر ۲ ساعت عقب
    default_since = now - float(CONFIG.get("OUTCOME_REPORT_INTERVAL_SEC", 7200))
    since = float(since_ts if since_ts is not None else (_OUTCOME_STATE.get("last_2h_ts") or default_since))
    if since <= 0:
        since = default_since
    if since >= now:
        since = default_since

    data = _resolve_signals_in_window(since, now)
    start_txt = time.strftime("%H:%M", time.localtime(since))
    end_txt = time.strftime("%H:%M", time.localtime(now))
    date_txt = time.strftime("%Y-%m-%d", time.localtime(now))

    lines = [
        f"📋 نتایج از آخرین خلاصه — {date_txt} {start_txt}–{end_txt}",
        f"(فقط سیگنال‌های ارسال‌شده در این بازه)",
        "",
    ]
    if data["rows"]:
        for r in data["rows"]:
            lines.append(f"{r['emoji']} {r['sym']} {r['direction']} → {r['tag']}{r['ret_s']}")
    else:
        lines.append("• در این بازه سیگنال ارسال‌شده‌ای ثبت نشده.")

    to_line = (
        f"TIMEOUT جزئی: رو به TP={data.get('n_to_toward_tp', 0)} | "
        f"رو به SL={data.get('n_to_toward_sl', 0)} | خنثی={data.get('n_to_flat', 0)}"
        if data.get("n_timeout") else None
    )
    open_line = (
        f"OPEN جزئی: رو به TP={data.get('n_open_toward_tp', 0)} | "
        f"رو به SL={data.get('n_open_toward_sl', 0)} | خنثی/نامشخص={data.get('n_open_flat', 0)}"
        if data.get("n_open") else None
    )
    lines.extend([
        "",
        "📊 جمع این بازه:",
        f"سیگنال ارسال‌شده: {data['n_sent']}",
        f"بسته شده: {data['closed']} | برد (TP1/2/3): {data['n_win']} | باخت (SL): {data['n_loss']} | باز: {data['n_open']}",
        f"TP1: {data['n_tp1']} | TP2: {data['n_tp2']} | TP3: {data['n_tp3']} | SL: {data['n_sl']} | TIMEOUT: {data['n_timeout']}"
        + (f" | OTHER: {data['n_other']}" if data["n_other"] else ""),
        *([to_line] if to_line else []),
        *([open_line] if open_line else []),
        (
            f"موفقیت (بدون TIMEOUT): {data['wr_decided']:.1f}%  ({data['n_win']}/{data['decided']})"
            if data["decided"] else "موفقیت (بدون TIMEOUT): —"
        ),
        (
            f"موفقیت روی همه بسته‌شده‌ها: {data['wr_all_closed']:.1f}%  ({data['n_win']}/{data['closed']})"
            if data["closed"] else "موفقیت روی همه بسته‌شده‌ها: —"
        ),
    ])
    return "\n".join(lines)


def build_6h_outcome_summary(since_ts: Optional[float] = None, until_ts: Optional[float] = None) -> str:
    """جمع فشرده هر ۶ ساعت — بدون لیست کامل نمادها."""
    now = float(until_ts or time.time())
    default_since = now - float(CONFIG.get("OUTCOME_SUMMARY_INTERVAL_SEC", 21600))
    since = float(since_ts if since_ts is not None else (_OUTCOME_STATE.get("last_6h_ts") or default_since))
    if since <= 0:
        since = default_since
    if since >= now:
        since = default_since

    data = _resolve_signals_in_window(since, now)
    start_txt = time.strftime("%Y-%m-%d %H:%M", time.localtime(since))
    end_txt = time.strftime("%Y-%m-%d %H:%M", time.localtime(now))
    hours = max(1, int(round((now - since) / 3600)))

    lines = [
        f"📅 خلاصه {hours} ساعته — {start_txt} → {end_txt}",
        "",
        f"سیگنال ارسال‌شده: {data['n_sent']}",
        f"بسته شده: {data['closed']} | هنوز باز: {data['n_open']}",
        f"  ✅ TP1/TP2/TP3: {data['n_win']}  (TP1={data['n_tp1']} TP2={data['n_tp2']} TP3={data['n_tp3']})",
        f"  ❌ SL: {data['n_sl']}",
        f"  ⏱️ TIMEOUT: {data['n_timeout']}"
        + (
            f"  (رو به TP={data.get('n_to_toward_tp', 0)} | رو به SL={data.get('n_to_toward_sl', 0)} | خنثی={data.get('n_to_flat', 0)})"
            if data.get("n_timeout") else ""
        ),
        "",
        (
            f"موفقیت (بدون TIMEOUT): {data['wr_decided']:.1f}%  ({data['n_win']}/{data['decided']})"
            if data["decided"] else "موفقیت (بدون TIMEOUT): —"
        ),
        (
            f"موفقیت روی همه بسته‌شده‌ها: {data['wr_all_closed']:.1f}%  ({data['n_win']}/{data['closed']})"
            if data["closed"] else "موفقیت روی همه بسته‌شده‌ها: —"
        ),
        "",
        (
            f"جمع سود/زیان بسته‌شده‌ها: {data.get('sum_return_closed_pct', 0):+.2f}%"
            f"  |  میانگین: {data.get('avg_return_closed_pct', 0):+.2f}%"
            if data.get("closed") else "جمع سود/زیان بسته‌شده‌ها: —"
        ),
        (
            f"جمع فقط TP/SL (بدون TIMEOUT): {data.get('sum_return_decided_pct', 0):+.2f}%"
            if data.get("decided") else ""
        ),
    ]
    return "\n".join(lines)


def send_2h_outcome_report_safely() -> bool:
    if not CONFIG.get("OUTCOME_REPORT_ENABLED", True):
        return False
    try:
        since = float(_OUTCOME_STATE.get("last_2h_ts") or 0)
        text = build_2h_outcome_report(since_ts=since if since > 0 else None)
        chunks = _split_telegram_text(text, CONFIG.get("REPORT_MAX_TELEGRAM_CHARS", 3800))
        if not chunks:
            return False
        total = len(chunks)
        ok = True
        for i, chunk in enumerate(chunks, 1):
            prefix = f"📋 خلاصه ۲ساعته — بخش {i}/{total}\n\n" if total > 1 else ""
            if not send_telegram_message(prefix + chunk, message_type="2h-outcome report", channel="report"):
                ok = False
        if ok:
            _OUTCOME_STATE["last_2h_ts"] = time.time()
            _save_outcome_report_state()
        return ok
    except Exception as e:
        logger.error(f"❌ ارسال خلاصه ۲ساعته: {e}")
        return False


def send_6h_outcome_summary_safely() -> bool:
    """کارت تصویری ۶h + متن خلاصه → هر دو کانال signal و report."""
    if not CONFIG.get("OUTCOME_REPORT_ENABLED", True):
        return False
    try:
        now = time.time()
        since = float(_OUTCOME_STATE.get("last_6h_ts") or 0)
        default_since = now - float(CONFIG.get("OUTCOME_SUMMARY_INTERVAL_SEC", 21600))
        if since <= 0 or since >= now:
            since = default_since

        data = _resolve_signals_in_window(since, now)
        text = build_6h_outcome_summary(since_ts=since, until_ts=now)
        caption = (
            f"📅 6h Report | Sent {data.get('n_sent', 0)} | "
            f"TP {data.get('n_win', 0)} / SL {data.get('n_sl', 0)} / TO {data.get('n_timeout', 0)}"
        )

        photo_ok = False
        card_path = render_6h_report_card(data, since, now)
        if card_path and os.path.exists(card_path):
            # هر دو کانال: سیگنال + گزارش
            channels = []
            _, sig_chat = _telegram_config("signal")
            _, rep_chat = _telegram_config("report")
            if sig_chat:
                channels.append("signal")
            if rep_chat and rep_chat != sig_chat:
                channels.append("report")
            elif not channels and rep_chat:
                channels.append("report")
            if not channels:
                channels = ["signal", "report"]

            sent_any = False
            for ch in channels:
                if send_telegram_photo(card_path, caption=caption, channel=ch):
                    sent_any = True
                    logger.info(f"✅ کارت ۶h به کانال {ch} ارسال شد")
                else:
                    logger.warning(f"⚠️ کارت ۶h به کانال {ch} ارسال نشد")
            photo_ok = sent_any
            try:
                os.remove(card_path)
            except Exception:
                pass

        # متن کامل هم به کانال report (و اگر report=signal همان یکی)
        text_ok = True
        chunks = _split_telegram_text(text, CONFIG.get("REPORT_MAX_TELEGRAM_CHARS", 3800))
        for i, chunk in enumerate(chunks, 1):
            prefix = f"📅 خلاصه ۶ساعته — بخش {i}/{len(chunks)}\n\n" if len(chunks) > 1 else ""
            body = prefix + chunk
            if not send_telegram_message(body, message_type="6h-outcome summary", channel="report"):
                text_ok = False
            # اگر کانال سیگنال جداست، همان متن را هم بفرست (مگر کارت رفته باشد و نخواهی شلوغ شود)
            _, sig_chat = _telegram_config("signal")
            _, rep_chat = _telegram_config("report")
            if sig_chat and rep_chat and sig_chat != rep_chat and not photo_ok:
                send_telegram_message(body, message_type="6h-outcome summary", channel="signal")

        ok = photo_ok or text_ok
        if ok:
            _OUTCOME_STATE["last_6h_ts"] = now
            _save_outcome_report_state()
        return ok
    except Exception as e:
        logger.error(f"❌ ارسال خلاصه ۶ساعته: {e}")
        return False


def send_30m_report_safely(report_text: str) -> bool:
    chunks = _split_telegram_text(report_text, CONFIG.get("REPORT_MAX_TELEGRAM_CHARS", 3800))
    if not chunks:
        return False
    total = len(chunks)
    for i, chunk in enumerate(chunks, 1):
        prefix = f"📊 گزارش جامع ۳۰ دقیقه‌ای — بخش {i}/{total}\n\n" if total > 1 else ""
        if not send_telegram_message(prefix + chunk, message_type="30-minute report", channel="report"):
            return False
    return True

def run_startup_audit(strict: bool = False) -> dict:
    checks = []
    def add(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": str(detail)})
    interval_ok = _interval_to_minutes(CONFIG.get("KLINE_INTERVAL", "15m")) is not None
    add("kline_interval", interval_ok, CONFIG.get("KLINE_INTERVAL"))
    risk = float(CONFIG.get("RISK_PERCENT", 0)); maxrisk = float(CONFIG.get("MAX_RISK_PERCENT", 0))
    add("risk_range", 0 < risk <= maxrisk, f"{risk}% <= {maxrisk}%")
    add("threshold_order", float(CONFIG.get("PUMP_THRESHOLD", 0)) > 0 and float(CONFIG.get("DUMP_THRESHOLD", 0)) < 0, "pump>0,dump<0")
    tps = CONFIG.get("TP_ATR_MULTS", [])
    add("tp_order", len(tps) >= 2 and all(float(a) < float(b) for a,b in zip(tps,tps[1:])), tps)
    add("data_dir", os.path.isdir(DATA_DIR) and os.access(DATA_DIR, os.W_OK), DATA_DIR)
    add("sklearn", SKLEARN_AVAILABLE, "ML dependency")
    for name in ("fetch_klines_df","enhanced_analysis","pro_signal_quality_gate","backtest_symbol_realistic","create_ml_features","build_complete_report","send_30m_report_safely"):
        add("callable:" + name, callable(globals().get(name)), type(globals().get(name)).__name__)
    for key in ("RUNTIME_TELEMETRY","SIGNAL_DIAGNOSTICS","REPORT_HISTORY","ML_MODEL_FILE"):
        path = PATHS.get(key); parent = os.path.dirname(path) if path else ""
        add("path:" + key, bool(path) and os.path.isdir(parent) and os.access(parent, os.W_OK), path)
    failed = [x for x in checks if not x["ok"]]
    result = {"ok": not failed, "failed": len(failed), "total": len(checks), "checks": checks, "timestamp": time.time()}
    _atomic_write_json(os.path.join(DATA_DIR, "startup_audit.json"), result)
    if failed:
        logger.warning(f"🔎 Startup audit: {len(failed)}/{len(checks)} checks failed")
        for item in failed:
            logger.warning(f"   AUDIT FAIL | {item['name']} | {item['detail']}")
        if strict:
            raise RuntimeError(f"Startup audit failed: {len(failed)} checks")
    else:
        logger.info(f"🔎 Startup audit: {len(checks)}/{len(checks)} checks passed")
    return result


# ============================================================================
# بخش 21: حلقه اصلی - نسخه 19.1 STABLE
# ============================================================================

_LAST_ACCEPTED_SIGNAL_TS = time.time()
_SIGNALS_HOUR_STATE = {"hour": int(time.time() // 3600), "count": 0}
_SIGNALS_HOUR_LOCK = threading.Lock()  # FIX v24.1: race-safe hourly cap


def _hourly_signal_limit_reached() -> bool:
    global _SIGNALS_HOUR_STATE
    try:
        hour = int(time.time() // 3600)
        with _SIGNALS_HOUR_LOCK:
            if _SIGNALS_HOUR_STATE.get("hour") != hour:
                _SIGNALS_HOUR_STATE = {"hour": hour, "count": 0}
            count = int(_SIGNALS_HOUR_STATE.get("count", 0))
        base_cap = int(CONFIG.get("MAX_NEW_SIGNALS_PER_HOUR", 24))
        busy_cap = int(CONFIG.get("MAX_NEW_SIGNALS_PER_HOUR_BUSY", 30))
        try:
            pf = float(performance_memory.get_profit_factor(40) or 0)
            wr = float(performance_memory.get_winrate(40) or 0)
            cap = busy_cap if (pf >= 1.35 and wr >= 58.0) else base_cap
        except Exception:
            cap = base_cap
        return count >= cap
    except Exception:
        return False


def _register_accepted_signal() -> None:
    global _SIGNALS_HOUR_STATE
    try:
        hour = int(time.time() // 3600)
        with _SIGNALS_HOUR_LOCK:
            if _SIGNALS_HOUR_STATE.get("hour") != hour:
                _SIGNALS_HOUR_STATE = {"hour": hour, "count": 0}
            _SIGNALS_HOUR_STATE["count"] = int(_SIGNALS_HOUR_STATE.get("count", 0)) + 1
    except Exception:
        pass


def _collect_open_signal_items() -> list:
    """سیگنال‌های باز: paper + sent اخیر + صف (صف فقط برای ضدتکرار نماد)."""
    items = []
    now = time.time()
    # 1) paper positions
    try:
        for p in list(getattr(portfolio_risk, "paper_open", []) or []):
            if not isinstance(p, dict):
                continue
            items.append({
                "symbol": str(p.get("symbol") or "").upper(),
                "direction": str(p.get("direction") or "").upper(),
                "ts": float(p.get("ts") or 0),
                "src": "paper",
            })
    except Exception:
        pass
    # 2) recently sent (real delivery)
    try:
        max_age = float(CONFIG.get("MAX_HOLD_MINUTES", 90)) * 60.0
        with _SENT_SIGNALS_LOCK:
            for s in list(_SENT_SIGNALS)[-300:]:
                ts = float(s.get("ts") or 0)
                if now - ts > max_age:
                    continue
                items.append({
                    "symbol": str(s.get("symbol") or "").upper(),
                    "direction": str(s.get("direction") or "").upper(),
                    "ts": ts,
                    "src": "sent",
                })
    except Exception:
        pass
    # 3) learning queue — فقط برای block هم‌نماد، نه سقف جهت/تعداد
    try:
        q_age = float(CONFIG.get("QUEUE_RISK_MAX_AGE_SEC", 5400))
        for item in list(getattr(auto_learning, "learning_queue", []) or []):
            if not isinstance(item, dict):
                continue
            ts = float(item.get("timestamp") or 0)
            if ts and (now - ts) > q_age:
                continue
            items.append({
                "symbol": str(item.get("symbol") or (item.get("signal") or {}).get("symbol") or "").upper(),
                "direction": str(item.get("direction") or (item.get("signal") or {}).get("direction") or "").upper(),
                "ts": ts,
                "src": "queue",
            })
    except Exception:
        pass
    return items


def _portfolio_open_gate(direction: str, symbol: str = "") -> Tuple[bool, str]:
    """
    paper/signal_only: سقف تعداد/جهت فقط از paper_open.
    sent و queue فقط برای ضدتکرار همان نماد — تاریخچه تلگرام سقف کل را پر نمی‌کند.
    """
    try:
        if hasattr(portfolio_risk, "daily_loss_breach") and portfolio_risk.daily_loss_breach():
            return False, "max_daily_loss"
        if hasattr(portfolio_risk, "portfolio_risk_breach") and portfolio_risk.portfolio_risk_breach():
            return False, "max_portfolio_risk"

        now = time.time()
        mode = str(CONFIG.get("EXECUTION_MODE", "paper")).lower()
        all_items = _collect_open_signal_items()

        if mode in ("paper", "signal_only"):
            exposure = [x for x in all_items if x.get("src") == "paper"]
        else:
            exposure = [x for x in all_items if x.get("src") in ("paper", "sent")]

        exp_seen = set()
        exp_unique = []
        for x in exposure:
            s = str(x.get("symbol") or "").upper()
            if not s or s in exp_seen:
                continue
            exp_seen.add(s)
            exp_unique.append(x)

        sym = str(symbol or "").upper()
        d = str(direction or "").upper()

        if sym and int(CONFIG.get("MAX_OPEN_PER_SYMBOL", 1)) > 0:
            min_gap = float(CONFIG.get("MIN_SYMBOL_RESHIFT_SEC", 2700))
            for x in all_items:
                if str(x.get("symbol") or "").upper() != sym:
                    continue
                if (now - float(x.get("ts") or 0)) < min_gap:
                    return False, "max_open_per_symbol"

        if len(exp_unique) >= int(CONFIG.get("MAX_OPEN_SIGNALS_TOTAL", 16)):
            return False, "max_open_signals_total"

        if d:
            same_dir = sum(
                1 for x in exp_unique
                if d in str(x.get("direction") or "").upper()
            )
            if same_dir >= int(CONFIG.get("MAX_OPEN_SAME_DIRECTION", 10)):
                return False, "max_open_same_direction"

        return True, "ok"
    except Exception:
        return True, "ok"


def get_adaptive_trigger_thresholds() -> tuple:
    try:
        idle_min = (time.time() - _LAST_ACCEPTED_SIGNAL_TS) / 60.0
        base = float(CONFIG.get("PUMP_THRESHOLD", 1.2))
        if idle_min >= CONFIG.get("SIGNAL_STARVATION_MINUTES", 12):
            steps = int((idle_min - CONFIG.get("SIGNAL_STARVATION_MINUTES", 12)) // 15) + 1
            base -= steps * CONFIG.get("SIGNAL_STARVATION_RECOVERY_STEP", 0.10)
            base = max(CONFIG.get("SIGNAL_STARVATION_THRESHOLD_MIN", 0.7), base)
        base = min(CONFIG.get("SIGNAL_STARVATION_THRESHOLD_MAX", 1.8), base)
        return base, -base
    except Exception:
        return float(CONFIG.get("PUMP_THRESHOLD", 1.2)), float(CONFIG.get("DUMP_THRESHOLD", -1.2))


def main_loop_v18():
    """
    حلقه اصلی - کامل با تمام سیستم‌های خودتکامل
    """
    logger.info("=" * 60)
    logger.info("🧬 **نسخه 24.3 QUANT MAX - EV + Drift + Feature Store + Purged ML**")
    logger.info("🤖 کاملاً خودکار - همه پارامترها خودشان بهینه می‌شوند")
    logger.info("📊 گزارش کامل هر ۳۰ دقیقه با تمام تغییرات")
    logger.info("=" * 60)
    logger.info(f"⏰ شروع: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"📊 اینتروال: {CONFIG['KLINE_INTERVAL']}")
    logger.info(f"🎯 هدف: کیفیت سیگنال + Expected Edge + کنترل ریسک + OOS validation")
    logger.info("=" * 60)
    if CONFIG.get("AUDIT_ON_START", True):
        run_startup_audit(bool(CONFIG.get("AUDIT_STRICT", False)))
    logger.info(f"🎛️ Mode: {RUN_MODE.upper()} | Leverage: {LEVERAGE}x")
    
    last_learning_update = 0
    last_report_time = 0.0
    last_outcome_report_time = 0.0
    last_outcome_6h_time = 0.0
    try:
        _load_sent_signals_log()
        _load_outcome_report_state()
        if float(_OUTCOME_STATE.get("last_2h_ts") or 0) > 0:
            last_outcome_report_time = float(_OUTCOME_STATE["last_2h_ts"])
        if float(_OUTCOME_STATE.get("last_6h_ts") or 0) > 0:
            last_outcome_6h_time = float(_OUTCOME_STATE["last_6h_ts"])
    except Exception as load_out_err:
        logger.warning(f"outcome report state load: {load_out_err}")
    auto_learning.start()
    self_healing_autopilot.run(force=True)
    self_diagnose_and_repair()
    check_count = 0
    signal_count = 0
    
    while True:
        cycle_started = time.time()
        _runtime_update(last_cycle_started=cycle_started)
        try:
            check_count += 1
            _runtime_inc("cycles")
            self_diagnose_and_repair()
            
            # ============================
            # دریافت داده‌های بازار
            # ============================
            fetch_started = time.time()
            coins = fetch_binance_all_ticker()
            fetch_ms = (time.time() - fetch_started) * 1000.0
            _runtime_update(last_fetch_latency_ms=round(fetch_ms, 1))
            _runtime_inc("fetch_latency_samples")
            _runtime_update(fetch_latency_ms_sum=_safe_float(_RUNTIME_STATE.get("fetch_latency_ms_sum"), 0.0) + fetch_ms)
            if not coins:
                _runtime_inc("empty_ticker_cycles")
                logger.warning("هیچ تیکری دریافت نشد!")
                time.sleep(30)
                continue
            
            history = load_history()
            update_history_with_coins(history, coins)
            price_map = {c.get("symbol"): c.get("current_price") for c in coins if c.get("symbol")}
            _runtime_update(last_ticker_count=len(coins), last_price_map_count=len(price_map))
            _runtime_inc("symbols_seen", len(coins))
            _runtime_inc("usdt_symbols_seen", sum(1 for c in coins if str(c.get("symbol", "")).upper().endswith("USDT")))
            
            pump_threshold, dump_threshold = get_adaptive_trigger_thresholds()
            signals = []
            pump_count = 0
            dump_count = 0
            
            # ============================
            # اسکن سیگنال‌ها
            # ============================
            for coin in coins:
                symbol = coin.get("symbol", "").upper()
                if not symbol.endswith("USDT"):
                    continue
                
                change_15m = get_change_from_history(history, symbol, 900)
                if change_15m is None:
                    continue
                
                direction_hint = None
                if change_15m >= pump_threshold:
                    direction_hint = "bull"
                    pump_count += 1
                    _runtime_inc("pump_triggers")
                    _diag_inc("TRIGGER", "pump")
                elif change_15m <= dump_threshold:
                    direction_hint = "bear"
                    dump_count += 1
                    _runtime_inc("dump_triggers")
                    _diag_inc("TRIGGER", "dump")
                else:
                    _diag_inc("REJECT", "trigger_not_reached")
                    continue
                
                allowed, block_reason = self_healing_autopilot.emergency_gate(
                    symbol, "LONG" if direction_hint == "bull" else "SHORT"
                )
                if not allowed:
                    _diag_inc("REJECT", f"emergency_gate:{block_reason}")
                    continue

                dir_text = "LONG" if direction_hint == "bull" else "SHORT"
                port_ok, port_reason = _portfolio_open_gate(dir_text, symbol)
                if not port_ok:
                    _diag_inc("REJECT", f"portfolio_gate:{port_reason}")
                    continue
                    
                if len(signals) >= CONFIG.get("MAX_NEW_SIGNALS_PER_CYCLE", 4):
                    continue
                if _hourly_signal_limit_reached():
                    _diag_inc("REJECT", "hourly_signal_limit")
                    continue
                    
                summary = enhanced_analysis(symbol, direction_hint=direction_hint)
                if summary:
                    summary["pre_signal_change_15m"] = change_15m
                    ok_pro, pro_reason, pro_diag = pro_signal_quality_gate(summary)
                    _diag_inc("PRO_GATE_EVALUATED", "PRO_GATE", str(summary.get("market_regime", "UNKNOWN")))
                    summary["pro_quality_gate"] = {"passed": ok_pro, "reason": pro_reason, "diagnostics": pro_diag}
                    if not ok_pro:
                        _diag_inc("REJECT", f"PRO_GATE:{pro_reason}")
                        continue
                    # ACCEPTED is only a gate decision. Track every post-gate stage separately.
                    candidate_id = f"{symbol}-{int(time.time()*1000)}-{signal_count+1}"
                    summary["candidate_id"] = candidate_id
                    _runtime_inc("accepted_candidates")
                    _runtime_event("ACCEPTED", candidate_id, symbol, "gate_pass")
                    _runtime_inc("signal_build_started")
                    try:
                        # A signal is considered buildable only when the core contract is complete.
                        required = ("symbol", "direction", "entry", "sl", "tps", "confidence")
                        missing = [k for k in required if k not in summary or summary.get(k) in (None, "")]
                        if not summary.get("tps"):
                            missing.append("tps")
                        if missing:
                            raise ValueError("missing:" + ",".join(sorted(set(missing))))
                        _runtime_inc("signal_build_ok")
                        _runtime_event("SIGNAL_BUILD_OK", candidate_id, symbol)
                    except Exception as build_err:
                        _runtime_inc("signal_build_failed")
                        _runtime_update(last_post_gate_failure=f"signal_build:{build_err}")
                        _runtime_event("SIGNAL_BUILD_FAILED", candidate_id, symbol, str(build_err))
                        logger.error(f"Post-gate signal build failed for {symbol}: {build_err}")
                        continue

                    _runtime_inc("risk_checks")
                    risk_ok, risk_reason = self_healing_autopilot.emergency_gate(symbol, summary.get("direction", ""))
                    if not risk_ok:
                        _runtime_inc("risk_rejected")
                        _runtime_update(last_post_gate_failure=f"risk:{risk_reason}")
                        _runtime_event("RISK_REJECTED", candidate_id, symbol, risk_reason)
                        _diag_inc("REJECT", f"POST_GATE_RISK:{risk_reason}")
                        continue
                    _runtime_inc("risk_approved")
                    _runtime_inc("signal_created")
                    _runtime_event("SIGNAL_CREATED", candidate_id, symbol)
                    _diag_inc("ACCEPTED", f"{summary.get('market_regime', 'UNKNOWN')}|post_gate", str(summary.get("market_regime", "UNKNOWN")))
                    try:
                        portfolio_risk.register_signal(summary)
                    except Exception as _pe:
                        logger.debug(f"portfolio register: {_pe}")
                    signals.append(summary)
                    _runtime_inc("normal_signals")
                    globals()["_LAST_ACCEPTED_SIGNAL_TS"] = time.time()
                    _register_accepted_signal()
                    save_signal_history(summary)
                    auto_learning.add_signal_for_learning(summary)
                    signal_count += 1
                    
                    # نمایش در کنسول
                    print(f"\n{'='*50}")
                    print(f"🎯 سیگنال #{signal_count} - {summary['symbol']}")
                    print(f"   جهت: {summary['direction']}")
                    print(f"   قیمت: {summary['price']}")
                    print(f"   ورود: {summary['entry']}")
                    print(f"   SL: {summary['sl']}")
                    print(f"   TP1: {summary['tps'][0] if summary['tps'] else 'N/A'}")
                    print(f"   اطمینان: {summary.get('confidence', 0):.1f}/10")
                    print(f"   ML: {'✅' if summary.get('ml_used', False) else '❌'}")
                    print(f"   رژیم: {summary.get('market_regime', 'UNKNOWN')}")
                    print(f"{'='*50}\n")
                    
                    # ارسال متمرکز به Telegram
                    _runtime_inc("telegram_attempts")
                    _runtime_event("TELEGRAM_ATTEMPT", candidate_id, symbol)
                    delivery_status = deliver_signal_to_telegram(summary, source="normal")
                    if delivery_status == "SENT":
                        _runtime_inc("telegram_signal_ok")
                        _runtime_inc("telegram_sent")
                        _runtime_event("TELEGRAM_SENT", candidate_id, symbol)
                    elif delivery_status == "COOLDOWN":
                        _runtime_inc("telegram_cooldown")
                        _runtime_event("TELEGRAM_COOLDOWN", candidate_id, symbol)
                    else:
                        _runtime_inc("telegram_signal_fail")
                        _runtime_inc("telegram_failed")
                        _runtime_update(last_post_gate_failure=f"telegram:{delivery_status}")
                        _runtime_event("TELEGRAM_FAILED", candidate_id, symbol, delivery_status)

            # ============================
            # Smart Fallback
            # ============================
            idle_min = max(0.0, (time.time() - _LAST_ACCEPTED_SIGNAL_TS) / 60.0)
            fallback_after = float(CONFIG.get("FALLBACK_SCAN_AFTER_MINUTES", 12))
            if len(signals) < 2 and idle_min >= fallback_after:
                candidates = []
                for c in coins:
                    sym = str(c.get("symbol", "")).upper()
                    if not sym.endswith("USDT"):
                        continue
                    ch = get_change_from_history(history, sym, 900)
                    if ch is None:
                        continue
                    try:
                        candidates.append((abs(float(ch)), float(ch), sym))
                    except Exception:
                        continue
                candidates.sort(reverse=True)
                candidates = candidates[:int(CONFIG.get("FALLBACK_CANDIDATES", 6))]
                
                for _, ch, symbol in candidates:
                    if len(signals) >= int(CONFIG.get("MAX_NEW_SIGNALS_PER_CYCLE", 4)):
                        break
                    if _hourly_signal_limit_reached():
                        break
                    direction = "bull" if ch >= 0 else "bear"
                    direction_text = "LONG" if direction == "bull" else "SHORT"
                    allowed, reason = self_healing_autopilot.emergency_gate(symbol, direction_text)
                    if not allowed:
                        continue
                    try:
                        _runtime_inc("fallback_attempts")
                        summary = enhanced_analysis(symbol, direction_hint=direction, recovery_mode=True)
                    except Exception as e:
                        continue
                    if not summary:
                        continue
                    summary["pre_signal_change_15m"] = ch
                    summary["recovery_mode"] = True
                    ok_pro, pro_reason, pro_diag = pro_signal_quality_gate(summary)
                    _diag_inc("PRO_GATE_EVALUATED", "PRO_GATE", str(summary.get("market_regime", "UNKNOWN")))
                    summary["pro_quality_gate"] = {"passed": ok_pro, "reason": pro_reason, "diagnostics": pro_diag}
                    if not ok_pro:
                        _diag_inc("REJECT", f"PRO_GATE:{pro_reason}")
                        continue
                    candidate_id = f"{symbol}-{int(time.time()*1000)}-{signal_count+1}-fb"
                    summary["candidate_id"] = candidate_id
                    _runtime_inc("accepted_candidates")
                    _runtime_event("ACCEPTED", candidate_id, symbol, "fallback_gate_pass")
                    _runtime_inc("signal_build_started")
                    try:
                        required = ("symbol", "direction", "entry", "sl", "tps", "confidence")
                        missing = [k for k in required if k not in summary or summary.get(k) in (None, "")]
                        if not summary.get("tps"):
                            missing.append("tps")
                        if missing:
                            raise ValueError("missing:" + ",".join(sorted(set(missing))))
                        _runtime_inc("signal_build_ok")
                        _runtime_event("SIGNAL_BUILD_OK", candidate_id, symbol)
                    except Exception as build_err:
                        _runtime_inc("signal_build_failed")
                        _runtime_update(last_post_gate_failure=f"signal_build:{build_err}")
                        _runtime_event("SIGNAL_BUILD_FAILED", candidate_id, symbol, str(build_err))
                        continue
                    _runtime_inc("risk_checks")
                    risk_ok, risk_reason = self_healing_autopilot.emergency_gate(symbol, summary.get("direction", ""))
                    if not risk_ok:
                        _runtime_inc("risk_rejected")
                        _runtime_update(last_post_gate_failure=f"risk:{risk_reason}")
                        _runtime_event("RISK_REJECTED", candidate_id, symbol, risk_reason)
                        _diag_inc("REJECT", f"POST_GATE_RISK:{risk_reason}")
                        continue
                    _runtime_inc("risk_approved")
                    _runtime_inc("signal_created")
                    _runtime_event("SIGNAL_CREATED", candidate_id, symbol)
                    _diag_inc("ACCEPTED", f"{summary.get('market_regime', 'UNKNOWN')}|post_gate", str(summary.get("market_regime", "UNKNOWN")))
                    try:
                        portfolio_risk.register_signal(summary)
                    except Exception as _pe:
                        logger.debug(f"portfolio register fb: {_pe}")
                    signals.append(summary)
                    _runtime_inc("fallback_signals")
                    globals()["_LAST_ACCEPTED_SIGNAL_TS"] = time.time()
                    _register_accepted_signal()
                    save_signal_history(summary)
                    auto_learning.add_signal_for_learning(summary)
                    signal_count += 1
                    print(f"\n🎯 FALLBACK SIGNAL #{signal_count}: {summary.get('symbol')} {summary.get('direction')} | conf={float(summary.get('confidence', 0)):.1f}")
                    _runtime_inc("telegram_attempts")
                    _runtime_event("TELEGRAM_ATTEMPT", candidate_id, symbol)
                    delivery_status = deliver_signal_to_telegram(summary, source="fallback")
                    if delivery_status == "SENT":
                        _runtime_inc("telegram_signal_ok")
                        _runtime_inc("telegram_sent")
                        _runtime_event("TELEGRAM_SENT", candidate_id, symbol)
                    elif delivery_status == "COOLDOWN":
                        _runtime_inc("telegram_cooldown")
                        _runtime_event("TELEGRAM_COOLDOWN", candidate_id, symbol)
                    else:
                        _runtime_inc("telegram_signal_fail")
                        _runtime_inc("telegram_failed")
                        _runtime_update(last_post_gate_failure=f"telegram:{delivery_status}")
                        _runtime_event("TELEGRAM_FAILED", candidate_id, symbol, delivery_status)

            self_diagnose_and_repair()
            
            if signals:
                save_signal_json_overwrite(signals)
            
            # ============================
            # Self-Healing
            # ============================
            try:
                self_healing_autopilot.run()
            except Exception as heal_err:
                logger.error(f"AutoPilot error: {heal_err}")

            # ============================
            # ML Retrain
            # ============================
            try:
                if ml_model.should_retrain():
                    _runtime_inc("ml_retrain_attempts")
                    result = ml_model.train(force=True)
                    _runtime_update(last_ml_train=time.time(), last_ml_result=result or {"status": "FAILED"})
                    if result:
                        _runtime_inc("ml_retrain_success")
                        logger.info(f"🧠 ML بازآموزی شد: AUC={result.get('wf_auc', 0):.3f}")
                    else:
                        _runtime_inc("ml_retrain_fail")
            except Exception as ml_err:
                logger.error(f"ML retrain failed: {ml_err}")

            # ============================
            # به‌روزرسانی سیستم یادگیری (هر ۸ ساعت)
            # ============================
            now_hour = int(time.time() // 3600)
            if now_hour - last_learning_update >= CONFIG.get("ADAPTIVE_UPDATE_INTERVAL", 8):
                update_learning_system()
                _runtime_inc("learning_updates")
                _runtime_update(last_learning_update=time.time())
                last_learning_update = now_hour
                
                summary = performance_memory.get_summary()
                if summary["total_trades"] > 0:
                    logger.info(f"📈 گزارش: {summary['total_trades']} معامله, وین‌ریت: {summary['long_term_winrate']:.1f}%")
            
            # ============================
            # گزارش ۳۰ دقیقه‌ای
            # ============================
            if time.time() - last_report_time >= int(CONFIG.get("REPORT_INTERVAL_SEC", 1800)):  # هر ۳۰ دقیقه
                logger.info("📨 ارسال گزارش ۳۰ دقیقه‌ای...")
                report_text = build_complete_report(price_map, reset_window=False)
                logger.info("\n" + report_text + "\n")
                report_sent = send_30m_report_safely(report_text)
                if report_sent:
                    _runtime_inc("telegram_report_ok")
                    _diag_reset_window_after_report()
                    _runtime_reset_window()
                    last_report_time = time.time()
                else:
                    _runtime_inc("telegram_report_fail")
                    logger.warning("⚠️ گزارش ارسال نشد - پنجره Diagnostics حفظ شد")
                    last_report_time = time.time() - int(CONFIG.get("REPORT_INTERVAL_SEC", 1800)) + 60

            # ============================
            # خلاصه outcome هر ۲ ساعت (جزئی) → کانال گزارش
            # ============================
            outcome_iv = int(CONFIG.get("OUTCOME_REPORT_INTERVAL_SEC", 7200))
            if CONFIG.get("OUTCOME_REPORT_ENABLED", True) and (time.time() - last_outcome_report_time >= outcome_iv):
                logger.info("📨 ارسال خلاصه outcome دو ساعته...")
                if send_2h_outcome_report_safely():
                    last_outcome_report_time = time.time()
                else:
                    last_outcome_report_time = time.time() - outcome_iv + 120

            # ============================
            # خلاصه جمع هر ۶ ساعت → کانال گزارش
            # ============================
            summary_iv = int(CONFIG.get("OUTCOME_SUMMARY_INTERVAL_SEC", 21600))
            if CONFIG.get("OUTCOME_REPORT_ENABLED", True) and (time.time() - last_outcome_6h_time >= summary_iv):
                logger.info("📨 ارسال خلاصه ۶ ساعته...")
                if send_6h_outcome_summary_safely():
                    last_outcome_6h_time = time.time()
                else:
                    last_outcome_6h_time = time.time() - summary_iv + 300
            
            if check_count % 100 == 0:
                logger.print_summary()
            
        except KeyboardInterrupt:
            logger.info("\n⏹️ دریافت سیگنال توقف... در حال خروج...")
            auto_learning.stop()
            logger.info("✅ برنامه متوقف شد")
            break
            
        except Exception as e:
            _runtime_inc("cycle_errors")
            logger.error(f"خطا در حلقه اصلی: {e}")
            time.sleep(10)
        finally:
            _runtime_update(last_cycle_finished=time.time(), last_cycle_duration_sec=round(time.time() - cycle_started, 3))
        
        time.sleep(CONFIG["CHECK_INTERVAL"])


# ============================================================================
# بخش 22: نقطه شروع - نسخه 19.1 STABLE
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🧬 **نسخه 24.3 QUANT MAX - EV + Drift + Feature Store + Purged ML**")
    print("🤖 کاملاً خودکار - بدون نیاز به هیچ دخالت انسانی")
    print("📊 همه پارامترها خودشان بهینه می‌شوند")
    print("📈 گزارش کامل هر ۳۰ دقیقه با تمام تغییرات و دلایل")
    print("🎯 هدف: کیفیت سیگنال + Expected Edge + کنترل ریسک + OOS validation")
    print("=" * 60)
    print()
    
    # تست اتصال
    test_result = test_binance_connection()
    test_telegram_connection()

    # بک‌آپ یک‌باره به تلگرام (فقط اگر RUN_DATA_BACKUP=1)
    try:
        run_data_backup_to_telegram_once()
    except Exception as _bak_err:
        print(f"⚠️ بک‌آپ داده: {_bak_err}")
    
    if not test_result["success"]:
        print("\n⚠️ اخطار: اتصال به بایننس برقرار نیست!")
        print("   ممکن است به VPN نیاز داشته باشید.")
        # روی سرور (Railway و غیره) input نداریم — خودکار ادامه
        interactive = sys.stdin.isatty() and not (
            os.environ.get("RAILWAY_ENVIRONMENT")
            or os.environ.get("RAILWAY_PROJECT_ID")
            or os.environ.get("SKIP_INTERACTIVE", "").lower() in ("1", "true", "yes")
            or not sys.stdin.isatty()
        )
        if interactive:
            try:
                response = input("آیا ادامه می‌دهید؟ (y/n): ").strip().lower()
            except (EOFError, OSError):
                response = "y"
            if response != "y":
                print("خروج از برنامه...")
                sys.exit(1)
        else:
            print("⚙️ حالت غیرتعاملی: ادامه خودکار بدون تأیید دستی...")
    
    print("\n" + "=" * 60)
    print("شروع حلقه اصلی...")
    print("برای خروج Ctrl+C را بزنید")
    print("=" * 60 + "\n")
    
    # === QUANT UPGRADE (after all classes/functions are defined) ===
    try:
        from quant_upgrade_bridge import apply_quant_upgrade
        _q_ok = apply_quant_upgrade(globals())
        if _q_ok:
            print("✅ Quant upgrade fully applied (post-init)")
        else:
            print("⚠️ Quant upgrade returned False")
    except Exception as _qe:
        print(f"⚠️ Quant upgrade skipped: {_qe}")
    # ==============================================================

    try:
        main_loop_v18()
    except KeyboardInterrupt:
        print("\n⏹️ برنامه با موفقیت متوقف شد")
    except Exception as e:
        logger.error(f"خطای غیرمنتظره: {e}")
        traceback.print_exc()
