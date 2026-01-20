from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

# Import the refactored core logic
from core.preprocessing import predict_rendement
from core.models import solve_assignment

# Create a FastAPI app instance
app = FastAPI(
    title="Equilibrage Solver API",
    description="An API to receive production data and return an optimized plan.",
    version="1.0.0"
)

# --- Pydantic Models for API Request Body ---

class Metadata(BaseModel):
    timestamp: str
    version: str
    source: str

class Chaine(BaseModel):
    chaine_id: int
    nom_chaine: str

class Game(BaseModel):
    game_id: int
    game_name: str

class Operation(BaseModel):
    operation_id: int
    code_operation: str
    nom_operation: str
    temps_preparation: float
    temps_execution: float

class ProductionParams(BaseModel):
    nbr_op_par_emp: int
    nbr_machine_per_emp: int
    tolerance: float
    production_souhaite: int
    priorite: str
    date_limite: str | None
    shift: str

class ProductionData(BaseModel):
    metadata: Metadata
    chaine: Chaine
    employes: List[int]
    game: Game
    operations: List[Operation]
    parametres_production: ProductionParams


@app.post("/solve")
async def solve_production_plan(data: ProductionData):
    """
    This endpoint receives production data, orchestrates the prediction
    and solving process, and returns the final assignment plan.
    """
    try:
        print("--- Received Production Data ---")
        request_data = data.model_dump()
        print(request_data)

        # 1. Predict Rendement
        print("\n--- Step 1: Predicting Rendement ---")
        predicted_rendements = predict_rendement(
            employees=request_data['employes'],
            operations=request_data['operations'],
            chain_name=request_data['chaine']['nom_chaine']
        )
        if not predicted_rendements:
            raise HTTPException(status_code=400, detail="Rendement prediction failed or returned no results.")
        print(f"Successfully predicted {len(predicted_rendements)} rendements.")

        # 2. Prepare data for the solver
        gamme_for_solver = [
            {
                "idOp": str(op['operation_id']),
                "ordre": i,
                "base_time": op['temps_execution']
            }
            for i, op in enumerate(request_data['operations'])
        ]
        solver_config = {
            "max_operations_per_emp": request_data['parametres_production']['nbr_op_par_emp'],
        }

        # 3. Solve the Assignment Problem
        print("\n--- Step 2: Solving Assignment ---")
        assignment_result = solve_assignment(
            gamme=gamme_for_solver,
            employees=request_data['employes'],
            predicted_rendement=predicted_rendements,
            config=solver_config
        )
        print("Successfully generated assignment plan.")

        # 4. Return the final result, including predicted_rendements
        print("\n--- Step 3: Returning Final Plan ---")
        
        # Combine assignment results and predicted rendements
        final_response = {
            "assignment_plan": assignment_result,
            "predicted_rendements": predicted_rendements
        }
        return final_response

    except Exception as e:
        print(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# To run this API:
# uvicorn Solver:app --reload
