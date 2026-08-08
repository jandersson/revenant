"""Smoke-test script for the engine: look around, report the exits.

Run it from any attached front end:  ;hello
"""


def main(s):
    s.echo("hello from the script engine" + (f" (args: {s.args})" if s.args else ""))
    s.put("look")
    line = s.waitfor(r"Obvious (paths|exits)", timeout=10)
    if line:
        s.echo(f"exits spotted: {line.strip()}")
    else:
        s.echo("no exits line seen within 10s")
    if s.state is not None and s.state.compass:
        s.echo(f"compass agrees: {' '.join(s.state.compass)}")
