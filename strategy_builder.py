"""策略构建器 — 截面标准化 + 加权合成"""
import numpy as np
import pandas as pd

class StrategyBuilder:
    @staticmethod
    def normalize(values: dict, direction: int = 1, method: str = "rank") -> dict:
        """
        截面标准化: rank → 0~1 均匀分布。
        direction=1: 原始方向（IC为正的因子）；direction=-1: 反转（IC为负的因子）
        """
        if not values:
            return {}
        symbols = list(values.keys())
        raw = np.array([values[s] for s in symbols])
        if method == "rank":
            from scipy.stats import rankdata
            ranked = rankdata(raw, method="average") / len(raw)
        elif method == "zscore":
            ranked = (raw - np.nanmean(raw)) / (np.nanstd(raw) + 1e-8)
            ranked = 1 / (1 + np.exp(-ranked))
        else:
            ranked = raw
        # Flip for negative IC factors: higher raw value = lower score
        if direction == -1:
            ranked = 1.0 - ranked
        return {s: float(v) for s, v in zip(symbols, ranked)}

    @staticmethod
    def combine(factor_values: dict, weights: dict, target_n: int = 50, method: str = "rank") -> list:
        """加权合成 → Top-N 股票列表。method: rank=最终rank排序, zscore=保留原始合成值分布"""
        if not factor_values or not weights:
            return []
        symbols = None
        for fv in factor_values.values():
            if symbols is None:
                symbols = set(fv.keys())
            else:
                symbols &= set(fv.keys())
        if not symbols:
            return []
        symbols = list(symbols)
        total_w = sum(weights.values())
        composite = np.zeros(len(symbols))
        for fname, w in weights.items():
            vals = factor_values.get(fname, {})
            arr = np.array([vals.get(s, 0) for s in symbols])
            composite += (w / total_w) * arr
        # rank 模式：最终再做一次 rank；zscore 模式：直接用原始合成值（保留分布差异）
        if method == "zscore":
            # 标准化合成值到 0-1
            cmin, cmax = composite.min(), composite.max()
            if cmax > cmin:
                final = (composite - cmin) / (cmax - cmin)
            else:
                final = np.ones(len(composite)) * 0.5
        else:
            from scipy.stats import rankdata
            final = rankdata(composite, method="average") / len(composite)
        idx = np.argsort(final)[-target_n:][::-1]
        return [(symbols[i], float(final[i])) for i in idx]
