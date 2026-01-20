import streamlit as st
import pandas as pd
from datetime import datetime
import json
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
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables"""
    defaults = {
        'selected_chaine': None,
        'selected_employees': [],
        'selected_employee_names': [],
        'selected_games': [],
        'selected_game_names': [],
        'operations': [],
        'api_response': None,
        'show_advanced': False,
        'db_connected': False
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
        st.success("✅ Connected to MySQL database")
    else:
        st.error("❌ Database connection failed. Please check your configuration.")
        st.stop()

    st.markdown("---")


def get_chaine_selection():
    """Step 1: Chaine selection"""
    st.markdown('<h2 class="section-header">1. Sélectionner la Chaîne de Production</h2>', unsafe_allow_html=True)

    # Add refresh button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Rafraîchir la liste", use_container_width=True):
            st.rerun()

    with col1:
        chaines = db.get_chaine_list()

        if not chaines:
            st.warning("Aucune chaîne trouvée dans la base de données")
            return None

        # Format options for display
        chaine_options = {f"{c.get('chaine_id', '')} - {c.get('chaine_name', '')}": c for c in chaines}

        selected_option = st.selectbox(
            "Choisir une chaîne:",
            options=list(chaine_options.keys()),
            index=0 if not st.session_state.selected_chaine else None,
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
    """Step 2: Employee selection"""
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

    # Multi-select for employees
    selected_display = st.multiselect(
        "Sélectionner un ou plusieurs employés:",
        options=list(employee_options.keys()),
        default=st.session_state.selected_employee_names,
        key="employee_multiselect",
        help="Sélectionnez les employés qui participeront à la production"
    )

    # Get selected employee IDs and names
    selected_ids = []
    selected_names = []
    for display in selected_display:
        emp_data = employee_options[display]
        selected_ids.append(emp_data['id'])
        selected_names.append(display)

    st.session_state.selected_employees = selected_ids
    st.session_state.selected_employee_names = selected_names

    # Display selected employees
    if selected_ids:
        st.success(f"✅ {len(selected_ids)} employé(s) sélectionné(s)")

        # Show selected employees in a table
        selected_data = []
        for display in selected_display:
            emp_data = employee_options[display]
            selected_data.append({
                'ID': emp_data['id'],
                'Nom': emp_data['name'],
                'Code': emp_data['code'],
                'Poste': emp_data['poste']
            })

        df_employees = pd.DataFrame(selected_data)
        st.dataframe(df_employees, use_container_width=True, hide_index=True)

    return selected_ids


def get_game_selection():
    """Step 3: Game and operation selection"""
    st.markdown('<h2 class="section-header">3. Sélectionner Gamme</h2>', unsafe_allow_html=True)

    with st.spinner("Chargement des gammes..."):
        games = db.get_games()

    if not games:
        st.warning("Aucun gamme trouvee")
        return []

    # Format game options
    game_options = {}
    for game in games:
        game_id = game.get('id_game')
        game_code = game.get('code_game', 'N/A')
        game_date = game.get('date', 'N/A')
        game_NbrOperations = game.get('NbrOperations', 0)

        display_text = f"{game_id}: {game_date} - {game_code}: [{game_NbrOperations}]"
        game_options[display_text] = {
            'game_id': game_id,
            'game_date': game_date,
            'game_code': game_code,
            'game_NbrOperations': game_NbrOperations,
            'temps_standard': game.get('temps_standard')
        }

    # Multi-select for games
    selected_display = st.multiselect(
        "Sélectionner les jeux (opérations):",
        options=list(game_options.keys()),
        default=st.session_state.selected_game_names,
        key="game_multiselect",
        help="Sélectionnez les jeux/opérations à produire"
    )

    # Get operations data
    operations = []
    selected_game_names = []

    for display in selected_display:
        game_data = game_options[display]
        operations.append({
            'game_id': game_data['game_id'],
            'game_code': game_data['game_code'],
            'game_date': game_data['game_date'],
            'game_NbrOperations': game_data['game_NbrOperations'],
            'temps_standard': game_data['temps_standard']
        })
        selected_game_names.append(display)

    # Display selected operations
    if operations:
        st.success(f"✅ {len(operations)} opération(s) sélectionnée(s)")

        # Create dataframe for display
        operations_df = pd.DataFrame(operations)

        # Format columns
        display_cols = ['game_code', 'game_name', 'operation_code', 'temps_standard', 'complexite']
        display_df = operations_df[display_cols].copy()
        display_df.columns = ['Code Jeu', 'Nom Jeu', 'Code Opération', 'Temps Standard', 'Complexité']

        st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.session_state.selected_games = [game_options[d]['game_id'] for d in selected_display]
    st.session_state.selected_game_names = selected_game_names
    st.session_state.operations = operations

    return operations


def get_production_parameters():
    """Step 4: Production parameters input"""
    st.markdown('<h2 class="section-header">4. Paramètres de Production</h2>', unsafe_allow_html=True)

    # Advanced settings toggle
    st.session_state.show_advanced = st.checkbox(
        "Afficher les paramètres avancés",
        value=st.session_state.show_advanced,
        key="show_advanced"
    )

    # Main parameters
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        nbr_op_par_emp = st.number_input(
            "Nombre d'opérations par employé",
            min_value=1,
            max_value=50,
            value=1,
            step=1,
            key="nbr_op_par_emp",
            help="Nombre maximum d'opérations qu'un employé peut effectuer"
        )

    with col2:
        nbr_machine_per_emp = st.number_input(
            "Nombre de machines par employé",
            min_value=1,
            max_value=20,
            value=1,
            step=1,
            key="nbr_machine_per_emp",
            help="Nombre de machines qu'un employé peut opérer simultanément"
        )

    with col3:
        tolerance = st.slider(
            "Tolérance (%)",
            min_value=0.0,
            max_value=50.0,
            value=5.0,
            step=0.5,
            key="tolerance",
            help="Marge d'erreur acceptée dans la production"
        )

    with col4:
        production_souhaite = st.number_input(
            "Production souhaitée",
            min_value=1,
            max_value=100000,
            value=100,
            step=100,
            key="production_souhaite",
            help="Quantité totale à produire"
        )

    # Advanced parameters
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
        'priorite': priorite if st.session_state.show_advanced else 'Moyenne',
        'date_limite': date_limite.isoformat() if st.session_state.show_advanced else None,
        'shift': shift if st.session_state.show_advanced else 'Jour'
    }


def submit_to_api(chaine_data, employee_ids, operations, params):
    """Step 5: Submit data to API"""
    st.markdown('<h2 class="section-header">5. Soumettre au Calcul</h2>', unsafe_allow_html=True)

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

    if not operations:
        validation_passed = False
        validation_errors.append("❌ Aucune opération sélectionnée")

    # Display validation results
    if validation_errors:
        for error in validation_errors:
            st.error(error)
    else:
        st.success("✅ Toutes les validations sont passées")

        # Show summary
        with st.expander("📋 Aperçu des données à envoyer"):
            summary_data = {
                "Chaîne": chaine_data.get('nom_chaine', 'N/A'),
                "Nombre d'employés": len(employee_ids),
                "Nombre d'opérations": len(operations),
                "Production souhaitée": params['production_souhaite'],
                "Tolérance": f"{params['tolerance']}%"
            }

            for key, value in summary_data.items():
                st.write(f"**{key}:** {value}")

    # Submit button
    submit_col1, submit_col2 = st.columns([1, 3])

    with submit_col1:
        if st.button("🚀 Soumettre pour Calcul", type="primary", use_container_width=True):
            if not validation_passed:
                st.error("Veuillez corriger les erreurs avant de soumettre")
                return False

            # Prepare data for API
            api_data = {
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "version": "1.0",
                    "source": "streamlit_app"
                },
                "chaine": {
                    "id_chaine": chaine_data.get('id_chaine'),
                    "nom_chaine": chaine_data.get('nom_chaine')
                },
                "employes": employee_ids,
                "operations": operations,
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
                    st.success("✅ Données soumises avec succès!")
                    return True
                else:
                    st.error(f"❌ Échec de soumission: {result['message']}")
                    return False

    with submit_col2:
        if st.button("🔄 Nouvelle Configuration", use_container_width=True):
            # Clear session state for new configuration
            clear_keys = ['selected_chaine', 'selected_employees',
                          'selected_employee_names', 'selected_games',
                          'selected_game_names', 'operations', 'api_response']
            for key in clear_keys:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    return False


def display_api_results():
    """Display API response results"""
    if st.session_state.api_response and st.session_state.api_response['success']:
        st.markdown('<h2 class="section-header">📊 Résultats du Calcul</h2>', unsafe_allow_html=True)

        result_data = st.session_state.api_response['data']

        # Display metrics
        st.markdown("### Indicateurs de Performance")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Efficacité", f"{result_data.get('efficacite', 0):.1f}%")
        with col2:
            st.metric("Production Réelle", result_data.get('production_reelle', 0))
        with col3:
            st.metric("Temps Total", f"{result_data.get('temps_total', 0):.1f} h")
        with col4:
            st.metric("Coût Estimé", f"${result_data.get('cout_estime', 0):,.2f}")

        # Display in expandable sections
        with st.expander("📋 Plan de Production Détaillé", expanded=True):
            if 'plan_production' in result_data:
                plan_df = pd.DataFrame(result_data['plan_production'])
                st.dataframe(plan_df, use_container_width=True)

        with st.expander("👥 Allocation des Employés"):
            if 'allocation_employes' in result_data:
                alloc_df = pd.DataFrame(result_data['allocation_employes'])
                st.dataframe(alloc_df, use_container_width=True)

        with st.expander("⚙️ Planification des Machines"):
            if 'planification_machines' in result_data:
                machine_df = pd.DataFrame(result_data['planification_machines'])
                st.dataframe(machine_df, use_container_width=True)

        with st.expander("📈 Analyse des Résultats"):
            if 'analyse' in result_data:
                st.json(result_data['analyse'])

        # Download buttons
        st.markdown("### Téléchargement des Résultats")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📥 Télécharger CSV", use_container_width=True):
                # Convert to CSV
                csv_data = pd.DataFrame([result_data]).to_csv(index=False)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label="Cliquez pour télécharger",
                    data=csv_data,
                    file_name=f"production_results_{timestamp}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

        with col2:
            if st.button("📄 Télécharger JSON", use_container_width=True):
                json_data = json.dumps(result_data, indent=2, ensure_ascii=False)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label="Cliquez pour télécharger",
                    data=json_data,
                    file_name=f"production_results_{timestamp}.json",
                    mime="application/json",
                    use_container_width=True
                )

        with col3:
            if st.button("🖨️ Générer Rapport PDF", use_container_width=True):
                st.info("Fonctionnalité PDF en développement")

        # History and new calculation
        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("📜 Voir Historique", use_container_width=True):
                # Fetch and display history
                history = db.get_production_history(
                    chaine_data.get('chaine_id') if 'chaine_data' in locals() else None
                )
                if history:
                    history_df = pd.DataFrame(history)
                    st.dataframe(history_df, use_container_width=True)
                else:
                    st.info("Aucun historique disponible")

        with col2:
            if st.button("🔄 Nouveau Calcul", type="primary", use_container_width=True):
                # Clear session state
                for key in ['selected_chaine', 'selected_employees',
                            'selected_employee_names', 'selected_games',
                            'selected_game_names', 'operations', 'api_response']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()


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
        if st.button("🔄 Rafraîchir l'Application"):
            st.rerun()

    if page == "🧭 Configuration":
        # Step 1: Chaine selection
        chaine_data = get_chaine_selection()

        if chaine_data:
            # Step 2: Employee selection
            employee_ids = get_employee_selection(chaine_data['chaine_id'])

            # Step 3: Game selection
            operations = get_game_selection()

            # Step 4: Production parameters
            params = get_production_parameters()

            # Step 5: Submit to API
            submit_to_api(chaine_data, employee_ids, operations, params)

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