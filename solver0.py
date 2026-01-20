#api.py
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any
import json
from tabulate import tabulate
import math
import random
from collections import defaultdict, namedtuple
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

app = FastAPI()

# ----------------------------- INPUT MODELS -----------------------------

class OpItem(BaseModel):
    idOp: str
    ordre: int
    base_time: float

class EmpItem(BaseModel):
    idEmp: str

class RendItem(BaseModel):
    idEmp: str
    idOp: str
    rendement: float

class ConfigItem(BaseModel):
    max_operations_per_emp: int
    objective: str
    balance_weight: float
    minimize_employees: bool
    max_iter_local_search: int

class SolveRequest(BaseModel):
    gamme: List[OpItem]
    employees: List[EmpItem]
    predicted_rendement: List[RendItem]
    config: ConfigItem

# ----------------------------- Helper functions -----------------------------
def build_time_matrix(gamme, emps, rend_df):
    # force idOp and idEmp as string everywhere
    ops_df = pd.DataFrame(gamme)
    ops_df['idOp'] = ops_df['idOp'].astype(str)
    ops_df = ops_df.set_index('idOp')

    rm = pd.DataFrame(rend_df)
    rm['idOp'] = rm['idOp'].astype(str)
    rm['idEmp'] = rm['idEmp'].astype(str)
    rm = rm.pivot(index='idOp', columns='idEmp', values='rendement')

    emps_df = pd.DataFrame(emps)
    emps_df['idEmp'] = emps_df['idEmp'].astype(str)
    emps_df = emps_df.set_index('idEmp')

    # create time matrix: base_time / rendement
    rm = pd.DataFrame(rend_df).pivot(index='idOp', columns='idEmp', values='rendement')
    time_mat = pd.DataFrame(index=rm.index, columns=rm.columns)
    for op in time_mat.index:
        for emp in time_mat.columns:
            base    = float(ops_df.loc[op, 'base_time'])
            r       = float(rm.loc[op, emp])
            time_mat.loc[op, emp] = base / r if r>0 else float('inf')
    time_mat = time_mat.astype(float)
    return time_mat

# ----------------------------- functions ------------------------------------
def greedy_initial_assign(time_mat, cfg):
    # assign each op to the employee minimizing time, but respect max_operations_per_emp
    max_ops = cfg.get("max_operations_per_emp", len(time_mat))
    assignments = {}
    emp_load = defaultdict(float)
    emp_count = defaultdict(int)
    # sort ops by descending base_time to place heavy ops first
    ops_sorted = time_mat.index.tolist()
    ops_sorted = sorted(ops_sorted, key=lambda o: time_mat.loc[o].max(), reverse=True)
    for op in ops_sorted:
        # choose best available employee
        # sort employees by time then by current load
        candidates = list(time_mat.columns)
        # order by (time, load)
        candidates.sort(key=lambda e: (time_mat.loc[op, e], emp_load[e]))
        chosen = None
        for e in candidates:
            if emp_count[e] < max_ops:
                chosen = e
                break
        if chosen is None:
            # if none available (rare), choose absolute best (allow overflow)
            chosen = candidates[0]
        assignments[op] = chosen
        emp_load[chosen] += float(time_mat.loc[op, chosen])
        emp_count[chosen] += 1
    return assignments, emp_load

# ----------------------------- functions ------------------------------------
def compute_score(emp_load, emp_ops, max_ops, w1=0.6, w2=0.25, w3=0.05, w4=0.2): # w1=0.6, w2=0.25, w3=0.1, w4=0.05
    # w1=0.6, w2=0.25, w3=0.1, w4=0.15  -- Balanced Mode
    # w1=0.8, w2=0.1, w3=0.05, w4=0.05  -- Fastest Production
    # w1=0.4, w2=0.4, w3=0.1, w4=0.1    -- Best Employee Balance

    loads = list(emp_load.values())
    makespan = max(loads)
    total_time = sum(loads)

    # 1. Makespan normalized (the fastest possible production time - prioritize reducing bottleneck employee)
    makespan_norm = makespan / total_time if total_time > 0 else 1

    # 2. Load imbalance normalized (equal workload for everyone)
    min_load = min(loads)
    imbalance_norm = (makespan - min_load) / makespan if makespan > 0 else 0

    # 3. Overload penalty (max operations per employee is a strict rule)
    overload_sum = sum(
        max(0, len(emp_ops[e]) - max_ops)
        for e in emp_ops
    )
    total_ops = sum(len(v) for v in emp_ops.values())
    overload_penalty = overload_sum / total_ops if total_ops > 0 else 0

    # 4. Employee count penalty (minimize team size)
    used_employees = len([e for e in emp_ops if len(emp_ops[e]) > 0])
    total_employees = len(emp_ops)
    employee_count_penalty = used_employees / total_employees

    # Weighted score
    score = (
            w1 * makespan_norm +
            w2 * imbalance_norm +
            w3 * overload_penalty +
            w4 * employee_count_penalty
    )

    return score

