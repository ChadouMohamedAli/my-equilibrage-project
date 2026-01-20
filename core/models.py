import pandas as pd
import numpy as np
import random
from collections import defaultdict
from typing import List, Dict, Any

# ----------------------------- Helper functions from solver0.py -----------------------------

def build_time_matrix(gamme: List[Dict], emps: List[int], rend_df: pd.DataFrame) -> pd.DataFrame:
    ops_df = pd.DataFrame(gamme)
    ops_df['idOp'] = ops_df['idOp'].astype(str)
    ops_df = ops_df.set_index('idOp')

    rm = rend_df.pivot(index='idOp', columns='idEmp', values='rendement')

    all_op_ids = [str(g['idOp']) for g in gamme]
    all_emp_ids = [str(e) for e in emps]
    rm = rm.reindex(index=all_op_ids, columns=all_emp_ids)
    rm.fillna(0.85, inplace=True)

    time_mat = pd.DataFrame(index=rm.index, columns=rm.columns)
    for op in time_mat.index:
        for emp in time_mat.columns:
            base_time = float(ops_df.loc[op, 'base_time'])
            rendement = float(rm.loc[op, emp])
            time_mat.loc[op, emp] = base_time / rendement if rendement > 0 else float('inf')
    
    return time_mat.astype(float)

