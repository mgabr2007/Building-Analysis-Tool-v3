import math
import streamlit as st
import pandas as pd
import numpy as np
import ifcopenshell
import ifcopenshell.api
import ifcopenshell.util.element as Element
import matplotlib.pyplot as plt
from collections import defaultdict
import tempfile
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import logging
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.units import inch
import plotly.io as pio
import psutil
import pprint

pp = pprint.PrettyPrinter()

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
        fig.update_layout(paper_bgcolor='white', plot_bgcolor='white', font_color='black')
        st.plotly_chart(fig)

        if sort_by:
            df = pd.DataFrame({'Type': labels, 'Count': values}).sort_values(by=sort_by, ascending=False)
            st.table(df)
    else:
        st.write(f"No products found for {product_type}.")

def detailed_analysis_ui(ifc_file):
    with st.expander("Show Detailed Component Analysis"):
        product_types = sorted({entity.is_a() for entity in ifc_file.by_type('IfcProduct')})
        selected_product_type = st.selectbox("Select a product type for detailed analysis", product_types, key="product_type")
        sort_by = st.select_slider("Sort by", ["Type", "Count"], value='Count', key="sort")
        detailed_analysis(ifc_file, selected_product_type, sort_by)

# Visualization Functions
def visualize_component_count(component_count, chart_type='Bar Chart'):
    labels, values = zip(*sorted(component_count.items(), key=lambda item: item[1], reverse=True)) if component_count else ((), ())
    if chart_type == 'Bar Chart':
        fig = px.bar(x=labels, y=values)
    elif chart_type == 'Pie Chart':
        fig = px.pie(values=values, names=labels)
    fig.update_layout(transition_duration=500, paper_bgcolor='white', plot_bgcolor='white', font_color='black')
    return fig

def visualize_data(df, columns):
    figs = []
    for column in columns:
        if pd.api.types.is_numeric_dtype(df[column]):
            fig = px.histogram(df, x=column)
            fig.update_layout(paper_bgcolor='white', plot_bgcolor='white', font_color='black')
            st.plotly_chart(fig)
            figs.append(fig)
        else:
            fig = px.bar(df, x=column, title=f"Bar chart of {column}")
            fig.update_layout(paper_bgcolor='white', plot_bgcolor='white', font_color='black')
            st.plotly_chart(fig)
            figs.append(fig)
    return figs

def generate_insights(df):
    if not df.empty:
        st.write("Descriptive Statistics:", df.describe())
        # Placeholder for more sophisticated analysis or predictive modeling

