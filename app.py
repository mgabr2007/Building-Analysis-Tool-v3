import streamlit as st
import pandas as pd
import numpy as np
import ifcopenshell
import ifcopenshell.api
import matplotlib.pyplot as plt
from collections import defaultdict
import tempfile
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import hashlib
import logging
from fpdf import FPDF
import plotly.io as pio

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Utility Functions
def handle_file_upload(upload_type, file_types):
    uploaded_file = st.file_uploader(f"Choose a {upload_type} file", type=file_types, key=upload_type)
    if uploaded_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_types[0]}') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_file_path = tmp_file.name
        return tmp_file_path, uploaded_file.name
    return None, None

def process_ifc_file(file_path):
    try:
        return ifcopenshell.open(file_path)
    except Exception as e:
        error_message = f"Error opening IFC file: {e}"
        logging.error(error_message)
        st.error(error_message)
        return None

def read_excel(file):
    try:
        return pd.read_excel(file, engine='openpyxl')
    except Exception as e:
        error_message = f"Failed to read Excel file: {e}"
        logging.error(error_message)
        st.error(error_message)
        return pd.DataFrame()

# Metadata Management
def display_metadata(ifc_file):
    project = ifc_file.by_type('IfcProject')
    if project:
        project = project[0]
        st.write("### Project Metadata")
        st.write(f"Name: {project.Name}")
        st.write(f"Description: {project.Description}")
        st.write(f"Phase: {project.Phase}")
        if hasattr(project, 'CreationDate'):
            st.write(f"Time Stamp: {datetime.fromtimestamp(project.CreationDate)}")
        else:
            st.write("Time Stamp: Not available")

# IFC Analysis Functions
def count_building_components(ifc_file):
    component_count = defaultdict(int)
    try:
        for ifc_entity in ifc_file.by_type('IfcProduct'):
            component_count[ifc_entity.is_a()] += 1
    except Exception as e:
        error_message = f"Error processing IFC file: {e}"
        logging.error(error_message)
        st.error(error_message)
    return component_count

def detailed_analysis(ifc_file, product_type, sort_by=None):
    product_count = defaultdict(int)
    try:
        for product in ifc_file.by_type(product_type):
            product_name = product.Name if product.Name else "Unnamed"
            type_name = product_name.split(':')[0] if product_name else "Unnamed"
            product_count[type_name] += 1
    except Exception as e:
        error_message = f"Error during detailed analysis: {e}"
        logging.error(error_message)
        st.error(error_message)
        return

    labels, values = zip(*product_count.items()) if product_count else ((), ())
    if values:
        fig = px.pie(values=values, names=labels, title=f"Distribution of {product_type} Products by Type")
        st.plotly_chart(fig)

        if sort_by:
            df = pd.DataFrame({'Type': labels, 'Count': values}).sort_values(by=sort_by, ascending=False)
            st.table(df)
    else:
        st.write(f"No products found for {product_type}.")

# Visualization Functions
def visualize_component_count(component_count, chart_type='Bar Chart'):
    labels, values = zip(*sorted(component_count.items(), key=lambda item: item[1], reverse=True)) if component_count else ((), ())
    if chart_type == 'Bar Chart':
        fig = px.bar(x=labels, y=values)
    elif chart_type == 'Pie Chart':
        fig = px.pie(values=values, names=labels)
    fig.update_layout(transition_duration=500)
    return fig

def visualize_data(df, columns):
    figs = []
    for column in columns:
        if pd.api.types.is_numeric_dtype(df[column]):
            fig = px.histogram(df, x=column)
            st.plotly_chart(fig)
            figs.append(fig)
        else:
            fig = px.bar(df, x=column, title=f"Bar chart of {column}")
            st.plotly_chart(fig)
            figs.append(fig)
    return figs

def generate_insights(df):
    if not df.empty:
        st.write("Descriptive Statistics:", df.describe())
        # Placeholder for more sophisticated analysis or predictive modeling

