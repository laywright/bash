import dash
from dash import dcc, html, Input, Output, State, dash_table
import pandas as pd
import plotly.express as px
import numpy as np
import base64
import io
from scipy import stats

# Initialize the Dash app
app = dash.Dash(__name__)
app.title = "🚌 BasiGo Manpower Dashboard"

app.layout = html.Div([
    html.H1("🚌 BasiGo Manpower Dashboard", style={'textAlign': 'center'}),

    dcc.Upload(
        id='upload-data',
        children=html.Div(['📤 Drag and Drop or ', html.A('Select Excel File')]),
        style={
            'width': '100%', 'height': '60px', 'lineHeight': '60px',
            'borderWidth': '1px', 'borderStyle': 'dashed', 'borderRadius': '5px',
            'textAlign': 'center', 'margin': '10px'
        },
        multiple=False
    ),
    dcc.Tabs(id="tabs", value='tab-1', children=[
        dcc.Tab(label='Summary', value='tab-1'),
        dcc.Tab(label='Process Time Analysis', value='tab-2'),
        dcc.Tab(label='Staffing Distribution', value='tab-3'),
        dcc.Tab(label='Predictive Manpower Allocation', value='tab-4'),
    ]),
    html.Div(id='tabs-content')
])


# Global variables for caching data
global_df = pd.DataFrame()
bus_columns = []


@app.callback(
    Output('tabs-content', 'children'),
    Input('tabs', 'value'),
    State('upload-data', 'contents'),
    State('upload-data', 'filename')
)
def update_tab(tab, contents, filename):
    global global_df, bus_columns

    if contents is None:
        return html.Div("Please upload an Excel file to view data.")

    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    df = pd.read_excel(io.BytesIO(decoded), sheet_name='Manhours')

    df = df.dropna(how='all').rename(columns=lambda x: str(x).strip())
    df['Number of people'] = pd.to_numeric(df.get('Number of people', pd.Series(dtype=float)), errors='coerce')

    bus_columns = [col for col in df.columns if str(col).startswith('Bus') and col not in ['Bus 21', 'Bus 22', 'Bus 23', 'Bus 24']]
    df['Avg_Time_Per_Process'] = df[bus_columns].mean(axis=1)
    df['Variance'] = df[bus_columns].var(axis=1)
    df['Avg_Manhours'] = df[bus_columns].mean(axis=1)
    df['Manhours per person'] = df['Avg_Manhours'] / df['Number of people'].replace(0, pd.NA)

    global_df = df

    if tab == 'tab-1':
        return tab_summary(df)
    elif tab == 'tab-2':
        return tab_process_time(df)
    elif tab == 'tab-3':
        return tab_staffing(df)
    elif tab == 'tab-4':
        return tab_prediction(df)


def tab_summary(df):
    total_hours = df[bus_columns].multiply(df['Number of people'], axis=0).sum()
    total_df = pd.DataFrame({'Bus': bus_columns, 'Manhours': total_hours.values})
    avg_manhours = total_df['Manhours'].mean()

    fig = px.bar(
        total_df.sort_values(by='Manhours', ascending=False),
        x='Bus', y='Manhours',
        text='Manhours',
        title="🚌 Total Manhours per Bus",
        template='plotly_white',
        color='Bus'
    )
    fig.update_layout(title_font_size=20, xaxis_tickangle=-45)

    return html.Div([
        html.H3(f"Average Total Manhours per Bus: {avg_manhours:.1f} hrs"),
        dcc.Graph(figure=fig),
        html.H4("Top 5 Buses by Manhours"),
        dash_table.DataTable(
            data=total_df.sort_values(by='Manhours', ascending=False).head(5).to_dict('records'),
            columns=[{"name": i, "id": i} for i in total_df.columns],
            style_table={'overflowX': 'auto'}
        )
    ])


def tab_process_time(df):
    process_avg_df = df[['Process', 'Avg_Time_Per_Process']].dropna()
    process_avg_df = process_avg_df[process_avg_df['Process'].str.strip() != '']
    process_avg_df = process_avg_df.sort_values(by='Avg_Time_Per_Process', ascending=False)

    fig = px.bar(
        process_avg_df,
        x='Process', y='Avg_Time_Per_Process',
        title='⚙️ Average Time per Process',
        text='Avg_Time_Per_Process',
        template='plotly_white'
    )
    fig.update_layout(xaxis_tickangle=-45)

    return html.Div([
        html.H4("Top Processes by Average Time"),
        dcc.Graph(figure=fig)
    ])


def tab_staffing(df):
    staffing_summary = df.groupby(['Station', 'Process'])['Number of people'].sum().reset_index()

    fig = px.bar(
        staffing_summary.sort_values(by='Number of people', ascending=False),
        x='Process', y='Number of people', color='Station',
        title='👷‍♂️ Staffing by Process and Station',
        text='Number of people',
        template='plotly_white'
    )
    fig.update_layout(xaxis_tickangle=-45)

    return html.Div([
        html.H4("Current Staffing Distribution"),
        dcc.Graph(figure=fig)
    ])


def tab_prediction(df):
    current_output = 7
    target_output = 10
    STU = 51840  # in minutes
    working_days = 21
    hours_per_day = 8
    absenteeism_rate = 0.05
    indirect_ratio = 0.10

    AWH = working_days * hours_per_day
    efficiency_factor = current_output / target_output
    EHE = AWH * efficiency_factor * (1 - absenteeism_rate)
    current_direct_staff = df['Number of people'].sum()
    required_direct = (target_output * STU / 60) / EHE
    required_indirect = required_direct * indirect_ratio
    total_required = required_direct + required_indirect

    summary = df.groupby(['Station', 'Process'])['Number of people'].sum().reset_index()
    summary['Current_Proportion'] = summary['Number of people'] / summary['Number of people'].sum()
    summary['Predicted'] = (summary['Current_Proportion'] * required_direct).round(2)

    return html.Div([
        html.H4("📊 Predictive Staffing Requirements"),
        html.P(f"Current Direct Staff: {int(current_direct_staff)}"),
        html.P(f"Target Output: {target_output} buses"),
        html.P(f"Required Direct: {required_direct:.2f}"),
        html.P(f"Required Indirect: {required_indirect:.2f}"),
        html.P(f"Total Required: {total_required:.2f}"),
        dash_table.DataTable(
            data=summary[['Station', 'Process', 'Number of people', 'Predicted']].to_dict('records'),
            columns=[{"name": i, "id": i} for i in ['Station', 'Process', 'Number of people', 'Predicted']],
            style_table={'overflowX': 'auto'},
            style_cell={"textAlign": "left"}
        )
    ])


if __name__ == '__main__':
    app.run_server(debug=True)
