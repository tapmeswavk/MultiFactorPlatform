"""组合输出 — LQTP 格式 CSV 生成"""
import pandas as pd

SECTOR_MAP = {
    '沪主板': lambda s: s.startswith('6'),
    '深主板': lambda s: s.startswith('0'),
    '创业板': lambda s: s.startswith('3'),
    '科创板': lambda s: s.startswith('68'),
}

class PortfolioOutput:
    @staticmethod
    def filter_sector(selected: list, sectors: list) -> list:
        """按板块过滤。sectors为空=全选"""
        if not sectors or len(sectors) >= 4:
            return selected
        keep = []
        for s in selected:
            code = s[0] if isinstance(s, tuple) else s
            symbol = code if isinstance(code, str) else ''
            for sec in sectors:
                if sec in SECTOR_MAP and SECTOR_MAP[sec](symbol):
                    keep.append(s)
                    break
        return keep

    @staticmethod
    def generate_daily(connector, factors: dict, weights: dict, directions: dict,
                       builder, date: int, target_n: int = 50, warmup: int = 120,
                       neutralize: str = "", normalize_method: str = "rank",
                       sectors: list = None) -> pd.DataFrame:
        """单日组合输出"""
        factor_values = {}
        for fname, formula in factors.items():
            vals = connector.get_factor_values(formula, date, warmup=warmup, neutralize=neutralize)
            if vals:
                direction = directions.get(fname, 1)
                factor_values[fname] = builder.normalize(vals, direction=direction, method=normalize_method)

        selected = builder.combine(factor_values, weights, target_n, method=normalize_method)
        if not selected: return pd.DataFrame()

        # 板块过滤
        if sectors and len(sectors) < 4:
            selected = PortfolioOutput.filter_sector(selected, sectors)
            if not selected: return pd.DataFrame()

        rows = []
        val_per_stock = 1.0 / len(selected)
        for symbol, _ in selected:
            rows.append({"trade_date": date, "quote_time": 0, "symbol": symbol, "value": val_per_stock})
        return pd.DataFrame(rows)

    @staticmethod
    def generate_batch(connector, factors: dict, weights: dict, directions: dict,
                       builder, begin_date: int, end_date: int, target_n: int = 50,
                       rebalance_days: int = 1, warmup: int = 120,
                       neutralize: str = "", normalize_method: str = "rank",
                       sectors: list = None, progress_callback=None) -> pd.DataFrame:
        """
        多日批量组合输出。
        rebalance_days: 调仓频率（交易日）。1=每日, 3=每3个交易日调一次仓。
                       非调仓日沿用上一个调仓日的持仓。
        """
        from datetime import datetime, timedelta
        all_rows = []
        cur = datetime.strptime(str(begin_date), "%Y%m%d")
        end = datetime.strptime(str(end_date), "%Y%m%d")
        total_days = 0
        trading_day_count = 0
        last_portfolio = None  # 上一个调仓日的 DataFrame

        while cur <= end:
            if cur.weekday() < 5:  # skip weekends
                trade_date = int(cur.strftime("%Y%m%d"))
                trading_day_count += 1

                if trading_day_count == 1 or trading_day_count % rebalance_days == 1:
                    # 调仓日：重新计算因子值并生成组合
                    try:
                        df = PortfolioOutput.generate_daily(
                            connector, factors, weights, directions, builder,
                            trade_date, target_n, warmup, neutralize, normalize_method, sectors)
                        if not df.empty:
                            last_portfolio = df
                            all_rows.append(df)
                            total_days += 1
                    except Exception:
                        pass
                elif last_portfolio is not None:
                    # 非调仓日：沿用上期持仓
                    carry = last_portfolio.copy()
                    carry["trade_date"] = trade_date
                    all_rows.append(carry)

                if progress_callback:
                    progress_callback(total_days)
            cur += timedelta(days=1)

        if all_rows:
            result = pd.concat(all_rows, ignore_index=True)
            return result.sort_values(["trade_date", "symbol"]).reset_index(drop=True)
        return pd.DataFrame()
