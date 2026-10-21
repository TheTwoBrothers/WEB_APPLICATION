import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. MODULAR FUNCTIONS ---

@st.cache_data
def load_data(uploaded_file):
    """Loads data based on file extension."""
    filename = uploaded_file.name
    try:
        if filename.endswith('.csv'):
            return pd.read_csv(uploaded_file), None
        elif filename.endswith('.xlsx'):
            return pd.read_excel(uploaded_file), None
        elif filename.endswith('.json'):
            return pd.read_json(uploaded_file), None
        return None, "Unsupported file format."
    except Exception as e:
        return None, f"Error loading file: {e}"

def data_validation(df):
    """Returns basic data validation metrics."""
    return df.shape, df.columns.tolist(), df.isnull().sum(), df.duplicated().sum(), df.dtypes.astype(str)

def preprocess_data(df):
    """Cleans data, handles missing values, duplicates, and formats data types."""
    df_clean = df.copy()
    df_clean = df_clean.drop_duplicates()
    
    # 1. Force convert known numerical columns from object to float (fixes prac10.csv issues)
    num_keywords = ['sales', 'profit', 'quantity', 'discount', 'price']
    for col in df_clean.columns:
        if any(keyword in col.lower() for keyword in num_keywords) and df_clean[col].dtype == 'object':
            # Remove potential string artifacts like commas or dollar signs
            df_clean[col] = df_clean[col].astype(str).str.replace(r'[$,]', '', regex=True)
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')

    # 2. Parse date columns
    for col in df_clean.columns:
        if 'date' in col.lower() or df_clean[col].dtype == 'object':
            try:
                converted = pd.to_datetime(df_clean[col], errors='ignore')
                if pd.api.types.is_datetime64_any_dtype(converted):
                    df_clean[col] = converted
            except Exception:
                pass
                
    # 3. Handle missing values
    for col in df_clean.columns:
        if pd.api.types.is_numeric_dtype(df_clean[col]):
            df_clean[col] = df_clean[col].fillna(df_clean[col].median())
        else:
            mode_val = df_clean[col].mode()
            df_clean[col] = df_clean[col].fillna(mode_val[0] if not mode_val.empty else "Unknown")
            
    return df_clean

def calculate_kpis(df):
    """Calculates dynamically updating KPIs."""
    cols = {c.lower(): c for c in df.columns}
    
    sales = df[cols.get('sales')].sum() if 'sales' in cols else 0
    profit = df[cols.get('profit')].sum() if 'profit' in cols else 0
    quantity = df[cols.get('quantity')].sum() if 'quantity' in cols else 0
    
    order_col = next((c for c in cols if 'order' in c and 'id' in c), None)
    orders = df[cols[order_col]].nunique() if order_col else len(df)
    
    profit_margin = (profit / sales * 100) if sales > 0 else 0
    
    return sales, profit, orders, quantity, profit_margin

# --- 2. STREAMLIT APP LAYOUT ---

st.set_page_config(page_title="Data Analytics Dashboard", layout="wide")
st.title("Interactive Data Analysis Dashboard")

st.sidebar.header("1. Upload Data")
uploaded_file = st.sidebar.file_uploader("Upload CSV, Excel, or JSON", type=['csv', 'xlsx', 'json'])

if uploaded_file:
    df_raw, error = load_data(uploaded_file)
    
    if error:
        st.error(error)
    else:
        tab1, tab2 = st.tabs(["Data Validation & Preprocessing", "Interactive Dashboard"])
        
        # --- TAB 1: Validation & Preprocessing ---
        with tab1:
            st.subheader("Raw Data Validation")
            dim, cols, missing, dups, dtypes = data_validation(df_raw)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Rows", dim[0])
            c2.metric("Columns", dim[1])
            c3.metric("Duplicate Records", dups)
            
            st.write("**Data Types & Missing Values:**")
            st.dataframe(pd.DataFrame({"Data Type": dtypes, "Missing Values": missing}), use_container_width=True)
            
            with st.spinner("Cleaning data..."):
                df_clean = preprocess_data(df_raw)
                
            st.success("Data cleaned! Duplicates removed, numeric issues fixed, missing values imputed.")
            st.write("**Statistical Summary:**")
            st.dataframe(df_clean.describe(), use_container_width=True)

        # --- TAB 2: Dashboard & Filters ---
        with tab2:
            st.sidebar.header("2. Interactive Filters")
            
            # Select first 3 categorical columns for filtering (e.g., Segment, Category, Region)
            cat_cols = df_clean.select_dtypes(include=['object', 'category']).columns.tolist()
            filter_cols = cat_cols[:3] if len(cat_cols) >= 3 else cat_cols
            
            df_filtered = df_clean.copy()
            for col in filter_cols:
                unique_vals = df_clean[col].unique().tolist()
                selected_vals = st.sidebar.multiselect(f"Filter by {col}", unique_vals, default=unique_vals)
                df_filtered = df_filtered[df_filtered[col].isin(selected_vals)]
                
            st.sidebar.info(f"Showing {len(df_filtered)} out of {len(df_clean)} records.")
            
            # KPIs
            st.subheader("Key Performance Indicators")
            sales, profit, orders, qty, margin = calculate_kpis(df_filtered)
            
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("Total Sales", f"${sales:,.2f}")
            k2.metric("Total Profit", f"${profit:,.2f}")
            k3.metric("Total Orders", f"{orders:,}")
            k4.metric("Total Quantity", f"{qty:,.0f}")
            k5.metric("Profit Margin", f"{margin:.1f}%")
            
            st.divider()
            
            # Interactive Visualizations
            st.subheader("Visualizations")
            num_cols = df_filtered.select_dtypes(include=['number']).columns.tolist()
            
            if len(num_cols) >= 2 and len(cat_cols) >= 1:
                col1, col2 = st.columns(2)
                
                # Chart 1: Sales by Category (Bar Chart)
                with col1:
                    y_col = 'Sales' if 'Sales' in df_filtered.columns else num_cols[0]
                    fig1 = px.bar(df_filtered, x=cat_cols[0], y=y_col, title=f"Total {y_col} by {cat_cols[0]}", color=cat_cols[0])
                    st.plotly_chart(fig1, use_container_width=True)
                
                # Chart 2: Profit vs Sales (Scatter Plot)
                with col2:
                    x_scatter = 'Sales' if 'Sales' in df_filtered.columns else num_cols[0]
                    y_scatter = 'Profit' if 'Profit' in df_filtered.columns else num_cols[1]
                    fig2 = px.scatter(df_filtered, x=x_scatter, y=y_scatter, color=cat_cols[0], title=f"{y_scatter} vs {x_scatter}")
                    st.plotly_chart(fig2, use_container_width=True)
                
                # Chart 3: Distribution or Time Series
                date_cols = df_filtered.select_dtypes(include=['datetime64']).columns.tolist()
                if date_cols:
                    df_time = df_filtered.groupby(date_cols[0])[y_col].sum().reset_index()
                    fig3 = px.line(df_time, x=date_cols[0], y=y_col, title=f"{y_col} Over Time")
                else:
                    fig3 = px.pie(df_filtered, names=cat_cols[1] if len(cat_cols) > 1 else cat_cols[0], values=y_col, title=f"{y_col} Breakdown")
                st.plotly_chart(fig3, use_container_width=True)
                
            else:
                st.warning("Not enough numeric/categorical columns to generate full visualizations.")
else:
    st.info("Please upload `prac10.csv` from the sidebar to begin.")