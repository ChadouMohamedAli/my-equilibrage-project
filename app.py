import streamlit as st
import pandas as pd
import pickle
import os
from core.models import load_model, predict
from core.preprocessing import preprocess_data

# Page config
st.set_page_config(
    page_title="ML Predictor",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title
st.title("📊 Your Machine Learning App")
st.markdown("---")

# Sidebar for navigation/configuration
with st.sidebar:
    st.header("⚙️ Settings")
    model_choice = st.selectbox(
        "Select Model",
        ["Model 1", "Model 2", "Model 3"]
    )

    uploaded_file = st.file_uploader(
        "Upload CSV File",
        type=["csv"],
        help="Upload your data file for prediction"
    )

# Main content area in tabs
tab1, tab2, tab3 = st.tabs(["📈 Predict", "📁 Data", "⚡ API"])

with tab1:
    st.header("Make Predictions")

    if uploaded_file is not None:
        # Load and display data
        df = pd.read_csv(uploaded_file)
        st.write("### Uploaded Data Preview")
        st.dataframe(df.head())

        # Preprocess
        processed_df = preprocess_data(df)

        # Make predictions
        if st.button("🚀 Run Predictions", type="primary"):
            with st.spinner("Making predictions..."):
                model = load_model(model_choice)
                predictions = predict(model, processed_df)

                # Display results
                st.success("Predictions Complete!")
                st.write("### Results")
                st.dataframe(predictions)

                # Download button
                csv = predictions.to_csv(index=False)
                st.download_button(
                    label="📥 Download Predictions",
                    data=csv,
                    file_name="predictions.csv",
                    mime="text/csv"
                )
    else:
        st.info("👈 Please upload a CSV file to get started")

with tab2:
    st.header("Data Management")
    # Add data management features here
    st.write("Manage your data files and view datasets")

with tab3:
    st.header("API Access")
    st.code("""
    # Example API call
    curl -X POST http://localhost:8000/predict \\
         -H "Content-Type: application/json" \\
         -d '{"data": [...]}'
    """, language="bash")
    st.write("API running on http://localhost:8000")

# Footer
st.markdown("---")
st.caption("Built with Streamlit | Model Version 1.0")