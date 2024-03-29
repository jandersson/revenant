
# Beholder

This is a data visualization application for DragonRealms player data using the Dash interactive Python framework developed by [Plot.ly](https://plot.ly/)

There are also ideas for future implementations in the sandbox folder, such as a LNet chat TUI application.

*Note: This was a terrific project, I wish I had some screenshots to share. I haven't ran this in years. I don't know if it still works, but I want to jump back into getting it flying again at some point. At least it can be a proof of concept for others who want to dashboard :)*

## Getting Started

### Running the Dash app locally
First create a virtual environment with conda or venv inside a temp folder, then activate it.

#### Setup a python virtual environment

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

#### Download the repo

Clone the git repo, then install the requirements with pip
```
git clone https://github.com/jandersson/revenant 
cd revenant
pip install -r requirements.txt
```

#### Install the data logging script 
This assumes you have lich installed along with the [dr-scripts](https://github.com/rpherbig/dr-scripts) suite of scripts.

Copy the data logging script to your lich scripts directory and run it. You do not need to trust it
```
cp ~/revenant/dash/revenant.lic ~/lich/scripts
# Do the following in game
;revenant
# Recommended
;e autostart('revenant')
```

#### Run the app
You need to have activated the virtual or conda environment beforehand (See the above steps 'With conda' or 'With venv' for the appropriate command)
```
python dash/app.py
```