# PDF Export Function
def export_analysis_to_pdf(ifc_metadata, component_count, figs, author, subject, cover_text):
    buffer = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(buffer.name, pagesize=letter)
    styles = getSampleStyleSheet()
    flowables = []

    # Cover Page
    flowables.append(Spacer(1, 1 * inch))
    flowables.append(Paragraph(subject, styles['Title']))
    flowables.append(Spacer(1, 0.5 * inch))
    flowables.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", styles['Normal']))
    flowables.append(Paragraph(f"Author: {author}", styles['Normal']))
    flowables.append(Spacer(1, 1 * inch))
    flowables.append(Paragraph(cover_text, styles['Normal']))
    flowables.append(Spacer(1, 2 * inch))

    # IFC Metadata
    flowables.append(Paragraph("IFC File Metadata", styles['Heading2']))
    metadata_table_data = [
        ["Name", ifc_metadata.get('Name', 'Not available')],
        ["Description", ifc_metadata.get('Description', 'Not available')],
        ["Phase", ifc_metadata.get('Phase', 'Not available')],
        ["Creation Date", ifc_metadata.get('CreationDate', 'Not available')]
    ]
    metadata_table = Table(metadata_table_data)
    metadata_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ]))
    flowables.append(metadata_table)
    flowables.append(Spacer(1, 0.5 * inch))

    # Component Count
    flowables.append(Paragraph("Component Count", styles['Heading2']))
    component_table_data = [["Component", "Count"]] + [[component, str(count)] for component, count in component_count.items()]
    component_table = Table(component_table_data)
    component_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ]))
    flowables.append(component_table)
    flowables.append(Spacer(1, 0.5 * inch))

    # Adding Images
    for idx, fig in enumerate(figs):
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
            try:
                fig.update_layout(paper_bgcolor='white', plot_bgcolor='white', font_color='black')
                fig.write_image(tmp_file.name, format='png', engine='kaleido')
                flowables.append(Spacer(1, 0.5 * inch))
                flowables.append(Paragraph(f"Chart {idx + 1}", styles['Heading2']))
                flowables.append(Image(tmp_file.name))
            except Exception as e:
                logging.error(f"Error exporting chart to image: {e}")
                st.error(f"Error exporting chart to image: {e}")

    doc.build(flowables)
    return buffer.name

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

                # Get user inputs for cover page
                author = st.text_input("Author", value="Mostafa Gabr")
                subject = st.text_input("Main Subject", value="IFC and Excel File Analysis Report")
                cover_text = st.text_area("Cover Page Text", value="This report contains the analysis of IFC and Excel files. The following sections include metadata, component counts, and visualizations of the data.")

                if st.button("Export Analysis as PDF"):
                    pdf_file_path = export_analysis_to_pdf(ifc_metadata, component_count, figs, author, subject, cover_text)
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
                    fig.update_layout(barmode='group', title_text=f'Comparison of {selected_component} in {file_name1} and {file_name2}', xaxis_title="Component Type", yaxis_title="Count", paper_bgcolor='white', plot_bgcolor='white', font_color='black')
                    st.plotly_chart(fig)
                    figs.append(fig)

                    if st.button("Show Overall Comparison"):
                        differences = [comparison_result[comp]['Difference'] for comp in all_component_types]
                        fig_pie = go.Figure(data=[go.Pie(labels=all_component_types, values=differences, title=f'Overall Differences in Components between {file_name1} and {file_name2}')])
                        fig_pie.update_layout(paper_bgcolor='white', plot_bgcolor='white', font_color='black')
                        st.plotly_chart(fig_pie)
                        figs.append(fig_pie)

                if figs and st.button("Export Analysis as PDF"):
                    pdf_file_path = export_analysis_to_pdf({"Name": "IFC Files Comparison"}, {}, figs, "Author Name", "IFC Files Comparison Report", "This report contains the comparison analysis of two IFC files.")
                    with open(pdf_file_path, 'rb') as f:
                        st.download_button('Download PDF Report', f, 'ifc_comparison.pdf')

            os.remove(file_path1)
            os.remove(file_path2)

# Add new functionalities for detailed object data extraction and display
def get_objects_data_by_class(file, class_type):
    def add_pset_attributes(psets):
        for pset_name, pset_data in psets.items():
            for property_name in pset_data.keys():
                pset_attributes.add(f'{pset_name}.{property_name}')
    
    pset_attributes = set()
    objects_data = []
    objects = file.by_type(class_type)
      
    for obj in objects:
        psets = Element.get_psets(obj, psets_only=True)
        add_pset_attributes(psets)
        qtos = Element.get_psets(obj, qtos_only=True)
        add_pset_attributes(qtos)
        objects_data.append({
            "ExpressId": obj.id(),
            "GlobalId": getattr(obj, 'GlobalId', None),
            "Class": obj.is_a(),
            "PredefinedType": Element.get_predefined_type(obj),
            "Name": getattr(obj, 'Name', None),
            "Level": Element.get_container(obj).Name if Element.get_container(obj) else "",
            "Type": Element.get_type(obj).Name if Element.get_type(obj) else "",
            "QuantitySets": qtos,
            "PropertySets": psets,
        })
    return objects_data, list(pset_attributes)

