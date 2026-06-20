"""因子 IC 扫描器 — 逐个因子计算 IC 并排名"""
import json, os, time
import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")

class FactorScanner:
    def __init__(self, connector):
        self._conn = connector

    def scan_all(self, factors: list, begin: int = 20240102, end: int = 20260615,
                 progress_callback=None) -> pd.DataFrame:
        """扫描所有因子，返回排序后的 DataFrame"""
        results = []
        total = len(factors)
        for i, f in enumerate(factors):
            formula = f.get("formula", "")
            name = f.get("name", formula[:50])
            if not formula:
                continue
            try:
                ic_data = self._conn.scan_ic(formula, begin, end)
                if ic_data:
                    results.append({
                        "name": name, "formula": formula,
                        "definition_id": f.get("definition_id", ""),
                        "ic": ic_data["ic"], "icir": ic_data["icir"],
                        "pos_ratio": ic_data["pos_ratio"], "eff": ic_data["eff"],
                        "coverage": ic_data["coverage"],
                        "abs_ic": abs(ic_data["ic"]),
                    })
            except Exception as e:
                pass
            if progress_callback:
                progress_callback(i + 1, total, name)
            time.sleep(0.15)

        df = pd.DataFrame(results)
        if not df.empty:
            df = df.sort_values("abs_ic", ascending=False).reset_index(drop=True)
        return df

    def save_cache(self, df: pd.DataFrame, filename: str = "ic_scan.csv"):
        path = os.path.join(CACHE_DIR, filename)
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return path

    def load_cache(self, filename: str = "ic_scan.csv") -> pd.DataFrame:
        path = os.path.join(CACHE_DIR, filename)
        if os.path.exists(path):
            return pd.read_csv(path)
        return pd.DataFrame()
