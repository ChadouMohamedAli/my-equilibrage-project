import pandas as pd
import joblib
from typing import List, Dict, Any

# ------------------------------------------------------------
# Load model + encoders
# ------------------------------------------------------------
try:
    model = joblib.load("equilibrage_model_XGBRegressorMtest.pkl")
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

    print("=== Encoders loaded successfully ===")

except FileNotFoundError as e:
    print(f"Error loading model or data: {e}")
    print("Please ensure 'equilibrage_model_XGBRegressor.pkl' and 'input/agg.csv' are in the correct paths.")
    # Assign dummy values to allow import to succeed
    model = None
    EMP_FALLBACK, OP_FALLBACK, MACHINE_FALLBACK, CHAIN_FALLBACK = 0.85, 0.85, 0.85, 0.85
    enc_emp_map, enc_op_map, enc_machine_map, enc_chain_map = {}, {}, {}, {}


def predict_rendement(employees: List[int], operations: List[Dict[str, Any]], chain_name: str) -> List[Dict[str, Any]]:
    """
    Predicts the 'rendement' for each employee-operation combination.

    Args:
        employees: A list of employee IDs.
        operations: A list of dictionaries, where each dictionary represents an operation.
        chain_name: The name of the production chain.

    Returns:
        A list of dictionaries, each containing 'idEmp', 'idOp', and 'rendement'.
    """
    if model is None:
        print("Model not loaded. Returning empty predictions.")
        return []

    # 1) Build dataframe of combinations
    rows = []
    for emp_id in employees:
        for op in operations:
            rows.append({
                "IDEmploye": int(emp_id),
                "IDOperation": int(op['operation_id']),
                "avg_temps": float(op['temps_execution']),
                "most_used_machine": op.get("machine", "UNKNOWN"), # Get machine from op if available
                "most_used_chain": chain_name
            })

    if not rows:
        return []

    df = pd.DataFrame(rows)

    # 2) ENCODING
    df["IDEmploye_encoded"] = df["IDEmploye"].map(enc_emp_map)
    df["IDOperation_encoded"] = df["IDOperation"].map(enc_op_map)
    df["most_used_machine_encoded"] = df["most_used_machine"].map(enc_machine_map)
    df["most_used_chain_encoded"] = df["most_used_chain"].map(enc_chain_map)

    # *** SECONDARY FIX: Use modern pandas syntax to fill missing values ***
    df.fillna({
        "IDEmploye_encoded": EMP_FALLBACK,
        "IDOperation_encoded": OP_FALLBACK,
        "most_used_machine_encoded": MACHINE_FALLBACK,
        "most_used_chain_encoded": CHAIN_FALLBACK
    }, inplace=True)

    # 3) Build feature matrix
    X = df[[
        "IDEmploye_encoded",
        "IDOperation_encoded",
        "avg_temps",
        "most_used_machine_encoded",
        "most_used_chain_encoded"
    ]]

    # 4) Predict
    df["predicted_rendement"] = model.predict(X)

    # 5) Format output
    output = []
    for _, row in df.iterrows():
        output.append({
            "idEmp": str(row["IDEmploye"]),
            "idOp": str(row["IDOperation"]),
            "rendement": float(round(row["predicted_rendement"], 3))
        })

    return output