def get_attribute_value(object_data, attribute):
    if "." not in attribute:
        return object_data.get(attribute, None)
    elif "." in attribute:
        pset_name, prop_name = attribute.split(".", 1)
        if pset_name in object_data["PropertySets"]:
            return object_data["PropertySets"][pset_name].get(prop_name, None)
        if pset_name in object_data["QuantitySets"]:
            return object_data["QuantitySets"][pset_name].get(prop_name, None)
    return None

def display_detailed_object_data():
    try:
        st.markdown("""
        ## Instructions for Using the IFC File Processor

        1. **Upload an IFC File**:
        - Use the "Choose an IFC file" button to upload your IFC file. This file should be in the `.ifc` format.

        2. **Select Class Type**:
        - After uploading the IFC file, select the class type of objects you want to analyze from the dropdown menu. The dropdown will be populated with all unique class types present in the uploaded IFC file.

        3. **View Object Data**:
        - The app will display a table containing detailed information about the objects of the selected class type. This table includes attributes like `ExpressId`, `GlobalId`, `Class`, `PredefinedType`, `Name`, `Level`, and `Type`, along with any property sets and quantity sets associated with the objects.

        **Explanation**:
        - **ExpressId**: The internal identifier of the object in the IFC file.
        - **GlobalId**: The globally unique identifier of the object.
        - **Class**: The type of the object (e.g., IfcBeam, IfcWall).
        - **PredefinedType**: A subtype or specific classification of the object.
        - **Name**: The name of the object.
        - **Level**: The floor or level where the object is located.
        - **Type**: The specific type of the object.
        - **PropertySets** and **QuantitySets**: These columns contain various properties and quantities associated with the objects, respectively.

        4. **View Floor and Type Summary**:
        - Below the detailed table, you will see another table that shows the total count of each type of object per floor. This table is grouped by `Level` and `Type`.

        **Explanation**:
        - This summary helps you understand how many objects of each type are present on each floor. For example, it will show you how many beams, walls, or windows are on each level of the building.

        5. **Download Data**:
        - You can download the detailed object data as a CSV file by clicking the "Download data as CSV" button. This allows you to further analyze the data offline or integrate it with other tools.
        """)

        file_path, file_name = handle_file_upload("IFC", ['ifc'])
        if file_path:
            with st.spinner('Processing IFC file...'):
                ifc_file = process_ifc_file(file_path)
                if ifc_file:
                    all_classes = set(entity.is_a() for entity in ifc_file)
                    class_type = st.selectbox('Select Class Type', sorted(all_classes))

                    data, pset_attributes = get_objects_data_by_class(ifc_file, class_type)
                    attributes = ["ExpressId", "GlobalId", "Class", "PredefinedType", "Name", "Level", "Type"] + pset_attributes

                    pandas_data = []
                    for object_data in data:
                        row = [get_attribute_value(object_data, attribute) for attribute in attributes]
                        pandas_data.append(tuple(row))

                    dataframe = pd.DataFrame.from_records(pandas_data, columns=attributes)

                    st.subheader("Detailed Object Data")
                    st.write(dataframe)

                    st.subheader("Summary by Floor and Type")
                    if 'Level' in dataframe.columns and 'Type' in dataframe.columns:
                        floor_type_counts = dataframe.groupby(['Level', 'Type']).size().reset_index(name='Count')
                        st.write(floor_type_counts)
                    else:
                        st.write("Columns 'Level' and 'Type' not found in the data.")

                    st.download_button(
                        label="Download data as CSV",
                        data=dataframe.to_csv(index=False).encode('utf-8'),
                        file_name='ifc_data.csv',
                        mime='text/csv',
                    )

                    # Explanation for Windows Information Table
                    st.markdown("""
                    ### Windows Information Table

                    The **Windows Information** table provides detailed data about each window in the IFC file. Here is an explanation of each column:

                    - **GlobalId**: The globally unique identifier of the window object.
                    - **Name**: The name of the window object.
                    - **Area**: The area of the window's glass, measured in square units.
                    - **Orientation**: The primary orientation of the window, indicating the direction the window faces (e.g., East, West, North, South).
                    - **Azimuth**: The azimuth angle of the window, which represents the angle between the projection of the window's direction vector on the XY plane and the positive X-axis. This angle is measured in degrees and ranges from 0 to 360 degrees.

                    The total area of all windows is also displayed above the table for a quick summary. This information helps in understanding the placement and orientation of windows within the building, which is useful for assessing factors such as natural light, heat gain, and ventilation.
                    """)

                    # Display windows data
                    display_window_data(ifc_file)

                    os.remove(file_path)
    except Exception as e:
        logging.error(f"Error in display_detailed_object_data: {e}")
        st.error(f"Error in display_detailed_object_data: {e}")


