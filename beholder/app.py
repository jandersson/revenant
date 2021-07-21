import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_table_experiments as dt
import pandas as pd
import plotly.graph_objs as go
from sqlalchemy import create_engine


def get_exp(character):
    # TODO: Write this query more better: filter on the join, use a cte for readability
    exp_table_sql = f"""SELECT ms.skill_name,
                               ms.rank,
                               ms.mindstate_num as mindstate
                          FROM mindstate_r ms 
                          JOIN (select max(timestamp) as max_timestamp 
                                  from mindstate_r 
                                 where character_name='{character}') ts 
                            ON ts.max_timestamp = ms.timestamp
                         WHERE character_name='{character}';"""
    return pd.read_sql(exp_table_sql, engine)


def get_exp_history(character):
    # HACK: This is a brute force method that needs optimization
    # TODO: Length of history should be customizable
    return pd.read_sql(
        f"select * from mindstate_r where character_name = '{character}' order by mindstate_seq_num desc limit 30000",
        engine,
    ).set_index("skill_name", inplace=True)


def get_characters():
    # TODO: Create a character dimension, CHARACTER_D
    return pd.read_sql("select distinct(character_name) from mindstate_r", engine)["character_name"]


def get_skills():
    # TODO: Create a skill dimension, SKILL_D
    # TODO: The db current has different string encodings in the skill column. Remove differently encoded strings from the skill name column and get rid of this abomination
    return pd.unique(
        pd.read_sql("select distinct(skill_name) from mindstate_r", engine)["skill_name"]
        .str.encode("utf-8")
        .str.decode("utf-8")
        .dropna()
    )


def serve_layout():
    skills = get_skills()
    characters = get_characters()
    default_character = "Crannach"
    exp_df = get_exp(default_character)
    return html.Div(
        style={"backgroundColor": colors["background"]},
        children=[
            html.H2(
                "Revenant: MUD Navelgazing",
                style={
                    "position": "relative",
                    "font-family": "Dosis",
                    "font-size": "3.0rem",
                    "top": "0px",
                    "left": "10px",
                },
            ),
            html.Label("Character"),
            dcc.Dropdown(
                id="char-dropdown",
                options=[{"label": char_name, "value": char_name} for char_name in characters],
                value=default_character
                # value=characters.iloc[0]
            ),
            html.Label("Skills"),
            dcc.Dropdown(
                id="skills-dropdown",
                options=[{"label": skill_name, "value": skill_name} for skill_name in skills],
                value=["Sorcery"],
                multi=True,
            ),
            html.Label("Experience"),
            dcc.Graph(
                id="mindstate-plot",
            ),
            html.Div(
                [
                    dt.DataTable(
                        rows=exp_df.to_dict("records"),
                        id="exp-table",
                        row_selectable=True,
                        editable=False,
                        filterable=True,
                        sortable=True,
                        selected_row_indices=[],
                    ),
                    html.Div(id="selected_indexes"),
                ],
                id="exp-div",
            ),
            # Hidden component that allows for other components update on a timer
            dcc.Interval(id="interval-component", interval=50 * 1000, n_intervals=0),  # in milliseconds
        ],
    )


# TODO: Organize all this hackery into modules
engine = create_engine("sqlite:////home/jonas/lich/lich/data/revenant.db3")
app = dash.Dash()
server = app.server
external_css = ["//fonts.googleapis.com/css?family=Dosis:Medium", "https://codepen.io/chriddyp/pen/bWLwgP.css"]
for css in external_css:
    app.css.append_css({"external_url": css})
# TODO: Use a css file
colors = {"background": "#FFFFFF", "text": "#7FDBFF"}
app.layout = serve_layout


@app.callback(
    dash.dependencies.Output("exp-table", "rows"),
    [dash.dependencies.Input("char-dropdown", "value"), dash.dependencies.Input("interval-component", "n_intervals")],
)
def update_exp_table(character, num_intervals):
    return get_exp(character).to_dict("records")


@app.callback(
    dash.dependencies.Output("mindstate-plot", "figure"),
    [
        dash.dependencies.Input("char-dropdown", "value"),
        dash.dependencies.Input("skills-dropdown", "value"),
        dash.dependencies.Input("interval-component", "n_intervals"),
    ],
)
def update_mindstate_plot(character, skills, _dummy):
    """Update mindstate plot when the character or skills dropdown menus change. Update on timing interval"""

    conn = engine.connect()
    exp_df = pd.read_sql(
        f"select * from mindstate_r where character_name = '{character}' order by mindstate_seq_num desc limit 30000",
        conn,
    )
    conn.close()
    return {
        "data": [
            go.Scatter(
                x=pd.to_datetime(
                    exp_df[(exp_df.character_name == character) & (exp_df.skill_name == skill)]["timestamp"],
                    format="%Y-%m-%d %H:%M:%S",
                ),
                y=exp_df[(exp_df.character_name == character) & (exp_df.skill_name == skill)]["mindstate_num"],
                name=skill,
            )
            for skill in skills
        ],
        "layout": go.Layout(
            xaxis={
                "title": "Time (UTC)",
                "rangeselector": {
                    "buttons": [
                        {"count": 1, "label": "1d", "step": "day", "stepmode": "backward"},
                        {"count": 3, "label": "3d", "step": "day", "stepmode": "backward"},
                        {"step": "all"},
                    ]
                },
                "rangeslider": {},
                "type": "date",
            },
            yaxis={"title": "Mindstate"},
            title=f"Mindstate over Time for {character}",
        ),
    }


@app.callback(
    dash.dependencies.Output("exp-table", "selected_row_indices"),
    [dash.dependencies.Input("skills-dropdown", "value")],
    [dash.dependencies.State("exp-table", "rows"), dash.dependencies.State("exp-table", "selected_row_indices")],
)
def update_selected_row_indices(skills, rows, selected_row_indices):
    if len(skills) > 0:
        for skill in skills:
            selected_row_indices.append(skill)
    return selected_row_indices


if __name__ == "__main__":
    app.run_server(host="0.0.0.0", debug=True)
