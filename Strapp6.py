import streamlit as st
import pandas as pd
from datetime import datetime
import json
import io # Import io for handling in-memory files

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
        text-align: center;
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
        border-left: 44px solid #10B981;
    }
    .info-box {
        background-color: #DBEAFE;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #3B82F6;
    }
    .stButton > button {
        background-color: #3B82F6;
        color: white;
        font-weight: bold;
        border: none;
    }
    .stButton > button:hover {
        background-color: #2563EB;
        border: none;
    }
    .metric-card {
        background-color: #F3F4F6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #3B82F6;
    }
    .dataframe {
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables"""
    defaults = {
        'selected_chaine': None,
        'selected_employees': [],
        'selected_employee_names': [],
        'selected_game': None,
        'selected_game_name': None,
        'selected_operations': [],  # Store selected operation IDs
        'all_operations': [],  # Store all operations for selected game
        'api_response': None,
        'predicted_rendements_data': None, # New: Store predicted rendements
        'show_advanced': False,
        'db_connected': False,
        'operations_loaded': False,  # Track if operations are loaded
        'original_op_id_to_time_map': {} # New: Store original op ID to base time
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def display_header():
    """Display application header"""
    st.markdown(f'<h1 class="main-header">{config.PAGE_TITLE}</h1>', unsafe_allow_html=True)

    # Check database connection
    if not st.session_state.db_connected:
        with st.spinner("Connecting to database..."):
            st.session_state.db_connected = db.test_connection()

    if st.session_state.db_connected:
        #st.success("✅ Connected to MySQL database")
        st.toast(f"✅ Connected to MySQL database", duration=5)
    else:
        #st.error("❌ Database connection failed. Please check your configuration.")
        st.toast(f"❌ Database connection failed. Please check your configuration.", duration=15)
        st.stop()

    st.markdown("---")


def get_chaine_selection():
    """Step 1: Chaine selection"""
    st.markdown('<h2 class="section-header">1. Sélectionner la Chaîne de Production</h2>', unsafe_allow_html=True)

    # Add refresh button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Rafraîchir la liste", width='stretch'):
            st.rerun()
    with col1:
        chaines = db.get_chaine_list()

        if not chaines:
            st.warning("Aucune chaîne trouvée dans la base de données")
            return None

        # Format options for display
        chaine_options = {}
        for c in chaines:
            chaine_id = c.get('id_chaine', c.get('chaine_id', ''))
            chaine_name = c.get('nom_chaine', c.get('chaine_name', ''))
            display_text = f"{chaine_id} - {chaine_name}"
            chaine_options[display_text] = {
                'id_chaine': chaine_id,
                'nom_chaine': chaine_name
            }

    # Determine default index
    default_index = 0
    if st.session_state.selected_chaine:
            saved_chaine = st.session_state.selected_chaine
            saved_id = saved_chaine.get('id_chaine', saved_chaine.get('chaine_id', ''))
            for i, (display, data) in enumerate(chaine_options.items()):
                if str(data['id_chaine']) == str(saved_id):
                    default_index = i
                    break

    selected_option = st.selectbox(
            "Choisir une chaîne:",
            options=list(chaine_options.keys()),
            index=default_index,
            key="chaine_select",
            help="Sélectionnez la chaîne de production"
        )

    if selected_option:
        selected_chaine = chaine_options[selected_option]
        st.session_state.selected_chaine = selected_chaine

        # Display chaine info
        col1, col2 = st.columns(2)
        with col1:
                st.info(f"**Chaîne sélectionnée:** {selected_chaine.get('nom_chaine', 'N/A')}")
        with col2:
                st.info(f"**ID Chaîne:** {selected_chaine.get('id_chaine', 'N/A')}")

        return selected_chaine

    return None


def get_employee_selection(chaine_id):
    """Step 2: Employee selection with 'Select All' option"""
    st.markdown('<h2 class="section-header">2. Sélectionner les Employés</h2>', unsafe_allow_html=True)

    with st.spinner("Chargement des employés..."):
        employees = db.get_employees_by_chaine(chaine_id)

    if not employees:
        st.warning("Aucun employé trouvé pour cette chaîne")
        return []

    # Format employee options
    employee_options = {}
    for emp in employees:
        emp_id = emp.get('id_employe')
        emp_name = emp.get('nom_employe', 'N/A')
        emp_code = emp.get('code_employe', 'N/A')
        emp_poste = emp.get('poste', 'N/A')

        display_text = f"{emp_id} - {emp_name} ({emp_code}) - {emp_poste}"
        employee_options[display_text] = {
            'id': emp_id,
            'name': emp_name,
            'code': emp_code,
            'poste': emp_poste
        }
    
    # Create and store a mapping from employee ID to a unique name (Name (Code))
    st.session_state.employee_map = {
        str(v['id']): f"{v['name']} ({v['code']}) [ID:{v['id']}]" for v in employee_options.values()
    }

    # Add "Select All" option at the beginning
    all_option_text = "✅ Sélectionner tous les employés"
    employee_options_with_all = {all_option_text: {'id': 'ALL', 'is_all': True}}
    employee_options_with_all.update(employee_options)

    # Filter saved selections to only include valid options
    valid_saved_selections = []
    for saved_option in st.session_state.selected_employee_names:
        if saved_option in employee_options_with_all:
            valid_saved_selections.append(saved_option)
        else:
            # Option no longer exists, clear related session state
            st.session_state.selected_employee_names.remove(saved_option)
            if 'selected_employees' in st.session_state:
                # Try to remove the corresponding ID
                pass

    # Multi-select for employees
    selected_display = st.multiselect(
        "Sélectionner un ou plusieurs employés:",
        options=list(employee_options_with_all.keys()),
        default=valid_saved_selections,
        key="employee_multiselect",
        help="Sélectionnez les employés qui participeront à la production. 'Sélectionner tous' pour choisir tous les employés."
    )

    # Handle "Select All" logic
    selected_ids = []
    selected_names = []

    if all_option_text in selected_display:
        # Select all employees (excluding the "Select All" option itself)
        selected_names = [all_option_text] + list(employee_options.keys())
        selected_ids = [emp['id'] for emp in employee_options.values()]
    else:
        # Get selected employee IDs and names
        for display in selected_display:
            if display in employee_options:
                emp_data = employee_options[display]
                selected_ids.append(emp_data['id'])
                selected_names.append(display)

    st.session_state.selected_employees = selected_ids
    st.session_state.selected_employee_names = selected_names

    # Display selected employees
    if selected_ids:
        if all_option_text in selected_display:
            #st.success(f"✅ Tous les employés sont sélectionnés ({len(selected_ids)} employés)")
            st.toast(f"✅ Tous les employés sont sélectionnés ({len(selected_ids)} employés)", duration=10)
        else:
            #st.success(f"✅ {len(selected_ids)} employé(s) sélectionné(s)")
            st.toast(f"✅ {len(selected_ids)} employé(s) sélectionné(s)", duration=10)

        # Show selected employees in a table (limit to 10 for display)
        if selected_names and selected_names[0] != all_option_text:
            selected_data = []
            for display in selected_names[:10]:  # Show first 10 only
                if display in employee_options:
                    emp_data = employee_options[display]
                    selected_data.append({
                        'ID': emp_data['id'],
                        'Nom': emp_data['name'],
                        'Code': emp_data['code'],
                        'Poste': emp_data['poste']
                    })

            if selected_data:
                df_employees = pd.DataFrame(selected_data)
                st.dataframe(df_employees, width="stretch", hide_index=True)

                if len(selected_names) > 10:
                    st.info(f"Et {len(selected_names) - 10} autres employés...")

    return selected_ids


def get_game_selection():
    """Step 3: Game selection - SINGLE SELECTION ONLY"""
    st.markdown('<h2 class="section-header">3. Sélectionner la Gamme</h2>', unsafe_allow_html=True)

    with st.spinner("Chargement des gammes..."):
        games = db.get_games()

    if not games:
        st.warning("Aucune gamme trouvée")
        return []

    # Format game options for SINGLE SELECT
    game_options = {}
    for game in games:
        game_id = game.get('id_game')
        game_code = game.get('code_game', 'N/A')
        game_date = game.get('date', 'N/A')
        game_NbrOperations = game.get('NbrOperations', 0)

        # Format date if it exists
        try:
            if game_date and isinstance(game_date, str):
                game_date = datetime.strptime(game_date, '%Y-%m-%d').strftime('%d/%m/%Y')
        except:
            pass

        display_text = f"{game_id}: {game_date} - {game_code} [{game_NbrOperations} opérations]"
        game_options[display_text] = {
            'game_id': game_id,
            'game_date': game_date,
            'game_code': game_code,
            'game_NbrOperations': game_NbrOperations,
            'temps_standard': game.get('temps_standard')
        }

    # Add empty option at the beginning for "no selection"
    game_options_with_none = {"-- Sélectionner une gamme --": None}
    game_options_with_none.update(game_options)

    # Determine default selection - always start with no selection
    default_index = 0  # Always default to "no selection"

    # SINGLE SELECT for game (not multiselect) - NO DEFAULT SELECTION
    selected_display = st.selectbox(
        "Sélectionner une gamme:",
        options=list(game_options_with_none.keys()),
        index=default_index,
        key="game_select",
        help="Sélectionnez une seule gamme à produire"
    )

    # Clear operations if game is deselected
    if selected_display == "-- Sélectionner une gamme --":
        st.session_state.selected_game = None
        st.session_state.selected_game_name = None
        st.session_state.all_operations = []
        st.session_state.selected_operations = []
        st.session_state.operations_loaded = False
        st.session_state.original_op_id_to_time_map = {} # Clear map
        return []

    # Get selected game data
    if selected_display and selected_display in game_options:
        game_data = game_options[selected_display]

        # Check if game changed
        game_changed = (
                st.session_state.selected_game != game_data['game_id'] or
                not st.session_state.operations_loaded
        )

        st.session_state.selected_game = game_data['game_id']
        st.session_state.selected_game_name = selected_display

        if game_changed:
            # Load operations for this game
            with st.spinner("Chargement des opérations..."):
                operations = db.get_operations_by_games([game_data['game_id']])
                st.session_state.all_operations = operations
                st.session_state.selected_operations = []  # Clear previous selections
                st.session_state.operations_loaded = True
                # Create and store a mapping from operation ID to code
                st.session_state.operation_map = {str(op['id_operation']): op['code_operation'] for op in operations}
                # Create and store a mapping from original operation ID to its base time
                st.session_state.original_op_id_to_time_map = {str(op['id_operation']): op['tps'] for op in operations}


        # Display selected game info
        st.success(f"✅ Gamme sélectionnée")
        #print("/n :",game_data)
        #print("/n :", game_options)
        # Create dataframe for display
        game_info = pd.DataFrame([{
            'ID Gamme': game_data['game_id'],
            'Code': game_data['game_code'],
            'Date': game_data['game_date'],
            "Nombre d'opérations": game_data['game_NbrOperations'],
            'Temps Standard': f"{game_data['temps_standard']} mn" if game_data['temps_standard'] else 'N/A'
        }])

        st.dataframe(game_info, width="stretch", hide_index=True)

        return game_data['game_id']  # Return game ID

    return None

def get_operations_selection(game_id):
    """Step 4: Operations selection (MULTI-INSTANCE SAFE)"""

    if not game_id or not st.session_state.all_operations:
        return []

    st.markdown(
        '<h2 class="section-header">4. Sélectionner les Opérations</h2>',
        unsafe_allow_html=True
    )

    operations = st.session_state.all_operations

    # --------------------------------------------------
    # RESET WHEN GAMME CHANGES
    # --------------------------------------------------
    if st.session_state.get("op_game_id") != game_id:
        st.session_state.op_game_id = game_id
        st.session_state.op_selection = {}

    if "op_selection" not in st.session_state:
        st.session_state.op_selection = {}

    # --------------------------------------------------
    # UNIQUE INSTANCE ID (RULE A)
    # Same operation can appear multiple times → DISTINCT
    # --------------------------------------------------
    def instance_id(op):
        return f"{game_id}_{op['id_operation']}_{op['ordre']}"

    # --------------------------------------------------
    # INIT SELECTION STATE
    # --------------------------------------------------
    for op in operations:
        iid = instance_id(op)
        if iid not in st.session_state.op_selection:
            st.session_state.op_selection[iid] = {
                "selected": True,
                "data": op
            }

    st.write(f"**{len(operations)} opération(s) disponibles:**")

    # --------------------------------------------------
    # ACTION BUTTONS
    # --------------------------------0------------------
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("✅ Tout sélectionner", width="stretch"):
            for k in st.session_state.op_selection:
                st.session_state.op_selection[k]["selected"] = True
            st.rerun()

    with col2:
        if st.button("🔄 Inverser la sélection", width="stretch"):
            for k in st.session_state.op_selection:
                st.session_state.op_selection[k]["selected"] ^= True
            st.rerun()

    with col3:
        if st.button("❌ Supprimer non sélectionnées", width="stretch"):
            st.session_state.op_selection = {
                k: v for k, v in st.session_state.op_selection.items()
                if v["selected"]
            }
            st.rerun()

    st.markdown("---")

    # --------------------------------------------------
    # TABLE HEADER
    # --------------------------------------------------
    header_cols = st.columns([0.7, 1, 2, 3, 2, 1.5])
    headers = ["", "Ordre", "Code", "Nom", "Machine", "Temps"]
    for col, h in zip(header_cols, headers):
        col.markdown(f"**{h}**")

    # --------------------------------------------------
    # ROWS
    # --------------------------------------------------
    selected_ops = []

    for iid, entry in st.session_state.op_selection.items():
        op = entry["data"]

        cols = st.columns([0.7, 1, 2, 3, 2, 1.5])

        with cols[0]:
            entry["selected"] = st.checkbox(
                "Sélection",
                value=entry["selected"],
                key=f"op_chk_{iid}",
                label_visibility="collapsed"
            )

        cols[1].write(op.get("ordre", ""))
        cols[2].write(op.get("code_operation", "N/A"))
        cols[3].write(op.get("nom_operation", "N/A"))
        cols[4].write(op.get("machine", "N/A"))
        cols[5].write(f"{op.get('tps', 0)} mn")

        if entry["selected"]:
            selected_ops.append(op)

    # --------------------------------------------------
    # SAVE & SUMMARY
    # --------------------------------------------------
    st.session_state.selected_operations = selected_ops

    st.markdown("---")
    if selected_ops:
        st.success(f"✅ {len(selected_ops)} opération(s) sélectionnée(s)")
    else:
        st.warning("⚠️ Aucune opération sélectionnée")

    return selected_ops
def get_production_parameters():
    """Step 5: Production parameters input"""
    st.markdown('<h2 class="section-header">5. Paramètres de Production</h2>', unsafe_allow_html=True)

    # Advanced settings toggle - FIXED: Don't modify session state directly in widget
    show_advanced = st.checkbox(
        "Afficher les paramètres avancés",
        value=st.session_state.show_advanced,
        key="show_advanced_checkbox"
    )

    # Update session state based on checkbox
    if show_advanced != st.session_state.show_advanced:
        st.session_state.show_advanced = show_advanced

    # Main parameters
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        nbr_op_par_emp = st.number_input(
            "Nombre d'opérations par employé",
            min_value=1,
            max_value=10,
            value=2,
            step=1,
            key="nbr_op_par_emp",
            help="Nombre maximum d'opérations qu'un employé peut effectuer"
        )

    with col2:
        nbr_machine_per_emp = st.number_input(
            "Nombre de machines par employé",
            min_value=1,
            max_value=5,
            value=2,
            step=1,
            key="nbr_machine_per_emp",
            help="Nombre de machines qu'un employé peut opérer simultanément"
        )

    with col3:
        tolerance = st.slider(
            "Tolérance (%)",
            min_value=0.0,
            max_value=50.0,
            value=10.0,
            step=0.5,
            key="tolerance",
            help="Marge d'erreur acceptée dans la production"
        )

    with col4:
        production_souhaite = st.number_input(
            "Production souhaitée",
            min_value=1,
            max_value=10000,
            value=50,
            step=10,
            key="production_souhaite",
            help="Quantité totale à produire"
        )

    # Advanced parameters - only show if advanced is checked
    priorite = 'Moyenne'
    date_limite = datetime.now().date()
    shift = 'Jour'

    if st.session_state.show_advanced:
        st.markdown("#### Paramètres Avancés")

        col1, col2, col3 = st.columns(3)

        with col1:
            priorite = st.select_slider(
                "Priorité",
                options=['Basse', 'Moyenne', 'Haute', 'Urgente'],
                value='Moyenne',
                key="priorite"
            )

        with col2:
            date_limite = st.date_input(
                "Date limite de production",
                value=datetime.now().date(),
                key="date_limite"
            )

        with col3:
            shift = st.selectbox(
                "Shift/Équipe",
                options=['Jour', 'Nuit', 'Mixte'],
                key="shift"
            )

    return {
        'nbr_op_par_emp': nbr_op_par_emp,
        'nbr_machine_per_emp': nbr_machine_per_emp,
        'tolerance': tolerance,
        'production_souhaite': production_souhaite,
        'priorite': priorite,
        'date_limite': date_limite.isoformat() if date_limite else None,
        'shift': shift
    }


def submit_to_api(chaine_data, employee_ids, selected_operations, params):
    """Step 6: Submit data to API"""
    st.markdown('<h2 class="section-header">6. Soumettre au Calcul</h2>', unsafe_allow_html=True)

    # Validation section
    st.markdown("#### Validation des Données")

    validation_passed = True
    validation_errors = []

    if not chaine_data:
        validation_passed = False
        validation_errors.append("❌ Aucune chaîne sélectionnée")

    if not employee_ids:
        validation_passed = False
        validation_errors.append("❌ Aucun employé sélectionné")

    if not st.session_state.selected_game:
        validation_passed = False
        validation_errors.append("❌ Aucune gamme sélectionnée")

    if not selected_operations:
        validation_passed = False
        validation_errors.append("❌ Aucune opération sélectionnée")

    # Display validation results
    if validation_errors:
        for error in validation_errors:
            st.error(error)
    else:
        st.success("✅ Toutes les validations sont passées")

        # Show summary
        with st.expander("📋 Aperçu des données à envoyer", expanded=True):
            col1, col2, col3, col4 = st.columns([1.5, 0.5, 2, 0.5])

            with col1:
                st.metric("Chaîne", chaine_data.get('nom_chaine', 'N/A'))
            with col2:
                st.metric("Employés", len(employee_ids))
            with col3:
                st.metric("Gamme", st.session_state.selected_game_name.split(' - ')[
                    -1] if ' - ' in st.session_state.selected_game_name else st.session_state.selected_game_name)
            with col4:
                st.metric("Opérations", len(selected_operations))

            # Additional details
            st.markdown("**Détails supplémentaires:**")
            st.write(f"- **Production souhaitée:** {params['production_souhaite']}")
            st.write(f"- **Tolérance:** {params['tolerance']}%")
            st.write(f"- **Opérations par employé:** {params['nbr_op_par_emp']}")
            st.write(f"- **Machines par employé:** {params['nbr_machine_per_emp']}")
            if params.get('priorite'):
                st.write(f"- **Priorité:** {params['priorite']}")

    # Submit button
    submit_col1, submit_col2, submit_col3 = st.columns([1, 1, 2])

    with submit_col1:
        if st.button("🚀 Soumettre pour Calcul", type="primary", width="stretch"):
            if not validation_passed:
                st.error("Veuillez corriger les erreurs avant de soumettre")
                return False

            # Prepare operations data
            operations_data = []
            for op in selected_operations:
                operations_data.append({
                    'operation_id': op.get('id_operation'),
                    'code_operation': op.get('code_operation'),
                    'nom_operation': op.get('nom_operation'),
                    'temps_preparation': 0,  # Default value
                    'temps_execution': op.get('tps')
                })

            # Prepare data for API
            #print("**** chaine_data", chaine_data)
            api_data = {
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "version": "1.0",
                    "source": "streamlit_app"
                },
                "chaine": {
                    "chaine_id": chaine_data.get('id_chaine'),
                    "nom_chaine": chaine_data.get('nom_chaine')
                },
                "employes": employee_ids,
                "game": {
                    "game_id": st.session_state.selected_game,
                    "game_name": st.session_state.selected_game_name
                },
                "operations": operations_data,
                "parametres_production": {
                    "nbr_op_par_emp": params['nbr_op_par_emp'],
                    "nbr_machine_per_emp": params['nbr_machine_per_emp'],
                    "tolerance": params['tolerance'],
                    "production_souhaite": params['production_souhaite'],
                    "priorite": params['priorite'],
                    "date_limite": params['date_limite'],
                    "shift": params['shift']
                }
            }

            # Show loading spinner
            with st.spinner("Envoi des données à l'API et calcul en cours..."):
                # Send to API
                result = api_client.send_production_data(api_data)

                # Store result in session state
                st.session_state.api_response = result

                if result['success']:
                    full_api_data = result['data']
                    # Store assignment plan in api_response
                    st.session_state.api_response = {"success": True, "data": full_api_data.get('assignment_plan', {})}
                    # Store predicted rendements separately
                    st.session_state.predicted_rendements_data = full_api_data.get('predicted_rendements', [])
                    st.success("✅ Données soumises avec succès!")
                    st.balloons()
                    return True
                else:
                    st.error(f"❌ Échec de soumission: {result['message']}")
                    return False

    with submit_col2:
        if st.button("🔄 Réinitialiser", width="stretch"):
            # Clear only selection state, keep other settings
            clear_keys = ['selected_employees', 'selected_employee_names',
                          'selected_game', 'selected_game_name',
                          'selected_operations', 'all_operations',
                          'operations_loaded', 'api_response', 'predicted_rendements_data',
                          'original_op_id_to_time_map'] # Added new key
            for key in clear_keys:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    with submit_col3:
        if st.button("🗑️ Tout Effacer", width="stretch"):
            # Clear all session state for new configuration
            clear_keys = ['selected_chaine', 'selected_employees',
                          'selected_employee_names', 'selected_game',
                          'selected_game_name', 'selected_operations',
                          'all_operations', 'operations_loaded', 'api_response', 'predicted_rendements_data',
                          'original_op_id_to_time_map'] # Added new key
            for key in clear_keys:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    return False


def display_api_results():
    """Display API response results"""
    if 'api_response' in st.session_state and st.session_state.api_response:
        st.markdown('<h2 class="section-header">📊 Résultats du Calcul</h2>', unsafe_allow_html=True)

        result_data = st.session_state.api_response

        if result_data.get('success'):
            data = result_data.get('data', {}) # This now holds the assignment_plan
            metrics = data.get('metrics', {})

            # --- 1. KPIs ---
            st.markdown("### Indicateurs de Performance")
            col1, col2, col3 = st.columns(3)
            col1.metric(
                "Makespan (Temps Total)",
                f"{metrics.get('makespan', 0):.2f} mn",
                help="Le Makespan représente Le temps d'inactivité (ou temps perdu) désigne les périodes pendant lesquelles les ressources (employés ou machines) ne sont pas utilisées."
            )
            col2.metric("Employés Utilisés", metrics.get('used_employees', 0))
            col3.metric(
                "Indice d'Équilibre",
                f"{metrics.get('balance_index', 0) * 100:.1f}%",
                help="L'indice d'équilibre mesure la répartition de la charge de travail entre les employés. Un pourcentage plus élevé (proche de 100%) indique une meilleure répartition, tandis qu'un pourcentage plus faible signifie que certains employés sont beaucoup plus occupés que d'autres."
            )

            # --- 2. Create and Display the Pivoted Table ---
            st.markdown("### Plan d'Affectation")
            assignments = data.get('assignments', [])
            if assignments:
                assign_df = pd.DataFrame(assignments)
                pivot_df = assign_df.pivot(index='idOp', columns='idEmp', values='time')

                # --- 3. Sort for Diagonal View ---
                op_ordre_map = {str(op['id_operation']): op['ordre'] for op in st.session_state.all_operations}

                def get_op_sort_key(op_id):
                    base_id = str(op_id).split('_')[0]
                    main_order = op_ordre_map.get(base_id, float('inf'))
                    sub_order = int(str(op_id).split('_')[1]) if '_' in str(op_id) else 0
                    return (main_order, sub_order)

                sorted_op_index = sorted(pivot_df.index, key=get_op_sort_key)

                temp_df = pivot_df.reindex(index=sorted_op_index)
                emp_first_op_pos = {}
                for emp in temp_df.columns:
                    first_valid_idx = temp_df[emp].first_valid_index()
                    if first_valid_idx:
                        try:
                            emp_first_op_pos[emp] = sorted_op_index.index(first_valid_idx)
                        except ValueError:
                            emp_first_op_pos[emp] = float('inf')
                    else:
                        emp_first_op_pos[emp] = float('inf')
                
                sorted_emp_columns = sorted(temp_df.columns, key=lambda emp: emp_first_op_pos[emp])

                final_pivot_df = pivot_df.reindex(index=sorted_op_index, columns=sorted_emp_columns)

                # Multiply values by 100
                final_pivot_df = final_pivot_df * 100

                # --- 4. Map IDs to Names/Codes for Display ---
                emp_map = st.session_state.get('employee_map', {})
                op_map = st.session_state.get('operation_map', {})
                original_op_time_map = st.session_state.get('original_op_id_to_time_map', {})


                def map_op_id_to_code_and_time(op_id):
                    # op_id here is the unique identifier from the solver output, e.g., "574", "574_1"
                    base_original_op_id = str(op_id).split('_')[0] # e.g., "574" from "574_1"
                    # Get the code_operation for the original operation ID
                    code = op_map.get(base_original_op_id, f"Op({base_original_op_id})") # Fallback to "Op(574)"
                    # Get the base time for the original operation ID
                    base_time = original_op_time_map.get(base_original_op_id, "N/A")
                    
                    # Combine the code with the full unique solver ID and base time
                    return f"{code} ({op_id}) [{base_time} mn]"

                final_pivot_df.index = final_pivot_df.index.map(map_op_id_to_code_and_time)
                final_pivot_df.columns = final_pivot_df.columns.map(lambda x: emp_map.get(str(x), str(x)))

                # --- 5. Style and Display the Table ---
                st.dataframe(
                    final_pivot_df.style
                    .background_gradient(cmap='viridis_r', axis=None, low=0.1, high=1)
                    .format("{:.2f}", na_rep="")
                    .highlight_null('rgba(255, 255, 255, 0.05)')
                )

            else:
                st.info("Aucune donnée d'affectation n'a été retournée par le solveur.")

            # --- 6. Display Predicted Rendements ---
            st.markdown("### Rendements Prédits")
            predicted_rendements = st.session_state.get('predicted_rendements_data', [])

            if predicted_rendements:
                rendement_df = pd.DataFrame(predicted_rendements)
                
                # Map IDs to Names/Codes for readability
                emp_map = st.session_state.get('employee_map', {})
                # Create a temporary map for original operation IDs to their codes
                # This is needed because predicted_rendements uses original idOp, not solver's expanded idOp
                original_op_id_to_code_map = {str(op['id_operation']): op['code_operation'] for op in st.session_state.all_operations}

                rendement_df['idEmp'] = rendement_df['idEmp'].astype(str).map(lambda x: emp_map.get(x, x))
                rendement_df['idOp'] = rendement_df['idOp'].astype(str).map(lambda x: original_op_id_to_code_map.get(x, x))
                
                rendement_df.rename(columns={
                    'idEmp': 'Employé',
                    'idOp': 'Opération',
                    'rendement': 'Rendement Prédit'
                }, inplace=True)

                st.dataframe(rendement_df, hide_index=True)

                # Download button for Rendements
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                    rendement_df.to_excel(writer, sheet_name='Rendements', index=False)
                excel_buffer.seek(0)

                st.download_button(
                    label="📥 Télécharger les Rendements (XLSX)",
                    data=excel_buffer,
                    file_name=f"rendements_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.info("Aucune donnée de rendement prédit n'a été retournée par l'API.")

            # --- Keep Download Buttons ---
            st.markdown("### Téléchargement des Résultats")
            col1, col2 = st.columns(2)

            with col1:
                if st.button("📥 Télécharger les Affectations (CSV)", width="stretch"):
                    csv_data = pd.DataFrame(assignments).to_csv(index=False)
                    st.download_button(
                        label="Cliquez pour télécharger",
                        data=csv_data,
                        file_name=f"assignments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                    )

            with col2:
                if st.button("📄 Télécharger le Résultat Complet (JSON)", width="stretch"):
                    json_data = json.dumps(data, indent=2)
                    st.download_button(
                        label="Cliquez pour télécharger",
                        data=json_data,
                        file_name=f"full_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                    )
        else:
            st.error(f"Erreur de l'API: {result_data.get('message', 'Détail non disponible')}")


def main():
    """Main application flow"""
    initialize_session_state()
    display_header()

    # Create sidebar for navigation
    with st.sidebar:
        st.markdown("### Navigation")
        page = st.radio(
            "Sélectionner une page:",
            ["🧭 Configuration", "📊 Résultats", "⚙️ Paramètres"]
        )

        st.markdown("---")
        st.markdown("### Informations")
        st.info(f"Base de données: {config.DB_NAME}")
        st.info(f"API: {config.API_BASE_URL}")

        st.markdown("---")
        st.markdown("### Sélections actuelles")

        if st.session_state.selected_chaine:
            chaine_name = st.session_state.selected_chaine.get('nom_chaine', 'N/A')
            st.info(f"**Chaîne:** {chaine_name}")

        if st.session_state.selected_employees:
            if st.session_state.selected_employee_names and st.session_state.selected_employee_names[0].startswith(
                    "✅ Sélectionner tous"):
                st.info(f"**Employés:** Tous ({len(st.session_state.selected_employees)})")
            else:
                st.info(f"**Employés:** {len(st.session_state.selected_employees)} sélectionnés")

        if st.session_state.selected_game_name:
            st.info(
                f"**Gamme:** {st.session_state.selected_game_name.split(' - ')[-1] if ' - ' in st.session_state.selected_game_name else st.session_state.selected_game_name}")

        if st.session_state.selected_operations:
            st.info(f"**Opérations:** {len(st.session_state.selected_operations)} sélectionnées")

        st.markdown("---")
        if st.button("🔄 Rafraîchir l'Application"):
            st.rerun()

    if page == "🧭 Configuration":
        # Step 1: Chaine selection
        chaine_data = get_chaine_selection()

        if chaine_data:
            # Step 2: Employee selection
            employee_ids = get_employee_selection(chaine_data['id_chaine'])

            # Step 3: Game selection (SINGLE SELECT - NO DEFAULT)
            game_id = get_game_selection()

            # Step 3b: Operations selection (only if game is selected)
            if game_id:
                selected_operations = get_operations_selection(game_id)
            else:
                selected_operations = []

            # Step 4: Production parameters
            params = get_production_parameters()

            # Step 5: Submit to API
            submit_to_api(chaine_data, employee_ids, selected_operations, params)

    elif page == "📊 Résultats":
        # Display API results
        display_api_results()

    elif page == "⚙️ Paramètres":
        st.markdown('<h2 class="section-header">Paramètres de l\'Application</h2>', unsafe_allow_html=True)

        with st.expander("Configuration Base de Données"):
            st.write(f"**Hôte:** {config.DB_HOST}")
            st.write(f"**Port:** {config.DB_PORT}")
            st.write(f"**Base de données:** {config.DB_NAME}")
            st.write(f"**Utilisateur:** {config.DB_USER}")

        with st.expander("Configuration API"):
            st.write(f"**URL de base:** {config.API_BASE_URL}")
            st.write(f"**Endpoint:** {config.API_ENDPOINT}")
            st.write(f"**Timeout:** {config.API_TIMEOUT}s")

        if st.button("Tester la connexion base de données"):
            if db.test_connection():
                st.success("✅ Connexion réussie")
            else:
                st.error("❌ Échec de connexion")


if __name__ == "__main__":
    main()