# ----------------------------- functions ------------------------------------
def compute_metrics(assignments, time_mat):
    emp_load = defaultdict(float)
    emp_ops = defaultdict(list)
    for op, e in assignments.items():
        t = float(time_mat.loc[op, e])
        emp_load[e] += t
        emp_ops[e].append((op, t))
    loads = np.array(list(emp_load.values())) if emp_load else np.array([0.0])
    makespan = float(loads.max()) if len(loads)>0 else 0.0
    avg_load = float(loads.mean()) if len(loads)>0 else 0.0
    balance_index = float((loads.min()/loads.max()) if loads.max()>0 else 1.0)
    # identify used employees count
    used_emps = len([e for e,ops in emp_ops.items() if len(ops)>0])
    # prepare structured metrics
    metrics = {
        "makespan": round(makespan,2),
        "avg_load": round(avg_load,2),
        "balance_index": round(balance_index,3),
        "used_employees": used_emps,
        "emp_loads": {e: round(v,2) for e,v in emp_load.items()},
        "emp_ops": {e: [(op, round(t,2)) for op,t in ops] for e,ops in emp_ops.items()}
    }
    return metrics, emp_load, emp_ops

# ----------------------------- functions ------------------------------------
def local_search_balance(assignments, time_mat, cfg):

    max_iter = cfg.get("max_iter_local_search", 2000)
    max_ops = cfg.get("max_operations_per_emp", 999)

    ops = list(time_mat.index)
    emps = list(time_mat.columns)

    # Convert initial assignment to load + ops structures
    def build_state(assign):
        emp_load = defaultdict(float)
        emp_ops = defaultdict(list)
        for op, e in assign.items():
            t = float(time_mat.loc[op, e])
            emp_load[e] += t
            emp_ops[e].append(op)
        return emp_load, emp_ops

    best_assign = assignments.copy()
    emp_load, emp_ops = build_state(best_assign)

    best_score = compute_score(emp_load, emp_ops, max_ops)

    no_improve = 0
    patience = 200  # early stop

    for it in range(max_iter):

        # Early stopping
        if no_improve > patience:
            break

        # Pick an operation
        op = random.choice(ops)
        cur_emp = best_assign[op]
        cur_time = float(time_mat.loc[op, cur_emp])

        improved = False

        # --- TRY MOVING OPERATION TO ANOTHER EMPLOYEE ---
        for cand in sorted(emps, key=lambda e: time_mat.loc[op, e]):

            if cand == cur_emp:
                continue

            # simulate move
            cand_time = float(time_mat.loc[op, cand])

            # check max_ops constraint
            if len(emp_ops[cand]) >= max_ops:
                continue

            # update hypothetical loads
            emp_load[cur_emp] -= cur_time
            emp_load[cand] += cand_time

            # update hypothetical ops list
            emp_ops[cur_emp].remove(op)
            emp_ops[cand].append(op)

            new_score = compute_score(emp_load, emp_ops, max_ops)

            # revert
            emp_load[cur_emp] += cur_time
            emp_load[cand] -= cand_time
            emp_ops[cur_emp].append(op)
            emp_ops[cand].remove(op)

            if new_score < best_score:
                # accept move
                best_assign[op] = cand

                emp_load[cur_emp] -= cur_time
                emp_load[cand] += cand_time
                emp_ops[cur_emp].remove(op)
                emp_ops[cand].append(op)

                best_score = new_score
                improved = True
                no_improve = 0
                break

        if improved:
            continue

        # --- TRY SWAPPING WITH ANOTHER OP ---
        other_op = random.choice([o for o in ops if o != op])
        e2 = best_assign[other_op]

        if e2 != cur_emp:

            t1_old = float(time_mat.loc[op, cur_emp])
            t2_old = float(time_mat.loc[other_op, e2])
            t1_new = float(time_mat.loc[op, e2])
            t2_new = float(time_mat.loc[other_op, cur_emp])

            # max_ops constraint for swap
            if (len(emp_ops[cur_emp]) - 1 + 1 > max_ops) or \
               (len(emp_ops[e2]) - 1 + 1 > max_ops):
                # Actually swap two ops, so length unchanged -> safe
                pass  # no need to check

            # simulate swap
            emp_load[cur_emp] = emp_load[cur_emp] - t1_old + t2_new
            emp_load[e2] = emp_load[e2] - t2_old + t1_new

            emp_ops[cur_emp].remove(op)
            emp_ops[cur_emp].append(other_op)

            emp_ops[e2].remove(other_op)
            emp_ops[e2].append(op)

            new_score = compute_score(emp_load, emp_ops, max_ops)

            # revert
            emp_load[cur_emp] = emp_load[cur_emp] + t1_old - t2_new
            emp_load[e2] = emp_load[e2] + t2_old - t1_new

            emp_ops[cur_emp].remove(other_op)
            emp_ops[cur_emp].append(op)

            emp_ops[e2].remove(op)
            emp_ops[e2].append(other_op)

            if new_score < best_score:
                # accept swap
                best_assign[op], best_assign[other_op] = \
                    best_assign[other_op], best_assign[op]

                emp_load[cur_emp] = emp_load[cur_emp] - t1_old + t2_new
                emp_load[e2] = emp_load[e2] - t2_old + t1_new

                emp_ops[cur_emp].remove(op)
                emp_ops[cur_emp].append(other_op)

                emp_ops[e2].remove(other_op)
                emp_ops[e2].append(op)

                best_score = new_score
                improved = True
                no_improve = 0

        if not improved:
            no_improve += 1

    # Final recompute cleanly
    final_load, final_ops = build_state(best_assign)
    final_metrics, _, _ = compute_metrics(best_assign, time_mat)

    return best_assign, final_metrics, final_load, final_ops

