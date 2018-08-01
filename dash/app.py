import dash
import dash_core_components as dcc
import dash_html_components as html
import pandas as pd
import plotly.graph_objs as go
from sqlalchemy import create_engine


def serve_layout():
    conn = engine.connect()
    characters = pd.read_sql("select distinct(character_name) from mindstate_r", conn)['character_name']
    # TODO: Remove differently encoded strings from the skill name column and get rid of this abomination
    skills = pd.unique(pd.read_sql("select distinct(skill_name) from mindstate_r", conn)['skill_name'].str.encode('utf-8').str.decode('utf-8').dropna()) 
    conn.close()
    return html.Div(style={'backgroundColor': colors['background']}, children=[

        html.H2('Revenant: MUD Navelgazing',
            style={
                'position': 'relative',
                'font-family': 'Dosis',
                'font-size': '3.0rem',
                'top': '0px',
                'left': '10px',
            }
        ),

        html.Label('Character'),
        dcc.Dropdown(
            id='char-dropdown',
            options=[{'label': char_name, 'value': char_name} for char_name in characters],
            value=characters.iloc[0]
            ),
        html.Label('Skills'),
        dcc.Dropdown(
            id='skills-dropdown',
            options=[{'label': skill_name, 'value': skill_name} for skill_name in skills],
            value=['Sorcery'],
            multi=True,
            ),
        dcc.Graph(
            id='mindstate-plot',
            ),
        dcc.Interval(
            id='interval-component',
            interval=50*1000, # in milliseconds
            n_intervals=0
        ),
    ])


engine = create_engine('sqlite:////home/jonas/lich/lich/data/revenant.db3')
app = dash.Dash()
server = app.server

external_css = ["//fonts.googleapis.com/css?family=Dosis:Medium",
                "https://codepen.io/chriddyp/pen/bWLwgP.css"]
for css in external_css:
    app.css.append_css({"external_url": css})

colors = {
    'background': '#FFFFFF',
    'text': '#7FDBFF'
}

app.layout = serve_layout

@app.callback(dash.dependencies.Output('mindstate-plot', 'figure'),
              [dash.dependencies.Input('char-dropdown', 'value'), 
               dash.dependencies.Input('skills-dropdown', 'value'), 
               dash.dependencies.Input('interval-component', 'n_intervals')])
def update_mindstate_plot(character, skills, _dummy):
    """Update mindstate plot when the character or skills dropdown menus change. Update on timing interval"""

    conn = engine.connect()
    exp_df = pd.read_sql(f"select * from mindstate_r where character_name = '{character}' order by mindstate_seq_num desc limit 30000", conn)
    conn.close()
    return {
        'data': [
            go.Scatter(x=pd.to_datetime(exp_df[(exp_df.character_name == character) & (exp_df.skill_name == skill)]['timestamp'], format="%Y-%m-%d %H:%M:%S"),
                       y=exp_df[(exp_df.character_name == character) & (exp_df.skill_name == skill)]['mindstate_num'], name=skill) for skill in skills
        ],
        'layout': go.Layout(
                    xaxis={
                        'title': 'Time (UTC)',
                        'rangeselector': {
                            'buttons': [
                                {'count': 1, 'label':'1d', 'step': 'day', 'stepmode': 'backward'}, 
                                {'count': 3, 'label': '3d', 'step': 'day', 'stepmode': 'backward'},
                                {'step': 'all'}]
                            },
                        'rangeslider': {},
                        'type': 'date',
                        },
                    yaxis={'title': 'Mindstate'},
                    title=f"Mindstate over Time for {character}"
                )
    }



if __name__ == '__main__':
    app.run_server(host='0.0.0.0', debug=True)

