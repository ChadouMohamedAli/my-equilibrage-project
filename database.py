import pandas as pd
import mysql.connector
from mysql.connector import Error
from mysql.connector.pooling import MySQLConnectionPool
from config import config
import streamlit as st


class MySQLDatabase:
    def __init__(self):
        self.connection_pool = None
        self._init_pool()

    def _init_pool(self):
        """Initialize MySQL connection pool"""
        try:
            self.connection_pool = MySQLConnectionPool(
                pool_name="mypool",
                pool_size=5,
                pool_reset_session=True,
                host=config.DB_HOST,
                port=config.DB_PORT,
                database=config.DB_NAME,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                charset=config.DB_CHARSET,
                autocommit=True
            )
            #st.success("✅ Database connection pool created")
            st.toast(f"✅ Database connection pool created", duration=10)
            return True
        except Error as e:
            st.error(f"Failed to create connection pool: {e}")
            # Try without pool as fallback
            return False

    def get_connection(self):
        """Get connection from pool or create new one"""
        try:
            if self.connection_pool:
                connection = self.connection_pool.get_connection()
                if connection.is_connected():
                    return connection
                else:
                    st.warning("Connection from pool was closed, creating new connection")

            # Fallback to direct connection
            connection = mysql.connector.connect(
                host=config.DB_HOST,
                port=config.DB_PORT,
                database=config.DB_NAME,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                charset=config.DB_CHARSET
            )

            if connection.is_connected():
                st.info("📡 Created new database connection")
                return connection
            else:
                return None

        except Error as e:
            st.error(f"Failed to get database connection: {e}")
            return None

    def get_chaine_list(self):
        """Get list of chaines from database"""
        query = """
        SELECT DISTINCT IDChaineMontage as chaine_id, ChaineMontage as chaine_name
        FROM chainemontage
        WHERE etat = 1
        ORDER BY ChaineMontage;
        """
        return self._execute_query(query)

    def get_employees_by_chaine(self, chaine_id):
        """Get employees for a specific chaine"""
        query = """
        SELECT idemploye as id_employe, nom as nom_employe, Matricule as code_employe, Specialite as poste
        FROM employe 
        WHERE IDChaineMontage = %s 
        AND etat = 1
        ORDER BY nom
        """
        return self._execute_query(query, (chaine_id,))

    def get_games(self):
        query = f"""
        SELECT DISTINCT 
            g.idGamme as id_game, 
            g.gamme as code_game, 
            g.date as date,
            g.NbrOperations,
            g.TpsGamme as temps_standard
        FROM gamme g
        where g.etat = 1
        ORDER BY g.date, g.gamme;
        """
        return self._execute_query(query)

    def get_operations_by_games(self, game_ids):
        """Get operations for selected games"""
        if not game_ids:
            return []

        placeholders = ','.join(['%s'] * len(game_ids))
        query = f"""
        SELECT 
            op.idoperation,
            op.idoperation as id_operation,
            o.code as code_operation,
            o.Operation as nom_operation,
            op.idMachine,
            m.machine,
            op.temps as tps,
            op.ordre as ordre
        FROM op_gamme op
        left join operation o on o.idoperation = op.idoperation
        left join machine m on m.idmachine = op.idmachine
        WHERE op.idgamme IN ({placeholders});
        """
        return self._execute_query(query, tuple(game_ids))


    def _execute_query(self, query, params=None):
        """Execute query and return results as list of dictionaries"""
        connection = None
        cursor = None
        try:
            connection = self.get_connection()
            if not connection:
                st.error("No database connection available")
                return []

            # Create cursor with dictionary=True
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, params or ())

            # Fetch all rows as dictionaries
            results = cursor.fetchall()

            # Convert all values to string for safety
            processed_results = []
            for row in results:
                processed_row = {}
                for key, value in row.items():
                    # Handle None values
                    if value is None:
                        processed_row[key] = None
                    else:
                        # Convert to string, but keep numeric values as is for IDs
                        if isinstance(value, (int, float)):
                            processed_row[key] = value
                        else:
                            processed_row[key] = str(value)
                processed_results.append(processed_row)

            return processed_results

        except Error as e:
            st.error(f"Database query error: {e}")
            st.error(f"Query: {query}")
            if params:
                st.error(f"Params: {params}")
            return []
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    def test_connection(self):
        """Test database connection"""
        try:
            connection = self.get_connection()
            if connection and connection.is_connected():
                cursor = connection.cursor()
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
                cursor.close()
                connection.close()

                if result:
                    return True
        except Error as e:
            st.error(f"Connection test failed: {e}")
            return False
        return False


# Create a singleton instance
db = MySQLDatabase()