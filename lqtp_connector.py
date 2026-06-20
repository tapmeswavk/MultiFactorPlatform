"""LQTP gRPC 连接器 — token管理 + 因子调用"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "data", "proto"))
import grpc, Factor_pb2, Factor_pb2_grpc, Auth_pb2, Auth_pb2_grpc
import pandas as pd

class LQTPConnector:
    def __init__(self, server="118.89.191.220:50051"):
        self._server = server
        self._channel = None
        self._token = None
        self._factor_stub = None

    def login(self, username: str, password: str) -> str:
        self._channel = grpc.insecure_channel(self._server)
        auth = Auth_pb2_grpc.AuthServiceStub(self._channel)
        resp = auth.Login(Auth_pb2.LoginRequest(username=username, password=password), timeout=10)
        self._token = resp.access_token
        self._factor_stub = Factor_pb2_grpc.FactorServiceStub(self._channel)
        return self._token

    @property
    def token(self):
        return self._token

    @property
    def meta(self):
        return (("authorization", f"Bearer {self._token}"),) if self._token else None

    def list_factors(self) -> list:
        """返回所有因子 [{name, formula, definition_id, status, tags}]"""
        resp = self._factor_stub.ListFactors(Factor_pb2.ListFactorsRequest(), metadata=self.meta, timeout=15)
        factors = []
        for f in resp.factors:
            factors.append({
                "name": f.factor_name, "formula": f.formula,
                "definition_id": f.definition_id, "status": f.status,
                "tags": dict(f.tags) if f.tags else {},
            })
        return factors

    def run_factor(self, formula: str, begin: int, end: int, analyze: bool = True, warmup: int = 120) -> dict:
        """运行因子，返回 {values: [...], ic, icir, pos_ratio, coverage}"""
        resp = self._factor_stub.RunFactor(Factor_pb2.RunFactorRequest(
            formula=formula, begin_date=begin, end_date=end,
            warmup=warmup, analyze=analyze, value_return_mode=2),
            metadata=self.meta, timeout=120)
        result = {"values": [], "total_rows": resp.total_value_rows}
        if resp.analysis:
            result["ic"] = resp.analysis.mean_ic
            result["icir"] = resp.analysis.icir
            result["pos_ratio"] = resp.analysis.ic_positive_ratio
            result["coverage"] = resp.analysis.coverage
        for v in resp.values:
            day_vals = {}
            for sv in v.values:
                day_vals[sv.symbol] = sv.value
            result["values"].append({"trade_date": v.trade_date, "stocks": day_vals})
        return result

    def get_factor_values(self, formula: str, trade_date: int, warmup: int = 120) -> dict:
        """单日因子值 → {symbol: value}"""
        r = self.run_factor(formula, trade_date, trade_date, analyze=False, warmup=warmup)
        if r["values"]:
            return r["values"][0]["stocks"]
        return {}

    def scan_ic(self, formula: str, begin: int = 20240102, end: int = 20260615, warmup: int = 120) -> dict:
        """快速IC扫描"""
        resp = self._factor_stub.RunFactor(Factor_pb2.RunFactorRequest(
            formula=formula, begin_date=begin, end_date=end,
            warmup=warmup, analyze=True, value_return_mode=0),
            metadata=self.meta, timeout=120)
        a = resp.analysis
        if a and a.mean_ic is not None:
            ic = a.mean_ic
            return {"ic": ic, "icir": a.icir, "pos_ratio": a.ic_positive_ratio,
                    "coverage": a.coverage, "eff": (a.ic_positive_ratio if ic > 0 else 1-a.ic_positive_ratio)}
        return {}