def split_duration(d, target):
    if d <= target:
        return [d]
    best_k = 1
    best_diff = float('inf')
    max_k = max(2, int(d // target) + 3)
    for k in range(2, max_k + 1):
        chunk = d / k
        diff = abs(chunk - target)
        if diff < best_diff:
            best_diff = diff
            best_k = k
    chunk = d / best_k
    return [chunk] * best_k

def expand_gamme(gamme, target_duration):
    expanded = []
    for g in gamme:
        op_id = str(g["idOp"])
        base = float(g["base_time"])
        parts = split_duration(base, target_duration)
        if len(parts) == 1:
            expanded.append({"idOp": op_id, "ordre": g["ordre"], "base_time": parts[0]})
        else:
            for i, p in enumerate(parts, start=1):
                expanded.append({"idOp": f"{op_id}_{i}", "ordre": g["ordre"], "base_time": p})
    return expanded

def expand_rendement(rend_list, expanded_gamme):
    rend_df = pd.DataFrame(rend_list)
    rend_map = {(str(row["idOp"]), str(row["idEmp"])): row["rendement"] for _, row in rend_df.iterrows()}
    expanded = []
    employees = rend_df["idEmp"].unique()
    for g in expanded_gamme:
        full_id = g["idOp"]
        base_id = full_id.split("_")[0]
        for emp in employees:
            key = (base_id, str(emp))
            r = rend_map.get(key, 1.0)
            expanded.append({"idOp": full_id, "idEmp": emp, "rendement": r})
    return expanded

# ----------------------------- Core Solver Logic from solver0.py ------------------------------------

def greedy_initial_assign(time_mat: pd.DataFrame, cfg: Dict) -> Dict:
    max_ops = cfg.get("max_operations_per_emp", len(time_mat))
    assignments = {}
    emp_load = defaultdict(float)
    emp_count = defaultdict(int)
    
    ops_sorted = time_mat.index.tolist()
    ops_sorted = sorted(ops_sorted, key=lambda o: time_mat.loc[o].max(), reverse=True)

    for op in ops_sorted:
        candidates = list(time_mat.columns)
        candidates.sort(key=lambda e: (time_mat.loc[op, e], emp_load[e]))
        chosen = None
        for e in candidates:
            if emp_count[e] < max_ops:
                chosen = e
                break
        if chosen is None:
            chosen = candidates[0]
        assignments[op] = chosen
        emp_load[chosen] += float(time_mat.loc[op, chosen])
        emp_count[chosen] += 1
    return assignments

def compute_score(emp_load, emp_ops, max_ops, w1=0.6, w2=0.25, w3=0.05, w4=0.2):
    loads = list(emp_load.values())
    makespan = max(loads) if loads else 0
    total_time = sum(loads)
    makespan_norm = makespan / total_time if total_time > 0 else 1
    min_load = min(loads) if loads else 0
    imbalance_norm = (makespan - min_load) / makespan if makespan > 0 else 0
    overload_sum = sum(max(0, len(emp_ops[e]) - max_ops) for e in emp_ops)
    total_ops = sum(len(v) for v in emp_ops.values())
    overload_penalty = overload_sum / total_ops if total_ops > 0 else 0
    used_employees = len([e for e in emp_ops if len(emp_ops[e]) > 0])
    total_employees = len(emp_ops)
    employee_count_penalty = used_employees / total_employees if total_employees > 0 else 0
    return (w1 * makespan_norm + w2 * imbalance_norm + w3 * overload_penalty + w4 * employee_count_penalty)

def compute_metrics(assignments, time_mat):
    emp_load = defaultdict(float)
    emp_ops = defaultdict(list)
    for op, e in assignments.items():
        t = float(time_mat.loc[op, e])
        emp_load[e] += t
        emp_ops[e].append((op, t))
    loads = np.array(list(emp_load.values())) if emp_load else np.array([0.0])
    makespan = float(loads.max()) if len(loads) > 0 else 0.0
    avg_load = float(loads.mean()) if len(loads) > 0 else 0.0
    balance_index = float((loads.min() / loads.max()) if loads.max() > 0 else 1.0)
    used_emps = len([e for e, ops in emp_ops.items() if len(ops) > 0])
    metrics = {
        "makespan": round(makespan, 2),
        "avg_load": round(avg_load, 2),
        "balance_index": round(balance_index, 3),
        "used_employees": used_emps,
        "emp_loads": {e: round(v, 2) for e, v in emp_load.items()},
        "emp_ops": {e: [(op, round(t, 2)) for op, t in ops] for e, ops in emp_ops.items()}
    }
    return metrics, emp_load, emp_ops

def local_search_balance(assignments, time_mat, cfg):
    max_iter = cfg.get("max_iter_local_search", 2000)
    max_ops = cfg.get("max_operations_per_emp", 999)
    ops = list(time_mat.index)
    emps = list(time_mat.columns)

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
    no_improve, patience = 0, 200

    for _ in range(max_iter):
        if no_improve > patience: break
        op = random.choice(ops)
        cur_emp = best_assign[op]
        cur_time = float(time_mat.loc[op, cur_emp])
        improved = False
        for cand in sorted(emps, key=lambda e: time_mat.loc[op, e]):
            if cand == cur_emp or len(emp_ops[cand]) >= max_ops: continue
            cand_time = float(time_mat.loc[op, cand])
            emp_load[cur_emp] -= cur_time; emp_load[cand] += cand_time
            emp_ops[cur_emp].remove(op); emp_ops[cand].append(op)
            new_score = compute_score(emp_load, emp_ops, max_ops)
            emp_load[cur_emp] += cur_time; emp_load[cand] -= cand_time
            emp_ops[cur_emp].append(op); emp_ops[cand].remove(op)
            if new_score < best_score:
                best_assign[op] = cand
                emp_load[cur_emp] -= cur_time; emp_load[cand] += cand_time
                emp_ops[cur_emp].remove(op); emp_ops[cand].append(op)
                best_score = new_score
                improved = True; no_improve = 0
                break
        if improved: continue
        no_improve += 1
    
    final_metrics, _, _ = compute_metrics(best_assign, time_mat)
    return best_assign, final_metrics

# ----------------------------- Main `solve_assignment` function -----------------------------

def solve_assignment(gamme: List[Dict], employees: List[int], predicted_rendement: List[Dict], config: Dict) -> Dict:
    """ Main function to solve the assignment problem using the full logic from solver0.py """
    
    # 1. Expand gamme using splitting logic
    durations = [g["base_time"] for g in gamme]
    target_duration = float(np.mean(durations)) if durations else 0
    expanded_gamme = expand_gamme(gamme, target_duration)
    expanded_rend = expand_rendement(predicted_rendement, expanded_gamme)
    
    # 2. Build time matrix
    time_mat = build_time_matrix(expanded_gamme, employees, pd.DataFrame(expanded_rend))

    # 3. Initial greedy assignment
    initial_assign = greedy_initial_assign(time_mat, config)

    # 4. Local search optimizer
    best_assign, final_metrics = local_search_balance(initial_assign, time_mat, config)

    # 5. Build JSON result
    assignments_list = [{"idOp": op, "idEmp": emp, "time": float(time_mat.loc[op, emp])} for op, emp in best_assign.items()]

    return {"assignments": assignments_list, "metrics": final_metrics, "target_duration": target_duration}