# PDF Export Function
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'IFC and Excel File Analysis Report', 0, 1, 'C')
        self.ln(10)

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(5)

    def chapter_body(self, body):
        self.set_font('Arial', '', 12)
        self.multi_cell(0, 10, body)
        self.ln()

    def add_chapter(self, title, body):
        self.add_page()
        self.chapter_title(title)
        self.chapter_body(body)

    def add_image(self, image_path, title):
        self.add_page()
        self.chapter_title(title)
        self.image(image_path, x=10, y=30, w=190)

def export_analysis_to_pdf(ifc_metadata, component_count, figs):
    pdf = PDF()
    pdf.add_page()

    pdf.chapter_title("IFC File Metadata")
    metadata_body = f"""
    Name: {ifc_metadata.get('Name', 'Not available')}
    Description: {ifc_metadata.get('Description', 'Not available')}
    Phase: {ifc_metadata.get('Phase', 'Not available')}
    Creation Date: {ifc_metadata.get('CreationDate', 'Not available')}
    """
    pdf.chapter_body(metadata_body)

    pdf.chapter_title("Component Count")
    for component, count in component_count.items():
        pdf.chapter_body(f"{component}: {count}")

    for idx, fig in enumerate(figs):
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
            try:
                fig.write_image(tmp_file.name)
                pdf.add_image(tmp_file.name, f"Chart {idx + 1}")
            except Exception as e:
                logging.error(f"Error exporting chart to image: {e}")
                st.error(f"Error exporting chart to image: {e}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        pdf_file_path = tmp_file.name
        pdf.output(pdf_file_path)
    return pdf_file_path

# Main Analysis Functions
def ifc_file_analysis():
    st.write("""
    ### Instructions for Analyzing IFC Files:

    1. **Upload an IFC File:** Click on the "Choose a IFC file" button to upload an IFC (Industry Foundation Classes) file.

    2. **View Project Metadata:** After the file is processed, metadata of the project, including name, description, and phase, will be displayed.

    3. **Component Count Visualization:** Choose a chart type (Bar Chart or Pie Chart) to visualize the count of building components.

    4. **Detailed Analysis:** Expand the "Show Detailed Component Analysis" section, select a product type, and view detailed analysis of the selected product type.

    5. **Export Analysis as PDF:** Click the "Export Analysis as PDF" button to download a PDF report of the analysis.
    """)

    file_path, file_name = handle_file_upload("IFC", ['ifc'])
    if file_path:
        with st.spinner('Processing IFC file...'):
            ifc_file = process_ifc_file(file_path)
            if ifc_file:
                display_metadata(ifc_file)
                component_count = count_building_components(ifc_file)
                chart_type = st.radio("Chart Type", options=['Bar Chart', 'Pie Chart'], key="chart")
                fig = visualize_component_count(component_count, chart_type)
                st.plotly_chart(fig)
                detailed_analysis_ui(ifc_file)

                ifc_metadata = {
                    "Name": ifc_file.by_type('IfcProject')[0].Name,
                    "Description": ifc_file.by_type('IfcProject')[0].Description,
                    "Phase": ifc_file.by_type('IfcProject')[0].Phase,
                    "CreationDate": datetime.fromtimestamp(ifc_file.by_type('IfcProject')[0].CreationDate) if hasattr(ifc_file.by_type('IfcProject')[0], 'CreationDate') else 'Not available'
                }

                figs = [fig]
                if st.button("Export Analysis as PDF"):
                    pdf_file_path = export_analysis_to_pdf(ifc_metadata, component_count, figs)
                    with open(pdf_file_path, 'rb') as f:
                        st.download_button('Download PDF Report', f, file_name.replace('.ifc', '.pdf'))
            os.remove(file_path)

def save_ifc_file(ifc_file):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ifc') as tmp_file:
            ifc_file.write(tmp_file.name)
            return tmp_file.name
    except Exception as e:
        error_message = f"Error saving IFC file: {e}"
        logging.error(error_message)
        st.error(error_message)
        return None

def detailed_analysis_ui(ifc_file):
    with st.expander("Show Detailed Component Analysis"):
        product_types = sorted({entity.is_a() for entity in ifc_file.by_type('IfcProduct')})
        selected_product_type = st.selectbox("Select a product type for detailed analysis", product_types, key="product_type")
        sort_by = st.select_slider("Sort by", ["Type", "Count"], value='Count', key="sort")
        detailed_analysis(ifc_file, selected_product_type, sort_by)

def excel_file_analysis():
    st.write("""
    ### Instructions for Analyzing Excel Files:

    1. **Upload an Excel File:** Click on the "Choose an Excel file" button to upload an Excel spreadsheet.

    2. **Select Columns to Display:** Choose the columns you want to display from the uploaded Excel file.

    3. **Visualize Data:** Click on "Visualize Data" to generate charts for the selected columns.

    4. **Generate Insights:** Click on "Generate Insights" to view descriptive statistics and other insights from the data.
    """)

    file_path, _ = handle_file_upload("Excel", ['xlsx'])
    if file_path:
        df = read_excel(file_path)
        if not df.empty:
            selected_columns = st.multiselect("Select columns to display", df.columns.tolist(), default=df.columns.tolist(), key="columns")
            if selected_columns:
                st.dataframe(df[selected_columns])
                figs = []
                if st.button("Visualize Data", key="visualize"):
                    figs = visualize_data(df, selected_columns)
                if st.button("Generate Insights", key="insights"):
                    generate_insights(df)
                if figs and st.button("Export Analysis as PDF"):
                    pdf_file_path = export_analysis_to_pdf({"Name": "Excel Data Analysis"}, {}, figs)
                    with open(pdf_file_path, 'rb') as f:
                        st.download_button('Download PDF Report', f, 'excel_analysis.pdf')
            os.remove(file_path)

# Comparison Analysis Functions
def compare_ifc_files(ifc_file1, ifc_file2):
    components1 = count_building_components(ifc_file1)
    components2 = count_building_components(ifc_file2)

    comparison_result = defaultdict(dict)
    all_component_types = set(components1.keys()) | set(components2.keys())

    for component_type in all_component_types:
        count1 = components1.get(component_type, 0)
        count2 = components2.get(component_type, 0)
        comparison_result[component_type]['File 1 Count'] = count1
        comparison_result[component_type]['File 2 Count'] = count2
        comparison_result[component_type]['Difference'] = count1 - count2

    return comparison_result

def compare_ifc_files_ui():
    st.title("Compare IFC Files")
    st.write("""
    ### Instructions for Comparing IFC Files:

    Please follow the steps below to compare the components of two IFC (Industry Foundation Classes) files:

    1. **Upload First IFC File:** Click on the "Choose File" button below labeled **"Choose the first IFC file"**. Navigate to the location of the first IFC file on your device and select it for upload.

    2. **Upload Second IFC File:** Similarly, use the second "Choose File" button labeled **"Choose the second IFC file"** to upload the second IFC file you wish to compare with the first one.

    After uploading both files, you will be prompted to:

    3. **Select a Component Type for Detailed Comparison:** From the dropdown menu, select one of the available component types (e.g., walls, doors, windows) to compare between the two IFC files. The application will display a bar chart showing the count of the selected component type in both files, along with their difference.

    4. **View Overall Comparison:** After selecting a specific component type, you can also choose to view an overall comparison of all components by clicking the **"Show Overall Comparison"** button. This will display a pie chart visualizing the proportion of differences across all component types, giving you a comprehensive overview of how the two IFC files differ.

    This step-by-step process will help you understand the detailed differences in building components between the two IFC files, as well as provide an overall summary of the differences.
    """)

    file_path1, file_name1 = handle_file_upload("first IFC", ['ifc'])
    file_path2, file_name2 = handle_file_upload("second IFC", ['ifc'])

    if file_path1 and file_path2:
        with st.spinner('Processing IFC files...'):
            ifc_file1 = process_ifc_file(file_path1)
            ifc_file2 = process_ifc_file(file_path2)
            if ifc_file1 and ifc_file2:
                comparison_result = compare_ifc_files(ifc_file1, ifc_file2)
                all_component_types = list(comparison_result.keys())
                selected_component = st.selectbox("Select a component type for detailed comparison:", all_component_types, key="component_type")

                figs = []
                if selected_component:
                    component_data = comparison_result[selected_component]
                    fig = go.Figure(data=[
                        go.Bar(name=f"{file_name1} - File 1", x=[selected_component], y=[component_data['File 1 Count']], marker_color='indianred'),
                        go.Bar(name=f"{file_name2} - File 2", x=[selected_component], y=[component_data['File 2 Count']], marker_color='lightseagreen'),
                        go.Bar(name='Difference', x=[selected_component], y=[component_data['Difference']], marker_color='lightslategray')
                    ])
                    fig.update_layout(barmode='group', title_text=f'Comparison of {selected_component} in {file_name1} and {file_name2}', xaxis_title="Component Type", yaxis_title="Count")
                    st.plotly_chart(fig)
                    figs.append(fig)

                    if st.button("Show Overall Comparison"):
                        differences = [comparison_result[comp]['Difference'] for comp in all_component_types]
                        fig_pie = go.Figure(data=[go.Pie(labels=all_component_types, values=differences, title=f'Overall Differences in Components between {file_name1} and {file_name2}')])
                        st.plotly_chart(fig_pie)
                        figs.append(fig_pie)

                if figs and st.button("Export Analysis as PDF"):
                    pdf_file_path = export_analysis_to_pdf({"Name": "IFC Files Comparison"}, {}, figs)
                    with open(pdf_file_path, 'rb') as f:
                        st.download_button('Download PDF Report', f, 'ifc_comparison.pdf')

            os.remove(file_path1)
            os.remove(file_path2)

# Main Application Structure
def welcome_page():
    st.title("IFC and Excel File Analysis Tool")
    st.write("""
    ### Welcome to the IFC and Excel File Analysis Tool

    This Streamlit application provides an interactive interface for analyzing IFC (Industry Foundation Classes) files and Excel spreadsheets. It allows users to visualize component counts in IFC files and perform data analysis and visualization on Excel files.

    #### Features:

    - **IFC File Analysis:** Upload and analyze IFC files to view project metadata, perform component count visualization, and conduct detailed analysis of building components.
    - **Excel File Analysis:** Upload and analyze Excel spreadsheets to select and visualize data columns, and generate insights from the data.
    - **IFC File Comparison:** Compare the components of two IFC files to identify differences and view detailed and overall comparison charts.

    #### License:
    This project is licensed under the GNU General Public License v3.0. For more details, see the LICENSE file in the root directory of this source tree or visit [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.en.html).

    #### Copyright:
    Copyright (C) [2024] [Mostafa Gabr]. All rights reserved.
    """)

def main():
    st.sidebar.title("Navigation")
    if st.sidebar.button("Home"):
        st.session_state.analysis_choice = "Welcome"
    if st.sidebar.button("Analyze IFC File"):
        st.session_state.analysis_choice = "Analyze IFC File"
    if st.sidebar.button("Analyze Excel File"):
        st.session_state.analysis_choice = "Analyze Excel File"
    if st.sidebar.button("Compare IFC Files"):
        st.session_state.analysis_choice = "Compare IFC Files"

    if 'analysis_choice' not in st.session_state:
        st.session_state.analysis_choice = "Welcome"

    if st.session_state.analysis_choice == "Welcome":
        welcome_page()
    elif st.session_state.analysis_choice == "Analyze IFC File":
        ifc_file_analysis()
    elif st.session_state.analysis_choice == "Analyze Excel File":
        excel_file_analysis()
    elif st.session_state.analysis_choice == "Compare IFC Files":
        compare_ifc_files_ui()

if __name__ == "__main__":
    main()

st.sidebar.markdown("""
----------------
#### Copyright Notice
Copyright (C) [2024] [Mostafa Gabr]. All rights reserved.

This project is licensed under the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.en.html).
""")