# Add new functionalities for window data extraction and display
def calculate_glass_area(window):
    try:
        if hasattr(window, 'Representation') and window.Representation is not None:
            for rep in window.Representation.Representations:
                if rep.RepresentationType in ['SweptSolid', 'SurfaceModel', 'Brep'] and hasattr(rep, 'Items'):
                    for item in rep.Items:
                        if hasattr(item, 'LayerAssignments'):
                            for layer in item.LayerAssignments:
                                if 'Glass' in layer.Name:  # Assuming the layer name includes 'Glass'
                                    if hasattr(item, 'SweptArea') and hasattr(item.SweptArea, 'Area'):
                                        return item.SweptArea.Area
                                    elif hasattr(item, 'OuterBoundary'):
                                        return item.OuterBoundary.area
    except Exception as e:
        logging.error(f"Error calculating window glass area: {e}")
    return 0

def get_window_orientation(window):
    try:
        if hasattr(window, 'ObjectPlacement') and window.ObjectPlacement is not None:
            if hasattr(window.ObjectPlacement, 'RelativePlacement') and window.ObjectPlacement.RelativePlacement is not None:
                placement = window.ObjectPlacement.RelativePlacement
                if hasattr(placement, 'RefDirection') and placement.RefDirection is not None:
                    direction = placement.RefDirection.DirectionRatios
                    logging.info(f"Window {window.GlobalId} direction: {direction}")
                    if direction:
                        azimuth = math.degrees(math.atan2(direction[1], direction[0])) % 360
                        return {
                            'Orientation': 'East' if direction[0] > 0 else 'West' if direction[0] < 0 else 'North' if direction[1] > 0 else 'South',
                            'Azimuth': azimuth
                        }
    except Exception as e:
        logging.error(f"Error determining window orientation: {e}")
    return {'Orientation': 'Unknown', 'Azimuth': None}

def extract_window_data(ifc_file):
    windows_data = []
    windows = ifc_file.by_type('IfcWindow')
    
    for window in windows:
        logging.info(f"Processing window {window.GlobalId} with name {window.Name}")
        orientation_data = get_window_orientation(window)
        window_data = {
            "GlobalId": window.GlobalId,
            "Name": window.Name,
            "Area": calculate_glass_area(window),
            "Orientation": orientation_data['Orientation'],
            "Azimuth": orientation_data['Azimuth']
        }
        windows_data.append(window_data)
    
    return pd.DataFrame(windows_data)

def display_window_data(ifc_file):
    st.subheader("Windows Information")
    windows_df = extract_window_data(ifc_file)
    if not windows_df.empty:
        total_area = windows_df['Area'].sum()
        st.write(f"Total Window Area: {total_area:.2f} square units")
        st.dataframe(windows_df)
    else:
        st.write("No windows found in the IFC file.")

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
    - **Detailed Object Data Extraction:** Extract and display detailed object data from IFC files, including property sets and quantity sets.

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
    if st.sidebar.button("Detailed Object Data"):
        st.session_state.analysis_choice = "Detailed Object Data"

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
    elif st.session_state.analysis_choice == "Detailed Object Data":
        display_detailed_object_data()

if __name__ == "__main__":
    main()

st.sidebar.markdown("""
----------------
#### Copyright Notice
Copyright (C) [2024] [Mostafa Gabr]. All rights reserved.

This project is licensed under the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.en.html).
""")
