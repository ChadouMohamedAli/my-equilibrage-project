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
        'selected_game': None,  # Changed to single game
        'selected_game_name': None,
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

        # Format options for display - FIXED: Use correct field names
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

    # Add "Select All" option at the beginning
    all_option_text = "✅ Sélectionner tous les employés"
    employee_options_with_all = {all_option_text: {'id': 'ALL', 'is_all': True}}
    employee_options_with_all.update(employee_options)

    # Filter saved selections to only include valid options
    valid_saved_selections = []
    for saved_option in st.session_state.selected_employee_names:
        if saved_option in employee_options_with_all:
            valid_saved_selections.append(saved_option)

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
        selected_display = [all_option_text] + list(employee_options.keys())
        selected_names = selected_display
        selected_ids = [emp['id'] for emp in employee_options.values()]
    else:
        # Get selected employee IDs and names
        for display in selected_display:
            emp_data = employee_options_with_all[display]
            if display != all_option_text:  # Skip the "Select All" option for IDs
                selected_ids.append(emp_data['id'])
                selected_names.append(display)

    st.session_state.selected_employees = selected_ids
    st.session_state.selected_employee_names = selected_names

    # Display selected employees
    if selected_ids:
        if all_option_text in selected_display:
            st.success(f"✅ Tous les employés sont sélectionnés ({len(selected_ids)} employés)")
        else:
            st.success(f"✅ {len(selected_ids)} employé(s) sélectionné(s)")

        # Show selected employees in a table (limit to 10 for display)
        if len(selected_display) > 0 and selected_display[0] != all_option_text:
            selected_data = []
            for display in selected_display[:10]:  # Show first 10 only
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
                st.dataframe(df_employees, use_container_width=True, hide_index=True)

                if len(selected_display) > 10:
                    st.info(f"Et {len(selected_display) - 10} autres employés...")

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

    # Determine default selection
    default_option = None
    if st.session_state.selected_game_name and st.session_state.selected_game_name in game_options:
        default_option = st.session_state.selected_game_name

    # SINGLE SELECT for game (not multiselect)
    selected_display = st.selectbox(
        "Sélectionner une gamme:",
        options=list(game_options.keys()),
        index=0 if not default_option else list(game_options.keys()).index(default_option),
        key="game_select",
        help="Sélectionnez une seule gamme à produire"
    )

    # Get selected game data
    if selected_display:
        game_data = game_options[selected_display]
        operation = {
            'game_id': game_data['game_id'],
            'game_code': game_data['game_code'],
            'game_date': game_data['game_date'],
            'game_NbrOperations': game_data['game_NbrOperations'],
            'temps_standard': game_data['temps_standard']
        }

        st.session_state.selected_game = game_data['game_id']
        st.session_state.selected_game_name = selected_display
        st.session_state.operations = [operation]  # Single operation

        # Display selected game info
        st.success(f"✅ Gamme sélectionnée")

        # Create dataframe for display
        game_info = pd.DataFrame([{
            'ID Gamme': operation['game_id'],
            'Code': operation['game_code'],
            'Date': operation['game_date'],
            "Nombre d'opérations": operation['game_NbrOperations'],
            'Temps Standard': f"{operation['temps_standard']}h" if operation['temps_standard'] else 'N/A'
        }])

        st.dataframe(game_info, use_container_width=True, hide_index=True)

        return [operation]  # Return as list with single item

    return []


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

    # Set default values if advanced parameters not shown
    priorite = st.session_state.get('priorite', 'Moyenne')
    date_limite = st.session_state.get('date_limite', datetime.now().date())
    shift = st.session_state.get('shift', 'Jour')

    return {
        'nbr_op_par_emp': nbr_op_par_emp,
        'nbr_machine_per_emp': nbr_machine_per_emp,
        'tolerance': tolerance,
        'production_souhaite': production_souhaite,
        'priorite': priorite,
        'date_limite': date_limite.isoformat() if date_limite else None,
        'shift': shift
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
        validation_errors.append("❌ Aucune gamme sélectionnée")

    # Display validation results
    if validation_errors:
        for error in validation_errors:
            st.error(error)
    else:
        st.success("✅ Toutes les validations sont passées")

        # Show summary
        with st.expander("📋 Aperçu des données à envoyer", expanded=True):
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Chaîne", chaine_data.get('nom_chaine', 'N/A'))
            with col2:
                st.metric("Employés", len(employee_ids))
            with col3:
                st.metric("Gamme", operations[0]['game_code'] if operations else 'N/A')
            with col4:
                st.metric("Production", params['production_souhaite'])

            # Additional details
            st.markdown("**Détails supplémentaires:**")
            st.write(f"- **Tolérance:** {params['tolerance']}%")
            st.write(f"- **Opérations par employé:** {params['nbr_op_par_emp']}")
            st.write(f"- **Machines par employé:** {params['nbr_machine_per_emp']}")
            if params.get('priorite'):
                st.write(f"- **Priorité:** {params['priorite']}")

    # Submit button
    submit_col1, submit_col2, submit_col3 = st.columns([1, 1, 2])

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
                    st.balloons()
                    return True
                else:
                    st.error(f"❌ Échec de soumission: {result['message']}")
                    return False

    with submit_col2:
        if st.button("🔄 Réinitialiser", use_container_width=True):
            # Clear only selection state, keep other settings
            clear_keys = ['selected_employees', 'selected_employee_names',
                          'selected_game', 'selected_game_name', 'operations']
            for key in clear_keys:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    with submit_col3:
        if st.button("🗑️ Tout Effacer", use_container_width=True):
            # Clear all session state for new configuration
            clear_keys = ['selected_chaine', 'selected_employees',
                          'selected_employee_names', 'selected_game',
                          'selected_game_name', 'operations', 'api_response']
            for key in clear_keys:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    return False


def display_api_results():
    """Display API response results"""
    if st.session_state.api_response:
        st.markdown('<h2 class="section-header">📊 Résultats du Calcul</h2>', unsafe_allow_html=True)

        result_data = st.session_state.api_response

        if result_data['success']:
            data = result_data.get('data', {})

            # Display metrics
            st.markdown("### Indicateurs de Performance")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Efficacité", f"{data.get('efficacite', 0):.1f}%")
            with col2:
                st.metric("Production Réelle", data.get('production_reelle', 0))
            with col3:
                st.metric("Temps Total", f"{data.get('temps_total', 0):.1f} h")
            with col4:
                st.metric("Coût Estimé", f"${data.get('cout_estime', 0):,.2f}")

            # Display results in tabs
            tab1, tab2, tab3 = st.tabs(["Plan de Production", "Allocation", "Analyse"])

            with tab1:
                if 'plan_production' in data:
                    plan_df = pd.DataFrame(data['plan_production'])
                    st.dataframe(plan_df, use_container_width=True)
                else:
                    st.info("Aucun plan de production disponible")

            with tab2:
                if 'allocation_employes' in data:
                    alloc_df = pd.DataFrame(data['allocation_employes'])
                    st.dataframe(alloc_df, use_container_width=True)
                else:
                    st.info("Aucune allocation d'employés disponible")

            with tab3:
                if 'analyse' in data:
                    st.json(data['analyse'])
                else:
                    st.info("Aucune analyse disponible")

            # Download buttons
            st.markdown("### Téléchargement des Résultats")
            col1, col2 = st.columns(2)

            with col1:
                if st.button("📥 Télécharger CSV", use_container_width=True):
                    try:
                        if 'plan_production' in data:
                            csv_data = pd.DataFrame(data['plan_production']).to_csv(index=False)
                        else:
                            csv_data = pd.DataFrame([data]).to_csv(index=False)

                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        st.download_button(
                            label="Cliquez pour télécharger",
                            data=csv_data,
                            file_name=f"production_results_{timestamp}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"Erreur lors de la création du CSV: {e}")

            with col2:
                if st.button("📄 Télécharger JSON", use_container_width=True):
                    json_data = json.dumps(data, indent=2, ensure_ascii=False)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    st.download_button(
                        label="Cliquez pour télécharger",
                        data=json_data,
                        file_name=f"production_results_{timestamp}.json",
                        mime="application/json",
                        use_container_width=True
                    )

            # New calculation button
            st.markdown("---")
            if st.button("🔄 Nouveau Calcul", type="primary", use_container_width=True):
                # Clear session state
                for key in ['selected_chaine', 'selected_employees',
                            'selected_employee_names', 'selected_game',
                            'selected_game_name', 'operations', 'api_response']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
        else:
            st.error(f"❌ Erreur: {result_data['message']}")

            # Show retry button
            if st.button("🔄 Réessayer", type="secondary"):
                # Keep the data but clear the response
                if 'api_response' in st.session_state:
                    del st.session_state['api_response']
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
        st.markdown("### Sélections actuelles")

        if st.session_state.selected_chaine:
            chaine_name = st.session_state.selected_chaine.get('nom_chaine', 'N/A')
            st.info(f"**Chaîne:** {chaine_name}")

        if st.session_state.selected_employees:
            if len(st.session_state.selected_employees) > 10:
                st.info(f"**Employés:** Tous ({len(st.session_state.selected_employees)})")
            else:
                st.info(f"**Employés:** {len(st.session_state.selected_employees)} sélectionnés")

        if st.session_state.selected_game_name:
            st.info(
                f"**Gamme:** {st.session_state.selected_game_name.split(' - ')[-1] if ' - ' in st.session_state.selected_game_name else st.session_state.selected_game_name}")

        st.markdown("---")
        if st.button("🔄 Rafraîchir l'Application"):
            st.rerun()

    if page == "🧭 Configuration":
        # Step 1: Chaine selection
        chaine_data = get_chaine_selection()

        if chaine_data:
            # Step 2: Employee selection
            employee_ids = get_employee_selection(chaine_data['id_chaine'])

            # Step 3: Game selection (SINGLE SELECT)
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