# ----------------------------- functions ------------------------------------
def create_heatmap(assignments, time_mat, expanded_gamme, filename="assignment_heatmap.png"):
    op_order = sorted(expanded_gamme, key=lambda g: (g['ordre'], g['idOp']))
    ops = [g['idOp'] for g in op_order]
    #print(ops)

    # Create a mapping from operation to assigned employee
    op_to_emp = {}
    for op in ops:
        if op in assignments:  # For dictionary
            op_to_emp[op] = assignments[op]
            # Handle if assignments is Series (with fallback)
        elif hasattr(assignments, 'index') and op in assignments.index:
            op_to_emp[op] = assignments.loc[op]

    # Reorder employees to create diagonal pattern
    # Assign each operation to a column position based on its order
    emp_order = []
    used_emps = set()

    # First pass: assign employees in the order they appear in operations
    for op in ops:
        if op in op_to_emp and op_to_emp[op] not in used_emps:
            emp_order.append(op_to_emp[op])
            used_emps.add(op_to_emp[op])

    # Second pass: add any remaining employees not assigned to these operations
    all_emps = list(time_mat.columns)
    for emp in all_emps:
        if emp not in used_emps:
            emp_order.append(emp)

    # Now build the matrix with the new ordering
    emps = emp_order
    mat = np.full((len(ops), len(emps)), np.nan)

    for i, op in enumerate(ops):
        for j, emp in enumerate(emps):
            if op in op_to_emp and op_to_emp[op] == emp:
                mat[i, j] = float(time_mat.loc[op, emp])

    # Create visualization
    fig, ax = plt.subplots(figsize=(len(emps) * 1.2 + 2, len(ops) * 0.35 + 2))
    im = ax.imshow(np.nan_to_num(mat, nan=0.0), cmap='YlOrRd', aspect='auto')

    # Annotate cells
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            if not np.isnan(mat[i, j]) and mat[i, j] > 0:
                ax.text(j, i, f"{mat[i, j]:.1f}", ha='center', va='center',
                        color='black', fontsize=8)

    # Format axes
    ax.set_xticks(range(len(emps)))
    ax.set_xticklabels(emps, rotation=45, ha='right')
    ax.set_yticks(range(len(ops)))
    ax.set_yticklabels(ops)
    ax.set_xlabel("Employees")
    ax.set_ylabel("Operations")

    # Add grid lines to make the diagonal more visible
    ax.set_xticks(np.arange(-0.5, len(emps), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(ops), 1), minor=True)
    ax.grid(which="minor", color="gray", linestyle='-', linewidth=0.5)
    ax.tick_params(which="minor", size=0)

    fig.colorbar(im, ax=ax, label='Assigned Time')
    plt.tight_layout()
    plt.savefig(filename, dpi=200)
    plt.close(fig)
    #print(tabulate(mat))
    return filename

# ----------------------------- functions ------------------------------------
def metrics_to_assignments(final_metrics):
    assignments = []

    emp_ops = final_metrics["emp_ops"]

    for emp, ops in emp_ops.items():
        current_time = 0

        for (operation, duration) in ops:
            start = current_time
            end = start + duration

            assignments.append({
                "employee": emp,
                "operation": operation,
                "duration": duration,
                "start": start,
                "end": end,
            })

            current_time = end
    #print(assignments)
    return assignments

