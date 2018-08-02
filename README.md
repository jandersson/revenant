# Revenant
Python Utilities for DragonRealms. 

This is a data visualization application for DragonRealms player data using the Dash interactive Python framework developed by [Plot.ly](https://plot.ly/)

There are also ideas for future implementations in the sandbox folder, such as a LNet chat TUI application.

## Getting Started

### Running the Dash app locally
First create a virtual environment with conda or venv inside a temp folder, then activate it.

With conda
```
conda create -n revenant python=3.6

# Windows
activate revenant

# Linux
source activate revenant
```

With venv
```
virtualenv revenant

# Windows
revenant\Scripts\activate
# Or Linux
source venv/bin/activate
```

Clone the git repo, then install the requirements with pip
```
git clone https://github.com/jandersson/revenant 
cd revenant
pip install -r requirements.txt
```

Copy the data logging script to your lich scripts directory and run it. You do not need to trust it
```
cp ~/revenant/dash/revenant.lic ~/lich/scripts
# Do the following in game
;revenant
# Recommended
;e autostart('revenant')
```

Run the app. You need to have activated the virtual or conda environment beforehand (See the above steps 'With conda' or 'With venv' for the appropriate command)
```
python dash/app.py
```

