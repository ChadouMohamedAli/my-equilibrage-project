import streamlit as st
import pandas as pd
from datetime import datetime
from database import db
from api_client import api_client
from config import config

# Page configuration
st.set_page_config(
    page_title=config.PAGE_TITLE,
    page_icon=config.PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        margin-bottom: 1rem;
    }
    .section-header {
        font-size: 1.5rem;
        color: #374151;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #E5E7EB;
    }
    .success-box {
        background-color: #D1FAE5;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #10B981;
    }
    .info-box {
        background-color: #DBEAFE;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #3B82F6;
    }
    .stButton > button {
        width: 100%;
        background-color: #3B82F6;
        color: white;
        font-weight: bold;
    }
    .stButton > button:hover {
        background-color: #2563EB;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables"""
    if 'selected_chaine' not in st.session_state:
        st.session_state.selected_chaine = None
    if 'selected_employees' not in st.session_state:
        st.session_state.selected_employees = []
    if 'selected_games' not in st.session_state:
        st.session_state.selected_games = []
    if 'operations' not in st.session_state:
        st.session_state.operations = []
    if 'api_response' not in st.session_state:
        st.session_state.api_response = None


def display_header():
    """Display application header"""
    st.markdown(f'<h1 class="main-header">{config.PAGE_TITLE}</h1>', unsafe_allow_html=True)
    st.markdown("""
    This application allows you to:
    1. Select a production chain
    2. Choose employees
    3. Filter games and operations
    4. Set production parameters
    5. Submit to API for calculation
    """)


def get_chaine_selection():
    """Step 1: Chaine selection"""
    st.markdown('<h2 class="section-header">1. Select Production Chain</h2>', unsafe_allow_html=True)

    chaines = db.get_chaine_list()
    st.print(chaines)

    if not chaines:
        st.warning("No chaines found in database")
        return None

    chaine_options = {f"{c['chaine_id']} - {c['chaine_name']}": c for c in chaines}
    selected_option = st.selectbox(
        "Choose a chaine:",
        options=list(chaine_options.keys()),
        index=0 if not st.session_state.selected_chaine else None,
        key="chaine_select"
    )

    if selected_option:
        selected_chaine = chaine_options[selected_option]
        st.session_state.selected_chaine = selected_chaine
        st.success(f"Selected: **{selected_chaine['chaine_name']}**")
        return selected_chaine

    return None


def get_employee_selection(chaine_id):
    """Step 2: Employee selection"""
    st.markdown('<h2 class="section-header">2. Select Employees</h2>', unsafe_allow_html=True)

    employees = db.get_employees_by_chaine(chaine_id)

    if not employees:
        st.warning("No employees found for this chaine")
        return []

    employee_options = {
        f"{e['employee_id']} - {e['employee_name']} ({e['employee_code']})": e['employee_id']
        for e in employees
    }

    selected_employees = st.multiselect(
        "Select one or more employees:",
        options=list(employee_options.keys()),
        default=st.session_state.selected_employees,
        key="employee_multiselect"
    )

    selected_ids = [employee_options[e] for e in selected_employees]
    st.session_state.selected_employees = selected_ids

    if selected_employees:
        st.info(f"Selected {len(selected_employees)} employee(s)")

    return selected_ids


def get_game_selection(employee_ids):
    """Step 3: Game and operation selection"""
    st.markdown('<h2 class="section-header">3. Select Games and Operations</h2>', unsafe_allow_html=True)

    if not employee_ids:
        st.warning("Please select employees first")
        return []

    games = db.get_games_by_employees(employee_ids)

    if not games:
        st.warning("No games found for selected employees")
        return []

    game_options = {
        f"{g['game_id']} - {g['game_code']}: {g['game_name']}": {
            'game_id': g['game_id'],
            'operation_code': g['operation_code'],
            'game_name': g['game_name']
        }
        for g in games
    }

    selected_games = st.multiselect(
        "Select games (operations will be shown below):",
        options=list(game_options.keys()),
        default=st.session_state.selected_games,
        key="game_multiselect"
    )

    # Display selected operations
    operations = []
    if selected_games:
        st.markdown("**Selected Operations:**")
        for game_key in selected_games:
            game_data = game_options[game_key]
            operations.append({
                'operation_code': game_data['operation_code'],
                'game_name': game_data['game_name']
            })

        # Display operations in a table
        operations_df = pd.DataFrame(operations)
        st.dataframe(operations_df, use_container_width=True)

    st.session_state.selected_games = selected_games
    st.session_state.operations = operations

    return operations


def get_production_parameters():
    """Step 4: Production parameters input"""
    st.markdown('<h2 class="section-header">4. Production Parameters</h2>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        nbr_op_par_emp = st.number_input(
            "Number of operations per employee",
            min_value=1,
            max_value=20,
            value=1,
            step=1,
            key="nbr_op_par_emp"
        )

    with col2:
        nbr_machine_per_emp = st.number_input(
            "Number of machines per employee",
            min_value=1,
            max_value=10,
            value=1,
            step=1,
            key="nbr_machine_per_emp"
        )

    with col3:
        tolerance = st.number_input(
            "Tolerance (%)",
            min_value=0.0,
            max_value=100.0,
            value=5.0,
            step=0.1,
            format="%.1f",
            key="tolerance"
        )

    with col4:
        production_souhaite = st.number_input(
            "Production souhaitée",
            min_value=1,
            value=100,
            step=10,
            key="production_souhaite"
        )

    return {
        'nbr_op_par_emp': nbr_op_par_emp,
        'nbr_machine_per_emp': nbr_machine_per_emp,
        'tolerance': tolerance,
        'production_souhaite': production_souhaite
    }


def submit_to_api(chaine_data, employee_ids, operations, params):
    """Step 5: Submit data to API"""
    st.markdown('<h2 class="section-header">5. Submit to API</h2>', unsafe_allow_html=True)

    if st.button("🚀 Submit Production Plan", type="primary", use_container_width=True):
        if not chaine_data:
            st.error("Please select a chaine first")
            return

        if not employee_ids:
            st.error("Please select at least one employee")
            return

        if not operations:
            st.error("Please select at least one game/operation")
            return

        # Prepare data for API
        api_data = {
            "chaine_id": chaine_data['chaine_id'],
            "chaine_name": chaine_data['chaine_name'],
            "selected_employees": employee_ids,
            "selected_games": [g.split(' - ')[0] for g in st.session_state.selected_games],
            "operations": operations,
            "nbr_op_par_emp": params['nbr_op_par_emp'],
            "nbr_machine_per_emp": params['nbr_machine_per_emp'],
            "tolerance": params['tolerance'],
            "production_souhaite": params['production_souhaite']
        }

        # Show loading spinner
        with st.spinner("Sending data to API and calculating..."):
            # Send to API
            result = api_client.send_production_data(api_data)

            # Store result in session state
            st.session_state.api_response = result

            if result['success']:
                st.success("✅ Data submitted successfully!")
                return True
            else:
                st.error(f"❌ Submission failed: {result['message']}")
                return False

    return False


def display_api_results():
    """Display API response results"""
    if st.session_state.api_response and st.session_state.api_response['success']:
        st.markdown('<h2 class="section-header">📊 Calculation Results</h2>', unsafe_allow_html=True)

        result_data = st.session_state.api_response['data']

        # Display in expandable sections
        with st.expander("📋 Summary Results", expanded=True):
            if 'summary' in result_data:
                summary_df = pd.DataFrame([result_data['summary']])
                st.dataframe(summary_df, use_container_width=True)

        with st.expander("👥 Employee Allocation"):
            if 'employee_allocation' in result_data:
                emp_df = pd.DataFrame(result_data['employee_allocation'])
                st.dataframe(emp_df, use_container_width=True)

        with st.expander("🎮 Game Schedule"):
            if 'game_schedule' in result_data:
                game_df = pd.DataFrame(result_data['game_schedule'])
                st.dataframe(game_df, use_container_width=True)

        with st.expander("📈 Production Plan"):
            if 'production_plan' in result_data:
                plan_df = pd.DataFrame(result_data['production_plan'])
                st.dataframe(plan_df, use_container_width=True)

        # Download buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Download Results as CSV"):
                # Convert results to CSV
                csv = pd.DataFrame([result_data]).to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"production_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )

        with col2:
            if st.button("🔄 New Calculation"):
                # Clear session state for new calculation
                for key in ['selected_chaine', 'selected_employees',
                            'selected_games', 'operations', 'api_response']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()


def main():
    """Main application flow"""
    initialize_session_state()
    display_header()

    # Create tabs for better organization
    tab1, tab2 = st.tabs(["🧭 Configuration", "📊 Results"])

    with tab1:
        # Step 1: Chaine selection
        chaine_data = get_chaine_selection()

        if chaine_data:
            # Step 2: Employee selection
            employee_ids = get_employee_selection(chaine_data['chaine_id'])

            # Step 3: Game selection
            operations = get_game_selection(employee_ids)

            # Step 4: Production parameters
            params = get_production_parameters()

            # Step 5: Submit to API
            submitted = submit_to_api(chaine_data, employee_ids, operations, params)

            if submitted:
                st.balloons()

    with tab2:
        # Display API results
        display_api_results()


if __name__ == "__main__":
    main()