# ----------------------------- functions ------------------------------------
def summarize_assignment(assignments):
    df = pd.DataFrame(assignments)

    pivot = df.pivot_table(
        index="employee",
        columns="operation",
        values="duration",
        aggfunc="sum",
        fill_value=0
    )

    #pivot["Total Workload"] = pivot.sum(axis=1)
    # Sort columns numerically (operations)
    op_cols = sorted(
        [c for c in pivot.columns if c != "Total Workload"],
        key=lambda x: int(x)
    )
    pivot = pivot[op_cols]
    pivot["Total Workload"] = pivot.sum(axis=1)
    #pivot = pivot.sort_values("Total Workload", ascending=False)

    print("\n=== Assignment Summary (Pivot Table) ===\n")
    print(pivot.to_string(float_format=lambda x: f"{x:,.2f}"))

    print("\n=== Workload Spread (Max - Min) ===")
    max_wl = pivot["Total Workload"].max()
    min_wl = pivot["Total Workload"].min()
    print(f"Max: {max_wl:.2f}   Min: {min_wl:.2f}   Spread: {max_wl - min_wl:.2f}")

    return pivot

# ----------------------------- functions ------------------------------------
def split_duration(d, target):

    # If no splitting needed
    if d <= target:
        return [d]

    best_k = 1
    best_diff = float('inf')

    # Try k from 1 to maybe 10 chunks or d/target + 3
    max_k = max(2, int(d // target) + 3)

    for k in range(2, max_k + 1):     # start from 2 because we split only
        chunk = d / k
        diff = abs(chunk - target)

        # pick the k that gets chunk_size closest to target
        if diff < best_diff:
            best_diff = diff
            best_k = k

    # produce chunks
    chunk = d / best_k
    return [chunk] * best_k

# ----------------------------- functions ------------------------------------
def expand_gamme(gamme, target_duration):
    expanded = []
    for g in gamme:
        op_id = str(g["idOp"])
        base = float(g["base_time"])

        parts = split_duration(base, target_duration)

        if len(parts) == 1:
            expanded.append({
                "idOp": op_id,
                "ordre": g["ordre"],
                "base_time": parts[0]
            })
        else:
            for i, p in enumerate(parts, start=1):
                expanded.append({
                    "idOp": f"{op_id}_{i}",
                    "ordre": g["ordre"],   # keep same order so heatmap stays in line
                    "base_time": p
                })

    return expanded

def expand_rendement(rend_list, expanded_gamme):
    # Convert list → DataFrame
    rend_df = pd.DataFrame(rend_list)

    # Build lookup
    rend_map = {}
    for _, row in rend_df.iterrows():
        rend_map[(str(row["idOp"]), str(row["idEmp"]))] = row["rendement"]

    expanded = []

    # Get list of all employees from original rendement
    employees = rend_df["idEmp"].unique()

    # Build new rendement rows
    for g in expanded_gamme:
        full_id = g["idOp"]             # e.g., "13_1"
        base_id = full_id.split("_")[0] # e.g., "13"

        for emp in employees:
            key = (base_id, str(emp))
            r = rend_map.get(key, 1.0)
            expanded.append({
                "idOp": full_id,
                "idEmp": emp,
                "rendement": r
            })

    return expanded

# ----------------------------- SOLVE ENDPOINT -----------------------------

@app.post("/solve")
def solve(request: SolveRequest):

    # Convert Pydantic → dict
    data = request.model_dump()

    # -----------------------------
    # 1) Expand gamme using splitting logic
    # -----------------------------
    durations = [g["base_time"] for g in data["gamme"]]
    target_duration = float(np.mean(durations))

    expanded_gamme = expand_gamme(data["gamme"], target_duration)
    expanded_rend = expand_rendement(data["predicted_rendement"], expanded_gamme)

    # -----------------------------
    # 2) Build time matrix
    # -----------------------------
    time_mat = build_time_matrix(expanded_gamme, data["employees"], expanded_rend)

    # -----------------------------
    # 3) Initial greedy assignment
    # -----------------------------
    initial_assign, initial_load = greedy_initial_assign(time_mat, data["config"])
    initial_metrics, _, _ = compute_metrics(initial_assign, time_mat)

    # -----------------------------
    # 4) Local search optimizer
    # -----------------------------
    best_assign, final_metrics, emp_load, emp_ops = local_search_balance(
        initial_assign, time_mat, data["config"]
    )

    # -----------------------------
    # 5) Save heatmap
    # -----------------------------
    heatmap_file = create_heatmap(best_assign, time_mat, expanded_gamme, filename="heatmap_result.png")

    # -----------------------------
    # 6) Build JSON result
    # -----------------------------
    assignments_list = [
        {"idOp": op, "idEmp": emp, "time": float(time_mat.loc[op, emp])}
        for op, emp in best_assign.items()
    ]

    return {
        "assignments": assignments_list,
        "metrics": final_metrics,
        "target_duration": target_duration,
        "heatmap": heatmap_file,
    }