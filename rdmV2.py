# LAST Version 10/12/25
"""
test input
{
  "employees": ["191", "941", "903"],
  "operations": [
    {
      "idOp": "589",
      "avg_temps": 8.5,
      "machine": "MAC-01"
    },
    {
      "idOp": "587",
      "avg_temps": 31.2,
      "machine": "MAC-02"
    },
    {
      "idOp": "588",
      "avg_temps": 29.0,
      "machine": "NEW-MACHINE"
    }
  ]
}
"""
import pandas as pd
import joblib
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional

# ------------------------------------------------------------
# Load model + encoders
# ------------------------------------------------------------
model = joblib.load("equilibrage_model_XGBRegressor.pkl")

agg_df = pd.read_csv("input/agg.csv")

# Precompute encoders
enc_emp_map = agg_df.groupby("IDEmploye")["avg_rendement"].mean()
enc_op_map = agg_df.groupby("IDOperation")["avg_rendement"].mean()
enc_machine_map = agg_df.groupby("most_used_machine")["avg_rendement"].mean()
enc_chain_map = agg_df.groupby("most_used_chain")["avg_rendement"].mean()

EMP_FALLBACK = float(enc_emp_map.mean())
OP_FALLBACK = float(enc_op_map.mean())
MACHINE_FALLBACK = float(enc_machine_map.mean())
CHAIN_FALLBACK = float(enc_chain_map.mean())

print("=== Encoders loaded ===")
print("----------------------------------------")

# ------------------------------------------------------------
# Input format
# ------------------------------------------------------------
class OperationInput(BaseModel):
    idOp: str
    avg_temps: float
    machine: Optional[str] = None
    chain: Optional[str] = None   # <--- STILL REQUIRED BY MODEL (fallback allowed)

class PredictionInput(BaseModel):
    employees: List[str]
    operations: List[OperationInput]


# ------------------------------------------------------------
# Create API
# ------------------------------------------------------------
app = FastAPI()


@app.post("/predict-rendement")
def predict_rendement(input_data: PredictionInput):

    print("\n================ NEW REQUEST ================")

    # 1) Build dataframe of combinations
    rows = []
    for emp in input_data.employees:
        for op in input_data.operations:
            rows.append({
                "IDEmploye": int(emp),
                "IDOperation": int(op.idOp),
                "avg_temps": float(op.avg_temps),
                "most_used_machine": op.machine,
                "most_used_chain": op.chain
            })

    df = pd.DataFrame(rows)
    print("\n--- Incoming DF ---")
    print(df.head())
    print("----------------------------------------")

    # 2) ENCODING
    print("\n--- Encoding checks ---")

    df["IDEmploye_encoded"] = df["IDEmploye"].map(enc_emp_map)
    df["IDOperation_encoded"] = df["IDOperation"].map(enc_op_map)
    df["most_used_machine_encoded"] = df["most_used_machine"].map(enc_machine_map)
    df["most_used_chain_encoded"] = df["most_used_chain"].map(enc_chain_map)

    # Report missing categories
    if df["IDEmploye_encoded"].isna().any():
        print("⚠️ Missing employees:", df[df["IDEmploye_encoded"].isna()]["IDEmploye"].unique())

    if df["IDOperation_encoded"].isna().any():
        print("⚠️ Missing operations:", df[df["IDOperation_encoded"].isna()]["IDOperation"].unique())

    if df["most_used_machine_encoded"].isna().any():
        print("⚠️ Missing machines:", df[df["most_used_machine_encoded"].isna()]["most_used_machine"].unique())

    if df["most_used_chain_encoded"].isna().any():
        print("⚠️ Missing chains:", df[df["most_used_chain_encoded"].isna()]["most_used_chain"].unique())

    # Fill fallbacks
    df["IDEmploye_encoded"].fillna(EMP_FALLBACK, inplace=True)
    df["IDOperation_encoded"].fillna(OP_FALLBACK, inplace=True)
    df["most_used_machine_encoded"].fillna(MACHINE_FALLBACK, inplace=True)
    df["most_used_chain_encoded"].fillna(CHAIN_FALLBACK, inplace=True)

    print("\n--- Encoded DF ---")
    print(df[[
        "IDEmploye", "IDEmploye_encoded",
        "IDOperation", "IDOperation_encoded",
        "avg_temps",
        "most_used_machine", "most_used_machine_encoded",
        "most_used_chain", "most_used_chain_encoded"
    ]].head())
    print("----------------------------------------")

    # 3) Build feature matrix with EXACT SAME feature names as model training
    X = df[[
        "IDEmploye_encoded",
        "IDOperation_encoded",
        "avg_temps",
        "most_used_machine_encoded",
        "most_used_chain_encoded"
    ]]

    print("\n--- Feature Matrix Sent to Model ---")
    print(X.head())
    print("----------------------------------------")

    # 4) Predict
    df["predicted_rendement"] = model.predict(X)

    print("\n--- Predictions ---")
    print(df[["IDEmploye", "IDOperation", "predicted_rendement"]].head())
    print("----------------------------------------")

    # 5) Format output
    output = []
    for _, row in df.iterrows():
        output.append({
            "idEmp": str(row["IDEmploye"]),
            "idOp": str(row["IDOperation"]),
            "rendement": float(round(row["predicted_rendement"], 3))
        })

    return {"predicted_rendement": output}
